# Sprint Health AI Transformation Roadmap

**Author:** Sajan Banka  
**Created:** April 30, 2026  
**Purpose:** Transform Sprint Health from "Data Dashboard" to "AI Coach"

---

## 📋 Executive Summary

**Manager's Feedback:** "All these details are available in Jira. What is special that AI is doing?"

**Our Response:** Transform the dashboard to PREDICT outcomes, DETECT risks early, and COACH teams on improvement - not just display data.

---

## 🎯 Implementation Priority (User Confirmed)

| Priority | Phase | Feature | Status |
|----------|-------|---------|--------|
| 1st | Phase 2 | Scope Creep Detection | ✅ Complete |
| 2nd | Phase 3 | Capacity Intelligence | ✅ Complete |
| 3rd | Phase 1 | Sprint Goal Prominence | ✅ Complete |
| 4th | Phase 5 | Coaching & Improvement | ✅ Complete |
| 5th | Phase 4 | All Teams Enhancement | ⏳ Pending |

---

## 📐 Design Decisions (User Confirmed)

| Decision | Choice |
|----------|--------|
| Dashboard Strategy | Keep Strategic Insights separate, make main dashboard more predictive |
| Historical Comparison | Last 5 sprint trends |
| Scope Baseline Capture | Day 1 of sprint (automatic) |
| Capacity Calculation | Average SP completed per sprint (manual edit later) |
| Cross-Team Features | All (PI tracking, dependencies, resource conflicts) |
| Additional Feature | Sprint start timing indicator (started late/on time) |

---

## 🚀 Phase 2: Scope Creep Detection (PRIORITY 1)

### Features
1. **Sprint Snapshot on Day 1**
   - Capture original committed items at sprint start
   - Store: issue keys, SP, assignees
   - Detect when sprint actually started vs. planned start date

2. **Scope Change Tracker**
   - Items Added after Day 1: count, SP, who added
   - Items Removed after Day 1: count, SP
   - Net scope change percentage

3. **Impact on Sprint Goal**
   - Recalculate Monte Carlo with new scope
   - Show: "Scope increased 15% → Goal probability dropped from 85% to 68%"

4. **Sprint Start Indicator**
   - "Sprint started on time" ✅
   - "Sprint started 2 days late" ⚠️

### Files to Create/Modify
- `src/scope_tracker.py` (NEW) - Scope tracking engine
- `src/analyzer.py` - Integrate scope metrics
- `server.py` - API endpoints for scope data
- `templates/dashboard.html` - UI for scope creep display
- `data/sprint_snapshots/` (NEW) - Store Day 1 snapshots

### UI Mockup
```
┌─────────────────────────────────────────────────────────────┐
│ 📊 SCOPE HEALTH                            Sprint Day 5/10  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Original: 42 SP (18 items)    Current: 48 SP (21 items) │ │
│ │ ▲ +6 SP (+14%) scope increase                           │ │
│ │                                                         │ │
│ │ Added:   +3 items (DEM-501, DEM-502, DEM-503) = +8 SP   │ │
│ │ Removed: -1 item (DEM-400 descoped)           = -2 SP   │ │
│ │                                                         │ │
│ │ ⚠️ Impact: Goal probability ↓ 82% → 71%                 │ │
│ └─────────────────────────────────────────────────────────┘ │
│ Sprint started: On Time ✅ (April 28, 2026)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧠 Phase 3: Capacity Intelligence (PRIORITY 2)

### Features
1. **Individual Historical Capacity**
   - Calculate avg SP completed per person per sprint (last 5 sprints)
   - Store in config with manual override option

2. **Current Load Analysis**
   - SP assigned vs. capacity
   - Utilization percentage per person

3. **Capacity Alerts**
   - Overloaded: >100% capacity
   - Underutilized: <50% capacity
   - Available capacity for team

4. **Optimal Assignment Suggestion**
   - "Consider assigning DEM-789 to Sajan (has 5 SP capacity remaining)"

### Files to Create/Modify
- `src/capacity_tracker.py` (NEW) - Capacity intelligence
- `config/team_capacity.json` (NEW) - Per-person capacity data
- `templates/dashboard.html` - Capacity UI section

### UI Mockup
```
┌─────────────────────────────────────────────────────────────┐
│ 👥 TEAM CAPACITY                                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Member        │ Capacity │ Assigned │ Load   │ Status   │ │
│ │ ─────────────────────────────────────────────────────── │ │
│ │ Sajan Banka   │   8 SP   │   6 SP   │  75%   │ ✅ Good  │ │
│ │ Rahul Sharma  │  10 SP   │  10 SP   │ 100%   │ ⚠️ Full  │ │
│ │ Ankita Apte   │   8 SP   │  11 SP   │ 138%   │ 🔴 Over  │ │
│ │ Unassigned    │    -     │   4 SP   │   -    │ ❓       │ │
│ │ ─────────────────────────────────────────────────────── │ │
│ │ Team Total    │  26 SP   │  31 SP   │ 119%   │ ⚠️ Over  │ │
│ └─────────────────────────────────────────────────────────┘ │
│ 💡 Suggestion: Ankita overloaded - consider reassigning     │
│    DEM-456 (3 SP) to Sajan (has 2 SP available)            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Phase 1: Sprint Goal Prominence (PRIORITY 3)

