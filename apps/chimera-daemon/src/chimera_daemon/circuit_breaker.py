"""Circuit Breaker pattern for fault tolerance.

Implements circuit breaker with CLOSED/OPEN/HALF_OPEN states to prevent
cascading failures when a service or agent is failing repeatedly.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from hive_logging import get_logger
from hive_performance import counted

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Failure threshold exceeded, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration.

    Args:
        failure_threshold: Number of failures to open circuit (default: 5)
        success_threshold: Number of successes to close circuit from HALF_OPEN (default: 2)
        timeout_seconds: Time to wait before trying HALF_OPEN (default: 60)
        window_size: Number of recent calls to track for failure rate (default: 10)
    """

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 60.0
    window_size: int = 10


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    Tracks success/failure of operations and trips to OPEN state when
    failure threshold is exceeded. After timeout, enters HALF_OPEN state
    to test if the service has recovered.

    Example:
        breaker = CircuitBreaker(name="e2e_agent")

        async def protected_operation():
            async with breaker:
                result = await risky_operation()
            return result
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        """Initialize circuit breaker.

        Args:
            name: Circuit breaker name (for logging)
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.logger = logger

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None

        # Sliding window for tracking recent calls
        self._recent_calls: deque[bool] = deque(maxlen=self.config.window_size)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        self._update_state()
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (allowing requests)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    async def call(self, operation: Callable, *args, **kwargs) -> any:
        """Execute operation with circuit breaker protection.

        Args:
            operation: Async callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result from operation

        Raises:
            CircuitBreakerError: If circuit is open
        """
        self._update_state()

        if self._state == CircuitState.OPEN:
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN - blocking request"
            )

        try:
            result = await operation(*args, **kwargs)
            await self._record_success()
            return result

        except Exception:
            await self._record_failure()
            raise

    async def __aenter__(self):
        """Context manager entry."""
        self._update_state()

        if self._state == CircuitState.OPEN:
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN - blocking request"
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is None:
            # Success
            await self._record_success()
        else:
            # Failure
            await self._record_failure()

        return False  # Don't suppress exceptions

    @counted(metric_name="chimera.circuit_breaker.success")
    async def _record_success(self) -> None:
        """Record successful operation."""
        self._recent_calls.append(True)

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1

            if self._success_count >= self.config.success_threshold:
                self._transition_to_closed()

    @counted(metric_name="chimera.circuit_breaker.failure")
    async def _record_failure(self) -> None:
        """Record failed operation."""
        self._recent_calls.append(False)
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._state == CircuitState.HALF_OPEN:
            # Immediately trip back to OPEN on failure in HALF_OPEN
            self._transition_to_open()

        elif self._state == CircuitState.CLOSED:
            # Check if we should trip to OPEN
            # Only trip if we have enough data AND exceed threshold
            if self._failure_count >= self.config.failure_threshold:
                recent_failure_rate = self._calculate_failure_rate()

                # Also check failure rate if we have enough calls in window
                if (
                    len(self._recent_calls) >= self.config.window_size
                    and recent_failure_rate >= 0.5
                ):
                    self._transition_to_open()
                elif self._failure_count >= self.config.failure_threshold:
                    self._transition_to_open()

    def _calculate_failure_rate(self) -> float:
        """Calculate failure rate from recent calls.

        Returns:
            Failure rate (0.0 to 1.0)
        """
        if not self._recent_calls:
            return 0.0

        failures = sum(1 for success in self._recent_calls if not success)
        return failures / len(self._recent_calls)

    def _update_state(self) -> None:
        """Update circuit state based on timeout."""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            time_since_failure = datetime.now() - self._last_failure_time

            if time_since_failure >= timedelta(seconds=self.config.timeout_seconds):
                self._transition_to_half_open()

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self.logger.info(f"Circuit breaker '{self.name}' → CLOSED")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self.logger.warning(
            f"Circuit breaker '{self.name}' → OPEN "
            f"(failures: {self._failure_count}, "
            f"failure_rate: {self._calculate_failure_rate():.1%})"
        )
        self._state = CircuitState.OPEN
        self._success_count = 0

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self.logger.info(
            f"Circuit breaker '{self.name}' → HALF_OPEN (testing recovery)"
        )
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._failure_count = 0

    def get_metrics(self) -> dict[str, any]:
        """Get circuit breaker metrics.

        Returns:
            Dictionary with current state and statistics
        """
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_rate": self._calculate_failure_rate(),
            "recent_calls": len(self._recent_calls),
        }


__all__ = ["CircuitBreaker", "CircuitBreakerConfig", "CircuitState", "CircuitBreakerError"]
