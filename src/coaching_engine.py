"""
Coaching Engine Module for Sprint Health Agent
Provides sprint-over-sprint comparison, improvement patterns, and coaching tips

Features:
- Sprint-over-sprint metric comparison with trends
- Improvement pattern detection over last 5 sprints
- Common failure pattern identification
- Team Health Score (0-100)
- Actionable coaching tips based on patterns

Author: Sajan Banka
Created: April 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .models import SprintIssue, SprintInfo, SprintMetrics, VelocityMetrics, Phase

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Direction of a metric trend"""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


@dataclass
class MetricComparison:
    """Comparison of a metric between sprints"""
    metric_name: str
    display_name: str
    current_value: float
    previous_value: float
    change: float  # Absolute change
    change_pct: float  # Percentage change
    trend: TrendDirection
    trend_emoji: str
    is_better: bool  # True if the change is an improvement
    insight: str  # Human-readable insight


@dataclass
class ImprovementPattern:
    """Detected improvement or decline pattern"""
    pattern_type: str  # "velocity", "stuck_rate", "completion_rate", etc.
    description: str
    trend: TrendDirection
    change_pct: float
    sprints_analyzed: int
    data_points: List[float]
    recommendation: str


@dataclass
class FailurePattern:
    """Detected common failure pattern"""
    pattern_id: str
    severity: str  # "high", "medium", "low"
    title: str
    description: str
    occurrences: int  # How many times detected
    affected_items: List[str]  # Issue keys
    root_cause_hint: str
    coaching_tip: str


@dataclass
class CoachingTip:
    """Actionable coaching recommendation"""
    priority: str  # "high", "medium", "low"
    category: str  # "velocity", "quality", "process", "team"
    title: str
    message: str
    action_items: List[str]
    expected_impact: str


@dataclass
class TeamHealthScore:
    """Composite team health score"""
    overall_score: int  # 0-100
    grade: str  # A, B, C, D, F
    grade_emoji: str

    # Component scores
    velocity_score: int
    quality_score: int
    process_score: int
    predictability_score: int

    # Trend
    previous_score: Optional[int]
    score_change: int
    trend: TrendDirection

    # Breakdown explanations
    strengths: List[str]
    areas_for_improvement: List[str]