### Features
1. **Hero Section Redesign**
   - Giant Sprint Goal Probability at top
   - "78% likely to achieve sprint goal"
   - Confidence intervals (50%, 75%, 90%)

2. **Trend Comparison**
   - "Committed 45 SP vs. team avg 38 SP (last 5 sprints)"
   - Visual indicator if over/under committed

3. **Predicted Shortfall**
   - "3 items (8 SP) at risk of not completing"
   - List most likely to miss with confidence %

4. **Velocity Gap**
   - "Need 4.2 SP/day, currently doing 2.8 SP/day"
   - Visual gap indicator

### Files to Modify
- `templates/dashboard.html` - Hero section redesign
- `src/analyzer.py` - Enhanced prediction display

---

## 📈 Phase 5: Coaching & Improvement (PRIORITY 4)

### Features
1. **Sprint-over-Sprint Comparison**
   - Key metrics vs. previous sprint
   - Visual trend arrows

2. **Improvement Patterns**
   - "Velocity improved 12% over last 5 sprints"
   - "Stuck rate decreased 8%"

3. **Common Failure Pattern Detection**
   - ML-detected recurring issues
   - "Items in Ready for SIT consistently get stuck"

4. **Team Health Score**
   - Composite 0-100 score
   - Gamification for improvement

5. **Actionable Coaching Tips**
   - Specific suggestions based on patterns
   - "Consider pair testing to reduce SIT bottleneck"

---

## 🌐 Phase 4: All Teams Enhancement (PRIORITY 5)

### Features
1. **Program Goal Alignment**
   - All teams' contribution to PI objectives
   - Program-level success probability

2. **Cross-Team Common Blockers**
   - AI-detected shared issues
   - "Environment issues affecting Thunder, Striker"

3. **Resource Conflict Detection**
   - Same person overloaded across teams
   - "Sajan assigned across Thunder & Turbo"

4. **Cross-Team Velocity Comparison**
   - Normalized trends
   - Best practices from high-performing teams

---

## 📁 New File Structure

```
SprintHealth/
├── src/
│   ├── scope_tracker.py          (NEW - Phase 2)
│   ├── capacity_tracker.py       (NEW - Phase 3)
│   ├── coaching_engine.py        (NEW - Phase 5)
│   ├── program_insights.py       (NEW - Phase 4)
│   └── ... existing files ...
├── config/
│   ├── config.json
│   └── team_capacity.json        (NEW - Phase 3)
├── data/
│   ├── cache/
│   └── sprint_snapshots/         (NEW - Phase 2)
│       └── {team}_{sprint_id}_day1.json
└── templates/
    └── dashboard.html            (MODIFIED - All phases)
```

---

## 🔄 Backup Strategy

Before each phase:
1. Create timestamped backup folder
2. Copy all files to be modified
3. Document changes in this roadmap

---

## ✅ Progress Tracking

### Phase 2: Scope Creep Detection
- [x] Create `src/scope_tracker.py`
- [x] Create snapshot storage mechanism
- [x] Integrate with analyzer
- [x] Add API endpoints (`/api/scope`, `/api/scope/capture`, `/api/scope/reset`)
- [x] Update dashboard UI (JavaScript functions)
- [x] Add CSS styles for scope health section
- [x] Add sprint start timing indicator
- [x] Import ScopeTracker in server.py
- [x] **READY FOR TESTING** ✅

### Phase 3: Capacity Intelligence
- [x] Create `src/capacity_tracker.py`
- [x] Create `config/team_capacity.json`
- [x] Calculate capacity per member (default 8 SP, configurable)
- [x] Add capacity API endpoints (`/api/capacity`, `/api/capacity/set`, `/api/capacity/config`)
- [x] Add capacity UI section (dashboard.html)
- [x] Add CSS styles for capacity section
- [x] Add assignment suggestions based on capacity
- [x] Add overload/underutilization detection
- [x] **READY FOR TESTING** ✅

### Phase 1: Sprint Goal Prominence
- [x] Create `src/goal_predictor.py` - Enhanced goal prediction engine
- [x] Add API endpoint `/api/goal` for goal prediction data
- [x] Redesign hero section with giant probability display
- [x] Add velocity gap indicator (current vs required)
- [x] Add commitment comparison (vs historical avg)
- [x] Add at-risk items counter
- [x] Add confidence intervals mini-display
- [x] Add CSS styles for hero section
- [x] **READY FOR TESTING** ✅

### Phase 5: Coaching & Improvement
- [x] Create `src/coaching_engine.py` - Full coaching engine
- [x] Add API endpoint `/api/coaching` for coaching data
- [x] Sprint-over-sprint comparison with trends
- [x] Improvement pattern detection (velocity, completion rate)
- [x] Failure pattern detection (stuck phases, unassigned items)
- [x] Team Health Score (0-100) with grade (A-F)
- [x] Component scores (Velocity, Quality, Process, Predictability)
- [x] AI-generated coaching tips with priorities
- [x] Strengths and areas for improvement
- [x] Add dashboard UI section
- [x] Add CSS styles
- [x] **READY FOR TESTING** ✅

### Phase 4: All Teams Enhancement
- [ ] Program goal rollup
- [ ] Cross-team blocker detection
- [ ] Resource conflict alerts
- [ ] Velocity comparison

---

*Last Updated: April 30, 2026 - Phases 1, 2, 3 & 5 Complete (4 of 5)*











