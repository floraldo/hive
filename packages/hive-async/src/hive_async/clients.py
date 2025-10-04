"""Canonical base class for all service clients with connection pooling and resilience.

This module provides the foundational BaseServiceClient that all domain-specific
clients (cache, SSH, discovery, AI models) inherit from, eliminating duplicated
boilerplate for connection management, retries, circuit breaking, and metrics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

from hive_logging import get_logger
from hive_performance.metrics_collector import MetricsCollector

from .pools import ConnectionPool
from .resilience import AsyncCircuitBreaker, AsyncTimeoutManager

logger = get_logger(__name__)

T = TypeVar("T")  # Connection type
R = TypeVar("R")  # Return type


class BaseServiceClient(ABC, Generic[T]):
    """Canonical base class for all service clients.

    Provides unified infrastructure for:
    - Connection pooling and lifecycle management
    - Circuit breaker protection for fault tolerance
    - Automatic retry logic with exponential backoff
    - Performance metrics collection
    - Timeout management

    Architecture:
        All domain-specific clients (HiveCacheClient, SSHClient, DiscoveryClient,
        ModelClient) inherit from this base and focus purely on business logic.
        Infrastructure concerns are handled by this canonical implementation.

    Usage:
        class MyServiceClient(BaseServiceClient[MyConnectionType]):
            def service_name(self) -> str:
                return "my_service"

            async def my_operation(self, arg: str) -> dict:
                async def operation(conn: MyConnectionType) -> dict:
                    return await conn.execute(arg)

                return await self._execute_with_resilience_async(
                    "my_operation",
                    operation
                )
    """

    def __init__(
        self,
        pool: ConnectionPool[T],
        circuit_breaker: AsyncCircuitBreaker | None = None,
        metrics: MetricsCollector | None = None,
        timeout_manager: AsyncTimeoutManager | None = None,
        default_timeout: float = 30.0,
    ):
        """Initialize base service client.

        Args:
            pool: Connection pool for resource management
            circuit_breaker: Optional circuit breaker (creates default if None)
            metrics: Optional metrics collector (creates default if None)
            timeout_manager: Optional timeout manager (creates default if None)
            default_timeout: Default operation timeout in seconds

        """
        self._pool = pool
        self._default_timeout = default_timeout

        # Create circuit breaker with service-specific name
        self._circuit_breaker = circuit_breaker or AsyncCircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            name=self.service_name(),
        )

        # Create metrics collector
        self._metrics = metrics or MetricsCollector(
            collection_interval=5.0,
            max_history=1000,
            enable_system_metrics=False,
            enable_async_metrics=True,
        )

        # Create timeout manager
        self._timeout_manager = timeout_manager or AsyncTimeoutManager(
            default_timeout=default_timeout,
        )

        # Track client-level stats
        self._stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "circuit_breaker_opens": 0,
            "timeouts": 0,
        }

    @abstractmethod
    def service_name(self) -> str:
        """Return unique service identifier for metrics and logging.

        Examples: "redis_cache", "ssh_deployment", "service_discovery"
        """

    async def _execute_with_resilience_async(
        self,
        operation_name: str,
        operation: Callable[[T], Awaitable[R]],
        timeout: float | None = None,
    ) -> R:
        """Core execution wrapper providing connection pooling, circuit breaking,
        timeouts, and metrics collection.

        This is the canonical implementation pattern that all service clients use.

        Args:
            operation_name: Name of the operation for metrics/logging
            operation: Async function that takes a connection and returns result
            timeout: Optional timeout override (uses default if None)

        Returns:
            Result from the operation

        Raises:
            CircuitBreakerOpenError: Circuit breaker is open
            AsyncTimeoutError: Operation timed out
            ConnectionError: Connection acquisition failed
            Any exception raised by the operation

        """
        self._stats["total_operations"] += 1
        timeout = timeout or self._default_timeout

        # Check circuit breaker state first
        if self._circuit_breaker.is_open:
            self._stats["circuit_breaker_opens"] += 1
            logger.warning(
                f"{self.service_name()}.{operation_name} blocked by circuit breaker",
            )
            # Circuit breaker will raise CircuitBreakerOpenError
            await self._circuit_breaker.call_async(lambda: None)

        # Start metrics tracking
        start_id = await self._metrics.start_operation_tracking_async(
            operation_name=f"{self.service_name()}.{operation_name}",
            tags={
                "service": self.service_name(),
                "operation": operation_name,
            },
        )

        try:
            # Acquire connection from pool
            async with self._pool.connection_async() as conn:
                # Execute operation with timeout and circuit breaker protection
                async def wrapped_operation():
                    return await operation(conn)

                # Wrap with circuit breaker
                async def circuit_protected():
                    return await self._circuit_breaker.call_async(wrapped_operation)

                # Wrap with timeout
                result = await self._timeout_manager.run_with_timeout_async(
                    circuit_protected(),
                    timeout=timeout,
                    operation_name=f"{self.service_name()}.{operation_name}",
                )

                # Track success
                self._stats["successful_operations"] += 1
                await self._metrics.end_operation_tracking_async(
                    start_id,
                    success=True,
                    bytes_processed=self._estimate_bytes(result),
                )

                return result

        except TimeoutError:
            self._stats["timeouts"] += 1
            self._stats["failed_operations"] += 1
            await self._metrics.end_operation_tracking_async(start_id, success=False)
            raise

        except Exception as e:
            self._stats["failed_operations"] += 1
            await self._metrics.end_operation_tracking_async(start_id, success=False)
            logger.error(
                f"{self.service_name()}.{operation_name} failed: {e}",
                exc_info=True,
            )
            raise

    def _estimate_bytes(self, result: Any) -> int:
        """Estimate bytes processed for metrics (best effort)."""
        if result is None:
            return 0
        if isinstance(result, (bytes, bytearray)):
            return len(result)
        if isinstance(result, str):
            return len(result.encode("utf-8"))
        if hasattr(result, "__len__"):
            return len(str(result).encode("utf-8"))
        return 0

    async def initialize_async(self) -> None:
        """Initialize the service client.

        Subclasses can override to add service-specific initialization.
        Default implementation initializes the connection pool.
        """
        await self._pool.initialize_async()
        await self._metrics.start_collection_async()
        logger.info(f"{self.service_name()} client initialized")

    async def close_async(self) -> None:
        """Close the service client and cleanup resources.

        Subclasses can override to add service-specific cleanup.
        Default implementation closes pool, metrics, and timeout manager.
        """
        await self._pool.close_async()
        await self._metrics.stop_collection_async()
        await self._timeout_manager.cancel_all_tasks_async()
        logger.info(f"{self.service_name()} client closed")

    async def health_check_async(self) -> dict[str, Any]:
        """Perform health check on the service.

        Subclasses should override to implement service-specific health checks.
        Default implementation returns pool and circuit breaker status.
        """
        return {
            "service": self.service_name(),
            "healthy": not self._circuit_breaker.is_open,
            "pool_size": self._pool.size,
            "pool_available": self._pool.available,
            "circuit_breaker": self._circuit_breaker.get_status(),
            "stats": self.get_stats(),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get client operation statistics."""
        total = self._stats["total_operations"]
        success_rate = (
            self._stats["successful_operations"] / total * 100
            if total > 0 else 0.0
        )

        return {
            **self._stats,
            "success_rate_percent": round(success_rate, 2),
        }

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get detailed performance metrics."""
        metrics = {}

        # Get metrics for all operations
        all_metrics = self._metrics.get_all_metrics()
        for operation_name, operation_metrics in all_metrics.items():
            if operation_metrics:
                metrics[operation_name] = {
                    "count": len(operation_metrics),
                    "avg_execution_time": sum(m.execution_time for m in operation_metrics) / len(operation_metrics),
                    "avg_memory_usage": sum(m.memory_usage for m in operation_metrics) / len(operation_metrics),
                }

        return metrics

    async def reset_circuit_breaker_async(self) -> None:
        """Manually reset the circuit breaker."""
        await self._circuit_breaker.reset_async()
        logger.info(f"{self.service_name()} circuit breaker manually reset")

    def reset_stats(self) -> None:
        """Reset all statistics counters."""
        self._stats = dict.fromkeys(self._stats, 0)
