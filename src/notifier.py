"""
Notification Service for Sprint Health Agent
Supports Slack and Microsoft Teams
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .models import SprintHealthReport, Phase, HealthStatus
from .utils import format_progress_bar, format_percentage, format_story_points

logger = logging.getLogger(__name__)


class BaseNotifier:
    """Base class for notification services"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def send(self, report: SprintHealthReport) -> bool:
        """Send notification - to be implemented by subclasses"""
        raise NotImplementedError


class SlackNotifier(BaseNotifier):
    """Slack notification service"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.slack_config = config.get('notifications', {}).get('slack', {})
        self.bot_token = self.slack_config.get('bot_token')
        self.channel = self.slack_config.get('channel', '#sprint-health')

    def send(self, report: SprintHealthReport) -> bool:
        """Send sprint health report to Slack"""
        try:
            from slack_sdk import WebClient
            from slack_sdk.errors import SlackApiError

            client = WebClient(token=self.bot_token)

            blocks = self._build_slack_blocks(report)

            response = client.chat_postMessage(
                channel=self.channel,
                blocks=blocks,
                text=f"Sprint Health Report - {report.sprint_info.name}"
            )

            logger.info(f"Slack notification sent successfully to {self.channel}")
            return True

        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False

    def _build_slack_blocks(self, report: SprintHealthReport) -> list:
        """Build Slack Block Kit message"""
        sprint = report.sprint_info
        metrics = report.metrics
        velocity = report.velocity

        # Health status emoji and color
        status_emoji = report.health_emoji
        status_text = report.health_status.value.replace('_', ' ').title()

        blocks = [
            # Header
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🏃 Sprint Health Report - {sprint.name}",
                    "emoji": True
                }
            },
            # Sprint info
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"📅 Day {sprint.days_elapsed} of {sprint.total_days} | {sprint.days_remaining} days remaining"
                    }
                ]
            },
            {"type": "divider"},

            # Progress section
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📈 Sprint Progress*\n"
                            f"Committed: *{format_story_points(metrics.total_story_points)} SP* | "
                            f"Completed: *{format_story_points(metrics.completed_story_points)} SP* | "
                            f"Remaining: *{format_story_points(metrics.remaining_story_points)} SP*\n"
                            f"`{format_progress_bar(metrics.completion_percentage_by_points)}` {format_percentage(metrics.completion_percentage_by_points)}"
                }
            },

            # Completion probability
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎯 Completion Probability: {format_percentage(velocity.completion_probability)}* {status_emoji}\n"
                            f"Status: *{status_text}* | Velocity: {velocity.daily_velocity} SP/day"
                }
            },
            {"type": "divider"},
        ]

        # Phase distribution
        phase_text = "*📊 Work Distribution by Phase*\n```\n"
        phase_text += f"{'Phase':<18} {'Count':>6} {'% Total':>8} {'Stuck':>6}\n"
        phase_text += "-" * 40 + "\n"

        for pm in report.phase_breakdown:
            if pm.issue_count > 0 or pm.phase != Phase.UNKNOWN:
                stuck_indicator = f"{pm.stuck_count} ⚠️" if pm.stuck_count > 0 else "0"
                phase_text += f"{pm.phase_display_name:<18} {pm.issue_count:>6} {pm.percentage_of_total:>7.1f}% {stuck_indicator:>6}\n"

        phase_text += "```"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": phase_text}
        })

        # Stuck items section
        if report.stuck_summary.total_stuck_count > 0:
            blocks.append({"type": "divider"})

            stuck_text = f"*🚨 Stuck Items ({report.stuck_summary.total_stuck_count} tickets need attention)*\n"

            for issue in report.stuck_summary.most_critical_items[:5]:
                stuck_text += f"• `{issue.key}` - {issue.summary[:40]}{'...' if len(issue.summary) > 40 else ''}\n"
                stuck_text += f"  _{issue.status}_ | *{issue.days_in_current_status} days* | {issue.assignee or 'Unassigned'}\n"

            if report.stuck_summary.total_stuck_count > 5:
                stuck_text += f"\n_...and {report.stuck_summary.total_stuck_count - 5} more stuck items_"

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": stuck_text}
            })

        # Recommendations
        if report.recommendations:
            blocks.append({"type": "divider"})

            rec_text = "*💡 Recommendations*\n"
            for i, rec in enumerate(report.recommendations[:5], 1):
                priority_emoji = "🔴" if rec.priority == "high" else "🟡" if rec.priority == "medium" else "🟢"
                rec_text += f"{priority_emoji} {rec.message}\n"

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": rec_text}
            })

        # Footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Generated at {report.generated_at.strftime('%Y-%m-%d %H:%M')} | Sprint Health Agent 🤖"
                }
            ]
        })

        return blocks


class TeamsNotifier(BaseNotifier):
    """Microsoft Teams notification service"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.teams_config = config.get('notifications', {}).get('teams', {})
        self.webhook_url = self.teams_config.get('webhook_url')
        self.mention_scrum_master = self.teams_config.get('mention_scrum_master', False)
        self.scrum_master_email = self.teams_config.get('scrum_master_email')

    def send(self, report: SprintHealthReport) -> bool:
        """Send sprint health report to Microsoft Teams"""
        try:
            import pymsteams

            teams_message = pymsteams.connectorcard(self.webhook_url)

            sprint = report.sprint_info
            metrics = report.metrics
            velocity = report.velocity

            # Set title and summary
            teams_message.title(f"🏃 Sprint Health Report - {sprint.name}")
            teams_message.summary(f"Sprint Health: {report.health_status.value}")

            # Set color based on health
            color_map = {
                HealthStatus.HEALTHY: "00FF00",
                HealthStatus.AT_RISK: "FFA500",
                HealthStatus.CRITICAL: "FF0000"
            }
            teams_message.color(color_map.get(report.health_status, "808080"))

            # Sprint Progress Section
            progress_section = pymsteams.cardsection()
            progress_section.title("📈 Sprint Progress")
            progress_section.addFact("Day", f"{sprint.days_elapsed} of {sprint.total_days} ({sprint.days_remaining} remaining)")
            progress_section.addFact("Committed", f"{format_story_points(metrics.total_story_points)} SP")
            progress_section.addFact("Completed", f"{format_story_points(metrics.completed_story_points)} SP ({metrics.completed_issues} items)")
            progress_section.addFact("Remaining", f"{format_story_points(metrics.remaining_story_points)} SP ({metrics.remaining_issues} items)")
            progress_section.addFact("Progress", f"{format_percentage(metrics.completion_percentage_by_points)}")
            teams_message.addSection(progress_section)

            # ML Predictions Section (if available)
            if hasattr(report, 'ml_predictions') and report.ml_predictions:
                ml = report.ml_predictions
                ml_section = pymsteams.cardsection()
                ml_section.title("🤖 ML-Powered Forecast")
                ml_section.addFact("Completion Probability", f"{ml.probability_of_completion:.0f}% {report.health_emoji}")
                ml_section.addFact("Risk Level", ml.risk_level.upper())
                ml_section.addFact("Predicted Completion", f"{ml.predicted_completion_points:.0f} SP")

                if ml.confidence_intervals:
                    ci_text = " | ".join([f"{k}%: {v:.0f}SP" for k, v in ml.confidence_intervals.items()])
                    ml_section.addFact("Confidence Intervals", ci_text)

                if ml.forecast_details.get('average_velocity'):
                    ml_section.addFact("Historical Avg Velocity", f"{ml.forecast_details['average_velocity']:.1f} SP/sprint")

                teams_message.addSection(ml_section)
            else:
                # Fallback to simple velocity section
                velocity_section = pymsteams.cardsection()
                velocity_section.title("🎯 Completion Forecast")
                velocity_section.addFact("Completion Probability", f"{format_percentage(velocity.completion_probability)} {report.health_emoji}")
                velocity_section.addFact("Daily Velocity", f"{velocity.daily_velocity} SP/day")
                teams_message.addSection(velocity_section)

            # Phase Distribution Section
            phase_section = pymsteams.cardsection()
            phase_section.title("📊 Work Distribution")
            phase_text = ""
            for pm in report.phase_breakdown:
                if pm.issue_count > 0:
                    stuck_indicator = f" ⚠️ {pm.stuck_count} stuck" if pm.stuck_count > 0 else ""
                    phase_text += f"• {pm.phase_display_name}: {pm.issue_count} items ({pm.story_points:.0f} SP){stuck_indicator}\n"
            phase_section.text(phase_text)
            teams_message.addSection(phase_section)

            # Stuck Items Section
            if report.stuck_summary.total_stuck_count > 0:
                stuck_section = pymsteams.cardsection()
                stuck_section.title(f"🚨 Stuck Items ({report.stuck_summary.total_stuck_count})")

                stuck_text = ""
                for issue in report.stuck_summary.most_critical_items[:5]:
                    stuck_text += f"• **{issue.key}** - {issue.summary[:35]}...\n"
                    stuck_text += f"  _{issue.status}_ | {issue.days_in_current_status} days | {issue.assignee or 'Unassigned'}\n"

                stuck_section.text(stuck_text)
                teams_message.addSection(stuck_section)

            # Risk Assessment Section (if available)
            if hasattr(report, 'risk_assessment') and report.risk_assessment:
                risk = report.risk_assessment
                if risk.risk_factors:
                    risk_section = pymsteams.cardsection()
                    risk_section.title(f"⚠️ Risk Assessment (Score: {risk.overall_risk_score:.0f}/100)")

                    risk_text = ""
                    for rf in risk.risk_factors[:3]:
                        risk_text += f"• **{rf['issue_key']}** (Risk: {rf['risk_score']})\n"
                        for r in rf['risks'][:2]:
                            risk_text += f"  - {r}\n"

                    risk_section.text(risk_text)
                    teams_message.addSection(risk_section)

            # Recommendations Section
            if report.recommendations:
                rec_section = pymsteams.cardsection()
                rec_section.title("💡 Recommendations")

                rec_text = ""
                for rec in report.recommendations[:5]:
                    priority_icon = "🔴" if rec.priority == "high" else "🟡" if rec.priority == "medium" else "🟢"
                    rec_text += f"{priority_icon} {rec.message}\n"

                rec_section.text(rec_text)
                teams_message.addSection(rec_section)

            # Custom Metrics Section (if available)
            if hasattr(report, 'custom_metrics') and report.custom_metrics:
                critical_metrics = [m for m in report.custom_metrics if m.threshold_status in ['warning', 'critical']]
                if critical_metrics:
                    metrics_section = pymsteams.cardsection()
                    metrics_section.title("📏 Metrics Alerts")

                    metrics_text = ""
                    for m in critical_metrics[:4]:
                        icon = "🔴" if m.threshold_status == "critical" else "🟡"
                        metrics_text += f"{icon} {m.name.replace('_', ' ').title()}: {m.display_value}\n"

                    metrics_section.text(metrics_text)
                    teams_message.addSection(metrics_section)

            # Send message
            teams_message.send()

            logger.info("Teams notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Error sending Teams notification: {e}")
            return False


