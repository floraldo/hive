from hive_logging import get_logger

logger = get_logger(__name__)

"""
AI-Enhanced Observability for Hive AI.

Provides comprehensive monitoring, health checking, and cost management
for AI operations with real-time analytics and alerting.
"""

from .cost import BudgetPeriod, BudgetStatus, CostBudget, CostManager, CostRecord, CostSummary
from .health import HealthCheckResult, HealthStatus, ModelHealth, ModelHealthChecker, ProviderHealth
from .manager import ObservabilityConfig, ObservabilityManager
from .metrics import AIMetricsCollector, AIOperationMetrics, MetricDefinition, MetricType, MetricValue

__all__ = [
    # Metrics collection
    "AIMetricsCollector",
    "AIOperationMetrics",
    "BudgetPeriod",
    "BudgetStatus",
    "CostBudget",
    # Cost management
    "CostManager",
    "CostRecord",
    "CostSummary",
    "HealthCheckResult",
    "HealthStatus",
    "MetricDefinition",
    "MetricType",
    "MetricValue",
    "ModelHealth",
    # Health monitoring
    "ModelHealthChecker",
    "ObservabilityConfig",
    # Unified observability (NEW - recommended interface)
    "ObservabilityManager",
    "ProviderHealth",
]
