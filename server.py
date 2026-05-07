"""
Sprint Health Agent - Web Dashboard
Flask-based web interface for sprint health monitoring
With Smart Caching for improved performance

Author: Sajan Banka
Created: 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import json
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response

from src.utils import load_config, HISTORY_DIR
from src.jira_client import JiraClient
from src.analyzer import SprintAnalyzer
from src.models import Phase, HealthStatus
from src.cache import get_cache
from src.exporter import export_html_report, export_multi_team_html_report
from src.metric_builder import get_metric_builder
from src.strategic_insights import StrategicInsightsEngine, StrategicRecommendationTemplates
from src.scope_tracker import ScopeTracker
from src.capacity_tracker import CapacityTracker
from src.goal_predictor import SprintGoalPredictor
from src.coaching_engine import CoachingEngine
# Advanced Diagnostic Modules (Phase 2 - AI-Driven)
from src.sle_diagnostics import SLEDiagnosticsEngine
from src.flow_efficiency import FlowEfficiencyEngine
from src.sentiment_clustering import SentimentClusteringEngine
from src.quality_guardrails import QualityGuardrailsEngine
from src.rte_portfolio import RTEDiagnosticsEngine

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

# Initialize cache with 10 minute TTL for current sprint data
cache = get_cache(ttl_minutes=10)

# Clear cache on startup to ensure fresh data with any code changes
print("🔄 Clearing cache on startup to ensure fresh data...")
cache.clear_all_cache()


def get_teams_list():
    """Get list of all configured teams"""
    config = load_config()
    return config.get('teams', [])


def get_default_team():
    """Get default team name"""
    config = load_config()
    return config.get('default_team', '')


def get_report(team_name: str = None, force_refresh: bool = False):
    """Get current sprint health report with caching"""
    config = load_config()

    # Get team configuration
    teams = config.get('teams', [])
    default_team = config.get('default_team', '')

    # Find the team to use
    target_team = team_name or default_team
    team_config = None

    for team in teams:
        if team.get('name') == target_team:
            team_config = team
            break

    # If no team found, use the first team
    if not team_config and teams:
        team_config = teams[0]

    if not team_config:
        raise ValueError("No team configuration found")

    board_id = team_config.get('board_id')
    actual_team_name = team_config.get('name', 'Unknown')

    # Check cache first (unless force refresh)
    if not force_refresh:
        cached_report = cache.get_current_sprint(board_id, actual_team_name)
        if cached_report:
            cached_report.from_cache = True
            cached_report.cache_time = cache.get_cache_info().get('current_cache_items', [{}])[0].get('created_at', '')
            return cached_report

    # Merge team's board_id and sprint_id into jira config
    if 'jira' not in config:
        config['jira'] = {}
    config['jira']['board_id'] = team_config.get('board_id')
    config['jira']['sprint_id'] = team_config.get('sprint_id')

    jira = JiraClient(config)
    analyzer = SprintAnalyzer(config, jira)
    report = analyzer.analyze_sprint()

    # Attach metadata to report
    report.team_name = actual_team_name
    report.from_cache = False
    report.cache_time = None

    # Cache the report
    cache.set_current_sprint(board_id, actual_team_name, report)

    return report


def get_all_teams_reports(force_refresh: bool = False):
    """Get reports for all configured teams with caching"""
    config = load_config()
    teams = config.get('teams', [])

    team_reports = []

    for team in teams:
        try:
            team_name = team.get('name')
            board_id = team.get('board_id')

            # Check cache first (unless force refresh)
            if not force_refresh:
                cached_report = cache.get_current_sprint(board_id, team_name)
                if cached_report:
                    cached_report.from_cache = True
                    team_reports.append({
                        'name': team_name,
                        'report': cached_report,
                        'error': None,
                        'from_cache': True
                    })
                    continue

            # Create team-specific config
            team_config = config.copy()
            if 'jira' not in team_config:
                team_config['jira'] = {}
            team_config['jira'] = config.get('jira', {}).copy()
            team_config['jira']['board_id'] = board_id
            team_config['jira']['sprint_id'] = team.get('sprint_id')

            jira = JiraClient(team_config)
            analyzer = SprintAnalyzer(team_config, jira)
            report = analyzer.analyze_sprint()
            report.team_name = team_name
            report.from_cache = False

            # Cache the report
            cache.set_current_sprint(board_id, team_name, report)

            team_reports.append({
                'name': team_name,
                'report': report,
                'error': None,
                'from_cache': False
            })
        except Exception as e:
            team_reports.append({
                'name': team.get('name'),
                'report': None,
                'error': str(e),
                'from_cache': False
            })

    return team_reports


def serialize_chart_data(chart_data):
    """Convert chart data to JSON-serializable format"""
    if not chart_data:
        return None

    return {
        'sprint_name': chart_data.sprint_name,
        'start_date': chart_data.start_date,
        'end_date': chart_data.end_date,
        'total_days': chart_data.total_days,
        'current_day': chart_data.current_day,
        'data_points': [
            {
                'date': dp.date,
                'day_number': dp.day_number,
                'completed_points': dp.completed_points,
                'remaining_points': dp.remaining_points,
                'total_scope': dp.total_scope,
                'ideal_remaining': dp.ideal_remaining,
                'ideal_completed': dp.ideal_completed
            }
            for dp in chart_data.data_points
        ],
        'scope_changes': chart_data.scope_changes
    }


@app.route('/')
def dashboard():
    """Main dashboard page"""
    try:
        # Get team from URL parameter
        team_name = request.args.get('team')
        force_refresh = request.args.get('refresh') == '1'

        report = get_report(team_name, force_refresh=force_refresh)

        # Serialize chart data for JavaScript
        if hasattr(report, 'chart_data') and report.chart_data:
            report.chart_data_json = serialize_chart_data(report.chart_data)

        # Get list of all teams for dropdown
        teams = get_teams_list()
        current_team = report.team_name if hasattr(report, 'team_name') else get_default_team()

        # Cache info for display
        from_cache = getattr(report, 'from_cache', False)
        cache_info = cache.get_cache_info()

        return render_template('dashboard.html',
                             report=report,
                             teams=teams,
                             current_team=current_team,
                             view_mode='single',
                             from_cache=from_cache,
                             cache_info=cache_info)
    except Exception as e:
        return render_template('error.html', error=str(e))


@app.route('/all')
def dashboard_all_teams():
    """All teams dashboard view"""
    try:
        force_refresh = request.args.get('refresh') == '1'
        team_reports = get_all_teams_reports(force_refresh=force_refresh)
        teams = get_teams_list()
        cache_info = cache.get_cache_info()

        return render_template('dashboard_all.html',
                             team_reports=team_reports,
                             teams=teams,
                             view_mode='all',
                             cache_info=cache_info)
    except Exception as e:
        return render_template('error.html', error=str(e))


@app.route('/api/cache/clear')
def api_clear_cache():
    """API endpoint to clear all caches"""
    result = cache.clear_all_cache()
    return jsonify({
        'status': 'success',
        'cleared': result
    })


@app.route('/api/cache/info')
def api_cache_info():
    """API endpoint to get cache information"""
    return jsonify(cache.get_cache_info())


@app.route('/api/health')
def api_health():
    """API endpoint for sprint health data"""
    try:
        report = get_report()

        return jsonify({
            'status': 'success',
            'generated_at': report.generated_at.isoformat(),
            'sprint': {
                'id': report.sprint_info.id,
                'name': report.sprint_info.name,
                'days_elapsed': report.sprint_info.days_elapsed,
                'days_remaining': report.sprint_info.days_remaining,
                'total_days': report.sprint_info.total_days
            },
            'metrics': {
                'total_story_points': report.metrics.total_story_points,
                'completed_story_points': report.metrics.completed_story_points,
                'remaining_story_points': report.metrics.remaining_story_points,
                'completion_percentage': report.metrics.completion_percentage_by_points
            },
            'velocity': {
                'daily_velocity': report.velocity.daily_velocity,
                'completion_probability': report.velocity.completion_probability,
                'required_velocity': report.velocity.required_velocity
            },
            'health_status': report.health_status.value,
            'stuck_summary': {
                'total_count': report.stuck_summary.total_stuck_count,
                'total_points': report.stuck_summary.total_stuck_points,
                'items': [
                    {
                        'key': i.key,
                        'summary': i.summary,
                        'status': i.status,
                        'days': i.days_in_current_status,
                        'assignee': i.assignee
                    }
                    for i in report.stuck_summary.most_critical_items[:10]
                ]
            },
            'phase_breakdown': [
                {
                    'phase': pm.phase.value,
                    'display_name': pm.phase_display_name,
                    'count': pm.issue_count,
                    'points': pm.story_points,
                    'percentage': pm.percentage_of_total,
                    'stuck_count': pm.stuck_count
                }
                for pm in report.phase_breakdown
            ],
            'recommendations': [
                {
                    'priority': r.priority,
                    'category': r.category,
                    'message': r.message
                }
                for r in report.recommendations
            ]
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/history/<int:sprint_id>')
def api_history(sprint_id):
    """API endpoint for sprint history data"""
    try:
        history = []

        if HISTORY_DIR.exists():
            for filepath in HISTORY_DIR.glob(f"sprint_{sprint_id}_*.json"):
                with open(filepath, 'r') as f:
                    history.append(json.load(f))

        history = sorted(history, key=lambda x: x.get('date', ''))

        return jsonify({
            'status': 'success',
            'sprint_id': sprint_id,
            'history': history
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/stuck-items')
def api_stuck_items():
    """API endpoint for detailed stuck items"""
    try:
        report = get_report()

        stuck_by_phase = {}
        for phase, issues in report.stuck_summary.stuck_by_phase.items():
            stuck_by_phase[phase.value] = [
                {
                    'key': i.key,
                    'summary': i.summary,
                    'status': i.status,
                    'days_in_status': i.days_in_current_status,
                    'days_overdue': i.days_overdue,
                    'assignee': i.assignee,
                    'story_points': i.story_points,
                    'priority': i.priority
                }
                for i in issues
            ]

        return jsonify({
            'status': 'success',
            'total_stuck': report.stuck_summary.total_stuck_count,
            'stuck_by_phase': stuck_by_phase
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/download/team')
def api_download_team_report():
    """Download HTML report for a specific team"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)

        # Generate HTML content using temp file
        import tempfile
        import os

        # Use temp file to generate report
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            temp_path = f.name

        export_html_report(report, temp_path)

        with open(temp_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Clean up temp file
        os.unlink(temp_path)

        # Generate filename
        team_display = report.team_name if hasattr(report, 'team_name') else 'Team'
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Sprint_Health_{team_display}_{timestamp}.html"

        return Response(
            html_content,
            mimetype='text/html',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/download/all-teams')
def api_download_all_teams_report():
    """Download HTML report for all teams"""
    try:
        team_reports = get_all_teams_reports()

        # Filter out teams with errors
        valid_reports = [tr for tr in team_reports if tr['report'] is not None]

        if not valid_reports:
            return jsonify({
                'status': 'error',
                'message': 'No valid team reports available'
            }), 400

        # Generate HTML content
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            temp_path = f.name

        export_multi_team_html_report(valid_reports, temp_path)

        with open(temp_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        os.unlink(temp_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Sprint_Health_All_Teams_{timestamp}.html"

        return Response(
            html_content,
            mimetype='text/html',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================
# Custom Metric Builder API Endpoints
# ============================================

@app.route('/metrics')
def metrics_builder_page():
    """Custom Metric Builder page"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)
        teams = get_teams_list()
        current_team = report.team_name if hasattr(report, 'team_name') else get_default_team()

        # Get metric templates
        builder = get_metric_builder()
        templates = builder.get_templates()
        categories = builder.get_categories()

        return render_template('metrics_builder.html',
                             report=report,
                             teams=teams,
                             current_team=current_team,
                             templates=templates,
                             categories=categories)
    except Exception as e:
        return render_template('error.html', error=str(e))


@app.route('/api/metrics/templates')
def api_metric_templates():
    """API endpoint to get all metric templates"""
    builder = get_metric_builder()

    category = request.args.get('category')
    templates = builder.get_templates(category)

    return jsonify({
        'status': 'success',
        'categories': builder.get_categories(),
        'templates': [
            {
                'id': t.id,
                'name': t.name,
                'description': t.description,
                'category': t.category,
                'metric_type': t.metric_type.value,
                'configurable_params': t.configurable_params
            }
            for t in templates
        ]
    })


@app.route('/api/metrics/build', methods=['POST'])
def api_build_metric():
    """API endpoint to build a custom metric"""
    try:
        data = request.get_json()
        template_id = data.get('template_id')
        team_name = data.get('team')
        params = data.get('params', {})

        if not template_id:
            return jsonify({
                'status': 'error',
                'message': 'template_id is required'
            }), 400

        # Get report to access issues
        report = get_report(team_name)

        # Build the metric
        builder = get_metric_builder()
        result = builder.build_metric(
            template_id=template_id,
            issues=report.all_issues,
            sprint_info=report.sprint_info,
            params=params
        )

        if not result:
            return jsonify({
                'status': 'error',
                'message': f'Template {template_id} not found'
            }), 404

        return jsonify({
            'status': 'success',
            'metric': {
                'template_id': result.template_id,
                'name': result.name,
                'description': result.description,
                'metric_type': result.metric_type.value,
                'value': result.value,
                'display_value': result.display_value,
                'details': result.details,
                'generated_at': result.generated_at.isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/metrics/quick/<template_id>')
def api_quick_metric(template_id):
    """Quick API to get a metric with GET request"""
    try:
        team_name = request.args.get('team')

        # Collect any query params as metric params
        params = {k: v for k, v in request.args.items() if k != 'team'}

        # Get report
        report = get_report(team_name)

        # Build metric
        builder = get_metric_builder()
        result = builder.build_metric(
            template_id=template_id,
            issues=report.all_issues,
            sprint_info=report.sprint_info,
            params=params
        )

        if not result:
            return jsonify({
                'status': 'error',
                'message': f'Template {template_id} not found'
            }), 404

        return jsonify({
            'status': 'success',
            'metric': {
                'name': result.name,
                'display_value': result.display_value,
                'value': result.value,
                'details': result.details
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/debug/team/<team_name>')
def api_debug_team(team_name):
    """Debug endpoint to verify board filtering for a team"""
    try:
        config = load_config()
        teams = config.get('teams', [])

        # Find the team
        team_config = None
        for team in teams:
            if team.get('name') == team_name:
                team_config = team
                break

        if not team_config:
            return jsonify({'error': f'Team {team_name} not found'}), 404

        board_id = team_config.get('board_id')

        # Create team-specific config
        team_specific_config = config.copy()
        if 'jira' not in team_specific_config:
            team_specific_config['jira'] = {}
        team_specific_config['jira'] = config.get('jira', {}).copy()
        team_specific_config['jira']['board_id'] = board_id
        team_specific_config['jira']['sprint_id'] = team_config.get('sprint_id')

        # Create client and get filter info
        jira = JiraClient(team_specific_config)

        # Get board filter JQL
        board_filter_jql = jira._get_board_filter_jql(board_id)

        # Get active sprint
        sprint_info = jira.get_active_sprint()

        # Get issues count
        issues = jira.get_sprint_issues(sprint_info.id, board_id)

        # Get unique assignees
        assignees = set(i.assignee for i in issues if i.assignee)

        return jsonify({
            'status': 'success',
            'team_name': team_name,
            'board_id': board_id,
            'board_filter_jql': board_filter_jql,
            'sprint_id': sprint_info.id,
            'sprint_name': sprint_info.name,
            'total_issues': len(issues),
            'unique_assignees': sorted(list(assignees)),
            'assignee_count': len(assignees)
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================
# Strategic Insights API Endpoints
# ============================================

@app.route('/insights')
def strategic_insights_page():
    """Strategic Insights page for RTL"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)
        teams = get_teams_list()
        current_team = report.team_name if hasattr(report, 'team_name') else get_default_team()

        # Generate strategic insights
        config = load_config()
        engine = StrategicInsightsEngine(config)

        # Get historical data for trend analysis
        historical_data = []
        if hasattr(report, 'velocity_trend') and report.velocity_trend:
            historical_data = report.velocity_trend.historical_velocities if hasattr(report.velocity_trend, 'historical_velocities') else []

        insights = engine.generate_report(
            issues=report.all_issues,
            sprint_info=report.sprint_info,
            metrics=report.metrics,
            historical_data=historical_data
        )

        return render_template('strategic_insights.html',
                             report=report,
                             insights=insights,
                             teams=teams,
                             current_team=current_team)
    except Exception as e:
        return render_template('error.html', error=str(e))


@app.route('/api/insights')
def api_strategic_insights():
    """API endpoint for strategic insights data"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)

        # Generate strategic insights
        config = load_config()
        engine = StrategicInsightsEngine(config)

        insights = engine.generate_report(
            issues=report.all_issues,
            sprint_info=report.sprint_info,
            metrics=report.metrics,
            historical_data=[]
        )

        return jsonify({
            'status': 'success',
            'generated_at': insights.generated_at.isoformat(),
            'executive_summary': insights.executive_summary,
            'priority_actions': insights.priority_actions,
            'flow_efficiency': {
                'score': insights.flow_efficiency.score,
                'status': insights.flow_efficiency.status,
                'active_time': insights.flow_efficiency.total_active_time_days,
                'wait_time': insights.flow_efficiency.total_wait_time_days,
                'recommendation': insights.flow_efficiency.recommendation
            },
            'cycle_time': {
                'mean': insights.cycle_time.mean_cycle_time,
                'std_deviation': insights.cycle_time.std_deviation,
                'threshold': insights.cycle_time.threshold,
                'outlier_count': len(insights.cycle_time.outliers),
                'outliers': [
                    {
                        'key': o.issue_key,
                        'summary': o.summary,
                        'assignee': o.assignee,
                        'age_days': o.current_age_days,
                        'coaching_question': o.coaching_question
                    }
                    for o in insights.cycle_time.outliers
                ],
                'recommendation': insights.cycle_time.recommendation
            },
            'wip_stress': {
                'team_health': insights.wip_stress.team_health,
                'team_avg_wip': insights.wip_stress.team_avg_wip,
                'high_risk_count': len(insights.wip_stress.high_risk_assignees),
                'high_risk_assignees': [
                    {
                        'name': a.name,
                        'wip_count': a.wip_count,
                        'avg_age': a.avg_task_age,
                        'stress_level': a.stress_level,
                        'recommendation': a.recommendation
                    }
                    for a in insights.wip_stress.high_risk_assignees
                ],
                'recommendation': insights.wip_stress.recommendation
            },
            'innovation_rate': {
                'innovation_sp': insights.innovation_rate.innovation_sp,
                'maintenance_sp': insights.innovation_rate.maintenance_sp,
                'innovation_percentage': insights.innovation_rate.innovation_percentage,
                'maintenance_percentage': insights.innovation_rate.maintenance_percentage,
                'status': insights.innovation_rate.status,
                'trend': insights.innovation_rate.trend,
                'recommendation': insights.innovation_rate.recommendation
            },
            'ppm': {
                'planned_sp': insights.ppm.planned_sp,
                'actual_sp': insights.ppm.actual_sp,
                'score': insights.ppm.ppm_score,
                'status': insights.ppm.status,
                'pi_forecast': insights.ppm.pi_forecast,
                'recommendation': insights.ppm.recommendation
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/insights/all')
def strategic_insights_all_teams():
    """Strategic Insights summary for all teams - RTL Overview"""
    try:
        team_reports = get_all_teams_reports()
        teams = get_teams_list()
        config = load_config()
        engine = StrategicInsightsEngine(config)

        # Generate insights for each team
        all_insights = []
        for tr in team_reports:
            if tr['report']:
                try:
                    insights = engine.generate_report(
                        issues=tr['report'].all_issues,
                        sprint_info=tr['report'].sprint_info,
                        metrics=tr['report'].metrics,
                        historical_data=[]
                    )
                    all_insights.append({
                        'name': tr['name'],
                        'report': tr['report'],
                        'insights': insights,
                        'error': None
                    })
                except Exception as e:
                    all_insights.append({
                        'name': tr['name'],
                        'report': tr['report'],
                        'insights': None,
                        'error': str(e)
                    })
            else:
                all_insights.append({
                    'name': tr['name'],
                    'report': None,
                    'insights': None,
                    'error': tr.get('error', 'No data')
                })

        return render_template('strategic_insights_all.html',
                             all_insights=all_insights,
                             teams=teams)
    except Exception as e:
        return render_template('error.html', error=str(e))


# ============================================
# Scope Tracking API Endpoints (Phase 2)
# ============================================

@app.route('/api/scope')
def api_scope_analysis():
    """API endpoint for scope creep analysis"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)

        config = load_config()
        tracker = ScopeTracker(config)

        # Get current team name
        current_team = report.team_name if hasattr(report, 'team_name') else get_default_team()

        # Run scope analysis
        scope_report = tracker.analyze_scope_creep(
            sprint_info=report.sprint_info,
            current_issues=report.all_issues,
            metrics=report.metrics,
            team_name=current_team,
            goal_probability=report.velocity.completion_probability
        )

        # Get display-ready summary
        summary = tracker.get_scope_summary(scope_report)

        return jsonify({
            'status': 'success',
            'team': current_team,
            'sprint': {
                'id': report.sprint_info.id,
                'name': report.sprint_info.name,
                'day': report.sprint_info.days_elapsed,
                'total_days': report.sprint_info.total_days
            },
            'scope': summary
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/scope/capture', methods=['POST'])
def api_capture_baseline():
    """API endpoint to manually capture/reset baseline"""
    try:
        data = request.get_json() if request.is_json else {}
        team_name = data.get('team') or request.args.get('team')
        force = data.get('force', False)

        report = get_report(team_name)
        config = load_config()
        tracker = ScopeTracker(config)

        current_team = report.team_name if hasattr(report, 'team_name') else get_default_team()

        # Capture baseline
        snapshot = tracker.capture_baseline(
            sprint_info=report.sprint_info,
            issues=report.all_issues,
            team_name=current_team,
            force=force
        )

        return jsonify({
            'status': 'success',
            'message': f'Baseline captured for {current_team}',
            'snapshot': {
                'sprint_id': snapshot.sprint_id,
                'sprint_name': snapshot.sprint_name,
                'captured_at': snapshot.captured_at,
                'capture_day': snapshot.capture_day,
                'total_issues': snapshot.total_issues,
                'total_story_points': snapshot.total_story_points,
                'sprint_started_on_time': snapshot.sprint_started_on_time,
                'days_late': snapshot.days_late
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/scope/reset', methods=['POST'])
def api_reset_baseline():
    """API endpoint to delete baseline and re-capture"""
    try:
        data = request.get_json() if request.is_json else {}
        team_name = data.get('team') or request.args.get('team')

        report = get_report(team_name)
        config = load_config()
        tracker = ScopeTracker(config)

        current_team = report.team_name if hasattr(report, 'team_name') else get_default_team()

        # Delete existing baseline
        deleted = tracker.delete_baseline(current_team, report.sprint_info.id)

        # Capture fresh baseline
        snapshot = tracker.capture_baseline(
            sprint_info=report.sprint_info,
            issues=report.all_issues,
            team_name=current_team,
            force=True
        )

        return jsonify({
            'status': 'success',
            'message': f'Baseline reset for {current_team}',
            'previous_deleted': deleted,
            'new_snapshot': {
                'captured_at': snapshot.captured_at,
                'total_issues': snapshot.total_issues,
                'total_story_points': snapshot.total_story_points
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================
# Capacity Intelligence API Endpoints (Phase 3)
# ============================================

@app.route('/api/capacity')
def api_capacity_analysis():
    """API endpoint for team capacity analysis"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)

        config = load_config()
        tracker = CapacityTracker(config)

        current_team = report.team_name if hasattr(report, 'team_name') else get_default_team()

        # Run capacity analysis
        capacity_report = tracker.analyze_capacity(
            issues=report.all_issues,
            sprint_info=report.sprint_info,
            team_name=current_team
        )

        # Get display-ready summary
        summary = tracker.get_capacity_summary(capacity_report)

        return jsonify({
            'status': 'success',
            'team': current_team,
            'sprint': {
                'id': report.sprint_info.id,
                'name': report.sprint_info.name,
                'day': report.sprint_info.days_elapsed,
                'total_days': report.sprint_info.total_days
            },
            'capacity': summary
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/capacity/set', methods=['POST'])
def api_set_member_capacity():
    """API endpoint to set capacity for a team member"""
    try:
        data = request.get_json() if request.is_json else {}
        team_name = data.get('team')
        member_name = data.get('member')
        capacity_sp = data.get('capacity_sp')

        if not all([team_name, member_name, capacity_sp is not None]):
            return jsonify({
                'status': 'error',
                'message': 'team, member, and capacity_sp are required'
            }), 400

        config = load_config()
        tracker = CapacityTracker(config)

        # Set the capacity
        tracker.set_member_capacity(team_name, member_name, float(capacity_sp))

        return jsonify({
            'status': 'success',
            'message': f'Capacity set for {member_name} in {team_name}',
            'member': member_name,
            'team': team_name,
            'capacity_sp': capacity_sp
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/capacity/config')
def api_capacity_config():
    """API endpoint to get capacity configuration"""
    try:
        team_name = request.args.get('team')
        config = load_config()
        tracker = CapacityTracker(config)

        if team_name and team_name in tracker.capacity_configs:
            team_config = tracker.capacity_configs[team_name]
            return jsonify({
                'status': 'success',
                'team': team_name,
                'config': team_config.to_dict()
            })
        else:
            return jsonify({
                'status': 'success',
                'teams': {
                    name: cfg.to_dict()
                    for name, cfg in tracker.capacity_configs.items()
                }
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================
# Sprint Goal Prediction API Endpoints (Phase 1)
# ============================================

@app.route('/api/goal')
def api_goal_prediction():
    """API endpoint for sprint goal prediction data"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)

        config = load_config()
        predictor = SprintGoalPredictor(config)

        # Get historical data for comparison
        jira_config = config.copy()
        teams = config.get('teams', [])
        for team in teams:
            if team.get('name') == (report.team_name if hasattr(report, 'team_name') else get_default_team()):
                if 'jira' not in jira_config:
                    jira_config['jira'] = {}
                jira_config['jira']['board_id'] = team.get('board_id')
                break

        jira = JiraClient(jira_config)
        historical_data = jira.get_velocity(num_sprints=5)

        # Generate prediction
        prediction = predictor.generate_prediction(
            sprint_info=report.sprint_info,
            metrics=report.metrics,
            velocity=report.velocity,
            issues=report.all_issues,
            ml_predictions=getattr(report, 'ml_predictions', None),
            historical_data=historical_data
        )

        return jsonify({
            'status': 'success',
            'team': report.team_name if hasattr(report, 'team_name') else get_default_team(),
            'sprint': {
                'id': report.sprint_info.id,
                'name': report.sprint_info.name,
                'day': report.sprint_info.days_elapsed,
                'total_days': report.sprint_info.total_days,
                'days_remaining': report.sprint_info.days_remaining,
                'goal': report.sprint_info.goal
            },
            'prediction': prediction.to_dict()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================
# Coaching & Improvement API Endpoints (Phase 5)
# ============================================

@app.route('/api/coaching')
def api_coaching_report():
    """API endpoint for coaching and improvement data"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)

        config = load_config()
        engine = CoachingEngine(config)

        # Get historical data for trend analysis
        jira_config = config.copy()
        teams = config.get('teams', [])
        for team in teams:
            if team.get('name') == (report.team_name if hasattr(report, 'team_name') else get_default_team()):
                if 'jira' not in jira_config:
                    jira_config['jira'] = {}
                jira_config['jira']['board_id'] = team.get('board_id')
                break

        jira = JiraClient(jira_config)
        historical_data = jira.get_velocity(num_sprints=5)

        # Generate coaching report
        current_team = report.team_name if hasattr(report, 'team_name') else get_default_team()
        coaching_report = engine.generate_coaching_report(
            sprint_info=report.sprint_info,
            metrics=report.metrics,
            velocity=report.velocity,
            issues=report.all_issues,
            historical_data=historical_data,
            team_name=current_team
        )

        return jsonify({
            'status': 'success',
            'team': current_team,
            'sprint': {
                'id': report.sprint_info.id,
                'name': report.sprint_info.name,
                'day': report.sprint_info.days_elapsed,
                'total_days': report.sprint_info.total_days
            },
            'coaching': coaching_report.to_dict()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================
# Module 1: SLE Diagnostics (Stuck Item Diagnostic Engine)
# ============================================

@app.route('/api/diagnostics/aging')
def api_aging_wip():
    """API endpoint for Aging WIP analysis (SLE-based risk)"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)

        config = load_config()
        engine = SLEDiagnosticsEngine(config)

        # Get historical data for SLE calculation
        jira_config = config.copy()
        teams = config.get('teams', [])
        for team in teams:
            if team.get('name') == (report.team_name if hasattr(report, 'team_name') else get_default_team()):
                if 'jira' not in jira_config:
                    jira_config['jira'] = {}
                jira_config['jira']['board_id'] = team.get('board_id')
                break

        jira = JiraClient(jira_config)
        historical_data = jira.get_velocity(num_sprints=5)

        # Generate aging report
        aging_report = engine.analyze_aging_wip(
            issues=report.all_issues,
            sprint_info=report.sprint_info,
            historical_data=historical_data
        )

        return jsonify({
            'status': 'success',
            'team': report.team_name if hasattr(report, 'team_name') else get_default_team(),
            'data': aging_report.to_dict(),
            'visualization': engine.get_visualization_data(aging_report)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================
# Module 2: Flow Efficiency & Wait-Waste Analytics
# ============================================

@app.route('/api/diagnostics/flow')
def api_flow_efficiency():
    """API endpoint for Flow Efficiency analysis"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)

        config = load_config()
        engine = FlowEfficiencyEngine(config)

        # Generate flow report
        flow_report = engine.analyze_flow(
            issues=report.all_issues,
            sprint_info=report.sprint_info
        )

        return jsonify({
            'status': 'success',
            'team': report.team_name if hasattr(report, 'team_name') else get_default_team(),
            'data': flow_report.to_dict(),
            'visualization': engine.get_visualization_data(flow_report)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================
# Module 3: AI Sentiment & Blocker Clustering
# ============================================

@app.route('/api/diagnostics/sentiment')
def api_sentiment_analysis():
    """API endpoint for Sentiment Analysis and Blocker Clustering"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)

        config = load_config()
        engine = SentimentClusteringEngine(config)

        # Generate sentiment report
        sentiment_report = engine.analyze(
            issues=report.all_issues,
            sprint_info=report.sprint_info
        )

        return jsonify({
            'status': 'success',
            'team': report.team_name if hasattr(report, 'team_name') else get_default_team(),
            'data': sentiment_report.to_dict(),
            'pareto_chart': engine.get_pareto_chart_data(sentiment_report)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================
# Module 4: Quality & Technical Debt Guardrails
# ============================================

@app.route('/api/diagnostics/quality')
def api_quality_guardrails():
    """API endpoint for Quality & Technical Debt analysis"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)

        config = load_config()
        engine = QualityGuardrailsEngine(config)

        # Get previous TDR for trend (from cache or history)
        historical_tdr = None  # Would need to implement TDR history storage

        # Generate quality report
        quality_report = engine.analyze(
            issues=report.all_issues,
            sprint_info=report.sprint_info,
            historical_tdr=historical_tdr
        )

        return jsonify({
            'status': 'success',
            'team': report.team_name if hasattr(report, 'team_name') else get_default_team(),
            'data': quality_report.to_dict(),
            'visualization': engine.get_visualization_data(quality_report)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================
# RTE Portfolio View & Team Diagnostic View
# ============================================

@app.route('/rte/portfolio')
def rte_portfolio_page():
    """RTE Portfolio View - Program level overview"""
    try:
        team_reports = get_all_teams_reports()
        teams = get_teams_list()
        config = load_config()

        engine = RTEDiagnosticsEngine(config)

        # Prepare team data for portfolio view
        team_data = []
        for tr in team_reports:
            if tr['report']:
                team_data.append({
                    'name': tr['name'],
                    'report': tr['report'],
                    'issues': tr['report'].all_issues,
                    'historical_data': []
                })

        # Generate portfolio view
        portfolio = engine.generate_portfolio_view(
            program_name=config.get('program_name', 'Program'),
            team_reports=team_data
        )

        return render_template('rte_portfolio.html',
                             portfolio=portfolio,
                             teams=teams)
    except Exception as e:
        return render_template('error.html', error=str(e))


@app.route('/api/rte/portfolio')
def api_rte_portfolio():
    """API endpoint for RTE Portfolio View data"""
    try:
        team_reports = get_all_teams_reports()
        config = load_config()

        engine = RTEDiagnosticsEngine(config)

        # Prepare team data
        team_data = []
        for tr in team_reports:
            if tr['report']:
                team_data.append({
                    'name': tr['name'],
                    'report': tr['report'],
                    'issues': tr['report'].all_issues,
                    'historical_data': []
                })

        # Generate portfolio view
        portfolio = engine.generate_portfolio_view(
            program_name=config.get('program_name', 'Program'),
            team_reports=team_data
        )

        return jsonify({
            'status': 'success',
            'portfolio': portfolio.to_dict()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/rte/team/<team_name>')
def rte_team_diagnostic_page(team_name):
    """Team Diagnostic View - detailed team analysis"""
    try:
        report = get_report(team_name)
        teams = get_teams_list()
        config = load_config()

        engine = RTEDiagnosticsEngine(config)

        # Get historical data
        jira_config = config.copy()
        for team in config.get('teams', []):
            if team.get('name') == team_name:
                if 'jira' not in jira_config:
                    jira_config['jira'] = {}
                jira_config['jira']['board_id'] = team.get('board_id')
                break

        jira = JiraClient(jira_config)
        historical_data = jira.get_velocity(num_sprints=5)

        # Generate diagnostic view
        diagnostic = engine.generate_team_diagnostic(
            team_name=team_name,
            issues=report.all_issues,
            sprint_info=report.sprint_info,
            metrics=report.metrics,
            historical_data=historical_data
        )

        return render_template('rte_team_diagnostic.html',
                             diagnostic=diagnostic,
                             teams=teams,
                             current_team=team_name)
    except Exception as e:
        return render_template('error.html', error=str(e))


@app.route('/api/rte/team/<team_name>')
def api_rte_team_diagnostic(team_name):
    """API endpoint for Team Diagnostic View data"""
    try:
        report = get_report(team_name)
        config = load_config()

        engine = RTEDiagnosticsEngine(config)

        # Get historical data
        jira_config = config.copy()
        for team in config.get('teams', []):
            if team.get('name') == team_name:
                if 'jira' not in jira_config:
                    jira_config['jira'] = {}
                jira_config['jira']['board_id'] = team.get('board_id')
                break

        jira = JiraClient(jira_config)
        historical_data = jira.get_velocity(num_sprints=5)

        # Generate diagnostic view
        diagnostic = engine.generate_team_diagnostic(
            team_name=team_name,
            issues=report.all_issues,
            sprint_info=report.sprint_info,
            metrics=report.metrics,
            historical_data=historical_data
        )

        return jsonify({
            'status': 'success',
            'diagnostic': diagnostic.to_dict()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/diagnostics')
def diagnostics_dashboard_page():
    """Advanced Diagnostics Dashboard - combines all 4 modules"""
    try:
        team_name = request.args.get('team')
        report = get_report(team_name)
        teams = get_teams_list()
        current_team = report.team_name if hasattr(report, 'team_name') else get_default_team()

        config = load_config()

        # Initialize all engines
        sle_engine = SLEDiagnosticsEngine(config)
        flow_engine = FlowEfficiencyEngine(config)
        sentiment_engine = SentimentClusteringEngine(config)
        quality_engine = QualityGuardrailsEngine(config)

        # Get historical data
        jira_config = config.copy()
        for team in config.get('teams', []):
            if team.get('name') == current_team:
                if 'jira' not in jira_config:
                    jira_config['jira'] = {}
                jira_config['jira']['board_id'] = team.get('board_id')
                break

        jira = JiraClient(jira_config)
        historical_data = jira.get_velocity(num_sprints=5)

        # Generate all reports
        aging_report = sle_engine.analyze_aging_wip(
            report.all_issues, report.sprint_info, historical_data
        )
        flow_report = flow_engine.analyze_flow(
            report.all_issues, report.sprint_info
        )
        sentiment_report = sentiment_engine.analyze(
            report.all_issues, report.sprint_info
        )
        quality_report = quality_engine.analyze(
            report.all_issues, report.sprint_info
        )

        return render_template('diagnostics_dashboard.html',
                             report=report,
                             aging=aging_report,
                             flow=flow_report,
                             sentiment=sentiment_report,
                             quality=quality_report,
                             teams=teams,
                             current_team=current_team)
    except Exception as e:
        return render_template('error.html', error=str(e))


if __name__ == '__main__':
    print("🏃 Sprint Health Dashboard")
    print("   Open http://localhost:5000 in your browser")
    print("   Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=5000)

