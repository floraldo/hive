"""
Genesis Agent - The Hive App Creation Engine

The Genesis Agent is the capstone of the Hive Intelligence Initiative,
transforming the Oracle from advisor to architect by automating the
creation of strategically-sound, architecturally-compliant applications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from hive_logging import get_logger

from ..intelligence.oracle_service import OracleService
from .analyzer import SemanticAnalyzer
from .scaffolder import HiveScaffolder

logger = get_logger(__name__)


class AppCategory(Enum):
    """Categories of applications the Genesis Agent can create."""

    WEB_APPLICATION = "web_application"
    API_SERVICE = "api_service"
    DATA_PROCESSOR = "data_processor"
    AI_SERVICE = "ai_service"
    MICROSERVICE = "microservice"
    CLI_TOOL = "cli_tool"
    BACKGROUND_SERVICE = "background_service"


class Priority(Enum):
    """Feature priority levels based on Oracle intelligence."""

    CRITICAL = "critical"  # Must implement first
    HIGH = "high"  # High business value
    MEDIUM = "medium"  # Standard features
    LOW = "low"  # Nice to have
    FUTURE = "future"  # Roadmap items


@dataclass
class FeatureStub:
    """Represents a feature to be stubbed in the new application."""

    name: str
    description: str
    priority: Priority
    estimated_effort: str  # e.g., "2-3 days", "1 week"
    business_value: str  # Oracle-provided business justification

    # Technical details
    module_path: str  # Where to create the stub
    dependencies: list[str] = field(default_factory=list)  # Required hive-* packages

    # Oracle intelligence
    adoption_rate: float | None = None  # Similar feature adoption in existing apps
    revenue_impact: str | None = None  # Potential revenue impact
    user_engagement: str | None = None  # User engagement metrics for similar features

    # Implementation guidance
    implementation_notes: list[str] = field(default_factory=list)
    oracle_recommendations: list[str] = field(default_factory=list)


@dataclass
class AppSpec:
    """Complete specification for a new Hive application."""

    # Basic information
    name: str
    description: str
    category: AppCategory

    # Architectural decisions (Oracle-advised)
    recommended_packages: list[str] = field(default_factory=list)
    architecture_pattern: str = "standard_hive_app"
    storage_recommendation: str = "sqlite_with_migrations"

    # Features (AI-analyzed and Oracle-prioritized)
    features: list[FeatureStub] = field(default_factory=list)

    # Strategic intelligence
    market_opportunity: str = ""
    competitive_advantage: str = ""
    target_user_segment: str = ""

    # Oracle insights
    similar_apps_performance: dict[str, Any] = field(default_factory=dict)
    business_intelligence: dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    oracle_confidence: float = 0.0  # Oracle's confidence in recommendations (0-1)


class GenesisConfig(BaseModel):
    """Configuration for the Genesis Agent."""

    # AI Analysis settings
    ai_model: str = Field(default="gpt-4", description="AI model for semantic analysis")
    analysis_confidence_threshold: float = Field(default=0.7, description="Minimum confidence for AI recommendations")

    # Oracle integration
    enable_oracle_consultation: bool = Field(
        default=True, description="Use Oracle intelligence for strategic decisions"
    )
    oracle_query_timeout: int = Field(default=30, description="Timeout for Oracle queries in seconds")

    # Scaffolding settings
    default_template_path: str = Field(default="templates/hive_app", description="Default app template path")
    enforce_golden_rules: bool = Field(default=True, description="Ensure Golden Rules compliance")

    # Feature analysis
    max_features_per_app: int = Field(default=8, description="Maximum features to generate per app")
    min_feature_confidence: float = Field(default=0.6, description="Minimum confidence for feature recommendations")

    # Output settings
    output_base_path: str = Field(default="apps", description="Base path for new applications")
    generate_readme: bool = Field(default=True, description="Generate comprehensive README")
    generate_docs: bool = Field(default=True, description="Generate initial documentation")


class GenesisAgent:
    """
    The Genesis Agent - Hive App Creation Engine

    Transforms high-level app ideas into strategically-sound, architecturally-compliant
    application skeletons using the full power of the Oracle's intelligence.
    """

    def __init__(self, config: GenesisConfig, oracle_service: OracleService | None = None):
        self.config = config
        self.oracle = oracle_service
        self.analyzer = SemanticAnalyzer(config)
        self.scaffolder = HiveScaffolder(config)

        logger.info("Genesis Agent initialized - ready to create applications")

    async def create_app_async(self, name: str, description: str, target_path: Path | None = None) -> AppSpec:
        """
        Create a new Hive application with full Oracle intelligence integration.

        Args:
            name: Application name (must be valid directory name)
            description: High-level description of the application
            target_path: Optional custom path for the application

        Returns:
            AppSpec: Complete specification of the created application
        """
        logger.info(f"Genesis Agent creating new app: {name}")
        logger.info(f"Description: {description}")

        try:
            # Phase 1: Semantic Analysis
            logger.info("Phase 1: Analyzing application requirements...")
            analysis_result = await self.analyzer.analyze_description_async(description)

            # Phase 2: Oracle Consultation (if enabled)
            oracle_insights = {}
            if self.config.enable_oracle_consultation and self.oracle:
                logger.info("Phase 2: Consulting Oracle for strategic intelligence...")
                oracle_insights = await self._consult_oracle_async(analysis_result)

            # Phase 3: Create App Specification
            logger.info("Phase 3: Creating application specification...")
            app_spec = await self._create_app_spec_async(name, description, analysis_result, oracle_insights)

            # Phase 4: Generate Application Structure
            logger.info("Phase 4: Generating application structure...")
            app_path = target_path or Path(self.config.output_base_path) / name
            await self.scaffolder.generate_app_async(app_spec, app_path)

            logger.info(f"✅ Application '{name}' created successfully at {app_path}")
            logger.info(f"📊 Oracle confidence: {app_spec.oracle_confidence:.1%}")
            logger.info(f"🎯 Features identified: {len(app_spec.features)}")

            return app_spec

        except Exception as e:
            logger.error(f"Failed to create application '{name}': {e}")
            raise

    async def _consult_oracle_async(self, analysis_result: dict[str, Any]) -> dict[str, Any]:
        """Consult the Oracle for strategic intelligence about the new application."""

        oracle_insights = {
            "business_intelligence": {},
            "feature_performance": {},
            "strategic_recommendations": [],
            "confidence_score": 0.0,
        }

        try:
            if not self.oracle:
                logger.warning("Oracle service not available - using default recommendations")
                return oracle_insights

            # Get Oracle's dashboard data for business context
            dashboard_data = await self.oracle.get_dashboard_data_async()

            # Analyze feature performance from existing apps
            feature_keywords = analysis_result.get("features", [])
            feature_performance = self._analyze_feature_performance(
                feature_keywords, dashboard_data.feature_performance
            )

            # Get strategic recommendations based on business intelligence
            strategic_recs = self._get_strategic_recommendations(analysis_result, dashboard_data)

            # Calculate Oracle confidence based on data availability
            confidence = self._calculate_oracle_confidence(dashboard_data, analysis_result)

            oracle_insights.update(
                {
                    "business_intelligence": {
                        "customer_health_score": dashboard_data.customer_health.overall_health_score,
                        "feature_cost_efficiency": dashboard_data.feature_performance.avg_adoption_rate,
                        "revenue_growth_rate": dashboard_data.revenue_correlation.revenue_growth_rate,
                    },
                    "feature_performance": feature_performance,
                    "strategic_recommendations": strategic_recs,
                    "confidence_score": confidence,
                }
            )

            logger.info(f"Oracle consultation complete - confidence: {confidence:.1%}")

        except Exception as e:
            logger.error(f"Oracle consultation failed: {e}")
            # Continue with reduced intelligence

        return oracle_insights

    def _analyze_feature_performance(self, feature_keywords: list[str], feature_matrix: Any) -> dict[str, Any]:
        """Analyze performance of similar features in existing apps."""

        performance_data = {}

        try:
            # Map keywords to existing features
            keyword_mapping = {
                "photo": ["image", "media", "upload"],
                "user": ["auth", "profile", "account"],
                "search": ["query", "find", "filter"],
                "social": ["share", "comment", "like"],
                "ai": ["ml", "smart", "auto", "intelligent"],
                "data": ["analytics", "report", "dashboard"],
            }

            for keyword in feature_keywords:
                # Find similar features in existing apps
                similar_features = []
                for feature in feature_matrix.features:
                    feature_name_lower = feature.name.lower()
                    if keyword.lower() in feature_name_lower or any(
                        mapped in feature_name_lower for mapped in keyword_mapping.get(keyword.lower(), [])
                    ):
                        similar_features.append(
                            {
                                "name": feature.name,
                                "adoption_rate": feature.adoption_rate,
                                "cost": feature.operational_cost,
                                "roi_score": feature.roi_score,
                                "satisfaction": feature.satisfaction_score,
                            }
                        )

                if similar_features:
                    # Calculate aggregate performance metrics
                    avg_adoption = sum(f["adoption_rate"] for f in similar_features) / len(similar_features)
                    avg_cost = sum(f["cost"] for f in similar_features) / len(similar_features)
                    avg_roi = sum(f["roi_score"] for f in similar_features) / len(similar_features)

                    performance_data[keyword] = {
                        "similar_features_count": len(similar_features),
                        "avg_adoption_rate": avg_adoption,
                        "avg_operational_cost": avg_cost,
                        "avg_roi_score": avg_roi,
                        "recommendation": self._get_feature_recommendation(avg_adoption, avg_roi),
                    }

        except Exception as e:
            logger.error(f"Feature performance analysis failed: {e}")

        return performance_data

    def _get_feature_recommendation(self, adoption_rate: float, roi_score: float) -> str:
        """Get recommendation based on feature performance."""
        if roi_score > 15 and adoption_rate > 70:
            return "HIGH_PRIORITY - Proven high-value feature"
        elif roi_score > 10:
            return "MEDIUM_PRIORITY - Good ROI, consider promotion"
        elif adoption_rate < 10:
            return "LOW_PRIORITY - Low adoption risk"
        else:
            return "STANDARD - Typical performance expected"

    def _get_strategic_recommendations(self, analysis_result: dict[str, Any], dashboard_data: Any) -> list[str]:
        """Generate strategic recommendations based on Oracle intelligence."""

        recommendations = []

        try:
            # Revenue optimization recommendations
            if dashboard_data.revenue_correlation.trial_to_paid_conversion < 5.0:
                recommendations.append(
                    "Focus on user onboarding and time-to-value - current conversion rate is below benchmark"
                )

            # Feature strategy recommendations
            if len(dashboard_data.feature_performance.underperforming_features) > 0:
                recommendations.append("Avoid complex features initially - focus on core value proposition")

            # Customer success recommendations
            if len(dashboard_data.customer_health.customers_at_risk) > 0:
                recommendations.append("Prioritize reliability and error handling - customer health alerts detected")

            # Cost efficiency recommendations
            if dashboard_data.revenue_correlation.cost_efficiency_score < 80:
                recommendations.append(
                    "Consider cost-efficient architecture patterns - platform cost efficiency needs improvement"
                )

            # AI/ML recommendations based on analysis
            ai_features = analysis_result.get("ai_features", [])
            if ai_features:
                recommendations.append(
                    "AI features show high engagement - consider hive-ai integration for competitive advantage"
                )

        except Exception as e:
            logger.error(f"Strategic recommendations generation failed: {e}")

        return recommendations

    def _calculate_oracle_confidence(self, dashboard_data: Any, analysis_result: dict[str, Any]) -> float:
        """Calculate Oracle's confidence in recommendations based on data availability."""

        confidence_factors = []

        try:
            # Data availability factor
            if dashboard_data.feature_performance.features:
                confidence_factors.append(0.3)  # Feature performance data available

            if dashboard_data.customer_health.daily_active_users > 100:
                confidence_factors.append(0.2)  # Sufficient user data

            if dashboard_data.revenue_correlation.monthly_recurring_revenue > 10000:
                confidence_factors.append(0.2)  # Business metrics available

            # Analysis quality factor
            features_identified = len(analysis_result.get("features", []))
            if features_identified >= 3:
                confidence_factors.append(0.2)  # Good feature analysis

            # Strategic alignment factor
            if len(analysis_result.get("business_keywords", [])) > 2:
                confidence_factors.append(0.1)  # Business context understood

            confidence = sum(confidence_factors)

        except Exception as e:
            logger.error(f"Confidence calculation failed: {e}")
            confidence = 0.5  # Default moderate confidence

        return min(confidence, 1.0)  # Cap at 100%

    async def _create_app_spec_async(
        self, name: str, description: str, analysis_result: dict[str, Any], oracle_insights: dict[str, Any]
    ) -> AppSpec:
        """Create comprehensive application specification."""

        # Determine app category
        category = self._determine_app_category(analysis_result)

        # Select recommended packages
        recommended_packages = self._select_packages(analysis_result, oracle_insights)

        # Generate feature stubs
        features = self._generate_feature_stubs(analysis_result, oracle_insights)

        # Create app specification
        app_spec = AppSpec(
            name=name,
            description=description,
            category=category,
            recommended_packages=recommended_packages,
            features=features,
            oracle_confidence=oracle_insights.get("confidence_score", 0.0),
            business_intelligence=oracle_insights.get("business_intelligence", {}),
            similar_apps_performance=oracle_insights.get("feature_performance", {}),
        )

        # Add Oracle strategic insights
        strategic_recs = oracle_insights.get("strategic_recommendations", [])
        if strategic_recs:
            app_spec.market_opportunity = strategic_recs[0] if strategic_recs else ""
            app_spec.competitive_advantage = "Oracle-optimized architecture and feature selection"

        return app_spec

    def _determine_app_category(self, analysis_result: dict[str, Any]) -> AppCategory:
        """Determine the most appropriate app category based on analysis."""

        keywords = analysis_result.get("keywords", [])
        features = analysis_result.get("features", [])

        # Simple keyword-based categorization
        if any(kw in ["api", "service", "endpoint"] for kw in keywords):
            return AppCategory.API_SERVICE
        elif any(kw in ["web", "frontend", "ui", "dashboard"] for kw in keywords):
            return AppCategory.WEB_APPLICATION
        elif any(kw in ["ai", "ml", "intelligent", "smart"] for kw in keywords):
            return AppCategory.AI_SERVICE
        elif any(kw in ["cli", "command", "tool"] for kw in keywords):
            return AppCategory.CLI_TOOL
        elif any(kw in ["process", "batch", "worker"] for kw in keywords):
            return AppCategory.BACKGROUND_SERVICE
        elif any(kw in ["data", "analytics", "etl"] for kw in keywords):
            return AppCategory.DATA_PROCESSOR
        else:
            return AppCategory.MICROSERVICE

    def _select_packages(self, analysis_result: dict[str, Any], oracle_insights: dict[str, Any]) -> list[str]:
        """Select appropriate hive-* packages based on analysis and Oracle insights."""

        packages = ["hive-config"]  # Always include base config
        keywords = analysis_result.get("keywords", [])
        features = analysis_result.get("features", [])

        # Database package
        if any(kw in ["data", "store", "save", "database", "user"] for kw in keywords + features):
            packages.append("hive-db")

        # AI package
        if any(kw in ["ai", "ml", "intelligent", "smart", "analyze", "tag"] for kw in keywords + features):
            packages.append("hive-ai")

        # Bus package for messaging/events
        if any(kw in ["real-time", "message", "event", "notify", "update"] for kw in keywords + features):
            packages.append("hive-bus")

        # Deployment package
        packages.append("hive-deployment")  # Always include for proper deployment

        # Oracle-recommended packages based on performance data
        feature_performance = oracle_insights.get("feature_performance", {})
        for feature, perf in feature_performance.items():
            if perf.get("avg_roi_score", 0) > 15:  # High ROI features
                if "ai" in feature.lower() and "hive-ai" not in packages:
                    packages.append("hive-ai")
                elif "data" in feature.lower() and "hive-db" not in packages:
                    packages.append("hive-db")

        return packages

    def _generate_feature_stubs(
        self, analysis_result: dict[str, Any], oracle_insights: dict[str, Any]
    ) -> list[FeatureStub]:
        """Generate feature stubs with Oracle-prioritized recommendations."""

        features = []
        identified_features = analysis_result.get("features", [])
        feature_performance = oracle_insights.get("feature_performance", {})

        for i, feature_name in enumerate(identified_features[: self.config.max_features_per_app]):
            # Get Oracle intelligence for this feature
            perf_data = feature_performance.get(feature_name, {})

            # Determine priority based on Oracle data
            priority = self._determine_feature_priority(perf_data)

            # Generate business value justification
            business_value = self._generate_business_value(feature_name, perf_data)

            # Create feature stub
            feature_stub = FeatureStub(
                name=feature_name,
                description=f"Implement {feature_name} functionality",
                priority=priority,
                estimated_effort=self._estimate_effort(feature_name, perf_data),
                business_value=business_value,
                module_path=f"src/{feature_name.lower().replace(' ', '_')}.py",
                adoption_rate=perf_data.get("avg_adoption_rate"),
                revenue_impact=perf_data.get("recommendation", "Standard feature"),
                oracle_recommendations=self._get_oracle_feature_recommendations(feature_name, perf_data),
            )

            features.append(feature_stub)

        # Sort by priority (Critical first, Future last)
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
            Priority.FUTURE: 4,
        }
        features.sort(key=lambda f: priority_order.get(f.priority, 2))

        return features

    def _determine_feature_priority(self, perf_data: dict[str, Any]) -> Priority:
        """Determine feature priority based on Oracle performance data."""

        if not perf_data:
            return Priority.MEDIUM

        roi_score = perf_data.get("avg_roi_score", 0)
        adoption_rate = perf_data.get("avg_adoption_rate", 50)

        if roi_score > 15 and adoption_rate > 70:
            return Priority.CRITICAL
        elif roi_score > 10 or adoption_rate > 60:
            return Priority.HIGH
        elif roi_score > 5 or adoption_rate > 30:
            return Priority.MEDIUM
        elif adoption_rate > 10:
            return Priority.LOW
        else:
            return Priority.FUTURE

    def _generate_business_value(self, feature_name: str, perf_data: dict[str, Any]) -> str:
        """Generate business value justification for a feature."""

        if not perf_data:
            return f"Core functionality for {feature_name}"

        adoption_rate = perf_data.get("avg_adoption_rate", 0)
        roi_score = perf_data.get("avg_roi_score", 0)

        if roi_score > 15:
            return (
                f"High-value feature: Similar features show {roi_score:.1f} ROI score and {adoption_rate:.1f}% adoption"
            )
        elif adoption_rate > 70:
            return f"Popular feature: {adoption_rate:.1f}% adoption rate in similar apps"
        elif roi_score > 5:
            return f"Solid ROI: {roi_score:.1f} ROI score with moderate adoption"
        else:
            return f"Standard feature with {adoption_rate:.1f}% expected adoption"

    def _estimate_effort(self, feature_name: str, perf_data: dict[str, Any]) -> str:
        """Estimate implementation effort for a feature."""

        # Simple effort estimation based on feature complexity
        complex_keywords = ["ai", "ml", "intelligent", "real-time", "analytics"]
        medium_keywords = ["user", "auth", "search", "upload", "social"]

        feature_lower = feature_name.lower()

        if any(kw in feature_lower for kw in complex_keywords):
            return "1-2 weeks"
        elif any(kw in feature_lower for kw in medium_keywords):
            return "3-5 days"
        else:
            return "1-2 days"

    def _get_oracle_feature_recommendations(self, feature_name: str, perf_data: dict[str, Any]) -> list[str]:
        """Get Oracle-specific recommendations for implementing a feature."""

        recommendations = []

        if perf_data:
            recommendation = perf_data.get("recommendation", "")
            if "HIGH_PRIORITY" in recommendation:
                recommendations.append("Oracle: This is a proven high-value feature - prioritize implementation")
            elif "LOW_PRIORITY" in recommendation:
                recommendations.append("Oracle: Similar features have low adoption - consider alternative approaches")

            avg_cost = perf_data.get("avg_operational_cost", 0)
            if avg_cost > 500:
                recommendations.append(f"Oracle: Monitor costs - similar features average ${avg_cost:.0f}/month")

        # General Oracle recommendations
        feature_lower = feature_name.lower()
        if "ai" in feature_lower:
            recommendations.append("Oracle: Use hive-ai package for cost-efficient AI integration")
        elif "user" in feature_lower:
            recommendations.append("Oracle: Focus on user onboarding - conversion rates need improvement")
        elif "data" in feature_lower:
            recommendations.append("Oracle: Use efficient storage patterns - cost optimization is priority")

        return recommendations or ["Oracle: Implement using standard Hive patterns"]
