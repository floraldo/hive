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
    # Unified observability (NEW - recommended interface)
    "ObservabilityManager",
    "ObservabilityConfig",
    # Metrics collection
    "AIMetricsCollector",
    "MetricType",
    "MetricDefinition",
    "MetricValue",
    "AIOperationMetrics",
    # Health monitoring
    "ModelHealthChecker",
    "HealthStatus",
    "HealthCheckResult",
    "ProviderHealth",
    "ModelHealth",
    # Cost management
    "CostManager",
    "BudgetPeriod",
    "CostBudget",
    "CostRecord",
    "CostSummary",
    "BudgetStatus",
]
