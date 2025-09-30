"""
Strategic Recommendation Engine - The Oracle Function

Transforms analytics insights into strategic, actionable recommendations
that guide platform evolution, cost optimization, and failure prevention.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from hive_logging import get_logger

from .analytics_engine import AnalyticsEngine, Anomaly, Insight, TrendAnalysis
from .data_unification import MetricsWarehouse, MetricType

logger = get_logger(__name__)


class RecommendationType(Enum):
    """Types of strategic recommendations."""

    PREDICTIVE_MAINTENANCE = "predictive_maintenance"
    COST_OPTIMIZATION = "cost_optimization"
    PERFORMANCE_IMPROVEMENT = "performance_improvement"
    SECURITY_ENHANCEMENT = "security_enhancement"
    DEVELOPER_PRODUCTIVITY = "developer_productivity"
    ARCHITECTURAL_IMPROVEMENT = "architectural_improvement"
    CAPACITY_PLANNING = "capacity_planning"
    RISK_MITIGATION = "risk_mitigation"
    # New business strategy recommendation types
    PRODUCT_STRATEGY = "product_strategy"
    USER_EXPERIENCE = "user_experience"
    CUSTOMER_SUCCESS = "customer_success"
    REVENUE_OPTIMIZATION = "revenue_optimization"
    FEATURE_MANAGEMENT = "feature_management"
    BUSINESS_INTELLIGENCE = "business_intelligence"


class Priority(Enum):
    """Recommendation priority levels."""

    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"  # Action needed within 24 hours
    MEDIUM = "medium"  # Action needed within week
    LOW = "low"  # Action needed within month
    INFORMATIONAL = "info"  # FYI, no immediate action


class ImpactLevel(Enum):
    """Expected impact of implementing recommendation."""

    TRANSFORMATIONAL = "transformational"  # >50% improvement
    HIGH = "high"  # 20-50% improvement
    MEDIUM = "medium"  # 5-20% improvement
    LOW = "low"  # <5% improvement
    UNKNOWN = "unknown"  # Impact unclear


@dataclass
class StrategicInsight:
    """A strategic insight with detailed context."""

    title: str
    description: str
    category: str

    # Evidence and analysis
    supporting_data: dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0  # 0.0 to 1.0
    risk_level: str = "medium"  # low, medium, high, critical

    # Predictions
    predicted_outcome: str = ""
    probability: float = 0.0  # 0.0 to 1.0
    time_to_impact: timedelta | None = None

    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Recommendation:
    """Strategic recommendation with implementation details."""

    # Core recommendation
    title: str
    description: str
    recommendation_type: RecommendationType
    priority: Priority

    # Impact assessment
    expected_impact: ImpactLevel
    impact_description: str
    estimated_benefit: str | None = None  # e.g., "60% cost reduction"
    risk_assessment: str = "low"

    # Implementation details
    implementation_steps: list[str] = field(default_factory=list)
    estimated_effort: str = ""  # e.g., "2-3 days", "1 week"
    required_resources: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    # Supporting evidence
    strategic_insights: list[StrategicInsight] = field(default_factory=list)
    supporting_metrics: list[str] = field(default_factory=list)
    trends: list[TrendAnalysis] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)

    # Metadata
    generated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    tags: dict[str, str] = field(default_factory=dict)

    # GitHub integration
    github_issue_title: str = ""
    github_issue_body: str = ""
    github_labels: list[str] = field(default_factory=list)


@dataclass
class RecommendationReport:
    """Comprehensive recommendation report."""

    title: str
    summary: str
    generated_at: datetime

    # Recommendations by priority
    critical_recommendations: list[Recommendation] = field(default_factory=list)
    high_priority_recommendations: list[Recommendation] = field(default_factory=list)
    medium_priority_recommendations: list[Recommendation] = field(default_factory=list)
    low_priority_recommendations: list[Recommendation] = field(default_factory=list)

    # Insights
    key_insights: list[StrategicInsight] = field(default_factory=list)

    # Executive summary
    total_potential_savings: float = 0.0
    total_risk_mitigation: str = ""
    recommended_immediate_actions: list[str] = field(default_factory=list)


class RecommendationEngine:
    """
    Strategic Recommendation Engine - The Oracle Function

    Analyzes platform data and generates strategic, actionable
    recommendations for optimization, risk mitigation, and improvement.
    """

    def __init__(self, warehouse: MetricsWarehouse, analytics: AnalyticsEngine):
        self.warehouse = warehouse
        self.analytics = analytics

        # Configuration
        self.prediction_confidence_threshold = 0.7
        self.cost_optimization_threshold = 0.1  # 10% potential savings
        self.performance_degradation_threshold = 0.2  # 20% degradation

        # Knowledge base for recommendations
        self.recommendation_templates = self._load_recommendation_templates()

    def _load_recommendation_templates(self) -> dict[str, dict[str, Any]]:
        """Load recommendation templates and patterns."""

        return {
            "high_ai_costs": {
                "type": RecommendationType.COST_OPTIMIZATION,
                "title_template": "AI Costs Optimization: {model} Usage",
                "description_template": "AI costs for {model} have increased by {percentage}% over {period}",
                "implementation_steps": [
                    "Analyze usage patterns for {model}",
                    "Identify high-cost operations",
                    "Test alternative models (e.g., claude-3-haiku)",
                    "Implement A/B testing for model selection",
                    "Set up usage-based cost controls",
                ],
                "estimated_effort": "3-5 days",
                "expected_impact": ImpactLevel.HIGH,
            },
            "performance_degradation": {
                "type": RecommendationType.PREDICTIVE_MAINTENANCE,
                "title_template": "Performance Degradation Alert: {service}",
                "description_template": "{service} showing {percentage}% performance degradation over {period}",
                "implementation_steps": [
                    "Profile {service} performance",
                    "Identify bottlenecks in {component}",
                    "Optimize database queries",
                    "Review recent code changes",
                    "Consider resource scaling",
                ],
                "estimated_effort": "2-4 days",
                "expected_impact": ImpactLevel.HIGH,
            },
            "cicd_bottleneck": {
                "type": RecommendationType.DEVELOPER_PRODUCTIVITY,
                "title_template": "CI/CD Pipeline Optimization: {pipeline}",
                "description_template": "{pipeline} pipeline is the slowest, averaging {time} minutes",
                "implementation_steps": [
                    "Analyze {pipeline} build steps",
                    "Optimize Docker layer caching",
                    "Parallelize test execution",
                    "Consider build artifact caching",
                    "Review dependency management",
                ],
                "estimated_effort": "1-2 days",
                "expected_impact": ImpactLevel.MEDIUM,
            },
            "golden_rules_violations": {
                "type": RecommendationType.ARCHITECTURAL_IMPROVEMENT,
                "title_template": "Code Quality Improvement: Golden Rules Violations",
                "description_template": "Golden Rules violations trending upward: {violation_count} violations",
                "implementation_steps": [
                    "Review recent violations in {files}",
                    "Update development guidelines",
                    "Implement pre-commit hooks",
                    "Schedule team training session",
                    "Add automated fixes where possible",
                ],
                "estimated_effort": "1 week",
                "expected_impact": ImpactLevel.MEDIUM,
            },
            "resource_exhaustion": {
                "type": RecommendationType.CAPACITY_PLANNING,
                "title_template": "Resource Capacity Alert: {resource}",
                "description_template": "{resource} usage at {percentage}% - exhaustion predicted in {timeframe}",
                "implementation_steps": [
                    "Monitor {resource} usage patterns",
                    "Identify resource-intensive operations",
                    "Plan capacity expansion",
                    "Implement resource optimization",
                    "Set up proactive alerts",
                ],
                "estimated_effort": "2-3 days",
                "expected_impact": ImpactLevel.HIGH,
            },
            # New architectural compliance templates,
            "global_state_violations": {
                "type": RecommendationType.ARCHITECTURAL_IMPROVEMENT,
                "title_template": "Critical: Global State Access Violations in {package}",
                "description_template": "Package {package} has {violation_count} global state access violations - high architectural risk",
                "implementation_steps": [
                    "Identify all global state access points in {package}",
                    "Refactor to use dependency injection patterns",
                    "Update constructors to accept configuration parameters",
                    "Remove singleton patterns and global variables",
                    "Add unit tests for refactored components",
                ],
                "estimated_effort": "1-2 weeks",
                "expected_impact": ImpactLevel.HIGH,
            },
            "test_coverage_gaps": {
                "type": RecommendationType.ARCHITECTURAL_IMPROVEMENT,
                "title_template": "Test Coverage Gaps: {package} Missing {missing_count} Test Files",
                "description_template": "Package {package} has {missing_count} source files without corresponding tests",
                "implementation_steps": [
                    "Create test files for all missing modules in {package}",
                    "Implement basic unit tests for public interfaces",
                    "Add property-based tests for core algorithms",
                    "Set up test coverage monitoring",
                    "Establish minimum coverage thresholds",
                ],
                "estimated_effort": "3-5 days",
                "expected_impact": ImpactLevel.MEDIUM,
            },
            "package_discipline_violations": {
                "type": RecommendationType.ARCHITECTURAL_IMPROVEMENT,
                "title_template": "Package Discipline: Business Logic in Infrastructure Package {package}",
                "description_template": "Package {package} contains business logic that should be moved to application layer",
                "implementation_steps": [
                    "Identify business logic components in {package}",
                    "Create appropriate application modules",
                    "Move business logic to app layer",
                    "Update package to provide only infrastructure services",
                    "Update documentation and ADRs",
                ],
                "estimated_effort": "1-2 weeks",
                "expected_impact": ImpactLevel.HIGH,
            },
            "dependency_direction_violations": {
                "type": RecommendationType.ARCHITECTURAL_IMPROVEMENT,
                "title_template": "Dependency Direction: Package {package} Imports from Applications",
                "description_template": "Package {package} has forbidden dependencies on application modules",
                "implementation_steps": [
                    "Identify all app imports in package {package}",
                    "Refactor to use service interfaces or event patterns",
                    "Implement proper dependency injection",
                    "Update package interfaces to be app-agnostic",
                    "Add architectural tests to prevent regression",
                ],
                "estimated_effort": "1-2 weeks",
                "expected_impact": ImpactLevel.TRANSFORMATIONAL,
            },
            "interface_contract_violations": {
                "type": RecommendationType.ARCHITECTURAL_IMPROVEMENT,
                "title_template": "Interface Contracts: {package} Missing Type Hints and Documentation",
                "description_template": "Package {package} has {violation_count} functions missing proper type hints or documentation",
                "implementation_steps": [
                    "Add type hints to all public functions in {package}",
                    "Add comprehensive docstrings to public APIs",
                    "Update async function naming conventions",
                    "Run mypy type checking and fix issues",
                    "Add type checking to CI pipeline",
                ],
                "estimated_effort": "2-3 days",
                "expected_impact": ImpactLevel.MEDIUM,
            },
            # Business strategy and product recommendation templates,
            "feature_deprecation": {
                "type": RecommendationType.PRODUCT_STRATEGY,
                "title_template": "Feature Deprecation Recommendation: {feature}",
                "description_template": "Feature '{feature}' has {adoption_rate:.1f}% adoption but costs ${cost:.0f}/month - recommend deprecation",
                "implementation_steps": [
                    "Analyze user impact and create migration plan for {feature}",
                    "Communicate deprecation timeline to affected users",
                    "Provide alternative solutions or feature recommendations",
                    "Gradually reduce feature prominence in UI",
                    "Set deprecation date and remove feature infrastructure",
                ],
                "estimated_effort": "2-3 weeks",
                "expected_impact": ImpactLevel.HIGH,
            },
            "feature_promotion": {
                "type": RecommendationType.PRODUCT_STRATEGY,
                "title_template": "Feature Promotion Opportunity: {feature}",
                "description_template": "Feature '{feature}' has high ROI ({roi_score:.1f}) but only {adoption_rate:.1f}% adoption - promote to increase value",
                "implementation_steps": [
                    "Create feature awareness campaign for {feature}",
                    "Add prominent UI placement and onboarding flows",
                    "Develop tutorial content and documentation",
                    "Implement usage analytics and A/B testing",
                    "Monitor adoption metrics and iterate",
                ],
                "estimated_effort": "1-2 weeks",
                "expected_impact": ImpactLevel.HIGH,
            },
            "user_experience_optimization": {
                "type": RecommendationType.USER_EXPERIENCE,
                "title_template": "UX Critical: {workflow} Workflow Optimization",
                "description_template": "Workflow '{workflow}' has {completion_time:.1f}min completion time vs {benchmark:.1f}min benchmark - {abandonment_rate:.0f}% abandonment",
                "implementation_steps": [
                    "Conduct user journey analysis for {workflow}",
                    "Identify and eliminate friction points",
                    "Implement progressive disclosure and smart defaults",
                    "Add contextual help and guidance",
                    "A/B test optimized workflow against current version",
                ],
                "estimated_effort": "2-4 weeks",
                "expected_impact": ImpactLevel.TRANSFORMATIONAL,
            },
            "customer_health_alert": {
                "type": RecommendationType.CUSTOMER_SUCCESS,
                "title_template": "Customer Health Alert: {customer} Needs Immediate Attention",
                "description_template": "Customer '{customer}' showing {error_increase:.0f}% increase in API errors over {duration}h - proactive support required",
                "implementation_steps": [
                    "Create high-priority support ticket for {customer}",
                    "Assign dedicated customer success manager",
                    "Analyze error patterns and provide detailed diagnostics",
                    "Schedule immediate technical consultation call",
                    "Implement monitoring and preventive measures",
                ],
                "estimated_effort": "1-2 days",
                "expected_impact": ImpactLevel.HIGH,
            },
            "conversion_optimization": {
                "type": RecommendationType.REVENUE_OPTIMIZATION,
                "title_template": "Conversion Rate Optimization: Trial to Paid",
                "description_template": "Trial-to-paid conversion at {conversion_rate:.1f}% vs {benchmark:.1f}% benchmark - {potential_revenue:.0f} monthly revenue at risk",
                "implementation_steps": [
                    "Analyze trial user behavior and drop-off points",
                    "Optimize onboarding flow and time-to-value",
                    "Implement targeted in-app messaging and offers",
                    "Create personalized upgrade prompts based on usage",
                    "A/B test pricing strategies and trial lengths",
                ],
                "estimated_effort": "3-6 weeks",
                "expected_impact": ImpactLevel.TRANSFORMATIONAL,
            },
            "revenue_leakage": {
                "type": RecommendationType.REVENUE_OPTIMIZATION,
                "title_template": "Revenue Leakage: High CAC with Low LTV",
                "description_template": "LTV:CAC ratio at {ltv_cac_ratio:.1f} vs 3.0+ target - ${potential_loss:.0f}/month revenue inefficiency",
                "implementation_steps": [
                    "Analyze customer acquisition channels and costs",
                    "Optimize high-performing, low-cost acquisition channels",
                    "Implement customer retention and expansion programs",
                    "Review and optimize pricing strategy",
                    "Focus acquisition on high-value customer segments",
                ],
                "estimated_effort": "4-8 weeks",
                "expected_impact": ImpactLevel.TRANSFORMATIONAL,
            },
            "feature_cost_optimization": {
                "type": RecommendationType.COST_OPTIMIZATION,
                "title_template": "Feature Cost Optimization: {feature} Resource Usage",
                "description_template": "Feature '{feature}' costs ${cost:.0f}/month but has {satisfaction:.1f}/5.0 user satisfaction - optimize for efficiency",
                "implementation_steps": [
                    "Profile {feature} resource usage and identify bottlenecks",
                    "Implement caching and query optimization",
                    "Consider alternative algorithms or AI models",
                    "Add usage-based throttling for cost control",
                    "Monitor cost vs satisfaction metrics post-optimization",
                ],
                "estimated_effort": "2-4 weeks",
                "expected_impact": ImpactLevel.HIGH,
            },
            "customer_expansion_opportunity": {
                "type": RecommendationType.BUSINESS_INTELLIGENCE,
                "title_template": "Customer Expansion: {segment} Segment Growth Opportunity",
                "description_template": "{segment} customers show {usage_growth:.0f}% usage growth and {satisfaction:.1f} NPS - prime for expansion",
                "implementation_steps": [
                    "Identify expansion opportunities within {segment} segment",
                    "Create targeted upselling campaigns and offers",
                    "Develop premium features aligned with segment needs",
                    "Implement account-based marketing strategies",
                    "Track expansion revenue and customer lifetime value",
                ],
                "estimated_effort": "2-6 weeks",
                "expected_impact": ImpactLevel.HIGH,
            },
        }

    async def generate_recommendations_async(
        self, hours: int = 24, include_predictive: bool = True
    ) -> RecommendationReport:
        """Generate comprehensive strategic recommendations."""

        logger.info(f"Generating recommendations for last {hours} hours")

        # Get insights from analytics engine
        insights = await self.analytics.generate_insights_async(hours=hours)
        trends = await self.analytics.analyze_trends_async(hours=hours)
        anomalies = await self.analytics.detect_anomalies_async(hours=hours)

        # Generate recommendations
        recommendations = []

        # Cost optimization recommendations
        cost_recommendations = await self._generate_cost_recommendations_async(insights, trends)
        recommendations.extend(cost_recommendations)

        # Performance recommendations
        perf_recommendations = await self._generate_performance_recommendations_async(insights, trends, anomalies)
        recommendations.extend(perf_recommendations)

        # Developer productivity recommendations
        dev_recommendations = await self._generate_developer_recommendations_async(trends)
        recommendations.extend(dev_recommendations)

        # Predictive maintenance recommendations
        if include_predictive:
            predictive_recommendations = await self._generate_predictive_recommendations_async(trends, anomalies)
            recommendations.extend(predictive_recommendations)

        # Security recommendations
        security_recommendations = await self._generate_security_recommendations_async(anomalies)
        recommendations.extend(security_recommendations)

        # Architectural compliance recommendations
        architectural_recommendations = await self._generate_architectural_recommendations_async()
        recommendations.extend(architectural_recommendations)

        # Business strategy recommendations
        business_recommendations = await self._generate_business_strategy_recommendations_async()
        recommendations.extend(business_recommendations)

        # Sort and categorize recommendations
        recommendations.sort(
            key=lambda r: (
                {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}[r.priority.value],
                {"transformational": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}[r.expected_impact.value],
            ),
            reverse=True,
        )

        # Create report
        report = self._create_recommendation_report(recommendations, insights)

        logger.info(f"Generated {len(recommendations)} recommendations")
        return report

    async def _generate_cost_recommendations_async(
        self, insights: list[Insight], trends: list[TrendAnalysis]
    ) -> list[Recommendation]:
        """Generate cost optimization recommendations."""

        recommendations = []

        # Check for AI cost trends
        cost_trends = [t for t in trends if "cost" in t.metric_name.lower()]

        for trend in cost_trends:
            if trend.change_rate > 25 and trend.confidence > 0.7:  # 25% cost increase
                template = self.recommendation_templates["high_ai_costs"]

                # Extract model name from metric
                model_name = "AI models"  # Default
                if "gpt" in trend.metric_name.lower():
                    model_name = "GPT models"
                elif "claude" in trend.metric_name.lower():
                    model_name = "Claude models"

                # Calculate potential savings
                potential_savings = trend.current_value * 0.4  # Assume 40% potential savings

                recommendation = Recommendation(
                    title=template["title_template"].format(model=model_name),
                    description=template["description_template"].format(
                        model=model_name, percentage=f"{trend.change_rate:.1f}", period=f"{trend.time_period.days} days"
                    ),
                    recommendation_type=template["type"],
                    priority=Priority.HIGH if trend.change_rate > 50 else Priority.MEDIUM,
                    expected_impact=template["expected_impact"],
                    impact_description=f"Potential cost reduction of ${potential_savings:.2f}/month",
                    estimated_benefit=f"40-60% cost reduction (~${potential_savings:.2f}/month)",
                    implementation_steps=[step.format(model=model_name) for step in template["implementation_steps"]],
                    estimated_effort=template["estimated_effort"],
                    required_resources=["DevOps engineer", "Data analyst"],
                    trends=[trend],
                    supporting_metrics=[trend.metric_name],
                    github_issue_title=f"Cost Optimization: {model_name} Usage Analysis",
                    github_labels=["cost-optimization", "ai", "high-priority"],
                )

                recommendations.append(recommendation)

        # Check for budget exhaustion predictions,
        cost_insights = [i for i in insights if i.category == "cost"]

        for insight in cost_insights:
            if "budget" in insight.description.lower():
                recommendation = Recommendation(
                    title="Budget Alert: Cost Controls Implementation",
                    description="Current spending trajectory will exceed budget limits",
                    recommendation_type=RecommendationType.COST_OPTIMIZATION,
                    priority=Priority.CRITICAL,
                    expected_impact=ImpactLevel.HIGH,
                    impact_description="Prevent budget overrun and establish cost controls",
                    estimated_benefit="Maintain budget compliance, prevent cost overruns",
                    implementation_steps=[
                        "Implement daily cost monitoring",
                        "Set up automated cost alerts",
                        "Review and optimize high-cost operations",
                        "Establish usage quotas for AI services",
                        "Create cost approval workflows",
                    ],
                    estimated_effort="2-3 days",
                    required_resources=["DevOps engineer", "Finance team"],
                    github_issue_title="URGENT: Implement Cost Controls to Prevent Budget Overrun",
                    github_labels=["cost-optimization", "urgent", "budget"],
                )

                recommendations.append(recommendation)

        return recommendations

    async def _generate_performance_recommendations_async(
        self, insights: list[Insight], trends: list[TrendAnalysis], anomalies: list[Anomaly]
    ) -> list[Recommendation]:
        """Generate performance improvement recommendations."""

        recommendations = []

        # Check for performance degradation trends,
        perf_trends = [
            t for t in trends if "performance" in t.metric_name.lower() or "response" in t.metric_name.lower()
        ]

        for trend in perf_trends:
            if trend.direction.value == "degrading" and trend.confidence > 0.6:
                template = self.recommendation_templates["performance_degradation"]

                # Determine service name,
                service_name = "application",
                if "database" in trend.metric_name.lower():
                    service_name = "database",
                elif "api" in trend.metric_name.lower():
                    service_name = "API service"

                # Determine component,
                component = "application layer",
                if "database" in trend.metric_name.lower():
                    component = "database queries",
                elif "network" in trend.metric_name.lower():
                    component = "network connectivity"

                priority = Priority.CRITICAL if abs(trend.change_rate) > 50 else Priority.HIGH

                recommendation = Recommendation(
                    title=template["title_template"].format(service=service_name),
                    description=template["description_template"].format(
                        service=service_name,
                        percentage=f"{abs(trend.change_rate):.1f}",
                        period=f"{trend.time_period.days} days",
                    ),
                    recommendation_type=template["type"],
                    priority=priority,
                    expected_impact=template["expected_impact"],
                    impact_description=f"Restore {service_name} performance to baseline levels",
                    estimated_benefit=f"Improve {service_name} performance by {abs(trend.change_rate):.1f}%",
                    implementation_steps=[
                        step.format(service=service_name, component=component)
                        for step in template["implementation_steps"]
                    ],
                    estimated_effort=template["estimated_effort"],
                    required_resources=["Backend engineer", "DevOps engineer"],
                    trends=[trend],
                    supporting_metrics=[trend.metric_name],
                    github_issue_title=f"Performance Issue: {service_name} Degradation",
                    github_labels=["performance", "maintenance", "high-priority"],
                )

                recommendations.append(recommendation)

        # Check for performance anomalies,
        perf_anomalies = [a for a in anomalies if "performance" in a.metric_name.lower()]

        if len(perf_anomalies) > 2:  # Multiple performance anomalies,
            recommendation = Recommendation(
                title="System-Wide Performance Investigation",
                description=f"Multiple performance anomalies detected: {len(perf_anomalies)} issues",
                recommendation_type=RecommendationType.PREDICTIVE_MAINTENANCE,
                priority=Priority.HIGH,
                expected_impact=ImpactLevel.HIGH,
                impact_description="Prevent system-wide performance degradation",
                estimated_benefit="Maintain system performance and reliability",
                implementation_steps=[
                    "Conduct comprehensive system health check",
                    "Review resource utilization across all services",
                    "Analyze correlation between performance anomalies",
                    "Implement enhanced monitoring",
                    "Create performance baseline documentation",
                ],
                estimated_effort="3-5 days",
                required_resources=["Senior engineer", "DevOps team"],
                anomalies=perf_anomalies,
                supporting_metrics=[a.metric_name for a in perf_anomalies],
                github_issue_title="System Performance Investigation: Multiple Anomalies Detected",
                github_labels=["performance", "investigation", "system-health"],
            )

            recommendations.append(recommendation)

        return recommendations

    async def _generate_developer_recommendations_async(self, trends: list[TrendAnalysis]) -> list[Recommendation]:
        """Generate developer productivity recommendations."""

        recommendations = []

        # Check for CI/CD performance issues,
        cicd_trends = [t for t in trends if "cicd" in t.metric_name.lower() or "pipeline" in t.metric_name.lower()]

        for trend in cicd_trends:
            if trend.direction.value == "degrading" and trend.confidence > 0.6:
                template = self.recommendation_templates["cicd_bottleneck"]

                pipeline_name = "CI/CD pipeline",
                if "test" in trend.metric_name.lower():
                    pipeline_name = "test pipeline",
                elif "build" in trend.metric_name.lower():
                    pipeline_name = "build pipeline"

                # Estimate time impact,
                time_minutes = trend.current_value if trend.current_value > 10 else 15

                recommendation = Recommendation(
                    title=template["title_template"].format(pipeline=pipeline_name),
                    description=template["description_template"].format(
                        pipeline=pipeline_name, time=f"{time_minutes:.1f}"
                    ),
                    recommendation_type=template["type"],
                    priority=Priority.MEDIUM,
                    expected_impact=template["expected_impact"],
                    impact_description=f"Reduce {pipeline_name} time by 30-50%",
                    estimated_benefit=f"Save {time_minutes * 0.4:.1f} minutes per build",
                    implementation_steps=[
                        step.format(pipeline=pipeline_name) for step in template["implementation_steps"]
                    ],
                    estimated_effort=template["estimated_effort"],
                    required_resources=["DevOps engineer"],
                    trends=[trend],
                    supporting_metrics=[trend.metric_name],
                    github_issue_title=f"CI/CD Optimization: Improve {pipeline_name} Performance",
                    github_labels=["developer-experience", "cicd", "optimization"],
                )

                recommendations.append(recommendation)

        return recommendations

    async def _generate_predictive_recommendations_async(
        self, trends: list[TrendAnalysis], anomalies: list[Anomaly]
    ) -> list[Recommendation]:
        """Generate predictive maintenance recommendations."""

        recommendations = []

        # Look for trends that predict future issues,
        for trend in trends:
            if trend.confidence > 0.8 and trend.predicted_value_24h:
                current = trend.current_value,
                predicted = trend.predicted_value_24h

                # Check for resource exhaustion prediction,
                if "memory" in trend.metric_name.lower() or "disk" in trend.metric_name.lower():
                    if predicted > 90 and current < 80:  # Predict resource exhaustion,
                        resource_name = "memory" if "memory" in trend.metric_name.lower() else "disk"

                        template = self.recommendation_templates["resource_exhaustion"]

                        # Calculate time to exhaustion,
                        if trend.slope > 0:
                            time_to_exhaustion = (95 - current) / (trend.slope * 24)  # hours,
                            timeframe = f"{time_to_exhaustion:.1f} hours",
                        else:
                            timeframe = "unknown"

                        recommendation = Recommendation(
                            title=template["title_template"].format(resource=resource_name),
                            description=template["description_template"].format(
                                resource=resource_name, percentage=f"{current:.1f}", timeframe=timeframe
                            ),
                            recommendation_type=template["type"],
                            priority=Priority.HIGH,
                            expected_impact=template["expected_impact"],
                            impact_description=f"Prevent {resource_name} exhaustion and system downtime",
                            estimated_benefit="Maintain system availability and performance",
                            implementation_steps=[
                                step.format(resource=resource_name) for step in template["implementation_steps"]
                            ],
                            estimated_effort=template["estimated_effort"],
                            required_resources=["Infrastructure team", "DevOps engineer"],
                            trends=[trend],
                            supporting_metrics=[trend.metric_name],
                            github_issue_title=f"Capacity Planning: {resource_name.title()} Exhaustion Predicted",
                            github_labels=["capacity-planning", "predictive", "infrastructure"],
                        )

                        recommendations.append(recommendation)

        return recommendations

    async def _generate_security_recommendations_async(self, anomalies: list[Anomaly]) -> list[Recommendation]:
        """Generate security enhancement recommendations."""

        recommendations = []

        # Look for security-related anomalies,
        security_anomalies = [
            a
            for a in anomalies
            if "error" in a.metric_name.lower() or "security" in a.metric_name.lower() or a.deviation_score > 4.0
        ]  # Very high deviation

        if len(security_anomalies) > 1:
            recommendation = Recommendation(
                title="Security Monitoring Enhancement",
                description=f"Multiple security-related anomalies detected: {len(security_anomalies)} issues",
                recommendation_type=RecommendationType.SECURITY_ENHANCEMENT,
                priority=Priority.HIGH,
                expected_impact=ImpactLevel.MEDIUM,
                impact_description="Improve security posture and anomaly detection",
                estimated_benefit="Enhanced security monitoring and faster threat detection",
                implementation_steps=[
                    "Review security monitoring configuration",
                    "Enhance anomaly detection thresholds",
                    "Implement additional security metrics",
                    "Set up security incident response procedures",
                    "Schedule security audit",
                ],
                estimated_effort="1 week",
                required_resources=["Security engineer", "DevOps team"],
                anomalies=security_anomalies,
                supporting_metrics=[a.metric_name for a in security_anomalies],
                github_issue_title="Security Enhancement: Improve Anomaly Detection and Monitoring",
                github_labels=["security", "monitoring", "enhancement"],
            )

            recommendations.append(recommendation)

        return recommendations

    async def _generate_architectural_recommendations_async(self) -> list[Recommendation]:
        """Generate architectural compliance and improvement recommendations."""

        recommendations = []

        try:
            # Get recent architectural metrics,
            violation_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.ARCHITECTURAL_VIOLATION],
                start_time=datetime.utcnow() - timedelta(hours=48),  # Look back 48 hours for trends,
                limit=500,
            )

            compliance_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.GOLDEN_RULES_COMPLIANCE],
                start_time=datetime.utcnow() - timedelta(hours=24),
                limit=50,
            )

            debt_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.TECHNICAL_DEBT], start_time=datetime.utcnow() - timedelta(hours=24), limit=10
            )

            # Analyze violations by rule type and package,
            violations_by_rule = {}
            violations_by_package = {}

            for violation in violation_metrics:
                rule_name = violation.tags.get("rule_name", "unknown")
                violations_by_rule[rule_name] = violations_by_rule.get(rule_name, 0) + 1

                # Extract package from violation description,
                description = violation.metadata.get("violation_description", "")
                if "hive-" in description:
                    parts = description.split("hive-")
                    if len(parts) > 1:
                        package_part = parts[1].split("'")[0].split(" ")[0].split("/")[0]
                        package_name = f"hive-{package_part}",
                        violations_by_package[package_name] = violations_by_package.get(package_name, 0) + 1

            # Generate recommendations based on violation patterns

            # 1. Global State Access Violations,
            global_state_violations = violations_by_rule.get("Golden Rule 16: No Global State Access", 0)
            if global_state_violations > 0:
                # Find the package with most violations,
                affected_packages = {}
                for violation in violation_metrics:
                    if "Global State" in violation.tags.get("rule_name", ""):
                        desc = violation.metadata.get("violation_description", "")
                        if "hive-" in desc:
                            parts = desc.split("hive-")
                            if len(parts) > 1:
                                # Extract package name outside f-string to avoid backslash issues
                                pkg_part = parts[1].split("'")[0].split(" ")[0].split("/")[0]
                                package = f"hive-{pkg_part}"
                                affected_packages[package] = affected_packages.get(package, 0) + 1

                if affected_packages:
                    worst_package = max(affected_packages.items(), key=lambda x: x[1])
                    template = self.recommendation_templates["global_state_violations"]

                    recommendation = Recommendation(
                        title=template["title_template"].format(package=worst_package[0]),
                        description=template["description_template"].format(
                            package=worst_package[0], violation_count=worst_package[1]
                        ),
                        recommendation_type=template["type"],
                        priority=Priority.CRITICAL,  # Global state is critical,
                        expected_impact=template["expected_impact"],
                        impact_description=f"Eliminate architectural debt and improve maintainability in {worst_package[0]}",
                        estimated_benefit="15% reduction in maintenance costs, improved testability",
                        implementation_steps=[
                            step.format(package=worst_package[0]) for step in template["implementation_steps"]
                        ],
                        estimated_effort=template["estimated_effort"],
                        required_resources=["Senior engineer", "Architecture review"],
                        supporting_metrics=[f"global_state_violations_{worst_package[0]}"],
                        github_issue_title=f"CRITICAL: Refactor Global State Access in {worst_package[0]}",
                        github_labels=["architecture", "critical", "technical-debt", "global-state"],
                    )

                    recommendations.append(recommendation)

            # 2. Test Coverage Gaps,
            test_violations = violations_by_rule.get("Golden Rule 17: Test-to-Source File Mapping", 0)
            if test_violations > 10:  # Significant test coverage gap,
                # Find package with most missing tests,
                test_packages = {}
                for violation in violation_metrics:
                    if "Test-to-Source" in violation.tags.get("rule_name", ""):
                        desc = violation.metadata.get("violation_description", "")
                        if "hive-" in desc:
                            parts = desc.split("hive-")
                            if len(parts) > 1:
                                package = f"hive-{parts[1].split(':')[0]}",
                                test_packages[package] = test_packages.get(package, 0) + 1

                if test_packages:
                    worst_package = max(test_packages.items(), key=lambda x: x[1])
                    template = self.recommendation_templates["test_coverage_gaps"]

                    recommendation = Recommendation(
                        title=template["title_template"].format(
                            package=worst_package[0], missing_count=worst_package[1]
                        ),
                        description=template["description_template"].format(
                            package=worst_package[0], missing_count=worst_package[1]
                        ),
                        recommendation_type=template["type"],
                        priority=Priority.HIGH,
                        expected_impact=template["expected_impact"],
                        impact_description=f"Improve test coverage and code reliability for {worst_package[0]}",
                        estimated_benefit="Reduce production bugs by 30%, improve confidence in changes",
                        implementation_steps=[
                            step.format(package=worst_package[0]) for step in template["implementation_steps"]
                        ],
                        estimated_effort=template["estimated_effort"],
                        required_resources=["Developer", "QA engineer"],
                        supporting_metrics=[f"missing_tests_{worst_package[0]}"],
                        github_issue_title=f"Test Coverage: Add Missing Tests for {worst_package[0]}",
                        github_labels=["testing", "coverage", "quality"],
                    )

                    recommendations.append(recommendation)

            # 3. Package Discipline Violations,
            discipline_violations = violations_by_rule.get("Golden Rule 5: Package vs App Discipline", 0)
            if discipline_violations > 0:
                affected_packages = {}
                for violation in violation_metrics:
                    if "Package vs App Discipline" in violation.tags.get("rule_name", ""):
                        desc = violation.metadata.get("violation_description", "")
                        if "Package '" in desc:
                            package = desc.split("Package '")[1].split("'")[0]
                            affected_packages[package] = affected_packages.get(package, 0) + 1

                if affected_packages:
                    worst_package = max(affected_packages.items(), key=lambda x: x[1])
                    template = self.recommendation_templates["package_discipline_violations"]

                    recommendation = Recommendation(
                        title=template["title_template"].format(package=worst_package[0]),
                        description=template["description_template"].format(package=worst_package[0]),
                        recommendation_type=template["type"],
                        priority=Priority.HIGH,
                        expected_impact=template["expected_impact"],
                        impact_description="Improve architectural clarity and package reusability",
                        estimated_benefit="Better separation of concerns, improved package reusability",
                        implementation_steps=[
                            step.format(package=worst_package[0]) for step in template["implementation_steps"]
                        ],
                        estimated_effort=template["estimated_effort"],
                        required_resources=["Senior engineer", "Architecture team"],
                        supporting_metrics=[f"discipline_violations_{worst_package[0]}"],
                        github_issue_title=f"Architecture: Fix Package Discipline in {worst_package[0]}",
                        github_labels=["architecture", "package-discipline", "refactoring"],
                    )

                    recommendations.append(recommendation)

            # 4. Interface Contract Violations,
            interface_violations = violations_by_rule.get("Golden Rule 7: Interface Contracts", 0)
            if interface_violations > 20:  # Many missing type hints/docs,
                template = self.recommendation_templates["interface_contract_violations"]

                # Find most affected package,
                affected_packages = {}
                for violation in violation_metrics:
                    if "Interface Contracts" in violation.tags.get("rule_name", ""):
                        desc = violation.metadata.get("violation_description", "")
                        if ":" in desc:
                            file_path = desc.split(":")[0]
                            if "packages/" in file_path:
                                package_part = file_path.split("packages/")[1].split("/")[0]
                                affected_packages[package_part] = affected_packages.get(package_part, 0) + 1

                if affected_packages:
                    worst_package = max(affected_packages.items(), key=lambda x: x[1])

                    recommendation = Recommendation(
                        title=template["title_template"].format(package=worst_package[0]),
                        description=template["description_template"].format(
                            package=worst_package[0], violation_count=worst_package[1]
                        ),
                        recommendation_type=template["type"],
                        priority=Priority.MEDIUM,
                        expected_impact=template["expected_impact"],
                        impact_description=f"Improve API documentation and type safety for {worst_package[0]}",
                        estimated_benefit="Better developer experience, fewer runtime type errors",
                        implementation_steps=[
                            step.format(package=worst_package[0]) for step in template["implementation_steps"]
                        ],
                        estimated_effort=template["estimated_effort"],
                        required_resources=["Developer"],
                        supporting_metrics=[f"interface_violations_{worst_package[0]}"],
                        github_issue_title=f"Documentation: Add Type Hints and Docs to {worst_package[0]}",
                        github_labels=["documentation", "type-hints", "api"],
                    )

                    recommendations.append(recommendation)

            # 5. Overall compliance recommendation if score is low,
            if compliance_metrics:
                latest_compliance = max(compliance_metrics, key=lambda x: x.timestamp)
                compliance_score = float(latest_compliance.value)

                if compliance_score < 60:  # Poor overall compliance
                    recommendation = Recommendation(
                        title="URGENT: Platform Architectural Compliance Crisis",
                        description=f"Overall Golden Rules compliance is critically low at {compliance_score:.1f}%",
                        recommendation_type=RecommendationType.ARCHITECTURAL_IMPROVEMENT,
                        priority=Priority.CRITICAL,
                        expected_impact=ImpactLevel.TRANSFORMATIONAL,
                        impact_description="Prevent architectural decay and technical debt accumulation",
                        estimated_benefit="Restore platform architectural integrity, prevent future maintenance costs",
                        implementation_steps=[
                            "Declare architectural emergency and form task force",
                            "Prioritize fixing critical violations first",
                            "Implement daily architectural compliance monitoring",
                            "Establish architectural review gates for all changes",
                            "Create architectural debt reduction roadmap",
                        ],
                        estimated_effort="2-4 weeks",
                        required_resources=["Architecture team", "Senior engineers", "Tech lead"],
                        supporting_metrics=["overall_compliance_score"],
                        github_issue_title="EMERGENCY: Restore Platform Architectural Compliance",
                        github_labels=["architecture", "emergency", "compliance", "technical-debt"],
                    )

                    recommendations.append(recommendation)

            logger.info(f"Generated {len(recommendations)} architectural recommendations")

        except Exception as e:
            logger.error(f"Failed to generate architectural recommendations: {e}")

        return recommendations

    async def _generate_business_strategy_recommendations_async(self) -> list[Recommendation]:
        """Generate business strategy and product recommendations."""

        recommendations = []

        try:
            # Get business intelligence metrics,
            feature_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.FEATURE_ADOPTION], start_time=datetime.utcnow() - timedelta(days=7), limit=100
            )

            user_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.USER_BEHAVIOR, MetricType.USER_ENGAGEMENT],
                start_time=datetime.utcnow() - timedelta(days=7),
                limit=100,
            )

            business_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.REVENUE_METRICS, MetricType.CONVERSION_RATE, MetricType.BUSINESS_KPI],
                start_time=datetime.utcnow() - timedelta(days=30),
                limit=100,
            )

            customer_metrics = await self.warehouse.query_metrics_async(
                metric_types=[MetricType.CUSTOMER_SATISFACTION, MetricType.SUPPORT_METRICS],
                start_time=datetime.utcnow() - timedelta(days=7),
                limit=100,
            )

            # 1. Feature deprecation recommendations,
            for metric in feature_metrics:
                if metric.tags.get("review_required") == "true":
                    feature_name = metric.tags.get("feature_name", "Unknown")
                    adoption_rate = float(metric.value)
                    operational_cost = float(metric.metadata.get("operational_cost", 0))

                    if adoption_rate < 10 and operational_cost > 500:
                        template = self.recommendation_templates["feature_deprecation"]

                        recommendation = Recommendation(
                            title=template["title_template"].format(feature=feature_name),
                            description=template["description_template"].format(
                                feature=feature_name, adoption_rate=adoption_rate, cost=operational_cost
                            ),
                            recommendation_type=template["type"],
                            priority=Priority.HIGH,
                            expected_impact=template["expected_impact"],
                            impact_description=f"Reduce operational costs by ${operational_cost * 0.8:.0f}/month",
                            estimated_benefit=f"${operational_cost * 0.8:.0f}/month cost savings, simplified product focus",
                            implementation_steps=[
                                step.format(feature=feature_name) for step in template["implementation_steps"]
                            ],
                            estimated_effort=template["estimated_effort"],
                            required_resources=["Product manager", "Engineering team", "Customer success"],
                            supporting_metrics=[f"feature_adoption_{feature_name}"],
                            github_issue_title=f"Product Strategy: Deprecate {feature_name} Feature",
                            github_labels=["product", "deprecation", "cost-optimization"],
                        )

                        recommendations.append(recommendation)

            # 2. Feature promotion recommendations,
            for metric in feature_metrics:
                feature_name = metric.tags.get("feature_name", "Unknown")
                adoption_rate = float(metric.value)
                roi_score = float(metric.metadata.get("roi_score", 0))

                if roi_score > 10 and adoption_rate < 70:
                    template = self.recommendation_templates["feature_promotion"]

                    recommendation = Recommendation(
                        title=template["title_template"].format(feature=feature_name),
                        description=template["description_template"].format(
                            feature=feature_name, roi_score=roi_score, adoption_rate=adoption_rate
                        ),
                        recommendation_type=template["type"],
                        priority=Priority.MEDIUM,
                        expected_impact=template["expected_impact"],
                        impact_description=f"Increase feature adoption to 80%+ for {feature_name}",
                        estimated_benefit=f"Potential {(80 - adoption_rate) * 0.01 * 100:.0f}% increase in feature value realization",
                        implementation_steps=[
                            step.format(feature=feature_name) for step in template["implementation_steps"]
                        ],
                        estimated_effort=template["estimated_effort"],
                        required_resources=["Product marketing", "UX team", "Content team"],
                        supporting_metrics=[f"feature_roi_{feature_name}"],
                        github_issue_title=f"Product Marketing: Promote High-ROI Feature {feature_name}",
                        github_labels=["product", "marketing", "feature-promotion"],
                    )

                    recommendations.append(recommendation)

            # 3. User experience optimization,
            for metric in user_metrics:
                if metric.metric_type == MetricType.USER_BEHAVIOR and metric.tags.get("priority") == "high":
                    workflow = metric.tags.get("workflow", "Unknown")
                    completion_time = float(metric.value)
                    benchmark = float(metric.metadata.get("industry_benchmark", 5.0))
                    abandonment_rate = float(metric.metadata.get("abandonment_rate", 0)) * 100

                    if completion_time > benchmark * 2:  # More than 2x benchmark
                        template = self.recommendation_templates["user_experience_optimization"]

                        recommendation = Recommendation(
                            title=template["title_template"].format(workflow=workflow),
                            description=template["description_template"].format(
                                workflow=workflow,
                                completion_time=completion_time,
                                benchmark=benchmark,
                                abandonment_rate=abandonment_rate,
                            ),
                            recommendation_type=template["type"],
                            priority=Priority.HIGH if abandonment_rate > 20 else Priority.MEDIUM,
                            expected_impact=template["expected_impact"],
                            impact_description=f"Reduce {workflow} completion time to {benchmark:.1f}min benchmark",
                            estimated_benefit=f"Reduce abandonment by {abandonment_rate * 0.5:.0f}%, improve user satisfaction",
                            implementation_steps=[
                                step.format(workflow=workflow) for step in template["implementation_steps"]
                            ],
                            estimated_effort=template["estimated_effort"],
                            required_resources=["UX designer", "Frontend team", "Product analyst"],
                            supporting_metrics=[f"workflow_time_{workflow}"],
                            github_issue_title=f"UX Optimization: Streamline {workflow} Workflow",
                            github_labels=["ux", "workflow", "optimization"],
                        )

                        recommendations.append(recommendation)

            # 4. Customer health alerts,
            for metric in customer_metrics:
                if (
metric.metric_type == MetricType.CUSTOMER_SATISFACTION
                    and "error_rate_change" in metric.unit
                    and metric.tags.get("alert_level") == "critical"
                ):
                    customer = metric.tags.get("customer", "Unknown")
                    error_increase = float(metric.value) * 100
                    duration = float(metric.metadata.get("duration_hours", 24))

                    template = self.recommendation_templates["customer_health_alert"]

                    recommendation = Recommendation(
                        title=template["title_template"].format(customer=customer),
                        description=template["description_template"].format(
                            customer=customer, error_increase=error_increase, duration=duration
                        ),
                        recommendation_type=template["type"],
                        priority=Priority.CRITICAL,
                        expected_impact=template["expected_impact"],
                        impact_description=f"Prevent churn and maintain relationship with {customer}",
                        estimated_benefit="Retain enterprise customer, prevent potential revenue loss",
                        implementation_steps=[
                            step.format(customer=customer) for step in template["implementation_steps"]
                        ],
                        estimated_effort=template["estimated_effort"],
                        required_resources=["Customer success manager", "Support engineer", "Account manager"],
                        supporting_metrics=[f"customer_health_{customer}"],
                        github_issue_title=f"URGENT: Customer Health Alert - {customer}",
                        github_labels=["customer-success", "urgent", "enterprise"],
                    )

                    recommendations.append(recommendation)

            # 5. Conversion optimization,
            for metric in business_metrics:
                if (
metric.metric_type == MetricType.CONVERSION_RATE
                    and metric.tags.get("performance") == "below_benchmark"
                ):
                    conversion_rate = float(metric.value)
                    benchmark = float(metric.metadata.get("benchmark", 5.0))
                    trial_users = int(metric.metadata.get("trial_users", 100))
                    potential_revenue = (
                        (benchmark - conversion_rate) * 0.01 * trial_users * 100
                    )  # Simplified calculation

                    template = self.recommendation_templates["conversion_optimization"]

                    recommendation = Recommendation(
                        title=template["title_template"],
                        description=template["description_template"].format(
                            conversion_rate=conversion_rate, benchmark=benchmark, potential_revenue=potential_revenue
                        ),
                        recommendation_type=template["type"],
                        priority=Priority.HIGH,
                        expected_impact=template["expected_impact"],
                        impact_description=f"Increase conversion rate from {conversion_rate:.1f}% to {benchmark:.1f}%",
                        estimated_benefit=f"${potential_revenue:.0f}/month additional recurring revenue",
                        implementation_steps=template["implementation_steps"],
                        estimated_effort=template["estimated_effort"],
                        required_resources=["Growth team", "Product manager", "Data analyst", "UX designer"],
                        supporting_metrics=["trial_conversion_rate"],
                        github_issue_title="Revenue Optimization: Improve Trial-to-Paid Conversion",
                        github_labels=["revenue", "conversion", "growth"],
                    )

                    recommendations.append(recommendation)

            # 6. Revenue leakage optimization,
            for metric in business_metrics:
                if metric.metric_type == MetricType.BUSINESS_KPI and "cac" in metric.tags.get("metric_name", ""):
                    ltv_cac_ratio = float(metric.metadata.get("ltv_cac_ratio", 0))
                    if ltv_cac_ratio < 3.0:
                        cac = float(metric.value)
                        potential_loss = cac * 10  # Simplified calculation

                        template = self.recommendation_templates["revenue_leakage"]

                        recommendation = Recommendation(
                            title=template["title_template"],
                            description=template["description_template"].format(
                                ltv_cac_ratio=ltv_cac_ratio, potential_loss=potential_loss
                            ),
                            recommendation_type=template["type"],
                            priority=Priority.HIGH,
                            expected_impact=template["expected_impact"],
                            impact_description=f"Improve LTV:CAC ratio from {ltv_cac_ratio:.1f} to 3.0+",
                            estimated_benefit=f"${potential_loss:.0f}/month efficiency improvement",
                            implementation_steps=template["implementation_steps"],
                            estimated_effort=template["estimated_effort"],
                            required_resources=["Growth team", "Marketing", "Customer success", "Product"],
                            supporting_metrics=["ltv_cac_ratio"],
                            github_issue_title="Business Strategy: Optimize Customer Acquisition Efficiency",
                            github_labels=["business", "cac", "ltv", "efficiency"],
                        )

                        recommendations.append(recommendation)

            logger.info(f"Generated {len(recommendations)} business strategy recommendations")

        except Exception as e:
            logger.error(f"Failed to generate business strategy recommendations: {e}")

        return recommendations

    def _create_recommendation_report(
        self, recommendations: list[Recommendation], insights: list[Insight]
    ) -> RecommendationReport:
        """Create comprehensive recommendation report."""

        # Categorize recommendations by priority,
        critical = [r for r in recommendations if r.priority == Priority.CRITICAL]
        high = [r for r in recommendations if r.priority == Priority.HIGH]
        medium = [r for r in recommendations if r.priority == Priority.MEDIUM]
        low = [r for r in recommendations if r.priority == Priority.LOW]

        # Calculate potential savings,
        total_savings = 0.0,
        for rec in recommendations:
            if rec.recommendation_type == RecommendationType.COST_OPTIMIZATION:
                # Extract savings from estimated_benefit,
                benefit = rec.estimated_benefit or "",
                if "$" in benefit:
                    try:
                        # Simple extraction - in real implementation, use proper parsing,
                        savings_str = benefit.split("$")[1].split("/")[0].replace(",", "")
                        total_savings += float(savings_str)
                    except (ValueError, IndexError):
                        pass

        # Generate key insights,
        key_insights = []

        if critical:
            key_insights.append(
                StrategicInsight(
                    title="Critical Actions Required",
                    description=f"{len(critical)} critical recommendations require immediate attention",
                    category="urgency",
                    confidence_score=0.9,
                    risk_level="high",
                )
            )

        if total_savings > 100:
            key_insights.append(
                StrategicInsight(
                    title="Significant Cost Optimization Opportunity",
                    description=f"Potential monthly savings of ${total_savings:.2f} identified",
                    category="cost",
                    confidence_score=0.8,
                    risk_level="low",
                )
            )

        # Immediate actions,
        immediate_actions = []
        for rec in critical + high[:3]:  # Top critical and high priority,
            immediate_actions.extend(rec.implementation_steps[:2])  # First 2 steps

        # Generate summary,
        summary = f""",
        Generated {len(recommendations)} strategic recommendations based on platform analysis.

        Priority Breakdown:
        - Critical: {len(critical)} recommendations,
        - High: {len(high)} recommendations,
        - Medium: {len(medium)} recommendations,
        - Low: {len(low)} recommendations

        Key Focus Areas:
        - Cost optimization potential: ${total_savings:.2f}/month,
        - Performance improvements identified,
        - Predictive maintenance opportunities,
        - Developer productivity enhancements,
        """

        return RecommendationReport(
            title="Hive Platform Strategic Recommendations",
            summary=summary.strip(),
            generated_at=datetime.utcnow(),
            critical_recommendations=critical,
            high_priority_recommendations=high,
            medium_priority_recommendations=medium,
            low_priority_recommendations=low,
            key_insights=key_insights,
            total_potential_savings=total_savings,
            total_risk_mitigation="Enhanced monitoring and predictive maintenance",
            recommended_immediate_actions=immediate_actions[:5],  # Top 5
        )

    async def create_github_issues_async(
        self, recommendations: list[Recommendation], repository: str = "hive"
    ) -> list[dict[str, Any]]:
        """Create GitHub issues for recommendations (returns issue data for API calls)."""

        issues = []

        for rec in recommendations:
            if rec.priority in [Priority.CRITICAL, Priority.HIGH]:
                # Generate detailed issue body,
                issue_body = self._generate_github_issue_body(rec)

                issue_data = {
                    "title": rec.github_issue_title or rec.title,
                    "body": issue_body,
                    "labels": rec.github_labels + [f"priority-{rec.priority.value}"],
                    "assignees": [],  # Could be configured based on recommendation type,
                }

                issues.append(issue_data)

        return issues

    def _generate_github_issue_body(self, recommendation: Recommendation) -> str:
        """Generate detailed GitHub issue body for recommendation."""

        body = f"""## 🎯 Strategic Recommendation: {recommendation.title}

### Description
{recommendation.description}

### Expected Impact
- **Level**: {recommendation.expected_impact.value.title()}
- **Benefit**: {recommendation.estimated_benefit or 'Improved platform performance'}
- **Risk Assessment**: {recommendation.risk_assessment}

### Implementation Plan

#### Steps
"""

        for i, step in enumerate(recommendation.implementation_steps, 1):
            body += f"{i}. {step}\n"

        body += f"""
#### Effort Estimate
{recommendation.estimated_effort}

#### Required Resources
"""

        for resource in recommendation.required_resources:
            body += f"- {resource}\n"

        if recommendation.dependencies:
            body += "\n#### Dependencies\n"
            for dep in recommendation.dependencies:
                body += f"- {dep}\n"

        if recommendation.supporting_metrics:
            body += "\n#### Supporting Metrics\n"
            for metric in recommendation.supporting_metrics:
                body += f"- {metric}\n"

        body += f"""
### Priority: {recommendation.priority.value.upper()}

**Generated by Hive Intelligence Oracle at {recommendation.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}**

---
*This issue was automatically generated by the Hive Intelligence system based on platform analytics and strategic insights.*
"""

        return body
