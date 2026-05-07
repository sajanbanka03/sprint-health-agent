"""
Sprint Goal Predictor Module for Sprint Health Agent
Provides enhanced goal-focused predictions and insights

Features:
- Sprint goal probability (Monte Carlo powered)
- Commitment vs historical average comparison
- Velocity gap analysis
- Items at risk of not completing
- Predicted shortfall calculation

Author: Sajan Banka
Created: April 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from .models import SprintIssue, SprintInfo, SprintMetrics, VelocityMetrics, Phase

logger = logging.getLogger(__name__)


@dataclass
class AtRiskItem:
    """An item at risk of not completing"""
    key: str
    summary: str
    story_points: float
    assignee: Optional[str]
    status: str
    phase: str
    risk_score: float  # 0-100, higher = more at risk
    risk_reasons: List[str]

    @property
    def risk_level(self) -> str:
        if self.risk_score >= 80:
            return "critical"
        elif self.risk_score >= 60:
            return "high"
        elif self.risk_score >= 40:
            return "medium"
        return "low"


@dataclass
class SprintGoalPrediction:
    """Complete sprint goal prediction data"""
    # Core probability
    goal_probability: float  # 0-100%
    probability_display: str  # "78% likely to achieve sprint goal"

    # Confidence intervals
    confidence_50: float  # SP likely to complete at 50% confidence
    confidence_75: float  # SP likely to complete at 75% confidence
    confidence_90: float  # SP likely to complete at 90% confidence

    # Commitment comparison
    committed_sp: float
    historical_avg_sp: float
    commitment_delta: float  # positive = over-committed
    commitment_status: str  # "over", "under", "optimal"
    commitment_message: str

    # Velocity analysis
    current_velocity: float  # SP/day actual
    required_velocity: float  # SP/day needed to complete
    velocity_gap: float  # negative = behind
    velocity_status: str  # "ahead", "behind", "on_track"
    velocity_message: str

    # Predicted shortfall
    predicted_completion_sp: float
    shortfall_sp: float  # SP likely to miss
    shortfall_items: int  # Number of items likely to miss

    # At-risk items
    at_risk_items: List[AtRiskItem]
    at_risk_sp: float

    # Sprint goal text (if available)
    sprint_goal: Optional[str]

    # Health indicators
    health_emoji: str
    health_color: str  # "green", "yellow", "red"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON"""
        return {
            'goal_probability': self.goal_probability,
            'probability_display': self.probability_display,
            'confidence': {
                '50': self.confidence_50,
                '75': self.confidence_75,
                '90': self.confidence_90
            },
            'commitment': {
                'committed_sp': self.committed_sp,
                'historical_avg_sp': self.historical_avg_sp,
                'delta': self.commitment_delta,
                'status': self.commitment_status,
                'message': self.commitment_message
            },
            'velocity': {
                'current': self.current_velocity,
                'required': self.required_velocity,
                'gap': self.velocity_gap,
                'status': self.velocity_status,
                'message': self.velocity_message
            },
            'shortfall': {
                'predicted_completion_sp': self.predicted_completion_sp,
                'shortfall_sp': self.shortfall_sp,
                'shortfall_items': self.shortfall_items
            },
            'at_risk': {
                'count': len(self.at_risk_items),
                'total_sp': self.at_risk_sp,
                'items': [
                    {
                        'key': item.key,
                        'summary': item.summary,
                        'story_points': item.story_points,
                        'assignee': item.assignee,
                        'risk_score': item.risk_score,
                        'risk_level': item.risk_level,
                        'reasons': item.risk_reasons
                    }
                    for item in self.at_risk_items[:5]  # Top 5
                ]
            },
            'sprint_goal': self.sprint_goal,
            'health': {
                'emoji': self.health_emoji,
                'color': self.health_color
            }
        }


