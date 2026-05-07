"""
Module 2: Flow Efficiency & Wait-Waste Analytics
Analyzes active vs passive time using JIRA changelog

Features:
- Active vs Passive status time calculation
- Flow Efficiency = (Active Work Time / Total Cycle Time) × 100
- Wait vs Work ratio visualization
- RTE alerts when efficiency < 20%

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


class StatusType(Enum):
    """Type of status - Active or Passive"""
    ACTIVE = "active"      # Development, Testing - actual work happening
    PASSIVE = "passive"    # Ready for Review, Blocked, To Do - waiting
    DONE = "done"          # Completed
    UNKNOWN = "unknown"


@dataclass
class StatusTransition:
    """A single status transition"""
    from_status: str
    to_status: str
    from_type: StatusType
    to_type: StatusType
    transition_time: datetime
    time_in_status_hours: float


@dataclass
class ItemFlowAnalysis:
    """Flow analysis for a single work item"""
    issue_key: str
    summary: str
    assignee: Optional[str]
    current_status: str
    story_points: float

    # Time breakdown (hours)
    total_active_hours: float
    total_passive_hours: float
    total_cycle_hours: float

    # Flow efficiency
    flow_efficiency: float  # percentage

    # Status transitions
    transitions: List[StatusTransition]
    transition_count: int

    # Wait analysis
    longest_wait_status: Optional[str]
    longest_wait_hours: float

    # Is this item inefficient?
    is_inefficient: bool
    inefficiency_reason: Optional[str]

    @property
    def active_days(self) -> float:
        return self.total_active_hours / 24

    @property
    def passive_days(self) -> float:
        return self.total_passive_hours / 24

    @property
    def wait_work_ratio(self) -> float:
        """Ratio of wait time to work time"""
        if self.total_active_hours == 0:
            return float('inf') if self.total_passive_hours > 0 else 0
        return self.total_passive_hours / self.total_active_hours


@dataclass
class HandoffAnalysis:
    """Analysis of handoffs between states"""
    total_handoffs: int
    avg_handoffs_per_item: float
    most_common_handoff: Tuple[str, str]  # (from_status, to_status)
    handoff_wait_time: Dict[str, float]  # transition -> avg hours


@dataclass
class FlowEfficiencyReport:
    """Complete flow efficiency report"""
    generated_at: datetime
    sprint_info: SprintInfo

    # Overall metrics
    team_flow_efficiency: float  # percentage
    total_active_hours: float
    total_passive_hours: float
    total_cycle_hours: float

    # Wait vs Work ratio
    wait_work_ratio: float

    # Alert level
    alert_level: str  # "green", "amber", "red"
    alert_message: Optional[str]

    # Item-level analysis
    item_analyses: List[ItemFlowAnalysis]
    inefficient_items: List[ItemFlowAnalysis]

    # Status breakdown
    time_by_status: Dict[str, float]  # status -> total hours
    active_statuses_time: Dict[str, float]
    passive_statuses_time: Dict[str, float]

    # Handoff analysis
    handoff_analysis: HandoffAnalysis

    # Recommendations
    bottleneck_statuses: List[Tuple[str, float, str]]  # (status, hours, recommendation)

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
                'team_flow_efficiency': round(self.team_flow_efficiency, 1),
                'total_active_hours': round(self.total_active_hours, 1),
                'total_passive_hours': round(self.total_passive_hours, 1),
                'total_cycle_hours': round(self.total_cycle_hours, 1),
                'wait_work_ratio': round(self.wait_work_ratio, 2),
                'alert_level': self.alert_level,
                'alert_message': self.alert_message
            },
            'status_breakdown': {
                'active': {
                    status: round(hours, 1)
                    for status, hours in self.active_statuses_time.items()
                },
                'passive': {
                    status: round(hours, 1)
                    for status, hours in self.passive_statuses_time.items()
                }
            },
            'inefficient_items': [
                {
                    'key': item.issue_key,
                    'summary': item.summary,
                    'assignee': item.assignee,
                    'flow_efficiency': round(item.flow_efficiency, 1),
                    'active_hours': round(item.total_active_hours, 1),
                    'passive_hours': round(item.total_passive_hours, 1),
                    'longest_wait': item.longest_wait_status,
                    'longest_wait_hours': round(item.longest_wait_hours, 1),
                    'wait_work_ratio': round(item.wait_work_ratio, 2),
                    'reason': item.inefficiency_reason
                }
                for item in self.inefficient_items[:10]
            ],
            'handoffs': {
                'total': self.handoff_analysis.total_handoffs,
                'avg_per_item': round(self.handoff_analysis.avg_handoffs_per_item, 1),
                'most_common': list(self.handoff_analysis.most_common_handoff),
                'wait_times': {
                    k: round(v, 1)
                    for k, v in self.handoff_analysis.handoff_wait_time.items()
                }
            },
            'bottlenecks': [
                {
                    'status': status,
                    'total_hours': round(hours, 1),
                    'recommendation': rec
                }
                for status, hours, rec in self.bottleneck_statuses
            ]
        }


class FlowEfficiencyEngine:
    """
    Flow Efficiency Analysis Engine

    Calculates time spent in active vs passive states to determine
    flow efficiency and identify handoff delays.
    """

    # Status classification - customize based on your workflow
    ACTIVE_STATUSES = {
        'in development', 'in progress', 'developing', 'coding',
        'in testing', 'testing', 'in sit', 'in uat',
        'in analysis', 'analysis', 'in review', 'code review',
        'tpo review', 'in tpo review', 'qa testing'
    }

    PASSIVE_STATUSES = {
        'to do', 'todo', 'open', 'backlog', 'new',
        'ready for development', 'ready for dev', 'ready for testing',
        'ready for sit', 'ready for review', 'waiting', 'blocked',
        'on hold', 'pending', 'ready for qa', 'ready for tpo',
        'selected for development'
    }

    DONE_STATUSES = {
        'done', 'closed', 'resolved', 'complete', 'completed',
        'delivered', 'released'
    }

    # Alert thresholds
    EFFICIENCY_RED_THRESHOLD = 20  # Below 20% = systemic handoff delays
    EFFICIENCY_AMBER_THRESHOLD = 40  # Below 40% = needs attention

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Allow config overrides for status classification
        workflow_config = config.get('workflow_status_types', {})
        if workflow_config.get('active'):
            self.ACTIVE_STATUSES.update(s.lower() for s in workflow_config['active'])
        if workflow_config.get('passive'):
            self.PASSIVE_STATUSES.update(s.lower() for s in workflow_config['passive'])

    def analyze_flow(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        jira_client=None  # For fetching additional changelog if needed
    ) -> FlowEfficiencyReport:
        """
        Analyze flow efficiency for all issues.

        Args:
            issues: Sprint issues (should include changelog data)
            sprint_info: Sprint information
            jira_client: Optional Jira client for additional data

        Returns:
            FlowEfficiencyReport with complete analysis
        """
        item_analyses: List[ItemFlowAnalysis] = []

        total_active_hours = 0.0
        total_passive_hours = 0.0
        time_by_status: Dict[str, float] = {}
        active_statuses_time: Dict[str, float] = {}
        passive_statuses_time: Dict[str, float] = {}
        all_transitions: List[StatusTransition] = []

        # Analyze each issue
        for issue in issues:
            analysis = self._analyze_item_flow(issue)
            item_analyses.append(analysis)

            total_active_hours += analysis.total_active_hours
            total_passive_hours += analysis.total_passive_hours

            # Aggregate status times
            for transition in analysis.transitions:
                status = transition.from_status
                hours = transition.time_in_status_hours

                time_by_status[status] = time_by_status.get(status, 0) + hours

                if transition.from_type == StatusType.ACTIVE:
                    active_statuses_time[status] = active_statuses_time.get(status, 0) + hours
                elif transition.from_type == StatusType.PASSIVE:
                    passive_statuses_time[status] = passive_statuses_time.get(status, 0) + hours

            all_transitions.extend(analysis.transitions)

        # Calculate team flow efficiency
        total_cycle_hours = total_active_hours + total_passive_hours
        team_efficiency = (
            (total_active_hours / total_cycle_hours * 100)
            if total_cycle_hours > 0 else 100
        )

        # Calculate wait/work ratio
        wait_work_ratio = (
            total_passive_hours / total_active_hours
            if total_active_hours > 0 else float('inf')
        )

        # Determine alert level
        if team_efficiency < self.EFFICIENCY_RED_THRESHOLD:
            alert_level = "red"
            alert_message = (
                f"CRITICAL: Flow efficiency at {team_efficiency:.1f}% indicates "
                f"systemic handoff delays. Team spends {wait_work_ratio:.1f}x more time waiting than working."
            )
        elif team_efficiency < self.EFFICIENCY_AMBER_THRESHOLD:
            alert_level = "amber"
            alert_message = (
                f"Warning: Flow efficiency at {team_efficiency:.1f}% is below target. "
                f"Consider reducing wait states and handoff delays."
            )
        else:
            alert_level = "green"
            alert_message = None

        # Find inefficient items (below 30% efficiency)
        inefficient_items = [i for i in item_analyses if i.is_inefficient]
        inefficient_items.sort(key=lambda x: x.flow_efficiency)

        # Handoff analysis
        handoff_analysis = self._analyze_handoffs(all_transitions)

        # Find bottlenecks
        bottlenecks = self._identify_bottlenecks(passive_statuses_time)

        return FlowEfficiencyReport(
            generated_at=datetime.now(),
            sprint_info=sprint_info,
            team_flow_efficiency=team_efficiency,
            total_active_hours=total_active_hours,
            total_passive_hours=total_passive_hours,
            total_cycle_hours=total_cycle_hours,
            wait_work_ratio=wait_work_ratio,
            alert_level=alert_level,
            alert_message=alert_message,
            item_analyses=item_analyses,
            inefficient_items=inefficient_items,
            time_by_status=time_by_status,
            active_statuses_time=active_statuses_time,
            passive_statuses_time=passive_statuses_time,
            handoff_analysis=handoff_analysis,
            bottleneck_statuses=bottlenecks
        )

    def _analyze_item_flow(self, issue: SprintIssue) -> ItemFlowAnalysis:
        """Analyze flow for a single issue"""
        transitions = self._extract_transitions(issue)

        # Calculate time in each type
        total_active = sum(
            t.time_in_status_hours for t in transitions
            if t.from_type == StatusType.ACTIVE
        )
        total_passive = sum(
            t.time_in_status_hours for t in transitions
            if t.from_type == StatusType.PASSIVE
        )
        total_cycle = total_active + total_passive

        # Flow efficiency
        efficiency = (total_active / total_cycle * 100) if total_cycle > 0 else 100

        # Find longest wait
        passive_transitions = [t for t in transitions if t.from_type == StatusType.PASSIVE]
        longest_wait = max(passive_transitions, key=lambda x: x.time_in_status_hours) if passive_transitions else None

        # Determine if inefficient
        is_inefficient = efficiency < 30 or (total_passive > total_active * 2)
        inefficiency_reason = None
        if is_inefficient:
            if longest_wait:
                inefficiency_reason = f"Spent {longest_wait.time_in_status_hours:.1f}h waiting in '{longest_wait.from_status}'"
            else:
                inefficiency_reason = f"Only {efficiency:.0f}% active work time"

        return ItemFlowAnalysis(
            issue_key=issue.key,
            summary=issue.summary,
            assignee=issue.assignee,
            current_status=issue.status,
            story_points=issue.story_points,
            total_active_hours=total_active,
            total_passive_hours=total_passive,
            total_cycle_hours=total_cycle,
            flow_efficiency=efficiency,
            transitions=transitions,
            transition_count=len(transitions),
            longest_wait_status=longest_wait.from_status if longest_wait else None,
            longest_wait_hours=longest_wait.time_in_status_hours if longest_wait else 0,
            is_inefficient=is_inefficient,
            inefficiency_reason=inefficiency_reason
        )

    def _extract_transitions(self, issue: SprintIssue) -> List[StatusTransition]:
        """
        Extract status transitions from issue.

        For now, we estimate based on available data. In a full implementation,
        this would use the expand=changelog from JIRA API.
        """
        transitions = []

        # Get time in current status
        if issue.status_change_date:
            hours_in_status = (datetime.now() - issue.status_change_date).total_seconds() / 3600
        else:
            hours_in_status = (datetime.now() - issue.created_date).total_seconds() / 3600

        current_type = self._classify_status(issue.status)

        # Create a transition representing current state
        # This is simplified - full implementation would parse changelog
        transitions.append(StatusTransition(
            from_status=issue.status,
            to_status="current",
            from_type=current_type,
            to_type=StatusType.UNKNOWN,
            transition_time=issue.status_change_date or issue.created_date,
            time_in_status_hours=hours_in_status
        ))

        # Estimate historical time based on phase
        # This is a heuristic when we don't have full changelog
        if issue.phase == Phase.DONE:
            # Estimate active time based on story points
            estimated_active = issue.story_points * 4 if issue.story_points else 8  # hours
            estimated_passive = max(0, hours_in_status - estimated_active)

            if estimated_active > 0:
                transitions.append(StatusTransition(
                    from_status="In Development (estimated)",
                    to_status=issue.status,
                    from_type=StatusType.ACTIVE,
                    to_type=current_type,
                    transition_time=issue.created_date,
                    time_in_status_hours=estimated_active
                ))

            if estimated_passive > 2:  # More than 2 hours waiting
                transitions.append(StatusTransition(
                    from_status="Waiting (estimated)",
                    to_status="In Development",
                    from_type=StatusType.PASSIVE,
                    to_type=StatusType.ACTIVE,
                    transition_time=issue.created_date,
                    time_in_status_hours=estimated_passive
                ))

        return transitions

    def _classify_status(self, status: str) -> StatusType:
        """Classify a status as Active, Passive, or Done"""
        status_lower = status.lower().strip()

        if any(done in status_lower for done in self.DONE_STATUSES):
            return StatusType.DONE

        if any(active in status_lower for active in self.ACTIVE_STATUSES):
            return StatusType.ACTIVE

        if any(passive in status_lower for passive in self.PASSIVE_STATUSES):
            return StatusType.PASSIVE

        # Default heuristics
        if 'in ' in status_lower or 'ing' in status_lower:
            return StatusType.ACTIVE
        if 'ready' in status_lower or 'waiting' in status_lower:
            return StatusType.PASSIVE

        return StatusType.UNKNOWN

    def _analyze_handoffs(self, transitions: List[StatusTransition]) -> HandoffAnalysis:
        """Analyze handoff patterns"""
        if not transitions:
            return HandoffAnalysis(
                total_handoffs=0,
                avg_handoffs_per_item=0,
                most_common_handoff=("", ""),
                handoff_wait_time={}
            )

        # Count handoffs by type
        handoff_counts: Dict[Tuple[str, str], int] = {}
        handoff_times: Dict[Tuple[str, str], List[float]] = {}

        for t in transitions:
            if t.from_status and t.to_status and t.to_status != "current":
                key = (t.from_status, t.to_status)
                handoff_counts[key] = handoff_counts.get(key, 0) + 1

                if key not in handoff_times:
                    handoff_times[key] = []
                handoff_times[key].append(t.time_in_status_hours)

        # Find most common handoff
        most_common = max(handoff_counts.items(), key=lambda x: x[1])[0] if handoff_counts else ("", "")

        # Calculate average wait times for each transition
        avg_wait_times = {
            f"{k[0]} → {k[1]}": statistics.mean(v)
            for k, v in handoff_times.items() if v
        }

        return HandoffAnalysis(
            total_handoffs=sum(handoff_counts.values()),
            avg_handoffs_per_item=len(transitions) / max(1, len(set(t.from_status for t in transitions))),
            most_common_handoff=most_common,
            handoff_wait_time=avg_wait_times
        )

    def _identify_bottlenecks(
        self,
        passive_times: Dict[str, float]
    ) -> List[Tuple[str, float, str]]:
        """Identify bottleneck statuses with recommendations"""
        if not passive_times:
            return []

        bottlenecks = []

        # Sort by time spent
        sorted_statuses = sorted(
            passive_times.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for status, hours in sorted_statuses[:5]:  # Top 5 bottlenecks
            recommendation = self._get_bottleneck_recommendation(status, hours)
            bottlenecks.append((status, hours, recommendation))

        return bottlenecks

    def _get_bottleneck_recommendation(self, status: str, hours: float) -> str:
        """Generate recommendation for a bottleneck status"""
        status_lower = status.lower()

        if 'review' in status_lower or 'tpo' in status_lower:
            return "Consider increasing review capacity or reducing review batch size"
        elif 'ready' in status_lower:
            return "Items queuing up - consider pull-based flow instead of push"
        elif 'blocked' in status_lower:
            return "Address blockers immediately - escalate if > 2 days"
        elif 'testing' in status_lower or 'qa' in status_lower:
            return "Testing might be understaffed - consider shift-left testing"
        elif 'analysis' in status_lower:
            return "Requirements clarification needed earlier in process"
        else:
            return f"Investigate why items spend {hours:.0f}+ hours in this state"

    def get_visualization_data(self, report: FlowEfficiencyReport) -> Dict[str, Any]:
        """Get data formatted for Wait vs Work chart"""
        return {
            'chart_type': 'flow_efficiency',
            'title': 'Wait vs Work Time',
            'subtitle': f'Flow Efficiency: {report.team_flow_efficiency:.1f}%',
            'donut_data': {
                'active': round(report.total_active_hours, 1),
                'passive': round(report.total_passive_hours, 1),
                'labels': ['Active Work', 'Wait Time']
            },
            'bar_data': {
                'active_statuses': [
                    {'status': s, 'hours': round(h, 1)}
                    for s, h in sorted(
                        report.active_statuses_time.items(),
                        key=lambda x: -x[1]
                    )[:5]
                ],
                'passive_statuses': [
                    {'status': s, 'hours': round(h, 1)}
                    for s, h in sorted(
                        report.passive_statuses_time.items(),
                        key=lambda x: -x[1]
                    )[:5]
                ]
            },
            'alert': {
                'level': report.alert_level,
                'message': report.alert_message
            },
            'efficiency_gauge': {
                'value': report.team_flow_efficiency,
                'zones': [
                    {'min': 0, 'max': 20, 'color': 'red'},
                    {'min': 20, 'max': 40, 'color': 'orange'},
                    {'min': 40, 'max': 70, 'color': 'yellow'},
                    {'min': 70, 'max': 100, 'color': 'green'}
                ]
            }
        }

