"""Generic error handling and reporting toolkit.

Provides reusable components for building robust error management:
- Base exception classes with enhanced resilience patterns
- Error reporting patterns
- Recovery mechanisms
- Metrics collection

This package contains NO business logic - it's a generic toolkit
that can be used to build error handling for any system.
"""

from hive_logging import get_logger

from .base_exceptions import (
    APIError,
    AsyncTimeoutError,
    BaseError,
    CircuitBreakerOpenError,
    ConfigurationError,
    ConnectionError,
    PoolExhaustedError,
    RateLimitError,
    ResourceError,
    RetryExhaustedError,
    TimeoutError,
    ValidationError,
)
from .error_reporter import BaseErrorReporter
from .monitoring_error_reporter import (
    ErrorContext,
    ErrorStats,
    MonitoringErrorReporter,
    UnifiedErrorReporter,
    create_error_context,
    error_context,
    handle_async_errors,
)
from .recovery import RecoveryStatus, RecoveryStrategy, RetryStrategy

# Legacy imports for backward compatibility (DEPRECATED - use UnifiedErrorReporter)
try:
    from .async_error_handler import AsyncErrorHandler
except ImportError:
    # AsyncErrorHandler functionality is now in MonitoringErrorReporter/UnifiedErrorReporter
    AsyncErrorHandler = UnifiedErrorReporter  # type: ignore

logger = get_logger(__name__)

__all__ = [
    "APIError",
    # Legacy (DEPRECATED)
    "AsyncErrorHandler",  # Use UnifiedErrorReporter instead
    "AsyncTimeoutError",
    # Base error classes
    "BaseError",
    # Error handling infrastructure (UNIFIED)
    "BaseErrorReporter",
    # Resilience pattern errors
    "CircuitBreakerOpenError",
    "ConfigurationError",
    "ConnectionError",
    # Async error handling context (unified in MonitoringErrorReporter)
    "ErrorContext",
    "ErrorStats",
    "MonitoringErrorReporter",  # Alias to UnifiedErrorReporter
    "PoolExhaustedError",
    "RateLimitError",
    "RecoveryStatus",
    "RecoveryStrategy",
    "ResourceError",
    "RetryExhaustedError",
    "RetryStrategy",
    "TimeoutError",
    "UnifiedErrorReporter",  # Primary interface - use this
    "ValidationError",
    "create_error_context",
    "error_context",
    "handle_async_errors",
]
