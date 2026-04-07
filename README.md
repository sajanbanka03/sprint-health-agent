# 🏃 Sprint Health Agent

**Automated Sprint Intelligence for Agile Teams**

> Replace "what did you do yesterday?" with actionable sprint insights

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 What It Does

Sprint Health Agent monitors your Jira sprint board and provides:

- **📊 Sprint Progress** - Story points & item count tracking
- **🤖 ML Predictions** - Monte Carlo simulation for completion probability
- **🚨 Stuck Detection** - Flags items stuck > 2 days (configurable)
- **📈 Phase Analysis** - Work distribution across sprint phases
- **⚠️ Risk Assessment** - ML-based risk scoring per item
- **💡 Recommendations** - Actionable insights for the team
- **📉 Charts** - Burndown & Burnup visualization

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/sprint-health-agent.git
cd sprint-health-agent
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config/config.example.json config/config.json
# Edit config/config.json with your Jira credentials
```

### 3. Run

```bash
# Generate HTML report (opens in browser)
python -m src.main export-html

# Or use the batch file (Windows)
run_report.bat

# Console analysis
python -m src.main analyze

# Web dashboard
python server.py
```

## 📁 Project Structure

```
sprint-health-agent/
├── config/
│   ├── config.example.json    # Template - copy to config.json
│   └── config.json            # Your config (gitignored)
├── src/
│   ├── main.py                # CLI entry point
│   ├── jira_client.py         # Jira API integration
│   ├── analyzer.py            # Sprint health analysis
│   ├── ml_predictor.py        # Monte Carlo predictions
│   ├── charts.py              # Burndown/Burnup charts
│   ├── custom_metrics.py      # Extensible metrics
│   ├── notifier.py            # Slack/Teams/Chat notifications
│   ├── exporter.py            # HTML report export
│   └── models.py              # Data models
├── reports/                   # Generated HTML reports
├── templates/                 # Web dashboard templates
├── static/                    # CSS styles
├── run_report.bat             # Windows: double-click to run
├── run_report.sh              # Linux/Mac: ./run_report.sh
├── server.py                  # Web dashboard server
├── requirements.txt
└── README.md
```

## ⚙️ Configuration

### Jira Connection

Edit `config/config.json`:

```json
{
    "jira": {
        "url": "https://your-company.atlassian.net",
        "auth_method": "basic",
        "username": "your-email@company.com",
        "password": "your-api-token",
        "board_id": 123,
        "sprint_id": 456,
        "story_point_field": "customfield_10002",
        "verify_ssl": true
    }
}
```

#### Authentication Options

| Method | Use Case | Config |
|--------|----------|--------|
| **API Token** | Jira Cloud | `auth_method: "token"`, `email`, `api_token` |
| **Basic Auth** | Jira Server | `auth_method: "basic"`, `username`, `password` |
| **Bearer Token** | Jira Data Center | `auth_method: "bearer"`, `personal_access_token` |

#### Finding Your Board ID

1. Open your sprint board in browser
2. Look at URL: `https://jira.company.com/...boards/123`
3. The number after `boards/` is your board ID

#### Finding Story Point Field

```bash
python -m src.main find-fields
```

### Notifications (Optional)

#### Slack

```json
{
    "notifications": {
        "enabled": true,
        "platform": "slack",
        "slack": {
            "webhook_url": "https://hooks.slack.com/services/XXX/YYY/ZZZ",
            "channel": "#sprint-health"
        }
    }
}
```

#### Microsoft Teams

```json
{
    "notifications": {
        "enabled": true,
        "platform": "teams",
        "teams": {
            "webhook_url": "https://outlook.office.com/webhook/XXX"
        }
    }
}
```

#### Google Chat

```json
{
    "notifications": {
        "enabled": true,
        "platform": "google_chat",
        "google_chat": {
            "webhook_url": "https://chat.googleapis.com/v1/spaces/XXX/messages?key=YYY"
        }
    }
}
```

### Stuck Thresholds

Configure how many days before an item is flagged as "stuck":

```json
{
    "stuck_thresholds_days": {
        "in_analysis": 2,
        "in_dev": 2,
        "ready_for_sit": 2,
        "in_sit": 2,
        "in_review": 2
    }
}
```

### Phase Mapping

Map your Jira status names to phases:

```json
{
    "phases": {
        "backlog": ["Open", "To Do", "Backlog"],
        "in_analysis": ["In Analysis", "Refinement"],
        "in_dev": ["In Development", "In Progress"],
        "ready_for_sit": ["Ready for QA", "Dev Complete"],
        "in_sit": ["In QA", "In Testing"],
        "in_review": ["In Review", "Code Review"],
        "done": ["Done", "Closed"]
    }
}
```

## 📊 Available Commands

| Command | Description |
|---------|-------------|
| `python -m src.main analyze` | Console sprint analysis |
| `python -m src.main export-html` | Generate HTML report |
| `python -m src.main demo` | Demo with sample data |
| `python -m src.main test-connection` | Test Jira connection |
| `python -m src.main list-boards` | List available boards |
| `python -m src.main list-sprints --board ID` | List sprints |
| `python -m src.main find-fields` | Find story point field |
| `python -m src.main show-config` | View configuration |
| `python server.py` | Start web dashboard |

## 🔒 Security

- `config.json` is gitignored - credentials stay local
- Supports API tokens (recommended over passwords)
- SSL verification configurable for corporate proxies
- No data sent to external services (except your Jira/Slack)

## 🤖 ML Predictions

Uses Monte Carlo simulation with historical velocity:
- Runs 1000 simulations
- Provides confidence intervals (50%, 75%, 90%)
- Analyzes last 5 sprints for velocity trends

## 📏 Custom Metrics

Built-in metrics:
- Bug Ratio
- Unassigned Work
- Average Item Age
- Flow Efficiency
- Testing Queue Size

Add your own:

```python
from src.custom_metrics import BaseMetric, MetricResult

class MyMetric(BaseMetric):
    name = "my_metric"
    display_name = "My Custom Metric"
    
    def calculate(self, issues, sprint_info, metrics):
        value = # your calculation
        return MetricResult(
            name=self.name,
            value=value,
            display_value=f"{value}",
            threshold_status="good"  # good/warning/critical
        )
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - feel free to use in your organization!

## 🙏 Acknowledgments

Built to make standups more meaningful and less about status reporting.