class SprintGoalPredictor:
    """
    Generates sprint goal predictions and insights.

    Usage:
        predictor = SprintGoalPredictor(config)
        prediction = predictor.generate_prediction(
            sprint_info, metrics, velocity, issues,
            ml_predictions, historical_data
        )
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.thresholds = config.get('thresholds', {})

    def generate_prediction(
        self,
        sprint_info: SprintInfo,
        metrics: SprintMetrics,
        velocity: VelocityMetrics,
        issues: List[SprintIssue],
        ml_predictions: Any = None,
        historical_data: List[Dict[str, Any]] = None
    ) -> SprintGoalPrediction:
        """
        Generate comprehensive sprint goal prediction.

        Args:
            sprint_info: Current sprint information
            metrics: Sprint metrics
            velocity: Velocity metrics
            issues: All sprint issues
            ml_predictions: MonteCarloResult from ML predictor
            historical_data: Historical sprint velocity data

        Returns:
            SprintGoalPrediction with full analysis
        """
        # Get goal probability
        if ml_predictions and hasattr(ml_predictions, 'probability_of_completion'):
            goal_probability = ml_predictions.probability_of_completion
        else:
            goal_probability = velocity.completion_probability

        # Get confidence intervals
        if ml_predictions and hasattr(ml_predictions, 'confidence_intervals'):
            ci = ml_predictions.confidence_intervals
            confidence_50 = ci.get(50, metrics.completed_story_points)
            confidence_75 = ci.get(75, metrics.completed_story_points)
            confidence_90 = ci.get(90, metrics.completed_story_points)
        else:
            # Estimate from velocity
            predicted = velocity.predicted_completion_points
            confidence_50 = predicted
            confidence_75 = predicted * 0.9
            confidence_90 = predicted * 0.8

        # Calculate commitment comparison
        historical_avg = self._calculate_historical_average(historical_data)
        commitment_delta = metrics.total_story_points - historical_avg

        if commitment_delta > historical_avg * 0.15:
            commitment_status = "over"
            commitment_message = (
                f"Over-committed by {commitment_delta:.0f} SP "
                f"({metrics.total_story_points:.0f} SP vs avg {historical_avg:.0f} SP)"
            )
        elif commitment_delta < -historical_avg * 0.15:
            commitment_status = "under"
            commitment_message = (
                f"Under-committed by {abs(commitment_delta):.0f} SP "
                f"({metrics.total_story_points:.0f} SP vs avg {historical_avg:.0f} SP)"
            )
        else:
            commitment_status = "optimal"
            commitment_message = (
                f"Commitment aligned with team average "
                f"({metrics.total_story_points:.0f} SP vs avg {historical_avg:.0f} SP)"
            )

        # Velocity gap analysis
        velocity_gap = velocity.daily_velocity - velocity.required_velocity

        if velocity_gap >= 0.5:
            velocity_status = "ahead"
            velocity_message = (
                f"Ahead of target! Current {velocity.daily_velocity:.1f} SP/day, "
                f"need only {velocity.required_velocity:.1f} SP/day"
            )
        elif velocity_gap >= -0.5:
            velocity_status = "on_track"
            velocity_message = (
                f"On track: {velocity.daily_velocity:.1f} SP/day vs "
                f"{velocity.required_velocity:.1f} SP/day needed"
            )
        else:
            velocity_status = "behind"
            velocity_message = (
                f"Behind target: {velocity.daily_velocity:.1f} SP/day, "
                f"need {velocity.required_velocity:.1f} SP/day (+{abs(velocity_gap):.1f} gap)"
            )

        # Predicted completion and shortfall
        predicted_completion = velocity.predicted_completion_points
        shortfall_sp = max(0, metrics.total_story_points - predicted_completion)

        # Identify at-risk items
        at_risk_items = self._identify_at_risk_items(
            issues, sprint_info, velocity, shortfall_sp
        )
        at_risk_sp = sum(item.story_points for item in at_risk_items)
        shortfall_items = len([i for i in at_risk_items if i.risk_score >= 50])

        # Generate probability display text
        probability_display = self._generate_probability_text(goal_probability)

        # Determine health indicators
        health_emoji, health_color = self._get_health_indicators(goal_probability)

        return SprintGoalPrediction(
            goal_probability=round(goal_probability, 1),
            probability_display=probability_display,
            confidence_50=round(confidence_50, 1),
            confidence_75=round(confidence_75, 1),
            confidence_90=round(confidence_90, 1),
            committed_sp=metrics.total_story_points,
            historical_avg_sp=round(historical_avg, 1),
            commitment_delta=round(commitment_delta, 1),
            commitment_status=commitment_status,
            commitment_message=commitment_message,
            current_velocity=round(velocity.daily_velocity, 2),
            required_velocity=round(velocity.required_velocity, 2),
            velocity_gap=round(velocity_gap, 2),
            velocity_status=velocity_status,
            velocity_message=velocity_message,
            predicted_completion_sp=round(predicted_completion, 1),
            shortfall_sp=round(shortfall_sp, 1),
            shortfall_items=shortfall_items,
            at_risk_items=at_risk_items,
            at_risk_sp=round(at_risk_sp, 1),
            sprint_goal=sprint_info.goal,
            health_emoji=health_emoji,
            health_color=health_color
        )

    def _calculate_historical_average(
        self,
        historical_data: List[Dict[str, Any]]
    ) -> float:
        """Calculate average completed SP from historical data"""
        if not historical_data:
            return 0.0

        completed_points = []
        for sprint in historical_data:
            points = sprint.get('completed_points', 0)
            if points > 0:
                completed_points.append(points)

        if not completed_points:
            return 0.0

        return sum(completed_points) / len(completed_points)

    def _identify_at_risk_items(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        velocity: VelocityMetrics,
        shortfall_sp: float
    ) -> List[AtRiskItem]:
        """Identify items at risk of not completing"""
        at_risk = []

        # Only analyze items not yet done
        remaining_items = [i for i in issues if i.phase != Phase.DONE]

        for issue in remaining_items:
            risk_score = 0
            risk_reasons = []

            # Factor 1: Days remaining vs typical completion time
            days_left = sprint_info.days_remaining
            if days_left <= 1 and issue.phase not in [Phase.IN_TPO_REVIEW]:
                risk_score += 40
                risk_reasons.append(f"Only {days_left} day(s) left")
            elif days_left <= 2 and issue.phase in [Phase.BACKLOG, Phase.IN_ANALYSIS]:
                risk_score += 35
                risk_reasons.append("Not in development with only 2 days left")

            # Factor 2: Item is stuck
            if issue.is_stuck:
                risk_score += 30
                risk_reasons.append(f"Stuck for {issue.days_in_current_status} days")

            # Factor 3: Large story points with little time
            if issue.story_points >= 5 and days_left <= 2:
                risk_score += 20
                risk_reasons.append(f"Large item ({issue.story_points} SP) near sprint end")

            # Factor 4: Early phase with limited time
            if issue.phase in [Phase.BACKLOG, Phase.IN_ANALYSIS] and days_left <= 3:
                risk_score += 25
                risk_reasons.append(f"Still in early phase ({issue.phase.value})")

            # Factor 5: No assignee
            if not issue.assignee:
                risk_score += 15
                risk_reasons.append("No assignee")

            # Factor 6: Velocity shortfall (spread risk across remaining items)
            if shortfall_sp > 0 and len(remaining_items) > 0:
                # Items with more SP are more likely to be dropped
                sp_risk = (issue.story_points / sum(i.story_points for i in remaining_items)) * 20
                risk_score += sp_risk

            # Cap risk score at 100
            risk_score = min(100, risk_score)

            if risk_score >= 30:  # Only include items with meaningful risk
                at_risk.append(AtRiskItem(
                    key=issue.key,
                    summary=issue.summary,
                    story_points=issue.story_points,
                    assignee=issue.assignee,
                    status=issue.status,
                    phase=issue.phase.value,
                    risk_score=round(risk_score, 1),
                    risk_reasons=risk_reasons
                ))

        # Sort by risk score (highest first)
        at_risk.sort(key=lambda x: -x.risk_score)

        return at_risk

    def _generate_probability_text(self, probability: float) -> str:
        """Generate human-readable probability text"""
        if probability >= 90:
            return f"{probability:.0f}% confident - Sprint goal well within reach!"
        elif probability >= 75:
            return f"{probability:.0f}% likely to achieve sprint goal"
        elif probability >= 50:
            return f"{probability:.0f}% chance - Sprint goal at moderate risk"
        elif probability >= 25:
            return f"{probability:.0f}% chance - Sprint goal at high risk"
        else:
            return f"{probability:.0f}% - Sprint goal unlikely without intervention"

    def _get_health_indicators(self, probability: float) -> Tuple[str, str]:
        """Get emoji and color based on probability"""
        if probability >= 80:
            return "🟢", "green"
        elif probability >= 50:
            return "🟡", "yellow"
        else:
            return "🔴", "red"


# Singleton instance
_goal_predictor: Optional[SprintGoalPredictor] = None


def get_goal_predictor(config: Optional[Dict[str, Any]] = None) -> SprintGoalPredictor:
    """Get or create singleton goal predictor instance"""
    global _goal_predictor

    if _goal_predictor is None:
        if config is None:
            raise ValueError("Config required for first initialization")
        _goal_predictor = SprintGoalPredictor(config)

    return _goal_predictor

