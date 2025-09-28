"""Cache-specific exceptions for Hive Cache package."""


class CacheError(Exception):
    """Base exception for all cache-related errors."""

    def __init__(self, message: str, operation: str = None, key: str = None):
        super().__init__(message)
        self.operation = operation
        self.key = key


class CacheConnectionError(CacheError):
    """Raised when Redis connection fails."""
    pass


class CacheTimeoutError(CacheError):
    """Raised when cache operation times out."""
    pass


class CacheCircuitBreakerError(CacheError):
    """Raised when circuit breaker is open."""
    pass


class CacheSerializationError(CacheError):
    """Raised when serialization/deserialization fails."""
    pass


class CacheKeyError(CacheError):
    """Raised when cache key is invalid or not found."""
    pass


class CacheConfigurationError(CacheError):
    """Raised when cache configuration is invalid."""
    pass