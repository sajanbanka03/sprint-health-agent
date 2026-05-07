"""
Capacity Tracker Module for Sprint Health Agent
Tracks individual and team capacity for intelligent workload analysis

Features:
- Calculate average SP completed per person per sprint (last 5 sprints)
- Current load vs capacity analysis
- Overload/underutilization detection
- Assignment suggestions for unassigned items

Author: Sajan Banka
Created: April 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

from .models import SprintIssue, SprintInfo, SprintMetrics, Phase

logger = logging.getLogger(__name__)

# Configuration file for capacity data
CAPACITY_CONFIG_PATH = Path(__file__).parent.parent / "config" / "team_capacity.json"


class LoadStatus(Enum):
    """Load status for team members"""
    AVAILABLE = "available"      # <50% utilized
    OPTIMAL = "optimal"          # 50-80% utilized
    FULL = "full"                # 80-100% utilized
    OVERLOADED = "overloaded"    # >100% utilized


@dataclass
class MemberCapacity:
    """Capacity data for a single team member"""
    name: str
    default_capacity_sp: float  # Default SP capacity per sprint
    historical_avg_sp: float    # Average SP completed (last X sprints)
    assigned_sp: float          # Currently assigned SP
    completed_sp: float         # SP already completed this sprint
    in_progress_sp: float       # SP in progress
    remaining_sp: float         # SP not yet started
    utilization_pct: float      # Assigned / Capacity percentage
    available_capacity: float   # Remaining capacity available
    load_status: LoadStatus
    assigned_items: List[str]   # List of issue keys

    @property
    def status_emoji(self) -> str:
        """Get emoji for load status"""
        return {
            LoadStatus.AVAILABLE: "🟢",
            LoadStatus.OPTIMAL: "✅",
            LoadStatus.FULL: "⚠️",
            LoadStatus.OVERLOADED: "🔴"
        }.get(self.load_status, "❓")

    @property
    def status_display(self) -> str:
        """Human-readable status"""
        return {
            LoadStatus.AVAILABLE: "Available",
            LoadStatus.OPTIMAL: "Good",
            LoadStatus.FULL: "Full",
            LoadStatus.OVERLOADED: "Overloaded"
        }.get(self.load_status, "Unknown")


@dataclass
class TeamCapacityReport:
    """Complete team capacity analysis"""
    team_name: str
    sprint_name: str
    analysis_time: datetime

    # Team totals
    team_total_capacity: float
    team_assigned_sp: float
    team_completed_sp: float
    team_utilization_pct: float
    team_available_capacity: float
    team_load_status: LoadStatus

    # Member breakdown
    members: List[MemberCapacity]

    # Unassigned items
    unassigned_sp: float
    unassigned_items: List[Dict[str, Any]]

    # Assignment suggestions
    suggestions: List[str]

    # Summary stats
    overloaded_count: int
    optimal_count: int
    available_count: int

    @property
    def team_status_emoji(self) -> str:
        return {
            LoadStatus.AVAILABLE: "🟢",
            LoadStatus.OPTIMAL: "✅",
            LoadStatus.FULL: "⚠️",
            LoadStatus.OVERLOADED: "🔴"
        }.get(self.team_load_status, "❓")


@dataclass
class CapacityConfig:
    """Configuration for team capacity"""
    team_name: str
    default_capacity_sp: float  # Default SP per person if not specified
    members: Dict[str, float]   # member_name -> capacity_sp
    historical_sprints: int     # Number of sprints for historical average

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CapacityConfig':
        return cls(
            team_name=data.get('team_name', 'Unknown'),
            default_capacity_sp=data.get('default_capacity_sp', 8.0),
            members=data.get('members', {}),
            historical_sprints=data.get('historical_sprints', 5)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'team_name': self.team_name,
            'default_capacity_sp': self.default_capacity_sp,
            'members': self.members,
            'historical_sprints': self.historical_sprints
        }


class CapacityTracker:
    """
    Tracks team and individual capacity for workload analysis.

    Usage:
        tracker = CapacityTracker(config)
        report = tracker.analyze_capacity(issues, sprint_info, team_name)
    """

    # Thresholds for load status
    AVAILABLE_THRESHOLD = 50    # <50% = available
    OPTIMAL_THRESHOLD = 80      # 50-80% = optimal
    FULL_THRESHOLD = 100        # 80-100% = full
    # >100% = overloaded

    def __init__(self, config: Dict[str, Any]):
        """Initialize capacity tracker"""
        self.config = config
        self.capacity_configs: Dict[str, CapacityConfig] = {}

        # Load capacity config file
        self._load_capacity_config()

        # Allow config overrides
        capacity_settings = config.get('capacity_tracking', {})
        self.default_capacity = capacity_settings.get('default_capacity_sp', 8.0)
        self.historical_sprints = capacity_settings.get('historical_sprints', 5)

    def _load_capacity_config(self):
        """Load capacity configuration from file"""
        if CAPACITY_CONFIG_PATH.exists():
            try:
                with open(CAPACITY_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for team_data in data.get('teams', []):
                    team_config = CapacityConfig.from_dict(team_data)
                    self.capacity_configs[team_config.team_name] = team_config

                logger.info(f"Loaded capacity config for {len(self.capacity_configs)} teams")
            except Exception as e:
                logger.error(f"Error loading capacity config: {e}")

    def _save_capacity_config(self):
        """Save capacity configuration to file"""
        CAPACITY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'teams': [cfg.to_dict() for cfg in self.capacity_configs.values()],
            'last_updated': datetime.now().isoformat()
        }

        with open(CAPACITY_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def get_member_capacity(self, team_name: str, member_name: str) -> float:
        """Get capacity for a specific team member"""
        if team_name in self.capacity_configs:
            cfg = self.capacity_configs[team_name]
            return cfg.members.get(member_name, cfg.default_capacity_sp)
        return self.default_capacity

    def set_member_capacity(self, team_name: str, member_name: str, capacity_sp: float):
        """Set capacity for a specific team member"""
        if team_name not in self.capacity_configs:
            self.capacity_configs[team_name] = CapacityConfig(
                team_name=team_name,
                default_capacity_sp=self.default_capacity,
                members={},
                historical_sprints=self.historical_sprints
            )

        self.capacity_configs[team_name].members[member_name] = capacity_sp
        self._save_capacity_config()

    def _determine_load_status(self, utilization_pct: float) -> LoadStatus:
        """Determine load status based on utilization percentage"""
        if utilization_pct < self.AVAILABLE_THRESHOLD:
            return LoadStatus.AVAILABLE
        elif utilization_pct < self.OPTIMAL_THRESHOLD:
            return LoadStatus.OPTIMAL
        elif utilization_pct <= self.FULL_THRESHOLD:
            return LoadStatus.FULL
        else:
            return LoadStatus.OVERLOADED

    def analyze_capacity(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        team_name: str
    ) -> TeamCapacityReport:
        """
        Analyze team capacity based on current sprint issues.

        Args:
            issues: All issues in the sprint
            sprint_info: Current sprint information
            team_name: Team name for capacity lookup

        Returns:
            TeamCapacityReport with full analysis
        """
        # Group issues by assignee
        by_assignee: Dict[str, List[SprintIssue]] = {}
        unassigned: List[SprintIssue] = []

        for issue in issues:
            assignee = issue.assignee or "Unassigned"
            if assignee == "Unassigned":
                unassigned.append(issue)
            else:
                if assignee not in by_assignee:
                    by_assignee[assignee] = []
                by_assignee[assignee].append(issue)

        # Analyze each member
        members: List[MemberCapacity] = []
        team_total_capacity = 0
        team_assigned_sp = 0
        team_completed_sp = 0

        for assignee, assignee_issues in by_assignee.items():
            # Get capacity for this member
            capacity = self.get_member_capacity(team_name, assignee)
            team_total_capacity += capacity

            # Calculate SP breakdown
            assigned_sp = sum(i.story_points for i in assignee_issues)
            completed_sp = sum(
                i.story_points for i in assignee_issues
                if i.phase == Phase.DONE
            )
            in_progress_sp = sum(
                i.story_points for i in assignee_issues
                if i.phase in [Phase.IN_PROGRESS, Phase.TESTING]
            )
            remaining_sp = assigned_sp - completed_sp - in_progress_sp

            team_assigned_sp += assigned_sp
            team_completed_sp += completed_sp

            # Calculate utilization
            utilization_pct = (assigned_sp / capacity * 100) if capacity > 0 else 0
            available_capacity = max(0, capacity - assigned_sp)
            load_status = self._determine_load_status(utilization_pct)

            members.append(MemberCapacity(
                name=assignee,
                default_capacity_sp=capacity,
                historical_avg_sp=capacity,  # TODO: Calculate from history
                assigned_sp=assigned_sp,
                completed_sp=completed_sp,
                in_progress_sp=in_progress_sp,
                remaining_sp=remaining_sp,
                utilization_pct=round(utilization_pct, 1),
                available_capacity=round(available_capacity, 1),
                load_status=load_status,
                assigned_items=[i.key for i in assignee_issues]
            ))

        # Sort members by utilization (overloaded first)
        members.sort(key=lambda m: -m.utilization_pct)

        # Analyze unassigned items
        unassigned_sp = sum(i.story_points for i in unassigned)
        unassigned_items = [
            {
                'key': i.key,
                'summary': i.summary,
                'story_points': i.story_points,
                'status': i.status
            }
            for i in unassigned
        ]

        # Calculate team totals
        team_utilization = (team_assigned_sp / team_total_capacity * 100) if team_total_capacity > 0 else 0
        team_available = max(0, team_total_capacity - team_assigned_sp)
        team_load_status = self._determine_load_status(team_utilization)

        # Count statuses
        overloaded_count = sum(1 for m in members if m.load_status == LoadStatus.OVERLOADED)
        optimal_count = sum(1 for m in members if m.load_status == LoadStatus.OPTIMAL)
        available_count = sum(1 for m in members if m.load_status == LoadStatus.AVAILABLE)

        # Generate suggestions
        suggestions = self._generate_suggestions(members, unassigned, team_available)

        return TeamCapacityReport(
            team_name=team_name,
            sprint_name=sprint_info.name,
            analysis_time=datetime.now(),
            team_total_capacity=round(team_total_capacity, 1),
            team_assigned_sp=round(team_assigned_sp, 1),
            team_completed_sp=round(team_completed_sp, 1),
            team_utilization_pct=round(team_utilization, 1),
            team_available_capacity=round(team_available, 1),
            team_load_status=team_load_status,
            members=members,
            unassigned_sp=round(unassigned_sp, 1),
            unassigned_items=unassigned_items,
            suggestions=suggestions,
            overloaded_count=overloaded_count,
            optimal_count=optimal_count,
            available_count=available_count
        )

    def _generate_suggestions(
        self,
        members: List[MemberCapacity],
        unassigned: List[SprintIssue],
        team_available: float
    ) -> List[str]:
        """Generate assignment suggestions"""
        suggestions = []

        # Find overloaded members
        overloaded = [m for m in members if m.load_status == LoadStatus.OVERLOADED]
        available = [m for m in members if m.load_status == LoadStatus.AVAILABLE]

        # Suggest redistributing from overloaded to available
        for om in overloaded[:2]:  # Limit to top 2 overloaded
            excess = om.assigned_sp - om.default_capacity_sp
            if excess > 0 and available:
                best_avail = max(available, key=lambda m: m.available_capacity)
                if best_avail.available_capacity >= 2:  # At least 2 SP available
                    suggestions.append(
                        f"🔄 {om.name} is overloaded by {excess:.0f} SP. "
                        f"Consider reassigning some work to {best_avail.name} "
                        f"(has {best_avail.available_capacity:.0f} SP available)"
                    )

        # Suggest assignments for unassigned items
        if unassigned and available:
            for item in unassigned[:3]:  # Top 3 unassigned
                for member in available:
                    if member.available_capacity >= item.story_points:
                        suggestions.append(
                            f"📋 Consider assigning {item.key} ({item.story_points:.0f} SP) "
                            f"to {member.name} (has {member.available_capacity:.0f} SP available)"
                        )
                        break

        # Team-level suggestions
        if team_available > 10:
            suggestions.append(
                f"💡 Team has {team_available:.0f} SP available capacity. "
                "Consider pulling in more work or supporting other teams."
            )
        elif team_available < 0:
            suggestions.append(
                f"⚠️ Team is over-committed by {abs(team_available):.0f} SP. "
                "Consider descoping or re-prioritizing items."
            )

        # If no issues found
        if not suggestions:
            total_util = sum(m.utilization_pct for m in members) / len(members) if members else 0
            if 70 <= total_util <= 90:
                suggestions.append("✅ Team workload is well balanced. Great job!")
            elif total_util < 70:
                suggestions.append(
                    "💡 Team has good capacity available. "
                    "Consider helping other teams or pulling in stretch goals."
                )

        return suggestions[:5]  # Max 5 suggestions

    def get_capacity_summary(self, report: TeamCapacityReport) -> Dict[str, Any]:
        """
        Get a summary suitable for API/display.

        Returns:
            Dictionary with display-ready data
        """
        return {
            'team': {
                'name': report.team_name,
                'sprint': report.sprint_name,
                'total_capacity': report.team_total_capacity,
                'assigned_sp': report.team_assigned_sp,
                'completed_sp': report.team_completed_sp,
                'utilization_pct': report.team_utilization_pct,
                'available_capacity': report.team_available_capacity,
                'status': report.team_load_status.value,
                'status_emoji': report.team_status_emoji
            },
            'members': [
                {
                    'name': m.name,
                    'capacity': m.default_capacity_sp,
                    'assigned': m.assigned_sp,
                    'completed': m.completed_sp,
                    'in_progress': m.in_progress_sp,
                    'remaining': m.remaining_sp,
                    'utilization_pct': m.utilization_pct,
                    'available': m.available_capacity,
                    'status': m.load_status.value,
                    'status_emoji': m.status_emoji,
                    'status_display': m.status_display,
                    'item_count': len(m.assigned_items)
                }
                for m in report.members
            ],
            'unassigned': {
                'total_sp': report.unassigned_sp,
                'count': len(report.unassigned_items),
                'items': report.unassigned_items[:5]  # Top 5
            },
            'summary': {
                'overloaded_count': report.overloaded_count,
                'optimal_count': report.optimal_count,
                'available_count': report.available_count
            },
            'suggestions': report.suggestions
        }


# Singleton instance
_capacity_tracker: Optional[CapacityTracker] = None


def get_capacity_tracker(config: Optional[Dict[str, Any]] = None) -> CapacityTracker:
    """Get or create singleton capacity tracker instance"""
    global _capacity_tracker

    if _capacity_tracker is None:
        if config is None:
            raise ValueError("Config required for first initialization")
        _capacity_tracker = CapacityTracker(config)

    return _capacity_tracker

