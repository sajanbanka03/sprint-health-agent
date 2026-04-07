"""
ML-Based Predictions for Sprint Health Agent
Uses Monte Carlo simulation and historical analysis for accurate forecasting
"""
import logging
import random
import statistics
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from .models import SprintIssue, SprintInfo, SprintMetrics, Phase

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation"""
    simulations_run: int
    predicted_completion_points: float
    confidence_intervals: Dict[int, float]  # {50: 23.5, 75: 21.0, 90: 18.5}
    probability_of_completion: float
    risk_level: str  # "low", "medium", "high", "critical"
    likely_completion_date: Optional[date]
    forecast_details: Dict[str, Any]


@dataclass
class VelocityTrend:
    """Historical velocity analysis"""
    sprints_analyzed: int
    average_velocity: float
    median_velocity: float
    std_deviation: float
    velocity_trend: str  # "improving", "stable", "declining"
    trend_percentage: float
    historical_data: List[Dict[str, Any]]


@dataclass
class RiskAssessment:
    """Risk assessment for sprint items"""
    overall_risk_score: float  # 0-100
    risk_level: str
    risk_factors: List[Dict[str, Any]]
    at_risk_items: List[str]
    recommendations: List[str]


class MLPredictor:
    """
    Machine Learning based predictions for sprint health.
    Uses Monte Carlo simulation and historical pattern analysis.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ml_config = config.get('ml_predictions', {})
        self.simulations = self.ml_config.get('monte_carlo_simulations', 1000)
        self.confidence_levels = self.ml_config.get('confidence_levels', [50, 75, 90])
        self.historical_sprints = config.get('historical_sprints', 5)

    def run_monte_carlo_simulation(
        self,
        sprint_info: SprintInfo,
        metrics: SprintMetrics,
        historical_velocities: List[float]
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation to predict sprint completion probability.

        This simulates thousands of possible sprint outcomes based on
        historical velocity variance to give a probability distribution.

        Args:
            sprint_info: Current sprint information
            metrics: Current sprint metrics
            historical_velocities: List of velocities from past sprints

        Returns:
            MonteCarloResult with predictions and confidence intervals
        """
        if not historical_velocities:
            # No historical data - fall back to simple prediction
            return self._simple_prediction(sprint_info, metrics)

        # Calculate velocity statistics
        avg_velocity = statistics.mean(historical_velocities)
        if len(historical_velocities) > 1:
            std_dev = statistics.stdev(historical_velocities)
        else:
            std_dev = avg_velocity * 0.2  # Assume 20% variance if only one data point

        days_remaining = sprint_info.days_remaining
        remaining_work = metrics.remaining_story_points

        # Run simulations
        completion_counts = []
        simulated_completions = []

        for _ in range(self.simulations):
            # Sample velocity from normal distribution
            simulated_velocity = max(0, random.gauss(avg_velocity, std_dev))

            # Calculate work completed in remaining days
            # Add some daily variance too
            daily_variance = random.uniform(0.8, 1.2)
            work_completed = simulated_velocity * days_remaining * daily_variance / sprint_info.total_days

            total_completed = metrics.completed_story_points + work_completed
            simulated_completions.append(total_completed)

            # Did we complete all work?
            if total_completed >= metrics.total_story_points:
                completion_counts.append(1)
            else:
                completion_counts.append(0)

        # Calculate probability of completion
        probability = (sum(completion_counts) / self.simulations) * 100

        # Calculate confidence intervals
        simulated_completions.sort()
        confidence_intervals = {}
        for level in self.confidence_levels:
            percentile_idx = int(self.simulations * (1 - level / 100))
            confidence_intervals[level] = round(simulated_completions[percentile_idx], 1)

        # Calculate predicted completion (median)
        predicted_completion = statistics.median(simulated_completions)

        # Calculate likely completion date
        likely_completion_date = self._estimate_completion_date(
            sprint_info, metrics, avg_velocity
        )

        # Determine risk level
        risk_level = self._determine_risk_level(probability)

        return MonteCarloResult(
            simulations_run=self.simulations,
            predicted_completion_points=round(predicted_completion, 1),
            confidence_intervals=confidence_intervals,
            probability_of_completion=round(probability, 1),
            risk_level=risk_level,
            likely_completion_date=likely_completion_date,
            forecast_details={
                'average_velocity': round(avg_velocity, 2),
                'velocity_std_dev': round(std_dev, 2),
                'days_remaining': days_remaining,
                'remaining_work': remaining_work,
                'simulations': self.simulations
            }
        )

    def _simple_prediction(
        self,
        sprint_info: SprintInfo,
        metrics: SprintMetrics
    ) -> MonteCarloResult:
        """Fallback prediction when no historical data available"""
        days_elapsed = sprint_info.days_elapsed
        days_remaining = sprint_info.days_remaining

        if days_elapsed > 0:
            current_velocity = metrics.completed_story_points / days_elapsed
            predicted = metrics.completed_story_points + (current_velocity * days_remaining)
        else:
            predicted = metrics.total_story_points * 0.5  # Assume 50% if no data
            current_velocity = 0

        probability = min(100, (predicted / metrics.total_story_points) * 100) if metrics.total_story_points > 0 else 100

        return MonteCarloResult(
            simulations_run=0,
            predicted_completion_points=round(predicted, 1),
            confidence_intervals={50: predicted, 75: predicted * 0.9, 90: predicted * 0.8},
            probability_of_completion=round(probability, 1),
            risk_level=self._determine_risk_level(probability),
            likely_completion_date=None,
            forecast_details={
                'note': 'Simple prediction - no historical data available',
                'current_velocity': round(current_velocity, 2)
            }
        )

    def _estimate_completion_date(
        self,
        sprint_info: SprintInfo,
        metrics: SprintMetrics,
        velocity: float
    ) -> Optional[date]:
        """Estimate when the sprint work will actually be completed"""
        if velocity <= 0 or metrics.remaining_story_points <= 0:
            return sprint_info.end_date

        days_needed = (metrics.remaining_story_points / velocity) * sprint_info.total_days
        estimated_date = date.today() + timedelta(days=int(days_needed))

        return estimated_date

    def _determine_risk_level(self, probability: float) -> str:
        """Determine risk level based on completion probability"""
        if probability >= 85:
            return "low"
        elif probability >= 70:
            return "medium"
        elif probability >= 50:
            return "high"
        else:
            return "critical"

    def analyze_velocity_trend(
        self,
        historical_data: List[Dict[str, Any]]
    ) -> VelocityTrend:
        """
        Analyze velocity trends over multiple sprints.

        Args:
            historical_data: List of sprint data with completed_points

        Returns:
            VelocityTrend with analysis
        """
        if not historical_data:
            return VelocityTrend(
                sprints_analyzed=0,
                average_velocity=0,
                median_velocity=0,
                std_deviation=0,
                velocity_trend="unknown",
                trend_percentage=0,
                historical_data=[]
            )

        velocities = [d.get('completed_points', 0) for d in historical_data]

        avg = statistics.mean(velocities)
        median = statistics.median(velocities)
        std_dev = statistics.stdev(velocities) if len(velocities) > 1 else 0

        # Calculate trend (compare recent vs older)
        if len(velocities) >= 3:
            recent = statistics.mean(velocities[:2])  # Last 2 sprints
            older = statistics.mean(velocities[2:])   # Older sprints

            if older > 0:
                trend_pct = ((recent - older) / older) * 100
            else:
                trend_pct = 0

            if trend_pct > 10:
                trend = "improving"
            elif trend_pct < -10:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
            trend_pct = 0

        return VelocityTrend(
            sprints_analyzed=len(velocities),
            average_velocity=round(avg, 1),
            median_velocity=round(median, 1),
            std_deviation=round(std_dev, 1),
            velocity_trend=trend,
            trend_percentage=round(trend_pct, 1),
            historical_data=historical_data
        )

    def assess_item_risks(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo
    ) -> RiskAssessment:
        """
        Assess risks for individual sprint items and overall sprint.

        Uses pattern recognition to identify items likely to slip.

        Args:
            issues: List of sprint issues
            sprint_info: Sprint information

        Returns:
            RiskAssessment with detailed analysis
        """
        risk_factors = []
        at_risk_items = []
        total_risk_score = 0

        days_remaining = sprint_info.days_remaining

        for issue in issues:
            if issue.phase == Phase.DONE:
                continue

            item_risk_score = 0
            item_risks = []

            # Risk factor 1: Stuck for too long
            if issue.is_stuck:
                stuck_severity = min(issue.days_overdue * 15, 50)  # Max 50 points
                item_risk_score += stuck_severity
                item_risks.append(f"Stuck for {issue.days_in_current_status} days")

            # Risk factor 2: Large story still in early phase
            if issue.story_points >= 5:
                if issue.phase in [Phase.BACKLOG, Phase.IN_ANALYSIS]:
                    item_risk_score += 30
                    item_risks.append(f"Large story ({issue.story_points} SP) still in {issue.phase.value}")
                elif issue.phase == Phase.IN_DEV and days_remaining < 3:
                    item_risk_score += 25
                    item_risks.append(f"Large story in dev with only {days_remaining} days remaining")

            # Risk factor 3: Unassigned work
            if not issue.assignee and issue.phase not in [Phase.BACKLOG, Phase.DONE]:
                item_risk_score += 20
                item_risks.append("Unassigned work item")

            # Risk factor 4: Late sprint, early phase
            sprint_progress = sprint_info.days_elapsed / sprint_info.total_days if sprint_info.total_days > 0 else 0
            if sprint_progress > 0.6 and issue.phase in [Phase.BACKLOG, Phase.IN_ANALYSIS]:
                item_risk_score += 35
                item_risks.append(f"Sprint {sprint_progress*100:.0f}% complete but item still in {issue.phase.value}")

            # Flag high-risk items
            if item_risk_score >= 30:
                at_risk_items.append(issue.key)
                risk_factors.append({
                    'issue_key': issue.key,
                    'summary': issue.summary,
                    'risk_score': item_risk_score,
                    'risks': item_risks
                })

            total_risk_score += item_risk_score

        # Normalize overall risk score
        active_items = len([i for i in issues if i.phase != Phase.DONE])
        if active_items > 0:
            normalized_risk = min(100, total_risk_score / active_items)
        else:
            normalized_risk = 0

        # Determine overall risk level
        if normalized_risk >= 60:
            overall_level = "critical"
        elif normalized_risk >= 40:
            overall_level = "high"
        elif normalized_risk >= 20:
            overall_level = "medium"
        else:
            overall_level = "low"

        # Generate recommendations
        recommendations = self._generate_risk_recommendations(risk_factors, sprint_info)

        return RiskAssessment(
            overall_risk_score=round(normalized_risk, 1),
            risk_level=overall_level,
            risk_factors=sorted(risk_factors, key=lambda x: x['risk_score'], reverse=True),
            at_risk_items=at_risk_items,
            recommendations=recommendations
        )

    def _generate_risk_recommendations(
        self,
        risk_factors: List[Dict[str, Any]],
        sprint_info: SprintInfo
    ) -> List[str]:
        """Generate actionable recommendations based on risks"""
        recommendations = []

        # Group risks by type
        stuck_items = [rf for rf in risk_factors if any('Stuck' in r for r in rf['risks'])]
        large_late_items = [rf for rf in risk_factors if any('Large story' in r for r in rf['risks'])]
        unassigned_items = [rf for rf in risk_factors if any('Unassigned' in r for r in rf['risks'])]

        if stuck_items:
            recommendations.append(
                f"🔴 {len(stuck_items)} items are stuck - consider daily standups focused on unblocking"
            )

        if large_late_items:
            recommendations.append(
                f"⚠️ {len(large_late_items)} large stories at risk - consider splitting or pairing"
            )

        if unassigned_items:
            recommendations.append(
                f"👤 {len(unassigned_items)} items have no assignee - assign immediately"
            )

        if sprint_info.days_remaining <= 2 and len(risk_factors) > 3:
            recommendations.append(
                "🎯 Sprint ending soon with multiple risks - consider scope negotiation"
            )

        return recommendations

    def predict_item_completion(
        self,
        issue: SprintIssue,
        sprint_info: SprintInfo,
        avg_cycle_times: Dict[Phase, float]
    ) -> Dict[str, Any]:
        """
        Predict whether a specific item will complete in the sprint.

        Args:
            issue: The issue to predict
            sprint_info: Sprint information
            avg_cycle_times: Average time in each phase from historical data

        Returns:
            Prediction details for the item
        """
        if issue.phase == Phase.DONE:
            return {
                'issue_key': issue.key,
                'will_complete': True,
                'confidence': 100,
                'predicted_completion': 'Already done'
            }

        # Calculate remaining phases
        phase_order = [
            Phase.BACKLOG, Phase.IN_ANALYSIS, Phase.IN_DEV,
            Phase.READY_FOR_SIT, Phase.IN_SIT, Phase.IN_TPO_REVIEW, Phase.DONE
        ]

        current_idx = phase_order.index(issue.phase) if issue.phase in phase_order else 0
        remaining_phases = phase_order[current_idx + 1:]

        # Estimate time to completion
        estimated_days = issue.days_in_current_status  # Already spent

        for phase in remaining_phases:
            avg_time = avg_cycle_times.get(phase, 2)  # Default 2 days
            # Add variance
            estimated_days += avg_time * random.uniform(0.8, 1.3)

        days_remaining = sprint_info.days_remaining
        will_complete = estimated_days <= days_remaining

        # Calculate confidence
        if will_complete:
            buffer = days_remaining - estimated_days
            confidence = min(95, 50 + buffer * 10)
        else:
            overrun = estimated_days - days_remaining
            confidence = max(5, 50 - overrun * 10)

        return {
            'issue_key': issue.key,
            'summary': issue.summary,
            'current_phase': issue.phase.value,
            'will_complete': will_complete,
            'confidence': round(confidence),
            'estimated_days_remaining': round(estimated_days, 1),
            'sprint_days_remaining': days_remaining
        }

