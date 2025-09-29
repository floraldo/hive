from hive_errors import BaseError
from hive_logging import get_logger

logger = get_logger(__name__)


"""Cache-specific exceptions for Hive Cache package."""


class CacheError(Exception):
    """Base exception for all cache-related errors."""

    def __init__(self, message: str, operation: str = None, key: str = None) -> None:
        super().__init__(message)
        self.operation = operation
        self.key = key


class CacheConnectionError(BaseError):
    """Raised when Redis connection fails."""

    pass


class CacheTimeoutError(BaseError):
    """Raised when cache operation times out."""

    pass


class CacheCircuitBreakerError(BaseError):
    """Raised when circuit breaker is open."""

    pass


class CacheSerializationError(BaseError):
    """Raised when serialization/deserialization fails."""

    pass


class CacheKeyError(BaseError):
    """Raised when cache key is invalid or not found."""

    pass


class CacheConfigurationError(BaseError):
    """Raised when cache configuration is invalid."""

    pass
