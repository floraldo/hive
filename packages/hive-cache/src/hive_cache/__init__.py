from hive_logging import get_logger

logger = get_logger(__name__)

"""
Hive Cache - High-performance Redis-based caching for Hive platform.

This package provides intelligent caching solutions optimized for:
- Claude API response caching with smart TTL
- Performance-critical computations
- I/O operation optimization
- Circuit breaker patterns for resilience
"""

from .cache_client import HiveCacheClient, get_cache_client
from .claude_cache import ClaudeAPICache
from .config import CacheConfig
from .exceptions import (
    CacheCircuitBreakerError,
    CacheConnectionError,
    CacheError,
    CacheSerializationError,
    CacheTimeoutError,
)
from .health import CacheHealthMonitor
from .performance_cache import PerformanceCache

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
