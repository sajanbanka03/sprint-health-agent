"""
Data models for Sprint Health Agent
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Optional
from enum import Enum


class Phase(Enum):
    """Sprint phases that a ticket can be in"""
    BACKLOG = "backlog"
    IN_ANALYSIS = "in_analysis"
    IN_DEV = "in_dev"
    READY_FOR_SIT = "ready_for_sit"
    IN_SIT = "in_sit"
    IN_TPO_REVIEW = "in_tpo_review"
    DONE = "done"
    UNKNOWN = "unknown"


class HealthStatus(Enum):
    """Overall health status of the sprint"""
    HEALTHY = "healthy"          # > 80% completion probability
    AT_RISK = "at_risk"          # 50-80% completion probability
    CRITICAL = "critical"        # < 50% completion probability


@dataclass
class SprintIssue:
    """Represents a single issue/ticket in the sprint"""
    key: str
    summary: str
    status: str
    phase: Phase
    assignee: Optional[str]
    assignee_email: Optional[str]
    story_points: float
    issue_type: str
    priority: str
    created_date: datetime
    updated_date: datetime
    status_change_date: Optional[datetime]
    days_in_current_status: int
    is_stuck: bool = False
    stuck_threshold: int = 0
    labels: List[str] = field(default_factory=list)

    @property
    def days_overdue(self) -> int:
        """How many days past the stuck threshold"""
        if self.is_stuck:
            return self.days_in_current_status - self.stuck_threshold
        return 0


@dataclass
class PhaseMetrics:
    """Metrics for a single phase"""
    phase: Phase
    phase_display_name: str
    issue_count: int
    story_points: float
    percentage_of_total: float
    stuck_count: int
    stuck_issues: List[SprintIssue] = field(default_factory=list)
    wip_limit: Optional[int] = None
    wip_exceeded: bool = False


@dataclass
class SprintInfo:
    """Basic sprint information"""
    id: int
    name: str
    state: str  # active, closed, future
    start_date: Optional[date]
    end_date: Optional[date]
    goal: Optional[str]

    @property
    def total_days(self) -> int:
        """Total number of days in the sprint"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    @property
    def days_elapsed(self) -> int:
        """Number of days since sprint started"""
        if self.start_date:
            today = date.today()
            if today < self.start_date:
                return 0
            return min((today - self.start_date).days + 1, self.total_days)
        return 0

    @property
    def days_remaining(self) -> int:
        """Number of days remaining in the sprint"""
        return max(0, self.total_days - self.days_elapsed)

    @property
    def progress_percentage(self) -> float:
        """What percentage of sprint time has elapsed"""
        if self.total_days == 0:
            return 0.0
        return round((self.days_elapsed / self.total_days) * 100, 1)


@dataclass
class SprintMetrics:
    """Aggregated sprint metrics"""
    total_issues: int
    total_story_points: float
    completed_issues: int
    completed_story_points: float
    remaining_issues: int
    remaining_story_points: float

    @property
    def completion_percentage_by_count(self) -> float:
        """Percentage of issues completed"""
        if self.total_issues == 0:
            return 0.0
        return round((self.completed_issues / self.total_issues) * 100, 1)

    @property
    def completion_percentage_by_points(self) -> float:
        """Percentage of story points completed"""
        if self.total_story_points == 0:
            return 0.0
        return round((self.completed_story_points / self.total_story_points) * 100, 1)


@dataclass
class VelocityMetrics:
    """Velocity and prediction metrics"""
    daily_velocity: float              # Story points per day
    required_velocity: float           # Required velocity to complete on time
    completion_probability: float      # 0-100 percentage
    predicted_completion_points: float # What we'll likely complete
    shortfall_points: float            # Likely shortfall (if any)


@dataclass
class StuckSummary:
    """Summary of stuck items across phases"""
    total_stuck_count: int
    total_stuck_points: float
    stuck_by_phase: Dict[Phase, List[SprintIssue]]
    most_critical_items: List[SprintIssue]  # Sorted by days overdue


@dataclass
class Recommendation:
    """A recommendation for the team"""
    priority: str  # "high", "medium", "low"
    category: str  # "stuck_item", "wip", "velocity", "scope"
    message: str
    affected_issues: List[str] = field(default_factory=list)


@dataclass
class SprintHealthReport:
    """Complete sprint health report"""
    generated_at: datetime
    sprint_info: SprintInfo
    metrics: SprintMetrics
    velocity: VelocityMetrics
    phase_breakdown: List[PhaseMetrics]
    stuck_summary: StuckSummary
    health_status: HealthStatus
    recommendations: List[Recommendation]
    all_issues: List[SprintIssue]

    @property
    def health_emoji(self) -> str:
        """Emoji representation of health status"""
        return {
            HealthStatus.HEALTHY: "✅",
            HealthStatus.AT_RISK: "⚠️",
            HealthStatus.CRITICAL: "🚨"
        }.get(self.health_status, "❓")

    def get_phase_metrics(self, phase: Phase) -> Optional[PhaseMetrics]:
        """Get metrics for a specific phase"""
        for pm in self.phase_breakdown:
            if pm.phase == phase:
                return pm
        return None

