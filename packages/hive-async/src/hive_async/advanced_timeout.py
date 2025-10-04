"""Advanced resilience management combining timeout, circuit breaker, and retry patterns.

This module provides the unified AsyncResilienceManager which consolidates:
- Adaptive timeout management
- Circuit breaker fault tolerance
- Performance monitoring and metrics
- Alert callbacks and recommendations
"""

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from hive_errors import AsyncTimeoutError, CircuitBreakerOpenError
from hive_logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior."""

    # Basic timeout settings
    default_timeout: float = 30.0
    connect_timeout: float = 10.0
    read_timeout: float = 60.0
    write_timeout: float = 30.0

    # Adaptive timeout settings
    enable_adaptive: bool = True
    adaptation_factor: float = 1.5  # Multiply by this factor when adapting
    max_adaptive_timeout: float = 300.0  # 5 minutes max
    min_adaptive_timeout: float = 1.0  # 1 second min

    # Monitoring settings
    track_performance: bool = True
    history_size: int = 1000

    # Retry integration
    enable_retry_escalation: bool = True
    retry_timeout_multiplier: float = 2.0

    # Circuit breaker settings
    enable_circuit_breaker: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 60
    expected_exception: type = Exception


@dataclass
class TimeoutMetrics:
    """Metrics for timeout and circuit breaker operations."""

    operation_name: str
    total_attempts: int = 0
    successful_attempts: int = 0
    timeout_count: int = 0
    failure_count: int = 0
    circuit_breaker_trips: int = 0
    average_duration: float = 0.0
    p95_duration: float = 0.0
    p99_duration: float = 0.0
    last_success_duration: float | None = None
    consecutive_timeouts: int = 0
    consecutive_failures: int = 0
    recommended_timeout: float | None = None
    circuit_state: CircuitState = CircuitState.CLOSED
    last_failure_time: float | None = None
    durations: deque = field(default_factory=lambda: deque(maxlen=100))
    failure_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    state_transitions: deque = field(default_factory=lambda: deque(maxlen=100))


class AsyncResilienceManager:
    """Unified resilience manager combining timeout and circuit breaker patterns.

    Features:
    - Adaptive timeout adjustment based on historical performance
    - Circuit breaker fault tolerance with automatic recovery
    - Operation-specific timeout and failure profiles
    - Performance monitoring and comprehensive metrics
    - Integration with retry mechanisms
    - Timeout escalation and circuit breaker coordination
    - Comprehensive logging and alerting

    This replaces the separate AsyncCircuitBreaker and AsyncTimeoutManager classes.
    """

    def __init__(self, config: TimeoutConfig | None = None, name: str = "default") -> None:
        self.config = config or TimeoutConfig()
        self.name = name

        # Metrics tracking
        self._operation_metrics: dict[str, TimeoutMetrics] = {}
        self._global_stats = {
            "total_operations": 0,
            "total_timeouts": 0,
            "total_failures": 0,
            "timeout_rate": 0.0,
            "failure_rate": 0.0,
        }

        # Adaptive timeout cache
        self._adaptive_timeouts: dict[str, float] = {}
        self._last_adaptation: dict[str, datetime] = {}

        # Circuit breaker state (per operation)
        self._circuit_locks: dict[str, asyncio.Lock] = {}

        # Alert callbacks
        self._alert_callbacks: list[Callable] = []

    def get_timeout(self, operation_name: str, timeout_type: str = "default", retry_attempt: int = 0) -> float:
        """Get appropriate timeout for an operation.

        Args:
            operation_name: Name of the operation
            timeout_type: Type of timeout (default, connect, read, write)
            retry_attempt: Current retry attempt (0 for first attempt)

        Returns:
            Timeout value in seconds

        """
        # Get base timeout
        base_timeout = getattr(self.config, f"{timeout_type}_timeout", self.config.default_timeout)

        # Apply retry escalation if enabled
        if self.config.enable_retry_escalation and retry_attempt > 0:
            base_timeout *= self.config.retry_timeout_multiplier**retry_attempt

        # Apply adaptive timeout if enabled
        if self.config.enable_adaptive and operation_name in self._adaptive_timeouts:
            adaptive_timeout = self._adaptive_timeouts[operation_name]
            # Use the larger of base or adaptive timeout
            base_timeout = max(base_timeout, adaptive_timeout)

        # Ensure within bounds
        base_timeout = max(self.config.min_adaptive_timeout, base_timeout)
        base_timeout = min(self.config.max_adaptive_timeout, base_timeout)

        return base_timeout

    async def execute_with_timeout_async(
        self,
        operation: Callable,
        operation_name: str,
        timeout: float | None = None,
        timeout_type: str = "default",
        retry_attempt: int = 0,
        *args,
        **kwargs,
    ) -> Any:
        """Execute operation with unified timeout and circuit breaker management.

        Args:
            operation: Async function to execute
            operation_name: Name for metrics tracking
            timeout: Explicit timeout value (overrides automatic calculation)
            timeout_type: Type of timeout for automatic calculation
            retry_attempt: Current retry attempt
            *args, **kwargs: Arguments for the operation

        Returns:
            Operation result

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            AsyncTimeoutError: If operation times out
            Exception: Any exception from the operation

        """
        # Check circuit breaker state BEFORE execution
        if self.config.enable_circuit_breaker:
            await self._check_circuit_breaker_async(operation_name)

        # Determine timeout
        if timeout is None:
            timeout = self.get_timeout(operation_name, timeout_type, retry_attempt)

        # Initialize metrics if needed
        if operation_name not in self._operation_metrics:
            self._operation_metrics[operation_name] = TimeoutMetrics(operation_name=operation_name)

        metrics = self._operation_metrics[operation_name]
        metrics.total_attempts += 1
        self._global_stats["total_operations"] += 1

        start_time = time.perf_counter()

        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(operation):
                result = await asyncio.wait_for(operation(*args, **kwargs), timeout=timeout)
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(operation, *args, **kwargs), timeout=timeout,
                )

            # Record success
            duration = time.perf_counter() - start_time
            await self._record_success_async(operation_name, duration, timeout)

            return result

        except TimeoutError as e:
            # Record timeout as a type of failure
            duration = time.perf_counter() - start_time
            await self._record_timeout_async(operation_name, duration, timeout, retry_attempt)

            # Convert to AsyncTimeoutError with better context
            raise AsyncTimeoutError(
                f"Operation '{operation_name}' timed out",
                operation=operation_name,
                timeout_duration=timeout,
                elapsed_time=duration,
            ) from e

        except asyncio.CancelledError:
            # Handle cancellation without recording as failure
            logger.debug(f"Operation {operation_name} was cancelled")
            raise

        except Exception as e:
            # Record failure (will trigger circuit breaker logic)
            duration = time.perf_counter() - start_time
            await self._record_failure_async(operation_name, duration, e, retry_attempt)
            raise

    async def _record_success_async(self, operation_name: str, duration: float, timeout: float) -> None:
        """Record successful operation and update circuit breaker state."""
        metrics = self._operation_metrics[operation_name]

        metrics.successful_attempts += 1
        metrics.durations.append(duration)
        metrics.last_success_duration = duration
        metrics.consecutive_timeouts = 0
        metrics.consecutive_failures = 0

        # Circuit breaker state management
        if self.config.enable_circuit_breaker:
            lock = await self._get_circuit_lock_async(operation_name)
            async with lock:
                # If circuit was HALF_OPEN, success means we can close it
                if metrics.circuit_state == CircuitState.HALF_OPEN:
                    old_state = metrics.circuit_state
                    metrics.circuit_state = CircuitState.CLOSED
                    metrics.failure_count = 0

                    # Record state transition
                    metrics.state_transitions.append(
                        {
                            "timestamp": datetime.utcnow(),
                            "from_state": old_state.value,
                            "to_state": CircuitState.CLOSED.value,
                            "failure_count": 0,
                        },
                    )
                    logger.info(f"Circuit breaker for {operation_name} reset to CLOSED after successful recovery")

        # Update statistics
        await self._update_operation_stats_async(operation_name)

        # Potentially update adaptive timeout
        if self.config.enable_adaptive:
            await self._update_adaptive_timeout_async(operation_name)

        logger.debug(f"Operation {operation_name} completed in {duration:.3f}s (timeout: {timeout:.1f}s)")

    async def _record_timeout_async(
        self,
        operation_name: str,
        duration: float,
        timeout: float,
        retry_attempt: int,
    ) -> None:
        """Record timeout occurrence."""
        metrics = self._operation_metrics[operation_name]

        metrics.timeout_count += 1
        metrics.consecutive_timeouts += 1
        self._global_stats["total_timeouts"] += 1

        # Update global timeout rate
        self._global_stats["timeout_rate"] = (
            self._global_stats["total_timeouts"] / self._global_stats["total_operations"]
        )

        # Log timeout
        logger.warning(
            f"Timeout in operation {operation_name} after {duration:.3f}s ",
            f"(timeout: {timeout:.1f}s, attempt: {retry_attempt + 1})",
        )

        # Check for alert conditions
        await self._check_timeout_alerts_async(operation_name, metrics)

        # Update adaptive timeout if needed
        if self.config.enable_adaptive and metrics.consecutive_timeouts >= 3:
            await self._escalate_adaptive_timeout_async(operation_name)

    async def _update_operation_stats_async(self, operation_name: str) -> None:
        """Update operation statistics."""
        metrics = self._operation_metrics[operation_name]
        durations = list(metrics.durations)

        if not durations:
            return

        # Calculate statistics
        metrics.average_duration = sum(durations) / len(durations)

        # Calculate percentiles
        sorted_durations = sorted(durations)
        if len(sorted_durations) >= 20:  # Need reasonable sample size
            p95_index = int(len(sorted_durations) * 0.95)
            p99_index = int(len(sorted_durations) * 0.99)
            metrics.p95_duration = sorted_durations[p95_index]
            metrics.p99_duration = sorted_durations[p99_index]

    async def _update_adaptive_timeout_async(self, operation_name: str) -> None:
        """Update adaptive timeout based on performance."""
        metrics = self._operation_metrics[operation_name]

        # Need sufficient data for adaptation
        if len(metrics.durations) < 10:
            return

        # Calculate recommended timeout based on P95 + safety margin
        if metrics.p95_duration > 0:
            recommended = metrics.p95_duration * self.config.adaptation_factor

            # Ensure within bounds
            recommended = max(self.config.min_adaptive_timeout, recommended)
            recommended = min(self.config.max_adaptive_timeout, recommended)

            self._adaptive_timeouts[operation_name] = recommended
            metrics.recommended_timeout = recommended
            self._last_adaptation[operation_name] = datetime.utcnow()

            logger.info(
                f"Updated adaptive timeout for {operation_name}: {recommended:.2f}s ",
                f"(based on P95: {metrics.p95_duration:.2f}s)",
            )

    async def _escalate_adaptive_timeout_async(self, operation_name: str) -> None:
        """Escalate timeout due to consecutive failures."""
        current_timeout = self._adaptive_timeouts.get(operation_name, self.config.default_timeout)

        # Increase timeout more aggressively
        new_timeout = current_timeout * (self.config.adaptation_factor * 1.5)
        new_timeout = min(self.config.max_adaptive_timeout, new_timeout)

        self._adaptive_timeouts[operation_name] = new_timeout
        self._last_adaptation[operation_name] = datetime.utcnow()

        logger.warning(f"Escalated timeout for {operation_name} to {new_timeout:.2f}s due to consecutive timeouts")

    async def _check_timeout_alerts_async(self, operation_name: str, metrics: TimeoutMetrics) -> None:
        """Check if timeout conditions warrant alerts."""
        alerts = []

        # High consecutive timeout count
        if metrics.consecutive_timeouts >= 5:
            alerts.append(
                {
                    "type": "consecutive_timeouts",
                    "operation": operation_name,
                    "count": metrics.consecutive_timeouts,
                    "severity": "critical",
                    "message": f"Operation {operation_name} has {metrics.consecutive_timeouts} consecutive timeouts",
                },
            )

        # High timeout rate for operation
        if metrics.total_attempts > 20:  # Minimum sample size
            timeout_rate = metrics.timeout_count / metrics.total_attempts
            if timeout_rate > 0.5:  # 50% timeout rate
                alerts.append(
                    {
                        "type": "high_timeout_rate",
                        "operation": operation_name,
                        "timeout_rate": timeout_rate,
                        "severity": "warning",
                        "message": f"Operation {operation_name} has high timeout rate: {timeout_rate:.1%}",
                    },
                )

        # Trigger alerts if any
        if alerts:
            await self._trigger_alerts_async(alerts)

    async def _trigger_alerts_async(self, alerts: list[dict[str, Any]]) -> None:
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alerts)
                else:
                    callback(alerts)
            except Exception as e:
                logger.error(f"Error in timeout alert callback: {e}")

    async def _record_failure_async(
        self,
        operation_name: str,
        duration: float,
        error: Exception,
        retry_attempt: int,
    ) -> None:
        """Record operation failure and update circuit breaker state."""
        metrics = self._operation_metrics[operation_name]

        metrics.failure_count += 1
        metrics.consecutive_failures += 1
        metrics.durations.append(duration)
        self._global_stats["total_failures"] += 1

        # Update global failure rate
        self._global_stats["failure_rate"] = (
            self._global_stats["total_failures"] / self._global_stats["total_operations"]
        )

        # Record failure in history
        metrics.failure_history.append(
            {
                "timestamp": datetime.utcnow(),
                "error_type": type(error).__name__,
                "duration": duration,
                "state_before": metrics.circuit_state.value if self.config.enable_circuit_breaker else "disabled",
            },
        )

        # Circuit breaker logic
        if self.config.enable_circuit_breaker:
            lock = await self._get_circuit_lock_async(operation_name)
            async with lock:
                if metrics.failure_count >= self.config.failure_threshold:
                    old_state = metrics.circuit_state
                    metrics.circuit_state = CircuitState.OPEN
                    metrics.last_failure_time = time.time()
                    metrics.circuit_breaker_trips += 1

                    # Record state transition
                    metrics.state_transitions.append(
                        {
                            "timestamp": datetime.utcnow(),
                            "from_state": old_state.value,
                            "to_state": CircuitState.OPEN.value,
                            "failure_count": metrics.failure_count,
                        },
                    )

                    logger.warning(
                        f"Circuit breaker OPENED for {operation_name} after {metrics.failure_count} failures",
                    )

        logger.warning(
            f"Failure in operation {operation_name} after {duration:.3f}s ",
            f"(attempt: {retry_attempt + 1}, error: {type(error).__name__})",
        )

    async def _get_circuit_lock_async(self, operation_name: str) -> asyncio.Lock:
        """Get or create circuit breaker lock for operation."""
        if operation_name not in self._circuit_locks:
            self._circuit_locks[operation_name] = asyncio.Lock()
        return self._circuit_locks[operation_name]

    async def _check_circuit_breaker_async(self, operation_name: str) -> None:
        """Check circuit breaker state before executing operation."""
        if operation_name not in self._operation_metrics:
            return  # No metrics yet, allow operation

        metrics = self._operation_metrics[operation_name]
        lock = await self._get_circuit_lock_async(operation_name)

        async with lock:
            if metrics.circuit_state == CircuitState.OPEN:
                # Check if enough time has passed to attempt reset
                if self._should_attempt_reset(operation_name):
                    metrics.circuit_state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker for {operation_name} transitioning to HALF_OPEN")
                else:
                    # Still open - block operation
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN for operation '{operation_name}' - operation blocked",
                        failure_count=metrics.failure_count,
                        recovery_time=self.config.recovery_timeout,
                    )

    def _should_attempt_reset(self, operation_name: str) -> bool:
        """Check if enough time has passed to attempt circuit reset."""
        metrics = self._operation_metrics.get(operation_name)
        if not metrics or metrics.last_failure_time is None:
            return True
        return time.time() - metrics.last_failure_time > self.config.recovery_timeout

    async def reset_circuit_breaker_async(self, operation_name: str) -> None:
        """Manually reset circuit breaker for an operation."""
        if operation_name not in self._operation_metrics:
            logger.warning(f"No metrics found for operation {operation_name}")
            return

        metrics = self._operation_metrics[operation_name]
        lock = await self._get_circuit_lock_async(operation_name)

        async with lock:
            old_state = metrics.circuit_state
            metrics.circuit_state = CircuitState.CLOSED
            metrics.failure_count = 0
            metrics.consecutive_failures = 0
            metrics.last_failure_time = None

            # Record state transition
            metrics.state_transitions.append(
                {
                    "timestamp": datetime.utcnow(),
                    "from_state": old_state.value,
                    "to_state": CircuitState.CLOSED.value,
                    "failure_count": 0,
                },
            )

            logger.info(f"Circuit breaker for {operation_name} manually reset to CLOSED")

    def is_circuit_open(self, operation_name: str) -> bool:
        """Check if circuit breaker is open for an operation."""
        metrics = self._operation_metrics.get(operation_name)
        if not metrics or not self.config.enable_circuit_breaker:
            return False
        return metrics.circuit_state == CircuitState.OPEN

    def get_circuit_status(self, operation_name: str) -> dict[str, Any]:
        """Get circuit breaker status for an operation."""
        metrics = self._operation_metrics.get(operation_name)
        if not metrics:
            return {
                "state": "unknown",
                "failure_count": 0,
                "enabled": self.config.enable_circuit_breaker,
            }

        return {
            "state": metrics.circuit_state.value,
            "failure_count": metrics.failure_count,
            "failure_threshold": self.config.failure_threshold,
            "last_failure_time": metrics.last_failure_time,
            "recovery_timeout": self.config.recovery_timeout,
            "circuit_breaker_trips": metrics.circuit_breaker_trips,
            "enabled": self.config.enable_circuit_breaker,
        }

    def get_failure_history(
        self,
        operation_name: str,
        metric_type: str = "failure_rate",
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get failure history for predictive analysis.

        Returns failure metrics in MetricPoint-compatible format for
        integration with PredictiveAnalysisRunner.

        Args:
            operation_name: Operation to get history for
            metric_type: Type of metric (failure_rate, state_changes)
            hours: Number of hours of history to return

        Returns:
            List of metric points with timestamp, value, and metadata

        """
        metrics = self._operation_metrics.get(operation_name)
        if not metrics:
            logger.debug(f"No metrics available for {operation_name}")
            return []

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        if metric_type == "failure_rate":
            # Get recent failures
            recent_failures = [f for f in metrics.failure_history if f["timestamp"] >= cutoff_time]

            if not recent_failures:
                logger.debug(f"No failure history available for {operation_name}")
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
                            "operation": operation_name,
                            "metric_type": "failure_rate",
                            "unit": "failures_per_hour",
                        },
                    },
                )

            logger.debug(f"Retrieved {len(metric_points)} failure rate points for {operation_name}")
            return metric_points

        if metric_type == "state_changes":
            # Get recent state transitions
            recent_transitions = [t for t in metrics.state_transitions if t["timestamp"] >= cutoff_time]

            if not recent_transitions:
                logger.debug(f"No state transitions for {operation_name}")
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
                            "operation": operation_name,
                            "metric_type": "state_change",
                            "from_state": transition["from_state"],
                            "to_state": transition["to_state"],
                            "failure_count": transition["failure_count"],
                            "unit": "binary",
                        },
                    },
                )

            logger.debug(f"Retrieved {len(metric_points)} state transition points for {operation_name}")
            return metric_points

        logger.warning(f"Unknown metric type: {metric_type}")
        return []

    def add_alert_callback(self, callback: Callable) -> None:
        """Add alert callback for timeout and failure events."""
        self._alert_callbacks.append(callback)

    def get_operation_metrics(self, operation_name: str) -> TimeoutMetrics | None:
        """Get metrics for a specific operation."""
        return self._operation_metrics.get(operation_name)

    def get_all_metrics(self) -> dict[str, TimeoutMetrics]:
        """Get metrics for all operations."""
        return self._operation_metrics.copy()

    def get_global_stats(self) -> dict[str, Any]:
        """Get global timeout statistics."""
        return {
            **self._global_stats,
            "operations_tracked": len(self._operation_metrics),
            "adaptive_timeouts_active": len(self._adaptive_timeouts),
        }

    def get_recommendations(self) -> list[dict[str, Any]]:
        """Get timeout optimization recommendations."""
        recommendations = []

        for operation_name, metrics in self._operation_metrics.items():
            if metrics.total_attempts < 10:
                continue  # Not enough data

            # High timeout rate
            timeout_rate = metrics.timeout_count / metrics.total_attempts
            if timeout_rate > 0.2:  # 20% timeout rate
                recommendations.append(
                    {
                        "type": "high_timeout_rate",
                        "operation": operation_name,
                        "current_rate": timeout_rate,
                        "recommendation": "Consider increasing timeout or optimizing operation performance",
                        "priority": "high" if timeout_rate > 0.5 else "medium",
                    },
                )

            # Underutilized timeout
            if metrics.p99_duration > 0 and metrics.recommended_timeout:
                current_timeout = self.get_timeout(operation_name)
                if current_timeout > metrics.p99_duration * 3:  # 3x safety margin
                    recommendations.append(
                        {
                            "type": "over_timeout",
                            "operation": operation_name,
                            "current_timeout": current_timeout,
                            "recommended_timeout": metrics.p99_duration * 2,
                            "recommendation": "Timeout may be unnecessarily high - consider reducing",
                            "priority": "low",
                        },
                    )

            # Highly variable performance
            if len(metrics.durations) > 20:
                durations = list(metrics.durations)
                variance = max(durations) - min(durations)
                if variance > metrics.average_duration * 2:
                    recommendations.append(
                        {
                            "type": "high_variance",
                            "operation": operation_name,
                            "variance": variance,
                            "recommendation": "Operation has highly variable performance - investigate bottlenecks",
                            "priority": "medium",
                        },
                    )

        return recommendations

    def reset_adaptive_timeouts(self, operation_name: str | None = None) -> None:
        """Reset adaptive timeouts for debugging/testing."""
        if operation_name:
            self._adaptive_timeouts.pop(operation_name, None)
            self._last_adaptation.pop(operation_name, None)
            logger.info(f"Reset adaptive timeout for {operation_name}")
        else:
            self._adaptive_timeouts.clear()
            self._last_adaptation.clear()
            logger.info("Reset all adaptive timeouts")

    def export_metrics(self, format: str = "json") -> str:
        """Export timeout metrics in specified format."""
        export_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "global_stats": self.get_global_stats(),
            "operation_metrics": {
                name: {
                    "operation_name": metrics.operation_name,
                    "total_attempts": metrics.total_attempts,
                    "successful_attempts": metrics.successful_attempts,
                    "timeout_count": metrics.timeout_count,
                    "timeout_rate": (
                        metrics.timeout_count / metrics.total_attempts if metrics.total_attempts > 0 else 0.0
                    ),
                    "average_duration": metrics.average_duration,
                    "p95_duration": metrics.p95_duration,
                    "p99_duration": metrics.p99_duration,
                    "recommended_timeout": metrics.recommended_timeout,
                }
                for name, metrics in self._operation_metrics.items()
            },
            "adaptive_timeouts": self._adaptive_timeouts.copy(),
            "recommendations": self.get_recommendations(),
        }

        if format == "json":
            import json

            return json.dumps(export_data, indent=2)
        raise ValueError(f"Unsupported export format: {format}")