class ConsoleNotifier(BaseNotifier):
    """Console/Terminal notification (for testing and CLI)"""

    def send(self, report: SprintHealthReport) -> bool:
        """Print sprint health report to console"""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich import box

        console = Console()

        sprint = report.sprint_info
        metrics = report.metrics
        velocity = report.velocity

        # Header
        header = f"🏃 SPRINT HEALTH REPORT - {sprint.name} (Day {sprint.days_elapsed} of {sprint.total_days})"
        console.print(Panel(header, style="bold blue", box=box.DOUBLE))

        # Progress
        console.print("\n[bold cyan]📈 SPRINT PROGRESS[/bold cyan]")
        console.print(f"   Committed: [bold]{format_story_points(metrics.total_story_points)} SP[/bold] ({metrics.total_issues} items) | "
                     f"Completed: [green]{format_story_points(metrics.completed_story_points)} SP[/green] ({metrics.completed_issues} items) | "
                     f"Remaining: [yellow]{format_story_points(metrics.remaining_story_points)} SP[/yellow] ({metrics.remaining_issues} items)")
        console.print(f"   Progress: {format_progress_bar(metrics.completion_percentage_by_points)} "
                     f"{format_percentage(metrics.completion_percentage_by_points)}")

        # ML Predictions Section
        if hasattr(report, 'ml_predictions') and report.ml_predictions:
            ml = report.ml_predictions
            console.print("\n[bold cyan]🤖 ML-POWERED FORECAST[/bold cyan]")

            health_color = "green" if ml.risk_level == "low" else \
                          "yellow" if ml.risk_level == "medium" else "red"

            console.print(f"   Completion Probability: [{health_color}]{ml.probability_of_completion:.1f}%[/{health_color}] {report.health_emoji}")
            console.print(f"   Risk Level: [{health_color}]{ml.risk_level.upper()}[/{health_color}]")
            console.print(f"   Predicted Completion: {ml.predicted_completion_points:.0f} SP")

            if ml.confidence_intervals:
                ci_text = " | ".join([f"{k}%: {v:.0f} SP" for k, v in ml.confidence_intervals.items()])
                console.print(f"   Confidence Intervals: {ci_text}")

            if ml.simulations_run > 0:
                console.print(f"   [dim]Based on {ml.simulations_run} Monte Carlo simulations[/dim]")
        else:
            # Fallback to simple probability
            health_color = "green" if report.health_status == HealthStatus.HEALTHY else \
                          "yellow" if report.health_status == HealthStatus.AT_RISK else "red"

            console.print(f"\n[bold cyan]🎯 COMPLETION PROBABILITY: [{health_color}]{format_percentage(velocity.completion_probability)}[/{health_color}] {report.health_emoji}[/bold cyan]")
            console.print(f"   Based on: current velocity ({velocity.daily_velocity} SP/day) vs remaining work")

        # Velocity Trend (if available)
        if hasattr(report, 'velocity_trend') and report.velocity_trend and report.velocity_trend.sprints_analyzed > 0:
            vt = report.velocity_trend
            console.print(f"\n[bold cyan]📊 VELOCITY TREND[/bold cyan]")
            trend_color = "green" if vt.velocity_trend == "improving" else \
                         "yellow" if vt.velocity_trend == "stable" else "red"
            console.print(f"   Trend: [{trend_color}]{vt.velocity_trend.upper()}[/{trend_color}] ({vt.trend_percentage:+.1f}%)")
            console.print(f"   Historical Average: {vt.average_velocity:.1f} SP/sprint (over {vt.sprints_analyzed} sprints)")

        # Phase distribution table
        console.print("\n[bold cyan]📊 WORK DISTRIBUTION BY PHASE[/bold cyan]")

        phase_table = Table(box=box.ROUNDED)
        phase_table.add_column("Phase", style="cyan")
        phase_table.add_column("Count", justify="right")
        phase_table.add_column("SP", justify="right")
        phase_table.add_column("% Total", justify="right")
        phase_table.add_column("Stuck", justify="right")

        for pm in report.phase_breakdown:
            if pm.issue_count > 0:
                stuck_str = f"[red]{pm.stuck_count} ⚠️[/red]" if pm.stuck_count > 0 else "0"
                phase_table.add_row(
                    pm.phase_display_name,
                    str(pm.issue_count),
                    f"{pm.story_points:.0f}",
                    f"{pm.percentage_of_total:.1f}%",
                    stuck_str
                )

        console.print(phase_table)

        # Stuck items
        if report.stuck_summary.total_stuck_count > 0:
            console.print(f"\n[bold red]🚨 STUCK ITEMS ({report.stuck_summary.total_stuck_count} tickets need attention)[/bold red]")

            stuck_table = Table(box=box.ROUNDED)
            stuck_table.add_column("Key", style="cyan", no_wrap=True)
            stuck_table.add_column("Summary", max_width=35)
            stuck_table.add_column("Status", style="yellow")
            stuck_table.add_column("Days", justify="right", style="red")
            stuck_table.add_column("Assignee", style="green")
            stuck_table.add_column("SP", justify="right")

            for issue in report.stuck_summary.most_critical_items[:10]:
                summary = issue.summary[:35] + "..." if len(issue.summary) > 35 else issue.summary
                stuck_table.add_row(
                    issue.key,
                    summary,
                    issue.status,
                    str(issue.days_in_current_status),
                    issue.assignee or "Unassigned",
                    str(issue.story_points) if issue.story_points else "-"
                )

            console.print(stuck_table)

        # Risk Assessment (if available)
        if hasattr(report, 'risk_assessment') and report.risk_assessment:
            risk = report.risk_assessment
            if risk.risk_factors:
                console.print(f"\n[bold yellow]⚠️ RISK ASSESSMENT (Score: {risk.overall_risk_score:.0f}/100 - {risk.risk_level.upper()})[/bold yellow]")

                for rf in risk.risk_factors[:3]:
                    console.print(f"   • [bold]{rf['issue_key']}[/bold] (Risk Score: {rf['risk_score']})")
                    for r in rf['risks'][:2]:
                        console.print(f"     - {r}")

        # Custom Metrics (if available)
        if hasattr(report, 'custom_metrics') and report.custom_metrics:
            console.print("\n[bold cyan]📏 CUSTOM METRICS[/bold cyan]")

            metrics_table = Table(box=box.ROUNDED)
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Value", justify="right")
            metrics_table.add_column("Status", justify="center")

            for m in report.custom_metrics[:6]:
                status_style = "green" if m.threshold_status == "good" else \
                              "yellow" if m.threshold_status == "warning" else \
                              "red" if m.threshold_status == "critical" else "white"
                status_icon = "✅" if m.threshold_status == "good" else \
                             "⚠️" if m.threshold_status == "warning" else \
                             "🔴" if m.threshold_status == "critical" else "ℹ️"

                metrics_table.add_row(
                    m.name.replace('_', ' ').title(),
                    m.display_value,
                    f"[{status_style}]{status_icon}[/{status_style}]"
                )

            console.print(metrics_table)

        # Recommendations
        if report.recommendations:
            console.print("\n[bold cyan]💡 RECOMMENDATIONS[/bold cyan]")
            for rec in report.recommendations[:5]:
                priority_color = "red" if rec.priority == "high" else "yellow" if rec.priority == "medium" else "green"
                console.print(f"   [{priority_color}]●[/{priority_color}] {rec.message}")

        # Burnup Chart (ASCII)
        if hasattr(report, 'chart_data') and report.chart_data:
            from .charts import ChartGenerator
            cg = ChartGenerator(self.config)
            console.print("\n" + cg.generate_ascii_burnup(report.chart_data))

        console.print(f"\n[dim]Generated at {report.generated_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
        console.print("━" * 60)

        return True


class GoogleChatNotifier(BaseNotifier):
    """Google Chat notification service via webhook"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.gchat_config = config.get('notifications', {}).get('google_chat', {})
        self.webhook_url = self.gchat_config.get('webhook_url')

    def send(self, report: SprintHealthReport) -> bool:
        """Send sprint health report to Google Chat"""
        try:
            import requests

            sprint = report.sprint_info
            metrics = report.metrics
            velocity = report.velocity

            # Build Google Chat card message
            card = {
                "cards": [{
                    "header": {
                        "title": f"🏃 Sprint Health Report",
                        "subtitle": f"{sprint.name} - Day {sprint.days_elapsed} of {sprint.total_days}"
                    },
                    "sections": [
                        {
                            "header": "📈 Sprint Progress",
                            "widgets": [{
                                "keyValue": {
                                    "topLabel": "Completion Probability",
                                    "content": f"{velocity.completion_probability:.0f}% {report.health_emoji}",
                                    "bottomLabel": f"Committed: {metrics.total_story_points:.0f} SP | Done: {metrics.completed_story_points:.0f} SP"
                                }
                            }]
                        },
                        {
                            "header": f"🚨 Stuck Items ({report.stuck_summary.total_stuck_count})",
                            "widgets": [{
                                "textParagraph": {
                                    "text": self._format_stuck_items(report)
                                }
                            }]
                        },
                        {
                            "header": "💡 Recommendations",
                            "widgets": [{
                                "textParagraph": {
                                    "text": self._format_recommendations(report)
                                }
                            }]
                        }
                    ]
                }]
            }

            response = requests.post(
                self.webhook_url,
                json=card,
                headers={'Content-Type': 'application/json'},
                verify=self.config.get('jira', {}).get('verify_ssl', True)
            )

            if response.status_code == 200:
                logger.info("Google Chat notification sent successfully")
                return True
            else:
                logger.error(f"Google Chat error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending Google Chat notification: {e}")
            return False

    def _format_stuck_items(self, report: SprintHealthReport) -> str:
        """Format stuck items for Google Chat"""
        if report.stuck_summary.total_stuck_count == 0:
            return "✅ No stuck items!"

        lines = []
        for issue in report.stuck_summary.most_critical_items[:5]:
            lines.append(f"• <b>{issue.key}</b> - {issue.summary[:30]}... ({issue.days_in_current_status} days)")

        return "\n".join(lines)

    def _format_recommendations(self, report: SprintHealthReport) -> str:
        """Format recommendations for Google Chat"""
        if not report.recommendations:
            return "No recommendations at this time."

        lines = []
        for rec in report.recommendations[:3]:
            icon = "🔴" if rec.priority == "high" else "🟡"
            lines.append(f"{icon} {rec.message}")

        return "\n".join(lines)


class NotificationService:
    """Main notification service that routes to appropriate notifier"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.notification_config = config.get('notifications', {})
        self.enabled = self.notification_config.get('enabled', True)
        self.platform = self.notification_config.get('platform', 'console')

        # Initialize appropriate notifier
        self.notifiers = {
            'slack': SlackNotifier,
            'teams': TeamsNotifier,
            'google_chat': GoogleChatNotifier,
            'console': ConsoleNotifier
        }

    def send(self, report: SprintHealthReport, platform: Optional[str] = None) -> bool:
        """
        Send notification to configured platform

        Args:
            report: SprintHealthReport to send
            platform: Override platform (slack, teams, google_chat, console)

        Returns:
            True if notification sent successfully
        """
        if not self.enabled and platform != 'console':
            logger.info("Notifications disabled in config")
            return False

        target_platform = platform or self.platform

        notifier_class = self.notifiers.get(target_platform)
        if not notifier_class:
            logger.error(f"Unknown notification platform: {target_platform}")
            return False

        notifier = notifier_class(self.config)
        return notifier.send(report)

    def send_to_console(self, report: SprintHealthReport) -> bool:
        """Always send to console"""
        return ConsoleNotifier(self.config).send(report)

