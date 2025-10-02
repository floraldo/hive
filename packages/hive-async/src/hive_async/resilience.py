"""
Async resilience patterns for fault tolerance.

Provides circuit breakers, timeout management, and other resilience patterns
specifically designed for async operations.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any

from hive_errors import AsyncTimeoutError, CircuitBreakerOpenError
from hive_logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AsyncCircuitBreaker:
    """
    Async-optimized circuit breaker for fault tolerance.

    Prevents cascading failures by temporarily blocking operations
    when failure rate exceeds threshold.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

        # Async-specific improvements
        self._lock = asyncio.Lock()
        self._half_open_task = None

        # Failure history tracking for predictive analysis
        self._failure_history = deque(maxlen=1000)
        self._state_transitions = deque(maxlen=100)

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker"""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(
                        "Circuit breaker is OPEN - operation blocked",
                        failure_count=self.failure_count,
                        recovery_time=self.recovery_timeout,
                    )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Success - reset circuit breaker
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.CLOSED
                    logger.info("Circuit breaker reset to CLOSED")
                self.failure_count = 0

            return result

        except self.expected_exception as e:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()

                # Record failure for predictive analysis
                self._failure_history.append(
                    {"timestamp": datetime.utcnow(), "error_type": type(e).__name__, "state_before": self.state.value},
                )

                if self.failure_count >= self.failure_threshold:
                    old_state = self.state
                    self.state = CircuitState.OPEN

                    # Record state transition
                    self._state_transitions.append(
                        {
                            "timestamp": datetime.utcnow(),
                            "from_state": old_state.value,
                            "to_state": CircuitState.OPEN.value,
                            "failure_count": self.failure_count,
                        },
                    )

                    logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")

            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time > self.recovery_timeout

    async def reset_async(self) -> None:
        """Manually reset circuit breaker"""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = None
            logger.info("Circuit breaker manually reset")

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open"""
        return self.state == CircuitState.OPEN

    def get_status(self) -> dict:
        """Get current status for monitoring"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "recovery_timeout": self.recovery_timeout,
        }

    def get_failure_history(self, metric_type: str = "failure_rate", hours: int = 24) -> list[dict[str, Any]]:
        """
        Get failure history for predictive analysis.

        Returns failure metrics as MetricPoint-compatible format for
        integration with PredictiveAnalysisRunner.

        Args:
            metric_type: Type of metric (failure_rate, state_changes)
            hours: Number of hours of history to return

        Returns:
            List of metric points with timestamp, value, and metadata
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        if metric_type == "failure_rate":
            # Get recent failures
            recent_failures = [f for f in self._failure_history if f["timestamp"] >= cutoff_time]

            if not recent_failures:
                logger.debug(f"No failure history available for {self.name}")
                return []

            # Group by hour and count
            failure_counts_by_hour = defaultdict(int)
            for failure in recent_failures:
                hour_key = failure["timestamp"].replace(minute=0, second=0, microsecond=0)
                failure_counts_by_hour[hour_key] += 1

            # Convert to MetricPoint format
            metric_points = []
            for hour, count in sorted(failure_counts_by_hour.items()):
                metric_points.append(
                    {
                        "timestamp": hour,
                        "value": float(count),
                        "metadata": {
                            "circuit_breaker": self.name,
                            "metric_type": "failure_rate",
                            "unit": "failures_per_hour",
                        },
                    },
                )

            logger.debug(f"Retrieved {len(metric_points)} failure rate points for circuit breaker {self.name}")

            return metric_points

        elif metric_type == "state_changes":
            # Get recent state transitions
            recent_transitions = [t for t in self._state_transitions if t["timestamp"] >= cutoff_time]

            if not recent_transitions:
                logger.debug(f"No state transitions for {self.name}")
                return []

            # Convert state transitions to metric points
            metric_points = []
            for transition in recent_transitions:
                # Value: 1.0 for OPEN transitions (bad), 0.0 for CLOSED (good)
                value = 1.0 if transition["to_state"] == CircuitState.OPEN.value else 0.0

                metric_points.append(
                    {
                        "timestamp": transition["timestamp"],
                        "value": value,
                        "metadata": {
                            "circuit_breaker": self.name,
                            "metric_type": "state_change",
                            "from_state": transition["from_state"],
                            "to_state": transition["to_state"],
                            "failure_count": transition["failure_count"],
                            "unit": "binary",
                        },
                    },
                )

            logger.debug(f"Retrieved {len(metric_points)} state transition points for circuit breaker {self.name}")

            return metric_points

        else:
            logger.warning(f"Unknown metric type: {metric_type}")
            return []


