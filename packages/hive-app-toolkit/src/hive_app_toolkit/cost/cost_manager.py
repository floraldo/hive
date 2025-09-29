"""Generalized cost control manager for any resource-intensive operations."""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Protocol

from hive_cache import CacheClient
from hive_logging import get_logger
from hive_performance import MetricsCollector

logger = get_logger(__name__)
metrics = MetricsCollector()


class ResourceType(Enum):
    """Types of resources that can be tracked for cost."""

    API_CALL = "api_call"
    COMPUTE_TIME = "compute_time"
    STORAGE = "storage"
    BANDWIDTH = "bandwidth"
    EMAIL = "email"
    SMS = "sms"
    DATABASE_QUERY = "database_query"
    CUSTOM = "custom"


@dataclass
class ResourceCost:
    """Represents the cost of using a resource."""

    resource_type: ResourceType
    units: float  # e.g., tokens, seconds, bytes, requests
    cost_per_unit: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_cost(self) -> float:
        """Calculate total cost."""
        return self.units * self.cost_per_unit


class CostCalculator(Protocol):
    """Protocol for custom cost calculation."""

    def calculate_cost(self, operation: str, parameters: dict[str, Any]) -> ResourceCost:
        """Calculate cost for an operation."""
        ...


@dataclass
class BudgetLimits:
    """Budget limits for different time periods."""

    hourly_limit: float = 10.0
    daily_limit: float = 100.0
    monthly_limit: float = 2000.0
    per_operation_limit: float = 1.0


@dataclass
class UsageStats:
    """Usage statistics for a time period."""

    period: str
    usage: float = 0.0
    limit: float = 0.0
    operations: int = 0

    @property
    def remaining(self) -> float:
        """Remaining budget."""
        return max(0.0, self.limit - self.usage)

    @property
    def percentage_used(self) -> float:
        """Percentage of budget used."""
        return (self.usage / self.limit * 100) if self.limit > 0 else 0


