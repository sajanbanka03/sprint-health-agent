"""
Custom Metrics Framework for Sprint Health Agent
Extensible system for adding custom team-specific metrics
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from .models import SprintIssue, SprintInfo, SprintMetrics, Phase

logger = logging.getLogger(__name__)


@dataclass
class MetricResult:
    """Result of a custom metric calculation"""
    name: str
    value: Any
    unit: str
    display_value: str
    description: str
    trend: Optional[str] = None  # "up", "down", "stable"
    trend_is_good: Optional[bool] = None
    threshold_status: Optional[str] = None  # "good", "warning", "critical"
    details: Optional[Dict[str, Any]] = None


class BaseMetric(ABC):
    """
    Base class for custom metrics.

    To create a custom metric:
    1. Subclass BaseMetric
    2. Implement calculate() method
    3. Register with MetricsEngine

    Example:
    ```python
    class BugRatioMetric(BaseMetric):
        name = "bug_ratio"
        display_name = "Bug to Story Ratio"
        description = "Ratio of bugs to stories in sprint"

        def calculate(self, issues, sprint_info, metrics):
            bugs = len([i for i in issues if i.issue_type == 'Bug'])
            stories = len([i for i in issues if i.issue_type == 'Story'])
            ratio = bugs / stories if stories > 0 else 0

            return MetricResult(
                name=self.name,
                value=ratio,
                unit="ratio",
                display_value=f"{ratio:.2f}",
                description=self.description,
                threshold_status="good" if ratio < 0.3 else "warning"
            )
    ```
    """

    name: str = "base_metric"
    display_name: str = "Base Metric"
    description: str = "Base metric description"
    unit: str = ""

    @abstractmethod
    def calculate(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        metrics: SprintMetrics
    ) -> MetricResult:
        """
        Calculate the metric value.

        Args:
            issues: All issues in the sprint
            sprint_info: Sprint information
            metrics: Basic sprint metrics

        Returns:
            MetricResult with calculated value
        """
        pass


# ============================================
# Built-in Custom Metrics
# ============================================

class BugRatioMetric(BaseMetric):
    """Ratio of bugs to stories in sprint"""
    name = "bug_ratio"
    display_name = "Bug to Story Ratio"
    description = "Number of bugs per story - lower is better"
    unit = "ratio"

    def calculate(self, issues, sprint_info, metrics):
        bugs = len([i for i in issues if i.issue_type.lower() == 'bug'])
        stories = len([i for i in issues if i.issue_type.lower() == 'story'])
        ratio = bugs / stories if stories > 0 else 0

        if ratio <= 0.2:
            status = "good"
        elif ratio <= 0.5:
            status = "warning"
        else:
            status = "critical"

        return MetricResult(
            name=self.name,
            value=round(ratio, 2),
            unit=self.unit,
            display_value=f"{ratio:.2f}",
            description=self.description,
            threshold_status=status,
            details={'bugs': bugs, 'stories': stories}
        )


class UnassignedWorkMetric(BaseMetric):
    """Track unassigned work items"""
    name = "unassigned_work"
    display_name = "Unassigned Work Items"
    description = "Number of active items without assignee"
    unit = "items"

    def calculate(self, issues, sprint_info, metrics):
        active_issues = [i for i in issues if i.phase not in [Phase.BACKLOG, Phase.DONE]]
        unassigned = [i for i in active_issues if not i.assignee]
        count = len(unassigned)

        if count == 0:
            status = "good"
        elif count <= 2:
            status = "warning"
        else:
            status = "critical"

        return MetricResult(
            name=self.name,
            value=count,
            unit=self.unit,
            display_value=str(count),
            description=self.description,
            threshold_status=status,
            details={'unassigned_keys': [i.key for i in unassigned]}
        )


class AverageAgeMetric(BaseMetric):
    """Average age of in-progress items"""
    name = "average_age"
    display_name = "Average Item Age"
    description = "Average days items have been in current status"
    unit = "days"

    def calculate(self, issues, sprint_info, metrics):
        active_issues = [i for i in issues if i.phase not in [Phase.BACKLOG, Phase.DONE]]

        if not active_issues:
            return MetricResult(
                name=self.name,
                value=0,
                unit=self.unit,
                display_value="0 days",
                description=self.description,
                threshold_status="good"
            )

        total_age = sum(i.days_in_current_status for i in active_issues)
        avg_age = total_age / len(active_issues)

        if avg_age <= 2:
            status = "good"
        elif avg_age <= 4:
            status = "warning"
        else:
            status = "critical"

        return MetricResult(
            name=self.name,
            value=round(avg_age, 1),
            unit=self.unit,
            display_value=f"{avg_age:.1f} days",
            description=self.description,
            threshold_status=status
        )


class FlowEfficiencyMetric(BaseMetric):
    """
    Flow efficiency - ratio of work time to total time.
    Approximated by ratio of items in active states vs waiting states.
    """
    name = "flow_efficiency"
    display_name = "Flow Efficiency"
    description = "Percentage of items in active work states"
    unit = "percentage"

    def calculate(self, issues, sprint_info, metrics):
        active_phases = [Phase.IN_ANALYSIS, Phase.IN_DEV, Phase.IN_SIT, Phase.IN_TPO_REVIEW]
        waiting_phases = [Phase.BACKLOG, Phase.READY_FOR_SIT]

        in_progress = [i for i in issues if i.phase not in [Phase.DONE]]

        if not in_progress:
            return MetricResult(
                name=self.name,
                value=100,
                unit=self.unit,
                display_value="100%",
                description=self.description,
                threshold_status="good"
            )

        active_count = len([i for i in in_progress if i.phase in active_phases])
        efficiency = (active_count / len(in_progress)) * 100

        if efficiency >= 80:
            status = "good"
        elif efficiency >= 60:
            status = "warning"
        else:
            status = "critical"

        return MetricResult(
            name=self.name,
            value=round(efficiency, 1),
            unit=self.unit,
            display_value=f"{efficiency:.1f}%",
            description=self.description,
            threshold_status=status
        )


class StoryPointsPerDevMetric(BaseMetric):
    """Average story points per developer"""
    name = "sp_per_dev"
    display_name = "SP per Developer"
    description = "Average story points assigned per team member"
    unit = "SP"

    def calculate(self, issues, sprint_info, metrics):
        # Get unique assignees
        assignees = set(i.assignee for i in issues if i.assignee)
        dev_count = len(assignees) if assignees else 1

        total_points = metrics.total_story_points
        sp_per_dev = total_points / dev_count

        # No good/bad threshold - this is informational
        return MetricResult(
            name=self.name,
            value=round(sp_per_dev, 1),
            unit=self.unit,
            display_value=f"{sp_per_dev:.1f} SP",
            description=self.description,
            details={'developers': list(assignees), 'dev_count': dev_count}
        )


class HighPriorityCompletionMetric(BaseMetric):
    """Track completion of high priority items"""
    name = "high_priority_completion"
    display_name = "High Priority Completion"
    description = "Percentage of high/highest priority items completed"
    unit = "percentage"

    def calculate(self, issues, sprint_info, metrics):
        high_priority = ['Highest', 'High', 'Critical', 'Blocker']

        high_items = [i for i in issues if i.priority in high_priority]
        if not high_items:
            return MetricResult(
                name=self.name,
                value=100,
                unit=self.unit,
                display_value="N/A",
                description="No high priority items in sprint",
                threshold_status="good"
            )

        completed = len([i for i in high_items if i.phase == Phase.DONE])
        percentage = (completed / len(high_items)) * 100

        # Compare to overall sprint progress
        sprint_progress = metrics.completion_percentage_by_count

        if percentage >= sprint_progress:
            status = "good"
        elif percentage >= sprint_progress * 0.7:
            status = "warning"
        else:
            status = "critical"

        return MetricResult(
            name=self.name,
            value=round(percentage, 1),
            unit=self.unit,
            display_value=f"{percentage:.1f}%",
            description=self.description,
            threshold_status=status,
            details={
                'total_high_priority': len(high_items),
                'completed': completed,
                'remaining_keys': [i.key for i in high_items if i.phase != Phase.DONE]
            }
        )


class TestingQueueMetric(BaseMetric):
    """Track items waiting for testing"""
    name = "testing_queue"
    display_name = "Testing Queue Size"
    description = "Items waiting to be tested (Ready for SIT)"
    unit = "items"

    def calculate(self, issues, sprint_info, metrics):
        queue = [i for i in issues if i.phase == Phase.READY_FOR_SIT]
        count = len(queue)
        points = sum(i.story_points for i in queue)

        if count <= 2:
            status = "good"
        elif count <= 4:
            status = "warning"
        else:
            status = "critical"

        return MetricResult(
            name=self.name,
            value=count,
            unit=self.unit,
            display_value=f"{count} items ({points:.0f} SP)",
            description=self.description,
            threshold_status=status,
            details={
                'story_points': points,
                'items': [{'key': i.key, 'days_waiting': i.days_in_current_status} for i in queue]
            }
        )


# ============================================
# Metrics Engine
# ============================================

class MetricsEngine:
    """
    Engine for calculating and managing custom metrics.

    Usage:
    ```python
    engine = MetricsEngine(config)

    # Add built-in metrics
    engine.add_metric(BugRatioMetric())
    engine.add_metric(AverageAgeMetric())

    # Add custom metric
    engine.add_metric(MyCustomMetric())

    # Calculate all metrics
    results = engine.calculate_all(issues, sprint_info, metrics)
    ```
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.metrics: Dict[str, BaseMetric] = {}

        # Auto-register built-in metrics
        self._register_builtin_metrics()

    def _register_builtin_metrics(self):
        """Register all built-in metrics"""
        builtin = [
            BugRatioMetric(),
            UnassignedWorkMetric(),
            AverageAgeMetric(),
            FlowEfficiencyMetric(),
            StoryPointsPerDevMetric(),
            HighPriorityCompletionMetric(),
            TestingQueueMetric(),
        ]

        for metric in builtin:
            self.add_metric(metric)

    def add_metric(self, metric: BaseMetric) -> None:
        """Register a metric"""
        self.metrics[metric.name] = metric
        logger.debug(f"Registered metric: {metric.name}")

    def remove_metric(self, name: str) -> None:
        """Remove a metric"""
        if name in self.metrics:
            del self.metrics[name]

    def calculate_metric(
        self,
        name: str,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        metrics: SprintMetrics
    ) -> Optional[MetricResult]:
        """Calculate a single metric"""
        metric = self.metrics.get(name)
        if not metric:
            logger.warning(f"Metric not found: {name}")
            return None

        try:
            return metric.calculate(issues, sprint_info, metrics)
        except Exception as e:
            logger.error(f"Error calculating metric {name}: {e}")
            return None

    def calculate_all(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        metrics: SprintMetrics,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None
    ) -> List[MetricResult]:
        """
        Calculate all registered metrics.

        Args:
            issues: Sprint issues
            sprint_info: Sprint information
            metrics: Basic sprint metrics
            include: If provided, only calculate these metrics
            exclude: If provided, skip these metrics

        Returns:
            List of MetricResult objects
        """
        results = []

        for name, metric in self.metrics.items():
            # Filter
            if include and name not in include:
                continue
            if exclude and name in exclude:
                continue

            try:
                result = metric.calculate(issues, sprint_info, metrics)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error calculating metric {name}: {e}")

        return results

    def get_summary(self, results: List[MetricResult]) -> Dict[str, Any]:
        """Get a summary of metric results"""
        summary = {
            'total_metrics': len(results),
            'good': 0,
            'warning': 0,
            'critical': 0,
            'metrics': {}
        }

        for result in results:
            if result.threshold_status == 'good':
                summary['good'] += 1
            elif result.threshold_status == 'warning':
                summary['warning'] += 1
            elif result.threshold_status == 'critical':
                summary['critical'] += 1

            summary['metrics'][result.name] = {
                'display_name': result.name.replace('_', ' ').title(),
                'value': result.display_value,
                'status': result.threshold_status
            }

        return summary

    def list_metrics(self) -> List[Dict[str, str]]:
        """List all registered metrics"""
        return [
            {
                'name': m.name,
                'display_name': m.display_name,
                'description': m.description,
                'unit': m.unit
            }
            for m in self.metrics.values()
        ]

