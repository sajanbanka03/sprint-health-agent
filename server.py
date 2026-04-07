"""
Sprint Health Agent - Web Dashboard
Flask-based web interface for sprint health monitoring
"""
import json
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
from flask import Flask, render_template, jsonify, request

from src.utils import load_config, PROJECT_ROOT, HISTORY_DIR
from src.jira_client import JiraClient
from src.analyzer import SprintAnalyzer
from src.models import Phase, HealthStatus

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')


def get_report():
    """Get current sprint health report"""
    config = load_config()
    jira = JiraClient(config)
    analyzer = SprintAnalyzer(config, jira)
    return analyzer.analyze_sprint()


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
        report = get_report()

        # Serialize chart data for JavaScript
        if hasattr(report, 'chart_data') and report.chart_data:
            report.chart_data_json = serialize_chart_data(report.chart_data)

        return render_template('dashboard.html', report=report)
    except Exception as e:
        return render_template('error.html', error=str(e))


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


if __name__ == '__main__':
    print("🏃 Sprint Health Dashboard")
    print("   Open http://localhost:5000 in your browser")
    print("   Press Ctrl+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=5000)

