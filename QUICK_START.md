# Sprint Health Agent - Quick Start Guide

Get up and running in 5 minutes!

---

## Step 1: Install Dependencies

```cmd
cd SprintHealth
pip install -r requirements.txt
```

## Step 2: Configure Jira Connection

```cmd
copy config\config.example.json config\config.json
```

Edit `config\config.json` with your details:

```json
{
    "jira": {
        "url": "https://jiraagile.emirates.com",
        "auth_method": "basic",
        "username": "YOUR_EMPLOYEE_ID",
        "password": "YOUR_PASSWORD",
        "project_key": "RESMYB",
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

### Finding Your Board ID

**Option 1: From Jira URL**
1. Open your Jira board
2. Look at the URL: `https://jiraagile.emirates.com/.../boards/25399`
3. The number (25399) is your Board ID

**Option 2: Use the CLI**
```cmd
python -m src.main list-boards --project RESMYB
```
This shows all boards for your project!

## Step 3: Test the Connection

```cmd
python -m src.main test-connection
```

You should see:
```
✓ Connected as Your Name (your.email@emirates.com)
✓ Active sprint found: Sprint 47
```

## Step 4: Generate Your First Report

```cmd
python -m src.main export-html
```

This generates a beautiful HTML report and opens it in your browser!

## Step 5: Start Web Dashboard (Optional)

```cmd
python server.py
```

Open http://localhost:5000 in your browser for a live dashboard.

---

## Quick Commands

| Command | What it does |
|---------|--------------|
| `python -m src.main test-connection` | Test Jira connection |
| `python -m src.main list-boards -p RESMYB` | List all boards for project |
| `python -m src.main export-html` | Generate HTML report |
| `python -m src.main export-html -t "Team Striker"` | Report for specific team |
| `python -m src.main export-all` | Reports for all teams |
| `python server.py` | Start web dashboard |
| `python -m src.main demo` | Demo with sample data |

---

## Troubleshooting

### "401 Unauthorized"
- Check your username (employee ID) and password
- Make sure `auth_method` is set to `"basic"`

### "No active sprint found"
- Verify your board_id is correct
- Use `list-boards` command to find the right board
- Or set a specific `sprint_id` in the team config

### "Certificate verify failed"
- Set `"verify_ssl": false` in your config

### "'board_id' error"
- Each team in the `teams` array needs a `board_id`
- Use `list-boards` command to find board IDs

---

## Next Steps

- Check the full [README.md](README.md) for advanced configuration
- Set up notifications to MS Teams or Slack
- Schedule daily reports with `python -m src.main schedule`