class CostManager:
    """
    Generalized cost control manager for resource-intensive operations.

    Tracks usage across multiple resource types and enforces budget limits.
    Designed to be flexible enough for any type of operation that incurs costs.
    """

    def __init__(
        self,
        limits: BudgetLimits | None = None,
        cache_client: CacheClient | None = None,
    ) -> None:
        """Initialize cost manager."""
        self.limits = limits or BudgetLimits()
        self.cache = cache_client or CacheClient(ttl_seconds=86400)

        # Usage tracking,
        self.hourly_usage = defaultdict(float)
        self.daily_usage = defaultdict(float)
        self.monthly_usage = defaultdict(float)

        # Operation history,
        self.usage_history: deque[dict[str, Any]] = deque(maxlen=10000)

        # Reset timestamps,
        self._last_reset = {
            "hourly": datetime.now(),
            "daily": datetime.now(),
            "monthly": datetime.now(),
        }

        # Custom cost calculators,
        self.cost_calculators: dict[str, CostCalculator] = {}

        self._load_from_cache()

        logger.info(
            "CostManager initialized with limits: daily=$%.2f, monthly=$%.2f",
            self.limits.daily_limit,
            self.limits.monthly_limit,
        )

    def add_cost_calculator(self, operation: str, calculator: CostCalculator) -> None:
        """Add a custom cost calculator for an operation."""
        self.cost_calculators[operation] = calculator
        logger.info(f"Added custom cost calculator for operation: {operation}")

    def _load_from_cache(self) -> None:
        """Load usage data from cache."""
        try:
            cached_data = self.cache.get("cost_manager_state")
            if cached_data:
                self.daily_usage = defaultdict(float, cached_data.get("daily_usage", {}))
                self.monthly_usage = defaultdict(float, cached_data.get("monthly_usage", {}))

                for period, timestamp_str in cached_data.get("last_reset", {}).items():
                    self._last_reset[period] = datetime.fromisoformat(timestamp_str)

        except Exception as e:
            logger.warning(f"Failed to load cost manager state from cache: {e}")

    def _save_to_cache(self) -> None:
        """Save usage data to cache."""
        try:
            cache_data = {
                "daily_usage": dict(self.daily_usage),
                "monthly_usage": dict(self.monthly_usage),
                "last_reset": {period: ts.isoformat() for period, ts in self._last_reset.items()},
            }
            self.cache.set("cost_manager_state", cache_data)
        except Exception as e:
            logger.warning(f"Failed to save cost manager state to cache: {e}")

    def _check_and_reset_periods(self) -> None:
        """Check if usage periods need to be reset."""
        now = datetime.now()

        # Reset hourly
        if (now - self._last_reset["hourly"]).total_seconds() >= 3600:
            logger.info(f"Resetting hourly usage. Previous: ${sum(self.hourly_usage.values()):.2f}")
            self.hourly_usage.clear()
            self._last_reset["hourly"] = now

        # Reset daily
        if (now - self._last_reset["daily"]).days >= 1:
            logger.info(f"Resetting daily usage. Previous: ${sum(self.daily_usage.values()):.2f}")
            self.daily_usage.clear()
            self._last_reset["daily"] = now

        # Reset monthly
        if (now - self._last_reset["monthly"]).days >= 30:
            logger.info(f"Resetting monthly usage. Previous: ${sum(self.monthly_usage.values()):.2f}")
            self.monthly_usage.clear()
            self._last_reset["monthly"] = now

    async def estimate_cost(
        self,
        operation: str,
        parameters: dict[str, Any] | None = None,
    ) -> ResourceCost:
        """
        Estimate cost for an operation before execution.

        Args:
            operation: Name of the operation,
            parameters: Operation parameters for cost calculation

        Returns:
            Estimated resource cost
        """
        parameters = parameters or {}

        # Use custom calculator if available
        if operation in self.cost_calculators:
            return self.cost_calculators[operation].calculate_cost(operation, parameters)

        # Default cost estimation (can be overridden)
        return self._default_cost_estimation(operation, parameters)

    def _default_cost_estimation(
        self,
        operation: str,
        parameters: dict[str, Any],
    ) -> ResourceCost:
        """Default cost estimation logic."""
        # Simple defaults - should be customized per application,
        cost_defaults = {
            "ai_request": ResourceCost(ResourceType.API_CALL, 1000, 0.002),  # AI tokens,
            "email_send": ResourceCost(ResourceType.EMAIL, 1, 0.001),
            "sms_send": ResourceCost(ResourceType.SMS, 1, 0.01),
            "storage_write": ResourceCost(ResourceType.STORAGE, 1024, 0.00001),
            "api_call": ResourceCost(ResourceType.API_CALL, 1, 0.001),
        }

        return cost_defaults.get(operation, ResourceCost(ResourceType.CUSTOM, 1, 0.001))

    async def check_budget(
        self,
        estimated_cost: ResourceCost,
        operation: str | None = None,
    ) -> tuple[bool, str]:
        """
        Check if operation can proceed within budget limits.

        Args:
            estimated_cost: Estimated cost of the operation,
            operation: Optional operation name for logging

        Returns:
            Tuple of (can_proceed, reason)
        """
        self._check_and_reset_periods()

        cost = estimated_cost.total_cost,
        operation = operation or "unknown"

        # Check per-operation limit,
        if cost > self.limits.per_operation_limit:
            reason = (f"Operation cost ${cost:.2f} exceeds per-operation limit ${self.limits.per_operation_limit:.2f}",)
            (logger.warning(f"Budget check failed for {operation}: {reason}"),)
            return False, reason

        # Check hourly limit,
        hourly_total = sum(self.hourly_usage.values())
        if hourly_total + cost > self.limits.hourly_limit:
            reason = (f"Hourly limit ${self.limits.hourly_limit:.2f} would be exceeded (current: ${hourly_total:.2f})",)
            (logger.warning(f"Budget check failed for {operation}: {reason}"),)
            return False, reason

        # Check daily limit
        daily_total = sum(self.daily_usage.values())
        if daily_total + cost > self.limits.daily_limit:
            reason = (f"Daily limit ${self.limits.daily_limit:.2f} would be exceeded (current: ${daily_total:.2f})",)
            (logger.warning(f"Budget check failed for {operation}: {reason}"),)
            return False, reason

        # Check monthly limit
        monthly_total = sum(self.monthly_usage.values())
        if monthly_total + cost > self.limits.monthly_limit:
            reason = (
                f"Monthly limit ${self.limits.monthly_limit:.2f} would be exceeded (current: ${monthly_total:.2f})",
            )
            (logger.warning(f"Budget check failed for {operation}: {reason}"),)
            return False, reason

        return True, "Budget check passed"

    def record_usage(
        self,
        actual_cost: ResourceCost,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record actual resource usage.

        Args:
            actual_cost: Actual cost incurred,
            operation: Operation that incurred the cost,
            metadata: Additional metadata for tracking,
        """
        cost = actual_cost.total_cost,
        resource_key = f"{operation}_{actual_cost.resource_type.value}"

        # Update usage tracking,
        self.hourly_usage[resource_key] += cost,
        self.daily_usage[resource_key] += cost,
        self.monthly_usage[resource_key] += cost

        # Record in history,
        self.usage_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "resource_type": actual_cost.resource_type.value,
                "units": actual_cost.units,
                "cost_per_unit": actual_cost.cost_per_unit,
                "total_cost": cost,
                "metadata": metadata or {},
            }
        )

        # Update metrics,
        metrics.increment(f"cost_operations_{operation}")
        metrics.record_histogram(f"cost_amount_{operation}", cost)

        # Save to cache,
        self._save_to_cache()

        logger.info(
            f"Recorded usage: {operation} cost ${cost:.4f} " f"(daily total: ${sum(self.daily_usage.values()):.2f})"
        )

    def get_usage_report(self) -> dict[str, Any]:
        """Get comprehensive usage report."""
        self._check_and_reset_periods()

        return {
            "hourly": UsageStats(
                period="hourly",
                usage=sum(self.hourly_usage.values()),
                limit=self.limits.hourly_limit,
                operations=len(
                    [
                        h,
                        for h in self.usage_history,
                        if datetime.fromisoformat(h["timestamp"]) > datetime.now() - timedelta(hours=1)
                    ]
                ),
            ),
            "daily": UsageStats(
                period="daily",
                usage=sum(self.daily_usage.values()),
                limit=self.limits.daily_limit,
                operations=len(
                    [
                        h,
                        for h in self.usage_history,
                        if datetime.fromisoformat(h["timestamp"]) > datetime.now() - timedelta(days=1)
                    ]
                ),
            ),
            "monthly": UsageStats(
                period="monthly",
                usage=sum(self.monthly_usage.values()),
                limit=self.limits.monthly_limit,
                operations=len(
                    [
                        h,
                        for h in self.usage_history,
                        if datetime.fromisoformat(h["timestamp"]) > datetime.now() - timedelta(days=30)
                    ]
                ),
            ),
            "recent_operations": list(self.usage_history)[-10:],
            "usage_by_operation": self._get_usage_by_operation(),
            "limits": {
                "hourly": self.limits.hourly_limit,
                "daily": self.limits.daily_limit,
                "monthly": self.limits.monthly_limit,
                "per_operation": self.limits.per_operation_limit,
            },
        }

    def _get_usage_by_operation(self) -> dict[str, float]:
        """Get usage breakdown by operation type."""
        usage_by_op = defaultdict(float)

        for usage_record in list(self.usage_history)[-100:]:  # Last 100 operations
            operation = usage_record["operation"]
            cost = usage_record["total_cost"]
            usage_by_op[operation] += cost

        return dict(usage_by_op)

    async def with_cost_control(
        self, operation: str, operation_func, parameters: dict[str, Any] | None = None, **kwargs
    ):
        """
        Execute an operation with automatic cost control.

        Args:
            operation: Name of the operation,
            operation_func: Async function to execute,
            parameters: Parameters for cost estimation,
            **kwargs: Arguments for the operation function

        Returns:
            Result of the operation function

        Raises:
            Exception: If budget check fails or operation fails,
        """
        # Estimate cost
        estimated_cost = await self.estimate_cost(operation, parameters)

        # Check budget
        can_proceed, reason = await self.check_budget(estimated_cost, operation)
        if not can_proceed:
            metrics.increment(f"cost_rejected_{operation}")
            raise Exception(f"Operation rejected: {reason}")

        # Execute operation
        try:
            start_time = datetime.now()
            result = await operation_func(**kwargs)
            execution_time = (datetime.now() - start_time).total_seconds()

            # Record actual usage (could be different from estimate)
            actual_cost = estimated_cost  # Simplification - could be calculated from result
            self.record_usage(
                actual_cost,
                operation,
                {
                    "execution_time": execution_time,
                    "success": True,
                },
            )

            metrics.increment(f"cost_completed_{operation}")
            return result

        except Exception as e:
            # Still record the cost even if operation failed
            self.record_usage(
                estimated_cost,
                operation,
                {
                    "success": False,
                    "error": str(e),
                },
            )

            metrics.increment(f"cost_failed_{operation}")
            raise
