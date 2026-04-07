"""
Report Exporter - Export sprint health reports to various formats
Supports: HTML file, Email
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from .models import SprintHealthReport, Phase, HealthStatus
from .utils import format_progress_bar, format_percentage, format_story_points, PROJECT_ROOT


REPORT_DIR = PROJECT_ROOT / "reports"


def export_html_report(report: SprintHealthReport, output_path: str = None) -> str:
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

