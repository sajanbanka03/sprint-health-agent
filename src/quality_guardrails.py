"""
Module 4: Quality & Technical Debt Guardrails
Defect leakage rate and SQALE Technical Debt Ratio tracking

Features:
- Defect Leakage Rate: (External Defects / Total Defects) × 100
- SQALE Technical Debt Ratio: (Remediation Cost / Development Cost) × 100
- TDR warning when > 5%
- Quality trend analysis

Author: Sajan Banka
Created: May 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics

from .models import SprintIssue, SprintInfo, Phase

logger = logging.getLogger(__name__)


class DefectSource(Enum):
    """Where the defect was found"""
    DEVELOPMENT = "development"     # Found during dev
    CODE_REVIEW = "code_review"     # Found in PR review
    SIT = "sit"                     # System Integration Testing
    UAT = "uat"                     # User Acceptance Testing
    PRODUCTION = "production"       # Found in production


class DefectSeverity(Enum):
    """Defect severity classification"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QualityStatus(Enum):
    """Overall quality status"""
    EXCELLENT = "excellent"   # Leakage < 5%
    GOOD = "good"             # Leakage 5-10%
    WARNING = "warning"       # Leakage 10-20%
    CRITICAL = "critical"     # Leakage > 20%


@dataclass
class DefectAnalysis:
    """Analysis of a single defect"""
    issue_key: str
    summary: str
    severity: DefectSeverity
    source: DefectSource
    is_external: bool  # Found externally (UAT/Production)
    story_points: float
    days_to_find: int  # Days from creation to being found
    root_cause: Optional[str]
    associated_story: Optional[str]


@dataclass
class DefectLeakageMetrics:
    """Defect leakage rate metrics"""
    total_defects: int
    internal_defects: int  # Found in Dev/SIT
    external_defects: int  # Found in UAT/Production
    leakage_rate: float    # percentage

    # By source
    defects_by_source: Dict[DefectSource, int]

    # By severity
    severity_distribution: Dict[DefectSeverity, int]
    critical_leaked: int  # Critical defects found externally

    # Quality status
    status: QualityStatus
    status_message: str


@dataclass
class TechnicalDebtItem:
    """A technical debt item"""
    issue_key: str
    summary: str
    debt_type: str  # "code_smell", "bug_debt", "design_debt", etc.
    estimated_hours: float  # Remediation effort
    story_points: float
    age_days: int
    priority: str
    risk_if_not_fixed: str


@dataclass
class SQALEMetrics:
    """SQALE Technical Debt Ratio metrics"""
    # Remediation cost (in hours)
    total_remediation_hours: float

    # Development cost (in hours)
    total_development_hours: float

    # TDR = (Remediation / Development) × 100
    technical_debt_ratio: float

    # Status
    status: str  # "healthy", "warning", "critical"
    threshold_exceeded: bool  # > 5%

    # Debt breakdown
    debt_items: List[TechnicalDebtItem]
    debt_by_type: Dict[str, float]  # type -> hours

    # Trend
    trend: str  # "increasing", "stable", "decreasing"
    previous_tdr: Optional[float]


