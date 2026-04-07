"""
Jira API Client for Sprint Health Agent
Handles all communication with Jira REST API
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from jira import JIRA
from jira.exceptions import JIRAError

from .models import SprintIssue, SprintInfo, Phase
from .utils import parse_date, parse_datetime

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for interacting with Jira API"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Jira client with configuration

        Args:
            config: Dictionary containing jira configuration
                   (url, email, api_token, project_key, board_id)
        """
        self.config = config
        self.jira_config = config['jira']
        self.phases_config = config.get('phases', {})
        self.stuck_thresholds = config.get('stuck_thresholds_days', {})

        # Story point field - check both root level and inside jira config
        self.story_point_field = (
            config.get('story_point_field') or
            self.jira_config.get('story_point_field') or
            'customfield_10016'
        )

        # Initialize Jira connection
        # Supports both API token and username/password authentication
        auth_method = self.jira_config.get('auth_method', 'token')  # 'token' or 'basic'

        # SSL verification - disable for corporate self-signed certificates
        verify_ssl = self.jira_config.get('verify_ssl', True)

        # Set options
        options = {
            'server': self.jira_config['url'],
            'verify': verify_ssl
        }

        if auth_method == 'basic':
            # Username/Password authentication
            self.jira = JIRA(
                options=options,
                basic_auth=(
                    self.jira_config['username'],
                    self.jira_config['password']
                )
            )
        else:
            # API Token authentication (default)
            self.jira = JIRA(
                options=options,
                basic_auth=(
                    self.jira_config['email'],
                    self.jira_config['api_token']
                )
            )

        # Build status to phase mapping
        self._build_status_mapping()

    def _build_status_mapping(self) -> None:
        """Build a mapping from status names to phases"""
        self.status_to_phase: Dict[str, Phase] = {}

        phase_mapping = {
            'backlog': Phase.BACKLOG,
            'in_analysis': Phase.IN_ANALYSIS,
            'in_dev': Phase.IN_DEV,
            'ready_for_sit': Phase.READY_FOR_SIT,
            'in_sit': Phase.IN_SIT,
            'in_tpo_review': Phase.IN_TPO_REVIEW,
            'done': Phase.DONE
        }

        for phase_key, statuses in self.phases_config.items():
            phase = phase_mapping.get(phase_key, Phase.UNKNOWN)
            for status in statuses:
                self.status_to_phase[status.lower()] = phase

    def _get_phase_for_status(self, status: str) -> Phase:
        """Get the phase for a given status"""
        return self.status_to_phase.get(status.lower(), Phase.UNKNOWN)

    def _get_stuck_threshold(self, phase: Phase) -> int:
        """Get the stuck threshold in days for a phase"""
        phase_key = phase.value
        return self.stuck_thresholds.get(phase_key, 3)  # Default 3 days

    def get_active_sprint(self, board_id: Optional[int] = None) -> Optional[SprintInfo]:
        """
        Get the currently active sprint for the board

        Args:
            board_id: Jira board ID (uses config if not provided)

        Returns:
            SprintInfo object or None if no active sprint
        """
        board_id = board_id or self.jira_config['board_id']

        try:
            # Check if specific sprint_id is configured
            sprint_id = self.jira_config.get('sprint_id')

            if sprint_id:
                # Use specific sprint from config
                sprint = self.jira.sprint(sprint_id)

                return SprintInfo(
                    id=sprint.id,
                    name=sprint.name,
                    state=sprint.state,
                    start_date=parse_date(getattr(sprint, 'startDate', None)),
                    end_date=parse_date(getattr(sprint, 'endDate', None)),
                    goal=getattr(sprint, 'goal', None)
                )

            # Otherwise get active sprint from board
            sprints = self.jira.sprints(board_id, state='active')

            if not sprints:
                logger.warning(f"No active sprint found for board {board_id}")
                return None

            # Usually there's only one active sprint, take the first
            sprint = sprints[0]

            return SprintInfo(
                id=sprint.id,
                name=sprint.name,
                state=sprint.state,
                start_date=parse_date(getattr(sprint, 'startDate', None)),
                end_date=parse_date(getattr(sprint, 'endDate', None)),
                goal=getattr(sprint, 'goal', None)
            )

        except JIRAError as e:
            logger.error(f"Error fetching active sprint: {e}")
            raise

    def get_sprint_issues(self, sprint_id: int) -> List[SprintIssue]:
        """
        Get all issues in a sprint

        Args:
            sprint_id: The sprint ID

        Returns:
            List of SprintIssue objects
        """
        issues = []
        start_at = 0
        max_results = 100

        try:
            while True:
                # JQL to get all issues in sprint
                jql = f"Sprint = {sprint_id} ORDER BY status, priority DESC"

                results = self.jira.search_issues(
                    jql,
                    startAt=start_at,
                    maxResults=max_results,
                    expand='changelog'
                )

                if not results:
                    break

                for issue in results:
                    sprint_issue = self._convert_to_sprint_issue(issue)
                    issues.append(sprint_issue)

                if len(results) < max_results:
                    break

                start_at += max_results

            logger.info(f"Fetched {len(issues)} issues from sprint {sprint_id}")
            return issues

        except JIRAError as e:
            logger.error(f"Error fetching sprint issues: {e}")
            raise

    def _convert_to_sprint_issue(self, issue) -> SprintIssue:
        """Convert Jira issue to SprintIssue model"""
        fields = issue.fields

        # Get basic fields
        status = fields.status.name
        phase = self._get_phase_for_status(status)

        # Get assignee info
        assignee = None
        assignee_email = None
        if fields.assignee:
            assignee = fields.assignee.displayName
            assignee_email = getattr(fields.assignee, 'emailAddress', None)

        # Get story points - try multiple common field names (like complexityEstimator)
        story_points = None

        # List of common story point field names across different Jira instances
        sp_field_candidates = [
            self.story_point_field,  # User configured field first
            'customfield_10002',
            'customfield_10004',
            'customfield_10016',
            'customfield_10005',
            'customfield_10006',
            'customfield_10014',
            'customfield_10024',
            'customfield_10026',
            'customfield_10028',
            'story_points',
        ]

        for field_name in sp_field_candidates:
            try:
                value = getattr(fields, field_name, None)
                if value is not None:
                    # Handle if it's an object with 'value' attribute
                    if hasattr(value, 'value'):
                        value = value.value
                    # Try to convert to float
                    story_points = float(value)
                    if story_points > 0:
                        break  # Found a valid value
            except (ValueError, TypeError, AttributeError):
                continue

        # Default to 0 if nothing found
        if story_points is None:
            story_points = 0.0

        # Get dates
        created = parse_datetime(fields.created)
        updated = parse_datetime(fields.updated)

        # Calculate days in current status from changelog
        status_change_date = self._get_last_status_change(issue)
        days_in_status = self._calculate_days_in_status(status_change_date)

        # Determine if stuck
        stuck_threshold = self._get_stuck_threshold(phase)
        is_stuck = (
            phase not in [Phase.BACKLOG, Phase.DONE, Phase.UNKNOWN] and
            days_in_status >= stuck_threshold
        )

        # Get labels
        labels = fields.labels if hasattr(fields, 'labels') else []

        return SprintIssue(
            key=issue.key,
            summary=fields.summary,
            status=status,
            phase=phase,
            assignee=assignee,
            assignee_email=assignee_email,
            story_points=float(story_points) if story_points else 0.0,
            issue_type=fields.issuetype.name,
            priority=fields.priority.name if fields.priority else "None",
            created_date=created,
            updated_date=updated,
            status_change_date=status_change_date,
            days_in_current_status=days_in_status,
            is_stuck=is_stuck,
            stuck_threshold=stuck_threshold,
            labels=labels
        )

    def _get_last_status_change(self, issue) -> Optional[datetime]:
        """Get the datetime of the last status change from changelog"""
        if not hasattr(issue, 'changelog'):
            return None

        status_changes = []

        for history in issue.changelog.histories:
            for item in history.items:
                if item.field == 'status':
                    change_date = parse_datetime(history.created)
                    if change_date:
                        status_changes.append(change_date)

        if status_changes:
            return max(status_changes)

        # If no status changes, use created date
        return parse_datetime(issue.fields.created)

    def _calculate_days_in_status(self, status_change_date: Optional[datetime]) -> int:
        """Calculate the number of days an issue has been in current status"""
        if not status_change_date:
            return 0

        now = datetime.now()
        delta = now - status_change_date
        return delta.days

    def get_board_configuration(self, board_id: Optional[int] = None) -> Dict[str, Any]:
        """Get board configuration including columns"""
        board_id = board_id or self.jira_config['board_id']

        try:
            config = self.jira.get_board_configuration(board_id)
            return config
        except JIRAError as e:
            logger.error(f"Error fetching board configuration: {e}")
            return {}

    def get_velocity(self, board_id: Optional[int] = None, num_sprints: int = 5) -> List[Dict[str, Any]]:
        """
        Get velocity data for recent sprints

        Args:
            board_id: Board ID
            num_sprints: Number of past sprints to analyze

        Returns:
            List of sprint velocity data
        """
        board_id = board_id or self.jira_config['board_id']
        velocity_data = []

        try:
            # Get closed sprints
            sprints = self.jira.sprints(board_id, state='closed')

            # Sort by end date and take most recent
            sprints = sorted(
                sprints,
                key=lambda s: getattr(s, 'endDate', ''),
                reverse=True
            )[:num_sprints]

            for sprint in sprints:
                # Get completed story points for this sprint
                jql = f"Sprint = {sprint.id} AND status = Done"
                issues = self.jira.search_issues(jql, maxResults=500)

                completed_points = sum(
                    float(getattr(i.fields, self.story_point_field, 0) or 0)
                    for i in issues
                )

                velocity_data.append({
                    'sprint_id': sprint.id,
                    'sprint_name': sprint.name,
                    'completed_points': completed_points,
                    'start_date': parse_date(getattr(sprint, 'startDate', None)),
                    'end_date': parse_date(getattr(sprint, 'endDate', None))
                })

            return velocity_data

        except JIRAError as e:
            logger.error(f"Error fetching velocity data: {e}")
            return []

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test the Jira connection

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            myself = self.jira.myself()
            return True, f"Connected as {myself['displayName']} ({myself['emailAddress']})"
        except JIRAError as e:
            return False, f"Connection failed: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

