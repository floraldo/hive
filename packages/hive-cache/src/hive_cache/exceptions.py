"""
Cache error handling using generic exception patterns.

DEPRECATED: Cache-specific exception classes removed in Project Essence Phase 2.
Use generic exceptions from hive_errors with component tagging instead.

Migration Guide:
- CacheConnectionError → ConnectionError(component="cache")
- CacheTimeoutError → TimeoutError(component="cache")
- CacheCircuitBreakerError → CircuitBreakerOpenError(component="cache")
- CacheSerializationError → ValidationError(component="cache", operation="serialization")
- CacheKeyError → ValidationError(component="cache", operation="key_validation")
- CacheConfigurationError → ConfigurationError(component="cache")

This consolidation reduces exception class count from 50+ to <10 platform-wide.
"""

from hive_errors import (
    BaseError,
    CircuitBreakerOpenError,
    ConfigurationError,
    ConnectionError,
    TimeoutError,
    ValidationError,
)
from hive_logging import get_logger

logger = get_logger(__name__)

# Re-export generic exceptions for backward compatibility
# These will be removed in a future version
CacheError = BaseError
CacheConnectionError = ConnectionError
CacheTimeoutError = TimeoutError
CacheCircuitBreakerError = CircuitBreakerOpenError
CacheSerializationError = ValidationError
CacheKeyError = ValidationError
CacheConfigurationError = ConfigurationError

__all__ = [
    "BaseError",
    "ConnectionError",
    "TimeoutError",
    "CircuitBreakerOpenError",
    "ValidationError",
    "ConfigurationError",
    # Deprecated aliases
    "CacheError",
    "CacheConnectionError",
    "CacheTimeoutError",
    "CacheCircuitBreakerError",
    "CacheSerializationError",
    "CacheKeyError",
    "CacheConfigurationError",
]
