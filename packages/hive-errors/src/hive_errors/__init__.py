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

from .base_exceptions import (
    BaseError,
    ConfigurationError,
    ConnectionError,
    ValidationError,
    TimeoutError,
    ResourceError,
    CircuitBreakerOpenError,
    AsyncTimeoutError,
    RetryExhaustedError,
    PoolExhaustedError,
)
from .error_reporter import BaseErrorReporter
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
    "RecoveryStrategy",
    "RecoveryStatus",
]