@dataclass
class QualityGuardrailsReport:
    """Complete quality and technical debt report"""
    generated_at: datetime
    sprint_info: SprintInfo

    # Defect Leakage
    defect_metrics: DefectLeakageMetrics
    defect_details: List[DefectAnalysis]
    leaked_defects: List[DefectAnalysis]

    # Technical Debt
    sqale_metrics: SQALEMetrics
    high_priority_debt: List[TechnicalDebtItem]

    # Combined quality score (0-100)
    quality_score: float
    quality_grade: str  # A, B, C, D, F

    # Recommendations
    quality_recommendations: List[str]
    debt_recommendations: List[str]

    # Alerts for PM/RTE
    alerts: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON"""
        return {
            'generated_at': self.generated_at.isoformat(),
            'sprint': {
                'id': self.sprint_info.id,
                'name': self.sprint_info.name
            },
            'quality_overview': {
                'score': round(self.quality_score, 1),
                'grade': self.quality_grade,
                'alerts_count': len(self.alerts)
            },
            'defect_leakage': {
                'total_defects': self.defect_metrics.total_defects,
                'internal': self.defect_metrics.internal_defects,
                'external': self.defect_metrics.external_defects,
                'leakage_rate': round(self.defect_metrics.leakage_rate, 1),
                'status': self.defect_metrics.status.value,
                'critical_leaked': self.defect_metrics.critical_leaked,
                'by_source': {
                    k.value: v for k, v in self.defect_metrics.defects_by_source.items()
                },
                'by_severity': {
                    k.value: v for k, v in self.defect_metrics.severity_distribution.items()
                }
            },
            'leaked_defects': [
                {
                    'key': d.issue_key,
                    'summary': d.summary,
                    'severity': d.severity.value,
                    'source': d.source.value,
                    'days_to_find': d.days_to_find,
                    'root_cause': d.root_cause
                }
                for d in self.leaked_defects[:10]
            ],
            'technical_debt': {
                'remediation_hours': round(self.sqale_metrics.total_remediation_hours, 1),
                'development_hours': round(self.sqale_metrics.total_development_hours, 1),
                'tdr': round(self.sqale_metrics.technical_debt_ratio, 2),
                'status': self.sqale_metrics.status,
                'threshold_exceeded': self.sqale_metrics.threshold_exceeded,
                'trend': self.sqale_metrics.trend,
                'by_type': self.sqale_metrics.debt_by_type,
                'debt_items_count': len(self.sqale_metrics.debt_items)
            },
            'high_priority_debt': [
                {
                    'key': d.issue_key,
                    'summary': d.summary,
                    'type': d.debt_type,
                    'hours': d.estimated_hours,
                    'risk': d.risk_if_not_fixed
                }
                for d in self.high_priority_debt[:5]
            ],
            'recommendations': {
                'quality': self.quality_recommendations,
                'debt': self.debt_recommendations
            },
            'alerts': self.alerts
        }


class QualityGuardrailsEngine:
    """
    Quality & Technical Debt Guardrails Engine

    Tracks defect leakage rate and SQALE technical debt ratio
    to provide quality guardrails for the team.
    """

    # Defect source detection keywords
    SOURCE_PATTERNS = {
        DefectSource.PRODUCTION: [
            'prod', 'production', 'live', 'customer reported',
            'p1', 'incident', 'hotfix', 'emergency'
        ],
        DefectSource.UAT: [
            'uat', 'user acceptance', 'user testing', 'business testing',
            'qa validation', 'acceptance testing'
        ],
        DefectSource.SIT: [
            'sit', 'integration', 'system test', 'e2e', 'end to end',
            'regression', 'qa found'
        ],
        DefectSource.CODE_REVIEW: [
            'pr', 'pull request', 'code review', 'review',
            'merge', 'peer review'
        ],
        DefectSource.DEVELOPMENT: [
            'dev', 'development', 'unit test', 'local',
            'debug', 'self found'
        ]
    }

    # Technical debt type patterns
    DEBT_TYPE_PATTERNS = {
        'code_smell': [
            'refactor', 'cleanup', 'code smell', 'complexity',
            'duplication', 'naming', 'style', 'readability'
        ],
        'bug_debt': [
            'known issue', 'workaround', 'hack', 'temporary fix',
            'todo', 'fixme', 'tech debt bug'
        ],
        'design_debt': [
            'architecture', 'design', 'pattern', 'structure',
            'coupling', 'cohesion', 'solid violation'
        ],
        'test_debt': [
            'test coverage', 'missing test', 'flaky test',
            'test automation', 'unit test', 'integration test'
        ],
        'documentation_debt': [
            'documentation', 'readme', 'javadoc', 'comment',
            'api doc', 'swagger', 'confluence'
        ],
        'infrastructure_debt': [
            'infra', 'ci/cd', 'pipeline', 'deployment',
            'docker', 'kubernetes', 'config'
        ]
    }

    # Hour estimation by item type/size
    HOURS_PER_SP = 6  # Average hours per story point

    # TDR thresholds
    TDR_WARNING_THRESHOLD = 5   # 5% - warning
    TDR_CRITICAL_THRESHOLD = 10  # 10% - critical

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Allow configuration of hour estimates
        self.hours_per_sp = config.get('hours_per_story_point', self.HOURS_PER_SP)

    def analyze(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        historical_tdr: Optional[float] = None
    ) -> QualityGuardrailsReport:
        """
        Run quality and technical debt analysis.

        Args:
            issues: Sprint issues
            sprint_info: Sprint information
            historical_tdr: Previous sprint's TDR for trend analysis

        Returns:
            QualityGuardrailsReport with complete analysis
        """
        # Separate defects and other issues
        defects = self._identify_defects(issues)
        debt_items = self._identify_tech_debt(issues)

        # Analyze defect leakage
        defect_analyses = self._analyze_defects(defects)
        defect_metrics = self._calculate_defect_metrics(defect_analyses)
        leaked = [d for d in defect_analyses if d.is_external]

        # Analyze technical debt
        sqale_metrics = self._calculate_sqale_metrics(
            issues, debt_items, historical_tdr
        )
        high_priority = sorted(
            debt_items,
            key=lambda x: (-self._debt_priority_score(x))
        )[:5]

        # Calculate quality score
        quality_score = self._calculate_quality_score(
            defect_metrics, sqale_metrics
        )
        quality_grade = self._score_to_grade(quality_score)

        # Generate recommendations
        quality_recs = self._generate_quality_recommendations(defect_metrics)
        debt_recs = self._generate_debt_recommendations(sqale_metrics)

        # Generate alerts
        alerts = self._generate_alerts(defect_metrics, sqale_metrics)

        return QualityGuardrailsReport(
            generated_at=datetime.now(),
            sprint_info=sprint_info,
            defect_metrics=defect_metrics,
            defect_details=defect_analyses,
            leaked_defects=leaked,
            sqale_metrics=sqale_metrics,
            high_priority_debt=high_priority,
            quality_score=quality_score,
            quality_grade=quality_grade,
            quality_recommendations=quality_recs,
            debt_recommendations=debt_recs,
            alerts=alerts
        )

    def _identify_defects(self, issues: List[SprintIssue]) -> List[SprintIssue]:
        """Identify defect/bug issues"""
        defect_types = ['bug', 'defect', 'incident', 'issue']

        defects = []
        for issue in issues:
            issue_type_lower = issue.issue_type.lower()
            if any(dt in issue_type_lower for dt in defect_types):
                defects.append(issue)
            elif any(label.lower() in defect_types for label in issue.labels):
                defects.append(issue)

        return defects

    def _identify_tech_debt(self, issues: List[SprintIssue]) -> List[TechnicalDebtItem]:
        """Identify technical debt items"""
        debt_items = []

        debt_indicators = [
            'tech debt', 'technical debt', 'refactor', 'cleanup',
            'improvement', 'spike', 'enabler'
        ]

        for issue in issues:
            is_debt = (
                any(ind in issue.summary.lower() for ind in debt_indicators) or
                any(ind in label.lower() for label in issue.labels for ind in debt_indicators) or
                issue.issue_type.lower() in ['technical debt', 'tech debt', 'improvement', 'spike']
            )

            if is_debt:
                debt_type = self._classify_debt_type(issue)

                debt_items.append(TechnicalDebtItem(
                    issue_key=issue.key,
                    summary=issue.summary,
                    debt_type=debt_type,
                    estimated_hours=issue.story_points * self.hours_per_sp if issue.story_points else 4,
                    story_points=issue.story_points,
                    age_days=issue.days_in_current_status,
                    priority=issue.priority,
                    risk_if_not_fixed=self._assess_debt_risk(issue, debt_type)
                ))

        return debt_items

    def _classify_debt_type(self, issue: SprintIssue) -> str:
        """Classify the type of technical debt"""
        text = f"{issue.summary} {' '.join(issue.labels)}".lower()

        for debt_type, patterns in self.DEBT_TYPE_PATTERNS.items():
            if any(p in text for p in patterns):
                return debt_type

        return "general"

    def _assess_debt_risk(self, issue: SprintIssue, debt_type: str) -> str:
        """Assess the risk if debt is not fixed"""
        if issue.priority in ['Highest', 'Critical']:
            return "High risk - may cause production issues"

        risk_by_type = {
            'code_smell': "Reduced maintainability and velocity",
            'bug_debt': "May manifest as customer-facing bugs",
            'design_debt': "Architectural degradation over time",
            'test_debt': "Increased defect leakage risk",
            'documentation_debt': "Onboarding delays and knowledge gaps",
            'infrastructure_debt': "Deployment reliability concerns"
        }

        return risk_by_type.get(debt_type, "Technical degradation over time")

    def _debt_priority_score(self, item: TechnicalDebtItem) -> float:
        """Calculate priority score for sorting"""
        priority_multiplier = {
            'Highest': 4, 'Critical': 4,
            'High': 3,
            'Medium': 2,
            'Low': 1, 'Lowest': 0.5
        }

        mult = priority_multiplier.get(item.priority, 1)
        return (item.estimated_hours * mult) + (item.age_days * 0.1)

    def _analyze_defects(self, defects: List[SprintIssue]) -> List[DefectAnalysis]:
        """Analyze each defect"""
        analyses = []

        for defect in defects:
            source = self._detect_defect_source(defect)
            severity = self._classify_severity(defect)
            is_external = source in [DefectSource.UAT, DefectSource.PRODUCTION]

            # Estimate days to find (from creation)
            if defect.phase == Phase.DONE:
                days_to_find = 0  # Found during dev
            else:
                days_to_find = (datetime.now() - defect.created_date).days

            analyses.append(DefectAnalysis(
                issue_key=defect.key,
                summary=defect.summary,
                severity=severity,
                source=source,
                is_external=is_external,
                story_points=defect.story_points,
                days_to_find=days_to_find,
                root_cause=self._detect_root_cause(defect),
                associated_story=None  # Would need linked issue data
            ))

        return analyses

    def _detect_defect_source(self, defect: SprintIssue) -> DefectSource:
        """Detect where the defect was found"""
        text = f"{defect.summary} {defect.status} {' '.join(defect.labels)}".lower()

        for source, patterns in self.SOURCE_PATTERNS.items():
            if any(p in text for p in patterns):
                return source

        # Default based on status
        status_lower = defect.status.lower()
        if 'prod' in status_lower:
            return DefectSource.PRODUCTION
        elif 'uat' in status_lower:
            return DefectSource.UAT
        elif 'sit' in status_lower or 'test' in status_lower:
            return DefectSource.SIT

        return DefectSource.DEVELOPMENT

    def _classify_severity(self, defect: SprintIssue) -> DefectSeverity:
        """Classify defect severity"""
        priority = defect.priority.lower()

        if priority in ['highest', 'critical', 'p1', 'blocker']:
            return DefectSeverity.CRITICAL
        elif priority in ['high', 'p2', 'major']:
            return DefectSeverity.HIGH
        elif priority in ['medium', 'p3', 'normal']:
            return DefectSeverity.MEDIUM
        else:
            return DefectSeverity.LOW

    def _detect_root_cause(self, defect: SprintIssue) -> Optional[str]:
        """Attempt to detect root cause from defect details"""
        text = defect.summary.lower()

        root_causes = {
            'missing requirement': ['missing', 'undefined', 'not specified'],
            'logic error': ['incorrect', 'wrong', 'calculation', 'logic'],
            'integration issue': ['integration', 'api', 'interface', 'connection'],
            'data issue': ['data', 'null', 'empty', 'format', 'mapping'],
            'configuration': ['config', 'configuration', 'setting', 'property'],
            'performance': ['slow', 'timeout', 'performance', 'memory'],
            'ui/ux': ['display', 'ui', 'ux', 'layout', 'css', 'style']
        }

        for cause, keywords in root_causes.items():
            if any(kw in text for kw in keywords):
                return cause

        return None

    def _calculate_defect_metrics(
        self,
        defect_analyses: List[DefectAnalysis]
    ) -> DefectLeakageMetrics:
        """Calculate defect leakage metrics"""
        total = len(defect_analyses)

        if total == 0:
            return DefectLeakageMetrics(
                total_defects=0,
                internal_defects=0,
                external_defects=0,
                leakage_rate=0.0,
                defects_by_source={},
                severity_distribution={},
                critical_leaked=0,
                status=QualityStatus.EXCELLENT,
                status_message="No defects found - excellent quality!"
            )

        internal = len([d for d in defect_analyses if not d.is_external])
        external = len([d for d in defect_analyses if d.is_external])

        leakage_rate = (external / total) * 100

        # By source
        by_source = {}
        for source in DefectSource:
            count = len([d for d in defect_analyses if d.source == source])
            if count > 0:
                by_source[source] = count

        # By severity
        severity_dist = {}
        for sev in DefectSeverity:
            count = len([d for d in defect_analyses if d.severity == sev])
            if count > 0:
                severity_dist[sev] = count

        # Critical leaked
        critical_leaked = len([
            d for d in defect_analyses
            if d.is_external and d.severity == DefectSeverity.CRITICAL
        ])

        # Status
        if leakage_rate < 5:
            status = QualityStatus.EXCELLENT
            msg = "Excellent quality - minimal defect leakage"
        elif leakage_rate < 10:
            status = QualityStatus.GOOD
            msg = "Good quality - leakage within acceptable range"
        elif leakage_rate < 20:
            status = QualityStatus.WARNING
            msg = "Warning - defect leakage above target"
        else:
            status = QualityStatus.CRITICAL
            msg = "Critical - high defect leakage needs immediate attention"

        return DefectLeakageMetrics(
            total_defects=total,
            internal_defects=internal,
            external_defects=external,
            leakage_rate=leakage_rate,
            defects_by_source=by_source,
            severity_distribution=severity_dist,
            critical_leaked=critical_leaked,
            status=status,
            status_message=msg
        )

    def _calculate_sqale_metrics(
        self,
        issues: List[SprintIssue],
        debt_items: List[TechnicalDebtItem],
        historical_tdr: Optional[float]
    ) -> SQALEMetrics:
        """Calculate SQALE Technical Debt Ratio"""
        # Total remediation cost (tech debt hours)
        remediation_hours = sum(d.estimated_hours for d in debt_items)

        # Total development cost (all story points × hours)
        total_sp = sum(i.story_points for i in issues if i.story_points)
        development_hours = total_sp * self.hours_per_sp

        # TDR calculation
        if development_hours > 0:
            tdr = (remediation_hours / development_hours) * 100
        else:
            tdr = 0

        # Status
        if tdr > self.TDR_CRITICAL_THRESHOLD:
            status = "critical"
        elif tdr > self.TDR_WARNING_THRESHOLD:
            status = "warning"
        else:
            status = "healthy"

        # Debt by type
        debt_by_type = {}
        for item in debt_items:
            if item.debt_type not in debt_by_type:
                debt_by_type[item.debt_type] = 0
            debt_by_type[item.debt_type] += item.estimated_hours

        # Trend
        if historical_tdr is not None:
            if tdr > historical_tdr + 1:
                trend = "increasing"
            elif tdr < historical_tdr - 1:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "unknown"

        return SQALEMetrics(
            total_remediation_hours=remediation_hours,
            total_development_hours=development_hours,
            technical_debt_ratio=tdr,
            status=status,
            threshold_exceeded=tdr > self.TDR_WARNING_THRESHOLD,
            debt_items=debt_items,
            debt_by_type=debt_by_type,
            trend=trend,
            previous_tdr=historical_tdr
        )

    def _calculate_quality_score(
        self,
        defect_metrics: DefectLeakageMetrics,
        sqale_metrics: SQALEMetrics
    ) -> float:
        """Calculate combined quality score (0-100)"""
        # Leakage score (50 points)
        if defect_metrics.total_defects == 0:
            leakage_score = 50
        else:
            # Lower leakage = higher score
            leakage_score = max(0, 50 - (defect_metrics.leakage_rate * 2))

        # TDR score (50 points)
        # Lower TDR = higher score
        tdr_score = max(0, 50 - (sqale_metrics.technical_debt_ratio * 5))

        return leakage_score + tdr_score

    def _score_to_grade(self, score: float) -> str:
        """Convert score to letter grade"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def _generate_quality_recommendations(
        self,
        metrics: DefectLeakageMetrics
    ) -> List[str]:
        """Generate quality improvement recommendations"""
        recs = []

        if metrics.leakage_rate > 20:
            recs.append("🚨 Implement shift-left testing to catch defects earlier")
            recs.append("Add more unit tests and code review rigor")

        if metrics.critical_leaked > 0:
            recs.append(f"⚠️ {metrics.critical_leaked} critical defects reached UAT/Prod - review test coverage gaps")

        if DefectSource.PRODUCTION in metrics.defects_by_source:
            count = metrics.defects_by_source[DefectSource.PRODUCTION]
            recs.append(f"🔴 {count} production defects - consider canary deployments")

        if metrics.status == QualityStatus.EXCELLENT:
            recs.append("✅ Quality is excellent - maintain current practices")

        return recs if recs else ["👍 No critical quality issues detected"]

    def _generate_debt_recommendations(
        self,
        metrics: SQALEMetrics
    ) -> List[str]:
        """Generate technical debt recommendations"""
        recs = []

        if metrics.threshold_exceeded:
            recs.append(f"⚠️ TDR at {metrics.technical_debt_ratio:.1f}% exceeds 5% threshold")
            recs.append("Allocate sprint capacity for debt reduction")

        if metrics.trend == "increasing":
            recs.append("📈 Technical debt is increasing - address root cause")

        # Suggest addressing largest debt type
        if metrics.debt_by_type:
            largest = max(metrics.debt_by_type.items(), key=lambda x: x[1])
            recs.append(f"Focus on {largest[0]} debt ({largest[1]:.0f}h remediation)")

        if metrics.status == "healthy":
            recs.append("✅ Technical debt is under control")

        return recs if recs else ["No significant technical debt concerns"]

    def _generate_alerts(
        self,
        defect_metrics: DefectLeakageMetrics,
        sqale_metrics: SQALEMetrics
    ) -> List[str]:
        """Generate PM/RTE alerts"""
        alerts = []

        if defect_metrics.leakage_rate > 20:
            alerts.append(
                f"🔴 ALERT: Defect leakage rate at {defect_metrics.leakage_rate:.0f}% - "
                f"quality guardrail breached"
            )

        if defect_metrics.critical_leaked > 0:
            alerts.append(
                f"🔴 ALERT: {defect_metrics.critical_leaked} critical defects "
                f"escaped to UAT/Production"
            )

        if sqale_metrics.technical_debt_ratio > self.TDR_CRITICAL_THRESHOLD:
            alerts.append(
                f"🔴 ALERT: TDR at {sqale_metrics.technical_debt_ratio:.1f}% - "
                f"exceeds critical threshold of {self.TDR_CRITICAL_THRESHOLD}%"
            )
        elif sqale_metrics.threshold_exceeded:
            alerts.append(
                f"⚠️ WARNING: TDR at {sqale_metrics.technical_debt_ratio:.1f}% - "
                f"exceeds 5% threshold"
            )

        return alerts

    def get_visualization_data(
        self,
        report: QualityGuardrailsReport
    ) -> Dict[str, Any]:
        """Get data for quality dashboard visualizations"""
        return {
            'gauge': {
                'title': 'Quality Score',
                'value': report.quality_score,
                'grade': report.quality_grade,
                'max': 100
            },
            'leakage_funnel': {
                'title': 'Defect Detection Funnel',
                'data': [
                    {'stage': 'Development', 'count': report.defect_metrics.defects_by_source.get(DefectSource.DEVELOPMENT, 0)},
                    {'stage': 'Code Review', 'count': report.defect_metrics.defects_by_source.get(DefectSource.CODE_REVIEW, 0)},
                    {'stage': 'SIT', 'count': report.defect_metrics.defects_by_source.get(DefectSource.SIT, 0)},
                    {'stage': 'UAT', 'count': report.defect_metrics.defects_by_source.get(DefectSource.UAT, 0)},
                    {'stage': 'Production', 'count': report.defect_metrics.defects_by_source.get(DefectSource.PRODUCTION, 0)}
                ]
            },
            'tdr_gauge': {
                'title': 'Technical Debt Ratio',
                'value': report.sqale_metrics.technical_debt_ratio,
                'threshold': 5,
                'status': report.sqale_metrics.status
            },
            'debt_breakdown': {
                'title': 'Debt by Type',
                'data': [
                    {'type': k, 'hours': v}
                    for k, v in report.sqale_metrics.debt_by_type.items()
                ]
            }
        }

