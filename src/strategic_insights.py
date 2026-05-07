"""
Strategic Insights Module for Sprint Health Agent
Advanced metrics for RTL and Agile Leadership

Provides:
1. Flow Efficiency Score
2. Cycle Time Deviation (Outlier Detection)
3. WIP Stress Index (Burnout Predictor)
4. Innovation Rate vs Maintenance (RTL Insight)
5. Program Predictability Measure (PPM)

Author: Sajan Banka
Created: April 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import statistics

from .models import SprintIssue, SprintInfo, SprintMetrics, Phase

logger = logging.getLogger(__name__)


# =============================================================================
# JQL QUERIES FOR STRATEGIC INSIGHTS
# =============================================================================

class StrategicJQL:
    """JQL queries for pulling strategic data from Jira"""
    
    @staticmethod
    def transition_history(sprint_id: int) -> str:
        """Get issues with full transition history for a sprint"""
        return f"Sprint = {sprint_id} ORDER BY created ASC"
    
    @staticmethod
    def completed_issues_last_n_sprints(project_key: str, num_sprints: int = 5) -> str:
        """Get completed issues from recent sprints for cycle time analysis"""
        return f'project = {project_key} AND status = Done AND resolved >= -90d ORDER BY resolved DESC'
    
    @staticmethod
    def bugs_and_tech_debt(sprint_id: int) -> str:
        """Get bugs and tech debt items in sprint"""
        return f'Sprint = {sprint_id} AND (type = Bug OR labels in (tech-debt, "technical-debt", techdebt))'
    
    @staticmethod
    def new_features(sprint_id: int) -> str:
        """Get new feature stories in sprint"""
        return f'Sprint = {sprint_id} AND type = Story AND labels not in (tech-debt, "technical-debt", techdebt, bug-fix)'
    
    @staticmethod
    def issues_by_assignee(sprint_id: int) -> str:
        """Get all issues grouped by assignee"""
        return f'Sprint = {sprint_id} AND assignee is not EMPTY ORDER BY assignee ASC'


# =============================================================================
# DATA MODELS FOR STRATEGIC INSIGHTS
# =============================================================================

@dataclass
class FlowEfficiencyResult:
    """Result of Flow Efficiency calculation"""
    score: float  # Percentage (0-100)
    total_active_time_days: float
    total_wait_time_days: float
    total_lead_time_days: float
    status: str  # "healthy", "warning", "critical"
    recommendation: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CycleTimeOutlier:
    """An outlier issue detected by cycle time analysis"""
    issue_key: str
    summary: str
    assignee: Optional[str]
    current_age_days: int
    mean_cycle_time: float
    std_deviation: float
    threshold: float  # mean + 1.5 * std
    coaching_question: str


@dataclass
class CycleTimeResult:
    """Result of Cycle Time Deviation analysis"""
    mean_cycle_time: float
    std_deviation: float
    threshold: float
    outliers: List[CycleTimeOutlier]
    total_issues_analyzed: int
    recommendation: str


@dataclass
class WIPStressAssignee:
    """Assignee with high WIP stress"""
    name: str
    wip_count: int
    avg_task_age: float
    oldest_task_age: int
    oldest_task_key: str
    stress_level: str  # "low", "medium", "high", "critical"
    recommendation: str


@dataclass
class WIPStressResult:
    """Result of WIP Stress Index calculation"""
    high_risk_assignees: List[WIPStressAssignee]
    team_avg_wip: float
    team_health: str  # "healthy", "warning", "critical"
    recommendation: str


@dataclass
class InnovationRateResult:
    """Result of Innovation Rate analysis"""
    innovation_sp: float
    maintenance_sp: float
    innovation_percentage: float
    maintenance_percentage: float
    status: str  # "healthy", "warning", "critical"
    trend: str  # "improving", "stable", "declining"
    consecutive_high_maintenance_sprints: int
    recommendation: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PPMResult:
    """Result of Program Predictability Measure"""
    planned_sp: float
    actual_sp: float
    ppm_score: float  # Percentage (0-100+)
    status: str  # "on_track", "at_risk", "off_track"
    pi_forecast: str
    recommendation: str


@dataclass
class StrategicInsightsReport:
    """Complete strategic insights report"""
    generated_at: datetime
    flow_efficiency: FlowEfficiencyResult
    cycle_time: CycleTimeResult
    wip_stress: WIPStressResult
    innovation_rate: InnovationRateResult
    ppm: PPMResult
    executive_summary: str
    priority_actions: List[str]


# =============================================================================
# STRATEGIC INSIGHTS ENGINE
# =============================================================================

class StrategicInsightsEngine:
    """
    Engine for calculating advanced strategic metrics.
    
    Usage:
        engine = StrategicInsightsEngine(config)
        report = engine.generate_report(issues, sprint_info, metrics, historical_data)
    """
    
    # Phase categorization for Flow Efficiency
    ACTIVE_PHASES = [Phase.IN_ANALYSIS, Phase.IN_DEV, Phase.IN_SIT]
    WAIT_PHASES = [Phase.BACKLOG, Phase.READY_FOR_SIT, Phase.IN_TPO_REVIEW]
    
    # Thresholds
    FLOW_EFFICIENCY_WARNING = 20  # Below 20% is warning
    FLOW_EFFICIENCY_CRITICAL = 10  # Below 10% is critical
    
    WIP_THRESHOLD = 2  # More than 2 items per person
    AGE_THRESHOLD = 4  # Tasks older than 4 days
    
    MAINTENANCE_WARNING_THRESHOLD = 30  # 30% maintenance is warning
    MAINTENANCE_CONSECUTIVE_SPRINTS = 2  # 2 sprints triggers recommendation
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the strategic insights engine"""
        self.config = config
        self.thresholds = config.get('strategic_insights', {})
        
        # Allow config overrides
        self.flow_efficiency_warning = self.thresholds.get('flow_efficiency_warning', self.FLOW_EFFICIENCY_WARNING)
        self.wip_threshold = self.thresholds.get('wip_threshold', self.WIP_THRESHOLD)
        self.age_threshold = self.thresholds.get('age_threshold', self.AGE_THRESHOLD)
    
    def generate_report(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        metrics: SprintMetrics,
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> StrategicInsightsReport:
        """
        Generate complete strategic insights report.
        
        Args:
            issues: All issues in current sprint
            sprint_info: Current sprint information
            metrics: Current sprint metrics
            historical_data: Historical sprint data for trend analysis
        """
        historical_data = historical_data or []
        
        # Calculate all metrics
        flow_efficiency = self.calculate_flow_efficiency(issues, sprint_info)
        cycle_time = self.calculate_cycle_time_deviation(issues, historical_data)
        wip_stress = self.calculate_wip_stress_index(issues)
        innovation_rate = self.calculate_innovation_rate(issues, metrics, historical_data)
        ppm = self.calculate_ppm(metrics, sprint_info)
        
        # Generate executive summary and priority actions
        executive_summary = self._generate_executive_summary(
            flow_efficiency, cycle_time, wip_stress, innovation_rate, ppm
        )
        priority_actions = self._generate_priority_actions(
            flow_efficiency, cycle_time, wip_stress, innovation_rate, ppm
        )
        
        return StrategicInsightsReport(
            generated_at=datetime.now(),
            flow_efficiency=flow_efficiency,
            cycle_time=cycle_time,
            wip_stress=wip_stress,
            innovation_rate=innovation_rate,
            ppm=ppm,
            executive_summary=executive_summary,
            priority_actions=priority_actions
        )
    
    # =========================================================================
    # 1. FLOW EFFICIENCY SCORE
    # =========================================================================
    
    def calculate_flow_efficiency(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo
    ) -> FlowEfficiencyResult:
        """
        Calculate Flow Efficiency Score.
        
        Logic: 
        - Active Time = time in Development, Analysis, SIT
        - Wait Time = time in Backlog, Ready for SIT, TPO Review
        - Formula: (Active Time / Total Lead Time) * 100
        
        Args:
            issues: All sprint issues
            sprint_info: Sprint information
        
        Returns:
            FlowEfficiencyResult with score and recommendations
        """
        total_active_time = 0.0
        total_wait_time = 0.0
        phase_time_breakdown = defaultdict(float)
        
        for issue in issues:
            if issue.phase == Phase.DONE:
                continue  # Skip completed items
            
            days = issue.days_in_current_status
            
            if issue.phase in self.ACTIVE_PHASES:
                total_active_time += days
            elif issue.phase in self.WAIT_PHASES:
                total_wait_time += days
            
            phase_time_breakdown[issue.phase.value] += days
        
        total_lead_time = total_active_time + total_wait_time
        
        # Calculate efficiency score
        if total_lead_time > 0:
            score = (total_active_time / total_lead_time) * 100
        else:
            score = 100.0  # No items in progress = 100% efficient
        
        # Determine status
        if score >= self.flow_efficiency_warning:
            status = "healthy"
            recommendation = (
                f"✅ Flow Efficiency is healthy at {score:.1f}%. "
                "Team is spending most time on active work rather than waiting."
            )
        elif score >= self.FLOW_EFFICIENCY_CRITICAL:
            status = "warning"
            recommendation = (
                f"⚠️ Flow Efficiency Warning: {score:.1f}% (below {self.flow_efficiency_warning}%). "
                f"Wait time ({total_wait_time:.1f} days) is high relative to active time ({total_active_time:.1f} days). "
                "Consider: Review handoff processes, check for environment/dependency blockers."
            )
        else:
            status = "critical"
            recommendation = (
                f" CRITICAL: Flow Efficiency at {score:.1f}%. "
                "Systemic bottleneck detected - items spending excessive time waiting. "
                "Immediate action: Identify and resolve environment blockers, consider WIP limits."
            )
        
        return FlowEfficiencyResult(
            score=round(score, 1),
            total_active_time_days=round(total_active_time, 1),
            total_wait_time_days=round(total_wait_time, 1),
            total_lead_time_days=round(total_lead_time, 1),
            status=status,
            recommendation=recommendation,
            details={
                'phase_breakdown': dict(phase_time_breakdown),
                'active_phases': [p.value for p in self.ACTIVE_PHASES],
                'wait_phases': [p.value for p in self.WAIT_PHASES]
            }
        )
    
    # =========================================================================
    # 2. CYCLE TIME DEVIATION (OUTLIER DETECTION)
    # =========================================================================
    
    def calculate_cycle_time_deviation(
        self,
        current_issues: List[SprintIssue],
        historical_data: List[Dict[str, Any]]
    ) -> CycleTimeResult:
        """
        Calculate Cycle Time Deviation and detect outliers.
        
        Logic:
        - Calculate mean and std deviation from historical data
        - Flag items where Age > (Mean + 1.5 * StdDev)
        
        Args:
            current_issues: Current sprint issues
            historical_data: Historical sprint velocity/cycle time data
        
        Returns:
            CycleTimeResult with outliers and recommendations
        """
        # Calculate historical cycle times
        historical_cycle_times = []
        
        # Extract cycle times from historical data
        for sprint_data in historical_data:
            if 'avg_cycle_time' in sprint_data:
                historical_cycle_times.append(sprint_data['avg_cycle_time'])
            elif 'completed_points' in sprint_data:
                # Estimate: assume 2-3 days per story point as proxy
                historical_cycle_times.append(3.0)  # Default estimate
        
        # If no historical data, use sensible defaults
        if not historical_cycle_times:
            historical_cycle_times = [3.0, 4.0, 3.5, 4.5, 3.0]  # Default ~3-4 days
        
        # Calculate statistics
        mean_cycle_time = statistics.mean(historical_cycle_times)
        std_deviation = statistics.stdev(historical_cycle_times) if len(historical_cycle_times) > 1 else 1.0
        threshold = mean_cycle_time + (1.5 * std_deviation)
        
        # Find outliers in current sprint
        outliers = []
        in_progress_issues = [i for i in current_issues if i.phase not in [Phase.DONE, Phase.BACKLOG]]
        
        for issue in in_progress_issues:
            if issue.days_in_current_status > threshold:
                coaching_question = self._generate_coaching_question(issue, mean_cycle_time, threshold)
                
                outliers.append(CycleTimeOutlier(
                    issue_key=issue.key,
                    summary=issue.summary,
                    assignee=issue.assignee,
                    current_age_days=issue.days_in_current_status,
                    mean_cycle_time=round(mean_cycle_time, 1),
                    std_deviation=round(std_deviation, 1),
                    threshold=round(threshold, 1),
                    coaching_question=coaching_question
                ))
        
        # Sort by age (most overdue first)
        outliers.sort(key=lambda x: x.current_age_days, reverse=True)
        
        # Generate recommendation
        if not outliers:
            recommendation = (
                f"✅ No cycle time outliers detected. "
                f"All items within expected range (threshold: {threshold:.1f} days)."
            )
        else:
            recommendation = (
                f"⚠️ {len(outliers)} item(s) exceeding cycle time threshold ({threshold:.1f} days). "
                "Review these items for: hidden complexity, blocked dependencies, or scope creep. "
                "Consider breaking down large items or pairing on complex work."
            )
        
        return CycleTimeResult(
            mean_cycle_time=round(mean_cycle_time, 1),
            std_deviation=round(std_deviation, 1),
            threshold=round(threshold, 1),
            outliers=outliers,
            total_issues_analyzed=len(in_progress_issues),
            recommendation=recommendation
        )
    
    def _generate_coaching_question(
        self,
        issue: SprintIssue,
        mean_cycle_time: float,
        threshold: float
    ) -> str:
        """Generate a coaching question for an outlier"""
        days_over = issue.days_in_current_status - threshold
        
        questions = [
            f"'{issue.key}' has been in progress for {issue.days_in_current_status} days "
            f"(expected: {mean_cycle_time:.0f} days). Is this story too large? Consider breaking it down.",
            
            f"This item is {days_over:.0f} days over the typical cycle time. "
            "Is there hidden technical debt blocking progress?",
            
            f"'{issue.key}' is an outlier. Has the acceptance criteria changed mid-sprint? "
            "Consider: scope creep, missing requirements, or external dependencies."
        ]
        
        # Select based on age severity
        if days_over > 5:
            return questions[0]  # Focus on splitting
        elif days_over > 3:
            return questions[1]  # Tech debt question
        else:
            return questions[2]  # Requirements question
    
    # =========================================================================
    # 3. WIP STRESS INDEX (BURNOUT PREDICTOR)
    # =========================================================================
    
    def calculate_wip_stress_index(
        self,
        issues: List[SprintIssue]
    ) -> WIPStressResult:
        """
        Calculate WIP Stress Index per assignee.
        
        Logic:
        - Count open items per developer (WIP)
        - Check average age of their tasks
        - Flag if WIP > 2 AND age > 4 days
        
        Args:
            issues: All sprint issues
        
        Returns:
            WIPStressResult with high-risk assignees
        """
        # Group issues by assignee
        assignee_issues: Dict[str, List[SprintIssue]] = defaultdict(list)
        
        for issue in issues:
            if issue.phase not in [Phase.DONE, Phase.BACKLOG]:
                assignee = issue.assignee or "Unassigned"
                assignee_issues[assignee].append(issue)
        
        high_risk_assignees = []
        all_wip_counts = []
        
        for assignee, assigned_issues in assignee_issues.items():
            if assignee == "Unassigned":
                continue
            
            wip_count = len(assigned_issues)
            all_wip_counts.append(wip_count)
            
            ages = [i.days_in_current_status for i in assigned_issues]
            avg_age = statistics.mean(ages) if ages else 0
            max_age = max(ages) if ages else 0
            oldest_task = max(assigned_issues, key=lambda x: x.days_in_current_status) if assigned_issues else None
            
            # Determine stress level
            if wip_count > self.wip_threshold and avg_age > self.age_threshold:
                stress_level = "critical" if wip_count > 3 or avg_age > 6 else "high"
                recommendation = (
                    f" {assignee} has {wip_count} items in progress with avg age {avg_age:.1f} days. "
                    "HIGH BURNOUT RISK. Consider: reassigning work, pairing, or extending timelines."
                )
            elif wip_count > self.wip_threshold:
                stress_level = "medium"
                recommendation = (
                    f"⚠️ {assignee} has {wip_count} items (above WIP limit). "
                    "Monitor for context-switching overhead."
                )
            elif avg_age > self.age_threshold:
                stress_level = "medium"
                recommendation = (
                    f"⚠️ {assignee}'s tasks averaging {avg_age:.1f} days. "
                    "Check for blockers or need for assistance."
                )
            else:
                stress_level = "low"
                recommendation = f"✅ {assignee} workload appears balanced."
            
            if stress_level in ["high", "critical"]:
                high_risk_assignees.append(WIPStressAssignee(
                    name=assignee,
                    wip_count=wip_count,
                    avg_task_age=round(avg_age, 1),
                    oldest_task_age=max_age,
                    oldest_task_key=oldest_task.key if oldest_task else "",
                    stress_level=stress_level,
                    recommendation=recommendation
                ))
        
        # Calculate team health
        team_avg_wip = statistics.mean(all_wip_counts) if all_wip_counts else 0
        
        if len(high_risk_assignees) == 0:
            team_health = "healthy"
            team_recommendation = (
                "✅ Team workload is balanced. No burnout risks detected."
            )
        elif len(high_risk_assignees) <= 2:
            team_health = "warning"
            team_recommendation = (
                f"⚠️ {len(high_risk_assignees)} team member(s) showing high stress indicators. "
                "Consider workload rebalancing in next standup."
            )
        else:
            team_health = "critical"
            team_recommendation = (
                f" CRITICAL: {len(high_risk_assignees)} team members at burnout risk. "
                "Immediate intervention needed - review sprint commitment and consider scope reduction."
            )
        
        return WIPStressResult(
            high_risk_assignees=high_risk_assignees,
            team_avg_wip=round(team_avg_wip, 1),
            team_health=team_health,
            recommendation=team_recommendation
        )
    
    # =========================================================================
    # 4. INNOVATION RATE VS MAINTENANCE (RTL INSIGHT)
    # =========================================================================
    
    def calculate_innovation_rate(
        self,
        issues: List[SprintIssue],
        metrics: SprintMetrics,
        historical_data: List[Dict[str, Any]]
    ) -> InnovationRateResult:
        """
        Calculate Innovation vs Maintenance ratio.
        
        Logic:
        - Innovation = Story points for new features
        - Maintenance = Story points for Bugs + Tech Debt
        - Flag if Maintenance > 30% for 2+ sprints
        
        Args:
            issues: All sprint issues
            metrics: Sprint metrics
            historical_data: Historical sprint data
        
        Returns:
            InnovationRateResult with RTL recommendations
        """
        # Categorize issues
        innovation_sp = 0.0
        maintenance_sp = 0.0
        innovation_items = []
        maintenance_items = []
        
        maintenance_labels = ['tech-debt', 'technical-debt', 'techdebt', 'bug-fix', 'maintenance', 'defect']
        
        for issue in issues:
            is_maintenance = (
                issue.issue_type.lower() == 'bug' or
                any(label.lower() in maintenance_labels for label in issue.labels)
            )
            
            if is_maintenance:
                maintenance_sp += issue.story_points
                maintenance_items.append(issue.key)
            else:
                innovation_sp += issue.story_points
                innovation_items.append(issue.key)
        
        total_sp = innovation_sp + maintenance_sp
        
        if total_sp > 0:
            innovation_pct = (innovation_sp / total_sp) * 100
            maintenance_pct = (maintenance_sp / total_sp) * 100
        else:
            innovation_pct = 100.0
            maintenance_pct = 0.0
        
        # Check historical trend
        consecutive_high_maintenance = 0
        for sprint_data in historical_data:
            historical_maintenance = sprint_data.get('maintenance_percentage', 0)
            if historical_maintenance > self.MAINTENANCE_WARNING_THRESHOLD:
                consecutive_high_maintenance += 1
            else:
                break  # Reset if a good sprint breaks the streak
        
        # Include current sprint in count if applicable
        if maintenance_pct > self.MAINTENANCE_WARNING_THRESHOLD:
            consecutive_high_maintenance += 1
        
        # Determine status and trend
        if maintenance_pct <= self.MAINTENANCE_WARNING_THRESHOLD:
            status = "healthy"
            trend = "stable"
            recommendation = (
                f"✅ Innovation Rate is healthy at {innovation_pct:.0f}%. "
                f"Maintenance work ({maintenance_pct:.0f}%) is under control."
            )
        elif consecutive_high_maintenance >= self.MAINTENANCE_CONSECUTIVE_SPRINTS:
            status = "critical"
            trend = "declining"
            recommendation = (
                f" RTL ALERT: Maintenance has exceeded {self.MAINTENANCE_WARNING_THRESHOLD}% "
                f"for {consecutive_high_maintenance} consecutive sprints. "
                "Current: {maintenance_pct:.0f}% maintenance, {innovation_pct:.0f}% innovation. "
                "RECOMMENDATION: Schedule a 'Quality Focus' session with the team. "
                "Consider: dedicated tech debt sprint, refactoring time-box, or architecture review."
            )
        else:
            status = "warning"
            trend = "declining"
            recommendation = (
                f"⚠️ Maintenance ({maintenance_pct:.0f}%) exceeds target ({self.MAINTENANCE_WARNING_THRESHOLD}%). "
                f"Innovation at {innovation_pct:.0f}%. Monitor trend - if this continues, "
                "schedule quality improvement initiative."
            )
        
        return InnovationRateResult(
            innovation_sp=innovation_sp,
            maintenance_sp=maintenance_sp,
            innovation_percentage=round(innovation_pct, 1),
            maintenance_percentage=round(maintenance_pct, 1),
            status=status,
            trend=trend,
            consecutive_high_maintenance_sprints=consecutive_high_maintenance,
            recommendation=recommendation,
            details={
                'innovation_items': innovation_items,
                'maintenance_items': maintenance_items,
                'threshold': self.MAINTENANCE_WARNING_THRESHOLD
            }
        )
    
    # =========================================================================
    # 5. PROGRAM PREDICTABILITY MEASURE (PPM)
    # =========================================================================
    
    def calculate_ppm(
        self,
        metrics: SprintMetrics,
        sprint_info: SprintInfo
    ) -> PPMResult:
        """
        Calculate Program Predictability Measure.
        
        Formula: (Actual Completed SP / Planned SP) * 100
        
        Args:
            metrics: Sprint metrics with planned vs actual
            sprint_info: Sprint information
        
        Returns:
            PPMResult with PI forecast
        """
        planned_sp = metrics.total_story_points
        actual_sp = metrics.completed_story_points
        
        if planned_sp > 0:
            ppm_score = (actual_sp / planned_sp) * 100
        else:
            ppm_score = 100.0
        
        # Calculate progress-adjusted PPM (account for sprint progress)
        sprint_progress = sprint_info.progress_percentage / 100  # 0 to 1
        expected_completion = planned_sp * sprint_progress
        
        if expected_completion > 0:
            pace_ratio = actual_sp / expected_completion
        else:
            pace_ratio = 1.0
        
        # Determine status
        if ppm_score >= 90 or pace_ratio >= 0.95:
            status = "on_track"
            pi_forecast = (
                f"PI on track. Current pace: {ppm_score:.0f}% of sprint commitment completed. "
                f"Projected to complete {min(100, ppm_score / max(sprint_progress, 0.1)):.0f}% by sprint end."
            )
            recommendation = (
                f"✅ Sprint predictability is strong at {ppm_score:.0f}% completion. "
                "Team is delivering as committed."
            )
        elif ppm_score >= 70 or pace_ratio >= 0.7:
            status = "at_risk"
            remaining_sp = planned_sp - actual_sp
            pi_forecast = (
                f"PI AT RISK. {remaining_sp:.0f} SP remaining with {sprint_info.days_remaining} days left. "
                f"Need {remaining_sp / max(sprint_info.days_remaining, 1):.1f} SP/day to meet commitment."
            )
            recommendation = (
                f"⚠️ Sprint at {ppm_score:.0f}% - below target pace. "
                "Consider: scope negotiation, removing impediments, or extending support."
            )
        else:
            status = "off_track"
            pi_forecast = (
                f"PI SIGNIFICANTLY OFF TRACK. Only {ppm_score:.0f}% complete at "
                f"{sprint_info.progress_percentage:.0f}% through sprint. "
                "Recommend immediate PI planning adjustment."
            )
            recommendation = (
                f" CRITICAL: PPM at {ppm_score:.0f}%. Sprint commitment unlikely to be met. "
                "Actions: 1) Descope immediately, 2) Escalate blockers, 3) Adjust PI plan."
            )
        
        return PPMResult(
            planned_sp=planned_sp,
            actual_sp=actual_sp,
            ppm_score=round(ppm_score, 1),
            status=status,
            pi_forecast=pi_forecast,
            recommendation=recommendation
        )
    
    # =========================================================================
    # EXECUTIVE SUMMARY & PRIORITY ACTIONS
    # =========================================================================
    
    def _generate_executive_summary(
        self,
        flow: FlowEfficiencyResult,
        cycle: CycleTimeResult,
        wip: WIPStressResult,
        innovation: InnovationRateResult,
        ppm: PPMResult
    ) -> str:
        """Generate executive summary for RTL"""
        
        # Count critical items
        critical_count = sum([
            1 if flow.status == "critical" else 0,
            1 if len(cycle.outliers) > 3 else 0,
            1 if wip.team_health == "critical" else 0,
            1 if innovation.status == "critical" else 0,
            1 if ppm.status == "off_track" else 0
        ])
        
        warning_count = sum([
            1 if flow.status == "warning" else 0,
            1 if 0 < len(cycle.outliers) <= 3 else 0,
            1 if wip.team_health == "warning" else 0,
            1 if innovation.status == "warning" else 0,
            1 if ppm.status == "at_risk" else 0
        ])
        
        if critical_count > 0:
            summary = (
                f" EXECUTIVE ALERT: {critical_count} critical metric(s) require immediate attention. "
                f"PPM: {ppm.ppm_score:.0f}% | Flow Efficiency: {flow.score:.0f}% | "
                f"Team Stress: {wip.team_health.upper()} | Innovation: {innovation.innovation_percentage:.0f}%"
            )
        elif warning_count > 0:
            summary = (
                f"⚠️ ATTENTION: {warning_count} metric(s) showing warning signs. "
                f"PPM: {ppm.ppm_score:.0f}% | Flow Efficiency: {flow.score:.0f}% | "
                f"Cycle Time Outliers: {len(cycle.outliers)} | Innovation: {innovation.innovation_percentage:.0f}%"
            )
        else:
            summary = (
                f"✅ SPRINT HEALTH: All strategic metrics within healthy ranges. "
                f"PPM: {ppm.ppm_score:.0f}% | Flow Efficiency: {flow.score:.0f}% | "
                f"Team balanced with {innovation.innovation_percentage:.0f}% innovation focus."
            )
        
        return summary
    
    def _generate_priority_actions(
        self,
        flow: FlowEfficiencyResult,
        cycle: CycleTimeResult,
        wip: WIPStressResult,
        innovation: InnovationRateResult,
        ppm: PPMResult
    ) -> List[str]:
        """Generate prioritized action items"""
        actions = []
        
        # Priority 1: Critical issues
        if ppm.status == "off_track":
            actions.append(" [P0] Immediate scope negotiation required - PPM significantly below target")
        
        if wip.team_health == "critical":
            actions.append(f" [P0] Address team burnout risk - {len(wip.high_risk_assignees)} members overloaded")
        
        if flow.status == "critical":
            actions.append(" [P0] Investigate systemic bottleneck - Flow Efficiency critically low")
        
        # Priority 2: Warning issues
        if ppm.status == "at_risk":
            actions.append(" [P1] Monitor sprint burndown closely - consider removing impediments")
        
        if cycle.outliers:
            actions.append(f" [P1] Review {len(cycle.outliers)} cycle time outliers in next standup")
        
        if innovation.status in ["warning", "critical"]:
            actions.append(f" [P1] Schedule quality focus session - maintenance at {innovation.maintenance_percentage:.0f}%")
        
        if wip.team_health == "warning":
            actions.append(" [P1] Discuss workload distribution in team retrospective")
        
        # If no issues, add positive reinforcement
        if not actions:
            actions.append("✅ No critical actions needed - continue current practices")
            actions.append(" Consider: Knowledge sharing session to document successful patterns")
        
        return actions


# =============================================================================
# RECOMMENDATION TEMPLATES
# =============================================================================

class StrategicRecommendationTemplates:
    """Text templates for AI Agent to present to RTL"""
    
    @staticmethod
    def flow_efficiency_critical(score: float, wait_time: float) -> str:
        return f"""
 **Flow Efficiency Alert**

Current Score: {score:.1f}% (CRITICAL - below 10%)
Wait Time: {wait_time:.1f} days accumulated

**Root Cause Analysis Recommended:**
1. Are environment dependencies causing delays?
2. Is the QA/SIT queue backed up?
3. Are reviews happening in a timely manner?

**Suggested Actions:**
- Implement WIP limits to prevent queue buildup
- Schedule a value stream mapping session
- Consider dedicated 'flow improvement' time in next sprint
"""
    
    @staticmethod
    def cycle_time_outlier(outlier: CycleTimeOutlier) -> str:
        return f"""
⏱️ **Cycle Time Outlier Detected**

Issue: {outlier.issue_key}
Assignee: {outlier.assignee or 'Unassigned'}
Current Age: {outlier.current_age_days} days (Threshold: {outlier.threshold:.1f} days)

**Coaching Question for SM:**
{outlier.coaching_question}

**Suggested Discussion Points:**
- Is the acceptance criteria clear?
- Are there undocumented dependencies?
- Would pair programming help accelerate?
"""
    
    @staticmethod
    def burnout_risk(assignee: WIPStressAssignee) -> str:
        return f"""
 **Burnout Risk Identified**

Team Member: {assignee.name}
WIP Count: {assignee.wip_count} items
Avg Task Age: {assignee.avg_task_age} days
Stress Level: {assignee.stress_level.upper()}

**Recommended Actions:**
1. Check in with {assignee.name} on workload
2. Consider reassigning {assignee.oldest_task_key} 
3. Review sprint commitment for realistic capacity
"""
    
    @staticmethod
    def quality_focus_needed(maintenance_pct: float, consecutive_sprints: int) -> str:
        return f"""
 **RTL Alert: Quality Focus Recommended**

Maintenance Ratio: {maintenance_pct:.0f}% (Target: <30%)
Consecutive High-Maintenance Sprints: {consecutive_sprints}

**Recommendation for RTL:**
Schedule a "Quality Focus" session with the following agenda:
1. Tech debt inventory review
2. Identify top 3 systemic issues
3. Allocate dedicated refactoring capacity next PI
4. Consider: bug bash, architecture review, or test automation investment
"""
    
    @staticmethod
    def ppm_off_track(ppm: float, remaining_sp: float, days_left: int) -> str:
        return f"""
 **Program Predictability Critical**

Current PPM: {ppm:.0f}%
Remaining Work: {remaining_sp:.0f} SP
Days Remaining: {days_left}

**Immediate Actions for SM:**
1. Facilitate scope negotiation with PO
2. Identify and escalate blockers
3. Consider: carryover candidates, stretch goals to remove

**For RTL:**
- Adjust PI-level forecasts
- Communicate risk to stakeholders
- Support team with removing impediments
"""
