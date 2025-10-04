from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Generic base exception classes with enhanced resilience patterns.

These are pure, business-logic-free exception patterns that can be used
to build robust error handling for any system.
"""

from typing import Any


class BaseError(Exception):
    """Generic base exception for any system.

    Contains only the minimal, universal properties that any system error needs:
    - Error message
    - Component identification
    - Operation context
    - Additional details
    - Recovery suggestions
    """

    def __init__(
        self,
        message: str,
        component: str = "unknown",
        operation: str | None = None,
        details: dict[str, Any] | None = None,
        recovery_suggestions: list[str] | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.component = component
        self.operation = operation
        self.details = details or {}
        self.recovery_suggestions = recovery_suggestions or []
        self.original_error = original_error

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for serialization"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "component": self.component,
            "operation": self.operation,
            "details": self.details,
            "recovery_suggestions": self.recovery_suggestions,
            "original_error": str(self.original_error) if self.original_error else None,
        }


class ConfigurationError(BaseError):
    """Generic configuration-related error"""



class ConnectionError(BaseError):
    """Generic connection-related error"""



class ValidationError(BaseError):
    """Generic validation-related error"""



class TimeoutError(BaseError):
    """Generic timeout-related error"""



class ResourceError(BaseError):
    """Generic resource-related error (memory, disk, etc.)"""



class CircuitBreakerOpenError(BaseError):
    """Error raised when circuit breaker is open and preventing operation execution.

    This error indicates that the circuit breaker has detected too many failures
    and is preventing further operations to allow the system to recover.
    """

    def __init__(
        self,
        message: str = "Circuit breaker is open - operation blocked",
        component: str = "circuit_breaker",
        operation: str | None = None,
        failure_count: int | None = None,
        recovery_time: float | None = None,
        **kwargs,
    ):
        super().__init__(message, component, operation, **kwargs)
        self.failure_count = failure_count
        self.recovery_time = recovery_time

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary with circuit breaker details"""
        result = super().to_dict()
        result.update({"failure_count": self.failure_count, "recovery_time": self.recovery_time})
        return result


class AsyncTimeoutError(BaseError):
    """Enhanced timeout error for async operations with additional context.

    Extends the standard asyncio.TimeoutError to provide more detailed
    information about the timeout context and recovery suggestions.
    """

    def __init__(
        self,
        message: str = "Async operation timed out",
        component: str = "async_timeout",
        operation: str | None = None,
        timeout_duration: float | None = None,
        elapsed_time: float | None = None,
        **kwargs,
    ):
        super().__init__(message, component, operation, **kwargs)
        self.timeout_duration = timeout_duration
        self.elapsed_time = elapsed_time

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary with timeout details"""
        result = super().to_dict()
        result.update({"timeout_duration": self.timeout_duration, "elapsed_time": self.elapsed_time})
        return result


class RetryExhaustedError(BaseError):
    """Error raised when all retry attempts have been exhausted.

    Provides detailed information about the retry attempts and
    the original error that caused the retries to fail.
    """

    def __init__(
        self,
        message: str = "All retry attempts exhausted",
        component: str = "retry_mechanism",
        operation: str | None = None,
        max_attempts: int | None = None,
        attempt_count: int | None = None,
        last_error: Exception | None = None,
        **kwargs,
    ):
        super().__init__(message, component, operation, original_error=last_error, **kwargs)
        self.max_attempts = max_attempts
        self.attempt_count = attempt_count
        self.last_error = last_error

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary with retry details"""
        result = super().to_dict()
        result.update(
            {
                "max_attempts": self.max_attempts,
                "attempt_count": self.attempt_count,
                "last_error": str(self.last_error) if self.last_error else None,
            },
        )
        return result


class PoolExhaustedError(BaseError):
    """Error raised when connection or resource pool is exhausted.

    This error indicates that all connections/resources in a pool
    are currently in use and no new ones can be created.
    """

    def __init__(
        self,
        message: str = "Resource pool exhausted",
        component: str = "connection_pool",
        operation: str | None = None,
        pool_size: int | None = None,
        active_connections: int | None = None,
        **kwargs,
    ):
        super().__init__(message, component, operation, **kwargs)
        self.pool_size = pool_size
        self.active_connections = active_connections

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary with pool details"""
        result = super().to_dict()
        result.update({"pool_size": self.pool_size, "active_connections": self.active_connections})
        return result


class APIError(BaseError):
    """Generic API-related error.

    Raised when external API calls fail or return errors.
    """



class RateLimitError(BaseError):
    """Rate limit exceeded error.

    Raised when API rate limits are exceeded.
    """

