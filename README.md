# 🏃 Sprint Health Agent

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)

**AI-Powered Sprint Intelligence for Agile Teams**

> Transform from "what happened" to "what will happen" with predictive analytics

---

## 🆕 What's New in v2.0.0

| Feature | Description |
|---------|-------------|
| 🎯 **Sprint Goal Prominence** | Giant hero section with goal probability |
| 📊 **Scope Creep Detection** | Day 1 baseline capture, change tracking |
| 👥 **Capacity Intelligence** | Per-person workload vs capacity analysis |
| 📈 **Flow Efficiency** | Wait vs Work time analysis (SLE-based) |
| 🧠 **AI Sentiment Analysis** | Comment sentiment & burnout risk detection |
| 🏛️ **RTE Portfolio View** | Cross-team program predictability |
| 🎓 **Coaching Engine** | AI-powered improvement recommendations |
| 🔍 **Quality Guardrails** | Defect leakage & tech debt tracking |

---

## 📋 Table of Contents
- [What It Does](#-what-it-does)
- [Quick Start (5 Minutes)](#-quick-start-5-minutes)
- [Deployment Guide](#-deployment-guide)
- [Configuration](#-configuration)
- [Commands Reference](#-commands-reference)
- [Features](#-features)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 What It Does

This agent monitors your team's sprint board and provides:

| Feature | Description |
|---------|-------------|
| 📊 **Sprint Progress** | Visual progress tracking (Story Points + Item Count) |
| 🤖 **ML Predictions** | Monte Carlo simulation for completion probability |
| 📈 **Burnup Charts** | Progress visualization with scope change tracking |
| 🚨 **Stuck Detection** | Identifies tickets blocked in any phase |
| ⚠️ **Risk Assessment** | ML-based risk scoring for at-risk items |
| 💬 **Notifications** | MS Teams/Slack alerts for scrum masters |

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Install Dependencies
```cmd
cd SprintHealth
pip install -r requirements.txt
```

### Step 2: Configure Jira Connection
```cmd
copy config\config.example.json config\config.json
```

Edit `config\config.json` with your credentials:
```json
{
    "jira": {
        "url": "https://jiraagile.emirates.com",
        "auth_method": "basic",
        "username": "YOUR_EMPLOYEE_ID",
        "password": "YOUR_PASSWORD",
        "verify_ssl": false
    },
    "teams": [
        {
            "name": "Team Thunder",
            "board_id": 25399,
            "sprint_id": null
        }
    ],
    "default_team": "Team Thunder"
}
```

### Step 3: Test Connection
```cmd
python -m src.main test-connection
```
You should see: `✓ Connected as Your Name (your.email@emirates.com)`

### Step 4: Generate Your First Report
```cmd
python -m src.main export-html
```
This opens a beautiful HTML report in your browser!

### Step 5: Start the Web Dashboard (Optional)
```cmd
python server.py
```
Open http://localhost:5000 in your browser.

---

## 📦 Deployment Guide

### Deploying to Another Machine

#### Prerequisites
- Windows 10/11
- Python 3.10+ (Download from python.org)
- Network access to Jira (same intranet)

#### Step-by-Step

1. **Copy the SprintHealth folder** to the target machine
   ```
   C:\Tools\SprintHealth
   ```

2. **Install Python** (if not installed)
   - Download from https://www.python.org/downloads/
   - ✅ CHECK "Add Python to PATH" during installation
   - Verify: `python --version`

3. **Install dependencies**
   ```cmd
   cd C:\Tools\SprintHealth
   pip install -r requirements.txt
   ```

4. **Configure credentials**
   - Copy `config\config.example.json` to `config\config.json`
   - Update with the user's Jira credentials

5. **Create a desktop shortcut** (Optional)
   Create `Start Dashboard.bat`:
   ```bat
   @echo off
   cd /d C:\Tools\SprintHealth
   start http://localhost:5000
   python server.py
   ```

---

## ⚙️ Configuration

### Minimal Configuration (Just Get It Working)

```json
{
    "jira": {
        "url": "https://jiraagile.emirates.com",
        "auth_method": "basic",
        "username": "YOUR_EMPLOYEE_ID",
        "password": "YOUR_PASSWORD",
        "verify_ssl": false
    },
    "teams": [
        {
            "name": "Team Thunder",
            "board_id": 25399,
            "sprint_id": null
        }
    ],
    "default_team": "Team Thunder"
}
```

### How to Find Your Board ID

1. Open your Jira board in browser
2. Look at the URL: `https://jiraagile.emirates.com/.../boards/25399`
3. The number at the end (25399) is your Board ID

### How to Find Your Sprint ID (Optional)

1. Open any issue in the sprint
2. Look at the Sprint field
3. Or use: `python -m src.main test-connection` - it shows the active sprint

### Full Configuration Reference

| Setting | Description | Required |
|---------|-------------|----------|
| `jira.url` | Your Jira server URL | ✅ Yes |
| `jira.auth_method` | "basic" for username/password | ✅ Yes |
| `jira.username` | Your employee ID | ✅ Yes |
| `jira.password` | Your password | ✅ Yes |
| `jira.verify_ssl` | Set `false` for corporate SSL | ✅ Yes |
| `teams[].name` | Team display name | ✅ Yes |
| `teams[].board_id` | Jira board ID | ✅ Yes |
| `teams[].sprint_id` | **OPTIONAL** - Auto-detects active sprint if not set | ❌ No |
| `default_team` | Default team for reports | No |
| `stuck_thresholds_days` | Days before "stuck" warning | No |
| `historical_sprints` | Number of past sprints for ML training (default: 5) | No |

### About sprint_id (Optional)

**You don't need to provide sprint_id!** The system automatically:
1. Detects the **active sprint** from your board
2. Uses the **last 5 closed sprints** for ML predictions and velocity trends

**When to use sprint_id:**
- To analyze a specific historical sprint
- To override auto-detection for testing

```json
{
    "teams": [
        {
            "name": "Team Thunder",
            "board_id": 25399
            // No sprint_id = auto-detect active sprint ✅
        }
    ]
}
```

### Workflow Phase Mapping

Map your Jira statuses to phases:

```json
{
    "phases": {
        "backlog": ["Open", "To Do", "Backlog"],
        "in_analysis": ["In Analysis", "Refinement"],
        "in_dev": ["In Development", "In Progress"],
        "ready_for_sit": ["Ready for SIT", "Dev Complete"],
        "in_sit": ["In SIT", "Testing"],
        "in_tpo_review": ["In TPO Review", "In Review"],
        "done": ["Done", "Closed", "Resolved"]
    }
}
```

---

## 📟 Commands Reference

| Command | Description |
|---------|-------------|
| `python -m src.main analyze` | Analyze sprint, show in terminal |
| `python -m src.main export-html` | Generate HTML report |
| `python -m src.main export-html -t "Team Striker"` | Report for specific team |
| `python -m src.main export-all` | Reports for all teams |
| `python -m src.main list-boards -p RESMYB` | List all boards for a project |
| `python -m src.main test-connection` | Test Jira connection |
| `python -m src.main demo` | Demo with sample data |
| `python server.py` | Start web dashboard |

### Web Dashboard URLs

| URL | Description |
|-----|-------------|
| `http://localhost:5000/` | Dashboard for default team |
| `http://localhost:5000/?team=Team%20Striker` | Dashboard for specific team |
| `http://localhost:5000/all` | All teams overview |

### Batch Files

| File | Description |
|------|-------------|
| `run_daily_report.bat` | Generate report for default team |
| `run_all_teams_report.bat` | Generate reports for all teams |

---

## ✨ Features

### 🤖 ML-Powered Predictions

- **Monte Carlo Simulation**: Runs 1000+ simulations using historical velocity
- **Confidence Intervals**: 50%, 75%, 90% probability bounds
- **Risk Scoring**: Identifies items likely to slip

### 🎯 Sprint Goal Prominence (NEW in v2)

- Giant probability display at top of dashboard
- Velocity gap analysis (current vs required)
- At-risk item identification with reasons
- Commitment comparison vs historical average

### 📊 Scope Creep Detection (NEW in v2)

- Automatic Day 1 baseline capture
- Track items added/removed after sprint start
- Impact on goal probability calculation
- Sprint start timing indicator (on time / late)

### 👥 Capacity Intelligence (NEW in v2)

- Per-person capacity tracking (SP per sprint)
- Utilization analysis with visual bars
- Overload/availability alerts
- AI suggestions for work redistribution

### 📈 Flow Efficiency Analytics (NEW in v2)

- **SLE-Based Risk**: 85th percentile cycle time thresholds
- **Aging WIP**: Items flagged Amber (50% SLE) or Red (85% SLE)
- **Wait vs Work**: Time in active vs passive statuses
- **Bottleneck Detection**: Identify systemic handoff delays

### 🧠 AI Sentiment & Clustering (NEW in v2)

- Comment sentiment analysis (positive/negative/frustrated)
- Burnout risk detection before official blocks
- Blocker categorization with Pareto analysis
- Root cause clustering (External Dependency, Environment, etc.)

### 🏛️ RTE Portfolio View (NEW in v2)

- Program predictability (Actual vs Planned)
- Cross-team comparison and rankings
- Team diagnostic deep-dives
- Executive alerts and action items

### 🎓 Coaching Engine (NEW in v2)

- Team health score (0-100 with A-F grades)
- Sprint-over-sprint comparisons
- Improvement pattern detection
- Priority-ranked coaching tips

### 🔍 Quality Guardrails (NEW in v2)

- Defect leakage rate (SIT/UAT vs Production)
- SQALE Technical Debt Ratio
- PM alerts when TDR > 5%
- Quality score with grading

### 📈 Burnup Charts (Recommended)

Shows completed work AND scope changes:
- ✅ Makes scope creep visible
- ✅ Team sees progress even when scope changes
- ✅ Honest picture for stakeholders

### 📊 Custom Metrics

| Metric | Description |
|--------|-------------|
| Bug Ratio | Bugs per story |
| Unassigned Work | Items without assignee |
| Average Age | Days in current status |
| Flow Efficiency | % items in active states |
| Testing Queue | Items waiting for SIT |

---

## 🔧 Troubleshooting

### "No active sprint found"
- ✅ Check your board_id is correct
- ✅ Ensure there's an active sprint on the board
- ✅ Or specify sprint_id in config

### "401 Unauthorized"
- ✅ Check username and password
- ✅ Ensure auth_method is "basic"
- ✅ Your account may be locked - try logging into Jira web

### "Certificate verify failed"
- ✅ Set `"verify_ssl": false` in config

### "'board_id' error"
- ✅ Make sure teams array has board_id for each team
- ✅ Check default_team matches a team name

### Flask dashboard shows error
- ✅ Check the terminal for full error traceback
- ✅ Ensure config.json is valid JSON

---

## 📁 Project Structure

```
SprintHealth/
├── config/
│   ├── config.example.json    # Template configuration
│   ├── config.json            # Your config (gitignored)
│   └── team_capacity.json     # Capacity settings per team (NEW)
├── data/
│   └── sprint_snapshots/      # Day 1 baselines (NEW)
├── reports/                   # Generated HTML reports
├── src/
│   ├── main.py                # CLI commands
│   ├── jira_client.py         # Jira API integration
│   ├── analyzer.py            # Sprint health analysis
│   ├── ml_predictor.py        # ML predictions (Monte Carlo)
│   ├── charts.py              # Chart generation
│   ├── exporter.py            # HTML report export
│   ├── goal_predictor.py      # Sprint goal prominence (NEW)
│   ├── scope_tracker.py       # Scope creep detection (NEW)
│   ├── capacity_tracker.py    # Capacity intelligence (NEW)
│   ├── coaching_engine.py     # Coaching & improvement (NEW)
│   ├── flow_efficiency.py     # Flow efficiency analytics (NEW)
│   ├── sle_diagnostics.py     # SLE-based aging WIP (NEW)
│   ├── sentiment_clustering.py # AI sentiment analysis (NEW)
│   ├── quality_guardrails.py  # Quality & tech debt (NEW)
│   ├── rte_portfolio.py       # RTE portfolio view (NEW)
│   └── strategic_insights.py  # Strategic metrics (NEW)
├── templates/                 # Dashboard templates
│   ├── dashboard.html         # Main dashboard
│   ├── all_teams.html         # All teams view
│   ├── diagnostics.html       # Advanced diagnostics (NEW)
│   ├── rte_portfolio.html     # RTE portfolio view (NEW)
│   └── team_diagnostic.html   # Team diagnostic view (NEW)
├── static/                    # CSS styles
├── server.py                  # Web dashboard
├── run_daily_report.bat       # Daily report script
└── requirements.txt           # Python dependencies
```

---

## 📝 License

MIT License - Created by Sajan Banka

---

## 👤 Author

**Sajan Banka**

- GitHub: [@sajanbanka](https://github.com/sajanbanka)
