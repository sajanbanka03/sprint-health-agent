# Changelog

All notable changes to Sprint Health Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-05-07

### 🎯 AI Transformation Release

This release transforms Sprint Health from a "data visualization layer" to an "AI Coach" that predicts outcomes, detects risks, and provides coaching recommendations.

### Added

#### Phase 1: Sprint Goal Prominence
- Giant probability display at top of dashboard (5rem font)
- Velocity gap analysis (current vs required SP/day)
- Commitment comparison vs team historical average
- At-risk item identification with risk scores
- Confidence intervals display (50%, 75%, 90%)

#### Phase 2: Scope Creep Detection
- Automatic Day 1 baseline capture
- Track items added/removed after sprint start
- Net scope change percentage
- Impact on goal probability calculation
- Sprint start timing indicator (on time / late)
- Reset baseline functionality

#### Phase 3: Capacity Intelligence
- Per-person capacity tracking (default: 8 SP/sprint)
- Utilization analysis with visual progress bars
- Load status: Available / Optimal / Full / Overloaded
- Unassigned items tracking
- AI suggestions for work redistribution
- Configurable capacity per team member

#### Phase 4: Advanced Diagnostics (Modules 1-4)
- **Module 1: SLE-Based Stuck Diagnostics**
  - Work Item Age calculation
  - 85th percentile Service Level Expectation
  - Aging WIP visualization (Amber at 50%, Red at 85%)
  
- **Module 2: Flow Efficiency Analytics**
  - Active vs Passive status time tracking
  - Flow Efficiency formula: (Active Time / Total Time) × 100
  - Wait vs Work ratio chart
  - RTE alert when efficiency < 20%
  - Bottleneck detection with recommendations

- **Module 3: AI Sentiment & Blocker Clustering**
  - NLP-based comment sentiment analysis
  - Burnout risk detection from frustrated comments
  - Blocker categorization (9 root cause types)
  - Pareto chart of blocker root causes

- **Module 4: Quality & Technical Debt Guardrails**
  - Defect Leakage Rate (SIT/UAT vs Production)
  - SQALE Technical Debt Ratio
  - PM alert when TDR > 5%
  - Quality score with A-F grading

#### Phase 5: Coaching & Improvement
- Team Health Score (0-100 with letter grades)
- Component scores: Velocity, Quality, Process, Predictability
- Sprint-over-sprint comparisons with trends
- Strength identification
- Improvement area detection
- Priority-ranked AI coaching tips
- Failure pattern recognition
- Executive summary generation

#### RTE Portfolio & Team Views
- `/rte/portfolio` - Cross-team program predictability
- `/rte/team/<name>` - Team diagnostic deep-dive
- `/diagnostics` - All 4 modules in one dashboard
- Team rankings and comparisons
- Executive alerts and action items

### Changed
- Dashboard redesigned with hero section for goal probability
- Navigation enhanced with new view links
- Scope Health section now prominent on main dashboard
- Capacity section added below ML predictions

### Fixed
- Sprint timing logic: Sprints not started now show "Not Started Yet"
- Fixed sprint_started_on_time to be Optional[bool]
- Historical data banner shows correctly for ended sprints

### API Endpoints Added

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/goal` | GET | Sprint goal prediction |
| `/api/scope` | GET | Scope creep analysis |
| `/api/scope/reset` | POST | Reset scope baseline |
| `/api/capacity` | GET | Team capacity analysis |
| `/api/capacity/set` | POST | Set member capacity |
| `/api/coaching` | GET | Coaching recommendations |
| `/api/diagnostics/aging` | GET | SLE-based aging WIP |
| `/api/diagnostics/flow` | GET | Flow efficiency |
| `/api/diagnostics/sentiment` | GET | Sentiment analysis |
| `/api/diagnostics/quality` | GET | Quality guardrails |
| `/api/rte/portfolio` | GET | RTE portfolio data |
| `/api/rte/team/<name>` | GET | Team diagnostic data |

---

## [1.0.0] - 2026-04-15

### Added
- Initial release
- Sprint progress tracking (Story Points + Item Count)
- Monte Carlo simulation for completion probability
- Burnup and Burndown charts
- Stuck item detection
- Risk assessment with ML scoring
- MS Teams/Slack notifications
- Web dashboard with Flask
- CLI commands for report generation
- Multi-team support
- HTML report export
- Custom metrics (Bug Ratio, Flow Efficiency, etc.)
- Strategic Insights page with 5 metrics:
  - Flow Efficiency
  - Cycle Time Deviation
  - WIP Stress
  - Innovation Rate
  - PPM (Planned vs Delivered)
- All Teams overview page
- Smart caching with TTL
- Download reports button
- Historical data banner

---

## Version History

| Version | Date | Codename | Description |
|---------|------|----------|-------------|
| 2.0.0 | 2026-05-07 | "AI Coach" | AI transformation with predictive intelligence |
| 1.0.0 | 2026-04-15 | "Observer" | Initial release with data visualization |

---

**Author:** Sajan Banka

