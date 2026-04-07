"""
Utility functions for Sprint Health Agent
"""
import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich import box

console = Console()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
HISTORY_DIR = DATA_DIR / "sprint_history"


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from JSON file"""
    if config_path is None:
        config_path = CONFIG_DIR / "config.json"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        example_path = CONFIG_DIR / "config.example.json"
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}\n"
            f"Please copy {example_path} to {config_path} and update with your settings."
        )

    with open(config_path, 'r') as f:
        return json.load(f)


def save_sprint_history(sprint_id: int, data: Dict[str, Any]) -> None:
    """Save sprint data to history for trend analysis"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    filename = f"sprint_{sprint_id}_{today}.json"
    filepath = HISTORY_DIR / filename

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def load_sprint_history(sprint_id: int) -> list:
    """Load historical data for a sprint"""
    history = []

    if not HISTORY_DIR.exists():
        return history

    for filepath in HISTORY_DIR.glob(f"sprint_{sprint_id}_*.json"):
        with open(filepath, 'r') as f:
            history.append(json.load(f))

    return sorted(history, key=lambda x: x.get('date', ''))


def format_progress_bar(percentage: float, width: int = 20) -> str:
    """Create a text-based progress bar"""
    filled = int(width * percentage / 100)
    empty = width - filled
    return f"{'█' * filled}{'░' * empty}"


def calculate_working_days(start_date: date, end_date: date) -> int:
    """Calculate number of working days between two dates"""
    working_days = 0
    current = start_date

    while current <= end_date:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            working_days += 1
        current = current + timedelta(days=1)

    return working_days


def parse_date(date_str: str) -> Optional[date]:
    """Parse various date formats"""
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.split('.')[0].replace('Z', ''), fmt.split('.')[0].replace('Z', '').replace('%z', ''))
            return dt.date() if isinstance(dt, datetime) else dt
        except ValueError:
            continue

    return None


def parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse various datetime formats"""
    if not dt_str:
        return None

    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]

    # Remove timezone info for simpler parsing
    clean_str = dt_str.replace('Z', '').split('+')[0].split('.')[0]

    for fmt in formats:
        clean_fmt = fmt.replace('%z', '').replace('Z', '').split('.')[0]
        try:
            return datetime.strptime(clean_str, clean_fmt)
        except ValueError:
            continue

    return None


def print_header(title: str) -> None:
    """Print a styled header"""
    console.print(Panel(title, style="bold blue", box=box.DOUBLE))


def print_section(title: str) -> None:
    """Print a section header"""
    console.print(f"\n[bold cyan]{title}[/bold cyan]")
    console.print("─" * 50)


def create_issues_table(issues: list, title: str = "Issues") -> Table:
    """Create a Rich table for displaying issues"""
    table = Table(title=title, box=box.ROUNDED)

    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Summary", style="white", max_width=40)
    table.add_column("Status", style="yellow")
    table.add_column("Days", justify="right", style="red")
    table.add_column("Assignee", style="green")
    table.add_column("SP", justify="right", style="magenta")

    for issue in issues:
        days_style = "red bold" if issue.days_in_current_status > 3 else "yellow"
        table.add_row(
            issue.key,
            issue.summary[:40] + "..." if len(issue.summary) > 40 else issue.summary,
            issue.status,
            f"[{days_style}]{issue.days_in_current_status}[/{days_style}]",
            issue.assignee or "Unassigned",
            str(issue.story_points) if issue.story_points else "-"
        )

    return table


def get_health_color(probability: float) -> str:
    """Get color based on completion probability"""
    if probability >= 80:
        return "green"
    elif probability >= 50:
        return "yellow"
    else:
        return "red"


def format_percentage(value: float) -> str:
    """Format a percentage value"""
    return f"{value:.1f}%"


def format_story_points(value: float) -> str:
    """Format story points value"""
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


# Need this import for calculate_working_days
from datetime import timedelta

