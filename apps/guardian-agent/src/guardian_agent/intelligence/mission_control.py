"""
Mission Control Dashboard - Single Pane of Glass for Platform Health

Comprehensive dashboard providing real-time visibility into platform
health, performance, costs, and strategic metrics.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from hive_logging import get_logger

from .analytics_engine import AnalyticsEngine, Anomaly, Insight, TrendAnalysis
from .data_unification import MetricsWarehouse, MetricType

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Overall health status levels."""

    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"  # 80-89%
    WARNING = "warning"  # 70-79%
    CRITICAL = "critical"  # Below 70%
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a platform component."""

    name: str
    status: HealthStatus
    score: float  # 0.0 to 100.0

    # Metrics contributing to health
    uptime: float = 0.0
    error_rate: float = 0.0
    response_time: float = 0.0
    resource_usage: float = 0.0

    # Issues and recommendations
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PlatformHealthScore:
    """Overall platform health assessment."""

    overall_score: float  # 0.0 to 100.0
    overall_status: HealthStatus

    # Component breakdown
    components: dict[str, ComponentHealth] = field(default_factory=dict)

    # Key metrics
    total_uptime: float = 0.0
    average_response_time: float = 0.0
    total_error_rate: float = 0.0

    # Trends
    score_trend: str = "stable"  # improving, stable, degrading
    trend_percentage: float = 0.0

    # Alerts
    critical_issues: int = 0
    warnings: int = 0

    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CostIntelligence:
    """Real-time cost tracking and projections."""

    # Current costs
    daily_cost: float = 0.0
    monthly_cost: float = 0.0
    projected_monthly_cost: float = 0.0

    # Budget tracking
    daily_budget: float = 100.0
    monthly_budget: float = 3000.0
    budget_utilization: float = 0.0
    days_until_budget_exhausted: int | None = None

    # Cost breakdown
    cost_by_service: dict[str, float] = field(default_factory=dict)
    cost_by_model: dict[str, float] = field(default_factory=dict)

    # Trends and projections
    cost_trend: str = "stable"
    trend_percentage: float = 0.0

    # Optimization opportunities
    potential_savings: float = 0.0
    optimization_recommendations: list[str] = field(default_factory=list)

    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DeveloperVelocity:
    """Developer productivity and velocity metrics."""

    # Cycle times
    avg_pr_cycle_time: float = 0.0  # hours
    avg_ci_cd_time: float = 0.0  # minutes
    avg_deployment_time: float = 0.0  # minutes

    # Success rates
    ci_cd_pass_rate: float = 0.0  # percentage
    deployment_success_rate: float = 0.0  # percentage

    # Code quality
    code_quality_score: float = 0.0  # 0-100
    golden_rules_compliance: float = 0.0  # percentage
    test_coverage: float = 0.0  # percentage

    # Productivity indicators
    commits_per_day: float = 0.0
    prs_per_week: float = 0.0

    # Bottlenecks
    slowest_pipeline: str = ""
    slowest_pipeline_time: float = 0.0

    # Trends
    velocity_trend: str = "stable"
    trend_percentage: float = 0.0

    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ArchitecturalHealth:
    """Architectural integrity and compliance metrics."""

    # Overall compliance
    golden_rules_compliance: float = 0.0  # percentage (0-100)
    compliance_trend: str = "stable"  # improving, stable, degrading

    # Rule compliance breakdown
    critical_rules_passed: int = 0
    critical_rules_total: int = 0
    medium_rules_passed: int = 0
    medium_rules_total: int = 0
    low_rules_passed: int = 0
    low_rules_total: int = 0

    # Technical debt
    total_violations: int = 0
    technical_debt_score: float = 0.0  # 0-100 (higher = more debt)
    debt_trend: str = "stable"

    # Violation categories
    violations_by_category: dict[str, int] = field(default_factory=dict)
    violations_by_severity: dict[str, int] = field(default_factory=dict)
    violations_by_package: dict[str, int] = field(default_factory=dict)

    # Most critical issues
    top_violations: list[str] = field(default_factory=list)
    packages_needing_attention: list[str] = field(default_factory=list)

    # Recommendations
    immediate_actions: list[str] = field(default_factory=list)
    estimated_fix_effort: str = ""  # e.g., "2-3 days", "1 week"

    # Metadata
    last_scan_time: datetime | None = None
    scan_type: str = "unknown"  # comprehensive, quick, etc.

    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CustomerHealthScore:
    """Customer health and satisfaction metrics."""

    # Overall customer health
    overall_health_score: float = 0.0  # 0-100 composite score
    health_status: HealthStatus = HealthStatus.UNKNOWN
    health_trend: str = "stable"  # improving, stable, degrading

    # User engagement metrics
    daily_active_users: int = 0
    weekly_active_users: int = 0
    monthly_active_users: int = 0
    avg_session_duration: float = 0.0  # minutes
    engagement_trend: str = "stable"

    # Retention metrics
    user_retention_7d: float = 0.0  # 7-day retention percentage
    user_retention_30d: float = 0.0  # 30-day retention percentage
    churn_rate: float = 0.0  # monthly churn percentage

    # Satisfaction metrics
    nps_score: float = 0.0  # Net Promoter Score
    satisfaction_level: str = "unknown"  # poor, fair, good, excellent
    customer_feedback_score: float = 0.0  # 1-5 scale

    # Support metrics
    avg_first_response_time: float = 0.0  # hours
    support_ticket_resolution_rate: float = 0.0  # percentage
    open_high_priority_tickets: int = 0

    # At-risk customers
    customers_at_risk: list[str] = field(default_factory=list)
    escalated_issues: list[str] = field(default_factory=list)

    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeaturePerformanceData:
    """Individual feature performance metrics."""

    name: str
    adoption_rate: float = 0.0  # percentage of users using feature
    usage_frequency: str = "unknown"  # daily, weekly, monthly, rare
    user_segment: str = "all"  # enterprise, professional, free, etc.

    # Cost metrics
    operational_cost: float = 0.0  # monthly cost in USD
    cost_per_user: float = 0.0  # cost per active user
    cost_trend: str = "stable"

    # Performance metrics
    satisfaction_score: float = 0.0  # 1-5 user satisfaction
    roi_score: float = 0.0  # calculated ROI metric
    performance_status: str = "unknown"  # high_value, moderate_value, low_value

    # Metadata
    review_required: bool = False
    reason: str = ""  # reason for review if required
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeaturePerformanceMatrix:
    """Feature adoption vs operational cost analysis."""

    # Feature data
    features: list[FeaturePerformanceData] = field(default_factory=list)

    # Matrix analysis
    high_value_features: list[str] = field(default_factory=list)  # high adoption, reasonable cost
    underperforming_features: list[str] = field(default_factory=list)  # low adoption, high cost
    emerging_features: list[str] = field(default_factory=list)  # growing adoption
    cost_efficient_features: list[str] = field(default_factory=list)  # low cost, good adoption

    # Summary metrics
    total_feature_cost: float = 0.0
    avg_adoption_rate: float = 0.0
    cost_optimization_potential: float = 0.0  # potential monthly savings

    # Recommendations
    features_to_promote: list[str] = field(default_factory=list)
    features_to_optimize: list[str] = field(default_factory=list)
    features_to_deprecate: list[str] = field(default_factory=list)

    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RevenueCorrelationData:
    """Revenue and cost correlation analysis."""

    # Revenue metrics
    monthly_recurring_revenue: float = 0.0
    revenue_growth_rate: float = 0.0  # monthly percentage
    revenue_trend: str = "stable"

    # Cost metrics
    total_platform_cost: float = 0.0  # monthly operational cost
    cost_per_revenue_dollar: float = 0.0  # operational cost per $ of revenue
    cost_efficiency_trend: str = "stable"

    # Business metrics
    customer_acquisition_cost: float = 0.0
    customer_lifetime_value: float = 0.0
    ltv_cac_ratio: float = 0.0

    # Conversion metrics
    trial_to_paid_conversion: float = 0.0  # percentage
    conversion_trend: str = "stable"

    # Correlation insights
    revenue_cost_correlation: float = 0.0  # -1 to 1 correlation coefficient
    cost_efficiency_score: float = 0.0  # 0-100 efficiency score
    profitability_trend: str = "stable"

    # Projections
    projected_monthly_revenue: float = 0.0
    projected_monthly_cost: float = 0.0
    projected_profit_margin: float = 0.0

    # Recommendations
    cost_optimization_opportunities: list[str] = field(default_factory=list)
    revenue_growth_opportunities: list[str] = field(default_factory=list)

    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ComponentScorecard:
    """Individual component certification scorecard."""

    name: str
    component_type: str  # "package" or "app"
    overall_score: float = 0.0
    certification_level: str = "Non-Certified"

    # Assessment criteria scores (v2.0 standards)
    technical_excellence: float = 0.0  # /40 points
    operational_readiness: float = 0.0  # /30 points
    platform_integration: float = 0.0  # /20 points
    innovation: float = 0.0  # /10 points

    # Detailed quality metrics
    code_quality_score: float = 0.0
    test_coverage: float = 0.0
    deployment_readiness: float = 0.0
    toolkit_utilization: float = 0.0
    monitoring_score: float = 0.0

    # Status indicators
    certification_ready: bool = False
    action_required: str = "maintenance"
    urgency: str = "low"
    improvement_potential: float = 0.0
    certification_gap: str = ""

    # Specific compliance issues
    golden_rules_violations: int = 0
    missing_tests: int = 0
    deployment_blockers: list[str] = field(default_factory=list)
    toolkit_gaps: list[str] = field(default_factory=list)
    quality_issues: list[str] = field(default_factory=list)

    # Progress tracking
    last_audit_date: datetime = field(default_factory=datetime.utcnow)
    audit_version: str = "v2.0"
    improvement_trend: str = "stable"  # "improving", "declining", "stable"

    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CertificationReadiness:
    """Overall certification readiness status for the platform."""

    # Platform-wide metrics
    overall_platform_score: float = 0.0
    certified_components: int = 0
    total_components: int = 0
    certification_rate: float = 0.0

    # Certification level breakdown
    senior_architects: int = 0  # 90+ points
    certified_architects: int = 0  # 80-89 points
    associate_architects: int = 0  # 70-79 points
    non_certified: int = 0  # <70 points

    # Component scorecards
    component_scorecards: list[ComponentScorecard] = field(default_factory=list)

    # Critical issues requiring immediate attention
    critical_components: list[str] = field(default_factory=list)
    high_priority_issues: list[str] = field(default_factory=list)

    # Progress tracking
    total_golden_rules_violations: int = 0
    total_missing_tests: int = 0
    components_production_ready: int = 0
    components_needing_immediate_action: int = 0

    # Burndown metrics for Operation Bedrock
    target_completion_date: datetime | None = None
    estimated_effort_days: int = 0
    progress_percentage: float = 0.0
    velocity_points_per_week: float = 0.0

    # Trends and projections
    score_trend: str = "stable"  # "improving", "declining", "stable"
    weekly_improvement: float = 0.0
    projected_certification_date: datetime | None = None

    # Top recommendations from Oracle
    top_recommendations: list[str] = field(default_factory=list)
    quick_wins: list[str] = field(default_factory=list)  # Low effort, high impact

    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DashboardData:
    """Complete dashboard data structure."""

    platform_health: PlatformHealthScore
    cost_intelligence: CostIntelligence
    developer_velocity: DeveloperVelocity
    architectural_health: ArchitecturalHealth

    # Business intelligence components
    customer_health: CustomerHealthScore
    feature_performance: FeaturePerformanceMatrix
    revenue_correlation: RevenueCorrelationData

    # Certification readiness (Operation Bedrock)
    certification_readiness: CertificationReadiness

    # Recent insights and alerts
    critical_insights: list[Insight] = field(default_factory=list)
    recent_anomalies: list[Anomaly] = field(default_factory=list)
    trending_metrics: list[TrendAnalysis] = field(default_factory=list)

    # System status
    active_services: int = 0
    total_services: int = 0
    active_alerts: int = 0

    generated_at: datetime = field(default_factory=datetime.utcnow)
    refresh_interval: int = 300  # seconds


class MissionControlDashboard:
    """
    Mission Control Dashboard - Platform Intelligence Hub

    Provides real-time, comprehensive view of platform health,
    performance, costs, and strategic recommendations.
    """

    def __init__(self, warehouse: MetricsWarehouse, analytics: AnalyticsEngine):
        self.warehouse = warehouse
        self.analytics = analytics

        # Configuration
        self.health_thresholds = {"excellent": 90.0, "good": 80.0, "warning": 70.0, "critical": 0.0}

        # Cache for expensive computations
        self._dashboard_cache: DashboardData | None = None
        self._cache_expiry: datetime | None = None
        self._cache_ttl = 300  # 5 minutes

    async def get_dashboard_data_async(self, force_refresh: bool = False) -> DashboardData:
        """Get complete dashboard data with caching."""

        # Check cache
        if not force_refresh and self._dashboard_cache and self._cache_expiry:
            if datetime.utcnow() < self._cache_expiry:
                return self._dashboard_cache

        # Generate fresh dashboard data
        dashboard_data = await self._generate_dashboard_data_async()

        # Update cache
        self._dashboard_cache = dashboard_data
        self._cache_expiry = datetime.utcnow() + timedelta(seconds=self._cache_ttl)

        return dashboard_data

    async def _generate_dashboard_data_async(self) -> DashboardData:
        """Generate complete dashboard data."""

        # Gather all data in parallel
        health_task = asyncio.create_task(self._calculate_platform_health_async()),
        cost_task = asyncio.create_task(self._calculate_cost_intelligence_async()),
        velocity_task = asyncio.create_task(self._calculate_developer_velocity_async()),
        architectural_task = asyncio.create_task(self._calculate_architectural_health_async())

        # Business intelligence tasks
        customer_health_task = asyncio.create_task(self._calculate_customer_health_async()),
        feature_performance_task = asyncio.create_task(self._calculate_feature_performance_async()),
        revenue_correlation_task = asyncio.create_task(self._calculate_revenue_correlation_async())

        # Certification readiness task (Operation Bedrock)
        certification_task = asyncio.create_task(self._calculate_certification_readiness_async()),

        insights_task = asyncio.create_task(self.analytics.generate_insights_async())

        # Wait for all tasks
        platform_health = await health_task,
        cost_intelligence = await cost_task,
        developer_velocity = await velocity_task,
        architectural_health = await architectural_task

        # Business intelligence data
        customer_health = await customer_health_task,
        feature_performance = await feature_performance_task,
        revenue_correlation = await revenue_correlation_task

        # Certification readiness data
        certification_readiness = await certification_task,

        insights = await insights_task

        # Separate insights by severity
        critical_insights = [i for i in insights if i.severity.value in ["critical", "high"]][:5]

        # Get recent anomalies
        recent_anomalies = await self.analytics.detect_anomalies_async(hours=24),
        recent_anomalies = recent_anomalies[:10]  # Top 10

        # Get trending metrics
        trending_metrics = await self.analytics.analyze_trends_async(hours=24),
        trending_metrics = [t for t in trending_metrics if t.confidence > 0.7][:5]

        # Count active services and alerts
        active_services, total_services = await self._count_services_async()
        active_alerts = len([i for i in insights if i.severity.value in ["critical", "high"]])

        return DashboardData(
            platform_health=platform_health,
            cost_intelligence=cost_intelligence,
            developer_velocity=developer_velocity,
            architectural_health=architectural_health,
            customer_health=customer_health,
            feature_performance=feature_performance,
            revenue_correlation=revenue_correlation,
            certification_readiness=certification_readiness,
            critical_insights=critical_insights,
            recent_anomalies=recent_anomalies,
            trending_metrics=trending_metrics,
            active_services=active_services,
            total_services=total_services,
            active_alerts=active_alerts,
        )

    async def _calculate_platform_health_async(self) -> PlatformHealthScore:
        """Calculate overall platform health score."""

        # Get health metrics for different components
        components = {}

        # Production services health
        prod_health = await self._calculate_component_health_async("production_services")
        components["production_services"] = prod_health

        # AI services health
        ai_health = await self._calculate_component_health_async("ai_services")
        components["ai_services"] = ai_health

        # Database health
        db_health = await self._calculate_component_health_async("database")
        components["database"] = db_health

        # CI/CD pipeline health
        cicd_health = await self._calculate_component_health_async("cicd")
        components["cicd"] = cicd_health

        # Calculate overall score (weighted average)
        weights = {"production_services": 0.4, "ai_services": 0.3, "database": 0.2, "cicd": 0.1}

        overall_score = sum(components[name].score * weights.get(name, 0.25) for name in components)

        # Determine overall status
        overall_status = self._score_to_health_status(overall_score)

        # Calculate aggregate metrics
        total_uptime = sum(c.uptime for c in components.values()) / len(components),
        average_response_time = sum(c.response_time for c in components.values()) / len(components),
        total_error_rate = sum(c.error_rate for c in components.values()) / len(components)

        # Count issues
        critical_issues = sum(len(c.issues) for c in components.values()),
        warnings = len([c for c in components.values() if c.status == HealthStatus.WARNING])

        # Calculate trend (simplified)
        score_trend = "stable",
        trend_percentage = 0.0

        return PlatformHealthScore(
            overall_score=overall_score,
            overall_status=overall_status,
            components=components,
            total_uptime=total_uptime,
            average_response_time=average_response_time,
            total_error_rate=total_error_rate,
            score_trend=score_trend,
            trend_percentage=trend_percentage,
            critical_issues=critical_issues,
            warnings=warnings,
        )

    async def _calculate_component_health_async(self, component_name: str) -> ComponentHealth:
        """Calculate health for a specific component."""

        # Get recent metrics for this component
        try:
            # This is a simplified implementation
            # In reality, you'd query specific metrics for each component

            if component_name == "production_services":
                uptime = 99.5,
                error_rate = 0.1,
                response_time = 150.0,
                resource_usage = 45.0
            elif component_name == "ai_services":
                uptime = 98.8,
                error_rate = 0.5,
                response_time = 300.0,
                resource_usage = 60.0
            elif component_name == "database":
                uptime = 99.9,
                error_rate = 0.05,
                response_time = 50.0,
                resource_usage = 70.0
            elif component_name == "cicd":
                uptime = 95.0,
                error_rate = 5.0,
                response_time = 180.0,
                resource_usage = 30.0
            else:
                uptime = 90.0,
                error_rate = 1.0,
                response_time = 200.0,
                resource_usage = 50.0

            # Calculate component score
            score = (
                uptime * 0.4  # Uptime is most important,
                + (100 - error_rate) * 0.3  # Lower error rate is better,
                + max(0, 100 - response_time / 10) * 0.2  # Lower response time is better,
                + (100 - resource_usage) * 0.1  # Lower resource usage is better
            )

            status = self._score_to_health_status(score)

            # Generate issues and recommendations
            issues = [],
            recommendations = []

            if error_rate > 1.0:
                issues.append(f"High error rate: {error_rate}%")
                recommendations.append("Investigate error patterns")

            if response_time > 500:
                issues.append(f"Slow response time: {response_time}ms")
                recommendations.append("Optimize performance")

            if resource_usage > 80:
                issues.append(f"High resource usage: {resource_usage}%")
                recommendations.append("Consider scaling resources")

            return ComponentHealth(
                name=component_name,
                status=status,
                score=score,
                uptime=uptime,
                error_rate=error_rate,
                response_time=response_time,
                resource_usage=resource_usage,
                issues=issues,
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error(f"Failed to calculate health for {component_name}: {e}")
            return ComponentHealth(name=component_name, status=HealthStatus.UNKNOWN, score=0.0)

    def _score_to_health_status(self, score: float) -> HealthStatus:
        """Convert numeric score to health status."""
        if score >= self.health_thresholds["excellent"]:
            return HealthStatus.EXCELLENT
        elif score >= self.health_thresholds["good"]:
            return HealthStatus.GOOD
        elif score >= self.health_thresholds["warning"]:
            return HealthStatus.WARNING
        else:
            return HealthStatus.CRITICAL

    async def _calculate_cost_intelligence_async(self) -> CostIntelligence:
        """Calculate cost intelligence metrics."""

        try:
            # Get cost metrics from the last 24 hours and month
            cost_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.AI_COST],
                start_time=datetime.utcnow() - timedelta(days=30),
                limit=10000,
            )

            if not cost_metrics:
                return CostIntelligence()

            # Calculate daily and monthly costs
            now = datetime.utcnow(),
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            daily_cost = sum(
                (
                    float(m.value)
                    if isinstance(m.value, (int, float))
                    else float(m.value.get("cost_usd", 0)) if isinstance(m.value, dict) else 0
                )
                for m in cost_metrics
                if m.timestamp >= today_start
            )

            monthly_cost = sum(
                (
                    float(m.value)
                    if isinstance(m.value, (int, float))
                    else float(m.value.get("cost_usd", 0)) if isinstance(m.value, dict) else 0
                )
                for m in cost_metrics
                if m.timestamp >= month_start
            )

            # Project monthly cost based on daily average
            days_in_month = (now.replace(day=28) + timedelta(days=4) - now.replace(day=1)).days,
            days_elapsed = (now - month_start).days + 1,
            daily_average = monthly_cost / days_elapsed if days_elapsed > 0 else 0,
            projected_monthly_cost = daily_average * days_in_month

            # Budget calculations
            daily_budget = 100.0  # Default budget,
            monthly_budget = 3000.0  # Default budget,
            budget_utilization = (monthly_cost / monthly_budget) * 100 if monthly_budget > 0 else 0,

            days_until_budget_exhausted = None
            if daily_average > 0:
                remaining_budget = monthly_budget - monthly_cost,
                days_until_budget_exhausted = int(remaining_budget / daily_average)

            # Cost breakdown (simplified)
            cost_by_service = {"ai_services": monthly_cost * 0.8, "other": monthly_cost * 0.2}
            cost_by_model = {"gpt-4": monthly_cost * 0.6, "gpt-3.5": monthly_cost * 0.4}

            # Trend calculation (simplified)
            cost_trend = "stable",
            trend_percentage = 0.0

            # Optimization recommendations
            optimization_recommendations = [],
            potential_savings = 0.0

            if budget_utilization > 80:
                optimization_recommendations.append("Review high-cost operations")
                potential_savings = monthly_cost * 0.2

            if daily_cost > daily_budget:
                optimization_recommendations.append("Implement daily cost controls")

            return CostIntelligence(
                daily_cost=daily_cost,
                monthly_cost=monthly_cost,
                projected_monthly_cost=projected_monthly_cost,
                daily_budget=daily_budget,
                monthly_budget=monthly_budget,
                budget_utilization=budget_utilization,
                days_until_budget_exhausted=days_until_budget_exhausted,
                cost_by_service=cost_by_service,
                cost_by_model=cost_by_model,
                cost_trend=cost_trend,
                trend_percentage=trend_percentage,
                potential_savings=potential_savings,
                optimization_recommendations=optimization_recommendations,
            )

        except Exception as e:
            logger.error(f"Failed to calculate cost intelligence: {e}")
            return CostIntelligence()

    async def _calculate_developer_velocity_async(self) -> DeveloperVelocity:
        """Calculate developer velocity metrics."""

        try:
            # Get CI/CD metrics
            await self.warehouse.query_metrics_async(
                metric_types=[MetricType.CI_CD_METRICS],
                start_time=datetime.utcnow() - timedelta(days=7),
                limit=1000,
            )

            # Calculate metrics (simplified implementation)
            avg_pr_cycle_time = 4.5  # hours,
            avg_ci_cd_time = 12.0  # minutes,
            avg_deployment_time = 5.0  # minutes,

            ci_cd_pass_rate = 85.0  # percentage,
            deployment_success_rate = 95.0  # percentage,

            code_quality_score = 82.0  # 0-100,
            golden_rules_compliance = 75.0  # percentage,
            test_coverage = 78.0  # percentage,

            commits_per_day = 15.0,
            prs_per_week = 8.0,

            slowest_pipeline = "ecosystemiser-ci",
            slowest_pipeline_time = 18.0  # minutes,

            velocity_trend = "improving",
            trend_percentage = 5.2

            return DeveloperVelocity(
                avg_pr_cycle_time=avg_pr_cycle_time,
                avg_ci_cd_time=avg_ci_cd_time,
                avg_deployment_time=avg_deployment_time,
                ci_cd_pass_rate=ci_cd_pass_rate,
                deployment_success_rate=deployment_success_rate,
                code_quality_score=code_quality_score,
                golden_rules_compliance=golden_rules_compliance,
                test_coverage=test_coverage,
                commits_per_day=commits_per_day,
                prs_per_week=prs_per_week,
                slowest_pipeline=slowest_pipeline,
                slowest_pipeline_time=slowest_pipeline_time,
                velocity_trend=velocity_trend,
                trend_percentage=trend_percentage,
            )

        except Exception as e:
            logger.error(f"Failed to calculate developer velocity: {e}")
            return DeveloperVelocity()

    async def _calculate_architectural_health_async(self) -> ArchitecturalHealth:
        """Calculate architectural health and compliance metrics."""

        try:
            # Get recent architectural metrics
            compliance_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.GOLDEN_RULES_COMPLIANCE],
                start_time=datetime.utcnow() - timedelta(hours=24),
                limit=100,
            )

            violation_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.ARCHITECTURAL_VIOLATION],
                start_time=datetime.utcnow() - timedelta(hours=24),
                limit=1000,
            )

            debt_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.TECHNICAL_DEBT],
                start_time=datetime.utcnow() - timedelta(hours=24),
                limit=50,
            )

            # Calculate overall compliance
            overall_compliance = 0.0,
            compliance_trend = "stable",
            last_scan_time = None,
            scan_type = "unknown"

            if compliance_metrics:
                # Get the most recent comprehensive scan
                comprehensive_scans = [m for m in compliance_metrics if m.tags.get("scan_type") == "comprehensive"]
                if comprehensive_scans:
                    latest_scan = max(comprehensive_scans, key=lambda x: x.timestamp)
                    overall_compliance = float(latest_scan.value),
                    last_scan_time = latest_scan.timestamp,
                    scan_type = "comprehensive"
                else:
                    # Fall back to quick scans
                    quick_scans = [m for m in compliance_metrics if m.tags.get("scan_type") == "quick_critical"]
                    if quick_scans:
                        latest_scan = max(quick_scans, key=lambda x: x.timestamp)
                        overall_compliance = float(latest_scan.value),
                        last_scan_time = latest_scan.timestamp,
                        scan_type = "quick"

            # Calculate rule compliance breakdown
            critical_rules_passed = 0,
            critical_rules_total = 4  # Based on our critical checks,
            medium_rules_passed = 0,
            medium_rules_total = 0,
            low_rules_passed = 0,
            low_rules_total = 0

            # Count violations by category and severity
            violations_by_category = {},
            violations_by_severity = {},
            violations_by_package = {},
            total_violations = len(violation_metrics)

            for violation in violation_metrics:
                # Count by category
                category = violation.tags.get("category", "unknown")
                violations_by_category[category] = violations_by_category.get(category, 0) + 1

                # Count by severity
                severity = violation.tags.get("severity", "unknown")
                violations_by_severity[severity] = violations_by_severity.get(severity, 0) + 1

                # Extract package from violation description
                description = violation.metadata.get("violation_description", "")
                if "hive-" in description:
                    # Extract package name
                    parts = description.split("hive-")
                    if len(parts) > 1:
                        package_part = parts[1].split("'")[0].split(" ")[0].split("/")[0],
                        package_name = f"hive-{package_part}"
                        violations_by_package[package_name] = violations_by_package.get(package_name, 0) + 1

            # Calculate technical debt score
            technical_debt_score = 0.0,
            debt_trend = "stable"

            if debt_metrics:
                latest_debt = max(debt_metrics, key=lambda x: x.timestamp)
                technical_debt_score = float(latest_debt.value),
                debt_trend = latest_debt.tags.get("debt_level", "stable")

            # Generate top violations (most frequent)
            top_violations = [],
            violation_descriptions = {}

            for violation in violation_metrics:
                desc = violation.metadata.get("violation_description", "")
                if desc:
                    # Simplify description for grouping
                    rule_name = violation.tags.get("rule_name", "Unknown Rule")
                    key = f"{rule_name}: {desc[:100]}..."
                    violation_descriptions[key] = violation_descriptions.get(key, 0) + 1

            # Get top 5 most frequent violations
            top_violations = sorted(violation_descriptions.items(), key=lambda x: x[1], reverse=True)[:5]
            top_violations = [f"{desc} (x{count})" for desc, count in top_violations]

            # Get packages needing most attention
            packages_needing_attention = sorted(violations_by_package.items(), key=lambda x: x[1], reverse=True)[:5]
            packages_needing_attention = [pkg for pkg, count in packages_needing_attention]

            # Generate immediate actions
            immediate_actions = [],
            estimated_effort = "Unknown"

            if overall_compliance < 50:
                immediate_actions.append("CRITICAL: Address high-severity violations immediately")
                estimated_effort = "1-2 weeks"
            elif overall_compliance < 80:
                immediate_actions.append("Review and fix medium-priority violations")
                estimated_effort = "3-5 days"
            else:
                immediate_actions.append("Continue monitoring and address remaining violations")
                estimated_effort = "1-2 days"

            if violations_by_severity.get("high", 0) > 0:
                immediate_actions.append(f"Fix {violations_by_severity['high']} high-severity violations")

            if packages_needing_attention:
                immediate_actions.append(f"Focus on {packages_needing_attention[0]} package")

            # Determine compliance trend (simplified)
            if len(compliance_metrics) > 1:
                sorted_metrics = sorted(compliance_metrics, key=lambda x: x.timestamp)
                if len(sorted_metrics) >= 2:
                    recent_score = float(sorted_metrics[-1].value),
                    older_score = float(sorted_metrics[-2].value)
                    if recent_score > older_score + 5:
                        compliance_trend = "improving"
                    elif recent_score < older_score - 5:
                        compliance_trend = "degrading"
                    else:
                        compliance_trend = "stable"

            return ArchitecturalHealth(
                golden_rules_compliance=overall_compliance,
                compliance_trend=compliance_trend,
                critical_rules_passed=critical_rules_passed,
                critical_rules_total=critical_rules_total,
                medium_rules_passed=medium_rules_passed,
                medium_rules_total=medium_rules_total,
                low_rules_passed=low_rules_passed,
                low_rules_total=low_rules_total,
                total_violations=total_violations,
                technical_debt_score=technical_debt_score,
                debt_trend=debt_trend,
                violations_by_category=violations_by_category,
                violations_by_severity=violations_by_severity,
                violations_by_package=violations_by_package,
                top_violations=top_violations,
                packages_needing_attention=packages_needing_attention,
                immediate_actions=immediate_actions,
                estimated_fix_effort=estimated_effort,
                last_scan_time=last_scan_time,
                scan_type=scan_type,
            )

        except Exception as e:
            logger.error(f"Failed to calculate architectural health: {e}")
            return ArchitecturalHealth()

    async def _calculate_customer_health_async(self) -> CustomerHealthScore:
        """Calculate customer health and satisfaction metrics."""

        try:
            # Get user engagement metrics
            engagement_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.USER_ENGAGEMENT, MetricType.USER_BEHAVIOR],
                start_time=datetime.utcnow() - timedelta(hours=24),
                limit=100,
            )

            # Get retention metrics
            retention_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.USER_RETENTION],
                start_time=datetime.utcnow() - timedelta(days=7),
                limit=50,
            )

            # Get satisfaction metrics
            satisfaction_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.CUSTOMER_SATISFACTION],
                start_time=datetime.utcnow() - timedelta(days=30),
                limit=100,
            )

            # Get support metrics
            support_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.SUPPORT_METRICS],
                start_time=datetime.utcnow() - timedelta(days=7),
                limit=100,
            )

            # Calculate engagement metrics
            daily_active_users = 0,
            avg_session_duration = 0.0

            for metric in engagement_metrics:
                if metric.tags.get("metric_name") == "daily_active_users":
                    daily_active_users = int(metric.metadata.get("active_users", 0))
                elif metric.tags.get("metric_name") == "avg_session_duration":
                    avg_session_duration = float(metric.value)

            # Calculate retention
            user_retention_7d = 0.0
            if retention_metrics:
                retention_7d_metrics = [m for m in retention_metrics if m.tags.get("retention_period") == "7_days"]
                if retention_7d_metrics:
                    user_retention_7d = float(max(retention_7d_metrics, key=lambda x: x.timestamp).value)

            # Calculate satisfaction
            nps_score = 0.0,
            satisfaction_level = "unknown"

            for metric in satisfaction_metrics:
                if metric.tags.get("metric_name") == "nps":
                    nps_score = float(metric.value),
                    satisfaction_level = metric.tags.get("satisfaction_level", "unknown")

            # Calculate support metrics
            avg_first_response_time = 0.0,
            support_ticket_resolution_rate = 0.0,
            open_high_priority_tickets = 0

            for metric in support_metrics:
                if metric.tags.get("metric_name") == "first_response_time":
                    avg_first_response_time = float(metric.value)
                elif metric.tags.get("metric_name") == "open_tickets" and metric.tags.get("priority") == "high":
                    open_high_priority_tickets = int(metric.value)

            # Calculate overall health score (composite)
            health_components = []

            # Engagement component (30%)
            if daily_active_users > 0:
                engagement_score = min(100, (daily_active_users / 1000) * 100)  # Assume 1000 is excellent
                health_components.append(engagement_score * 0.3)

            # Retention component (25%)
            if user_retention_7d > 0:
                health_components.append(user_retention_7d * 0.25)

            # Satisfaction component (25%)
            if nps_score > 0:
                satisfaction_score = min(100, max(0, (nps_score + 100) / 2))  # Convert NPS (-100 to 100) to 0-100
                health_components.append(satisfaction_score * 0.25)

            # Support component (20%)
            if avg_first_response_time > 0:
                support_score = max(0, 100 - (avg_first_response_time * 10))  # Penalty for slow response
                health_components.append(support_score * 0.2)

            overall_health_score = sum(health_components) if health_components else 0.0

            # Determine health status
            if overall_health_score >= 90:
                health_status = HealthStatus.EXCELLENT
            elif overall_health_score >= 80:
                health_status = HealthStatus.GOOD
            elif overall_health_score >= 70:
                health_status = HealthStatus.WARNING
            else:
                health_status = HealthStatus.CRITICAL

            # Identify at-risk customers
            customers_at_risk = [],
            escalated_issues = []

            for metric in satisfaction_metrics:
                if "error_rate_change" in metric.unit and metric.tags.get("alert_level") == "critical":
                    customer = metric.tags.get("customer", "Unknown")
                    customers_at_risk.append(customer)
                    escalated_issues.append(f"{customer}: {metric.value * 100:.0f}% increase in API errors")

            return CustomerHealthScore(
                overall_health_score=overall_health_score,
                health_status=health_status,
                health_trend="stable",  # Would need historical data for trend,
                daily_active_users=daily_active_users,
                weekly_active_users=daily_active_users * 5,  # Estimated,
                monthly_active_users=daily_active_users * 20,  # Estimated
                avg_session_duration=avg_session_duration,
                engagement_trend="stable",
                user_retention_7d=user_retention_7d,
                user_retention_30d=user_retention_7d * 0.8,  # Estimated
                churn_rate=5.0,  # Would come from business metrics
                nps_score=nps_score,
                satisfaction_level=satisfaction_level,
                customer_feedback_score=4.2,  # Would come from surveys
                avg_first_response_time=avg_first_response_time,
                support_ticket_resolution_rate=support_ticket_resolution_rate,
                open_high_priority_tickets=open_high_priority_tickets,
                customers_at_risk=customers_at_risk,
                escalated_issues=escalated_issues,
            )

        except Exception as e:
            logger.error(f"Failed to calculate customer health: {e}")
            return CustomerHealthScore()

    async def _calculate_feature_performance_async(self) -> FeaturePerformanceMatrix:
        """Calculate feature adoption vs operational cost analysis."""

        try:
            # Get feature adoption metrics
            feature_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.FEATURE_ADOPTION],
                start_time=datetime.utcnow() - timedelta(days=7),
                limit=100,
            )

            features = [],
            high_value_features = [],
            underperforming_features = [],
            emerging_features = [],
            cost_efficient_features = [],

            total_cost = 0.0,
            adoption_rates = []

            for metric in feature_metrics:
                feature_name = metric.tags.get("feature_name", "Unknown")
                adoption_rate = float(metric.value),
                operational_cost = float(metric.metadata.get("operational_cost", 0))
                satisfaction_score = float(metric.metadata.get("satisfaction_score", 0))
                roi_score = float(metric.metadata.get("roi_score", 0))

                feature_data = FeaturePerformanceData(
                    name=feature_name,
                    adoption_rate=adoption_rate,
                    usage_frequency=metric.tags.get("usage_frequency", "unknown"),
                    user_segment=metric.tags.get("user_segment", "all"),
                    operational_cost=operational_cost,
                    cost_per_user=float(metric.metadata.get("cost_per_user", 0)),
                    satisfaction_score=satisfaction_score,
                    roi_score=roi_score,
                    performance_status=metric.tags.get("feature_status", "unknown"),
                    review_required=metric.tags.get("review_required") == "true",
                    reason=metric.tags.get("reason", ""),
                )

                features.append(feature_data)
                total_cost += operational_cost
                adoption_rates.append(adoption_rate)

                # Categorize features
                if roi_score > 15:
                    high_value_features.append(feature_name)
                elif adoption_rate < 10 and operational_cost > 500:
                    underperforming_features.append(feature_name)
                elif adoption_rate > 50 and operational_cost < 400:
                    cost_efficient_features.append(feature_name)
                elif adoption_rate > 30:  # Growing features
                    emerging_features.append(feature_name)

            avg_adoption_rate = sum(adoption_rates) / len(adoption_rates) if adoption_rates else 0.0

            # Calculate cost optimization potential
            cost_optimization_potential = sum(
                f.operational_cost * 0.3 for f in features if f.adoption_rate < 10 and f.operational_cost > 500
            )

            # Generate recommendations
            features_to_promote = [f.name for f in features if f.roi_score > 10 and f.adoption_rate < 70],
            features_to_optimize = [f.name for f in features if f.operational_cost > 600 and f.satisfaction_score > 4.0],
            features_to_deprecate = [f.name for f in features if f.adoption_rate < 5 and f.operational_cost > 300]

            return FeaturePerformanceMatrix(
                features=features,
                high_value_features=high_value_features,
                underperforming_features=underperforming_features,
                emerging_features=emerging_features,
                cost_efficient_features=cost_efficient_features,
                total_feature_cost=total_cost,
                avg_adoption_rate=avg_adoption_rate,
                cost_optimization_potential=cost_optimization_potential,
                features_to_promote=features_to_promote,
                features_to_optimize=features_to_optimize,
                features_to_deprecate=features_to_deprecate,
            )

        except Exception as e:
            logger.error(f"Failed to calculate feature performance: {e}")
            return FeaturePerformanceMatrix()

    async def _calculate_revenue_correlation_async(self) -> RevenueCorrelationData:
        """Calculate revenue and cost correlation analysis."""

        try:
            # Get business metrics
            revenue_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.REVENUE_METRICS, MetricType.BUSINESS_KPI, MetricType.CONVERSION_RATE],
                start_time=datetime.utcnow() - timedelta(days=30),
                limit=100,
            )

            # Get cost metrics
            await self.warehouse.query_metrics_async(
                metric_types=[MetricType.AI_COST, MetricType.SYSTEM_PERFORMANCE],
                start_time=datetime.utcnow() - timedelta(days=30),
                limit=100,
            )

            # Extract revenue data
            monthly_recurring_revenue = 0.0,
            revenue_growth_rate = 0.0,
            customer_acquisition_cost = 0.0,
            customer_lifetime_value = 0.0,
            trial_to_paid_conversion = 0.0

            for metric in revenue_metrics:
                if metric.tags.get("metric_name") == "mrr":
                    monthly_recurring_revenue = float(metric.value),
                    revenue_growth_rate = float(metric.metadata.get("growth_rate", 0)) * 100
                elif metric.tags.get("metric_name") == "cac":
                    customer_acquisition_cost = float(metric.value),
                    customer_lifetime_value = customer_acquisition_cost * float(metric.metadata.get("ltv_cac_ratio", 3))
                elif metric.tags.get("conversion_type") == "trial_to_paid":
                    trial_to_paid_conversion = float(metric.value)

            # Calculate total platform cost (simplified)
            total_platform_cost = 2500.0  # Would aggregate from various cost sources

            # Calculate derived metrics
            cost_per_revenue_dollar = total_platform_cost / max(monthly_recurring_revenue, 1)
            ltv_cac_ratio = (
                customer_lifetime_value / max(customer_acquisition_cost, 1) if customer_acquisition_cost > 0 else 0
            )
            cost_efficiency_score = max(0, 100 - (cost_per_revenue_dollar * 100))

            # Projections (simplified)
            projected_monthly_revenue = monthly_recurring_revenue * (1 + revenue_growth_rate / 100),
            projected_monthly_cost = total_platform_cost * 1.05  # Assume 5% cost growth,
            projected_profit_margin = (
                (projected_monthly_revenue - projected_monthly_cost) / projected_monthly_revenue
            ) * 100

            # Revenue-cost correlation (would need historical data for proper calculation)
            revenue_cost_correlation = 0.65  # Moderate positive correlation

            # Generate recommendations
            cost_optimization_opportunities = [],
            revenue_growth_opportunities = []

            if cost_per_revenue_dollar > 0.6:
                cost_optimization_opportunities.append("High cost per revenue dollar - optimize operational efficiency")

            if trial_to_paid_conversion < 5:
                revenue_growth_opportunities.append("Low trial conversion rate - improve onboarding experience")

            if ltv_cac_ratio < 3:
                cost_optimization_opportunities.append(
                    "Low LTV:CAC ratio - reduce acquisition costs or increase retention",
                )

            return RevenueCorrelationData(
                monthly_recurring_revenue=monthly_recurring_revenue,
                revenue_growth_rate=revenue_growth_rate,
                revenue_trend="healthy" if revenue_growth_rate > 5 else "stable",
                total_platform_cost=total_platform_cost,
                cost_per_revenue_dollar=cost_per_revenue_dollar,
                cost_efficiency_trend="stable",
                customer_acquisition_cost=customer_acquisition_cost,
                customer_lifetime_value=customer_lifetime_value,
                ltv_cac_ratio=ltv_cac_ratio,
                trial_to_paid_conversion=trial_to_paid_conversion,
                conversion_trend="stable",
                revenue_cost_correlation=revenue_cost_correlation,
                cost_efficiency_score=cost_efficiency_score,
                profitability_trend="improving" if projected_profit_margin > 20 else "stable",
                projected_monthly_revenue=projected_monthly_revenue,
                projected_monthly_cost=projected_monthly_cost,
                projected_profit_margin=projected_profit_margin,
                cost_optimization_opportunities=cost_optimization_opportunities,
                revenue_growth_opportunities=revenue_growth_opportunities,
            )

        except Exception as e:
            logger.error(f"Failed to calculate revenue correlation: {e}")
            return RevenueCorrelationData()

    async def _calculate_certification_readiness_async(self) -> CertificationReadiness:
        """Calculate comprehensive certification readiness for Operation Bedrock."""

        try:
            # Query certification metrics from the data warehouse
            cert_metrics = await self.warehouse.query_metrics_async(
                metric_types=[
                    MetricType.CERTIFICATION_SCORE,
                    MetricType.CODE_QUALITY_SCORE,
                    MetricType.TESTING_COVERAGE,
                    MetricType.DEPLOYMENT_READINESS,
                    MetricType.TOOLKIT_UTILIZATION,
                    MetricType.PLATFORM_INTEGRATION,
                    MetricType.MONITORING_SCORE,
                    MetricType.INNOVATION_SCORE,
                ],
                start_time=datetime.utcnow() - timedelta(hours=24),
                limit=500,
            )

            # Process metrics into component scorecards
            component_scorecards = self._process_certification_metrics(cert_metrics)

            # Calculate platform-wide statistics
            total_components = len(component_scorecards)
            if total_components == 0:
                return CertificationReadiness()

            # Calculate certification level breakdown
            senior_architects = len([c for c in component_scorecards if c.overall_score >= 90]),
            certified_architects = len([c for c in component_scorecards if 80 <= c.overall_score < 90]),
            associate_architects = len([c for c in component_scorecards if 70 <= c.overall_score < 80]),
            non_certified = len([c for c in component_scorecards if c.overall_score < 70]),

            certified_components = senior_architects + certified_architects + associate_architects,
            certification_rate = (certified_components / total_components) * 100 if total_components > 0 else 0

            # Calculate overall platform score (weighted average)
            total_score = sum(c.overall_score for c in component_scorecards),
            overall_platform_score = total_score / total_components if total_components > 0 else 0

            # Identify critical issues
            critical_components = [c.name for c in component_scorecards if c.urgency == "high"],
            high_priority_issues = []

            # Aggregate issues across all components
            total_golden_rules_violations = sum(c.golden_rules_violations for c in component_scorecards),
            total_missing_tests = sum(c.missing_tests for c in component_scorecards),
            components_production_ready = len([c for c in component_scorecards if c.deployment_readiness >= 80]),
            components_needing_immediate_action = len(
                [c for c in component_scorecards if c.action_required == "immediate"],
            )

            # Generate high priority issues list
            for scorecard in component_scorecards:
                if scorecard.urgency == "high":
                    high_priority_issues.append(f"{scorecard.name}: {scorecard.certification_gap}")
                if scorecard.golden_rules_violations > 0:
                    high_priority_issues.append(
                        f"{scorecard.name}: {scorecard.golden_rules_violations} Golden Rules violations",
                    )
                if scorecard.test_coverage < 70:
                    high_priority_issues.append(f"{scorecard.name}: Low test coverage ({scorecard.test_coverage:.1f}%)")

            # Calculate burndown metrics
            estimated_effort_days = self._estimate_bedrock_effort(component_scorecards),
            progress_percentage = self._calculate_bedrock_progress(component_scorecards)

            # Generate Oracle recommendations
            top_recommendations = self._generate_certification_recommendations(component_scorecards),
            quick_wins = self._identify_quick_wins(component_scorecards)

            return CertificationReadiness(
                overall_platform_score=overall_platform_score,
                certified_components=certified_components,
                total_components=total_components,
                certification_rate=certification_rate,
                senior_architects=senior_architects,
                certified_architects=certified_architects,
                associate_architects=associate_architects,
                non_certified=non_certified,
                component_scorecards=component_scorecards,
                critical_components=critical_components,
                high_priority_issues=high_priority_issues[:10],  # Top 10 issues
                total_golden_rules_violations=total_golden_rules_violations,
                total_missing_tests=total_missing_tests,
                components_production_ready=components_production_ready,
                components_needing_immediate_action=components_needing_immediate_action,
                estimated_effort_days=estimated_effort_days,
                progress_percentage=progress_percentage,
                top_recommendations=top_recommendations[:5],  # Top 5 recommendations
                quick_wins=quick_wins[:3],  # Top 3 quick wins
            )

        except Exception as e:
            logger.error(f"Failed to calculate certification readiness: {e}")
            return CertificationReadiness()

    def _process_certification_metrics(self, metrics: list[Any]) -> list[ComponentScorecard]:
        """Process raw certification metrics into component scorecards."""

        # Group metrics by component
        component_metrics = {}
        for metric in metrics:
            component_name = metric.tags.get("component", "unknown")
            if component_name not in component_metrics:
                component_metrics[component_name] = {}

            metric_type = metric.metric_type
            component_metrics[component_name][metric_type] = metric

        # Create scorecards for each component
        scorecards = []
        for component_name, comp_metrics in component_metrics.items():
            scorecard = self._create_component_scorecard(component_name, comp_metrics)
            scorecards.append(scorecard)

        # Sort by score (lowest first for prioritization)
        scorecards.sort(key=lambda x: x.overall_score)

        return scorecards

    def _create_component_scorecard(self, component_name: str, metrics: dict[Any, Any]) -> ComponentScorecard:
        """Create a component scorecard from its metrics."""

        # Extract overall certification score
        cert_metric = metrics.get(MetricType.CERTIFICATION_SCORE),
        overall_score = cert_metric.value if cert_metric else 0.0

        # Extract individual criteria scores
        code_quality_metric = metrics.get(MetricType.CODE_QUALITY_SCORE),
        code_quality_score = code_quality_metric.value if code_quality_metric else 0.0,

        coverage_metric = metrics.get(MetricType.TESTING_COVERAGE),
        test_coverage = coverage_metric.value if coverage_metric else 0.0,

        deployment_metric = metrics.get(MetricType.DEPLOYMENT_READINESS),
        deployment_readiness = deployment_metric.value if deployment_metric else 0.0,

        toolkit_metric = metrics.get(MetricType.TOOLKIT_UTILIZATION),
        toolkit_utilization = toolkit_metric.value if toolkit_metric else 0.0,

        monitoring_metric = metrics.get(MetricType.MONITORING_SCORE),
        monitoring_score = monitoring_metric.value if monitoring_metric else 0.0,

        platform_metric = metrics.get(MetricType.PLATFORM_INTEGRATION),
        platform_integration = platform_metric.value if platform_metric else 0.0,

        innovation_metric = metrics.get(MetricType.INNOVATION_SCORE),
        innovation_score = innovation_metric.value if innovation_metric else 0.0

        # Determine component type and certification level
        component_type = cert_metric.tags.get("component_type", "unknown") if cert_metric else "unknown"
        certification_level = (
            cert_metric.tags.get("certification_level", "Non-Certified") if cert_metric else "Non-Certified"
        )

        # Extract status indicators
        action_required = cert_metric.tags.get("action_required", "maintenance") if cert_metric else "maintenance"
        urgency = cert_metric.tags.get("urgency", "low") if cert_metric else "low"

        # Calculate improvement potential and certification gap
        improvement_potential = 100 - overall_score,
        certification_gap = cert_metric.metadata.get("certification_gap", "") if cert_metric else ""

        # Extract specific issues
        golden_rules_violations = 0,
        missing_tests = 0,
        deployment_blockers = [],
        toolkit_gaps = [],
        quality_issues = []

        # Get violations from architectural metrics (if available)
        if component_name == "hive-ai":
            golden_rules_violations = 7  # Known from previous analysis,
            missing_tests = 20
        elif component_name == "ecosystemiser":
            missing_tests = 5,
            deployment_blockers = ["CI/CD not configured"]

        # Determine certification readiness
        certification_ready = overall_score >= 70

        return ComponentScorecard(
            name=component_name,
            component_type=component_type,
            overall_score=overall_score,
            certification_level=certification_level,
            technical_excellence=code_quality_score * 0.4,  # Scale to /40 points,
            operational_readiness=deployment_readiness * 0.3,  # Scale to /30 points
            platform_integration=platform_integration * 0.2,  # Scale to /20 points
            innovation=innovation_score,  # Already /10 points
            code_quality_score=code_quality_score,
            test_coverage=test_coverage,
            deployment_readiness=deployment_readiness,
            toolkit_utilization=toolkit_utilization,
            monitoring_score=monitoring_score,
            certification_ready=certification_ready,
            action_required=action_required,
            urgency=urgency,
            improvement_potential=improvement_potential,
            certification_gap=certification_gap,
            golden_rules_violations=golden_rules_violations,
            missing_tests=missing_tests,
            deployment_blockers=deployment_blockers,
            toolkit_gaps=toolkit_gaps,
            quality_issues=quality_issues,
        )

    def _estimate_bedrock_effort(self, scorecards: list[ComponentScorecard]) -> int:
        """Estimate total effort in days for Operation Bedrock."""

        total_effort = 0

        for scorecard in scorecards:
            # Base effort based on score gap
            score_gap = 90 - scorecard.overall_score  # Target: Senior Architect level
            if score_gap > 0:
                # Rough estimate: 1 day per 5 points improvement needed
                component_effort = max(1, int(score_gap / 5))

                # Add specific issue penalties
                component_effort += scorecard.golden_rules_violations * 0.5  # 0.5 days per violation
                component_effort += scorecard.missing_tests * 0.1  # 0.1 days per missing test
                component_effort += len(scorecard.deployment_blockers) * 2  # 2 days per blocker

                total_effort += component_effort

        return int(total_effort)

    def _calculate_bedrock_progress(self, scorecards: list[ComponentScorecard]) -> float:
        """Calculate overall progress percentage for Operation Bedrock."""

        if not scorecards:
            return 0.0

        # Progress is based on how close we are to 90+ scores for all components
        total_possible = len(scorecards) * 90  # Target score for each component,
        total_actual = sum(min(s.overall_score, 90) for s in scorecards)

        progress = (total_actual / total_possible) * 100 if total_possible > 0 else 0
        return min(progress, 100.0)

    def _generate_certification_recommendations(self, scorecards: list[ComponentScorecard]) -> list[str]:
        """Generate top Oracle recommendations for certification improvement."""

        recommendations = []

        # Prioritize by urgency and impact
        critical_scorecards = [s for s in scorecards if s.urgency == "high"]

        for scorecard in critical_scorecards[:3]:  # Top 3 critical components
            if scorecard.golden_rules_violations > 0:
                recommendations.append(
                    f"CRITICAL: Fix {scorecard.golden_rules_violations} Golden Rules violations in {scorecard.name}",
                )

            if scorecard.test_coverage < 70:
                recommendations.append(
                    f"HIGH: Increase test coverage in {scorecard.name} from {scorecard.test_coverage:.1f}% to 90%",
                )

            if scorecard.deployment_readiness < 80:
                recommendations.append(f"MEDIUM: Improve deployment readiness for {scorecard.name}")

        # Add general recommendations
        if len(recommendations) < 5:
            low_scoring = [s for s in scorecards if s.overall_score < 80][:2]
            for scorecard in low_scoring:
                recommendations.append(f"Focus on {scorecard.name}: {scorecard.certification_gap}")

        return recommendations

    def _identify_quick_wins(self, scorecards: list[ComponentScorecard]) -> list[str]:
        """Identify quick wins - low effort, high impact improvements."""

        quick_wins = []

        for scorecard in scorecards:
            # Missing tests are often quick wins
            if 0 < scorecard.missing_tests <= 5:
                quick_wins.append(f"Add {scorecard.missing_tests} missing test files in {scorecard.name}")

            # Toolkit gaps are usually straightforward
            if scorecard.toolkit_utilization < 80 and scorecard.toolkit_utilization > 60:
                quick_wins.append(f"Improve toolkit utilization in {scorecard.name}")

            # Monitoring setup is often a quick win
            if scorecard.monitoring_score < 50:
                quick_wins.append(f"Add basic monitoring to {scorecard.name}")

        return quick_wins[:5]  # Return top 5 quick wins

    async def _count_services_async(self) -> tuple[int, int]:
        """Count active and total services."""

        try:
            # Get recent health metrics
            health_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.PRODUCTION_HEALTH],
                start_time=datetime.utcnow() - timedelta(hours=1),
                limit=100,
            )

            # Count unique services
            services = set(),
            active_services = set()

            for metric in health_metrics:
                service_name = metric.tags.get("service", "unknown")
                services.add(service_name)

                if isinstance(metric.value, dict) and metric.value.get("status") == "healthy":
                    active_services.add(service_name)

            return len(active_services), len(services)

        except Exception as e:
            logger.error(f"Failed to count services: {e}")
            return 0, 0

    async def generate_dashboard_html_async(self) -> str:
        """Generate HTML dashboard for display."""

        data = await self.get_dashboard_data_async()

        # This is a simplified HTML template
        # In a real implementation, you'd use a proper templating system
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Hive Mission Control</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }}
                .dashboard {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }}
                .card {{ background: #2a2a2a; padding: 20px; border-radius: 8px; border-left: 4px solid #007acc; }}
                .status-excellent {{ border-left-color: #28a745; }}
                .status-good {{ border-left-color: #17a2b8; }}
                .status-warning {{ border-left-color: #ffc107; }}
                .status-critical {{ border-left-color: #dc3545; }}
                .metric {{ margin: 10px 0; }}
                .metric-value {{ font-size: 24px; font-weight: bold; }}
                .metric-label {{ font-size: 14px; color: #ccc; }}
                .insights {{ grid-column: 1 / -1; }}
                .insight {{ background: #3a3a3a; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .insight-critical {{ border-left: 4px solid #dc3545; }}
                .insight-high {{ border-left: 4px solid #fd7e14; }}
            </style>
        </head>
        <body>
            <h1>🎯 Hive Mission Control Dashboard</h1>
            <p>Generated at: {data.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")}</p>

            <div class="dashboard">
                <!-- Platform Health -->
                <div class="card status-{data.platform_health.overall_status.value}">
                    <h2>🏥 Platform Health</h2>
                    <div class="metric">
                        <div class="metric-value">{data.platform_health.overall_score:.1f}%</div>
                        <div class="metric-label">Overall Health Score</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.platform_health.total_uptime:.1f}%</div>
                        <div class="metric-label">Average Uptime</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.platform_health.critical_issues}</div>
                        <div class="metric-label">Critical Issues</div>
                    </div>
                </div>

                <!-- Cost Intelligence -->
                <div class="card">
                    <h2>💰 Cost Intelligence</h2>
                    <div class="metric">
                        <div class="metric-value">${data.cost_intelligence.daily_cost:.2f}</div>
                        <div class="metric-label">Today's Cost</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${data.cost_intelligence.monthly_cost:.2f}</div>
                        <div class="metric-label">Monthly Cost</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.cost_intelligence.budget_utilization:.1f}%</div>
                        <div class="metric-label">Budget Utilization</div>
                    </div>
                </div>

                <!-- Developer Velocity -->
                <div class="card">
                    <h2>🚀 Developer Velocity</h2>
                    <div class="metric">
                        <div class="metric-value">{data.developer_velocity.avg_pr_cycle_time:.1f}h</div>
                        <div class="metric-label">Avg PR Cycle Time</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.developer_velocity.ci_cd_pass_rate:.1f}%</div>
                        <div class="metric-label">CI/CD Pass Rate</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.developer_velocity.code_quality_score:.1f}</div>
                        <div class="metric-label">Code Quality Score</div>
                    </div>
                </div>

                <!-- Architectural Health -->
                <div class="card status-{self._get_compliance_status(data.architectural_health.golden_rules_compliance)}">
                    <h2>🏛️ Architectural Health</h2>
                    <div class="metric">
                        <div class="metric-value">{data.architectural_health.golden_rules_compliance:.1f}%</div>
                        <div class="metric-label">Golden Rules Compliance</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.architectural_health.total_violations}</div>
                        <div class="metric-label">Active Violations</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.architectural_health.technical_debt_score:.0f}</div>
                        <div class="metric-label">Technical Debt Score</div>
                    </div>
                </div>

                <!-- Customer Health Score -->
                <div class="card status-{self._get_health_status(data.customer_health.health_status)}">
                    <h2>👥 Customer Health</h2>
                    <div class="metric">
                        <div class="metric-value">{data.customer_health.overall_health_score:.1f}</div>
                        <div class="metric-label">Health Score</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.customer_health.daily_active_users}</div>
                        <div class="metric-label">Daily Active Users</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.customer_health.nps_score:.1f}</div>
                        <div class="metric-label">NPS Score</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.customer_health.user_retention_7d:.1f}%</div>
                        <div class="metric-label">7-Day Retention</div>
                    </div>
                </div>

                <!-- Feature Performance Matrix -->
                <div class="card">
                    <h2>⚡ Feature Performance</h2>
                    <div class="metric">
                        <div class="metric-value">${data.feature_performance.total_feature_cost:.0f}</div>
                        <div class="metric-label">Total Feature Cost</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.feature_performance.avg_adoption_rate:.1f}%</div>
                        <div class="metric-label">Avg Adoption Rate</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${data.feature_performance.cost_optimization_potential:.0f}</div>
                        <div class="metric-label">Optimization Potential</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{len(data.feature_performance.high_value_features)}</div>
                        <div class="metric-label">High-Value Features</div>
                    </div>
                </div>

                <!-- Revenue & Cost Correlation -->
                <div class="card status-{self._get_profitability_status(data.revenue_correlation.projected_profit_margin)}">
                    <h2>📊 Revenue Intelligence</h2>
                    <div class="metric">
                        <div class="metric-value">${data.revenue_correlation.monthly_recurring_revenue:,.0f}</div>
                        <div class="metric-label">Monthly Recurring Revenue</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.revenue_correlation.revenue_growth_rate:.1f}%</div>
                        <div class="metric-label">Growth Rate</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.revenue_correlation.ltv_cac_ratio:.1f}</div>
                        <div class="metric-label">LTV:CAC Ratio</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{data.revenue_correlation.cost_efficiency_score:.0f}</div>
                        <div class="metric-label">Cost Efficiency Score</div>
                    </div>
                </div>

                <!-- Critical Insights -->
                <div class="insights">
                    <h2>🔍 Critical Insights</h2>
                    {self._generate_insights_html(data.critical_insights)}

                    <!-- Architectural Violations Section -->
                    {self._generate_architectural_violations_html(data.architectural_health)}

                    <!-- Business Intelligence Section -->
                    {self._generate_business_intelligence_html(data)}
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _generate_insights_html(self, insights: list[Insight]) -> str:
        """Generate HTML for insights section."""
        if not insights:
            return "<p>No critical insights at this time. Platform is operating normally.</p>"

        html = ""
        for insight in insights:
            severity_class = f"insight-{insight.severity.value}"
            html += f"""
            <div class="insight {severity_class}">
                <h3>{insight.title}</h3>
                <p>{insight.description}</p>
                <strong>Recommended Actions:</strong>
                <ul>
                    {"".join(f"<li>{action}</li>" for action in insight.recommended_actions)}
                </ul>
            </div>
            """

        return html

    def _get_compliance_status(self, compliance_score: float) -> str:
        """Get status class based on compliance score."""
        if compliance_score >= 90:
            return "excellent"
        elif compliance_score >= 80:
            return "good"
        elif compliance_score >= 70:
            return "warning"
        else:
            return "critical"

    def _generate_architectural_violations_html(self, arch_health: ArchitecturalHealth) -> str:
        """Generate HTML for architectural violations section."""
        if not arch_health.top_violations and not arch_health.packages_needing_attention:
            return "<div class='insight'><h3>✅ No Major Architectural Issues</h3><p>Platform architecture is in good shape!</p></div>"

        html = "<div class='insight insight-high'><h3>🏗️ Architectural Status</h3>"

        # Compliance summary
        html += f"<p><strong>Compliance:</strong> {arch_health.golden_rules_compliance:.1f}% "
        html += f"({arch_health.compliance_trend})</p>"

        # Technical debt
        if arch_health.technical_debt_score > 0:
            html += f"<p><strong>Technical Debt:</strong> {arch_health.technical_debt_score:.0f} points "
            html += f"({arch_health.debt_trend})</p>"

        # Top violations
        if arch_health.top_violations:
            html += "<p><strong>Top Violations:</strong></p><ul>"
            for violation in arch_health.top_violations[:3]:  # Show top 3
                html += f"<li>{violation}</li>"
            html += "</ul>"

        # Packages needing attention
        if arch_health.packages_needing_attention:
            html += "<p><strong>Packages Needing Attention:</strong> "
            html += ", ".join(arch_health.packages_needing_attention[:3])
            html += "</p>"

        # Immediate actions
        if arch_health.immediate_actions:
            html += "<p><strong>Immediate Actions:</strong></p><ul>"
            for action in arch_health.immediate_actions[:3]:
                html += f"<li>{action}</li>"
            html += "</ul>"

        # Last scan info
        if arch_health.last_scan_time:
            html += f"<p><em>Last scan: {arch_health.last_scan_time.strftime('%Y-%m-%d %H:%M')} UTC "
            html += f"({arch_health.scan_type})</em></p>"

        html += "</div>"
        return html

    def _get_health_status(self, health_status: HealthStatus) -> str:
        """Get status class based on health status enum."""
        return health_status.value

    def _get_profitability_status(self, profit_margin: float) -> str:
        """Get status class based on profit margin."""
        if profit_margin >= 30:
            return "excellent"
        elif profit_margin >= 20:
            return "good"
        elif profit_margin >= 10:
            return "warning"
        else:
            return "critical"

    def _generate_business_intelligence_html(self, data: DashboardData) -> str:
        """Generate HTML for business intelligence section."""
        html = "<div class='insight'><h3>📈 Business Intelligence Summary</h3>"

        # Customer health alerts
        if data.customer_health.customers_at_risk:
            html += "<div class='insight insight-critical'>"
            html += "<h4>⚠️ Customers at Risk</h4>"
            html += "<ul>"
            for issue in data.customer_health.escalated_issues[:3]:
                html += f"<li>{issue}</li>"
            html += "</ul></div>"

        # Feature performance insights
        if data.feature_performance.underperforming_features:
            html += "<div class='insight insight-warning'>"
            html += "<h4>💸 Underperforming Features</h4>"
            html += f"<p>{len(data.feature_performance.underperforming_features)} features have low adoption but high costs:</p>"
            html += "<ul>"
            for feature in data.feature_performance.underperforming_features[:3]:
                html += f"<li>{feature}</li>"
            html += "</ul>"
            if data.feature_performance.cost_optimization_potential > 0:
                html += f"<p><strong>Potential monthly savings:</strong> ${data.feature_performance.cost_optimization_potential:.0f}</p>"
            html += "</div>"

        # Revenue growth opportunities
        if data.revenue_correlation.revenue_growth_opportunities:
            html += "<div class='insight insight-medium'>"
            html += "<h4>🚀 Revenue Growth Opportunities</h4>"
            html += "<ul>"
            for opportunity in data.revenue_correlation.revenue_growth_opportunities:
                html += f"<li>{opportunity}</li>"
            html += "</ul></div>"

        # Cost optimization opportunities
        if data.revenue_correlation.cost_optimization_opportunities:
            html += "<div class='insight insight-medium'>"
            html += "<h4>💡 Cost Optimization Opportunities</h4>"
            html += "<ul>"
            for opportunity in data.revenue_correlation.cost_optimization_opportunities:
                html += f"<li>{opportunity}</li>"
            html += "</ul></div>"

        # High-value features to promote
        if data.feature_performance.features_to_promote:
            html += "<div class='insight insight-low'>"
            html += "<h4>⭐ Features to Promote</h4>"
            html += f"<p>These {len(data.feature_performance.features_to_promote)} features have high ROI but low adoption:</p>"
            html += "<ul>"
            for feature in data.feature_performance.features_to_promote[:3]:
                html += f"<li>{feature}</li>"
            html += "</ul></div>"

        # Revenue and efficiency summary
        html += "<div class='business-summary'>"
        html += f"<p><strong>Revenue Growth:</strong> {data.revenue_correlation.revenue_growth_rate:.1f}% monthly</p>"
        html += f"<p><strong>Cost Efficiency:</strong> {data.revenue_correlation.cost_efficiency_score:.0f}/100</p>"
        html += f"<p><strong>Customer Health:</strong> {data.customer_health.overall_health_score:.0f}/100 "
        html += f"({data.customer_health.satisfaction_level})</p>"
        html += "</div>"

        html += "</div>"
        return html
