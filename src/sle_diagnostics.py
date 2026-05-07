"""
Module 1: Stuck Item Diagnostic Engine (SLE-Based Risk)
Service Level Expectation based Work Item Age analysis

Features:
- Work Item Age (WIA) calculation
- Historical 85th percentile cycle time (SLE)
- Amber (>50% SLE) and Red (>85% SLE) flagging
- Aging WIP visualization data

Author: Sajan Banka
Created: May 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics

from .models import SprintIssue, SprintInfo, Phase

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level for aging work items"""
    GREEN = "green"      # Under 50% of SLE
    AMBER = "amber"      # 50-85% of SLE
    RED = "red"          # Over 85% of SLE - Critical Blockage
    CRITICAL = "critical"  # Over 100% of SLE


@dataclass
class WorkItemAge:
    """Work Item Age analysis for a single item"""
    issue_key: str
    summary: str
    assignee: Optional[str]
    status: str
    phase: str

    # Work Item Age calculation
    start_date: datetime
    current_date: datetime
    work_item_age_days: int  # WIA = (Current Date - Start Date) + 1

    # SLE comparison
    sle_days: float  # 85th percentile threshold
    sle_percentage: float  # WIA as % of SLE

    # Risk assessment
    risk_level: RiskLevel
    risk_message: str

    # Story points and priority
    story_points: float
    priority: str

    @property
    def days_until_sle(self) -> int:
        """Days remaining until SLE breach"""
        return max(0, int(self.sle_days - self.work_item_age_days))

    @property
    def over_sle_days(self) -> int:
        """Days over SLE if breached"""
        return max(0, int(self.work_item_age_days - self.sle_days))


@dataclass
class PhaseAgingStats:
    """Aging statistics for a phase"""
    phase: str
    phase_display: str
    total_items: int
    green_count: int
    amber_count: int
    red_count: int
    critical_count: int
    avg_age_days: float
    max_age_days: int
    sle_days: float
    items: List[WorkItemAge]


