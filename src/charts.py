"""
Chart Generator for Sprint Health Agent
Generates Burndown and Burnup charts with scope change tracking
"""
import json
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

from .models import SprintInfo, SprintMetrics, Phase
from .utils import HISTORY_DIR


@dataclass
class ChartDataPoint:
    """Single data point for charts"""
    date: str
    day_number: int
    completed_points: float
    remaining_points: float
    total_scope: float
    ideal_remaining: float
    ideal_completed: float


@dataclass
class ChartData:
    """Complete chart data for rendering"""
    sprint_name: str
    start_date: str
    end_date: str
    total_days: int
    data_points: List[ChartDataPoint]
    scope_changes: List[Dict[str, Any]]
    current_day: int
    chart_type: str  # "burndown", "burnup", "both"


class ChartGenerator:
    """
    Generates Burndown and Burnup chart data.

    Burndown vs Burnup:
    ------------------

    BURNDOWN CHART:
    - Shows REMAINING work over time
    - Y-axis starts at total story points, goes down to zero
    - Simple to understand: "How much work is left?"
    - Limitation: Hides scope changes (if scope increases, line goes UP which looks bad)

    BURNUP CHART (RECOMMENDED):
    - Shows COMPLETED work over time PLUS total scope line
    - Two lines: Completed work (going up) and Total scope (may change)
    - Advantages:
      * Shows scope creep clearly (scope line goes up)
      * Shows progress AND scope changes in one view
      * Team can see they're making progress even if scope changed
      * More honest representation of sprint reality

    We generate BOTH and let the dashboard show the user's preference.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.chart_config = config.get('charts', {})
        self.show_burndown = self.chart_config.get('show_burndown', True)
        self.show_burnup = self.chart_config.get('show_burnup', True)
        self.show_scope_changes = self.chart_config.get('show_scope_changes', True)

    def generate_chart_data(
        self,
        sprint_info: SprintInfo,
        metrics: SprintMetrics,
        historical_snapshots: List[Dict[str, Any]]
    ) -> ChartData:
        """
        Generate chart data from sprint info and historical snapshots.

        Args:
            sprint_info: Current sprint information
            metrics: Current sprint metrics
            historical_snapshots: Daily snapshots of sprint progress

        Returns:
            ChartData object for rendering charts
        """
        total_days = sprint_info.total_days
        start_date = sprint_info.start_date
        end_date = sprint_info.end_date

        # Initial scope (from first snapshot or current)
        if historical_snapshots:
            initial_scope = historical_snapshots[0].get('total_points', metrics.total_story_points)
        else:
            initial_scope = metrics.total_story_points

        data_points = []
        scope_changes = []

        # Generate ideal line data
        ideal_daily_completion = metrics.total_story_points / total_days if total_days > 0 else 0

        # Process each day of the sprint
        for day_num in range(total_days + 1):
            current_date = start_date + timedelta(days=day_num)

            # Find historical data for this day
            snapshot = self._find_snapshot_for_date(historical_snapshots, current_date)

            if snapshot:
                completed = snapshot.get('completed_points', 0)
                total_scope = snapshot.get('total_points', metrics.total_story_points)
                remaining = total_scope - completed
            elif day_num == 0:
                # First day - no progress yet
                completed = 0
                total_scope = initial_scope
                remaining = total_scope
            elif current_date <= date.today():
                # Past day with no snapshot - interpolate or use last known
                prev_point = data_points[-1] if data_points else None
                if prev_point:
                    completed = prev_point.completed_points
                    total_scope = prev_point.total_scope
                    remaining = prev_point.remaining_points
                else:
                    completed = 0
                    total_scope = initial_scope
                    remaining = total_scope
            else:
                # Future day - no data yet
                completed = None
                total_scope = metrics.total_story_points
                remaining = None

            # Calculate ideal values
            ideal_completed = ideal_daily_completion * day_num
            ideal_remaining = metrics.total_story_points - ideal_completed

            data_points.append(ChartDataPoint(
                date=current_date.isoformat(),
                day_number=day_num,
                completed_points=completed,
                remaining_points=remaining,
                total_scope=total_scope,
                ideal_remaining=round(ideal_remaining, 1),
                ideal_completed=round(ideal_completed, 1)
            ))

            # Detect scope changes
            if day_num > 0 and completed is not None:
                prev_scope = data_points[-2].total_scope if len(data_points) > 1 else initial_scope
                if prev_scope and total_scope != prev_scope:
                    scope_changes.append({
                        'date': current_date.isoformat(),
                        'day_number': day_num,
                        'previous_scope': prev_scope,
                        'new_scope': total_scope,
                        'change': total_scope - prev_scope,
                        'change_type': 'increase' if total_scope > prev_scope else 'decrease'
                    })

        return ChartData(
            sprint_name=sprint_info.name,
            start_date=start_date.isoformat() if start_date else '',
            end_date=end_date.isoformat() if end_date else '',
            total_days=total_days,
            data_points=data_points,
            scope_changes=scope_changes,
            current_day=sprint_info.days_elapsed,
            chart_type=self.chart_config.get('type', 'both')
        )

    def _find_snapshot_for_date(
        self,
        snapshots: List[Dict[str, Any]],
        target_date: date
    ) -> Optional[Dict[str, Any]]:
        """Find snapshot for a specific date"""
        target_str = target_date.isoformat()

        for snapshot in snapshots:
            snapshot_date = snapshot.get('date', '')[:10]  # Get date part only
            if snapshot_date == target_str:
                return snapshot

        return None

    def to_chart_js_data(self, chart_data: ChartData) -> Dict[str, Any]:
        """
        Convert ChartData to Chart.js compatible format.

        Returns data structure ready for Chart.js rendering.
        """
        labels = [f"Day {dp.day_number}" for dp in chart_data.data_points]
        dates = [dp.date for dp in chart_data.data_points]

        # Burndown data
        burndown_actual = [
            dp.remaining_points for dp in chart_data.data_points
        ]
        burndown_ideal = [
            dp.ideal_remaining for dp in chart_data.data_points
        ]

        # Burnup data
        burnup_completed = [
            dp.completed_points for dp in chart_data.data_points
        ]
        burnup_ideal = [
            dp.ideal_completed for dp in chart_data.data_points
        ]
        burnup_scope = [
            dp.total_scope for dp in chart_data.data_points
        ]

        return {
            'labels': labels,
            'dates': dates,
            'current_day': chart_data.current_day,
            'burndown': {
                'actual': burndown_actual,
                'ideal': burndown_ideal,
                'title': 'Sprint Burndown',
                'y_label': 'Remaining Story Points'
            },
            'burnup': {
                'completed': burnup_completed,
                'ideal': burnup_ideal,
                'scope': burnup_scope,
                'title': 'Sprint Burnup',
                'y_label': 'Story Points'
            },
            'scope_changes': chart_data.scope_changes,
            'metadata': {
                'sprint_name': chart_data.sprint_name,
                'start_date': chart_data.start_date,
                'end_date': chart_data.end_date,
                'total_days': chart_data.total_days
            }
        }

    def generate_ascii_burndown(self, chart_data: ChartData, width: int = 50, height: int = 15) -> str:
        """
        Generate ASCII art burndown chart for terminal display.
        """
        points = [dp for dp in chart_data.data_points if dp.remaining_points is not None]

        if not points:
            return "No data available for chart"

        max_val = max(dp.total_scope for dp in points)
        min_val = 0

        # Build the chart
        chart_lines = []

        # Title
        chart_lines.append(f"📉 BURNDOWN CHART - {chart_data.sprint_name}")
        chart_lines.append("=" * (width + 10))

        # Y-axis labels and chart area
        for row in range(height, -1, -1):
            y_val = min_val + (max_val - min_val) * row / height
            y_label = f"{y_val:5.0f} │"

            line = ""
            for i, dp in enumerate(points):
                col_pos = int(i * (width - 1) / max(len(points) - 1, 1))

                # Actual value
                if dp.remaining_points is not None:
                    actual_row = int((dp.remaining_points - min_val) / (max_val - min_val) * height) if max_val > min_val else 0
                    if actual_row == row:
                        line += "●"
                    else:
                        line += " "
                else:
                    line += " "

            chart_lines.append(y_label + line.ljust(width))

        # X-axis
        chart_lines.append("      └" + "─" * width)

        # X-axis labels
        x_labels = "       "
        for i in range(0, len(points), max(1, len(points) // 5)):
            x_labels += f"D{points[i].day_number}".ljust(width // 5)
        chart_lines.append(x_labels)

        # Legend
        chart_lines.append("")
        chart_lines.append("● Actual remaining work")

        return "\n".join(chart_lines)

    def generate_ascii_burnup(self, chart_data: ChartData, width: int = 50, height: int = 15) -> str:
        """
        Generate ASCII art burnup chart for terminal display.
        """
        points = [dp for dp in chart_data.data_points if dp.completed_points is not None]

        if not points:
            return "No data available for chart"

        max_val = max(dp.total_scope for dp in points)
        min_val = 0

        chart_lines = []

        # Title
        chart_lines.append(f"📈 BURNUP CHART - {chart_data.sprint_name}")
        chart_lines.append("=" * (width + 10))

        # Y-axis labels and chart area
        for row in range(height, -1, -1):
            y_val = min_val + (max_val - min_val) * row / height
            y_label = f"{y_val:5.0f} │"

            line = ""
            for i, dp in enumerate(points):
                # Scope line
                scope_row = int((dp.total_scope - min_val) / (max_val - min_val) * height) if max_val > min_val else 0
                # Completed line
                completed_row = int((dp.completed_points - min_val) / (max_val - min_val) * height) if max_val > min_val and dp.completed_points else 0

                if scope_row == row and completed_row == row:
                    line += "◆"  # Both lines intersect
                elif scope_row == row:
                    line += "─"  # Scope line
                elif completed_row == row:
                    line += "●"  # Completed line
                else:
                    line += " "

            chart_lines.append(y_label + line.ljust(width))

        # X-axis
        chart_lines.append("      └" + "─" * width)

        # X-axis labels
        x_labels = "       "
        step = max(1, len(points) // 5)
        for i in range(0, len(points), step):
            x_labels += f"D{points[i].day_number}".ljust(width // 5)
        chart_lines.append(x_labels)

        # Legend
        chart_lines.append("")
        chart_lines.append("● Completed work    ─ Total scope")

        # Show scope changes if any
        if chart_data.scope_changes:
            chart_lines.append("")
            chart_lines.append("⚠️ Scope changes detected:")
            for sc in chart_data.scope_changes[:3]:
                direction = "↑" if sc['change'] > 0 else "↓"
                chart_lines.append(f"   Day {sc['day_number']}: {direction} {abs(sc['change'])} SP")

        return "\n".join(chart_lines)

    def load_historical_snapshots(self, sprint_id: int) -> List[Dict[str, Any]]:
        """Load historical daily snapshots for a sprint"""
        snapshots = []

        if not HISTORY_DIR.exists():
            return snapshots

        for filepath in sorted(HISTORY_DIR.glob(f"sprint_{sprint_id}_*.json")):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    snapshots.append(data)
            except (json.JSONDecodeError, IOError):
                continue

        return snapshots


def explain_burndown_vs_burnup() -> str:
    """
    Returns an explanation of burndown vs burnup charts.
    Useful for documentation and help commands.
    """
    return """
