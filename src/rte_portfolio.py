"""
RTE Portfolio & Team Diagnostic Views
Comprehensive views for RTE (Release Train Engineer) and Team diagnostics

Features:
- RTE Portfolio View: Program Predictability (Actual vs Planned Business Value)
- Team Diagnostic View: Work Item Age, Quality, Flow Efficiency
- Cross-team comparison
- Program-level insights

Author: Sajan Banka
Created: May 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from .models import SprintIssue, SprintInfo, SprintMetrics, Phase
from .sle_diagnostics import SLEDiagnosticsEngine, AgingWIPReport, RiskLevel
from .flow_efficiency import FlowEfficiencyEngine, FlowEfficiencyReport
from .sentiment_clustering import SentimentClusteringEngine, SentimentClusteringReport
from .quality_guardrails import QualityGuardrailsEngine, QualityGuardrailsReport

logger = logging.getLogger(__name__)


@dataclass
class ProgramPredictability:
    """Program Predictability metrics (Actual vs Planned)"""
    planned_business_value: float  # Committed SP
    actual_business_value: float   # Completed SP
    predictability_score: float    # (Actual/Planned) × 100, capped at 100
    variance: float                # Planned - Actual
    variance_percentage: float     # Variance as % of planned
    on_track: bool                 # >= 80% predictability
    status: str                    # "on_track", "warning", "off_track"
    message: str


@dataclass
class TeamDiagnostic:
    """Team-level diagnostic summary"""
    team_name: str
    sprint_info: SprintInfo

    # Work Item Age
    aging_summary: Dict[str, int]  # risk_level -> count
    aging_alert_count: int
    sle_threshold_days: float

    # Flow Efficiency
    flow_efficiency: float
    wait_work_ratio: float
    flow_alert: Optional[str]

    # Sentiment
    team_sentiment: str
    burnout_risk_count: int
    blocker_count: int
    top_blocker_cause: Optional[str]

    # Quality
    defect_leakage_rate: float
    technical_debt_ratio: float
    quality_score: float
    quality_grade: str

    # Overall health
    overall_health: str  # "healthy", "warning", "critical"
    health_score: float  # 0-100
    top_concerns: List[str]
    top_strengths: List[str]


@dataclass
class RTEPortfolioView:
    """RTE Portfolio View - Program level overview"""
    generated_at: datetime
    program_name: str

    # All teams
    teams: List[TeamDiagnostic]

    # Program Predictability
    program_predictability: ProgramPredictability

    # Aggregated metrics
    total_planned_sp: float
    total_actual_sp: float
    total_remaining_sp: float

    # Cross-team comparison
    team_rankings: List[Dict[str, Any]]  # Teams ranked by health

    # Program-level alerts
    program_alerts: List[str]

    # Recommendations for RTE
    rte_recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'generated_at': self.generated_at.isoformat(),
            'program_name': self.program_name,
            'predictability': {
                'planned': self.program_predictability.planned_business_value,
                'actual': self.program_predictability.actual_business_value,
                'score': round(self.program_predictability.predictability_score, 1),
                'variance': round(self.program_predictability.variance, 1),
                'variance_pct': round(self.program_predictability.variance_percentage, 1),
                'on_track': self.program_predictability.on_track,
                'status': self.program_predictability.status,
                'message': self.program_predictability.message
            },
            'totals': {
                'planned_sp': self.total_planned_sp,
                'actual_sp': self.total_actual_sp,
                'remaining_sp': self.total_remaining_sp
            },
            'teams': [
                {
                    'name': t.team_name,
                    'sprint': t.sprint_info.name,
                    'health': t.overall_health,
                    'health_score': round(t.health_score, 1),
                    'flow_efficiency': round(t.flow_efficiency, 1),
                    'quality_grade': t.quality_grade,
                    'aging_alerts': t.aging_alert_count,
                    'burnout_risks': t.burnout_risk_count,
                    'top_concerns': t.top_concerns[:3]
                }
                for t in self.teams
            ],
            'rankings': self.team_rankings,
            'alerts': self.program_alerts,
            'recommendations': self.rte_recommendations
        }


@dataclass
class TeamDiagnosticView:
    """Detailed Team Diagnostic View"""
    generated_at: datetime
    team_diagnostic: TeamDiagnostic

    # Detailed reports
    aging_report: AgingWIPReport
    flow_report: FlowEfficiencyReport
    sentiment_report: SentimentClusteringReport
    quality_report: QualityGuardrailsReport

    # Action items
    immediate_actions: List[str]
    medium_term_actions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'generated_at': self.generated_at.isoformat(),
            'team': self.team_diagnostic.team_name,
            'sprint': self.team_diagnostic.sprint_info.name,
            'summary': {
                'health': self.team_diagnostic.overall_health,
                'health_score': self.team_diagnostic.health_score,
                'concerns': self.team_diagnostic.top_concerns,
                'strengths': self.team_diagnostic.top_strengths
            },
            'aging': self.aging_report.to_dict() if self.aging_report else None,
            'flow': self.flow_report.to_dict() if self.flow_report else None,
            'sentiment': self.sentiment_report.to_dict() if self.sentiment_report else None,
            'quality': self.quality_report.to_dict() if self.quality_report else None,
            'actions': {
                'immediate': self.immediate_actions,
                'medium_term': self.medium_term_actions
            }
        }


class RTEDiagnosticsEngine:
    """
    RTE Diagnostics Engine

    Combines all diagnostic modules to provide:
    1. RTE Portfolio View (Program level)
    2. Team Diagnostic View (Team level)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sle_engine = SLEDiagnosticsEngine(config)
        self.flow_engine = FlowEfficiencyEngine(config)
        self.sentiment_engine = SentimentClusteringEngine(config)
        self.quality_engine = QualityGuardrailsEngine(config)

    def generate_team_diagnostic(
        self,
        team_name: str,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        metrics: SprintMetrics,
        historical_data: List[Dict[str, Any]] = None
    ) -> TeamDiagnosticView:
        """
        Generate detailed diagnostic view for a single team.

        Args:
            team_name: Name of the team
            issues: Sprint issues
            sprint_info: Sprint information
            metrics: Sprint metrics
            historical_data: Historical sprint data

        Returns:
            TeamDiagnosticView with all diagnostic data
        """
        # Run all analyses
        aging_report = self.sle_engine.analyze_aging_wip(
            issues, sprint_info, historical_data
        )

        flow_report = self.flow_engine.analyze_flow(
            issues, sprint_info
        )

        sentiment_report = self.sentiment_engine.analyze(
            issues, sprint_info
        )

        quality_report = self.quality_engine.analyze(
            issues, sprint_info
        )

        # Create team diagnostic summary
        diagnostic = self._create_team_diagnostic(
            team_name, sprint_info,
            aging_report, flow_report,
            sentiment_report, quality_report
        )

        # Generate action items
        immediate, medium_term = self._generate_action_items(
            aging_report, flow_report,
            sentiment_report, quality_report
        )

        return TeamDiagnosticView(
            generated_at=datetime.now(),
            team_diagnostic=diagnostic,
            aging_report=aging_report,
            flow_report=flow_report,
            sentiment_report=sentiment_report,
            quality_report=quality_report,
            immediate_actions=immediate,
            medium_term_actions=medium_term
        )

    def generate_portfolio_view(
        self,
        program_name: str,
        team_reports: List[Dict[str, Any]]  # [{name, report, issues, metrics}]
    ) -> RTEPortfolioView:
        """
        Generate RTE Portfolio View across all teams.

        Args:
            program_name: Name of the program/train
            team_reports: List of team data with issues and metrics

        Returns:
            RTEPortfolioView with program-level insights
        """
        team_diagnostics = []
        total_planned = 0.0
        total_actual = 0.0
        total_remaining = 0.0

        for tr in team_reports:
            if tr.get('report') and tr.get('issues'):
                # Generate diagnostic for each team
                diag_view = self.generate_team_diagnostic(
                    team_name=tr['name'],
                    issues=tr['issues'],
                    sprint_info=tr['report'].sprint_info,
                    metrics=tr['report'].metrics,
                    historical_data=tr.get('historical_data')
                )

                team_diagnostics.append(diag_view.team_diagnostic)

                # Aggregate totals
                total_planned += tr['report'].metrics.total_story_points
                total_actual += tr['report'].metrics.completed_story_points
                total_remaining += tr['report'].metrics.remaining_story_points

        # Calculate program predictability
        predictability = self._calculate_predictability(
            total_planned, total_actual
        )

        # Rank teams by health
        rankings = self._rank_teams(team_diagnostics)

        # Generate program-level alerts
        program_alerts = self._generate_program_alerts(team_diagnostics)

        # Generate RTE recommendations
        rte_recs = self._generate_rte_recommendations(
            team_diagnostics, predictability
        )

        return RTEPortfolioView(
            generated_at=datetime.now(),
            program_name=program_name,
            teams=team_diagnostics,
            program_predictability=predictability,
            total_planned_sp=total_planned,
            total_actual_sp=total_actual,
            total_remaining_sp=total_remaining,
            team_rankings=rankings,
            program_alerts=program_alerts,
            rte_recommendations=rte_recs
        )

    def _create_team_diagnostic(
        self,
        team_name: str,
        sprint_info: SprintInfo,
        aging: AgingWIPReport,
        flow: FlowEfficiencyReport,
        sentiment: SentimentClusteringReport,
        quality: QualityGuardrailsReport
    ) -> TeamDiagnostic:
        """Create team diagnostic summary from individual reports"""
        # Aging summary
        aging_summary = {
            'green': aging.total_green,
            'amber': aging.total_amber,
            'red': aging.total_red + aging.total_critical
        }

        # Determine overall health
        concerns = []
        strengths = []

        # Check aging
        if aging.total_red + aging.total_critical > 0:
            concerns.append(f"{aging.total_red + aging.total_critical} items exceed SLE")
        elif aging.total_amber == 0:
            strengths.append("All items within SLE targets")

        # Check flow
        if flow.team_flow_efficiency < 20:
            concerns.append(f"Critical: Flow efficiency at {flow.team_flow_efficiency:.0f}%")
        elif flow.team_flow_efficiency >= 50:
            strengths.append(f"Good flow efficiency ({flow.team_flow_efficiency:.0f}%)")

        # Check sentiment
        if sentiment.burnout_risk_count > 0:
            concerns.append(f"{sentiment.burnout_risk_count} burnout risk(s) detected")
        elif sentiment.team_sentiment.value == 'positive':
            strengths.append("Positive team sentiment")

        # Check quality
        if quality.defect_metrics.leakage_rate > 20:
            concerns.append(f"High defect leakage ({quality.defect_metrics.leakage_rate:.0f}%)")
        elif quality.defect_metrics.leakage_rate < 10:
            strengths.append("Strong quality - low defect leakage")

        # Calculate health score
        health_score = self._calculate_health_score(
            aging, flow, sentiment, quality
        )

        if health_score >= 80:
            overall_health = "healthy"
        elif health_score >= 60:
            overall_health = "warning"
        else:
            overall_health = "critical"

        return TeamDiagnostic(
            team_name=team_name,
            sprint_info=sprint_info,
            aging_summary=aging_summary,
            aging_alert_count=aging.total_red + aging.total_critical,
            sle_threshold_days=aging.percentile_85_cycle_time,
            flow_efficiency=flow.team_flow_efficiency,
            wait_work_ratio=flow.wait_work_ratio,
            flow_alert=flow.alert_message,
            team_sentiment=sentiment.team_sentiment.value,
            burnout_risk_count=sentiment.burnout_risk_count,
            blocker_count=sentiment.total_blockers,
            top_blocker_cause=sentiment.top_root_cause.value if sentiment.top_root_cause else None,
            defect_leakage_rate=quality.defect_metrics.leakage_rate,
            technical_debt_ratio=quality.sqale_metrics.technical_debt_ratio,
            quality_score=quality.quality_score,
            quality_grade=quality.quality_grade,
            overall_health=overall_health,
            health_score=health_score,
            top_concerns=concerns[:3],
            top_strengths=strengths[:3]
        )

    def _calculate_health_score(
        self,
        aging: AgingWIPReport,
        flow: FlowEfficiencyReport,
        sentiment: SentimentClusteringReport,
        quality: QualityGuardrailsReport
    ) -> float:
        """Calculate overall team health score (0-100)"""
        # Aging score (25 points)
        total_items = aging.total_active_items or 1
        green_pct = aging.total_green / total_items
        aging_score = green_pct * 25

        # Flow score (25 points)
        flow_score = min(25, flow.team_flow_efficiency / 4)

        # Sentiment score (25 points)
        if sentiment.team_sentiment.value == 'positive':
            sentiment_score = 25
        elif sentiment.team_sentiment.value == 'neutral':
            sentiment_score = 18
        elif sentiment.team_sentiment.value == 'negative':
            sentiment_score = 10
        else:  # frustrated
            sentiment_score = 0

        # Burnout penalty
        sentiment_score -= sentiment.burnout_risk_count * 5
        sentiment_score = max(0, sentiment_score)

        # Quality score (25 points)
        quality_pts = min(25, quality.quality_score / 4)

        return aging_score + flow_score + sentiment_score + quality_pts

    def _calculate_predictability(
        self,
        planned: float,
        actual: float
    ) -> ProgramPredictability:
        """Calculate program predictability score"""
        if planned == 0:
            return ProgramPredictability(
                planned_business_value=0,
                actual_business_value=0,
                predictability_score=100,
                variance=0,
                variance_percentage=0,
                on_track=True,
                status="on_track",
                message="No planned work"
            )

        score = min(100, (actual / planned) * 100)
        variance = planned - actual
        variance_pct = (variance / planned) * 100

        if score >= 80:
            status = "on_track"
            on_track = True
            msg = f"Program on track at {score:.0f}% delivery"
        elif score >= 60:
            status = "warning"
            on_track = False
            msg = f"Program at risk - {score:.0f}% delivered, {variance:.0f} SP gap"
        else:
            status = "off_track"
            on_track = False
            msg = f"Program off track - only {score:.0f}% delivered"

        return ProgramPredictability(
            planned_business_value=planned,
            actual_business_value=actual,
            predictability_score=score,
            variance=variance,
            variance_percentage=variance_pct,
            on_track=on_track,
            status=status,
            message=msg
        )

    def _rank_teams(
        self,
        diagnostics: List[TeamDiagnostic]
    ) -> List[Dict[str, Any]]:
        """Rank teams by health score"""
        sorted_teams = sorted(
            diagnostics,
            key=lambda x: -x.health_score
        )

        return [
            {
                'rank': i + 1,
                'team': t.team_name,
                'health_score': round(t.health_score, 1),
                'health': t.overall_health,
                'flow_efficiency': round(t.flow_efficiency, 1),
                'quality_grade': t.quality_grade
            }
            for i, t in enumerate(sorted_teams)
        ]

    def _generate_program_alerts(
        self,
        diagnostics: List[TeamDiagnostic]
    ) -> List[str]:
        """Generate program-level alerts"""
        alerts = []

        critical_teams = [d for d in diagnostics if d.overall_health == 'critical']
        if critical_teams:
            names = ', '.join(t.team_name for t in critical_teams)
            alerts.append(f"🔴 CRITICAL: {len(critical_teams)} team(s) in critical state: {names}")

        burnout_total = sum(d.burnout_risk_count for d in diagnostics)
        if burnout_total > 0:
            alerts.append(f"⚠️ ALERT: {burnout_total} burnout risk(s) detected across teams")

        low_flow = [d for d in diagnostics if d.flow_efficiency < 30]
        if low_flow:
            names = ', '.join(t.team_name for t in low_flow)
            alerts.append(f"⚠️ Flow efficiency below 30% for: {names}")

        high_tdr = [d for d in diagnostics if d.technical_debt_ratio > 5]
        if high_tdr:
            names = ', '.join(t.team_name for t in high_tdr)
            alerts.append(f"⚠️ Technical debt ratio exceeds 5% for: {names}")

        return alerts

    def _generate_rte_recommendations(
        self,
        diagnostics: List[TeamDiagnostic],
        predictability: ProgramPredictability
    ) -> List[str]:
        """Generate recommendations for RTE"""
        recs = []

        if not predictability.on_track:
            recs.append(
                "📊 Program behind target - consider scope negotiation or capacity reallocation"
            )

        critical_teams = [d for d in diagnostics if d.overall_health == 'critical']
        for team in critical_teams:
            recs.append(f"🎯 Schedule health check with {team.team_name}")

        # Check for systemic issues
        low_flow_count = len([d for d in diagnostics if d.flow_efficiency < 40])
        if low_flow_count >= len(diagnostics) / 2:
            recs.append(
                "🔄 Multiple teams with low flow efficiency - investigate systemic handoff delays"
            )

        high_blocker_teams = [d for d in diagnostics if d.blocker_count > 3]
        if high_blocker_teams:
            recs.append(
                f"🚧 {len(high_blocker_teams)} team(s) with significant blockers - facilitate unblocking"
            )

        if not recs:
            recs.append("✅ Program health stable - continue monitoring")

        return recs

    def _generate_action_items(
        self,
        aging: AgingWIPReport,
        flow: FlowEfficiencyReport,
        sentiment: SentimentClusteringReport,
        quality: QualityGuardrailsReport
    ) -> Tuple[List[str], List[str]]:
        """Generate immediate and medium-term action items"""
        immediate = []
        medium_term = []

        # Immediate actions
        if aging.total_critical > 0:
            immediate.append(f"Address {aging.total_critical} items exceeding SLE immediately")

        if sentiment.burnout_risk_count > 0:
            immediate.append("Check in with team members showing burnout signals")

        if quality.defect_metrics.critical_leaked > 0:
            immediate.append("Investigate root cause of leaked critical defects")

        for bottleneck in flow.bottleneck_statuses[:2]:
            immediate.append(f"Clear bottleneck: {bottleneck[2]}")

        # Medium-term actions
        if flow.team_flow_efficiency < 40:
            medium_term.append("Review and optimize workflow to reduce wait times")

        if quality.sqale_metrics.threshold_exceeded:
            medium_term.append("Allocate capacity for technical debt reduction")

        if sentiment.top_root_cause:
            medium_term.append(
                f"Address recurring blocker type: {sentiment.top_root_cause.value}"
            )

        if aging.total_amber > aging.total_green:
            medium_term.append("Review and adjust SLE thresholds or team capacity")

        return immediate, medium_term

