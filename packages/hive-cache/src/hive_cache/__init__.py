"""
Hive Cache - High-performance Redis-based caching for Hive platform.

This package provides intelligent caching solutions optimized for:
- Claude API response caching with smart TTL
- Performance-critical computations
- I/O operation optimization
- Circuit breaker patterns for resilience
"""

from .cache_client import HiveCacheClient, get_cache_client
from .config import CacheConfig
from .claude_cache import ClaudeAPICache
from .performance_cache import PerformanceCache
from .health import CacheHealthMonitor
from .exceptions import (
    CacheError,
    CacheConnectionError,
    CacheTimeoutError,
    CacheCircuitBreakerError,
    CacheSerializationError,
)

__version__ = "1.0.0"
__all__ = [
    "HiveCacheClient",
    "get_cache_client",
    "CacheConfig",
    "ClaudeAPICache",
    "PerformanceCache",
    "CacheHealthMonitor",
    "CacheError",
    "CacheConnectionError",
    "CacheTimeoutError",
    "CacheCircuitBreakerError",
    "CacheSerializationError",
]