"""
Custom Metric Builder - Template-Based Metric Generation
Allows users to create custom metrics from predefined templates

Author: Sajan Banka
Created: April 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from datetime import datetime, date, timedelta

from .models import SprintIssue, SprintInfo, SprintMetrics, Phase


class MetricType(Enum):
    """Types of metrics that can be generated"""
    COUNT = "count"
    SUM = "sum"
    AVERAGE = "average"
    LIST = "list"
    PERCENTAGE = "percentage"
    DISTRIBUTION = "distribution"


class FilterOperator(Enum):
    """Filter operators for metric conditions"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    IN_LIST = "in_list"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


@dataclass
class MetricFilter:
    """A single filter condition"""
    field: str
    operator: FilterOperator
    value: Any


@dataclass
class MetricTemplate:
    """Predefined metric template"""
    id: str
    name: str
    description: str
    category: str
    metric_type: MetricType
    default_filters: List[MetricFilter] = field(default_factory=list)
    group_by: Optional[str] = None
    value_field: Optional[str] = None  # For sum/average
    configurable_params: List[str] = field(default_factory=list)


@dataclass
class CustomMetricResult:
    """Result of a custom metric calculation"""
    template_id: str
    name: str
    description: str
    metric_type: MetricType
    value: Any  # Could be number, list, dict depending on type
    display_value: str
    details: Optional[Dict[str, Any]] = None
    generated_at: datetime = field(default_factory=datetime.now)


