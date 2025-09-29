"""
Oracle Service - The Complete Intelligence Integration

Orchestrates the entire Hive Intelligence system, providing the main
interface for strategic insights, recommendations, and platform wisdom.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from hive_cache import CacheManager
from hive_logging import get_logger
from pydantic import BaseModel, Field

from .analytics_engine import AnalyticsEngine, InsightGenerator
from .data_unification import DataUnificationLayer, MetricsWarehouse
from .mission_control import MissionControlDashboard
from .recommendation_engine import RecommendationEngine, RecommendationReport

logger = get_logger(__name__)


class OracleConfig(BaseModel):
    """Configuration for the Oracle Service."""

    # Data collection settings
    collection_interval: int = Field(default=300, description="Data collection interval in seconds")
    analysis_interval: int = Field(default=3600, description="Analysis interval in seconds")
    reporting_interval: int = Field(default=86400, description="Reporting interval in seconds")

    # Intelligence settings
    min_confidence_threshold: float = Field(default=0.7, description="Minimum confidence for insights")
    prediction_horizon_hours: int = Field(default=24, description="Prediction time horizon in hours")
    enable_predictive_analysis: bool = Field(default=True, description="Enable predictive analytics")
    enable_github_integration: bool = Field(default=True, description="Enable GitHub issue creation")

    # Storage settings
    data_retention_days: int = Field(default=90, description="Data retention period in days")
    cache_ttl_seconds: int = Field(default=300, description="Cache TTL in seconds")

    # GitHub integration
    github_repository: str = Field(default="hive", description="GitHub repository name")
    github_labels: list[str] = Field(default=["oracle", "intelligence", "automated"], description="GitHub issue labels")

    # Dashboard settings
    dashboard_refresh_interval: int = Field(default=300, description="Dashboard refresh interval in seconds")
    dashboard_port: int = Field(default=8080, description="Dashboard server port")


class OracleService:
    """
    The Oracle Service - Complete Platform Intelligence

    Transforms the Guardian Agent into an Oracle that provides:
    - Real-time platform health monitoring
    - Predictive analytics and insights
    - Strategic recommendations
    - Automated issue creation
    - Cost optimization guidance
    - Performance improvement suggestions
    """

    def __init__(self, config: Optional[OracleConfig] = None):
        self.config = config or OracleConfig()

        # Initialize core components
        self.warehouse = MetricsWarehouse()
        self.data_layer = DataUnificationLayer(self.warehouse)
        self.analytics = AnalyticsEngine(self.warehouse)
        self.insight_generator = InsightGenerator(self.analytics)
        self.dashboard = MissionControlDashboard(self.warehouse, self.analytics)
        self.recommendation_engine = RecommendationEngine(self.warehouse, self.analytics)

        # Service state
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # Cache for expensive operations
        self.cache = CacheManager("oracle_service")

        # Last analysis timestamps
        self._last_analysis: Optional[datetime] = None
        self._last_report: Optional[datetime] = None

        logger.info("Oracle Service initialized - Guardian Agent evolved to Oracle")

    async def start_async(self) -> None:
        """Start the Oracle Service."""
        if self._running:
            logger.warning("Oracle Service already running")
            return

        self._running = True
        logger.info("🔮 Starting Hive Oracle Service - Platform Intelligence Active")

        # Start data collection
        await self.data_layer.start_collection_async()

        # Start periodic tasks
        self._tasks = [
            asyncio.create_task(self._analysis_loop_async()),
            asyncio.create_task(self._reporting_loop_async()),
            asyncio.create_task(self._dashboard_update_loop_async()),
            asyncio.create_task(self._maintenance_loop_async()),
        ]

        logger.info("Oracle Service fully operational - All intelligence systems active")

    async def stop_async(self) -> None:
        """Stop the Oracle Service."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping Oracle Service...")

        # Stop data collection
        await self.data_layer.stop_collection_async()

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("Oracle Service stopped")

    async def _analysis_loop_async(self) -> None:
        """Continuous analysis loop."""
        logger.info("Starting Oracle analysis loop")

        while self._running:
            try:
                await self._perform_analysis_async()
                await asyncio.sleep(self.config.analysis_interval)

            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def _reporting_loop_async(self) -> None:
        """Periodic reporting loop."""
        logger.info("Starting Oracle reporting loop")

        while self._running:
            try:
                await self._generate_strategic_report_async()
                await asyncio.sleep(self.config.reporting_interval)

            except Exception as e:
                logger.error(f"Error in reporting loop: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retry

    async def _dashboard_update_loop_async(self) -> None:
        """Dashboard update loop."""
        logger.info("Starting Oracle dashboard update loop")

        while self._running:
            try:
                # Force refresh dashboard data
                await self.dashboard.get_dashboard_data_async(force_refresh=True)
                await asyncio.sleep(self.config.dashboard_refresh_interval)

            except Exception as e:
                logger.error(f"Error in dashboard update loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry

    async def _maintenance_loop_async(self) -> None:
        """Maintenance and cleanup loop."""
        logger.info("Starting Oracle maintenance loop")

        while self._running:
            try:
                await self._perform_maintenance_async()
                await asyncio.sleep(86400)  # Daily maintenance

            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retry

    async def _perform_analysis_async(self) -> None:
        """Perform comprehensive platform analysis."""
        logger.info("Performing Oracle analysis...")

        start_time = datetime.utcnow()

        try:
            # Generate insights
            insights = await self.insight_generator.generate_insights_async(hours=self.config.prediction_horizon_hours)

            # Filter high-confidence insights
            critical_insights = [
                i
                for i in insights
                if i.confidence >= self.config.min_confidence_threshold and i.severity.value in ["critical", "high"]
            ]

            if critical_insights:
                logger.warning(f"Oracle detected {len(critical_insights)} critical insights")

                # Cache critical insights
                await self.cache.set_async(
                    "critical_insights",
                    [insight.__dict__ for insight in critical_insights],
                    ttl=self.config.cache_ttl_seconds,
                )

            # Update analysis timestamp
            self._last_analysis = start_time

            # Log analysis summary
            analysis_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Oracle analysis completed in {analysis_time:.2f}s - {len(insights)} insights generated")

        except Exception as e:
            logger.error(f"Oracle analysis failed: {e}")

    async def _generate_strategic_report_async(self) -> None:
        """Generate comprehensive strategic report."""
        logger.info("Generating Oracle strategic report...")

        try:
            # Generate recommendations
            report = await self.recommendation_engine.generate_recommendations_async(
                hours=24, include_predictive=self.config.enable_predictive_analysis
            )

            # Save report
            report_path = Path("data/intelligence/reports")
            report_path.mkdir(parents=True, exist_ok=True)

            report_file = report_path / f"oracle_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

            with open(report_file, "w") as f:
                json.dump(self._serialize_report(report), f, indent=2, default=str)

            # Create GitHub issues if enabled
            if self.config.enable_github_integration:
                await self._create_github_issues_async(report)

            # Update report timestamp
            self._last_report = datetime.utcnow()

            logger.info(
                f"Oracle strategic report generated: {len(report.critical_recommendations + report.high_priority_recommendations)} high-priority recommendations"
            )

        except Exception as e:
            logger.error(f"Oracle report generation failed: {e}")

    async def _create_github_issues_async(self, report: RecommendationReport) -> None:
        """Create GitHub issues for high-priority recommendations."""

        try:
            # Get high-priority recommendations
            high_priority_recs = report.critical_recommendations + report.high_priority_recommendations

            if not high_priority_recs:
                return

            # Generate issue data
            issues = await self.recommendation_engine.create_github_issues_async(
                recommendations=high_priority_recs, repository=self.config.github_repository
            )

            # In a real implementation, you would use GitHub API to create issues
            # For now, we'll log the issues that would be created
            logger.info(f"Oracle would create {len(issues)} GitHub issues for strategic recommendations")

            for issue in issues:
                logger.info(f"GitHub Issue: {issue['title']}")

        except Exception as e:
            logger.error(f"Failed to create GitHub issues: {e}")

    async def _perform_maintenance_async(self) -> None:
        """Perform system maintenance tasks."""
        logger.info("Performing Oracle maintenance...")

        try:
            # Clean old data
            cutoff_date = datetime.utcnow() - timedelta(days=self.config.data_retention_days)

            # In a real implementation, you would clean old metrics from the warehouse
            logger.info(f"Oracle maintenance: Data older than {cutoff_date} would be cleaned")

            # Clear old cache entries
            await self.cache.clear_expired_async()

            # Log maintenance completion
            logger.info("Oracle maintenance completed")

        except Exception as e:
            logger.error(f"Oracle maintenance failed: {e}")

    def _serialize_report(self, report: RecommendationReport) -> dict[str, Any]:
        """Serialize report for JSON storage."""

        def serialize_recommendation(rec):
            return {
                "title": rec.title,
                "description": rec.description,
                "type": rec.recommendation_type.value,
                "priority": rec.priority.value,
                "expected_impact": rec.expected_impact.value,
                "impact_description": rec.impact_description,
                "estimated_benefit": rec.estimated_benefit,
                "implementation_steps": rec.implementation_steps,
                "estimated_effort": rec.estimated_effort,
                "required_resources": rec.required_resources,
                "supporting_metrics": rec.supporting_metrics,
                "generated_at": rec.generated_at.isoformat(),
            }

        return {
            "title": report.title,
            "summary": report.summary,
            "generated_at": report.generated_at.isoformat(),
            "critical_recommendations": [serialize_recommendation(r) for r in report.critical_recommendations],
            "high_priority_recommendations": [
                serialize_recommendation(r) for r in report.high_priority_recommendations
            ],
            "medium_priority_recommendations": [
                serialize_recommendation(r) for r in report.medium_priority_recommendations
            ],
            "low_priority_recommendations": [serialize_recommendation(r) for r in report.low_priority_recommendations],
            "total_potential_savings": report.total_potential_savings,
            "recommended_immediate_actions": report.recommended_immediate_actions,
        }

    # Public API methods

    async def get_platform_health_async(self) -> dict[str, Any]:
        """Get current platform health status."""
        dashboard_data = await self.dashboard.get_dashboard_data_async()
        return {
            "overall_score": dashboard_data.platform_health.overall_score,
            "status": dashboard_data.platform_health.overall_status.value,
            "components": {
                name: {"score": comp.score, "status": comp.status.value, "issues": comp.issues}
                for name, comp in dashboard_data.platform_health.components.items()
            },
            "active_alerts": dashboard_data.active_alerts,
            "last_updated": dashboard_data.generated_at.isoformat(),
        }

    async def get_cost_intelligence_async(self) -> dict[str, Any]:
        """Get current cost intelligence."""
        dashboard_data = await self.dashboard.get_dashboard_data_async()
        cost_intel = dashboard_data.cost_intelligence

        return {
            "daily_cost": cost_intel.daily_cost,
            "monthly_cost": cost_intel.monthly_cost,
            "projected_monthly_cost": cost_intel.projected_monthly_cost,
            "budget_utilization": cost_intel.budget_utilization,
            "cost_trend": cost_intel.cost_trend,
            "optimization_recommendations": cost_intel.optimization_recommendations,
            "potential_savings": cost_intel.potential_savings,
            "last_updated": cost_intel.last_updated.isoformat(),
        }

    async def get_strategic_insights_async(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get strategic insights for the specified time period."""
        insights = await self.insight_generator.generate_insights_async(hours=hours)

        return [
            {
                "title": insight.title,
                "description": insight.description,
                "severity": insight.severity.value,
                "category": insight.category,
                "confidence": insight.confidence,
                "recommended_actions": insight.recommended_actions,
                "generated_at": insight.generated_at.isoformat(),
            }
            for insight in insights
        ]

    async def get_recommendations_async(self, include_predictive: bool = True) -> dict[str, Any]:
        """Get strategic recommendations."""
        report = await self.recommendation_engine.generate_recommendations_async(
            hours=24, include_predictive=include_predictive
        )

        return self._serialize_report(report)

    async def get_dashboard_html_async(self) -> str:
        """Get HTML dashboard for display."""
        return await self.dashboard.generate_dashboard_html_async()

    async def force_analysis_async(self) -> dict[str, Any]:
        """Force immediate analysis and return results."""
        logger.info("Oracle performing forced analysis...")

        await self._perform_analysis_async()

        # Get fresh insights
        insights = await self.get_strategic_insights_async()
        health = await self.get_platform_health_async()

        return {
            "analysis_completed_at": datetime.utcnow().isoformat(),
            "platform_health": health,
            "insights_count": len(insights),
            "critical_insights": [i for i in insights if i["severity"] in ["critical", "high"]],
        }

    def get_service_status(self) -> dict[str, Any]:
        """Get Oracle Service status."""
        return {
            "running": self._running,
            "last_analysis": self._last_analysis.isoformat() if self._last_analysis else None,
            "last_report": self._last_report.isoformat() if self._last_report else None,
            "active_tasks": len(self._tasks),
            "config": {
                "analysis_interval": self.config.analysis_interval,
                "reporting_interval": self.config.reporting_interval,
                "predictive_analysis": self.config.enable_predictive_analysis,
                "github_integration": self.config.enable_github_integration,
            },
        }
