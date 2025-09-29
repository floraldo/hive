from hive_logging import get_logger

logger = get_logger(__name__)

"""
Generic error handling and reporting toolkit.

Provides reusable components for building robust error management:
- Base exception classes with enhanced resilience patterns
- Error reporting patterns
- Recovery mechanisms
- Metrics collection

This package contains NO business logic - it's a generic toolkit
that can be used to build error handling for any system.
"""

from .async_error_handler import (
    AsyncErrorHandler,
    ErrorContext,
    ErrorStats,
    create_error_context,
    error_context_async,
    handle_async_errors,
)
from .base_exceptions import (
    AsyncTimeoutError,
    BaseError,
    CircuitBreakerOpenError,
    ConfigurationError,
    ConnectionError,
    PoolExhaustedError,
    ResourceError,
    RetryExhaustedError,
    TimeoutError,
    ValidationError,
)
from .error_reporter import BaseErrorReporter
from .monitoring_error_reporter import MonitoringErrorReporter
from .recovery import RecoveryStatus, RecoveryStrategy

__all__ = [
    # Base error classes
    "BaseError",
    "ConfigurationError",
    "ConnectionError",
    "ValidationError",
    "TimeoutError",
    "ResourceError",
    # Resilience pattern errors
    "CircuitBreakerOpenError",
    "AsyncTimeoutError",
    "RetryExhaustedError",
    "PoolExhaustedError",
    # Error handling infrastructure
    "BaseErrorReporter",
    "MonitoringErrorReporter",
    "RecoveryStrategy",
    "RecoveryStatus",
    # Async error handling
    "AsyncErrorHandler",
    "ErrorContext",
    "ErrorStats",
    "error_context_async",
    "handle_async_errors",
    "create_error_context",
]
