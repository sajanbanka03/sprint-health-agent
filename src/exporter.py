"""
Report Exporter - Export sprint health reports to various formats
Supports: HTML file, Email
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from .models import SprintHealthReport, Phase, HealthStatus
from .utils import format_progress_bar, format_percentage, format_story_points, PROJECT_ROOT


REPORT_DIR = PROJECT_ROOT / "reports"


def export_html_report(report: SprintHealthReport, output_path: str = None) -> str:
    print(f"DEBUG: REPORT_DIR = {REPORT_DIR}")
    print(f"DEBUG: REPORT_DIR exists = {REPORT_DIR.exists()}")
    """
    Export sprint health report to HTML file.

    Args:
        report: SprintHealthReport object
        output_path: Optional output path (defaults to reports folder)

    Returns:
        Path to generated HTML file
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"sprint_health_{report.sprint_info.id}_{timestamp}.html"
        output_path = REPORT_DIR / filename

    print(f"DEBUG: output_path = {output_path}")
    sprint = report.sprint_info
    metrics = report.metrics
    velocity = report.velocity

    # Health color
    health_colors = {
        HealthStatus.HEALTHY: "#10b981",
        HealthStatus.AT_RISK: "#f59e0b",
        HealthStatus.CRITICAL: "#ef4444"
    }
    health_color = health_colors.get(report.health_status, "#666")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Sprint Health Report - {sprint.name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; padding: 30px; border-radius: 8px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0 0 10px 0; }}
        .health-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; background: {health_color}; color: white; font-weight: bold; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }}
        .metric {{ text-align: center; padding: 15px; background: #f9fafb; border-radius: 8px; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #1f2937; }}
        .metric-label {{ color: #6b7280; font-size: 0.9em; }}
        .progress-bar {{ background: #e5e7eb; height: 20px; border-radius: 10px; overflow: hidden; }}
        .progress-fill {{ background: linear-gradient(90deg, #2563eb, #10b981); height: 100%; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f9fafb; font-weight: 600; }}
        .stuck {{ color: #ef4444; font-weight: bold; }}
        .warning {{ background: #fef3c7; }}
        .rec-high {{ border-left: 3px solid #ef4444; padding-left: 10px; margin: 5px 0; }}
        .rec-medium {{ border-left: 3px solid #f59e0b; padding-left: 10px; margin: 5px 0; }}
        .footer {{ text-align: center; color: #6b7280; padding: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🏃 Sprint Health Report</h1>
        <div>{sprint.name} - Day {sprint.days_elapsed} of {sprint.total_days}</div>
        <div style="margin-top: 15px;">
            <span class="health-badge">{report.health_status.value.replace('_', ' ').upper()} - {velocity.completion_probability:.0f}% Completion Probability</span>
        </div>
    </div>

    <div class="card">
        <h2>📈 Sprint Progress</h2>
        <div class="metrics-grid">
            <div class="metric">
                <div class="metric-value">{metrics.total_story_points:.0f}</div>
                <div class="metric-label">Committed SP</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color: #10b981;">{metrics.completed_story_points:.0f}</div>
                <div class="metric-label">Completed SP</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color: #f59e0b;">{metrics.remaining_story_points:.0f}</div>
                <div class="metric-label">Remaining SP</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color: #2563eb;">{velocity.daily_velocity:.1f}</div>
                <div class="metric-label">SP/Day</div>
            </div>
        </div>
        <div style="margin-top: 20px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>Progress</span>
                <span>{metrics.completion_percentage_by_points:.1f}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {metrics.completion_percentage_by_points}%;"></div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>📊 Work Distribution by Phase</h2>
        <table>
            <tr><th>Phase</th><th>Count</th><th>SP</th><th>% Total</th><th>Stuck</th></tr>
"""

    for pm in report.phase_breakdown:
        if pm.issue_count > 0:
            stuck_class = 'warning' if pm.stuck_count > 0 else ''
            stuck_display = f'<span class="stuck">{pm.stuck_count} ⚠️</span>' if pm.stuck_count > 0 else '0'
            html += f'<tr class="{stuck_class}"><td>{pm.phase_display_name}</td><td>{pm.issue_count}</td><td>{pm.story_points:.0f}</td><td>{pm.percentage_of_total:.1f}%</td><td>{stuck_display}</td></tr>\n'

    html += """
        </table>
    </div>
"""

    if report.stuck_summary.total_stuck_count > 0:
        html += f"""
    <div class="card">
        <h2>🚨 Stuck Items ({report.stuck_summary.total_stuck_count})</h2>
        <table>
            <tr><th>Key</th><th>Summary</th><th>Status</th><th>Days</th><th>Assignee</th></tr>
"""
        for issue in report.stuck_summary.most_critical_items[:10]:
            summary = issue.summary[:40] + '...' if len(issue.summary) > 40 else issue.summary
            html += f'<tr><td><strong>{issue.key}</strong></td><td>{summary}</td><td>{issue.status}</td><td class="stuck">{issue.days_in_current_status}</td><td>{issue.assignee or "Unassigned"}</td></tr>\n'

        html += """
        </table>
    </div>
"""

    if report.recommendations:
        html += """
    <div class="card">
        <h2>💡 Recommendations</h2>
"""
        for rec in report.recommendations[:5]:
            rec_class = f'rec-{rec.priority}'
            icon = '🔴' if rec.priority == 'high' else '🟡' if rec.priority == 'medium' else '🟢'
            html += f'<div class="{rec_class}">{icon} {rec.message}</div>\n'

        html += """
    </div>
"""

    html += f"""
    <div class="footer">
        Generated at {report.generated_at.strftime('%Y-%m-%d %H:%M')} | Sprint Health Agent 🤖
    </div>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"DEBUG: File written, exists = {Path(output_path).exists()}")
    return str(output_path)


def send_email_report(report: SprintHealthReport, config: Dict[str, Any]) -> bool:
    """
    Send sprint health report via email using Outlook/SMTP.

    This uses the default email client on Windows.
    """
    import subprocess
    import webbrowser
    from urllib.parse import quote

    email_config = config.get('notifications', {}).get('email', {})
    to_address = email_config.get('to', '')

    if not to_address:
        print("Email 'to' address not configured")
        return False

    sprint = report.sprint_info
    metrics = report.metrics
    velocity = report.velocity

    subject = f"Sprint Health Report - {sprint.name} ({velocity.completion_probability:.0f}% completion)"

    body = f"""Sprint Health Report - {sprint.name}
Day {sprint.days_elapsed} of {sprint.total_days}

SPRINT PROGRESS
Committed: {metrics.total_story_points:.0f} SP ({metrics.total_issues} items)
Completed: {metrics.completed_story_points:.0f} SP ({metrics.completed_issues} items)
Remaining: {metrics.remaining_story_points:.0f} SP ({metrics.remaining_issues} items)

COMPLETION PROBABILITY: {velocity.completion_probability:.0f}% {report.health_emoji}

STUCK ITEMS: {report.stuck_summary.total_stuck_count}
"""

    for issue in report.stuck_summary.most_critical_items[:5]:
        body += f"  - {issue.key}: {issue.summary[:40]}... ({issue.days_in_current_status} days)\n"

    if report.recommendations:
        body += "\nRECOMMENDATIONS:\n"
        for rec in report.recommendations[:3]:
            body += f"  - {rec.message}\n"

    body += f"\nGenerated: {report.generated_at.strftime('%Y-%m-%d %H:%M')}"

    # Try to open default email client
    mailto_url = f"mailto:{to_address}?subject={quote(subject)}&body={quote(body)}"

    try:
        webbrowser.open(mailto_url)
        return True
    except Exception as e:
        print(f"Failed to open email client: {e}")
        return False

def export_multi_team_html_report(
    team_reports: List[Dict[str, Any]],
    output_path: str = None
) -> str:
    """
    Export combined HTML report for multiple teams.

    Args:
        team_reports: List of {"name": "Team Name", "report": SprintHealthReport}
        output_path: Optional output path

    Returns:
        Path to generated HTML file
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"all_teams_sprint_health_{timestamp}.html"
        output_path = REPORT_DIR / filename

    # Calculate summary stats
    total_committed = sum(tr['report'].metrics.total_story_points for tr in team_reports)
    total_completed = sum(tr['report'].metrics.completed_story_points for tr in team_reports)
    total_stuck = sum(tr['report'].stuck_summary.total_stuck_count for tr in team_reports)
    avg_probability = sum(tr['report'].velocity.completion_probability for tr in team_reports) / len(team_reports)

    # Find team with most issues
    most_stuck_team = max(team_reports, key=lambda x: x['report'].stuck_summary.total_stuck_count)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>All Teams - Sprint Health Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #1e3a5f, #2563eb); color: white; padding: 30px; border-radius: 8px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0 0 10px 0; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin-bottom: 20px; }}
        .summary-card {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .summary-value {{ font-size: 2em; font-weight: bold; }}
        .summary-label {{ color: #6b7280; font-size: 0.9em; }}
        .tabs {{ display: flex; gap: 5px; margin-bottom: 0; background: white; padding: 10px 10px 0; border-radius: 8px 8px 0 0; }}
        .tab {{ padding: 12px 24px; cursor: pointer; border: none; background: #e5e7eb; border-radius: 8px 8px 0 0; font-size: 1em; }}
        .tab.active {{ background: #2563eb; color: white; }}
        .tab-content {{ display: none; background: white; padding: 20px; border-radius: 0 0 8px 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .tab-content.active {{ display: block; }}
        .team-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #e5e7eb; }}
        .health-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; color: white; font-weight: bold; }}
        .health-healthy {{ background: #10b981; }}
        .health-at_risk {{ background: #f59e0b; }}
        .health-critical {{ background: #ef4444; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }}
        .metric {{ text-align: center; padding: 15px; background: #f9fafb; border-radius: 8px; }}
        .metric-value {{ font-size: 1.8em; font-weight: bold; color: #1f2937; }}
        .metric-label {{ color: #6b7280; font-size: 0.85em; }}
        .progress-bar {{ background: #e5e7eb; height: 16px; border-radius: 8px; overflow: hidden; margin: 15px 0; }}
        .progress-fill {{ background: linear-gradient(90deg, #2563eb, #10b981); height: 100%; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f9fafb; font-weight: 600; }}
        .stuck {{ color: #ef4444; font-weight: bold; }}
        .warning {{ background: #fef3c7; }}
        .section {{ margin-top: 20px; }}
        .section h3 {{ margin-bottom: 10px; color: #1f2937; }}
        .rec-high {{ border-left: 3px solid #ef4444; padding-left: 10px; margin: 5px 0; background: #fee2e2; padding: 8px; border-radius: 0 4px 4px 0; }}
        .rec-medium {{ border-left: 3px solid #f59e0b; padding-left: 10px; margin: 5px 0; background: #fef3c7; padding: 8px; border-radius: 0 4px 4px 0; }}
        .footer {{ text-align: center; color: #6b7280; padding: 20px; }}
        .team-comparison {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏃 All Teams - Sprint Health Report</h1>
            <div>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>

        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-value">{len(team_reports)}</div>
                <div class="summary-label">Teams</div>
            </div>
            <div class="summary-card">
                <div class="summary-value">{total_committed:.0f}</div>
                <div class="summary-label">Total Committed SP</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" style="color: #10b981;">{total_completed:.0f}</div>
                <div class="summary-label">Total Completed SP</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" style="color: #ef4444;">{total_stuck}</div>
                <div class="summary-label">Total Stuck Items</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" style="color: #2563eb;">{avg_probability:.0f}%</div>
                <div class="summary-label">Avg Completion Prob</div>
            </div>
        </div>

        <div class="team-comparison">
            <h2>📊 Team Comparison</h2>
            <table>
                <tr>
                    <th>Team</th>
                    <th>Sprint</th>
                    <th>Committed</th>
                    <th>Completed</th>
                    <th>Progress</th>
                    <th>Probability</th>
                    <th>Stuck</th>
                    <th>Status</th>
                </tr>
"""

    for tr in team_reports:
        report = tr['report']
        health_class = f"health-{report.health_status.value}"
        progress_pct = report.metrics.completion_percentage_by_points
        html += f"""
                <tr>
                    <td><strong>{tr['name']}</strong></td>
                    <td>{report.sprint_info.name}</td>
                    <td>{report.metrics.total_story_points:.0f} SP</td>
                    <td>{report.metrics.completed_story_points:.0f} SP</td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div style="flex: 1; background: #e5e7eb; height: 8px; border-radius: 4px;">
                                <div style="background: #2563eb; height: 100%; width: {progress_pct}%; border-radius: 4px;"></div>
                            </div>
                            <span>{progress_pct:.0f}%</span>
                        </div>
                    </td>
                    <td>{report.velocity.completion_probability:.0f}%</td>
                    <td class="{'stuck' if report.stuck_summary.total_stuck_count > 0 else ''}">{report.stuck_summary.total_stuck_count}</td>
                    <td><span class="health-badge {health_class}">{report.health_status.value.replace('_', ' ').upper()}</span></td>
                </tr>
"""

    html += """
            </table>
        </div>

        <div class="tabs">
"""

    for i, tr in enumerate(team_reports):
        active = "active" if i == 0 else ""
        html += f'            <button class="tab {active}" onclick="showTab({i})">{tr["name"]}</button>\n'

    html += "        </div>\n"

    for i, tr in enumerate(team_reports):
        report = tr['report']
        active = "active" if i == 0 else ""
        health_class = f"health-{report.health_status.value}"
        sprint = report.sprint_info
        metrics = report.metrics
        velocity = report.velocity

        html += f"""
        <div class="tab-content {active}" id="tab-{i}">
            <div class="team-header">
                <div>
                    <h2>{tr['name']}</h2>
                    <div>{sprint.name} - Day {sprint.days_elapsed} of {sprint.total_days}</div>
                </div>
                <span class="health-badge {health_class}">{velocity.completion_probability:.0f}% Completion</span>
            </div>

            <div class="metrics-grid">
                <div class="metric">
                    <div class="metric-value">{metrics.total_story_points:.0f}</div>
                    <div class="metric-label">Committed SP</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #10b981;">{metrics.completed_story_points:.0f}</div>
                    <div class="metric-label">Completed SP</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #f59e0b;">{metrics.remaining_story_points:.0f}</div>
                    <div class="metric-label">Remaining SP</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #2563eb;">{velocity.daily_velocity:.1f}</div>
                    <div class="metric-label">SP/Day</div>
                </div>
            </div>

            <div class="progress-bar">
                <div class="progress-fill" style="width: {metrics.completion_percentage_by_points}%;"></div>
            </div>
            <div style="text-align: center; color: #6b7280;">Progress: {metrics.completion_percentage_by_points:.1f}%</div>

            <div class="section">
                <h3>📊 Phase Distribution</h3>
                <table>
                    <tr><th>Phase</th><th>Count</th><th>SP</th><th>Stuck</th></tr>
"""

        for pm in report.phase_breakdown:
            if pm.issue_count > 0:
                stuck_class = 'warning' if pm.stuck_count > 0 else ''
                stuck_display = f'<span class="stuck">{pm.stuck_count} ⚠️</span>' if pm.stuck_count > 0 else '0'
                html += f'                    <tr class="{stuck_class}"><td>{pm.phase_display_name}</td><td>{pm.issue_count}</td><td>{pm.story_points:.0f}</td><td>{stuck_display}</td></tr>\n'

        html += "                </table>\n            </div>\n"

        if report.stuck_summary.total_stuck_count > 0:
            html += f"""
            <div class="section">
                <h3>🚨 Stuck Items ({report.stuck_summary.total_stuck_count})</h3>
                <table>
                    <tr><th>Key</th><th>Summary</th><th>Status</th><th>Days</th><th>Assignee</th></tr>
"""
            for issue in report.stuck_summary.most_critical_items[:8]:
                summary = issue.summary[:35] + '...' if len(issue.summary) > 35 else issue.summary
                html += f'                    <tr><td><strong>{issue.key}</strong></td><td>{summary}</td><td>{issue.status}</td><td class="stuck">{issue.days_in_current_status}</td><td>{issue.assignee or "Unassigned"}</td></tr>\n'

            html += "                </table>\n            </div>\n"

        if report.recommendations:
            html += "            <div class=\"section\">\n                <h3>💡 Recommendations</h3>\n"
            for rec in report.recommendations[:4]:
                rec_class = f'rec-{rec.priority}'
                icon = '🔴' if rec.priority == 'high' else '🟡'
                html += f'                <div class="{rec_class}">{icon} {rec.message}</div>\n'
            html += "            </div>\n"

        html += "        </div>\n"

    html += """
        <div class="footer">
            Sprint Health Agent 🤖 - All Teams Report
        </div>
    </div>

    <script>
        function showTab(index) {
            document.querySelectorAll('.tab').forEach((tab, i) => {
                tab.classList.toggle('active', i === index);
            });
            document.querySelectorAll('.tab-content').forEach((content, i) => {
                content.classList.toggle('active', i === index);
            });
        }
    </script>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return str(output_path)