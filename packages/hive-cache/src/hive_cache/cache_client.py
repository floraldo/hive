"""Core Redis cache client with async operations and circuit breaker."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union, AsyncGenerator, Callable
import time
import json
import gzip
from datetime import datetime, timedelta

import aioredis
import msgpack
import xxhash
from async_timeout import timeout as async_timeout
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import CacheConfig
from .exceptions import (
    CacheError,
    CacheConnectionError,
    CacheTimeoutError,
    CacheCircuitBreakerError,
    CacheSerializationError,
    CacheKeyError,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker for cache operations."""

    def __init__(self, threshold: int = 5, timeout: float = 60.0, recovery_timeout: float = 30.0):
        self.threshold = threshold
        self.timeout = timeout
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                return False
            return True
        return False

    def record_success(self):
        """Record successful operation."""
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


class HiveCacheClient:
    """
    High-performance async Redis cache client with circuit breaker protection.

    Features:
    - Async Redis operations with connection pooling
    - Circuit breaker for resilience
    - Intelligent serialization (MessagePack, JSON, binary)
    - Compression for large payloads
    - TTL management with smart defaults
    - Key namespacing and pattern operations
    - Health monitoring and metrics
    """

    def __init__(self, config: CacheConfig):
        self.config = config
        self._redis_pool = None
        self._circuit_breaker = None
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
            "circuit_breaker_opens": 0,
        }
        self._last_health_check = None
        self._health_status = {"healthy": True, "last_check": None, "errors": []}

        if config.circuit_breaker_enabled:
            self._circuit_breaker = CircuitBreaker(
                threshold=config.circuit_breaker_threshold,
                timeout=config.circuit_breaker_timeout,
                recovery_timeout=config.circuit_breaker_recovery_timeout,
            )

    async def initialize(self) -> None:
        """Initialize Redis connection pool."""
        try:
            # Parse Redis URL and create connection pool
            self._redis_pool = aioredis.ConnectionPool.from_url(
                self.config.redis_url,
                **self.config.get_redis_connection_kwargs(),
            )

            # Test connection
            async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                await redis.ping()

            logger.info("Hive Cache client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize cache client: {e}")
            raise CacheConnectionError(f"Failed to connect to Redis: {e}")

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._redis_pool:
            await self._redis_pool.disconnect()
            logger.info("Hive Cache client closed")

    def _check_circuit_breaker(self) -> None:
        """Check circuit breaker state."""
        if self._circuit_breaker and self._circuit_breaker.is_open():
            self._metrics["circuit_breaker_opens"] += 1
            raise CacheCircuitBreakerError("Circuit breaker is open")

    async def _execute_with_circuit_breaker(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation with circuit breaker protection."""
        self._check_circuit_breaker()

        try:
            async with async_timeout(self.config.response_timeout):
                result = await operation(*args, **kwargs)

            if self._circuit_breaker:
                self._circuit_breaker.record_success()

            return result

        except asyncio.TimeoutError:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()
            self._metrics["errors"] += 1
            raise CacheTimeoutError("Cache operation timed out")

        except Exception as e:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()
            self._metrics["errors"] += 1
            raise CacheConnectionError(f"Cache operation failed: {e}")

    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value using configured format."""
        try:
            if self.config.serialization_format == "msgpack":
                serialized = msgpack.packb(value, use_bin_type=True)
            elif self.config.serialization_format == "json":
                serialized = json.dumps(value, default=str).encode("utf-8")
            else:
                import pickle
                serialized = pickle.dumps(value)

            # Apply compression if enabled and value is large enough
            if (
                self.config.compression_enabled
                and len(serialized) > self.config.compression_threshold
            ):
                compressed = gzip.compress(serialized, compresslevel=self.config.compression_level)
                # Add compression marker
                return b"GZIP:" + compressed

            return serialized

        except Exception as e:
            raise CacheSerializationError(f"Failed to serialize value: {e}")

    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from bytes."""
        try:
            # Check for compression marker
            if data.startswith(b"GZIP:"):
                data = gzip.decompress(data[5:])

            if self.config.serialization_format == "msgpack":
                return msgpack.unpackb(data, raw=False)
            elif self.config.serialization_format == "json":
                return json.loads(data.decode("utf-8"))
            else:
                import pickle
                return pickle.loads(data)

        except Exception as e:
            # Try JSON fallback if enabled
            if self.config.enable_json_fallback and self.config.serialization_format != "json":
                try:
                    return json.loads(data.decode("utf-8"))
                except:
                    pass

            raise CacheSerializationError(f"Failed to deserialize value: {e}")

    def _generate_key_hash(self, key: str) -> str:
        """Generate consistent hash for cache key."""
        return xxhash.xxh64(key.encode()).hexdigest()

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "default",
        overwrite: bool = True,
    ) -> bool:
        """Set a value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            namespace: Cache namespace
            overwrite: Whether to overwrite existing key

        Returns:
            True if value was set successfully
        """
        try:
            # Generate namespaced key
            cache_key = self.config.get_namespaced_key(namespace, key)

            # Use namespace-specific TTL if not provided
            if ttl is None:
                ttl = self.config.get_ttl_for_namespace(namespace)

            # Clamp TTL to configured limits
            ttl = max(self.config.min_ttl, min(ttl, self.config.max_ttl))

            # Serialize value
            serialized_value = self._serialize_value(value)

            # Execute Redis operation
            async def _set_operation():
                async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                    if overwrite:
                        return await redis.setex(cache_key, ttl, serialized_value)
                    else:
                        return await redis.set(cache_key, serialized_value, ex=ttl, nx=True)

            result = await self._execute_with_circuit_breaker(_set_operation)
            self._metrics["sets"] += 1

            return bool(result)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to set cache key: {e}", operation="set", key=key)

    async def get(self, key: str, namespace: str = "default", default: Any = None) -> Any:
        """Get a value from cache.

        Args:
            key: Cache key
            namespace: Cache namespace
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        try:
            # Generate namespaced key
            cache_key = self.config.get_namespaced_key(namespace, key)

            # Execute Redis operation
            async def _get_operation():
                async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                    return await redis.get(cache_key)

            result = await self._execute_with_circuit_breaker(_get_operation)

            if result is None:
                self._metrics["misses"] += 1
                return default

            # Deserialize value
            value = self._deserialize_value(result)
            self._metrics["hits"] += 1
            return value

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to get cache key: {e}", operation="get", key=key)

    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl: Optional[int] = None,
        namespace: str = "default",
        *args,
        **kwargs,
    ) -> Any:
        """Get value from cache or compute and set if missing.

        Args:
            key: Cache key
            factory: Function to compute value if missing
            ttl: Time to live in seconds
            namespace: Cache namespace
            *args: Arguments for factory function
            **kwargs: Keyword arguments for factory function

        Returns:
            Cached or computed value
        """
        # Try to get from cache first
        value = await self.get(key, namespace)

        if value is not None:
            return value

        # Compute value using factory
        if asyncio.iscoroutinefunction(factory):
            computed_value = await factory(*args, **kwargs)
        else:
            computed_value = factory(*args, **kwargs)

        # Set in cache
        await self.set(key, computed_value, ttl, namespace)

        return computed_value

    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a key from cache.

        Args:
            key: Cache key
            namespace: Cache namespace

        Returns:
            True if key was deleted
        """
        try:
            # Generate namespaced key
            cache_key = self.config.get_namespaced_key(namespace, key)

            # Execute Redis operation
            async def _delete_operation():
                async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                    return await redis.delete(cache_key)

            result = await self._execute_with_circuit_breaker(_delete_operation)
            self._metrics["deletes"] += 1

            return bool(result)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to delete cache key: {e}", operation="delete", key=key)

    async def delete_pattern(self, pattern: str, namespace: str = "default") -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern: Key pattern (supports * wildcards)
            namespace: Cache namespace

        Returns:
            Number of keys deleted
        """
        try:
            # Generate namespaced pattern
            cache_pattern = self.config.get_namespaced_key(namespace, pattern)

            # Execute Redis operation
            async def _delete_pattern_operation():
                async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                    keys = await redis.keys(cache_pattern)
                    if keys:
                        return await redis.delete(*keys)
                    return 0

            result = await self._execute_with_circuit_breaker(_delete_pattern_operation)
            self._metrics["deletes"] += result

            return result

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to delete pattern: {e}", operation="delete_pattern", key=pattern)

    async def exists(self, key: str, namespace: str = "default") -> bool:
        """Check if a key exists in cache.

        Args:
            key: Cache key
            namespace: Cache namespace

        Returns:
            True if key exists
        """
        try:
            # Generate namespaced key
            cache_key = self.config.get_namespaced_key(namespace, key)

            # Execute Redis operation
            async def _exists_operation():
                async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                    return await redis.exists(cache_key)

            result = await self._execute_with_circuit_breaker(_exists_operation)
            return bool(result)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to check key existence: {e}", operation="exists", key=key)

    async def ttl(self, key: str, namespace: str = "default") -> int:
        """Get time to live for a key.

        Args:
            key: Cache key
            namespace: Cache namespace

        Returns:
            TTL in seconds (-1 if no expiry, -2 if key doesn't exist)
        """
        try:
            # Generate namespaced key
            cache_key = self.config.get_namespaced_key(namespace, key)

            # Execute Redis operation
            async def _ttl_operation():
                async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                    return await redis.ttl(cache_key)

            return await self._execute_with_circuit_breaker(_ttl_operation)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to get TTL: {e}", operation="ttl", key=key)

    async def extend_ttl(self, key: str, ttl: int, namespace: str = "default") -> bool:
        """Extend TTL for an existing key.

        Args:
            key: Cache key
            ttl: New TTL in seconds
            namespace: Cache namespace

        Returns:
            True if TTL was updated
        """
        try:
            # Generate namespaced key
            cache_key = self.config.get_namespaced_key(namespace, key)

            # Execute Redis operation
            async def _expire_operation():
                async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                    return await redis.expire(cache_key, ttl)

            result = await self._execute_with_circuit_breaker(_expire_operation)
            return bool(result)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to extend TTL: {e}", operation="extend_ttl", key=key)

    async def scan_keys(
        self, pattern: str = "*", namespace: str = "default", count: int = 10
    ) -> AsyncGenerator[str, None]:
        """Scan keys matching a pattern.

        Args:
            pattern: Key pattern
            namespace: Cache namespace
            count: Number of keys to return per iteration

        Yields:
            Matching keys (without namespace prefix)
        """
        try:
            # Generate namespaced pattern
            cache_pattern = self.config.get_namespaced_key(namespace, pattern)
            namespace_prefix = self.config.get_namespaced_key(namespace, "")

            async def _scan_operation():
                async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                    async for key in redis.scan_iter(match=cache_pattern, count=count):
                        # Remove namespace prefix
                        if key.startswith(namespace_prefix):
                            yield key[len(namespace_prefix) :]
                        else:
                            yield key

            async for key in self._execute_with_circuit_breaker(_scan_operation):
                yield key

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to scan keys: {e}", operation="scan", key=pattern)

    async def mget(self, keys: List[str], namespace: str = "default") -> Dict[str, Any]:
        """Get multiple values from cache.

        Args:
            keys: List of cache keys
            namespace: Cache namespace

        Returns:
            Dictionary of key-value pairs (missing keys omitted)
        """
        try:
            # Generate namespaced keys
            cache_keys = [self.config.get_namespaced_key(namespace, key) for key in keys]

            # Execute Redis operation
            async def _mget_operation():
                async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                    return await redis.mget(cache_keys)

            results = await self._execute_with_circuit_breaker(_mget_operation)

            # Build result dictionary
            result_dict = {}
            for i, (original_key, value) in enumerate(zip(keys, results)):
                if value is not None:
                    try:
                        result_dict[original_key] = self._deserialize_value(value)
                        self._metrics["hits"] += 1
                    except CacheSerializationError:
                        logger.warning(f"Failed to deserialize value for key: {original_key}")
                        self._metrics["misses"] += 1
                else:
                    self._metrics["misses"] += 1

            return result_dict

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to get multiple keys: {e}", operation="mget")

    async def mset(
        self, mapping: Dict[str, Any], ttl: Optional[int] = None, namespace: str = "default"
    ) -> bool:
        """Set multiple values in cache.

        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time to live in seconds
            namespace: Cache namespace

        Returns:
            True if all values were set
        """
        try:
            # Use namespace-specific TTL if not provided
            if ttl is None:
                ttl = self.config.get_ttl_for_namespace(namespace)

            # Execute Redis operation
            async def _mset_operation():
                async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                    pipe = redis.pipeline()

                    for key, value in mapping.items():
                        cache_key = self.config.get_namespaced_key(namespace, key)
                        serialized_value = self._serialize_value(value)
                        pipe.setex(cache_key, ttl, serialized_value)

                    return await pipe.execute()

            results = await self._execute_with_circuit_breaker(_mset_operation)
            self._metrics["sets"] += len(mapping)

            return all(results)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to set multiple keys: {e}", operation="mset")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on cache.

        Returns:
            Health status dictionary
        """
        try:
            start_time = time.time()

            # Test basic operations
            async with aioredis.Redis(connection_pool=self._redis_pool) as redis:
                # Test ping
                ping_result = await redis.ping()

                # Test set/get
                test_key = f"health_check_{int(time.time())}"
                await redis.setex(test_key, 30, "test_value")
                get_result = await redis.get(test_key)
                await redis.delete(test_key)

            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            self._health_status = {
                "healthy": True,
                "last_check": datetime.utcnow().isoformat(),
                "response_time_ms": round(response_time, 2),
                "ping_result": ping_result,
                "set_get_test": get_result == b"test_value",
                "circuit_breaker_state": self._circuit_breaker.state if self._circuit_breaker else "disabled",
                "errors": [],
            }

            self._last_health_check = time.time()
            return self._health_status

        except Exception as e:
            self._health_status = {
                "healthy": False,
                "last_check": datetime.utcnow().isoformat(),
                "errors": [str(e)],
                "circuit_breaker_state": self._circuit_breaker.state if self._circuit_breaker else "disabled",
            }
            return self._health_status

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache operation metrics.

        Returns:
            Metrics dictionary
        """
        total_operations = self._metrics["hits"] + self._metrics["misses"]
        hit_rate = (self._metrics["hits"] / total_operations * 100) if total_operations > 0 else 0

        return {
            **self._metrics,
            "hit_rate_percent": round(hit_rate, 2),
            "total_operations": total_operations,
            "circuit_breaker_state": self._circuit_breaker.state if self._circuit_breaker else "disabled",
            "last_health_check": self._last_health_check,
        }

    def reset_metrics(self) -> None:
        """Reset all metrics counters."""
        self._metrics = {key: 0 for key in self._metrics}


# Global cache client instance
_global_cache_client: Optional[HiveCacheClient] = None


async def get_cache_client(config: Optional[CacheConfig] = None) -> HiveCacheClient:
    """Get or create global cache client instance.

    Args:
        config: Optional cache configuration (uses environment if None)

    Returns:
        HiveCacheClient instance
    """
    global _global_cache_client

    if _global_cache_client is None:
        if config is None:
            config = CacheConfig.from_env()

        _global_cache_client = HiveCacheClient(config)
        await _global_cache_client.initialize()

    return _global_cache_client


async def close_cache_client() -> None:
    """Close global cache client."""
    global _global_cache_client

    if _global_cache_client:
        await _global_cache_client.close()
        _global_cache_client = None