@dataclass
class AgingWIPReport:
    """Complete Aging WIP analysis report"""
    generated_at: datetime
    sprint_info: SprintInfo

    # Overall statistics
    total_active_items: int
    total_green: int
    total_amber: int
    total_red: int
    total_critical: int

    # SLE thresholds (85th percentile from history)
    sle_thresholds: Dict[str, float]  # phase -> days

    # Phase breakdown
    phase_stats: List[PhaseAgingStats]

    # Most critical items (sorted by risk)
    critical_items: List[WorkItemAge]
    amber_items: List[WorkItemAge]

    # Historical data used
    historical_sprints_analyzed: int
    avg_cycle_time: float
    percentile_85_cycle_time: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON"""
        return {
            'generated_at': self.generated_at.isoformat(),
            'sprint': {
                'id': self.sprint_info.id,
                'name': self.sprint_info.name,
                'day': self.sprint_info.days_elapsed,
                'total_days': self.sprint_info.total_days
            },
            'summary': {
                'total_active_items': self.total_active_items,
                'risk_distribution': {
                    'green': self.total_green,
                    'amber': self.total_amber,
                    'red': self.total_red,
                    'critical': self.total_critical
                },
                'health_percentage': round(
                    (self.total_green / self.total_active_items * 100)
                    if self.total_active_items > 0 else 100, 1
                )
            },
            'sle': {
                'thresholds': self.sle_thresholds,
                'historical_sprints_analyzed': self.historical_sprints_analyzed,
                'avg_cycle_time': round(self.avg_cycle_time, 1),
                'percentile_85': round(self.percentile_85_cycle_time, 1)
            },
            'phase_stats': [
                {
                    'phase': ps.phase,
                    'display_name': ps.phase_display,
                    'total_items': ps.total_items,
                    'green': ps.green_count,
                    'amber': ps.amber_count,
                    'red': ps.red_count,
                    'critical': ps.critical_count,
                    'avg_age_days': round(ps.avg_age_days, 1),
                    'max_age_days': ps.max_age_days,
                    'sle_days': round(ps.sle_days, 1)
                }
                for ps in self.phase_stats
            ],
            'critical_items': [
                {
                    'key': item.issue_key,
                    'summary': item.summary,
                    'assignee': item.assignee,
                    'status': item.status,
                    'phase': item.phase,
                    'age_days': item.work_item_age_days,
                    'sle_days': round(item.sle_days, 1),
                    'sle_percentage': round(item.sle_percentage, 1),
                    'risk_level': item.risk_level.value,
                    'risk_message': item.risk_message,
                    'over_sle_days': item.over_sle_days,
                    'story_points': item.story_points
                }
                for item in self.critical_items[:10]
            ],
            'amber_items': [
                {
                    'key': item.issue_key,
                    'summary': item.summary,
                    'assignee': item.assignee,
                    'status': item.status,
                    'age_days': item.work_item_age_days,
                    'sle_percentage': round(item.sle_percentage, 1),
                    'days_until_sle': item.days_until_sle,
                    'story_points': item.story_points
                }
                for item in self.amber_items[:10]
            ]
        }


class SLEDiagnosticsEngine:
    """
    Service Level Expectation Diagnostics Engine

    Analyzes work item age against historical cycle time thresholds
    to identify items at risk of missing SLE.
    """

    # Default SLE thresholds (days) by phase if no historical data
    DEFAULT_SLE_THRESHOLDS = {
        Phase.IN_ANALYSIS: 3,
        Phase.IN_DEV: 5,
        Phase.READY_FOR_SIT: 2,
        Phase.IN_SIT: 4,
        Phase.IN_TPO_REVIEW: 2,
    }

    # Phase display names
    PHASE_DISPLAY_NAMES = {
        Phase.BACKLOG: "Backlog",
        Phase.IN_ANALYSIS: "In Analysis",
        Phase.IN_DEV: "In Development",
        Phase.READY_FOR_SIT: "Ready for SIT",
        Phase.IN_SIT: "In SIT",
        Phase.IN_TPO_REVIEW: "In TPO Review",
        Phase.DONE: "Done",
        Phase.UNKNOWN: "Unknown"
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sle_thresholds: Dict[Phase, float] = {}

    def analyze_aging_wip(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        historical_data: List[Dict[str, Any]] = None
    ) -> AgingWIPReport:
        """
        Analyze all work items for aging risk.

        Args:
            issues: Current sprint issues
            sprint_info: Sprint information
            historical_data: Historical sprint data for SLE calculation

        Returns:
            AgingWIPReport with full analysis
        """
        # Calculate SLE thresholds from history
        self._calculate_sle_thresholds(historical_data or [])

        # Get active items (not done, not backlog)
        active_issues = [
            i for i in issues
            if i.phase not in [Phase.DONE, Phase.BACKLOG]
        ]

        # Analyze each item
        work_item_ages: List[WorkItemAge] = []
        phase_items: Dict[Phase, List[WorkItemAge]] = {}

        for issue in active_issues:
            wia = self._calculate_work_item_age(issue)
            work_item_ages.append(wia)

            if issue.phase not in phase_items:
                phase_items[issue.phase] = []
            phase_items[issue.phase].append(wia)

        # Calculate phase statistics
        phase_stats = []
        for phase, items in phase_items.items():
            stats = self._calculate_phase_stats(phase, items)
            phase_stats.append(stats)

        # Sort phase stats by phase order
        phase_order = [
            Phase.IN_ANALYSIS, Phase.IN_DEV, Phase.READY_FOR_SIT,
            Phase.IN_SIT, Phase.IN_TPO_REVIEW
        ]
        phase_stats.sort(key=lambda x: phase_order.index(Phase(x.phase))
                        if Phase(x.phase) in phase_order else 99)

        # Categorize items by risk
        critical_items = [w for w in work_item_ages if w.risk_level in [RiskLevel.RED, RiskLevel.CRITICAL]]
        amber_items = [w for w in work_item_ages if w.risk_level == RiskLevel.AMBER]

        # Sort by risk (highest first)
        critical_items.sort(key=lambda x: -x.sle_percentage)
        amber_items.sort(key=lambda x: -x.sle_percentage)

        # Count totals
        total_green = len([w for w in work_item_ages if w.risk_level == RiskLevel.GREEN])
        total_amber = len(amber_items)
        total_red = len([w for w in critical_items if w.risk_level == RiskLevel.RED])
        total_critical = len([w for w in critical_items if w.risk_level == RiskLevel.CRITICAL])

        # Calculate historical stats
        cycle_times = self._extract_cycle_times(historical_data or [])
        avg_cycle_time = statistics.mean(cycle_times) if cycle_times else 5.0
        p85_cycle_time = self._percentile(cycle_times, 85) if cycle_times else 7.0

        return AgingWIPReport(
            generated_at=datetime.now(),
            sprint_info=sprint_info,
            total_active_items=len(active_issues),
            total_green=total_green,
            total_amber=total_amber,
            total_red=total_red,
            total_critical=total_critical,
            sle_thresholds={
                self.PHASE_DISPLAY_NAMES.get(p, p.value): t
                for p, t in self.sle_thresholds.items()
            },
            phase_stats=phase_stats,
            critical_items=critical_items,
            amber_items=amber_items,
            historical_sprints_analyzed=len(historical_data) if historical_data else 0,
            avg_cycle_time=avg_cycle_time,
            percentile_85_cycle_time=p85_cycle_time
        )

    def _calculate_sle_thresholds(self, historical_data: List[Dict[str, Any]]) -> None:
        """Calculate 85th percentile thresholds from historical data"""
        if not historical_data:
            # Use defaults
            self.sle_thresholds = self.DEFAULT_SLE_THRESHOLDS.copy()
            return

        # Extract cycle times by phase from historical data
        phase_cycle_times: Dict[Phase, List[float]] = {}

        for sprint_data in historical_data:
            # If historical data contains phase-level cycle times
            if 'phase_cycle_times' in sprint_data:
                for phase_str, times in sprint_data['phase_cycle_times'].items():
                    try:
                        phase = Phase(phase_str)
                        if phase not in phase_cycle_times:
                            phase_cycle_times[phase] = []
                        phase_cycle_times[phase].extend(times)
                    except ValueError:
                        continue

        # Calculate 85th percentile for each phase
        for phase in self.DEFAULT_SLE_THRESHOLDS.keys():
            if phase in phase_cycle_times and phase_cycle_times[phase]:
                self.sle_thresholds[phase] = self._percentile(
                    phase_cycle_times[phase], 85
                )
            else:
                self.sle_thresholds[phase] = self.DEFAULT_SLE_THRESHOLDS[phase]

    def _calculate_work_item_age(self, issue: SprintIssue) -> WorkItemAge:
        """Calculate Work Item Age for a single issue"""
        # Work Item Age = (Current Date - Start Date) + 1
        start_date = issue.status_change_date or issue.created_date
        current_date = datetime.now()
        wia_days = (current_date - start_date).days + 1

        # Get SLE for this phase
        sle_days = self.sle_thresholds.get(
            issue.phase,
            self.DEFAULT_SLE_THRESHOLDS.get(issue.phase, 5)
        )

        # Calculate percentage of SLE
        sle_percentage = (wia_days / sle_days * 100) if sle_days > 0 else 0

        # Determine risk level
        if sle_percentage >= 100:
            risk_level = RiskLevel.CRITICAL
            risk_message = f"CRITICAL: {wia_days - int(sle_days)} days over SLE"
        elif sle_percentage >= 85:
            risk_level = RiskLevel.RED
            risk_message = f"At risk: {int(sle_percentage)}% of SLE reached"
        elif sle_percentage >= 50:
            risk_level = RiskLevel.AMBER
            risk_message = f"Warning: {int(sle_days - wia_days)} days until SLE"
        else:
            risk_level = RiskLevel.GREEN
            risk_message = "On track"

        return WorkItemAge(
            issue_key=issue.key,
            summary=issue.summary,
            assignee=issue.assignee,
            status=issue.status,
            phase=issue.phase.value,
            start_date=start_date,
            current_date=current_date,
            work_item_age_days=wia_days,
            sle_days=sle_days,
            sle_percentage=sle_percentage,
            risk_level=risk_level,
            risk_message=risk_message,
            story_points=issue.story_points,
            priority=issue.priority
        )

    def _calculate_phase_stats(
        self,
        phase: Phase,
        items: List[WorkItemAge]
    ) -> PhaseAgingStats:
        """Calculate statistics for a phase"""
        if not items:
            return PhaseAgingStats(
                phase=phase.value,
                phase_display=self.PHASE_DISPLAY_NAMES.get(phase, phase.value),
                total_items=0,
                green_count=0,
                amber_count=0,
                red_count=0,
                critical_count=0,
                avg_age_days=0,
                max_age_days=0,
                sle_days=self.sle_thresholds.get(phase, 5),
                items=[]
            )

        ages = [i.work_item_age_days for i in items]

        return PhaseAgingStats(
            phase=phase.value,
            phase_display=self.PHASE_DISPLAY_NAMES.get(phase, phase.value),
            total_items=len(items),
            green_count=len([i for i in items if i.risk_level == RiskLevel.GREEN]),
            amber_count=len([i for i in items if i.risk_level == RiskLevel.AMBER]),
            red_count=len([i for i in items if i.risk_level == RiskLevel.RED]),
            critical_count=len([i for i in items if i.risk_level == RiskLevel.CRITICAL]),
            avg_age_days=statistics.mean(ages) if ages else 0,
            max_age_days=max(ages) if ages else 0,
            sle_days=self.sle_thresholds.get(phase, 5),
            items=items
        )

    def _extract_cycle_times(self, historical_data: List[Dict[str, Any]]) -> List[float]:
        """Extract overall cycle times from historical data"""
        cycle_times = []

        for sprint in historical_data:
            if 'completed_points' in sprint:
                # Estimate cycle time from sprint data
                # This is a rough estimation - ideally we'd have issue-level data
                avg_days = sprint.get('average_days_per_item', 5)
                if avg_days > 0:
                    cycle_times.append(avg_days)

        return cycle_times if cycle_times else [5.0]  # Default

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)

        if index == int(index):
            return sorted_data[int(index)]

        lower = sorted_data[int(index)]
        upper = sorted_data[int(index) + 1]
        fraction = index - int(index)

        return lower + (upper - lower) * fraction

    def get_visualization_data(self, report: AgingWIPReport) -> Dict[str, Any]:
        """Get data formatted for Aging WIP visualization"""
        return {
            'chart_type': 'aging_wip',
            'title': 'Aging Work In Progress',
            'subtitle': f'SLE: 85th Percentile = {report.percentile_85_cycle_time:.1f} days',
            'phases': [
                {
                    'name': ps.phase_display,
                    'total': ps.total_items,
                    'sle_threshold': ps.sle_days,
                    'distribution': {
                        'green': ps.green_count,
                        'amber': ps.amber_count,
                        'red': ps.red_count + ps.critical_count
                    },
                    'items': [
                        {
                            'key': item.issue_key,
                            'age': item.work_item_age_days,
                            'sle_pct': item.sle_percentage,
                            'risk': item.risk_level.value,
                            'assignee': item.assignee
                        }
                        for item in ps.items
                    ]
                }
                for ps in report.phase_stats
            ],
            'alert_count': report.total_red + report.total_critical,
            'warning_count': report.total_amber
        }

