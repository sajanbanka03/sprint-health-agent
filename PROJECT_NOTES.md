# Sprint Health Dashboard - Project Notes & Chat History

**Author:** Sajan Banka  
**Last Updated:** April 17, 2026
**Purpose:** This file preserves context for AI assistants to continue development across chat sessions.

---

##  Project Overview

Sprint Health Dashboard is a Flask-based web application that provides real-time sprint health monitoring for Agile teams. It connects to Jira, fetches sprint data, and provides insights, predictions, and recommendations for Scrum Masters and Agile Delivery Leads.

---

## ✅ Features Implemented

### Core Features
- [x] Jira integration with basic auth (username/password)
- [x] Multi-team support (configured in config.json)
- [x] Single team dashboard view (`/`)
- [x] All teams dashboard view (`/all`)
- [x] Team dropdown selector
- [x] Smart caching (in-memory with TTL for current sprint, file-based for historical)
- [x] Force refresh button
- [x] Download reports (single team & all teams)

### Analytics & Metrics
- [x] Sprint health status (Healthy/At Risk/Critical)
- [x] Stuck items detection (configurable thresholds per phase)
- [x] Phase distribution breakdown
- [x] Velocity tracking (SP/day)
- [x] ML-powered Monte Carlo predictions
- [x] Burnup/Burndown charts
- [x] Risk assessment
- [x] Recommendations engine

### UI/UX
- [x] Loading spinner during navigation
- [x] Download button without showing loader (fixed)
- [x] Historical data banner (shows when viewing ended sprint)
- [x] Cache indicator (From Cache / Fresh Data)
- [x] Footer with author credit ("By Sajan Banka")
- [x] Copyright in code files

### Export
- [x] HTML report export (single team)
- [x] HTML report export (all teams)
- [x] Batch export scripts (.bat files)

---

##  In Progress

### Custom Metric Builder (Phase 1 - Template-Based)
User-requested feature to allow custom metric generation.

**Status:** ✅ IMPLEMENTED (April 17, 2026)

**What's Done:**
- Created `src/metric_builder.py` - Template-based metric engine
- 17 pre-built metric templates across 5 categories
- API endpoints: `/api/metrics/templates`, `/api/metrics/build`, `/api/metrics/quick/<template_id>`
- UI page: `/metrics` - Interactive metric builder with parameter forms
- Added "Custom Metrics" button to main dashboard

**Templates Available:**
- Team: Items by Assignee, Workload by Assignee, Completion by Assignee
- Risk: Unassigned Items, Stuck Items, High Priority Incomplete, Zero Point Items
- Progress: Items in Phase, Phase Distribution, Completed Items
- Analysis: Items by Type, Bugs in Sprint, Bugs vs Stories, Items by Priority
- Activity: Recently Updated, Stale Items

**Next Phase:**
- Phase 2: Smart suggestions
- Phase 3: Natural language (AI-powered)

---

##  Pending Features (Ideas Discussed)

### High Priority
1. **Custom Metric Builder** - Let users create their own metrics
2. **Scope Creep Tracker** - Items added/removed after sprint start
3. **Team Load Balancing** - Workload distribution across team members
4. **Rework/Bounce-back Detection** - Items that moved backward
5. **Risk Flags/Early Warnings** - Proactive alerts

### Medium Priority
6. **Flow Efficiency / Cycle Time** - Active time vs wait time
7. **Time in Phase Heatmap** - Visual bottleneck identification
8. **Sprint Comparison** - Historical sprint comparison
9. **Issue Type Analytics** - Breakdown by Story/Bug/Task

### Future Ideas
10. **"What If" Scenario Planner** - Scope negotiation tool
11. **Sprint Goal Alignment Tracker** - Track goal-related items
12. **Natural Language Metric Generator** - AI-powered queries

---

##  Technical Notes

### File Structure
```
SprintHealth/
├── server.py              # Flask web server
├── config/
│   └── config.json        # Configuration (teams, Jira creds)
├── src/
│   ├── jira_client.py     # Jira API client
│   ├── analyzer.py        # Sprint analysis engine
│   ├── models.py          # Data models
│   ├── cache.py           # Smart caching
│   ├── ml_predictor.py    # Monte Carlo predictions
│   ├── charts.py          # Chart generation
│   ├── custom_metrics.py  # Custom metrics engine
│   ├── exporter.py        # HTML report export
│   └── utils.py           # Utilities
├── templates/
│   ├── dashboard.html     # Single team view
│   ├── dashboard_all.html # All teams view
│   └── error.html         # Error page
├── static/
│   └── styles.css         # CSS styles
├── backups/               # Backup files
├── reports/               # Generated reports
└── data/
    └── cache/             # Cache files
```

### Key Configuration (config/config.json)
```json
{
  "jira": {
    "url": "https://jiraagile.emirates.com",
    "auth_method": "basic",
    "username": "...",
    "password": "...",
    "verify_ssl": false
  },
  "teams": [
    {"name": "Team Thunder", "board_id": 25399, "sprint_id": 62688},
    {"name": "Team Striker", "board_id": 25456}
  ],
  "default_team": "Team Thunder"
}
```

### Important Notes
- Sprint ID is optional - if not provided, fetches active sprint automatically
- `verify_ssl: false` needed for corporate intranet
- Debug mode removed from Flask for cleaner output
- Always create backups before modifying files

---

##  Issues Fixed

1. **Loader showing after download** - Added `isDownloading` flag to prevent beforeunload from showing loader
2. **Missing jira package** - Added to requirements.txt
3. **Debug mode output** - Removed `debug=True` from Flask
4. **Extra blank lines in code** - Cleaned up jira_client.py
5. **Unused imports** - Removed from server.py

---

##  Key Decisions Made

1. **Authentication:** Using basic auth (username/password) instead of API tokens for corporate Jira
2. **Caching Strategy:** 10-minute TTL for current sprint, permanent for historical data
3. **No sprint_id:** Auto-fetches current active sprint if not specified
4. **Team selector:** Dropdown in header + /all endpoint for multi-team view
5. **Historical banner:** Shows when viewing ended/closed sprint

---

##  Next Steps (For Next Chat Session)

1. **Complete Custom Metric Builder (Phase 1)**
   - Create metric templates
   - Add UI components
   - Implement backend logic

2. **Consider implementing:**
   - Scope Creep Tracker
   - Team Load Balancing view
   - Risk Flags dashboard section

3. **Performance:**
   - Parallel team fetching for /all endpoint

---

##  Commands Reference

```bash
# Run the server
python server.py

# Install dependencies
pip install -r requirements.txt

# List all boards for a project
python list_boards.py
```

---

##  Security Note

The config.json contains credentials. Never commit to Git. Use config.example.json as template.

---

*This file should be read at the start of each new chat session to maintain context.*

