"""
Sprint Health Analyzer
Calculates metrics, predictions, and recommendations
Now with ML predictions, charts, and custom metrics!
"""
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from collections import defaultdict

from .models import (
    SprintIssue, SprintInfo, SprintMetrics, PhaseMetrics,
    VelocityMetrics, StuckSummary, Recommendation,
    SprintHealthReport, Phase, HealthStatus
)
from .jira_client import JiraClient
from .ml_predictor import MLPredictor, MonteCarloResult, VelocityTrend, RiskAssessment
from .charts import ChartGenerator, ChartData
from .custom_metrics import MetricsEngine, MetricResult

logger = logging.getLogger(__name__)


class SprintAnalyzer:
    """Analyzes sprint data and generates health reports"""

    def __init__(self, config: Dict[str, Any], jira_client: JiraClient):
        """
        Initialize analyzer

        Args:
            config: Application configuration
            jira_client: Initialized JiraClient
        """
        self.config = config
        self.jira = jira_client
        self.thresholds = config.get('thresholds', {})

        # Initialize ML predictor
        self.ml_predictor = MLPredictor(config)

        # Initialize chart generator
        self.chart_generator = ChartGenerator(config)

        # Initialize custom metrics engine
        self.metrics_engine = MetricsEngine(config)

    def analyze_sprint(self, sprint_info: Optional[SprintInfo] = None) -> SprintHealthReport:
        """
        Perform complete sprint health analysis

        Args:
            sprint_info: Sprint to analyze (uses active sprint if None)

        Returns:
            Complete SprintHealthReport
        """
        # Get active sprint if not provided
        if sprint_info is None:
            sprint_info = self.jira.get_active_sprint()
            if sprint_info is None:
                raise ValueError("No active sprint found")

        logger.info(f"Analyzing sprint: {sprint_info.name}")

        # Fetch all sprint issues
        issues = self.jira.get_sprint_issues(sprint_info.id)

        # Calculate all metrics
        metrics = self._calculate_sprint_metrics(issues)
        phase_breakdown = self._calculate_phase_breakdown(issues)

        # Get historical velocity data for ML predictions
        historical_data = self.jira.get_velocity(num_sprints=self.config.get('historical_sprints', 5))
        historical_velocities = [d.get('completed_points', 0) for d in historical_data]

        # Run ML-based predictions
        ml_predictions = self.ml_predictor.run_monte_carlo_simulation(
            sprint_info, metrics, historical_velocities
        )

        # Analyze velocity trends
        velocity_trend = self.ml_predictor.analyze_velocity_trend(historical_data)

        # Assess item-level risks
        risk_assessment = self.ml_predictor.assess_item_risks(issues, sprint_info)

        # Generate chart data
        historical_snapshots = self.chart_generator.load_historical_snapshots(sprint_info.id)
        chart_data = self.chart_generator.generate_chart_data(
            sprint_info, metrics, historical_snapshots
        )

        # Calculate custom metrics
        custom_metrics = self.metrics_engine.calculate_all(issues, sprint_info, metrics)

        # Original velocity calculation (kept for compatibility)
        velocity = self._calculate_velocity_metrics(sprint_info, metrics, issues)

        # Override with ML predictions if available
        if ml_predictions.simulations_run > 0:
            velocity.completion_probability = ml_predictions.probability_of_completion
            velocity.predicted_completion_points = ml_predictions.predicted_completion_points

        stuck_summary = self._calculate_stuck_summary(issues)
        health_status = self._determine_health_status(velocity.completion_probability)

        # Generate recommendations (including ML-based ones)
        recommendations = self._generate_recommendations(
            sprint_info, metrics, velocity, stuck_summary, phase_breakdown,
            ml_predictions, risk_assessment, custom_metrics
        )

        report = SprintHealthReport(
            generated_at=datetime.now(),
            sprint_info=sprint_info,
            metrics=metrics,
            velocity=velocity,
            phase_breakdown=phase_breakdown,
            stuck_summary=stuck_summary,
            health_status=health_status,
            recommendations=recommendations,
            all_issues=issues
        )

        # Attach additional data to report for extended usage
        report.ml_predictions = ml_predictions
        report.velocity_trend = velocity_trend
        report.risk_assessment = risk_assessment
        report.chart_data = chart_data
        report.custom_metrics = custom_metrics

        return report

    def _calculate_sprint_metrics(self, issues: List[SprintIssue]) -> SprintMetrics:
        """Calculate basic sprint metrics"""
        total_issues = len(issues)
        total_points = sum(i.story_points for i in issues)

        completed = [i for i in issues if i.phase == Phase.DONE]
        completed_issues = len(completed)
        completed_points = sum(i.story_points for i in completed)

        return SprintMetrics(
            total_issues=total_issues,
            total_story_points=total_points,
            completed_issues=completed_issues,
            completed_story_points=completed_points,
            remaining_issues=total_issues - completed_issues,
            remaining_story_points=total_points - completed_points
        )

    def _calculate_phase_breakdown(self, issues: List[SprintIssue]) -> List[PhaseMetrics]:
        """Calculate metrics for each phase"""
        # Group issues by phase
        phase_issues: Dict[Phase, List[SprintIssue]] = defaultdict(list)
        for issue in issues:
            phase_issues[issue.phase].append(issue)

        total_issues = len(issues)
        phase_display_names = {
            Phase.BACKLOG: "Backlog",
            Phase.IN_ANALYSIS: "In Analysis",
            Phase.IN_DEV: "In Development",
            Phase.READY_FOR_SIT: "Ready for SIT",
            Phase.IN_SIT: "In SIT",
            Phase.IN_TPO_REVIEW: "In TPO Review",
            Phase.DONE: "Done",
            Phase.UNKNOWN: "Unknown"
        }

        # WIP limits from config
        wip_limits = {
            Phase.IN_DEV: self.thresholds.get('wip_limit_in_dev'),
            Phase.IN_SIT: self.thresholds.get('wip_limit_in_sit')
        }

        breakdown = []

        # Process phases in order
        phase_order = [
            Phase.BACKLOG, Phase.IN_ANALYSIS, Phase.IN_DEV,
            Phase.READY_FOR_SIT, Phase.IN_SIT, Phase.IN_TPO_REVIEW,
            Phase.DONE
        ]

        for phase in phase_order:
            issues_in_phase = phase_issues.get(phase, [])
            count = len(issues_in_phase)
            points = sum(i.story_points for i in issues_in_phase)
            percentage = (count / total_issues * 100) if total_issues > 0 else 0

            stuck_issues = [i for i in issues_in_phase if i.is_stuck]

            wip_limit = wip_limits.get(phase)
            wip_exceeded = wip_limit is not None and count > wip_limit

            breakdown.append(PhaseMetrics(
                phase=phase,
                phase_display_name=phase_display_names[phase],
                issue_count=count,
                story_points=points,
                percentage_of_total=round(percentage, 1),
                stuck_count=len(stuck_issues),
                stuck_issues=stuck_issues,
                wip_limit=wip_limit,
                wip_exceeded=wip_exceeded
            ))

        return breakdown

    def _calculate_velocity_metrics(
        self,
        sprint_info: SprintInfo,
        metrics: SprintMetrics,
        issues: List[SprintIssue]
    ) -> VelocityMetrics:
        """Calculate velocity and predict completion probability"""

        days_elapsed = sprint_info.days_elapsed
        days_remaining = sprint_info.days_remaining
        total_days = sprint_info.total_days

        # Calculate current daily velocity
        if days_elapsed > 0:
            daily_velocity = metrics.completed_story_points / days_elapsed
        else:
            daily_velocity = 0.0

        # Calculate required velocity to complete all remaining work
        if days_remaining > 0:
            required_velocity = metrics.remaining_story_points / days_remaining
        else:
            required_velocity = float('inf') if metrics.remaining_story_points > 0 else 0

        # Predict completion
        predicted_completion = metrics.completed_story_points + (daily_velocity * days_remaining)

        # Calculate shortfall
        shortfall = max(0, metrics.total_story_points - predicted_completion)

        # Calculate completion probability
        # Simple model: based on ratio of predicted vs total
        if metrics.total_story_points > 0:
            raw_probability = (predicted_completion / metrics.total_story_points) * 100
            # Cap between 0 and 100
            completion_probability = max(0, min(100, raw_probability))
        else:
            completion_probability = 100.0  # No work = 100% complete

        # Adjust for work in progress - items close to done boost probability
        in_review_points = sum(
            i.story_points for i in issues
            if i.phase in [Phase.IN_SIT, Phase.IN_TPO_REVIEW]
        )
        if metrics.total_story_points > 0:
            # Items in late stages likely to complete
            boost = (in_review_points / metrics.total_story_points) * 10
            completion_probability = min(100, completion_probability + boost)

        return VelocityMetrics(
            daily_velocity=round(daily_velocity, 2),
            required_velocity=round(required_velocity, 2) if required_velocity != float('inf') else 999,
            completion_probability=round(completion_probability, 1),
            predicted_completion_points=round(predicted_completion, 1),
            shortfall_points=round(shortfall, 1)
        )

    def _calculate_stuck_summary(self, issues: List[SprintIssue]) -> StuckSummary:
        """Summarize stuck items"""
        stuck_issues = [i for i in issues if i.is_stuck]

        # Group by phase
        stuck_by_phase: Dict[Phase, List[SprintIssue]] = defaultdict(list)
        for issue in stuck_issues:
            stuck_by_phase[issue.phase].append(issue)

        # Sort each phase's stuck issues by days overdue
        for phase in stuck_by_phase:
            stuck_by_phase[phase].sort(key=lambda x: x.days_overdue, reverse=True)

        # Get most critical items (sorted by days overdue across all phases)
        most_critical = sorted(stuck_issues, key=lambda x: x.days_overdue, reverse=True)[:10]

        return StuckSummary(
            total_stuck_count=len(stuck_issues),
            total_stuck_points=sum(i.story_points for i in stuck_issues),
            stuck_by_phase=dict(stuck_by_phase),
            most_critical_items=most_critical
        )

    def _determine_health_status(self, completion_probability: float) -> HealthStatus:
        """Determine overall health status"""
        warning_threshold = self.thresholds.get('completion_probability_warning', 70)
        critical_threshold = self.thresholds.get('completion_probability_critical', 50)

        if completion_probability >= warning_threshold:
            return HealthStatus.HEALTHY
        elif completion_probability >= critical_threshold:
            return HealthStatus.AT_RISK
        else:
            return HealthStatus.CRITICAL

    def _generate_recommendations(
        self,
        sprint_info: SprintInfo,
        metrics: SprintMetrics,
        velocity: VelocityMetrics,
        stuck_summary: StuckSummary,
        phase_breakdown: List[PhaseMetrics],
        ml_predictions: Optional[MonteCarloResult] = None,
        risk_assessment: Optional[RiskAssessment] = None,
        custom_metrics: Optional[List[MetricResult]] = None
    ) -> List[Recommendation]:
        """Generate actionable recommendations"""
        recommendations = []

        # ML-based risk recommendations
        if risk_assessment and risk_assessment.recommendations:
            for rec in risk_assessment.recommendations[:2]:
                recommendations.append(Recommendation(
                    priority="high" if "🔴" in rec else "medium",
                    category="ml_risk",
                    message=rec,
                    affected_issues=risk_assessment.at_risk_items[:3]
                ))

        # Critical stuck items
        for issue in stuck_summary.most_critical_items[:3]:
            if issue.days_overdue >= 3:
                recommendations.append(Recommendation(
                    priority="high",
                    category="stuck_item",
                    message=f"{issue.key} has been stuck in {issue.status} for {issue.days_in_current_status} days - needs immediate attention",
                    affected_issues=[issue.key]
                ))

        # ML prediction based recommendations
        if ml_predictions and ml_predictions.simulations_run > 0:
            if ml_predictions.risk_level == "critical":
                recommendations.append(Recommendation(
                    priority="high",
                    category="ml_prediction",
                    message=f"Monte Carlo simulation ({ml_predictions.simulations_run} runs) shows only {ml_predictions.probability_of_completion:.0f}% completion probability",
                    affected_issues=[]
                ))

            # Confidence interval insight
            if 90 in ml_predictions.confidence_intervals:
                ci_90 = ml_predictions.confidence_intervals[90]
                if ci_90 < metrics.total_story_points * 0.8:
                    recommendations.append(Recommendation(
                        priority="medium",
                        category="ml_prediction",
                        message=f"90% confidence: Sprint will complete at least {ci_90:.0f} SP (target: {metrics.total_story_points:.0f} SP)",
                        affected_issues=[]
                    ))

        # WIP limit violations (if enabled)
        wip_config = self.config.get('wip_limits', {})
        if wip_config.get('enabled', False):
            for pm in phase_breakdown:
                wip_limit = wip_config.get(pm.phase.value)
                if wip_limit and pm.issue_count > wip_limit:
                    recommendations.append(Recommendation(
                        priority="medium",
                        category="wip",
                        message=f"WIP limit exceeded in {pm.phase_display_name}: {pm.issue_count} items (limit: {wip_limit})",
                        affected_issues=[i.key for i in pm.stuck_issues]
                    ))

        # Velocity concerns
        if velocity.completion_probability < 70:
            shortfall_msg = f"Current velocity ({velocity.daily_velocity} SP/day) suggests {velocity.shortfall_points} SP shortfall"
            recommendations.append(Recommendation(
                priority="high" if velocity.completion_probability < 50 else "medium",
                category="velocity",
                message=shortfall_msg,
                affected_issues=[]
            ))

        # Scope recommendation if critical
        if velocity.completion_probability < 50 and sprint_info.days_remaining > 0:
            recommendations.append(Recommendation(
                priority="high",
                category="scope",
                message="Consider scope reduction - sprint is at high risk of not completing committed work",
                affected_issues=[]
            ))

        # Bottleneck detection
        ready_for_sit = next((pm for pm in phase_breakdown if pm.phase == Phase.READY_FOR_SIT), None)
        if ready_for_sit and ready_for_sit.issue_count >= 3:
            recommendations.append(Recommendation(
                priority="medium",
                category="bottleneck",
                message=f"Bottleneck detected: {ready_for_sit.issue_count} items waiting for SIT",
                affected_issues=[i.key for i in ready_for_sit.stuck_issues]
            ))

        # Custom metrics based recommendations
        if custom_metrics:
            for cm in custom_metrics:
                if cm.threshold_status == "critical":
                    recommendations.append(Recommendation(
                        priority="high",
                        category="custom_metric",
                        message=f"{cm.name.replace('_', ' ').title()}: {cm.display_value} - {cm.description}",
                        affected_issues=cm.details.get('items', []) if cm.details else []
                    ))

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 3))

        return recommendations

