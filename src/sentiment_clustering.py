"""
Module 3: AI Sentiment & Blocker Clustering
NLP-powered comment sentiment analysis and blocker categorization

Features:
- Team Sentiment Trend tracking from comments
- Burnout Risk detection via negative sentiment
- Automatic blocker categorization (Pareto analysis)
- Root cause clustering

Author: Sajan Banka
Created: May 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter
import statistics

from .models import SprintIssue, SprintInfo, Phase

logger = logging.getLogger(__name__)


class SentimentLevel(Enum):
    """Sentiment classification"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"  # Strong negative / potential burnout


class BlockerCategory(Enum):
    """Root cause categories for blockers"""
    EXTERNAL_DEPENDENCY = "external_dependency"
    ENVIRONMENT = "environment"
    UNCLEAR_REQUIREMENTS = "unclear_requirements"
    TECHNICAL_DEBT = "technical_debt"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    WAITING_FOR_REVIEW = "waiting_for_review"
    ACCESS_PERMISSION = "access_permission"
    THIRD_PARTY = "third_party"
    DESIGN_DECISION = "design_decision"
    OTHER = "other"


@dataclass
class CommentSentiment:
    """Sentiment analysis of a single comment"""
    issue_key: str
    author: str
    timestamp: datetime
    text: str
    sentiment: SentimentLevel
    sentiment_score: float  # -1 to 1
    frustration_indicators: List[str]
    is_blocker_related: bool


@dataclass
class IssueSentimentTrend:
    """Sentiment trend for a single issue"""
    issue_key: str
    summary: str
    assignee: Optional[str]
    total_comments: int
    positive_count: int
    negative_count: int
    frustrated_count: int
    overall_sentiment: SentimentLevel
    trend: str  # "improving", "stable", "declining"
    burnout_risk: bool
    burnout_reason: Optional[str]


@dataclass
class CategorizedBlocker:
    """A blocker with root cause categorization"""
    issue_key: str
    summary: str
    assignee: Optional[str]
    status: str
    days_blocked: int
    category: BlockerCategory
    category_confidence: float  # 0-1
    detected_keywords: List[str]
    story_points: float
    impact_score: float  # Based on SP × days blocked


@dataclass
class BlockerDistribution:
    """Pareto analysis of blocker categories"""
    category: BlockerCategory
    display_name: str
    count: int
    percentage: float
    total_sp_blocked: float
    total_days_blocked: int
    avg_days_per_blocker: float
    examples: List[str]  # Issue keys


