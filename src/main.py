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
@click.option('--project', '-p', default=None, help='Project key (e.g., RESMYB)')
@click.pass_context
def list_boards(ctx, project):
    """List all boards for a project - helps find board_id"""
    try:
        config = load_config(ctx.obj.get('config_path'))

        # Use project from argument or config
        project_key = project or config.get('jira', {}).get('project_key')

        if not project_key:
            console.print("[red]❌ No project key provided. Use --project or set jira.project_key in config[/red]")
            sys.exit(1)

        console.print(f"\n[bold blue]📋 Listing boards for project: {project_key}[/bold blue]\n")

        jira = JiraClient(config)
        boards = jira.get_boards_for_project(project_key)

        if not boards:
            console.print(f"[yellow]No boards found for project {project_key}[/yellow]")
            sys.exit(0)

        console.print(f"[green]Found {len(boards)} board(s):[/green]\n")

        from rich.table import Table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Board ID", style="bold yellow")
        table.add_column("Board Name")
        table.add_column("Type")

        for board in boards:
            table.add_row(
                str(board['id']),
                board['name'],
                board.get('type', 'unknown')
            )

        console.print(table)
        console.print("\n[dim]Use the Board ID in your config.json teams array[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
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
@click.option('--team', '-t', default=None, help='Team name to generate report for')
@click.pass_context
def export_html(ctx, output, team):
    """Export sprint health report to HTML file"""
    try:
        config = load_config(ctx.obj.get('config_path'))

        # Get team configuration (same logic as server.py)
        teams = config.get('teams', [])
        default_team = config.get('default_team', '')

        # Find the team to use
        target_team = team or default_team
        team_config = None

        for t in teams:
            if t.get('name') == target_team:
                team_config = t
                break

        # If no team found, use the first team
        if not team_config and teams:
            team_config = teams[0]

        # Merge team's board_id and sprint_id into jira config
        if team_config:
            if 'jira' not in config:
                config['jira'] = {}
            config['jira']['board_id'] = team_config.get('board_id')
            config['jira']['sprint_id'] = team_config.get('sprint_id')
            console.print(f"[dim]Using team: {team_config.get('name')}[/dim]")

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
@click.option('--team', '-t', default=None, help='Analyze specific team by name')
@click.pass_context
def analyze_all(ctx, team):
    """Analyze all teams configured in config.json"""
    try:
        config = load_config(ctx.obj.get('config_path'))
        teams = config.get('teams', [])

        if not teams:
            console.print("[yellow]No teams configured. Add 'teams' array to config.json[/yellow]")
            console.print("Example:")
            console.print('[cyan]"teams": [{"name": "Team A", "board_id": 123, "sprint_id": 456}][/cyan]')
            sys.exit(1)

        # Filter by team name if specified
        if team:
            teams = [t for t in teams if t['name'].lower() == team.lower()]
            if not teams:
                console.print(f"[red]Team '{team}' not found in config[/red]")
                sys.exit(1)

        console.print(f"\n[bold blue]🏃 Analyzing {len(teams)} team(s)...[/bold blue]\n")

        notifier = NotificationService(config)

        for t in teams:
            console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
            console.print(f"[bold cyan]Team: {t['name']}[/bold cyan]")
            console.print(f"[bold cyan]{'='*60}[/bold cyan]")

            try:
                # Create team-specific config
                team_config = config.copy()
                team_config['jira'] = config['jira'].copy()
                team_config['jira']['board_id'] = t['board_id']
                if t.get('sprint_id'):
                    team_config['jira']['sprint_id'] = t['sprint_id']
                else:
                    team_config['jira'].pop('sprint_id', None)

                jira = JiraClient(team_config)
                analyzer = SprintAnalyzer(team_config, jira)
                report = analyzer.analyze_sprint()

                # Display console output
                notifier.send_to_console(report)

            except Exception as e:
                console.print(f"[red]❌ Error analyzing {t['name']}: {e}[/red]")

        console.print(f"\n[green]✓ Analysis complete for {len(teams)} team(s)[/green]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--combined/--separate', default=True, help='Generate combined report (default) or separate files')
@click.pass_context
def export_all(ctx, combined):
    """Export HTML reports for all teams"""
    try:
        config = load_config(ctx.obj.get('config_path'))
        teams = config.get('teams', [])

        if not teams:
            console.print("[yellow]No teams configured. Add 'teams' array to config.json[/yellow]")
            sys.exit(1)

        console.print(f"\n[bold blue]📄 Generating reports for {len(teams)} teams...[/bold blue]\n")

        team_reports = []
        individual_files = []

        for t in teams:
            console.print(f"  Analyzing [cyan]{t['name']}[/cyan]...", end=" ")

            try:
                # Create team-specific config
                team_config = config.copy()
                team_config['jira'] = config['jira'].copy()
                team_config['jira']['board_id'] = t['board_id']
                if t.get('sprint_id'):
                    team_config['jira']['sprint_id'] = t['sprint_id']
                else:
                    team_config['jira'].pop('sprint_id', None)

                jira = JiraClient(team_config)
                analyzer = SprintAnalyzer(team_config, jira)
                report = analyzer.analyze_sprint()

                team_reports.append({
                    'name': t['name'],
                    'report': report
                })

                # Generate individual report
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                safe_name = t['name'].replace(' ', '_')
                individual_path = export_html_report(
                    report,
                    f"reports/{safe_name}_{timestamp}.html"
                )
                individual_files.append(individual_path)

                console.print(f"[green]✓[/green]")

            except Exception as e:
                console.print(f"[red]✗ Error: {e}[/red]")

        if team_reports:
            # Generate combined report
            combined_path = export_multi_team_html_report(team_reports)

            console.print(f"\n[bold green]✓ Reports generated:[/bold green]")
            console.print(f"\n  [bold]Combined report:[/bold]")
            console.print(f"    {combined_path}")
            console.print(f"\n  [bold]Individual reports:[/bold]")
            for f in individual_files:
                console.print(f"    {f}")

            # Open combined report in browser
            import webbrowser
            try:
                webbrowser.open(f'file:///{combined_path}')
                console.print("\n[dim]Opening combined report in browser...[/dim]")
            except:
                pass
        else:
            console.print("[red]No reports generated[/red]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
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
def demo(ctx, html, multi_team):
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

    def create_demo_report(team_name="Demo Team", sprint_name="Sprint 47",
                           completion_pct=62, stuck_count=3, health=HealthStatus.AT_RISK):
        """Create a demo report with customizable parameters"""
        sprint_info = SprintInfo(
            id=123,
            name=f"{sprint_name} - {team_name}",
            state="active",
            start_date=date.today() - timedelta(days=7),
            end_date=date.today() + timedelta(days=3),
            goal=f"Complete sprint goals for {team_name}"
        )

        # Sample issues with varied data
        import random
        base_issues = [
            ("Implement payment gateway SDK", "Done", Phase.DONE, "John", 8, False, 0),
            ("Add retry logic for failed payments", "In Dev", Phase.IN_DEV, "Sarah", 5, True, 4),
            ("Payment confirmation email", "In SIT", Phase.IN_SIT, "Mike", 3, True, 5),
            ("Fix currency conversion bug", "Ready for SIT", Phase.READY_FOR_SIT, "Lisa", 2, True, 3),
            ("Update API documentation", "In TPO Review", Phase.IN_TPO_REVIEW, "John", 2, False, 1),
            ("Refund flow implementation", "In Analysis", Phase.IN_ANALYSIS, None, 5, False, 2),
        ]

        issues = []
        for i, (summary, status, phase, assignee, sp, stuck, days) in enumerate(base_issues):
            prefix = team_name.split()[0].upper()[:3]
            issues.append(SprintIssue(
                key=f"{prefix}-{100+i}",
                summary=summary,
                status=status,
                phase=phase,
                assignee=assignee,
                assignee_email=None,
                story_points=sp,
                issue_type="Story" if i < 4 else "Bug" if i == 3 else "Task",
                priority="High" if stuck else "Medium",
                created_date=datetime.now(),
                updated_date=datetime.now(),
                status_change_date=datetime.now() - timedelta(days=days),
                days_in_current_status=days,
                is_stuck=stuck,
                stuck_threshold=2
            ))

        total_sp = sum(i.story_points for i in issues)
        done_sp = sum(i.story_points for i in issues if i.phase == Phase.DONE)

        metrics = SprintMetrics(
            total_issues=len(issues),
            total_story_points=total_sp,
            completed_issues=len([i for i in issues if i.phase == Phase.DONE]),
            completed_story_points=done_sp,
            remaining_issues=len([i for i in issues if i.phase != Phase.DONE]),
            remaining_story_points=total_sp - done_sp
        )

        velocity = VelocityMetrics(
            daily_velocity=done_sp / 7 if done_sp > 0 else 1.0,
            required_velocity=5.67,
            completion_probability=completion_pct,
            predicted_completion_points=done_sp + 3,
            shortfall_points=total_sp - done_sp - 3
        )

        stuck_issues = [i for i in issues if i.is_stuck]
        stuck_summary = StuckSummary(
            total_stuck_count=len(stuck_issues),
            total_stuck_points=sum(i.story_points for i in stuck_issues),
            stuck_by_phase={
                Phase.IN_DEV: [i for i in stuck_issues if i.phase == Phase.IN_DEV],
                Phase.READY_FOR_SIT: [i for i in stuck_issues if i.phase == Phase.READY_FOR_SIT],
                Phase.IN_SIT: [i for i in stuck_issues if i.phase == Phase.IN_SIT]
            },
            most_critical_items=sorted(stuck_issues, key=lambda x: x.days_in_current_status, reverse=True)
        )

        phase_breakdown = [
            PhaseMetrics(Phase.IN_ANALYSIS, "In Analysis", 1, 5, 16.7, 0, []),
            PhaseMetrics(Phase.IN_DEV, "In Development", 1, 5, 16.7, 1, [issues[1]] if len(issues) > 1 else []),
            PhaseMetrics(Phase.READY_FOR_SIT, "Ready for SIT", 1, 2, 16.7, 1, [issues[3]] if len(issues) > 3 else []),
            PhaseMetrics(Phase.IN_SIT, "In SIT", 1, 3, 16.7, 1, [issues[2]] if len(issues) > 2 else []),
            PhaseMetrics(Phase.IN_TPO_REVIEW, "In TPO Review", 1, 2, 16.7, 0, []),
            PhaseMetrics(Phase.DONE, "Done", 1, 8, 16.7, 0, []),
        ]

        recommendations = [
            Recommendation("high", "ml_risk", f"🔴 {len(stuck_issues)} items stuck - focus on unblocking", [i.key for i in stuck_issues]),
            Recommendation("high", "ml_prediction", f"Monte Carlo shows {completion_pct}% completion probability", []),
            Recommendation("medium", "velocity", f"Current velocity suggests shortfall", []),
        ]

        ml_predictions = MonteCarloResult(
            simulations_run=1000,
            predicted_completion_points=19.5,
            confidence_intervals={50: 20.0, 75: 17.5, 90: 14.0},
            probability_of_completion=completion_pct,
            risk_level="high" if completion_pct < 70 else "medium",
            likely_completion_date=date.today() + timedelta(days=5),
            forecast_details={'simulations': 1000}
        )

        velocity_trend = VelocityTrend(
            sprints_analyzed=5, average_velocity=22.5, median_velocity=23.0,
            std_deviation=4.2, velocity_trend="stable", trend_percentage=-2.5,
            historical_data=[]
        )

        risk_assessment = RiskAssessment(
            overall_risk_score=45.5, risk_level="high",
            risk_factors=[{'issue_key': i.key, 'summary': i.summary, 'risk_score': 50, 'risks': ['Stuck']} for i in stuck_issues[:3]],
            at_risk_items=[i.key for i in stuck_issues],
            recommendations=[]
        )

        chart_data = ChartData(
            sprint_name=sprint_name, start_date=(date.today() - timedelta(days=7)).isoformat(),
            end_date=(date.today() + timedelta(days=3)).isoformat(), total_days=10,
            data_points=[
                ChartDataPoint(date=(date.today() - timedelta(days=7-i)).isoformat(), day_number=i,
                              completed_points=min(i * 1.2, 8), remaining_points=25 - min(i * 1.2, 8),
                              total_scope=25, ideal_remaining=25 - (i * 2.5), ideal_completed=i * 2.5)
                for i in range(8)
            ],
            scope_changes=[], current_day=7, chart_type="both"
        )

        config = {'thresholds': {}, 'stuck_thresholds_days': {}, 'wip_limits': {'enabled': False}}
        metrics_engine = MetricsEngine(config)
        custom_metrics = metrics_engine.calculate_all(issues, sprint_info, metrics)

        report = SprintHealthReport(
            generated_at=datetime.now(),
            sprint_info=sprint_info, metrics=metrics, velocity=velocity,
            phase_breakdown=phase_breakdown, stuck_summary=stuck_summary,
            health_status=health, recommendations=recommendations, all_issues=issues
        )

        report.ml_predictions = ml_predictions
        report.velocity_trend = velocity_trend
        report.risk_assessment = risk_assessment
        report.chart_data = chart_data
        report.custom_metrics = custom_metrics

        return report

    if multi_team:
        console.print("\n[bold blue]🎭 Running Multi-Team Demo[/bold blue]\n")

        # Create 4 demo teams with different health statuses
        demo_teams = [
            {"name": "Team Thunder", "sprint": "Sprint 47", "completion": 85, "stuck": 1, "health": HealthStatus.HEALTHY},
            {"name": "Team Lightning", "sprint": "Sprint 47", "completion": 62, "stuck": 3, "health": HealthStatus.AT_RISK},
            {"name": "Team Storm", "sprint": "Sprint 47", "completion": 45, "stuck": 5, "health": HealthStatus.CRITICAL},
            {"name": "Team Rain", "sprint": "Sprint 47", "completion": 78, "stuck": 2, "health": HealthStatus.AT_RISK},
        ]

        team_reports = []
        for t in demo_teams:
            console.print(f"  Creating demo for [cyan]{t['name']}[/cyan]...")
            report = create_demo_report(
                team_name=t['name'],
                sprint_name=t['sprint'],
                completion_pct=t['completion'],
                stuck_count=t['stuck'],
                health=t['health']
            )
            team_reports.append({"name": t['name'], "report": report})

        if html:
            # Export combined HTML
            combined_path = export_multi_team_html_report(team_reports)
            console.print(f"\n[green]✓ Multi-team demo report saved to: {combined_path}[/green]")

            import webbrowser
            try:
                webbrowser.open(f'file:///{combined_path}')
                console.print("[dim]Opening in browser...[/dim]")
            except:
                pass
        else:
            # Console output for each team
            from .notifier import ConsoleNotifier
            config = {'thresholds': {}, 'stuck_thresholds_days': {}, 'wip_limits': {'enabled': False}}
            notifier = ConsoleNotifier(config)
            for tr in team_reports:
                console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
                console.print(f"[bold cyan]{tr['name']}[/bold cyan]")
                console.print(f"[bold cyan]{'='*60}[/bold cyan]")
                notifier.send(tr['report'])

    else:
        console.print("\n[bold blue]🎭 Running Demo with Sample Data + ML Predictions[/bold blue]\n")

        report = create_demo_report()

        if html:
            # Export HTML
            output_path = export_html_report(report)
            console.print(f"\n[green]✓ Demo report saved to: {output_path}[/green]")

            import webbrowser
            try:
                webbrowser.open(f'file:///{output_path}')
                console.print("[dim]Opening in browser...[/dim]")
            except:
                pass
        else:
            # Console output
            from .notifier import ConsoleNotifier
            config = {'thresholds': {}, 'stuck_thresholds_days': {}, 'wip_limits': {'enabled': False}}
            notifier = ConsoleNotifier(config)
            notifier.send(report)

    console.print("\n[dim]This was demo data. No Jira connection required.[/dim]")


def main():
    """Main entry point"""
    cli(obj={})


if __name__ == '__main__':
    main()