class AsyncTimeoutManager:
    """
    Enhanced timeout management for async operations.

    Provides centralized timeout handling with detailed error context
    and operation tracking.
    """

    def __init__(self, default_timeout: float = 30.0) -> None:
        self.default_timeout = default_timeout
        self._active_tasks = set()
        self._operation_stats = {}

    async def run_with_timeout_async(
        self,
        coro,
        timeout: float | None = None,
        operation_name: str | None = None,
        fallback: Any | None = None,
    ) -> Any:
        """
        Run coroutine with timeout and enhanced error context.

        Args:
            coro: Coroutine to execute,
            timeout: Timeout in seconds (uses default if None),
            operation_name: Name for monitoring and debugging,
            fallback: Value to return on timeout (if not None, no exception raised)

        Returns:
            Result of coroutine execution

        Raises:
            AsyncTimeoutError: If operation times out and no fallback provided,
        """
        timeout = (timeout or self.default_timeout,)
        operation_name = operation_name or getattr(coro, "__name__", "unknown_operation")
        start_time = time.time()

        try:
            task = asyncio.create_task(coro)
            self._active_tasks.add(task)

            result = await asyncio.wait_for(task, timeout=timeout)

            # Track success
            elapsed = time.time() - start_time
            self._update_stats(operation_name, elapsed, success=True)

            return result

        except TimeoutError:
            elapsed = time.time() - start_time
            self._update_stats(operation_name, elapsed, success=False)

            if fallback is not None:
                logger.warning(f"Operation {operation_name} timed out, using fallback")
                return fallback

            raise AsyncTimeoutError(
                f"Operation '{operation_name}' timed out",
                operation=operation_name,
                timeout_duration=timeout,
                elapsed_time=elapsed,
            )
        finally:
            if "task" in locals():
                self._active_tasks.discard(task)

    def _update_stats(self, operation_name: str, elapsed: float, success: bool) -> None:
        """Update operation statistics"""
        if operation_name not in self._operation_stats:
            self._operation_stats[operation_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "total_time": 0.0,
                "timeouts": 0,
                "avg_time": 0.0,
                "success_rate": 0.0,
            }

        stats = (self._operation_stats[operation_name],)
        stats["total_calls"] += (1,)
        stats["total_time"] += elapsed

        if success:
            stats["successful_calls"] += (1,)
        else:
            stats["timeouts"] += 1

        # Update derived metrics
        stats["avg_time"] = (stats["total_time"] / stats["total_calls"],)
        stats["success_rate"] = stats["successful_calls"] / stats["total_calls"]

    async def cancel_all_tasks_async(self) -> None:
        """Cancel all active tasks"""
        if self._active_tasks:
            logger.info(f"Cancelling {len(self._active_tasks)} active tasks")
            for task in self._active_tasks.copy():
                task.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
            self._active_tasks.clear()

    def get_statistics(self) -> dict:
        """Get timeout statistics for monitoring"""
        return {
            "active_tasks": len(self._active_tasks),
            "default_timeout": self.default_timeout,
            "operation_stats": self._operation_stats.copy(),
        }


def async_circuit_breaker(failure_threshold: int = 5, recovery_timeout: int = 60, expected_exception: type = Exception):
    """
    Decorator to add circuit breaker protection to async functions.

    Args:
        failure_threshold: Number of failures before opening circuit,
        recovery_timeout: Seconds to wait before attempting reset,
        expected_exception: Exception type that triggers circuit breaker,
    """
    breaker = AsyncCircuitBreaker(failure_threshold, recovery_timeout, expected_exception)

    def decorator(func) -> Any:
        @wraps(func)
        async def wrapper_async(*args, **kwargs):
            return await breaker.call_async(func, *args, **kwargs)

        return wrapper_async

    return decorator


def async_timeout(seconds: float, operation_name: str | None = None) -> None:
    """
    Decorator to add timeout protection to async functions.

    Args:
        seconds: Timeout duration
        operation_name: Name for monitoring (defaults to function name)
    """

    def decorator(func) -> Any:
        timeout_manager = AsyncTimeoutManager()

        @wraps(func)
        async def wrapper_async(*args, **kwargs):
            op_name = operation_name or func.__name__
            return await timeout_manager.run_with_timeout_async(
                func(*args, **kwargs),
                timeout=seconds,
                operation_name=op_name,
            )

        return wrapper_async

    return decorator


# Composite resilience decorator
def async_resilient(
    timeout: float = 30.0,
    circuit_failure_threshold: int = 5,
    circuit_recovery_timeout: int = 60,
    operation_name: str | None = None,
):
    """
    Composite decorator providing both timeout and circuit breaker protection.

    Args:
        timeout: Operation timeout in seconds,
        circuit_failure_threshold: Failures before circuit opens,
        circuit_recovery_timeout: Circuit recovery time,
        operation_name: Operation name for monitoring,
    """

    def decorator(func) -> None:
        # Apply circuit breaker first, then timeout
        circuit_protected = async_circuit_breaker(circuit_failure_threshold, circuit_recovery_timeout)(func)

        timeout_protected = async_timeout(timeout, operation_name)(circuit_protected)

        return timeout_protected

    return decorator
