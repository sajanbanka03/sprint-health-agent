"""
Scope Tracker Module for Sprint Health Agent
Detects scope creep by comparing current sprint vs. Day 1 snapshot

Features:
- Capture sprint snapshot at Day 1 (or on demand)
- Detect items added/removed after sprint start
- Calculate scope change percentage
- Predict impact on sprint goal probability
- Track sprint start timing (on time/delayed)

Author: Sajan Banka
Created: April 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import json
import logging
import os
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .models import SprintIssue, SprintInfo, SprintMetrics, Phase

logger = logging.getLogger(__name__)

# Directory for storing sprint snapshots
SNAPSHOTS_DIR = Path(__file__).parent.parent / "data" / "sprint_snapshots"


@dataclass
class SprintSnapshot:
    """Snapshot of sprint state at a point in time"""
    sprint_id: int
    sprint_name: str
    team_name: str
    captured_at: str  # ISO datetime string
    capture_day: int  # Day number in sprint (1 = first day)

    # Sprint timing
    planned_start_date: str  # ISO date
    actual_start_date: str   # When snapshot was first captured
    sprint_started_on_time: Optional[bool]  # None = not started yet, True = on time, False = late
    days_late: int  # 0 if on time, positive if late

    # Scope data
    total_issues: int
    total_story_points: float
    issue_keys: List[str]

    # Detailed issue data for comparison
    issues_data: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SprintSnapshot':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class ScopeChange:
    """Represents a scope change (item added or removed)"""
    issue_key: str
    summary: str
    story_points: float
    assignee: Optional[str]
    change_type: str  # "added" or "removed"
    phase: str


@dataclass
class ScopeCreepReport:
    """Complete scope creep analysis report"""
    sprint_id: int
    sprint_name: str
    team_name: str
    analysis_time: datetime

    # Snapshot info
    has_baseline: bool
    baseline_captured_at: Optional[str]
    baseline_day: Optional[int]

    # Sprint timing
    sprint_started_on_time: Optional[bool]  # None = not started yet, True = on time, False = late
    days_late: int
    planned_start_date: Optional[str]
    actual_start_date: Optional[str]

    # Original scope (from baseline)
    original_issues: int
    original_story_points: float

    # Current scope
    current_issues: int
    current_story_points: float

    # Changes
    items_added: List[ScopeChange]
    items_removed: List[ScopeChange]

    # Calculated metrics
    net_issues_change: int
    net_sp_change: float
    scope_change_percentage: float

    # Impact analysis
    original_goal_probability: float
    current_goal_probability: float
    probability_impact: float  # negative means reduced probability

    # Recommendations
    status: str  # "healthy", "warning", "critical"
    recommendation: str

    @property
    def added_count(self) -> int:
        return len(self.items_added)

    @property
    def removed_count(self) -> int:
        return len(self.items_removed)

    @property
    def added_sp(self) -> float:
        return sum(i.story_points for i in self.items_added)

    @property
    def removed_sp(self) -> float:
        return sum(i.story_points for i in self.items_removed)


class ScopeTracker:
    """
    Tracks scope changes throughout a sprint.

    Usage:
        tracker = ScopeTracker(config)

        # Capture baseline on Day 1
        tracker.capture_baseline(sprint_info, issues, team_name)

        # Later, analyze scope creep
        report = tracker.analyze_scope_creep(sprint_info, issues, metrics, team_name)
    """

    # Thresholds
    WARNING_THRESHOLD = 10  # 10% scope increase = warning
    CRITICAL_THRESHOLD = 20  # 20% scope increase = critical

    def __init__(self, config: Dict[str, Any]):
        """Initialize scope tracker"""
        self.config = config

        # Ensure snapshots directory exists
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        # Allow config overrides
        scope_config = config.get('scope_tracking', {})
        self.warning_threshold = scope_config.get('warning_threshold', self.WARNING_THRESHOLD)
        self.critical_threshold = scope_config.get('critical_threshold', self.CRITICAL_THRESHOLD)
        self.auto_capture_day = scope_config.get('auto_capture_day', 1)  # Day 1 by default

    def _get_snapshot_path(self, team_name: str, sprint_id: int) -> Path:
        """Get file path for a sprint snapshot"""
        safe_team_name = team_name.replace(" ", "_").lower()
        return SNAPSHOTS_DIR / f"{safe_team_name}_sprint_{sprint_id}_baseline.json"

    def has_baseline(self, team_name: str, sprint_id: int) -> bool:
        """Check if baseline snapshot exists for a sprint"""
        return self._get_snapshot_path(team_name, sprint_id).exists()

    def capture_baseline(
        self,
        sprint_info: SprintInfo,
        issues: List[SprintIssue],
        team_name: str,
        force: bool = False
    ) -> SprintSnapshot:
        """
        Capture baseline snapshot of sprint scope.

        Should be called on Day 1 of the sprint or when sprint starts.

        Args:
            sprint_info: Current sprint information
            issues: All issues in the sprint
            team_name: Team name for identification
            force: If True, overwrite existing baseline

        Returns:
            SprintSnapshot of the baseline
        """
        snapshot_path = self._get_snapshot_path(team_name, sprint_info.id)

        # Check if baseline already exists
        if snapshot_path.exists() and not force:
            logger.info(f"Baseline already exists for {team_name} sprint {sprint_info.id}")
            return self.load_baseline(team_name, sprint_info.id)

        # Determine sprint timing
        today = date.today()
        planned_start = sprint_info.start_date

        if planned_start:
            # Check if sprint hasn't started yet
            if today < planned_start:
                # Sprint not started yet
                sprint_started_on_time = True  # Will check again when it starts
                days_late = 0
                days_early = (planned_start - today).days
            else:
                # Sprint has started
                days_late = (today - planned_start).days
                sprint_started_on_time = days_late == 0
                days_early = 0
        else:
            sprint_started_on_time = True
            days_late = 0
            days_early = 0

        # Create snapshot
        snapshot = SprintSnapshot(
            sprint_id=sprint_info.id,
            sprint_name=sprint_info.name,
            team_name=team_name,
            captured_at=datetime.now().isoformat(),
            capture_day=sprint_info.days_elapsed or 1,
            planned_start_date=planned_start.isoformat() if planned_start else "",
            actual_start_date=today.isoformat(),
            sprint_started_on_time=sprint_started_on_time,
            days_late=days_late,
            total_issues=len(issues),
            total_story_points=sum(i.story_points for i in issues),
            issue_keys=[i.key for i in issues],
            issues_data=[
                {
                    'key': i.key,
                    'summary': i.summary,
                    'story_points': i.story_points,
                    'assignee': i.assignee,
                    'phase': i.phase.value,
                    'status': i.status
                }
                for i in issues
            ]
        )

        # Save snapshot
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        logger.info(f"Captured baseline for {team_name} sprint {sprint_info.id}: "
                   f"{snapshot.total_issues} issues, {snapshot.total_story_points} SP")

        return snapshot

    def load_baseline(self, team_name: str, sprint_id: int) -> Optional[SprintSnapshot]:
        """Load existing baseline snapshot"""
        snapshot_path = self._get_snapshot_path(team_name, sprint_id)

        if not snapshot_path.exists():
            return None

        try:
            with open(snapshot_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return SprintSnapshot.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading baseline: {e}")
            return None

    def should_auto_capture(self, sprint_info: SprintInfo, team_name: str) -> bool:
        """
        Check if we should automatically capture baseline.

        Returns True if:
        - No baseline exists
        - Sprint has started (day >= 1)
        - Current day is within auto_capture window
        """
        # Already have baseline?
        if self.has_baseline(team_name, sprint_info.id):
            return False

        # Sprint started?
        if sprint_info.days_elapsed < 1:
            return False

        # Within capture window (typically Day 1, but allow Day 2 for late starts)
        return sprint_info.days_elapsed <= max(2, self.auto_capture_day)

    def analyze_scope_creep(
        self,
        sprint_info: SprintInfo,
        current_issues: List[SprintIssue],
        metrics: SprintMetrics,
        team_name: str,
        goal_probability: float = 0.0
    ) -> ScopeCreepReport:
        """
        Analyze scope creep by comparing current state to baseline.

        Args:
            sprint_info: Current sprint information
            current_issues: Current list of issues in sprint
            metrics: Current sprint metrics
            team_name: Team name
            goal_probability: Current Monte Carlo probability

        Returns:
            ScopeCreepReport with full analysis
        """
        # Auto-capture baseline if needed
        if self.should_auto_capture(sprint_info, team_name):
            self.capture_baseline(sprint_info, current_issues, team_name)

        # Load baseline
        baseline = self.load_baseline(team_name, sprint_info.id)

        if not baseline:
            # No baseline yet - return minimal report
            return self._create_no_baseline_report(
                sprint_info, current_issues, metrics, team_name, goal_probability
            )

        # Compare current to baseline
        current_keys = set(i.key for i in current_issues)
        baseline_keys = set(baseline.issue_keys)

        # Find added and removed items
        added_keys = current_keys - baseline_keys
        removed_keys = baseline_keys - current_keys

        # Build change lists
        items_added = []
        for issue in current_issues:
            if issue.key in added_keys:
                items_added.append(ScopeChange(
                    issue_key=issue.key,
                    summary=issue.summary,
                    story_points=issue.story_points,
                    assignee=issue.assignee,
                    change_type="added",
                    phase=issue.phase.value
                ))

        items_removed = []
        baseline_lookup = {d['key']: d for d in baseline.issues_data}
        for key in removed_keys:
            if key in baseline_lookup:
                item = baseline_lookup[key]
                items_removed.append(ScopeChange(
                    issue_key=item['key'],
                    summary=item['summary'],
                    story_points=item['story_points'],
                    assignee=item.get('assignee'),
                    change_type="removed",
                    phase=item.get('phase', 'unknown')
                ))

        # Calculate metrics
        current_issues_count = len(current_issues)
        current_sp = sum(i.story_points for i in current_issues)

        added_sp = sum(i.story_points for i in items_added)
        removed_sp = sum(i.story_points for i in items_removed)
        net_sp_change = added_sp - removed_sp
        net_issues_change = len(items_added) - len(items_removed)

        # Calculate scope change percentage (based on SP)
        if baseline.total_story_points > 0:
            scope_change_pct = (net_sp_change / baseline.total_story_points) * 100
        else:
            scope_change_pct = 0.0

        # Estimate impact on goal probability
        # Simple model: for every 10% scope increase, reduce probability by ~8%
        if scope_change_pct > 0:
            probability_impact = -(scope_change_pct * 0.8)
        else:
            probability_impact = abs(scope_change_pct) * 0.5  # Reduction helps, but less

        # Original probability (estimate from baseline)
        original_probability = min(100, goal_probability - probability_impact)

        # Determine status
        if abs(scope_change_pct) >= self.critical_threshold:
            status = "critical"
            if scope_change_pct > 0:
                recommendation = (
                    f"🚨 CRITICAL: Scope has increased by {scope_change_pct:.0f}% since sprint start. "
                    f"{len(items_added)} items ({added_sp:.0f} SP) added. "
                    "Immediate scope negotiation recommended - sprint goal at high risk."
                )
            else:
                recommendation = (
                    f"📉 Significant scope reduction ({abs(scope_change_pct):.0f}%). "
                    f"{len(items_removed)} items ({removed_sp:.0f} SP) removed. "
                    "Review with PO if descoping was intentional."
                )
        elif abs(scope_change_pct) >= self.warning_threshold:
            status = "warning"
            if scope_change_pct > 0:
                recommendation = (
                    f"⚠️ Scope has increased by {scope_change_pct:.0f}% since sprint start. "
                    f"{len(items_added)} items added. Monitor closely and consider descoping lower priority items."
                )
            else:
                recommendation = (
                    f"📉 Scope reduced by {abs(scope_change_pct):.0f}%. "
                    "Team may have more capacity available."
                )
        else:
            status = "healthy"
            if net_sp_change == 0:
                recommendation = "✅ Scope is stable - no significant changes since sprint start."
            else:
                recommendation = f"✅ Minor scope adjustment ({scope_change_pct:+.0f}%). Within acceptable range."

        return ScopeCreepReport(
            sprint_id=sprint_info.id,
            sprint_name=sprint_info.name,
            team_name=team_name,
            analysis_time=datetime.now(),
            has_baseline=True,
            baseline_captured_at=baseline.captured_at,
            baseline_day=baseline.capture_day,
            sprint_started_on_time=baseline.sprint_started_on_time,
            days_late=baseline.days_late,
            planned_start_date=baseline.planned_start_date,
            actual_start_date=baseline.actual_start_date,
            original_issues=baseline.total_issues,
            original_story_points=baseline.total_story_points,
            current_issues=current_issues_count,
            current_story_points=current_sp,
            items_added=items_added,
            items_removed=items_removed,
            net_issues_change=net_issues_change,
            net_sp_change=net_sp_change,
            scope_change_percentage=round(scope_change_pct, 1),
            original_goal_probability=round(original_probability, 1),
            current_goal_probability=round(goal_probability, 1),
            probability_impact=round(probability_impact, 1),
            status=status,
            recommendation=recommendation
        )

    def _create_no_baseline_report(
        self,
        sprint_info: SprintInfo,
        issues: List[SprintIssue],
        metrics: SprintMetrics,
        team_name: str,
        goal_probability: float
    ) -> ScopeCreepReport:
        """Create report when no baseline exists yet"""
        current_sp = sum(i.story_points for i in issues)

        # Determine sprint timing
        today = date.today()
        planned_start = sprint_info.start_date
        sprint_not_started = False

        if planned_start:
            if today < planned_start:
                # Sprint not started yet
                sprint_not_started = True
                sprint_started_on_time = True  # TBD when it starts
                days_late = 0
            else:
                days_late = (today - planned_start).days
                sprint_started_on_time = days_late == 0
        else:
            sprint_started_on_time = True
            days_late = 0

        if sprint_not_started or sprint_info.days_elapsed < 1:
            recommendation = "🔄 Sprint not yet started. Baseline will be captured on Day 1."
            # Don't mark as on_time yet - sprint hasn't started
            if sprint_not_started:
                sprint_started_on_time = None  # Indicate not yet determined
        else:
            recommendation = (
                f"📸 Baseline captured today (Day {sprint_info.days_elapsed}). "
                "Scope changes will be tracked from this point."
            )
            # Auto-capture now
            self.capture_baseline(sprint_info, issues, team_name)

        return ScopeCreepReport(
            sprint_id=sprint_info.id,
            sprint_name=sprint_info.name,
            team_name=team_name,
            analysis_time=datetime.now(),
            has_baseline=False,
            baseline_captured_at=None,
            baseline_day=None,
            sprint_started_on_time=sprint_started_on_time,
            days_late=days_late,
            planned_start_date=planned_start.isoformat() if planned_start else None,
            actual_start_date=today.isoformat(),
            original_issues=len(issues),
            original_story_points=current_sp,
            current_issues=len(issues),
            current_story_points=current_sp,
            items_added=[],
            items_removed=[],
            net_issues_change=0,
            net_sp_change=0,
            scope_change_percentage=0,
            original_goal_probability=goal_probability,
            current_goal_probability=goal_probability,
            probability_impact=0,
            status="healthy",
            recommendation=recommendation
        )

    def get_scope_summary(self, report: ScopeCreepReport) -> Dict[str, Any]:
        """
        Get a summary of scope changes suitable for display.

        Returns:
            Dictionary with display-ready data
        """
        # Determine start timing display
        if report.sprint_started_on_time is None:
            start_timing_display = "🔄 Not Started Yet"
        elif report.sprint_started_on_time:
            start_timing_display = "✅ On Time"
        else:
            start_timing_display = f"⚠️ {report.days_late} day(s) late"

        return {
            'has_baseline': report.has_baseline,
            'sprint_started_on_time': report.sprint_started_on_time,
            'days_late': report.days_late,
            'start_timing_display': start_timing_display,
            'original': {
                'issues': report.original_issues,
                'story_points': report.original_story_points
            },
            'current': {
                'issues': report.current_issues,
                'story_points': report.current_story_points
            },
            'changes': {
                'added_count': report.added_count,
                'added_sp': report.added_sp,
                'removed_count': report.removed_count,
                'removed_sp': report.removed_sp,
                'net_issues': report.net_issues_change,
                'net_sp': report.net_sp_change,
                'percentage': report.scope_change_percentage
            },
            'impact': {
                'original_probability': report.original_goal_probability,
                'current_probability': report.current_goal_probability,
                'probability_change': report.probability_impact
            },
            'status': report.status,
            'status_emoji': (
                "✅" if report.status == "healthy"
                else "⚠️" if report.status == "warning"
                else "🚨"
            ),
            'recommendation': report.recommendation,
            'items_added': [
                {
                    'key': i.issue_key,
                    'summary': i.summary,
                    'story_points': i.story_points,
                    'assignee': i.assignee
                }
                for i in report.items_added
            ],
            'items_removed': [
                {
                    'key': i.issue_key,
                    'summary': i.summary,
                    'story_points': i.story_points
                }
                for i in report.items_removed
            ]
        }

    def delete_baseline(self, team_name: str, sprint_id: int) -> bool:
        """
        Delete baseline snapshot for a sprint.
        Useful for resetting or re-capturing.
        """
        snapshot_path = self._get_snapshot_path(team_name, sprint_id)

        if snapshot_path.exists():
            snapshot_path.unlink()
            logger.info(f"Deleted baseline for {team_name} sprint {sprint_id}")
            return True

        return False


# Singleton instance for global access
_scope_tracker: Optional[ScopeTracker] = None


def get_scope_tracker(config: Optional[Dict[str, Any]] = None) -> ScopeTracker:
    """Get or create singleton scope tracker instance"""
    global _scope_tracker

    if _scope_tracker is None:
        if config is None:
            raise ValueError("Config required for first initialization")
        _scope_tracker = ScopeTracker(config)

    return _scope_tracker