📊 BURNDOWN vs BURNUP CHARTS - Which Should You Use?
═══════════════════════════════════════════════════════

BURNDOWN CHART 📉
─────────────────
What it shows: REMAINING work over time
Visual: Starts high (total work), ideally goes down to zero

Pros:
  ✓ Simple to understand
  ✓ Clear "are we done?" indicator
  ✓ Traditional agile metric

Cons:
  ✗ Hides scope changes (scope increase looks like negative progress)
  ✗ Can be demoralizing if scope changes often
  ✗ Doesn't show HOW MUCH work was done, only what's left


BURNUP CHART 📈 (RECOMMENDED)
─────────────────────────────
What it shows: TWO lines - Completed work AND Total scope
Visual: Completed work goes up, scope line shows total (may also go up)

Pros:
  ✓ Shows progress clearly (work goes UP = good)
  ✓ Makes scope creep VISIBLE (scope line moves up)
  ✓ Team sees they're making progress even if scope changed
  ✓ More honest picture of what's happening
  ✓ Better for stakeholder communication

Cons:
  ✗ Slightly more complex (two lines to track)
  ✗ Less familiar to some teams


OUR RECOMMENDATION:
───────────────────
Use BURNUP charts because:
1. They show the truth about scope changes
2. Teams stay motivated seeing completed work go UP
3. Stakeholders understand why sprint might miss target

Example scenario:
- Team completes 30 SP
- But scope increased by 10 SP mid-sprint
- Burndown: Shows team is "behind" (remaining work went up)
- Burnup: Shows team completed 30 SP AND scope increased (honest picture)

We provide BOTH so you can choose what works for your team!
"""