class MetricBuilder:
    """
    Template-based custom metric builder.
    Users select from predefined templates and optionally configure parameters.
    """

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, MetricTemplate]:
        """Load predefined metric templates"""
        templates = {}

        # ===== ASSIGNEE METRICS =====
        templates['items_by_assignee'] = MetricTemplate(
            id='items_by_assignee',
            name='Items by Assignee',
            description='Distribution of items across team members',
            category='Team',
            metric_type=MetricType.DISTRIBUTION,
            group_by='assignee'
        )

        templates['unassigned_items'] = MetricTemplate(
            id='unassigned_items',
            name='Unassigned Items',
            description='Items with no assignee',
            category='Risk',
            metric_type=MetricType.LIST,
            default_filters=[
                MetricFilter('assignee', FilterOperator.IS_NULL, None)
            ]
        )

        templates['assignee_workload'] = MetricTemplate(
            id='assignee_workload',
            name='Workload by Assignee',
            description='Story points assigned to each team member',
            category='Team',
            metric_type=MetricType.DISTRIBUTION,
            group_by='assignee',
            value_field='story_points'
        )

        # ===== STUCK METRICS =====
        templates['stuck_items'] = MetricTemplate(
            id='stuck_items',
            name='Stuck Items',
            description='Items exceeding their stuck threshold',
            category='Risk',
            metric_type=MetricType.LIST,
            default_filters=[
                MetricFilter('is_stuck', FilterOperator.EQUALS, True)
            ]
        )

        templates['items_by_days_stuck'] = MetricTemplate(
            id='items_by_days_stuck',
            name='Items by Days in Status',
            description='Items that have been in current status for N or more days',
            category='Risk',
            metric_type=MetricType.LIST,
            configurable_params=['min_days']
        )

        templates['stuck_by_assignee'] = MetricTemplate(
            id='stuck_by_assignee',
            name='Stuck Items by Assignee',
            description='Count of stuck items per team member',
            category='Risk',
            metric_type=MetricType.DISTRIBUTION,
            default_filters=[
                MetricFilter('is_stuck', FilterOperator.EQUALS, True)
            ],
            group_by='assignee'
        )

        # ===== PHASE METRICS =====
        templates['items_in_phase'] = MetricTemplate(
            id='items_in_phase',
            name='Items in Phase',
            description='Items currently in a specific phase',
            category='Progress',
            metric_type=MetricType.LIST,
            configurable_params=['phase']
        )

        templates['phase_breakdown'] = MetricTemplate(
            id='phase_breakdown',
            name='Phase Breakdown',
            description='Items and story points in each phase (combined view)',
            category='Progress',
            metric_type=MetricType.DISTRIBUTION,
            group_by='phase',
            value_field='both'  # Special flag to show both count and SP
        )

        # ===== TYPE METRICS =====
        templates['items_by_type'] = MetricTemplate(
            id='items_by_type',
            name='Items by Type',
            description='Distribution by issue type (Story, Bug, Task, etc.)',
            category='Analysis',
            metric_type=MetricType.DISTRIBUTION,
            group_by='issue_type'
        )

        templates['bugs_in_sprint'] = MetricTemplate(
            id='bugs_in_sprint',
            name='Bugs in Sprint',
            description='All bug items in the current sprint',
            category='Analysis',
            metric_type=MetricType.LIST,
            default_filters=[
                MetricFilter('issue_type', FilterOperator.EQUALS, 'Bug')
            ]
        )

        templates['bugs_vs_stories'] = MetricTemplate(
            id='bugs_vs_stories',
            name='Bugs vs Stories Ratio',
            description='Percentage of bugs compared to stories',
            category='Analysis',
            metric_type=MetricType.PERCENTAGE
        )

        # ===== PRIORITY METRICS =====
        templates['items_by_priority'] = MetricTemplate(
            id='items_by_priority',
            name='Items by Priority',
            description='Distribution by priority level',
            category='Analysis',
            metric_type=MetricType.DISTRIBUTION,
            group_by='priority'
        )

        templates['high_priority_incomplete'] = MetricTemplate(
            id='high_priority_incomplete',
            name='High Priority Items Not Done',
            description='High/Highest priority items not yet completed',
            category='Risk',
            metric_type=MetricType.LIST,
            default_filters=[
                MetricFilter('priority', FilterOperator.IN_LIST, ['High', 'Highest', 'Critical']),
                MetricFilter('phase', FilterOperator.NOT_EQUALS, Phase.DONE)
            ]
        )

        # ===== COMPLETION METRICS =====
        templates['completed_items'] = MetricTemplate(
            id='completed_items',
            name='Completed Items',
            description='All items marked as Done',
            category='Progress',
            metric_type=MetricType.LIST,
            default_filters=[
                MetricFilter('phase', FilterOperator.EQUALS, Phase.DONE)
            ]
        )

        templates['completion_by_assignee'] = MetricTemplate(
            id='completion_by_assignee',
            name='Completion by Assignee',
            description='Story points completed per team member',
            category='Team',
            metric_type=MetricType.DISTRIBUTION,
            default_filters=[
                MetricFilter('phase', FilterOperator.EQUALS, Phase.DONE)
            ],
            group_by='assignee',
            value_field='story_points'
        )

        templates['zero_point_items'] = MetricTemplate(
            id='zero_point_items',
            name='Items Without Story Points',
            description='Items that have 0 or no story points assigned',
            category='Risk',
            metric_type=MetricType.LIST,
            default_filters=[
                MetricFilter('story_points', FilterOperator.EQUALS, 0)
            ]
        )

        # ===== LABEL METRICS =====
        templates['items_with_label'] = MetricTemplate(
            id='items_with_label',
            name='Items with Label',
            description='Items containing a specific label',
            category='Analysis',
            metric_type=MetricType.LIST,
            configurable_params=['label']
        )

        # ===== TIME METRICS =====
        templates['recently_updated'] = MetricTemplate(
            id='recently_updated',
            name='Recently Updated Items',
            description='Items updated in the last N days',
            category='Activity',
            metric_type=MetricType.LIST,
            configurable_params=['days']
        )

        templates['stale_items'] = MetricTemplate(
            id='stale_items',
            name='Stale Items',
            description='Items not updated in the last N days',
            category='Risk',
            metric_type=MetricType.LIST,
            configurable_params=['days']
        )

        return templates

    def get_templates(self, category: Optional[str] = None) -> List[MetricTemplate]:
        """Get all templates, optionally filtered by category"""
        templates = list(self.templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return templates

    def get_categories(self) -> List[str]:
        """Get all unique categories"""
        categories = set(t.category for t in self.templates.values())
        return sorted(list(categories))

    def get_template(self, template_id: str) -> Optional[MetricTemplate]:
        """Get a specific template by ID"""
        return self.templates.get(template_id)

    def build_metric(
        self,
        template_id: str,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[CustomMetricResult]:
        """
        Build and calculate a metric from a template.

        Args:
            template_id: The template to use
            issues: List of sprint issues to analyze
            sprint_info: Current sprint information
            params: Optional parameters for configurable templates

        Returns:
            CustomMetricResult or None if template not found
        """
        template = self.get_template(template_id)
        if not template:
            return None

        params = params or {}
        # Include template_id in params for filter logic (e.g., stale vs recently_updated)
        params['_template_id'] = template_id

        # Apply filters
        filtered_issues = self._apply_filters(issues, template.default_filters, params)

        # Calculate based on metric type
        if template.metric_type == MetricType.LIST:
            return self._build_list_metric(template, filtered_issues)
        elif template.metric_type == MetricType.COUNT:
            return self._build_count_metric(template, filtered_issues)
        elif template.metric_type == MetricType.SUM:
            return self._build_sum_metric(template, filtered_issues)
        elif template.metric_type == MetricType.AVERAGE:
            return self._build_average_metric(template, filtered_issues)
        elif template.metric_type == MetricType.DISTRIBUTION:
            return self._build_distribution_metric(template, filtered_issues)
        elif template.metric_type == MetricType.PERCENTAGE:
            return self._build_percentage_metric(template, issues, filtered_issues)

        return None

    def _apply_filters(
        self,
        issues: List[SprintIssue],
        filters: List[MetricFilter],
        params: Dict[str, Any]
    ) -> List[SprintIssue]:
        """Apply filters to issues list"""
        result = issues

        for f in filters:
            result = [i for i in result if self._matches_filter(i, f)]

        # Apply parameter-based filters
        if 'min_days' in params and params['min_days']:
            try:
                min_days = int(params['min_days'])
                result = [i for i in result if i.days_in_current_status >= min_days]
            except (ValueError, TypeError):
                pass  # Invalid min_days, skip filter

        if 'phase' in params and params['phase']:
            phase_value = params['phase']
            if isinstance(phase_value, str):
                phase_value = Phase(phase_value) if phase_value in [p.value for p in Phase] else None
            if phase_value:
                result = [i for i in result if i.phase == phase_value]

        if 'label' in params and params['label']:
            label = str(params['label']).lower()
            result = [i for i in result if any(label in l.lower() for l in (i.labels or []))]

        if 'days' in params and params['days']:
            try:
                days = int(params['days'])
                cutoff = datetime.now() - timedelta(days=days)
                if 'stale' in params.get('_template_id', ''):
                    result = [i for i in result if i.updated_date and i.updated_date < cutoff]
                else:
                    result = [i for i in result if i.updated_date and i.updated_date >= cutoff]
            except (ValueError, TypeError):
                pass  # Invalid days, skip filter

        return result

    def _matches_filter(self, issue: SprintIssue, f: MetricFilter) -> bool:
        """Check if an issue matches a filter"""
        value = getattr(issue, f.field, None)

        if f.operator == FilterOperator.EQUALS:
            return value == f.value
        elif f.operator == FilterOperator.NOT_EQUALS:
            return value != f.value
        elif f.operator == FilterOperator.GREATER_THAN:
            return value is not None and value > f.value
        elif f.operator == FilterOperator.LESS_THAN:
            return value is not None and value < f.value
        elif f.operator == FilterOperator.CONTAINS:
            return f.value in str(value) if value else False
        elif f.operator == FilterOperator.IN_LIST:
            return value in f.value if f.value else False
        elif f.operator == FilterOperator.IS_NULL:
            return value is None
        elif f.operator == FilterOperator.IS_NOT_NULL:
            return value is not None

        return True

    def _build_list_metric(
        self,
        template: MetricTemplate,
        issues: List[SprintIssue]
    ) -> CustomMetricResult:
        """Build a list-type metric"""
        items = [
            {
                'key': i.key,
                'summary': i.summary,
                'assignee': i.assignee or 'Unassigned',
                'status': i.status,
                'story_points': i.story_points,
                'days_in_status': i.days_in_current_status
            }
            for i in issues
        ]

        total_points = sum(i.story_points for i in issues)

        return CustomMetricResult(
            template_id=template.id,
            name=template.name,
            description=template.description,
            metric_type=template.metric_type,
            value=items,
            display_value=f"{len(items)} items ({total_points} SP)",
            details={
                'count': len(items),
                'total_story_points': total_points,
                'items': items
            }
        )

    def _build_count_metric(
        self,
        template: MetricTemplate,
        issues: List[SprintIssue]
    ) -> CustomMetricResult:
        """Build a count-type metric"""
        count = len(issues)

        return CustomMetricResult(
            template_id=template.id,
            name=template.name,
            description=template.description,
            metric_type=template.metric_type,
            value=count,
            display_value=str(count)
        )

    def _build_sum_metric(
        self,
        template: MetricTemplate,
        issues: List[SprintIssue]
    ) -> CustomMetricResult:
        """Build a sum-type metric"""
        field = template.value_field or 'story_points'
        total = sum(getattr(i, field, 0) for i in issues)

        return CustomMetricResult(
            template_id=template.id,
            name=template.name,
            description=template.description,
            metric_type=template.metric_type,
            value=total,
            display_value=f"{total:.1f}"
        )

    def _build_average_metric(
        self,
        template: MetricTemplate,
        issues: List[SprintIssue]
    ) -> CustomMetricResult:
        """Build an average-type metric"""
        field = template.value_field or 'story_points'
        values = [getattr(i, field, 0) for i in issues]
        avg = sum(values) / len(values) if values else 0

        return CustomMetricResult(
            template_id=template.id,
            name=template.name,
            description=template.description,
            metric_type=template.metric_type,
            value=avg,
            display_value=f"{avg:.1f}"
        )

    def _build_distribution_metric(
        self,
        template: MetricTemplate,
        issues: List[SprintIssue]
    ) -> CustomMetricResult:
        """Build a distribution-type metric"""
        group_by = template.group_by
        value_field = template.value_field

        distribution = {}
        for issue in issues:
            key = getattr(issue, group_by, 'Unknown')
            if key is None:
                key = 'Unassigned' if group_by == 'assignee' else 'Unknown'
            if isinstance(key, Phase):
                key = key.value

            if key not in distribution:
                distribution[key] = {'count': 0, 'story_points': 0}

            distribution[key]['count'] += 1
            # Always collect story points for all distributions
            distribution[key]['story_points'] += getattr(issue, 'story_points', 0) or 0

        # Calculate totals
        total_items = len(issues)
        total_sp = sum(d['story_points'] for d in distribution.values())

        # Sort and format based on value_field
        if value_field == 'both':
            # Combined view - sort by count, show both prominently
            sorted_dist = dict(sorted(
                distribution.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            ))
            display_value = f"{total_items} items | {total_sp:.0f} SP across {len(sorted_dist)} phases"
        elif value_field == 'story_points':
            # Sort by story points for SP-based metrics
            sorted_dist = dict(sorted(
                distribution.items(),
                key=lambda x: x[1]['story_points'],
                reverse=True
            ))
            display_value = f"{total_sp:.1f} SP across {len(sorted_dist)} groups"
        else:
            # Sort by count for count-based metrics
            sorted_dist = dict(sorted(
                distribution.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            ))
            display_value = f"{total_items} items across {len(sorted_dist)} groups"

        return CustomMetricResult(
            template_id=template.id,
            name=template.name,
            description=template.description,
            metric_type=template.metric_type,
            value=sorted_dist,
            display_value=display_value,
            details={
                'distribution': sorted_dist,
                'total_items': total_items,
                'total_story_points': total_sp,
                'value_field': value_field or 'count',  # Tell frontend what to display
                'group_by': group_by
            }
        )

    def _build_percentage_metric(
        self,
        template: MetricTemplate,
        all_issues: List[SprintIssue],
        filtered_issues: List[SprintIssue]
    ) -> CustomMetricResult:
        """Build a percentage-type metric"""
        # Special handling for bugs_vs_stories
        if template.id == 'bugs_vs_stories':
            bugs = [i for i in all_issues if i.issue_type == 'Bug']
            stories = [i for i in all_issues if i.issue_type == 'Story']

            bug_count = len(bugs)
            story_count = len(stories)
            total = bug_count + story_count

            bug_pct = (bug_count / total * 100) if total > 0 else 0

            return CustomMetricResult(
                template_id=template.id,
                name=template.name,
                description=template.description,
                metric_type=template.metric_type,
                value=bug_pct,
                display_value=f"{bug_pct:.1f}% bugs ({bug_count} bugs, {story_count} stories)",
                details={
                    'bugs': bug_count,
                    'stories': story_count,
                    'bug_percentage': bug_pct
                }
            )

        # Generic percentage
        pct = (len(filtered_issues) / len(all_issues) * 100) if all_issues else 0

        return CustomMetricResult(
            template_id=template.id,
            name=template.name,
            description=template.description,
            metric_type=template.metric_type,
            value=pct,
            display_value=f"{pct:.1f}%"
        )


# Singleton instance
_metric_builder: Optional[MetricBuilder] = None


def get_metric_builder() -> MetricBuilder:
    """Get or create the metric builder instance"""
    global _metric_builder
    if _metric_builder is None:
        _metric_builder = MetricBuilder()
    return _metric_builder