@dataclass
class CoachingReport:
    """Complete coaching and improvement report"""
    team_name: str
    sprint_name: str
    generated_at: datetime

    # Sprint comparison
    comparisons: List[MetricComparison]

    # Patterns
    improvement_patterns: List[ImprovementPattern]
    failure_patterns: List[FailurePattern]

    # Health
    health_score: TeamHealthScore

    # Coaching
    coaching_tips: List[CoachingTip]

    # Summary
    executive_summary: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON"""
        return {
            'team_name': self.team_name,
            'sprint_name': self.sprint_name,
            'generated_at': self.generated_at.isoformat(),
            'comparisons': [
                {
                    'metric': c.metric_name,
                    'display_name': c.display_name,
                    'current': c.current_value,
                    'previous': c.previous_value,
                    'change': c.change,
                    'change_pct': c.change_pct,
                    'trend': c.trend.value,
                    'trend_emoji': c.trend_emoji,
                    'is_better': c.is_better,
                    'insight': c.insight
                }
                for c in self.comparisons
            ],
            'improvement_patterns': [
                {
                    'type': p.pattern_type,
                    'description': p.description,
                    'trend': p.trend.value,
                    'change_pct': p.change_pct,
                    'sprints': p.sprints_analyzed,
                    'recommendation': p.recommendation
                }
                for p in self.improvement_patterns
            ],
            'failure_patterns': [
                {
                    'id': f.pattern_id,
                    'severity': f.severity,
                    'title': f.title,
                    'description': f.description,
                    'occurrences': f.occurrences,
                    'coaching_tip': f.coaching_tip
                }
                for f in self.failure_patterns
            ],
            'health_score': {
                'overall': self.health_score.overall_score,
                'grade': self.health_score.grade,
                'grade_emoji': self.health_score.grade_emoji,
                'components': {
                    'velocity': self.health_score.velocity_score,
                    'quality': self.health_score.quality_score,
                    'process': self.health_score.process_score,
                    'predictability': self.health_score.predictability_score
                },
                'trend': self.health_score.trend.value,
                'previous': self.health_score.previous_score,
                'change': self.health_score.score_change,
                'strengths': self.health_score.strengths,
                'improvements': self.health_score.areas_for_improvement
            },
            'coaching_tips': [
                {
                    'priority': t.priority,
                    'category': t.category,
                    'title': t.title,
                    'message': t.message,
                    'actions': t.action_items,
                    'impact': t.expected_impact
                }
                for t in self.coaching_tips
            ],
            'executive_summary': self.executive_summary
        }


class CoachingEngine:
    """
    Generates coaching insights and improvement recommendations.

    Usage:
        engine = CoachingEngine(config)
        report = engine.generate_coaching_report(
            sprint_info, metrics, velocity, issues, historical_data
        )
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.thresholds = config.get('thresholds', {})
        self.historical_sprints = config.get('historical_sprints', 5)

    def generate_coaching_report(
        self,
        sprint_info: SprintInfo,
        metrics: SprintMetrics,
        velocity: VelocityMetrics,
        issues: List[SprintIssue],
        historical_data: List[Dict[str, Any]],
        team_name: str
    ) -> CoachingReport:
        """
        Generate comprehensive coaching report.

        Args:
            sprint_info: Current sprint information
            metrics: Sprint metrics
            velocity: Velocity metrics
            issues: All sprint issues
            historical_data: Historical sprint data (last 5 sprints)
            team_name: Team name

        Returns:
            CoachingReport with full analysis
        """
        # Sprint-over-sprint comparisons
        comparisons = self._generate_comparisons(metrics, velocity, historical_data)

        # Improvement patterns over time
        improvement_patterns = self._detect_improvement_patterns(historical_data)

        # Failure patterns in current sprint
        failure_patterns = self._detect_failure_patterns(issues, sprint_info)

        # Team health score
        health_score = self._calculate_health_score(
            metrics, velocity, issues, historical_data, comparisons
        )

        # Coaching tips based on all analysis
        coaching_tips = self._generate_coaching_tips(
            comparisons, improvement_patterns, failure_patterns, health_score, issues
        )

        # Executive summary
        executive_summary = self._generate_executive_summary(
            health_score, comparisons, improvement_patterns, coaching_tips
        )

        return CoachingReport(
            team_name=team_name,
            sprint_name=sprint_info.name,
            generated_at=datetime.now(),
            comparisons=comparisons,
            improvement_patterns=improvement_patterns,
            failure_patterns=failure_patterns,
            health_score=health_score,
            coaching_tips=coaching_tips,
            executive_summary=executive_summary
        )

    def _generate_comparisons(
        self,
        metrics: SprintMetrics,
        velocity: VelocityMetrics,
        historical_data: List[Dict[str, Any]]
    ) -> List[MetricComparison]:
        """Generate sprint-over-sprint comparisons"""
        comparisons = []

        # Get previous sprint data
        if not historical_data or len(historical_data) < 1:
            return comparisons

        prev_sprint = historical_data[0] if historical_data else {}

        # Velocity comparison
        prev_velocity = prev_sprint.get('completed_points', 0) / max(prev_sprint.get('total_days', 10), 1)
        comparisons.append(self._create_comparison(
            'daily_velocity', 'Daily Velocity',
            velocity.daily_velocity, prev_velocity,
            higher_is_better=True
        ))

        # Completion rate comparison
        current_completion = metrics.completion_percentage_by_points
        prev_completion = (prev_sprint.get('completed_points', 0) /
                          max(prev_sprint.get('committed_points', 1), 1)) * 100
        comparisons.append(self._create_comparison(
            'completion_rate', 'Completion Rate',
            current_completion, prev_completion,
            higher_is_better=True,
            suffix='%'
        ))

        # Committed SP comparison
        prev_committed = prev_sprint.get('committed_points', 0)
        comparisons.append(self._create_comparison(
            'committed_sp', 'Committed SP',
            metrics.total_story_points, prev_committed,
            higher_is_better=None  # Neutral
        ))

        return comparisons

    def _create_comparison(
        self,
        metric_name: str,
        display_name: str,
        current: float,
        previous: float,
        higher_is_better: Optional[bool] = True,
        suffix: str = ''
    ) -> MetricComparison:
        """Create a metric comparison"""
        change = current - previous
        change_pct = (change / previous * 100) if previous != 0 else 0

        # Determine trend
        if abs(change_pct) < 5:
            trend = TrendDirection.STABLE
            trend_emoji = "➡️"
        elif change > 0:
            trend = TrendDirection.IMPROVING if higher_is_better else TrendDirection.DECLINING
            trend_emoji = "📈" if higher_is_better else "📉"
        else:
            trend = TrendDirection.DECLINING if higher_is_better else TrendDirection.IMPROVING
            trend_emoji = "📉" if higher_is_better else "📈"

        # Determine if change is better
        if higher_is_better is None:
            is_better = abs(change_pct) < 15  # Stability is good for neutral metrics
        else:
            is_better = (change > 0) == higher_is_better

        # Generate insight
        if trend == TrendDirection.STABLE:
            insight = f"{display_name} is stable at {current:.1f}{suffix}"
        elif is_better:
            insight = f"{display_name} improved by {abs(change_pct):.0f}% from {previous:.1f}{suffix} to {current:.1f}{suffix}"
        else:
            insight = f"{display_name} declined by {abs(change_pct):.0f}% from {previous:.1f}{suffix} to {current:.1f}{suffix}"

        return MetricComparison(
            metric_name=metric_name,
            display_name=display_name,
            current_value=round(current, 1),
            previous_value=round(previous, 1),
            change=round(change, 1),
            change_pct=round(change_pct, 1),
            trend=trend,
            trend_emoji=trend_emoji,
            is_better=is_better,
            insight=insight
        )

    def _detect_improvement_patterns(
        self,
        historical_data: List[Dict[str, Any]]
    ) -> List[ImprovementPattern]:
        """Detect improvement or decline patterns over multiple sprints"""
        patterns = []

        if len(historical_data) < 2:
            return patterns

        # Velocity trend
        velocities = [
            s.get('completed_points', 0) / max(s.get('total_days', 10), 1)
            for s in historical_data
        ]
        if velocities:
            velocity_pattern = self._analyze_trend(
                'velocity', 'Team Velocity', velocities[:self.historical_sprints],
                higher_is_better=True
            )
            if velocity_pattern:
                patterns.append(velocity_pattern)

        # Completion rate trend
        completion_rates = []
        for s in historical_data:
            committed = s.get('committed_points', 0)
            completed = s.get('completed_points', 0)
            if committed > 0:
                completion_rates.append((completed / committed) * 100)

        if completion_rates:
            completion_pattern = self._analyze_trend(
                'completion_rate', 'Sprint Completion Rate', completion_rates[:self.historical_sprints],
                higher_is_better=True
            )
            if completion_pattern:
                patterns.append(completion_pattern)

        return patterns

    def _analyze_trend(
        self,
        pattern_type: str,
        description: str,
        data_points: List[float],
        higher_is_better: bool
    ) -> Optional[ImprovementPattern]:
        """Analyze a metric trend over multiple sprints"""
        if len(data_points) < 2:
            return None

        # Calculate overall change (oldest to newest)
        # Note: data_points[0] is most recent, data_points[-1] is oldest
        newest = data_points[0]
        oldest = data_points[-1]

        if oldest == 0:
            return None

        change_pct = ((newest - oldest) / oldest) * 100

        # Determine trend direction
        if abs(change_pct) < 10:
            trend = TrendDirection.STABLE
            description = f"{description} has remained stable over the last {len(data_points)} sprints"
            recommendation = f"Continue current practices to maintain {pattern_type} consistency."
        elif change_pct > 0:
            if higher_is_better:
                trend = TrendDirection.IMPROVING
                description = f"{description} improved by {change_pct:.0f}% over the last {len(data_points)} sprints"
                recommendation = f"Great progress! Identify what's working and continue these practices."
            else:
                trend = TrendDirection.DECLINING
                description = f"{description} increased by {change_pct:.0f}%, which may indicate issues"
                recommendation = f"Investigate the root cause and implement corrective measures."
        else:
            if higher_is_better:
                trend = TrendDirection.DECLINING
                description = f"{description} declined by {abs(change_pct):.0f}% over the last {len(data_points)} sprints"
                recommendation = f"Consider a retrospective to identify blockers and improvement opportunities."
            else:
                trend = TrendDirection.IMPROVING
                description = f"{description} reduced by {abs(change_pct):.0f}%, which is positive"
                recommendation = f"Good improvement! Keep up the current approach."

        return ImprovementPattern(
            pattern_type=pattern_type,
            description=description,
            trend=trend,
            change_pct=round(change_pct, 1),
            sprints_analyzed=len(data_points),
            data_points=data_points,
            recommendation=recommendation
        )

    def _detect_failure_patterns(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo
    ) -> List[FailurePattern]:
        """Detect common failure patterns in current sprint"""
        patterns = []

        # Pattern 1: Items stuck in specific phases
        stuck_by_phase = {}
        for issue in issues:
            if issue.is_stuck:
                phase = issue.phase.value
                if phase not in stuck_by_phase:
                    stuck_by_phase[phase] = []
                stuck_by_phase[phase].append(issue.key)

        for phase, stuck_keys in stuck_by_phase.items():
            if len(stuck_keys) >= 2:
                patterns.append(FailurePattern(
                    pattern_id=f"stuck_{phase}",
                    severity="high" if len(stuck_keys) >= 3 else "medium",
                    title=f"Multiple items stuck in {phase.replace('_', ' ').title()}",
                    description=f"{len(stuck_keys)} items are stuck in the {phase.replace('_', ' ')} phase",
                    occurrences=len(stuck_keys),
                    affected_items=stuck_keys[:5],
                    root_cause_hint=self._get_phase_root_cause(phase),
                    coaching_tip=self._get_phase_coaching_tip(phase)
                ))

        # Pattern 2: Unassigned items late in sprint
        days_left = sprint_info.days_remaining
        if days_left <= 3:
            unassigned = [i for i in issues if not i.assignee and i.phase != Phase.DONE]
            if len(unassigned) >= 2:
                patterns.append(FailurePattern(
                    pattern_id="unassigned_late",
                    severity="high",
                    title="Unassigned items near sprint end",
                    description=f"{len(unassigned)} items without assignees with only {days_left} days left",
                    occurrences=len(unassigned),
                    affected_items=[i.key for i in unassigned[:5]],
                    root_cause_hint="Work may not have been properly distributed at sprint planning",
                    coaching_tip="Assign remaining items immediately or consider moving to backlog"
                ))

        # Pattern 3: Large items not started
        large_not_started = [
            i for i in issues
            if i.story_points >= 5 and i.phase in [Phase.BACKLOG, Phase.IN_ANALYSIS]
        ]
        if large_not_started and days_left <= sprint_info.total_days // 2:
            patterns.append(FailurePattern(
                pattern_id="large_not_started",
                severity="high" if days_left <= 3 else "medium",
                title="Large items not yet in development",
                description=f"{len(large_not_started)} large items (≥5 SP) still in early phases",
                occurrences=len(large_not_started),
                affected_items=[i.key for i in large_not_started[:5]],
                root_cause_hint="Large items may need early prioritization or breaking down",
                coaching_tip="Consider breaking down large items or prioritizing them earlier in the sprint"
            ))

        return patterns

    def _get_phase_root_cause(self, phase: str) -> str:
        """Get common root cause hint for a phase"""
        hints = {
            'in_analysis': "Requirements may be unclear or dependencies unresolved",
            'in_dev': "Technical complexity, blockers, or resource constraints",
            'ready_for_sit': "Testing capacity bottleneck or environment issues",
            'in_sit': "Defects found, unclear test criteria, or environment problems",
            'in_tpo_review': "Waiting for TPO availability or approval delays"
        }
        return hints.get(phase, "Review and address blockers")

    def _get_phase_coaching_tip(self, phase: str) -> str:
        """Get coaching tip for items stuck in a phase"""
        tips = {
            'in_analysis': "Schedule a refinement session to clarify requirements and resolve dependencies",
            'in_dev': "Consider pair programming, mob sessions, or breaking down complex items",
            'ready_for_sit': "Schedule dedicated testing time or consider test automation",
            'in_sit': "Implement a swarming approach for quick defect resolution",
            'in_tpo_review': "Schedule regular TPO sync meetings to reduce wait time"
        }
        return tips.get(phase, "Hold a focused meeting to remove blockers")

    def _calculate_health_score(
        self,
        metrics: SprintMetrics,
        velocity: VelocityMetrics,
        issues: List[SprintIssue],
        historical_data: List[Dict[str, Any]],
        comparisons: List[MetricComparison]
    ) -> TeamHealthScore:
        """Calculate composite team health score"""
        # Velocity score (0-25)
        if velocity.completion_probability >= 80:
            velocity_score = 25
        elif velocity.completion_probability >= 60:
            velocity_score = 20
        elif velocity.completion_probability >= 40:
            velocity_score = 15
        else:
            velocity_score = 10

        # Quality score based on stuck rate (0-25)
        stuck_count = sum(1 for i in issues if i.is_stuck)
        stuck_rate = (stuck_count / len(issues) * 100) if issues else 0
        if stuck_rate <= 5:
            quality_score = 25
        elif stuck_rate <= 15:
            quality_score = 20
        elif stuck_rate <= 25:
            quality_score = 15
        else:
            quality_score = 10

        # Process score based on WIP distribution (0-25)
        unassigned_rate = sum(1 for i in issues if not i.assignee) / len(issues) * 100 if issues else 0
        if unassigned_rate <= 5:
            process_score = 25
        elif unassigned_rate <= 15:
            process_score = 20
        elif unassigned_rate <= 25:
            process_score = 15
        else:
            process_score = 10

        # Predictability score based on commitment vs completion (0-25)
        completion_pct = metrics.completion_percentage_by_points
        if 90 <= completion_pct <= 110:  # Close to target
            predictability_score = 25
        elif 75 <= completion_pct <= 125:
            predictability_score = 20
        elif 60 <= completion_pct <= 140:
            predictability_score = 15
        else:
            predictability_score = 10

        # Overall score
        overall_score = velocity_score + quality_score + process_score + predictability_score

        # Grade
        if overall_score >= 90:
            grade, grade_emoji = 'A', '🌟'
        elif overall_score >= 80:
            grade, grade_emoji = 'B', '✨'
        elif overall_score >= 70:
            grade, grade_emoji = 'C', '👍'
        elif overall_score >= 60:
            grade, grade_emoji = 'D', '⚠️'
        else:
            grade, grade_emoji = 'F', '🔴'

        # Calculate trend (simplified - would need previous health scores stored)
        previous_score = None
        score_change = 0
        trend = TrendDirection.STABLE

        # Determine strengths and improvements
        strengths = []
        areas_for_improvement = []

        if velocity_score >= 22:
            strengths.append("Strong velocity and on-track for sprint goal")
        if quality_score >= 22:
            strengths.append("Low stuck rate indicates good flow")
        if process_score >= 22:
            strengths.append("Work is well distributed across team")
        if predictability_score >= 22:
            strengths.append("Good predictability in sprint commitments")

        if velocity_score < 18:
            areas_for_improvement.append("Velocity needs improvement to meet sprint goals")
        if quality_score < 18:
            areas_for_improvement.append("Too many stuck items - address blockers quickly")
        if process_score < 18:
            areas_for_improvement.append("Improve work distribution and assignment")
        if predictability_score < 18:
            areas_for_improvement.append("Sprint commitment vs completion variance is high")

        return TeamHealthScore(
            overall_score=overall_score,
            grade=grade,
            grade_emoji=grade_emoji,
            velocity_score=velocity_score,
            quality_score=quality_score,
            process_score=process_score,
            predictability_score=predictability_score,
            previous_score=previous_score,
            score_change=score_change,
            trend=trend,
            strengths=strengths if strengths else ["Team is performing consistently"],
            areas_for_improvement=areas_for_improvement if areas_for_improvement else ["Continue current good practices"]
        )

    def _generate_coaching_tips(
        self,
        comparisons: List[MetricComparison],
        improvement_patterns: List[ImprovementPattern],
        failure_patterns: List[FailurePattern],
        health_score: TeamHealthScore,
        issues: List[SprintIssue]
    ) -> List[CoachingTip]:
        """Generate actionable coaching tips"""
        tips = []

        # Tips based on failure patterns
        for pattern in failure_patterns:
            if pattern.severity == "high":
                tips.append(CoachingTip(
                    priority="high",
                    category="process",
                    title=f"Address: {pattern.title}",
                    message=pattern.description,
                    action_items=[pattern.coaching_tip],
                    expected_impact="Reduce blocked work and improve flow"
                ))

        # Tips based on health score components
        if health_score.velocity_score < 18:
            tips.append(CoachingTip(
                priority="high",
                category="velocity",
                title="Boost Sprint Velocity",
                message="Current velocity is below target, putting sprint goal at risk",
                action_items=[
                    "Focus on completing in-progress items before starting new ones",
                    "Remove blockers in daily standups",
                    "Consider swarming on critical items"
                ],
                expected_impact="Improve sprint goal achievement by 15-20%"
            ))

        if health_score.quality_score < 18:
            tips.append(CoachingTip(
                priority="high",
                category="quality",
                title="Reduce Stuck Items",
                message="High stuck rate is impacting team flow and delivery",
                action_items=[
                    "Review each stuck item and identify specific blockers",
                    "Escalate dependency issues immediately",
                    "Schedule focused unblocking sessions"
                ],
                expected_impact="Improve flow efficiency by 20-30%"
            ))

        # Tips based on improvement patterns
        for pattern in improvement_patterns:
            if pattern.trend == TrendDirection.DECLINING:
                tips.append(CoachingTip(
                    priority="medium",
                    category="improvement",
                    title=f"Address {pattern.pattern_type.replace('_', ' ').title()} Decline",
                    message=pattern.description,
                    action_items=[pattern.recommendation],
                    expected_impact="Reverse declining trend and stabilize performance"
                ))

        # Add a positive tip if doing well
        if health_score.overall_score >= 80 and not tips:
            tips.append(CoachingTip(
                priority="low",
                category="team",
                title="Keep Up the Great Work!",
                message="Team is performing well across all metrics",
                action_items=[
                    "Share successful practices with other teams",
                    "Document what's working in the retrospective",
                    "Consider taking on a stretch goal"
                ],
                expected_impact="Maintain high performance and share knowledge"
            ))

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        tips.sort(key=lambda t: priority_order.get(t.priority, 1))

        return tips[:5]  # Max 5 tips

    def _generate_executive_summary(
        self,
        health_score: TeamHealthScore,
        comparisons: List[MetricComparison],
        improvement_patterns: List[ImprovementPattern],
        coaching_tips: List[CoachingTip]
    ) -> str:
        """Generate executive summary"""
        summary_parts = []

        # Health score summary
        summary_parts.append(
            f"Team Health Score: {health_score.overall_score}/100 (Grade {health_score.grade} {health_score.grade_emoji})"
        )

        # Key comparison insights
        better_metrics = [c for c in comparisons if c.is_better]
        worse_metrics = [c for c in comparisons if not c.is_better]

        if better_metrics:
            summary_parts.append(
                f"Improving: {', '.join(c.display_name for c in better_metrics[:2])}"
            )

        if worse_metrics:
            summary_parts.append(
                f"Needs attention: {', '.join(c.display_name for c in worse_metrics[:2])}"
            )

        # Top priority
        high_priority_tips = [t for t in coaching_tips if t.priority == "high"]
        if high_priority_tips:
            summary_parts.append(f"Priority action: {high_priority_tips[0].title}")

        return " | ".join(summary_parts)


# Singleton instance
_coaching_engine: Optional[CoachingEngine] = None


def get_coaching_engine(config: Optional[Dict[str, Any]] = None) -> CoachingEngine:
    """Get or create singleton coaching engine instance"""
    global _coaching_engine

    if _coaching_engine is None:
        if config is None:
            raise ValueError("Config required for first initialization")
        _coaching_engine = CoachingEngine(config)

    return _coaching_engine