@dataclass
class SentimentClusteringReport:
    """Complete sentiment and blocker analysis report"""
    generated_at: datetime
    sprint_info: SprintInfo

    # Team Sentiment Overview
    team_sentiment: SentimentLevel
    sentiment_score: float  # -1 to 1, team average
    sentiment_trend: str  # "improving", "stable", "declining"

    # Burnout Risk
    burnout_risk_items: List[IssueSentimentTrend]
    burnout_risk_count: int

    # Issue sentiment breakdown
    issue_sentiments: List[IssueSentimentTrend]
    negative_sentiment_count: int

    # Blocker Analysis
    total_blockers: int
    categorized_blockers: List[CategorizedBlocker]

    # Pareto Analysis (root causes)
    blocker_distribution: List[BlockerDistribution]
    top_root_cause: Optional[BlockerCategory]

    # Recommendations
    sentiment_recommendations: List[str]
    blocker_recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON"""
        return {
            'generated_at': self.generated_at.isoformat(),
            'sprint': {
                'id': self.sprint_info.id,
                'name': self.sprint_info.name
            },
            'team_sentiment': {
                'level': self.team_sentiment.value,
                'score': round(self.sentiment_score, 2),
                'trend': self.sentiment_trend,
                'negative_count': self.negative_sentiment_count
            },
            'burnout_risk': {
                'count': self.burnout_risk_count,
                'items': [
                    {
                        'key': item.issue_key,
                        'summary': item.summary,
                        'assignee': item.assignee,
                        'sentiment': item.overall_sentiment.value,
                        'frustrated_comments': item.frustrated_count,
                        'reason': item.burnout_reason
                    }
                    for item in self.burnout_risk_items
                ]
            },
            'blockers': {
                'total': self.total_blockers,
                'categories': [
                    {
                        'category': bd.category.value,
                        'display_name': bd.display_name,
                        'count': bd.count,
                        'percentage': round(bd.percentage, 1),
                        'sp_blocked': bd.total_sp_blocked,
                        'avg_days': round(bd.avg_days_per_blocker, 1),
                        'examples': bd.examples[:3]
                    }
                    for bd in self.blocker_distribution
                ],
                'top_cause': self.top_root_cause.value if self.top_root_cause else None
            },
            'recommendations': {
                'sentiment': self.sentiment_recommendations,
                'blockers': self.blocker_recommendations
            }
        }


class SentimentClusteringEngine:
    """
    AI-powered Sentiment Analysis and Blocker Clustering Engine

    Uses keyword-based NLP for sentiment detection and
    rule-based clustering for blocker categorization.
    """

    # Sentiment keywords (can be enhanced with ML model)
    POSITIVE_KEYWORDS = {
        'great', 'excellent', 'good', 'thanks', 'thank you', 'perfect',
        'awesome', 'nice', 'done', 'completed', 'resolved', 'fixed',
        'working', 'success', 'appreciate', 'helpful', 'love', 'happy',
        'smooth', 'easy', 'quick', 'efficient', '👍', '✅', '🎉'
    }

    NEGATIVE_KEYWORDS = {
        'issue', 'problem', 'error', 'bug', 'fail', 'failed', 'broken',
        'wrong', 'not working', 'doesn\'t work', 'crash', 'stuck',
        'blocker', 'blocked', 'delay', 'late', 'missing', 'unclear',
        'confused', 'difficult', 'hard', 'slow', 'waiting', 'pending'
    }

    FRUSTRATED_KEYWORDS = {
        'again', 'still', 'yet again', 'frustrat', 'annoying', 'ridiculous',
        'unacceptab', 'waste', 'wasting', 'stupid', 'terrible', 'worst',
        'never', 'always', 'no response', 'no update', 'ignored',
        'escalat', 'urgent', 'critical', 'asap', 'immediately',
        'disappointed', 'unbelievab', 'seriously', '!!', '???',
        'how many times', 'once again', 'repeated'
    }

    # Blocker category patterns
    BLOCKER_PATTERNS = {
        BlockerCategory.EXTERNAL_DEPENDENCY: [
            'external', 'vendor', 'third party', '3rd party', 'supplier',
            'partner', 'api', 'integration', 'upstream', 'downstream',
            'another team', 'other team', 'dependency', 'dependent on'
        ],
        BlockerCategory.ENVIRONMENT: [
            'environment', 'env', 'server', 'deployment', 'infra',
            'infrastructure', 'database', 'db', 'connection', 'network',
            'config', 'configuration', 'pipeline', 'jenkins', 'ci/cd',
            'sandbox', 'staging', 'prod', 'production'
        ],
        BlockerCategory.UNCLEAR_REQUIREMENTS: [
            'requirement', 'unclear', 'clarification', 'confirm',
            'need more info', 'specification', 'spec', 'ac', 'acceptance',
            'criteria', 'scope', 'business', 'ba', 'product', 'po',
            'what exactly', 'not sure', 'need to understand', 'ambiguous'
        ],
        BlockerCategory.TECHNICAL_DEBT: [
            'tech debt', 'technical debt', 'legacy', 'refactor',
            'deprecated', 'old code', 'workaround', 'hack', 'temporary',
            'need to fix', 'debt', 'cleanup', 'outdated'
        ],
        BlockerCategory.RESOURCE_UNAVAILABLE: [
            'leave', 'vacation', 'pto', 'sick', 'unavailable',
            'capacity', 'bandwidth', 'busy', 'occupied', 'meeting',
            'training', 'ooo', 'out of office', 'absent'
        ],
        BlockerCategory.WAITING_FOR_REVIEW: [
            'review', 'pr', 'pull request', 'code review', 'approval',
            'sign off', 'sign-off', 'merge', 'tpo', 'qa', 'testing',
            'waiting for', 'pending review', 'awaiting'
        ],
        BlockerCategory.ACCESS_PERMISSION: [
            'access', 'permission', 'credentials', 'login', 'password',
            'authorization', 'rights', 'role', 'vpn', 'firewall',
            'certificate', 'token', 'key', 'security'
        ],
        BlockerCategory.THIRD_PARTY: [
            'third party', 'external api', 'service', 'saas',
            'platform', 'library', 'package', 'npm', 'maven',
            'outage', 'downtime'
        ],
        BlockerCategory.DESIGN_DECISION: [
            'design', 'architecture', 'architect', 'decision',
            'approach', 'solution', 'strategy', 'direction',
            'tda', 'hld', 'lld', 'diagram'
        ]
    }

    CATEGORY_DISPLAY_NAMES = {
        BlockerCategory.EXTERNAL_DEPENDENCY: "External Dependency",
        BlockerCategory.ENVIRONMENT: "Environment/Infrastructure",
        BlockerCategory.UNCLEAR_REQUIREMENTS: "Unclear Requirements",
        BlockerCategory.TECHNICAL_DEBT: "Technical Debt",
        BlockerCategory.RESOURCE_UNAVAILABLE: "Resource Unavailable",
        BlockerCategory.WAITING_FOR_REVIEW: "Waiting for Review",
        BlockerCategory.ACCESS_PERMISSION: "Access/Permissions",
        BlockerCategory.THIRD_PARTY: "Third Party Service",
        BlockerCategory.DESIGN_DECISION: "Design Decision Needed",
        BlockerCategory.OTHER: "Other/Unknown"
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def analyze(
        self,
        issues: List[SprintIssue],
        sprint_info: SprintInfo,
        comments_data: Optional[List[Dict[str, Any]]] = None
    ) -> SentimentClusteringReport:
        """
        Run sentiment and blocker clustering analysis.

        Args:
            issues: Sprint issues
            sprint_info: Sprint information
            comments_data: Optional preloaded comments (issue_key -> comments)

        Returns:
            SentimentClusteringReport with full analysis
        """
        # Analyze sentiments
        issue_sentiments = self._analyze_sentiments(issues, comments_data)

        # Calculate team sentiment
        team_sentiment, sentiment_score, sentiment_trend = self._calculate_team_sentiment(
            issue_sentiments
        )

        # Identify burnout risks
        burnout_items = [i for i in issue_sentiments if i.burnout_risk]

        # Count negative sentiments
        negative_count = len([
            i for i in issue_sentiments
            if i.overall_sentiment in [SentimentLevel.NEGATIVE, SentimentLevel.FRUSTRATED]
        ])

        # Analyze blockers
        blockers = self._identify_blockers(issues)
        categorized = self._categorize_blockers(blockers)
        distribution = self._calculate_pareto(categorized)

        # Get top root cause
        top_cause = distribution[0].category if distribution else None

        # Generate recommendations
        sentiment_recs = self._generate_sentiment_recommendations(
            team_sentiment, burnout_items, sentiment_trend
        )
        blocker_recs = self._generate_blocker_recommendations(distribution)

        return SentimentClusteringReport(
            generated_at=datetime.now(),
            sprint_info=sprint_info,
            team_sentiment=team_sentiment,
            sentiment_score=sentiment_score,
            sentiment_trend=sentiment_trend,
            burnout_risk_items=burnout_items,
            burnout_risk_count=len(burnout_items),
            issue_sentiments=issue_sentiments,
            negative_sentiment_count=negative_count,
            total_blockers=len(blockers),
            categorized_blockers=categorized,
            blocker_distribution=distribution,
            top_root_cause=top_cause,
            sentiment_recommendations=sentiment_recs,
            blocker_recommendations=blocker_recs
        )

    def _analyze_sentiments(
        self,
        issues: List[SprintIssue],
        comments_data: Optional[List[Dict[str, Any]]]
    ) -> List[IssueSentimentTrend]:
        """Analyze sentiment for each issue"""
        results = []

        for issue in issues:
            # Get comments for this issue (simulate if not provided)
            comments = self._get_comments_for_issue(issue, comments_data)

            # Analyze each comment
            sentiments = []
            for comment in comments:
                sentiment = self._analyze_comment(issue.key, comment)
                sentiments.append(sentiment)

            # Calculate overall sentiment
            positive = len([s for s in sentiments if s.sentiment == SentimentLevel.POSITIVE])
            negative = len([s for s in sentiments if s.sentiment == SentimentLevel.NEGATIVE])
            frustrated = len([s for s in sentiments if s.sentiment == SentimentLevel.FRUSTRATED])

            # Determine overall
            if frustrated >= 2 or (frustrated >= 1 and negative >= 1):
                overall = SentimentLevel.FRUSTRATED
            elif negative > positive:
                overall = SentimentLevel.NEGATIVE
            elif positive > negative:
                overall = SentimentLevel.POSITIVE
            else:
                overall = SentimentLevel.NEUTRAL

            # Determine trend
            if len(sentiments) >= 3:
                recent = sentiments[-2:]
                older = sentiments[:-2]
                recent_neg = len([s for s in recent if s.sentiment in [SentimentLevel.NEGATIVE, SentimentLevel.FRUSTRATED]])
                older_neg = len([s for s in older if s.sentiment in [SentimentLevel.NEGATIVE, SentimentLevel.FRUSTRATED]]) / max(1, len(older))

                if recent_neg > older_neg:
                    trend = "declining"
                elif recent_neg < older_neg:
                    trend = "improving"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            # Burnout risk detection
            burnout = frustrated >= 2 or (overall == SentimentLevel.FRUSTRATED)
            burnout_reason = None
            if burnout:
                if frustrated >= 2:
                    burnout_reason = f"{frustrated} frustrated comments detected"
                elif issue.is_stuck:
                    burnout_reason = f"Stuck item with negative sentiment"
                else:
                    burnout_reason = "Escalating frustration detected"

            results.append(IssueSentimentTrend(
                issue_key=issue.key,
                summary=issue.summary,
                assignee=issue.assignee,
                total_comments=len(comments),
                positive_count=positive,
                negative_count=negative,
                frustrated_count=frustrated,
                overall_sentiment=overall,
                trend=trend,
                burnout_risk=burnout,
                burnout_reason=burnout_reason
            ))

        return results

    def _get_comments_for_issue(
        self,
        issue: SprintIssue,
        comments_data: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Get or simulate comments for an issue"""
        if comments_data:
            return [c for c in comments_data if c.get('issue_key') == issue.key]

        # Simulate comments based on issue state (for demo/testing)
        comments = []

        if issue.is_stuck:
            comments.append({
                'author': issue.assignee or 'Team Member',
                'timestamp': datetime.now() - timedelta(days=1),
                'text': f"Still waiting for resolution. This has been stuck for {issue.days_in_current_status} days."
            })
            if issue.days_in_current_status > 5:
                comments.append({
                    'author': issue.assignee or 'Team Member',
                    'timestamp': datetime.now(),
                    'text': "Yet again delayed. This is frustrating. Need help ASAP!"
                })

        if 'blocked' in issue.status.lower():
            comments.append({
                'author': 'Team Member',
                'timestamp': datetime.now() - timedelta(days=2),
                'text': "Blocked waiting for external dependency to be resolved."
            })

        if issue.phase == Phase.DONE:
            comments.append({
                'author': issue.assignee or 'Team Member',
                'timestamp': datetime.now() - timedelta(hours=12),
                'text': "Done! Thanks for the help. Great collaboration."
            })

        return comments

    def _analyze_comment(
        self,
        issue_key: str,
        comment: Dict[str, Any]
    ) -> CommentSentiment:
        """Analyze sentiment of a single comment"""
        text = comment.get('text', '').lower()

        # Check for patterns
        positive_matches = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
        negative_matches = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)
        frustrated_indicators = [kw for kw in self.FRUSTRATED_KEYWORDS if kw in text]

        # Calculate score
        score = (positive_matches - negative_matches - len(frustrated_indicators) * 1.5)
        score = max(-1, min(1, score / 3))  # Normalize to -1 to 1

        # Determine sentiment
        if frustrated_indicators or score < -0.5:
            sentiment = SentimentLevel.FRUSTRATED
        elif score < 0:
            sentiment = SentimentLevel.NEGATIVE
        elif score > 0.3:
            sentiment = SentimentLevel.POSITIVE
        else:
            sentiment = SentimentLevel.NEUTRAL

        # Is it blocker related?
        is_blocker = any(
            kw in text for kw in ['block', 'stuck', 'wait', 'depend', 'delay']
        )

        return CommentSentiment(
            issue_key=issue_key,
            author=comment.get('author', 'Unknown'),
            timestamp=comment.get('timestamp', datetime.now()),
            text=comment.get('text', ''),
            sentiment=sentiment,
            sentiment_score=score,
            frustration_indicators=frustrated_indicators,
            is_blocker_related=is_blocker
        )

    def _calculate_team_sentiment(
        self,
        issue_sentiments: List[IssueSentimentTrend]
    ) -> Tuple[SentimentLevel, float, str]:
        """Calculate overall team sentiment"""
        if not issue_sentiments:
            return SentimentLevel.NEUTRAL, 0.0, "stable"

        # Count by sentiment
        counts = Counter(i.overall_sentiment for i in issue_sentiments)
        total = len(issue_sentiments)

        # Calculate weighted score
        score_weights = {
            SentimentLevel.POSITIVE: 1,
            SentimentLevel.NEUTRAL: 0,
            SentimentLevel.NEGATIVE: -0.5,
            SentimentLevel.FRUSTRATED: -1
        }

        score = sum(
            score_weights[level] * count / total
            for level, count in counts.items()
        )

        # Determine overall
        frustrated_pct = counts.get(SentimentLevel.FRUSTRATED, 0) / total
        negative_pct = counts.get(SentimentLevel.NEGATIVE, 0) / total

        if frustrated_pct > 0.2 or (frustrated_pct + negative_pct) > 0.4:
            team = SentimentLevel.FRUSTRATED
        elif (frustrated_pct + negative_pct) > 0.2:
            team = SentimentLevel.NEGATIVE
        elif counts.get(SentimentLevel.POSITIVE, 0) > total * 0.5:
            team = SentimentLevel.POSITIVE
        else:
            team = SentimentLevel.NEUTRAL

        # Determine trend
        trend_counts = Counter(i.trend for i in issue_sentiments if i.trend != "stable")
        if trend_counts.get("declining", 0) > trend_counts.get("improving", 0):
            trend = "declining"
        elif trend_counts.get("improving", 0) > trend_counts.get("declining", 0):
            trend = "improving"
        else:
            trend = "stable"

        return team, score, trend

    def _identify_blockers(self, issues: List[SprintIssue]) -> List[SprintIssue]:
        """Identify blocked items"""
        blockers = []

        for issue in issues:
            is_blocked = (
                issue.is_stuck or
                'block' in issue.status.lower() or
                any(label.lower() in ['blocked', 'blocker', 'impediment']
                    for label in issue.labels)
            )
            if is_blocked:
                blockers.append(issue)

        return blockers

    def _categorize_blockers(
        self,
        blockers: List[SprintIssue]
    ) -> List[CategorizedBlocker]:
        """Categorize blockers by root cause"""
        categorized = []

        for issue in blockers:
            category, confidence, keywords = self._detect_category(issue)

            impact = issue.story_points * issue.days_in_current_status

            categorized.append(CategorizedBlocker(
                issue_key=issue.key,
                summary=issue.summary,
                assignee=issue.assignee,
                status=issue.status,
                days_blocked=issue.days_in_current_status,
                category=category,
                category_confidence=confidence,
                detected_keywords=keywords,
                story_points=issue.story_points,
                impact_score=impact
            ))

        return categorized

    def _detect_category(
        self,
        issue: SprintIssue
    ) -> Tuple[BlockerCategory, float, List[str]]:
        """Detect blocker category from issue text"""
        # Combine all searchable text
        search_text = f"{issue.summary} {issue.status} {' '.join(issue.labels)}".lower()

        category_scores: Dict[BlockerCategory, Tuple[int, List[str]]] = {}

        for category, patterns in self.BLOCKER_PATTERNS.items():
            matches = [p for p in patterns if p in search_text]
            if matches:
                category_scores[category] = (len(matches), matches)

        if not category_scores:
            return BlockerCategory.OTHER, 0.0, []

        # Pick highest scoring category
        best = max(category_scores.items(), key=lambda x: x[1][0])
        category = best[0]
        match_count = best[1][0]
        keywords = best[1][1]

        # Calculate confidence
        confidence = min(1.0, match_count / 3)

        return category, confidence, keywords

    def _calculate_pareto(
        self,
        categorized: List[CategorizedBlocker]
    ) -> List[BlockerDistribution]:
        """Calculate Pareto distribution of blocker categories"""
        if not categorized:
            return []

        # Group by category
        by_category: Dict[BlockerCategory, List[CategorizedBlocker]] = {}
        for blocker in categorized:
            if blocker.category not in by_category:
                by_category[blocker.category] = []
            by_category[blocker.category].append(blocker)

        # Calculate distribution
        total = len(categorized)
        distributions = []

        for category, items in by_category.items():
            count = len(items)
            sp_blocked = sum(b.story_points for b in items)
            days_blocked = sum(b.days_blocked for b in items)

            distributions.append(BlockerDistribution(
                category=category,
                display_name=self.CATEGORY_DISPLAY_NAMES[category],
                count=count,
                percentage=count / total * 100,
                total_sp_blocked=sp_blocked,
                total_days_blocked=days_blocked,
                avg_days_per_blocker=days_blocked / count if count > 0 else 0,
                examples=[b.issue_key for b in items]
            ))

        # Sort by count (Pareto - most common first)
        distributions.sort(key=lambda x: -x.count)

        return distributions

    def _generate_sentiment_recommendations(
        self,
        team_sentiment: SentimentLevel,
        burnout_items: List[IssueSentimentTrend],
        trend: str
    ) -> List[str]:
        """Generate sentiment-based recommendations"""
        recs = []

        if team_sentiment == SentimentLevel.FRUSTRATED:
            recs.append("🚨 Team frustration detected - schedule immediate check-in with affected members")

        if burnout_items:
            assignees = set(i.assignee for i in burnout_items if i.assignee)
            if assignees:
                recs.append(f"⚠️ Burnout risk identified for: {', '.join(assignees)}")
                recs.append("Consider redistributing workload or providing additional support")

        if trend == "declining":
            recs.append("📉 Sentiment trending negative - investigate root causes in standup")

        if team_sentiment == SentimentLevel.POSITIVE:
            recs.append("✅ Positive team sentiment - continue current practices")

        if not recs:
            recs.append("😊 Team sentiment is stable")

        return recs

    def _generate_blocker_recommendations(
        self,
        distribution: List[BlockerDistribution]
    ) -> List[str]:
        """Generate blocker-based recommendations"""
        recs = []

        if not distribution:
            recs.append("✅ No significant blockers detected")
            return recs

        # Top cause recommendations
        top = distribution[0]

        category_recs = {
            BlockerCategory.EXTERNAL_DEPENDENCY:
                "📤 Escalate external dependencies to PM for prioritization",
            BlockerCategory.ENVIRONMENT:
                "🔧 Engage DevOps to resolve environment issues",
            BlockerCategory.UNCLEAR_REQUIREMENTS:
                "📝 Schedule refinement session with BA/PO",
            BlockerCategory.TECHNICAL_DEBT:
                "🔨 Allocate sprint capacity for tech debt reduction",
            BlockerCategory.RESOURCE_UNAVAILABLE:
                "👥 Review team capacity and backup assignments",
            BlockerCategory.WAITING_FOR_REVIEW:
                "⏰ Set up dedicated review slots or pair programming",
            BlockerCategory.ACCESS_PERMISSION:
                "🔐 Pre-request access in sprint planning",
            BlockerCategory.THIRD_PARTY:
                "📞 Contact vendor support and establish SLAs",
            BlockerCategory.DESIGN_DECISION:
                "📐 Schedule architecture review meeting"
        }

        if top.category in category_recs:
            recs.append(f"Top blocker cause: {top.display_name} ({top.count} items)")
            recs.append(category_recs[top.category])

        # Pareto analysis
        if len(distribution) >= 2:
            top_two_pct = sum(d.percentage for d in distribution[:2])
            if top_two_pct > 70:
                recs.append(f"📊 Pareto: Top 2 causes account for {top_two_pct:.0f}% of blockers")

        return recs

    def get_pareto_chart_data(
        self,
        report: SentimentClusteringReport
    ) -> Dict[str, Any]:
        """Get data for Pareto chart visualization"""
        distribution = report.blocker_distribution

        # Calculate cumulative percentage
        cumulative = 0
        chart_data = []

        for dist in distribution:
            cumulative += dist.percentage
            chart_data.append({
                'category': dist.display_name,
                'count': dist.count,
                'percentage': round(dist.percentage, 1),
                'cumulative': round(cumulative, 1),
                'sp_blocked': dist.total_sp_blocked
            })

        return {
            'chart_type': 'pareto',
            'title': 'Blocker Root Cause Analysis',
            'data': chart_data,
            'total_blockers': report.total_blockers,
            'top_cause': report.top_root_cause.value if report.top_root_cause else None
        }

