"""Core Redis cache client with async operations and circuit breaker."""

import asyncio
import gzip
import json
import time
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union

import msgpack
import orjson
import redis.asyncio as redis
import xxhash
from async_timeout import timeout as async_timeout
from hive_async.resilience import AsyncCircuitBreaker
from hive_logging import get_logger
from hive_performance.metrics_collector import MetricsCollector
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import CacheConfig
from .exceptions import (
    CacheCircuitBreakerError,
    CacheConnectionError,
    CacheError,
    CacheKeyError,
    CacheSerializationError,
    CacheTimeoutError,
)

logger = get_logger(__name__)


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

    def __init__(self, config: CacheConfig) -> None:
        self.config = config
        self._redis_pool = None
        self._redis_client = None
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

        # Performance monitoring
        self._performance_monitor = (
            MetricsCollector(
                collection_interval=self.config.performance_monitor_interval
                if hasattr(self.config, "performance_monitor_interval")
                else 5.0,
                max_history=1000,
                enable_system_metrics=True,
                enable_async_metrics=True,
            )
            if config.enable_performance_monitoring
            else None
        )

        if config.circuit_breaker_enabled:
            self._circuit_breaker = AsyncCircuitBreaker(
                failure_threshold=config.circuit_breaker_threshold,
                recovery_timeout=config.circuit_breaker_timeout,
            )

    async def initialize_async(self) -> None:
        """Initialize Redis connection pool and client."""
        try:
            # Parse Redis URL and create connection pool
            self._redis_pool = redis.ConnectionPool.from_url(
                self.config.redis_url,
                **self.config.get_redis_connection_kwargs(),
            )

            # Create reusable Redis client
            self._redis_client = redis.Redis(connection_pool=self._redis_pool)

            # Test connection
            await self._redis_client.ping()

            # Start performance monitoring if enabled
            if self._performance_monitor:
                await self._performance_monitor.start_collection_async()
                logger.info("Performance monitoring started for cache operations")

            logger.info("Hive Cache client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize_async cache client: {e}")
            raise CacheConnectionError(f"Failed to connect to Redis: {e}")

    async def close_async(self) -> None:
        """Close Redis connection pool and client."""
        # Stop performance monitoring if enabled
        if self._performance_monitor:
            await self._performance_monitor.stop_collection_async()
            logger.info("Performance monitoring stopped")

        if self._redis_client:
            await self._redis_client.close()
        if self._redis_pool:
            await self._redis_pool.disconnect()
        logger.info("Hive Cache client closed")

    async def _track_performance_async(self, operation_name: str, operation_func, *args, **kwargs):
        """Track performance metrics for cache operations."""
        if not self._performance_monitor:
            return await operation_func(*args, **kwargs)

        # Start tracking
        start_id = await self._performance_monitor.start_operation_tracking_async(
            operation_name=operation_name,
            tags={"cache_operation": operation_name, "namespace": kwargs.get("namespace", "default")},
        )

        try:
            result = await operation_func(*args, **kwargs)
            # Calculate bytes processed for cache operations
            bytes_processed = 0
            if hasattr(result, "__len__") and result is not None:
                bytes_processed = len(str(result).encode("utf-8"))
            elif isinstance(result, (bytes, bytearray)):
                bytes_processed = len(result)

            await self._performance_monitor.end_operation_tracking_async(
                start_id, success=True, bytes_processed=bytes_processed
            )
            return result
        except Exception as e:
            await self._performance_monitor.end_operation_tracking_async(start_id, success=False)
            raise

    def _check_circuit_breaker(self) -> None:
        """Check circuit breaker state."""
        if self._circuit_breaker and self._circuit_breaker.is_open:
            self._metrics["circuit_breaker_opens"] += 1
            raise CacheCircuitBreakerError("Circuit breaker is open")

    async def _execute_with_circuit_breaker_async(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation with circuit breaker protection."""
        self._check_circuit_breaker()

        try:
            async with async_timeout(self.config.response_timeout):
                result = await operation(*args, **kwargs)

            # Circuit breaker success is handled automatically by AsyncCircuitBreaker

            return result

        except asyncio.TimeoutError:
            # Circuit breaker failure is handled automatically by AsyncCircuitBreaker
            self._metrics["errors"] += 1
            raise CacheTimeoutError("Cache operation timed out")

        except Exception as e:
            # Circuit breaker failure is handled automatically by AsyncCircuitBreaker
            self._metrics["errors"] += 1
            raise CacheConnectionError(f"Cache operation failed: {e}")

    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value using configured format."""
        try:
            if self.config.serialization_format == "msgpack":
                serialized = msgpack.packb(value, use_bin_type=True)
            elif self.config.serialization_format == "orjson":
                serialized = orjson.dumps(value, default=str)
            elif self.config.serialization_format == "json":
                serialized = json.dumps(value, default=str).encode("utf-8")
            else:
                # Default to orjson for best performance
                serialized = orjson.dumps(value, default=str)

            # Apply compression if enabled and value is large enough
            if self.config.compression_enabled and len(serialized) > self.config.compression_threshold:
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
            elif self.config.serialization_format == "orjson":
                return orjson.loads(data)
            elif self.config.serialization_format == "json":
                return json.loads(data.decode("utf-8"))
            else:
                # Default to orjson for best performance
                return orjson.loads(data)

        except Exception as e:
            # Try JSON fallback if enabled
            if self.config.enable_json_fallback and self.config.serialization_format != "json":
                try:
                    return json.loads(data.decode("utf-8"))
                except Exception as e:
                    logger.warning(f"JSON fallback deserialization failed: {e}")
                    pass

            raise CacheSerializationError(f"Failed to deserialize value: {e}")

    def _generate_key_hash(self, key: str) -> str:
        """Generate consistent hash for cache key."""
        return xxhash.xxh64(key.encode()).hexdigest()

    async def set_async(
        self,
        key: str,
        value: Any,
        ttl_async: Optional[int] = None,
        namespace: str = "default",
        overwrite: bool = True,
    ) -> bool:
        """Set a value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_async: Time to live in seconds (uses default if None)
            namespace: Cache namespace
            overwrite: Whether to overwrite existing key

        Returns:
            True if value was set_async successfully
        """

        async def _set_implementation():
            # Generate namespaced key
            cache_key = self.config.get_namespaced_key(namespace, key)

            # Use namespace-specific TTL if not provided
            if ttl_async is None:
                ttl_async = self.config.get_ttl_for_namespace(namespace)

            # Clamp TTL to configured limits
            ttl_async = max(self.config.min_ttl, min(ttl_async, self.config.max_ttl))

            # Serialize value
            serialized_value = self._serialize_value(value)

            # Execute Redis operation
            async def _set_operation_async():
                if overwrite:
                    return await self._redis_client.setex(cache_key, ttl_async, serialized_value)
                else:
                    return await self._redis_client.set(cache_key, serialized_value, ex=ttl_async, nx=True)

            result = await self._execute_with_circuit_breaker_async(_set_operation_async)
            self._metrics["sets"] += 1

            return bool(result)

        try:
            return await self._track_performance_async("cache_set", _set_implementation, namespace=namespace)
        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to set_async cache key: {e}", operation="set_async", key=key)

    async def get_async(self, key: str, namespace: str = "default", default: Any = None) -> Any:
        """Get a value from cache.

        Args:
            key: Cache key
            namespace: Cache namespace
            default: Default value if key not found

        Returns:
            Cached value or default
        """

        async def _get_implementation():
            # Generate namespaced key
            cache_key = self.config.get_namespaced_key(namespace, key)

            # Execute Redis operation
            async def _get_operation_async():
                return await self._redis_client.get(cache_key)

            result = await self._execute_with_circuit_breaker_async(_get_operation_async)

            if result is None:
                self._metrics["misses"] += 1
                return default

            # Deserialize value
            value = self._deserialize_value(result)
            self._metrics["hits"] += 1
            return value

        try:
            return await self._track_performance_async("cache_get", _get_implementation, namespace=namespace)
        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to get_async cache key: {e}", operation="get_async", key=key)

    async def get_or_set_async(
        self,
        key: str,
        factory: Callable,
        ttl_async: Optional[int] = None,
        namespace: str = "default",
        *args,
        **kwargs,
    ) -> Any:
        """Get value from cache or compute and set_async if missing.

        Args:
            key: Cache key
            factory: Function to compute value if missing
            ttl_async: Time to live in seconds
            namespace: Cache namespace
            *args: Arguments for factory function
            **kwargs: Keyword arguments for factory function

        Returns:
            Cached or computed value
        """
        # Try to get_async from cache first
        value = await self.get_async(key, namespace)

        if value is not None:
            return value

        # Compute value using factory
        if asyncio.iscoroutinefunction(factory):
            computed_value = await factory(*args, **kwargs)
        else:
            computed_value = factory(*args, **kwargs)

        # Set in cache
        await self.set_async(key, computed_value, ttl_async, namespace)

        return computed_value

    async def delete_async(self, key: str, namespace: str = "default") -> bool:
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
            async def _delete_operation_async():
                return await self._redis_client.delete(cache_key)

            result = await self._execute_with_circuit_breaker_async(_delete_operation_async)
            self._metrics["deletes"] += 1

            return bool(result)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to delete_async cache key: {e}", operation="delete_async", key=key)

    async def delete_pattern_async(self, pattern: str, namespace: str = "default") -> int:
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
            async def _delete_pattern_operation_async():
                keys = await self._redis_client.keys(cache_pattern)
                if keys:
                    return await self._redis_client.delete(*keys)
                return 0

            result = await self._execute_with_circuit_breaker_async(_delete_pattern_operation_async)
            self._metrics["deletes"] += result

            return result

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to delete_async pattern: {e}", operation="delete_pattern_async", key=pattern)

    async def exists_async(self, key: str, namespace: str = "default") -> bool:
        """Check if a key exists_async in cache.

        Args:
            key: Cache key
            namespace: Cache namespace

        Returns:
            True if key exists_async
        """
        try:
            # Generate namespaced key
            cache_key = self.config.get_namespaced_key(namespace, key)

            # Execute Redis operation
            async def _exists_operation_async():
                return await self._redis_client.exists(cache_key)

            result = await self._execute_with_circuit_breaker_async(_exists_operation_async)
            return bool(result)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to check key existence: {e}", operation="exists_async", key=key)

    async def ttl_async(self, key: str, namespace: str = "default") -> int:
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
            async def _ttl_operation_async():
                return await self._redis_client.ttl(cache_key)

            return await self._execute_with_circuit_breaker_async(_ttl_operation_async)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to get_async TTL: {e}", operation="ttl_async", key=key)

    async def extend_ttl_async(self, key: str, ttl_async: int, namespace: str = "default") -> bool:
        """Extend TTL for an existing key.

        Args:
            key: Cache key
            ttl_async: New TTL in seconds
            namespace: Cache namespace

        Returns:
            True if TTL was updated
        """
        try:
            # Generate namespaced key
            cache_key = self.config.get_namespaced_key(namespace, key)

            # Execute Redis operation
            async def _expire_operation_async():
                return await self._redis_client.expire(cache_key, ttl_async)

            result = await self._execute_with_circuit_breaker_async(_expire_operation_async)
            return bool(result)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to extend TTL: {e}", operation="extend_ttl_async", key=key)

    async def scan_keys_async(
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

            async def _scan_operation_async() -> None:
                async for key in self._redis_client.scan_iter(match=cache_pattern, count=count):
                    # Remove namespace prefix
                    if key.startswith(namespace_prefix):
                        yield key[len(namespace_prefix) :]
                    else:
                        yield key

            async for key in self._execute_with_circuit_breaker_async(_scan_operation_async):
                yield key

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to scan keys: {e}", operation="scan", key=pattern)

    async def mget_async(self, keys: List[str], namespace: str = "default") -> Dict[str, Any]:
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
            async def _mget_operation_async():
                return await self._redis_client.mget(cache_keys)

            results = await self._execute_with_circuit_breaker_async(_mget_operation_async)

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
            raise CacheError(f"Failed to get_async multiple keys: {e}", operation="mget_async")

    async def mset_async(
        self, mapping: Dict[str, Any], ttl_async: Optional[int] = None, namespace: str = "default"
    ) -> bool:
        """Set multiple values in cache.

        Args:
            mapping: Dictionary of key-value pairs
            ttl_async: Time to live in seconds
            namespace: Cache namespace

        Returns:
            True if all values were set_async
        """
        try:
            # Use namespace-specific TTL if not provided
            if ttl_async is None:
                ttl_async = self.config.get_ttl_for_namespace(namespace)

            # Execute Redis operation
            async def _mset_operation_async():
                pipe = self._redis_client.pipeline()

                for key, value in mapping.items():
                    cache_key = self.config.get_namespaced_key(namespace, key)
                    serialized_value = self._serialize_value(value)
                    pipe.setex(cache_key, ttl_async, serialized_value)

                return await pipe.execute()

            results = await self._execute_with_circuit_breaker_async(_mset_operation_async)
            self._metrics["sets"] += len(mapping)

            return all(results)

        except (CacheCircuitBreakerError, CacheTimeoutError, CacheConnectionError):
            raise
        except Exception as e:
            raise CacheError(f"Failed to set_async multiple keys: {e}", operation="mset_async")

    async def health_check_async(self) -> Dict[str, Any]:
        """Perform health check on cache.

        Returns:
            Health status dictionary
        """
        try:
            start_time = time.time()

            # Test basic operations
            # Test ping
            ping_result = await self._redis_client.ping()

            # Test set/get operations
            test_key = f"health_check_{int(time.time())}"
            await self._redis_client.setex(test_key, 30, "test_value")
            get_result = await self._redis_client.get(test_key)
            await self._redis_client.delete(test_key)

            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            self._health_status = {
                "healthy": True,
                "last_check": datetime.utcnow().isoformat(),
                "response_time_ms": round(response_time, 2),
                "ping_result": ping_result,
                "set_get_test": get_result == b"test_value",
                "circuit_breaker_state": self._circuit_breaker.state.value if self._circuit_breaker else "disabled",
                "errors": [],
            }

            self._last_health_check = time.time()
            return self._health_status

        except Exception as e:
            self._health_status = {
                "healthy": False,
                "last_check": datetime.utcnow().isoformat(),
                "errors": [str(e)],
                "circuit_breaker_state": self._circuit_breaker.state.value if self._circuit_breaker else "disabled",
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
            "circuit_breaker_state": self._circuit_breaker.state.value if self._circuit_breaker else "disabled",
            "last_health_check": self._last_health_check,
        }

    def reset_metrics(self) -> None:
        """Reset all metrics counters."""
        self._metrics = {key: 0 for key in self._metrics}

    def get_performance_metrics(self) -> Optional[Dict[str, Any]]:
        """Get detailed performance metrics from the performance monitor.

        Returns:
            Performance metrics dictionary or None if monitoring is disabled
        """
        if not self._performance_monitor:
            return None

        metrics = {}

        # Get metrics for each cache operation
        for operation_name in ["cache_get", "cache_set", "cache_delete"]:
            operation_metrics = self._performance_monitor.get_metrics(operation_name)
            if operation_metrics:
                metrics[operation_name] = {
                    "total_operations": len(operation_metrics),
                    "avg_execution_time": sum(m.execution_time for m in operation_metrics) / len(operation_metrics),
                    "avg_memory_usage": sum(m.memory_usage for m in operation_metrics) / len(operation_metrics),
                    "avg_operations_per_second": sum(m.operations_per_second for m in operation_metrics)
                    / len(operation_metrics),
                    "total_bytes_processed": sum(m.bytes_processed for m in operation_metrics),
                    "error_rate": sum(m.error_count for m in operation_metrics) / len(operation_metrics)
                    if operation_metrics
                    else 0.0,
                }

        # Add system-level metrics
        system_metrics = self._performance_monitor.get_system_metrics()
        if system_metrics:
            metrics["system"] = system_metrics

        return metrics


# Global cache client instance
_global_cache_client: Optional[HiveCacheClient] = None


async def get_cache_client_async(config: Optional[CacheConfig] = None) -> HiveCacheClient:
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
        await _global_cache_client.initialize_async()

    return _global_cache_client


async def close_cache_client_async() -> None:
    """Close global cache client."""
    global _global_cache_client

    if _global_cache_client:
        await _global_cache_client.close_async()
        _global_cache_client = None
