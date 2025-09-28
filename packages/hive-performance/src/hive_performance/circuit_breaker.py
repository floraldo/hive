"""Circuit breaker pattern for external service calls"""

import time
from enum import Enum
from typing import Any, Callable, Optional
from functools import wraps
from hive_logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for fault tolerance"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and \
               time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
        return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function through circuit breaker"""
        if self.state == CircuitState.OPEN:
            raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            logger.info("Circuit breaker reset to CLOSED")

    def _on_failure(self):
        """Handle failed call"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN after {self._failure_count} failures")


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
):
    """Decorator for circuit breaker pattern"""
    breaker = CircuitBreaker(failure_threshold, recovery_timeout, expected_exception)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if breaker.state == CircuitState.OPEN:
                raise Exception("Circuit breaker is OPEN")

            try:
                result = await func(*args, **kwargs)
                breaker._on_success()
                return result
            except breaker.expected_exception as e:
                breaker._on_failure()
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper

    return decorator
