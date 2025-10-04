"""
Unified observability manager for AI operations.

Composes metrics collection, health monitoring, and cost management
into a single coherent interface for comprehensive AI observability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from hive_logging import get_logger

from ..core.exceptions import AIError
from ..core.interfaces import TokenUsage
from ..models.registry import ModelRegistry
from .cost import BudgetPeriod, BudgetStatus, CostBudget, CostManager, CostRecord, CostSummary
from .health import HealthCheckResult, HealthStatus, ModelHealth, ModelHealthChecker, ProviderHealth
from .metrics import AIMetricsCollector, AIOperationMetrics, MetricValue

logger = get_logger(__name__)


@dataclass
class ObservabilityConfig:
    """Configuration for unified observability manager."""

    # Metrics collection
    enable_metrics: bool = True
    metrics_retention_size: int = 10000

    # Health monitoring
    enable_health_checks: bool = True
    health_check_interval: int = 300  # 5 minutes
    degradation_threshold: float = 0.8
    unhealthy_threshold: float = 0.5

    # Cost management
    enable_cost_tracking: bool = True
    default_budgets: list[CostBudget] = field(default_factory=list)
    cost_alert_enabled: bool = True

    # General
    cache_enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class ObservabilityManager:
    """
    Unified observability manager for AI operations.

    Composes three core observability components:
    - AIMetricsCollector: Performance and usage metrics
    - ModelHealthChecker: Health monitoring and availability
    - CostManager: Budget control and cost optimization

    Provides single interface for comprehensive AI observability with
    coordinated metrics, health, and cost tracking across all AI operations.
    """

    def __init__(
        self,
        config: ObservabilityConfig | None = None,
        registry: ModelRegistry | None = None,
        ai_config: Any = None,
    ):
        """
        Initialize unified observability manager.

        Args:
            config: Observability configuration
            registry: ModelRegistry for health checks
            ai_config: AIConfig for component initialization
        """
        self.config = config or ObservabilityConfig()
        self.registry = registry
        self.ai_config = ai_config

        # Initialize components based on configuration
        self._metrics_collector: AIMetricsCollector | None = None
        self._health_checker: ModelHealthChecker | None = None
        self._cost_manager: CostManager | None = None

        self._initialize_components()

        logger.info(
            f"ObservabilityManager initialized: "
            f"metrics={self.config.enable_metrics}, "
            f"health={self.config.enable_health_checks}, "
            f"cost={self.config.enable_cost_tracking}"
        )

    def _initialize_components(self) -> None:
        """Initialize observability components based on configuration."""
        # Metrics collector
        if self.config.enable_metrics:
            self._metrics_collector = AIMetricsCollector(config=self.ai_config)
            logger.debug("AIMetricsCollector initialized")

        # Health checker
        if self.config.enable_health_checks and self.registry:
            self._health_checker = ModelHealthChecker(
                registry=self.registry,
                check_interval=self.config.health_check_interval,
                degradation_threshold=self.config.degradation_threshold,
                unhealthy_threshold=self.config.unhealthy_threshold,
            )
            logger.debug("ModelHealthChecker initialized")
        elif self.config.enable_health_checks and not self.registry:
            logger.warning("Health checks enabled but no ModelRegistry provided - health checks disabled")

        # Cost manager
        if self.config.enable_cost_tracking:
            self._cost_manager = CostManager(config=self.ai_config)

            # Apply default budgets
            for budget in self.config.default_budgets:
                self._cost_manager.add_budget(budget)

            logger.debug(f"CostManager initialized with {len(self.config.default_budgets)} budgets")

    # ==================== Unified Operation Tracking ====================

    def start_operation(
        self,
        operation_type: str,
        model: str,
        provider: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Start tracking an AI operation across all observability components.

        Args:
            operation_type: Type of operation (generation, embedding, etc.)
            model: Model being used
            provider: Provider name
            metadata: Additional operation metadata

        Returns:
            operation_id for tracking
        """
        operation_id = None

        # Start metrics tracking
        if self._metrics_collector:
            operation_id = self._metrics_collector.start_operation(
                operation_type=operation_type,
                model=model,
                provider=provider,
                metadata=metadata or {},
            )

        return operation_id or f"op_{datetime.utcnow().timestamp()}"

    def end_operation(
        self,
        operation_id: str,
        success: bool = True,
        tokens_used: TokenUsage | None = None,
        cost: float = 0.0,
        error_type: str | None = None,
        additional_metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        End tracking an AI operation and record across all components.

        Args:
            operation_id: Operation identifier from start_operation
            success: Whether operation succeeded
            tokens_used: Token usage information
            cost: Cost in USD
            error_type: Type of error if failed
            additional_metadata: Additional metadata to record
        """
        # End metrics tracking
        if self._metrics_collector:
            self._metrics_collector.end_operation(
                operation_id=operation_id,
                success=success,
                tokens_used=tokens_used,
                cost=cost,
                error_type=error_type,
                additional_metadata=additional_metadata or {},
            )

        # Record cost if tracking enabled
        if self._cost_manager and tokens_used:
            # Get operation details from metrics
            operation = self._metrics_collector.get_operation_metrics(operation_id) if self._metrics_collector else None

            if operation:
                cost_record = CostRecord(
                    timestamp=operation.start_time,
                    model=operation.model,
                    provider=operation.provider,
                    operation=operation.operation_type,
                    tokens_used=tokens_used.total_tokens if hasattr(tokens_used, "total_tokens") else 0,
                    cost_usd=cost,
                    request_id=operation_id,
                    metadata=additional_metadata or {},
                )
                self._cost_manager.record_cost(cost_record)

    # ==================== Metrics Access ====================

    @property
    def metrics(self) -> AIMetricsCollector:
        """Get metrics collector component."""
        if not self._metrics_collector:
            raise AIError("Metrics collection not enabled")
        return self._metrics_collector

    def get_operation_metrics(self, operation_id: str) -> AIOperationMetrics | None:
        """Get metrics for a specific operation."""
        if not self._metrics_collector:
            return None
        return self._metrics_collector.get_operation_metrics(operation_id)

    def get_metric_values(
        self, metric_name: str, since: datetime | None = None, limit: int = 100
    ) -> list[MetricValue]:
        """Get values for a specific metric."""
        if not self._metrics_collector:
            return []
        return self._metrics_collector.get_metric_values(metric_name, since=since, limit=limit)

    # ==================== Health Monitoring ====================

    @property
    def health(self) -> ModelHealthChecker:
        """Get health checker component."""
        if not self._health_checker:
            raise AIError("Health monitoring not enabled")
        return self._health_checker

    async def check_health_async(self) -> HealthCheckResult:
        """Perform comprehensive health check across all AI infrastructure."""
        if not self._health_checker:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                message="Health monitoring not enabled",
                timestamp=datetime.utcnow(),
            )
        return await self._health_checker.check_health_async()

    def get_provider_health(self, provider: str) -> ProviderHealth | None:
        """Get health status for a specific provider."""
        if not self._health_checker:
            return None
        return self._health_checker.get_provider_health(provider)

    def get_model_health(self, model: str, provider: str) -> ModelHealth | None:
        """Get health status for a specific model."""
        if not self._health_checker:
            return None
        return self._health_checker.get_model_health(model, provider)

    # ==================== Cost Management ====================

    @property
    def cost(self) -> CostManager:
        """Get cost manager component."""
        if not self._cost_manager:
            raise AIError("Cost tracking not enabled")
        return self._cost_manager

    def add_budget(self, budget: CostBudget) -> None:
        """Add a budget for cost control."""
        if not self._cost_manager:
            raise AIError("Cost tracking not enabled")
        self._cost_manager.add_budget(budget)

    def check_budget(self, budget_name: str) -> BudgetStatus:
        """Check status of a specific budget."""
        if not self._cost_manager:
            raise AIError("Cost tracking not enabled")
        return self._cost_manager.check_budget(budget_name)

    def get_cost_summary(
        self, period: BudgetPeriod = BudgetPeriod.DAILY, limit: int = 7
    ) -> list[CostSummary]:
        """Get cost summary for recent periods."""
        if not self._cost_manager:
            return []
        return self._cost_manager.get_cost_summary(period=period, limit=limit)

    # ==================== Unified Analytics ====================

    def get_unified_status(self) -> dict[str, Any]:
        """
        Get unified status across all observability components.

        Returns comprehensive status including:
        - Current health status
        - Recent metrics summary
        - Budget status
        - System overview
        """
        status: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "metrics": self.config.enable_metrics,
                "health": self.config.enable_health_checks,
                "cost": self.config.enable_cost_tracking,
            },
        }

        # Health status
        if self._health_checker:
            try:
                # Get cached health status (async check runs in background)
                overall_health = self._health_checker.get_overall_status()
                status["health"] = {
                    "status": overall_health.value,
                    "providers": len(self._health_checker._provider_health),
                    "models": len(self._health_checker._model_health),
                }
            except Exception as e:
                logger.warning(f"Failed to get health status: {e}")
                status["health"] = {"status": "unknown", "error": str(e)}

        # Metrics summary
        if self._metrics_collector:
            try:
                recent_ops = len(self._metrics_collector._recent_operations)
                active_ops = len(self._metrics_collector._active_operations)
                status["metrics"] = {
                    "recent_operations": recent_ops,
                    "active_operations": active_ops,
                    "metric_count": len(self._metrics_collector._metrics),
                }
            except Exception as e:
                logger.warning(f"Failed to get metrics summary: {e}")
                status["metrics"] = {"error": str(e)}

        # Cost summary
        if self._cost_manager:
            try:
                budgets = self._cost_manager.list_budgets()
                status["cost"] = {
                    "budget_count": len(budgets),
                    "budgets": [
                        {
                            "name": budget.name,
                            "period": budget.period.value,
                            "limit": budget.limit,
                            "enabled": budget.enabled,
                        }
                        for budget in budgets
                    ],
                }
            except Exception as e:
                logger.warning(f"Failed to get cost summary: {e}")
                status["cost"] = {"error": str(e)}

        return status

    async def close_async(self) -> None:
        """Clean up observability components."""
        if self._health_checker:
            await self._health_checker.stop_monitoring_async()

        if self._metrics_collector:
            self._metrics_collector.cache.clear()

        if self._cost_manager:
            self._cost_manager.cache.clear()

        logger.info("ObservabilityManager closed")


# Backward compatibility aliases
UnifiedObservabilityManager = ObservabilityManager
AIObservabilityManager = ObservabilityManager
