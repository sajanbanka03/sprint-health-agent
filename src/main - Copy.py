"""
Sprint Health Agent - Main Entry Point
CLI interface for running sprint health analysis
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from .utils import load_config, save_sprint_history, PROJECT_ROOT
from .jira_client import JiraClient
from .analyzer import SprintAnalyzer
from .notifier import NotificationService
from .charts import explain_burndown_vs_burnup
from .custom_metrics import MetricsEngine
from .exporter import export_html_report, export_multi_team_html_report

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)
console = Console()


@click.group()
@click.option('--config', '-c', default=None, help='Path to config file')
@click.pass_context
def cli(ctx, config):
    """🏃 Sprint Health Agent - Automated Sprint Intelligence"""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


@cli.command()
@click.option('--notify/--no-notify', default=False, help='Send notification to configured channel')
@click.option('--platform', '-p', type=click.Choice(['slack', 'teams', 'console']), default=None,
              help='Notification platform (overrides config)')
@click.option('--save-history/--no-save-history', default=True, help='Save sprint data to history')
@click.pass_context
def analyze(ctx, notify, platform, save_history):
    """Analyze current sprint health and generate report"""
    try:
        config = load_config(ctx.obj.get('config_path'))

        console.print("\n[bold blue]🔍 Analyzing Sprint Health...[/bold blue]\n")

        # Initialize components
        jira = JiraClient(config)
        analyzer = SprintAnalyzer(config, jira)
        notifier = NotificationService(config)

        # Test Jira connection
        success, message = jira.test_connection()
        if not success:
            console.print(f"[red]❌ Jira connection failed: {message}[/red]")
            sys.exit(1)

        console.print(f"[green]✓ {message}[/green]")

        # Analyze sprint
        report = analyzer.analyze_sprint()

        # Save history
        if save_history:
            history_data = {
                'date': datetime.now().isoformat(),
                'sprint_id': report.sprint_info.id,
                'sprint_name': report.sprint_info.name,
                'completion_probability': report.velocity.completion_probability,
                'completed_points': report.metrics.completed_story_points,
                'total_points': report.metrics.total_story_points,
                'stuck_count': report.stuck_summary.total_stuck_count
            }
            save_sprint_history(report.sprint_info.id, history_data)
            console.print("[dim]✓ Sprint history saved[/dim]")

        # Always show console output
        notifier.send_to_console(report)

        # Send notification if requested
        if notify:
            target_platform = platform or config.get('notifications', {}).get('platform', 'slack')
            console.print(f"\n[bold]📤 Sending notification to {target_platform}...[/bold]")

            if notifier.send(report, platform):
                console.print(f"[green]✓ Notification sent to {target_platform}[/green]")
            else:
                console.print(f"[red]❌ Failed to send notification[/red]")

    except FileNotFoundError as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.exception("Analysis failed")
        sys.exit(1)


@cli.command()
@click.pass_context
def test_connection(ctx):
    """Test Jira connection"""
    try:
        config = load_config(ctx.obj.get('config_path'))
        jira = JiraClient(config)

        console.print("\n[bold]Testing Jira connection...[/bold]")
        success, message = jira.test_connection()

        if success:
            console.print(f"[green]✓ {message}[/green]")

            # Also test getting active sprint
            sprint = jira.get_active_sprint()
            if sprint:
                console.print(f"[green]✓ Active sprint found: {sprint.name}[/green]")
                console.print(f"  Days elapsed: {sprint.days_elapsed}/{sprint.total_days}")
            else:
                console.print("[yellow]⚠ No active sprint found[/yellow]")
        else:
            console.print(f"[red]❌ {message}[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--time', '-t', default='09:00', help='Time to run daily (HH:MM format)')
@click.pass_context
def schedule(ctx, time):
    """Start the scheduler for daily reports"""
    import schedule
    import time as time_module

    try:
        config = load_config(ctx.obj.get('config_path'))

        console.print(f"\n[bold blue]🕐 Starting scheduler - Daily reports at {time}[/bold blue]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        def run_analysis():
            console.print(f"\n[bold]⏰ Running scheduled analysis at {datetime.now().strftime('%H:%M')}[/bold]")
            try:
                jira = JiraClient(config)
                analyzer = SprintAnalyzer(config, jira)
                notifier = NotificationService(config)

                report = analyzer.analyze_sprint()

                # Save history
                history_data = {
                    'date': datetime.now().isoformat(),
                    'sprint_id': report.sprint_info.id,
                    'sprint_name': report.sprint_info.name,
                    'completion_probability': report.velocity.completion_probability,
                    'completed_points': report.metrics.completed_story_points,
                    'total_points': report.metrics.total_story_points,
                    'stuck_count': report.stuck_summary.total_stuck_count
                }
                save_sprint_history(report.sprint_info.id, history_data)

                # Send notification
                notifier.send(report)
                console.print("[green]✓ Analysis complete and notification sent[/green]")

            except Exception as e:
                console.print(f"[red]❌ Scheduled analysis failed: {e}[/red]")
                logger.exception("Scheduled analysis failed")

        # Schedule daily run
        schedule.every().day.at(time).do(run_analysis)

        # Also run immediately
        run_analysis()

        # Keep running
        while True:
            schedule.run_pending()
            time_module.sleep(60)

    except KeyboardInterrupt:
        console.print("\n[yellow]Scheduler stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def show_config(ctx):
    """Show current configuration (masked secrets)"""
    try:
        config = load_config(ctx.obj.get('config_path'))

        console.print("\n[bold]Current Configuration:[/bold]\n")

        # Jira config (mask sensitive data)
        jira = config.get('jira', {})
        console.print("[cyan]Jira Settings:[/cyan]")
        console.print(f"  URL: {jira.get('url', 'not set')}")
        console.print(f"  Auth Method: {jira.get('auth_method', 'token')}")
        console.print(f"  Username: {jira.get('username', 'not set')}")
        console.print(f"  Password: {'*' * 10 if jira.get('password') else 'not set'}")
        console.print(f"  Email: {jira.get('email', 'not set')}")
        console.print(f"  API Token: {'*' * 20 if jira.get('api_token') else 'not set'}")
        console.print(f"  Project Key: {jira.get('project_key', 'not set')}")
        console.print(f"  Board ID: {jira.get('board_id', 'not set')}")
        console.print(f"  Sprint ID: {jira.get('sprint_id', 'not set')}")
        console.print(f"  [bold]Story Point Field: {jira.get('story_point_field', 'NOT SET - using auto-detect')}[/bold]")
        console.print(f"  Verify SSL: {jira.get('verify_ssl', True)}")

        # Notification config
        notif = config.get('notifications', {})
        console.print("\n[cyan]Notification Settings:[/cyan]")
        console.print(f"  Enabled: {notif.get('enabled', False)}")
        console.print(f"  Platform: {notif.get('platform', 'not set')}")

        # ML Predictions
        ml = config.get('ml_predictions', {})
        console.print("\n[cyan]ML Predictions:[/cyan]")
        console.print(f"  Enabled: {ml.get('enabled', False)}")
        console.print(f"  Monte Carlo Simulations: {ml.get('monte_carlo_simulations', 1000)}")

        # Thresholds
        thresholds = config.get('thresholds', {})
        console.print("\n[cyan]Thresholds:[/cyan]")
        console.print(f"  Warning probability: {thresholds.get('completion_probability_warning', 70)}%")
        console.print(f"  Critical probability: {thresholds.get('completion_probability_critical', 50)}%")

        # Stuck thresholds
        stuck = config.get('stuck_thresholds_days', {})
        console.print("\n[cyan]Stuck Thresholds (days):[/cyan]")
        for phase, days in stuck.items():
            console.print(f"  {phase}: {days} days")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def explain_charts(ctx):
    """Explain the difference between Burndown and Burnup charts"""
    console.print(explain_burndown_vs_burnup())


@cli.command()
@click.option('--output', '-o', default=None, help='Output file path')
@click.pass_context
def export_html(ctx, output):
    """Export sprint health report to HTML file"""
    try:
        config = load_config(ctx.obj.get('config_path'))

        console.print("\n[bold blue]📄 Generating HTML Report...[/bold blue]\n")

        jira = JiraClient(config)
        analyzer = SprintAnalyzer(config, jira)
        report = analyzer.analyze_sprint()

        output_path = export_html_report(report, output)

        console.print(f"[green]✓ Report saved to: {output_path}[/green]")
        console.print(f"\n[bold]Open in browser:[/bold] file:///{output_path.replace(chr(92), '/')}")

        # Try to open in default browser
        import webbrowser
        try:
            webbrowser.open(f'file:///{output_path}')
            console.print("[dim]Opening in browser...[/dim]")
        except:
            pass

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def list_metrics(ctx):
    """List all available custom metrics"""
    try:
        config = load_config(ctx.obj.get('config_path'))
        engine = MetricsEngine(config)

        console.print("\n[bold]Available Custom Metrics:[/bold]\n")

        from rich.table import Table
        from rich import box

        table = Table(box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Display Name", style="white")
        table.add_column("Description")
        table.add_column("Unit", style="yellow")

        for m in engine.list_metrics():
            table.add_row(
                m['name'],
                m['display_name'],
                m['description'],
                m['unit']
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(engine.list_metrics())} metrics available[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--project', '-p', default=None, help='Filter by project key (e.g., TREX)')
@click.pass_context
def list_boards(ctx, project):
    """List all available Jira boards"""
    try:
        config = load_config(ctx.obj.get('config_path'))
        jira = JiraClient(config)

        console.print("\n[bold]Fetching available boards...[/bold]\n")

        from rich.table import Table
        from rich import box

        # Get all boards
        start = 0
        boards = []
        while True:
            result = jira.jira.boards(startAt=start, maxResults=50, projectKeyOrID=project)
            if not result:
                break
            boards.extend(result)
            if len(result) < 50:
                break
            start += 50

        table = Table(box=box.ROUNDED, title="Available Boards")
        table.add_column("Board ID", style="cyan", justify="right")
        table.add_column("Name", style="white")
        table.add_column("Type", style="yellow")

        for board in boards[:30]:  # Limit to 30
            table.add_row(
                str(board.id),
                board.name,
                getattr(board, 'type', 'unknown')
            )

        console.print(table)

        if len(boards) > 30:
            console.print(f"\n[dim]Showing 30 of {len(boards)} boards. Use --project to filter.[/dim]")

        console.print("\n[bold]Next:[/bold] Use the Board ID in your config.json")
        console.print("Or run: [cyan]python -m src.main list-sprints --board <BOARD_ID>[/cyan]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--board', '-b', type=int, required=True, help='Board ID')
@click.option('--state', '-s', default='active', type=click.Choice(['active', 'future', 'closed', 'all']), help='Sprint state')
@click.pass_context
def list_sprints(ctx, board, state):
    """List sprints for a specific board"""
    try:
        config = load_config(ctx.obj.get('config_path'))
        jira = JiraClient(config)

        console.print(f"\n[bold]Fetching sprints for board {board}...[/bold]\n")

        from rich.table import Table
        from rich import box

        # Get sprints
        if state == 'all':
            sprints = jira.jira.sprints(board)
        else:
            sprints = jira.jira.sprints(board, state=state)

        table = Table(box=box.ROUNDED, title=f"Sprints (state: {state})")
        table.add_column("Sprint ID", style="cyan", justify="right")
        table.add_column("Name", style="white")
        table.add_column("State", style="yellow")
        table.add_column("Start Date", style="green")
        table.add_column("End Date", style="red")

        for sprint in sprints[:20]:
            table.add_row(
                str(sprint.id),
                sprint.name,
                sprint.state,
                getattr(sprint, 'startDate', '-')[:10] if hasattr(sprint, 'startDate') and sprint.startDate else '-',
                getattr(sprint, 'endDate', '-')[:10] if hasattr(sprint, 'endDate') and sprint.endDate else '-'
            )

        console.print(table)

        if sprints:
            console.print(f"\n[bold]To use a specific sprint:[/bold]")
            console.print("Add to config.json: [cyan]\"sprint_id\": <SPRINT_ID>[/cyan]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def find_fields(ctx):
    """Find Story Point and other custom field IDs in your Jira"""
    try:
        config = load_config(ctx.obj.get('config_path'))
        jira = JiraClient(config)

        console.print("\n[bold]Searching for Story Point field...[/bold]\n")

        from rich.table import Table
        from rich import box

        # Get all fields
        fields = jira.jira.fields()

        # Find story point related fields
        sp_keywords = ['story point', 'storypoint', 'story_point', 'estimation', 'estimate', 'points']

        table = Table(box=box.ROUNDED, title="Possible Story Point Fields")
        table.add_column("Field ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Type", style="yellow")

        found_fields = []
        for field in fields:
            field_name = field['name'].lower()
            if any(kw in field_name for kw in sp_keywords):
                found_fields.append(field)
                table.add_row(
                    field['id'],
                    field['name'],
                    field.get('schema', {}).get('type', 'unknown') if 'schema' in field else 'unknown'
                )

        if found_fields:
            console.print(table)
            console.print("\n[bold]Update your config.json with:[/bold]")
            console.print(f'[cyan]"story_point_field": "{found_fields[0]["id"]}"[/cyan]')
        else:
            console.print("[yellow]No obvious story point field found.[/yellow]")
            console.print("\n[bold]Let's check a sample issue to find the field...[/bold]")

        # Get a sample issue to show all fields with values
        sprint_id = config['jira'].get('sprint_id')
        if sprint_id:
            console.print(f"\n[bold]Checking fields on issues in sprint {sprint_id}...[/bold]\n")

            issues = jira.jira.search_issues(f"Sprint = {sprint_id}", maxResults=1)
            if issues:
                issue = issues[0]

                # Find fields with numeric values (likely story points)
                numeric_table = Table(box=box.ROUNDED, title=f"Numeric fields on {issue.key}")
                numeric_table.add_column("Field ID", style="cyan")
                numeric_table.add_column("Value", style="green")

                for field in fields:
                    field_id = field['id']
                    if field_id.startswith('customfield_'):
                        value = getattr(issue.fields, field_id, None)
                        if value is not None and (isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.','').isdigit())):
                            numeric_table.add_row(field_id, str(value))

                console.print(numeric_table)
                console.print("\n[bold]Look for the field with story point values (e.g., 1, 2, 3, 5, 8)[/bold]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--issue', '-i', default=None, help='Specific issue key to check (e.g., RESMYB-4256)')
@click.pass_context
def debug_fields(ctx, issue):
    """Debug: Show all field values for an issue to find story points"""
    try:
        config = load_config(ctx.obj.get('config_path'))
        jira = JiraClient(config)

        story_point_field = config.get('story_point_field', config.get('jira', {}).get('story_point_field', 'customfield_10016'))
        console.print(f"\n[bold]Current story_point_field in config: [cyan]{story_point_field}[/cyan][/bold]\n")

        # Get an issue
        if issue:
            issues = jira.jira.search_issues(f"key = {issue}", maxResults=1)
        else:
            sprint_id = config['jira'].get('sprint_id')
            issues = jira.jira.search_issues(f"Sprint = {sprint_id}", maxResults=3)

        if not issues:
            console.print("[red]No issues found[/red]")
            return

        from rich.table import Table
        from rich import box

        for iss in issues:
            console.print(f"\n[bold cyan]Issue: {iss.key} - {iss.fields.summary[:50]}...[/bold cyan]")

            # Check configured story point field
            sp_value = getattr(iss.fields, story_point_field, 'NOT_FOUND')
            console.print(f"  Configured field ({story_point_field}): [yellow]{sp_value}[/yellow] (type: {type(sp_value).__name__})")

            # Check common story point field names
            common_fields = ['customfield_10016', 'customfield_10002', 'customfield_10004',
                           'customfield_10005', 'customfield_10006', 'customfield_10014',
                           'customfield_10024', 'customfield_10026', 'customfield_10028']

            console.print("\n  [bold]Checking common SP field IDs:[/bold]")
            for cf in common_fields:
                val = getattr(iss.fields, cf, None)
                if val is not None:
                    console.print(f"    {cf}: [green]{val}[/green] (type: {type(val).__name__})")

            # Show all customfields with numeric-ish values
            console.print("\n  [bold]All custom fields with values:[/bold]")
            all_fields = jira.jira.fields()
            field_map = {f['id']: f['name'] for f in all_fields}

            for attr in dir(iss.fields):
                if attr.startswith('customfield_'):
                    val = getattr(iss.fields, attr, None)
                    if val is not None and val != [] and val != '':
                        field_name = field_map.get(attr, 'Unknown')
                        # Show value (truncate if too long)
                        val_str = str(val)[:50] + '...' if len(str(val)) > 50 else str(val)
                        console.print(f"    {attr} ({field_name}): {val_str}")

        console.print("\n[bold]Find the field showing story point values (1, 2, 3, 5, 8, 13...) and update config.json[/bold]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--html', is_flag=True, help='Export demo report as HTML')
@click.option('--multi-team', is_flag=True, help='Generate demo with multiple teams')
@click.pass_context
def demo(ctx, html, multi-team):
    """Run a demo with sample data (no Jira connection required)"""
    from datetime import date, timedelta
    from .models import (
        SprintInfo, SprintIssue, SprintMetrics, PhaseMetrics,
        VelocityMetrics, StuckSummary, Recommendation,
        SprintHealthReport, Phase, HealthStatus
    )
    from .ml_predictor import MonteCarloResult, VelocityTrend, RiskAssessment
    from .charts import ChartGenerator, ChartDataPoint, ChartData
    from .custom_metrics import MetricsEngine

    console.print("\n[bold blue]🎭 Running Demo with Sample Data + ML Predictions[/bold blue]\n")

    # Create sample data
    sprint_info = SprintInfo(
        id=123,
        name="Sprint 47 - Payment Integration",
        state="active",
        start_date=date.today() - timedelta(days=7),
        end_date=date.today() + timedelta(days=3),
        goal="Complete payment gateway integration and fix critical bugs"
    )

    # Sample issues
    issues = [
        SprintIssue(key="PAY-101", summary="Implement payment gateway SDK", status="Done",
                   phase=Phase.DONE, assignee="John", assignee_email=None, story_points=8,
                   issue_type="Story", priority="High", created_date=datetime.now(),
                   updated_date=datetime.now(), status_change_date=datetime.now(),
                   days_in_current_status=0, is_stuck=False),
        SprintIssue(key="PAY-102", summary="Add retry logic for failed payments", status="In Dev",
                   phase=Phase.IN_DEV, assignee="Sarah", assignee_email=None, story_points=5,
                   issue_type="Story", priority="High", created_date=datetime.now(),
                   updated_date=datetime.now(), status_change_date=datetime.now() - timedelta(days=4),
                   days_in_current_status=4, is_stuck=True, stuck_threshold=2),
        SprintIssue(key="PAY-103", summary="Payment confirmation email", status="In SIT",
                   phase=Phase.IN_SIT, assignee="Mike", assignee_email=None, story_points=3,
                   issue_type="Story", priority="Medium", created_date=datetime.now(),
                   updated_date=datetime.now(), status_change_date=datetime.now() - timedelta(days=5),
                   days_in_current_status=5, is_stuck=True, stuck_threshold=2),
        SprintIssue(key="PAY-104", summary="Fix currency conversion bug", status="Ready for SIT",
                   phase=Phase.READY_FOR_SIT, assignee="Lisa", assignee_email=None, story_points=2,
                   issue_type="Bug", priority="High", created_date=datetime.now(),
                   updated_date=datetime.now(), status_change_date=datetime.now() - timedelta(days=3),
                   days_in_current_status=3, is_stuck=True, stuck_threshold=2),
        SprintIssue(key="PAY-105", summary="Update API documentation", status="In TPO Review",
                   phase=Phase.IN_TPO_REVIEW, assignee="John", assignee_email=None, story_points=2,
                   issue_type="Task", priority="Low", created_date=datetime.now(),
                   updated_date=datetime.now(), status_change_date=datetime.now() - timedelta(days=1),
                   days_in_current_status=1, is_stuck=False),
        SprintIssue(key="PAY-106", summary="Refund flow implementation", status="In Analysis",
                   phase=Phase.IN_ANALYSIS, assignee=None, assignee_email=None, story_points=5,
                   issue_type="Story", priority="Medium", created_date=datetime.now(),
                   updated_date=datetime.now(), status_change_date=datetime.now() - timedelta(days=2),
                   days_in_current_status=2, is_stuck=False),
    ]

    metrics = SprintMetrics(
        total_issues=6, total_story_points=25,
        completed_issues=1, completed_story_points=8,
        remaining_issues=5, remaining_story_points=17
    )

    velocity = VelocityMetrics(
        daily_velocity=1.14, required_velocity=5.67,
        completion_probability=68.5, predicted_completion_points=11.4,
        shortfall_points=13.6
    )

    stuck_issues = [i for i in issues if i.is_stuck]
    stuck_summary = StuckSummary(
        total_stuck_count=3, total_stuck_points=10,
        stuck_by_phase={
            Phase.IN_DEV: [i for i in stuck_issues if i.phase == Phase.IN_DEV],
            Phase.READY_FOR_SIT: [i for i in stuck_issues if i.phase == Phase.READY_FOR_SIT],
            Phase.IN_SIT: [i for i in stuck_issues if i.phase == Phase.IN_SIT]
        },
        most_critical_items=sorted(stuck_issues, key=lambda x: x.days_in_current_status, reverse=True)
    )

    phase_breakdown = [
        PhaseMetrics(Phase.IN_ANALYSIS, "In Analysis", 1, 5, 16.7, 0, []),
        PhaseMetrics(Phase.IN_DEV, "In Development", 1, 5, 16.7, 1, [issues[1]]),
        PhaseMetrics(Phase.READY_FOR_SIT, "Ready for SIT", 1, 2, 16.7, 1, [issues[3]]),
        PhaseMetrics(Phase.IN_SIT, "In SIT", 1, 3, 16.7, 1, [issues[2]]),
        PhaseMetrics(Phase.IN_TPO_REVIEW, "In TPO Review", 1, 2, 16.7, 0, []),
        PhaseMetrics(Phase.DONE, "Done", 1, 8, 16.7, 0, []),
    ]

    recommendations = [
        Recommendation("high", "ml_risk", "🔴 3 items are stuck - consider daily standups focused on unblocking", ["PAY-102", "PAY-103", "PAY-104"]),
        Recommendation("high", "ml_prediction", "Monte Carlo simulation (1000 runs) shows only 62% completion probability", []),
        Recommendation("high", "stuck_item", "PAY-103 has been stuck in In SIT for 5 days - needs immediate attention", ["PAY-103"]),
        Recommendation("medium", "velocity", "Current velocity (1.14 SP/day) suggests 13.6 SP shortfall", []),
        Recommendation("medium", "custom_metric", "Unassigned Work Items: 1 - Number of active items without assignee", []),
    ]

    # Create ML predictions (sample)
    ml_predictions = MonteCarloResult(
        simulations_run=1000,
        predicted_completion_points=19.5,
        confidence_intervals={50: 20.0, 75: 17.5, 90: 14.0},
        probability_of_completion=62.3,
        risk_level="high",
        likely_completion_date=date.today() + timedelta(days=5),
        forecast_details={
            'average_velocity': 22.5,
            'velocity_std_dev': 4.2,
            'days_remaining': 3,
            'remaining_work': 17,
            'simulations': 1000
        }
    )

    # Create velocity trend (sample)
    velocity_trend = VelocityTrend(
        sprints_analyzed=5,
        average_velocity=22.5,
        median_velocity=23.0,
        std_deviation=4.2,
        velocity_trend="stable",
        trend_percentage=-2.5,
        historical_data=[
            {'sprint_name': 'Sprint 46', 'completed_points': 24},
            {'sprint_name': 'Sprint 45', 'completed_points': 21},
            {'sprint_name': 'Sprint 44', 'completed_points': 25},
            {'sprint_name': 'Sprint 43', 'completed_points': 20},
            {'sprint_name': 'Sprint 42', 'completed_points': 22.5},
        ]
    )

    # Create risk assessment (sample)
    risk_assessment = RiskAssessment(
        overall_risk_score=45.5,
        risk_level="high",
        risk_factors=[
            {'issue_key': 'PAY-103', 'summary': 'Payment confirmation email', 'risk_score': 65,
             'risks': ['Stuck for 5 days', 'In SIT with only 3 days remaining']},
            {'issue_key': 'PAY-106', 'summary': 'Refund flow implementation', 'risk_score': 55,
             'risks': ['Large story (5 SP) still in in_analysis', 'Unassigned work item']},
            {'issue_key': 'PAY-102', 'summary': 'Add retry logic', 'risk_score': 40,
             'risks': ['Stuck for 4 days']},
        ],
        at_risk_items=['PAY-103', 'PAY-106', 'PAY-102'],
        recommendations=[
            '🔴 3 items are stuck - consider daily standups focused on unblocking',
            '⚠️ 1 large stories at risk - consider splitting or pairing',
            '👤 1 items have no assignee - assign immediately'
        ]
    )

    # Create chart data (sample)
    chart_data = ChartData(
        sprint_name="Sprint 47",
        start_date=(date.today() - timedelta(days=7)).isoformat(),
        end_date=(date.today() + timedelta(days=3)).isoformat(),
        total_days=10,
        data_points=[
            ChartDataPoint(date=(date.today() - timedelta(days=7+i)).isoformat(), day_number=i,
                          completed_points=min(i * 1.2, 8), remaining_points=25 - min(i * 1.2, 8),
                          total_scope=25, ideal_remaining=25 - (i * 2.5), ideal_completed=i * 2.5)
            for i in range(8)
        ],
        scope_changes=[],
        current_day=7,
        chart_type="both"
    )

    # Calculate custom metrics
    config = {'thresholds': {}, 'stuck_thresholds_days': {}, 'wip_limits': {'enabled': False}}
    metrics_engine = MetricsEngine(config)
    custom_metrics = metrics_engine.calculate_all(issues, sprint_info, metrics)

    report = SprintHealthReport(
        generated_at=datetime.now(),
        sprint_info=sprint_info,
        metrics=metrics,
        velocity=velocity,
        phase_breakdown=phase_breakdown,
        stuck_summary=stuck_summary,
        health_status=HealthStatus.AT_RISK,
        recommendations=recommendations,
        all_issues=issues
    )

    # Attach extended data
    report.ml_predictions = ml_predictions
    report.velocity_trend = velocity_trend
    report.risk_assessment = risk_assessment
    report.chart_data = chart_data
    report.custom_metrics = custom_metrics

    # Display using console notifier
    from .notifier import ConsoleNotifier
    notifier = ConsoleNotifier(config)
    notifier.send(report)

    console.print("\n[dim]This was demo data with ML predictions. Configure config/config.json to connect to your Jira.[/dim]")


def main():
    """Main entry point"""
    cli(obj={})


if __name__ == '__main__':
    main()