# Context manager for resilience operations
@asynccontextmanager
async def resilience_context_async(
    manager: AsyncResilienceManager,
    operation_name: str,
    timeout: float | None = None,
    timeout_type: str = "default",
    retry_attempt: int = 0,
) -> AsyncGenerator[float, None]:
    """Context manager for unified resilience operations (timeout + circuit breaker)."""
    actual_timeout = timeout or manager.get_timeout(operation_name, timeout_type, retry_attempt)

    start_time = time.perf_counter()

    try:
        async with asyncio.timeout(actual_timeout):
            yield actual_timeout

        # Record success
        duration = time.perf_counter() - start_time
        await manager._record_success_async(operation_name, duration, actual_timeout)

    except TimeoutError:
        # Record timeout
        duration = time.perf_counter() - start_time
        await manager._record_timeout_async(operation_name, duration, actual_timeout, retry_attempt)
        raise


# Decorator for automatic resilience management
def with_resilience(
    manager: AsyncResilienceManager,
    operation_name: str | None = None,
    timeout_type: str = "default",
    timeout: float | None = None,
):
    """Decorator for automatic resilience management (timeout + circuit breaker)."""

    def decorator(func: Callable) -> Callable:
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"

        async def wrapper_async(*args, **kwargs):
            return await manager.execute_with_timeout_async(
                func,
                operation_name,
                *args,
                timeout=timeout,
                timeout_type=timeout_type,
                retry_attempt=kwargs.pop("_retry_attempt", 0),
                **kwargs,
            )

        return wrapper_async

    return decorator


# Backward compatibility aliases
AdvancedTimeoutManager = AsyncResilienceManager  # Primary alias
timeout_context_async = resilience_context_async
with_adaptive_timeout = with_resilience
timeout_context = resilience_context_async
