"""Generalized rate limiter for any type of operation."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

from hive_logging import get_logger
from hive_performance import MetricsCollector

logger = get_logger(__name__)
metrics = MetricsCollector()


@dataclass
class RateLimit:
    """Rate limit configuration for a specific operation."""

    operation: str
    max_requests_per_second: float = 1.0
    max_requests_per_minute: float = 60.0
    max_requests_per_hour: float = 1000.0
    max_concurrent: int = 10
    burst_allowance: int = 5


@dataclass
class RateLimitWindow:
    """Sliding window for tracking requests."""

    window_seconds: float
    max_requests: float
    requests: Deque[float] = field(default_factory=deque)

    def add_request(self) -> None:
        """Add a request to the window."""
        now = time.time()
        self.requests.append(now)
        self._clean_window(now)

    def can_proceed(self) -> tuple[bool, float]:
        """
        Check if request can proceed.

        Returns:
            Tuple of (can_proceed, wait_time_seconds)
        """
        now = time.time()
        self._clean_window(now)

        if len(self.requests) < self.max_requests:
            return True, 0.0

        # Calculate wait time until oldest request expires
        oldest_request = self.requests[0]
        wait_time = self.window_seconds - (now - oldest_request)
        return False, max(0.0, wait_time)

    def _clean_window(self, now: float) -> None:
        """Remove expired requests from window."""
        cutoff = now - self.window_seconds

        while self.requests and self.requests[0] <= cutoff:
            self.requests.popleft()

    @property
    def current_rate(self) -> float:
        """Get current request rate per second."""
        if not self.requests:
            return 0.0

        now = time.time()
        self._clean_window(now)

        if len(self.requests) < 2:
            return 0.0

        time_span = now - self.requests[0]
        return len(self.requests) / max(time_span, 1.0)


class RateLimiter:
    """
    Generalized rate limiter supporting multiple operations and time windows.

    Features:
    - Per-operation rate limits
    - Multiple time windows (second, minute, hour)
    - Burst allowance
    - Concurrent request limiting
    - Automatic backoff and retry logic
    """

    def __init__(self, default_limits: Optional[RateLimit] = None) -> None:
        """Initialize rate limiter."""
        self.default_limits = default_limits or RateLimit("default")

        # Per-operation rate limits
        self.operation_limits: Dict[str, RateLimit] = {}

        # Rate limiting windows for each operation
        self.windows: Dict[str, Dict[str, RateLimitWindow]] = {}

        # Semaphores for concurrent request limiting
        self.semaphores: Dict[str, asyncio.Semaphore] = {}

        logger.info("RateLimiter initialized")

    def set_operation_limits(self, operation: str, limits: RateLimit) -> None:
        """Set rate limits for a specific operation."""
        self.operation_limits[operation] = limits
        self._initialize_operation_windows(operation, limits)

        logger.info(
            f"Set rate limits for {operation}: "
            f"{limits.max_requests_per_second}/s, "
            f"{limits.max_requests_per_minute}/min, "
            f"{limits.max_concurrent} concurrent"
        )

    def _initialize_operation_windows(self, operation: str, limits: RateLimit) -> None:
        """Initialize rate limiting windows for an operation."""
        self.windows[operation] = {
            "second": RateLimitWindow(1.0, limits.max_requests_per_second),
            "minute": RateLimitWindow(60.0, limits.max_requests_per_minute),
            "hour": RateLimitWindow(3600.0, limits.max_requests_per_hour),
        }

        self.semaphores[operation] = asyncio.Semaphore(limits.max_concurrent)

    def _get_operation_limits(self, operation: str) -> RateLimit:
        """Get rate limits for an operation, falling back to defaults."""
        if operation not in self.operation_limits:
            # Use default limits with operation name
            limits = RateLimit(
                operation=operation,
                max_requests_per_second=self.default_limits.max_requests_per_second,
                max_requests_per_minute=self.default_limits.max_requests_per_minute,
                max_requests_per_hour=self.default_limits.max_requests_per_hour,
                max_concurrent=self.default_limits.max_concurrent,
                burst_allowance=self.default_limits.burst_allowance,
            )
            self.set_operation_limits(operation, limits)

        return self.operation_limits[operation]

    async def acquire(self, operation: str) -> bool:
        """
        Acquire permission to proceed with an operation.

        Args:
            operation: Name of the operation

        Returns:
            True if permission granted, False if rate limited
        """
        limits = self._get_operation_limits(operation)
        windows = self.windows[operation]

        # Check all time windows
        for window_name, window in windows.items():
            can_proceed, wait_time = window.can_proceed()

            if not can_proceed:
                if wait_time <= 5.0:  # Auto-wait for short delays
                    logger.info(f"Rate limit hit for {operation} ({window_name}), waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)

                    # Recheck after waiting
                    can_proceed, _ = window.can_proceed()
                    if not can_proceed:
                        metrics.increment(f"rate_limit_rejected_{operation}")
                        return False
                else:
                    # Long wait time, reject immediately
                    metrics.increment(f"rate_limit_rejected_{operation}")
                    logger.warning(
                        f"Rate limit exceeded for {operation} ({window_name}), " f"would need to wait {wait_time:.1f}s"
                    )
                    return False

        # All windows allow the request, record it
        for window in windows.values():
            window.add_request()

        metrics.increment(f"rate_limit_allowed_{operation}")
        return True

    async def execute_with_limit(self, operation: str, func, *args, **kwargs):
        """
        Execute a function with rate limiting and concurrency control.

        Args:
            operation: Name of the operation
            func: Function to execute (can be sync or async)
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If rate limit is exceeded or function fails
        """
        # Acquire rate limit permission
        if not await self.acquire(operation):
            raise Exception(f"Rate limit exceeded for operation: {operation}")

        # Acquire concurrency semaphore
        semaphore = self.semaphores[operation]

        async with semaphore:
            try:
                start_time = time.time()

                # Execute function (handle both sync and async)
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                execution_time = time.time() - start_time

                metrics.record_histogram(f"rate_limit_execution_time_{operation}", execution_time)
                metrics.increment(f"rate_limit_completed_{operation}")

                return result

            except Exception as e:
                metrics.increment(f"rate_limit_failed_{operation}")
                logger.error(f"Operation {operation} failed: {e}")
                raise

    def get_status(self, operation: Optional[str] = None) -> Dict[str, any]:
        """
        Get current rate limiter status.

        Args:
            operation: Specific operation to check (None for all)

        Returns:
            Status information
        """
        if operation:
            # Single operation status
            if operation not in self.windows:
                return {"error": f"Operation {operation} not found"}

            windows = self.windows[operation]
            limits = self._get_operation_limits(operation)
            semaphore = self.semaphores[operation]

            return {
                "operation": operation,
                "limits": {
                    "requests_per_second": limits.max_requests_per_second,
                    "requests_per_minute": limits.max_requests_per_minute,
                    "requests_per_hour": limits.max_requests_per_hour,
                    "max_concurrent": limits.max_concurrent,
                },
                "current_usage": {
                    "second": len(windows["second"].requests),
                    "minute": len(windows["minute"].requests),
                    "hour": len(windows["hour"].requests),
                    "concurrent": limits.max_concurrent - semaphore._value,
                },
                "current_rates": {
                    "second": windows["second"].current_rate,
                    "minute": windows["minute"].current_rate,
                    "hour": windows["hour"].current_rate,
                },
            }
        else:
            # All operations status
            status = {"operations": {}}

            for op in self.operation_limits.keys():
                status["operations"][op] = self.get_status(op)

            return status

    async def wait_for_capacity(
        self,
        operation: str,
        max_wait_seconds: float = 60.0,
    ) -> bool:
        """
        Wait for rate limit capacity to become available.

        Args:
            operation: Operation to wait for,
            max_wait_seconds: Maximum time to wait

        Returns:
            True if capacity became available, False if timeout
        """
        start_time = time.time()
        wait_interval = 0.1

        while time.time() - start_time < max_wait_seconds:
            if await self.acquire(operation):
                return True

            await asyncio.sleep(wait_interval)
            wait_interval = min(wait_interval * 1.2, 5.0)  # Exponential backoff

        return False

    def reset_operation(self, operation: str) -> None:
        """Reset rate limiting state for an operation."""
        if operation in self.windows:
            for window in self.windows[operation].values():
                window.requests.clear()

            logger.info(f"Reset rate limiting state for {operation}")

    def reset_all(self) -> None:
        """Reset all rate limiting state."""
        for operation in self.windows:
            self.reset_operation(operation)

        logger.info("Reset all rate limiting state")
