"""Performance-focused caching for expensive computations and I/O operations."""

import asyncio
import inspect
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from hive_logging import get_logger
import hashlib

from .cache_client import HiveCacheClient, get_cache_client
from .config import CacheConfig
from .exceptions import CacheError

logger = get_logger(__name__)


class PerformanceCache:
    """
    High-performance cache for expensive computations and I/O operations.

    Features:
    - Function result caching with automatic key generation
    - Computation time tracking and TTL optimization
    - Async and sync function support
    - Memoization decorators
    - Batch operation caching
    - Cache warming strategies
    """

    def __init__(self, cache_client: HiveCacheClient, config: CacheConfig):
        self.cache_client = cache_client
        self.config = config
        self.namespace = config.performance_cache_namespace

        # Performance-specific metrics
        self.perf_metrics = {
            "total_function_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_computation_time_saved": 0.0,
            "average_computation_time": 0.0,
            "expensive_operations_cached": 0,
        }

    @classmethod
    async def create(cls, config: Optional[CacheConfig] = None) -> "PerformanceCache":
        """Create performance cache instance.

        Args:
            config: Optional cache configuration

        Returns:
            PerformanceCache instance
        """
        cache_client = await get_cache_client(config)
        if config is None:
            config = CacheConfig.from_env()

        return cls(cache_client, config)

    def _generate_function_key(
        self,
        func: Callable,
        args: Tuple[Any, ...] = (),
        kwargs: Dict[str, Any] = None,
        key_prefix: Optional[str] = None,
    ) -> str:
        """Generate cache key for function call.

        Args:
            func: Function being cached
            args: Function positional arguments
            kwargs: Function keyword arguments
            key_prefix: Optional prefix for the key

        Returns:
            Cache key string
        """
        if kwargs is None:
            kwargs = {}

        # Get function identifier
        func_name = func.__name__
        func_module = func.__module__

        # Create parameter signature
        param_dict = {"args": args, "kwargs": sorted(kwargs.items())}
        param_str = str(param_dict)

        # Generate hash for large parameter sets
        if len(param_str) > 200:
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
            param_str = f"hash_{param_hash}"

        # Construct key
        key_parts = [func_module, func_name, param_str]
        if key_prefix:
            key_parts.insert(0, key_prefix)

        return "_".join(str(part) for part in key_parts)

    def _calculate_computation_ttl(self, computation_time: float, base_ttl: Optional[int] = None) -> int:
        """Calculate TTL based on computation expense.

        Args:
            computation_time: Time taken to compute result (seconds)
            base_ttl: Base TTL to adjust

        Returns:
            Calculated TTL in seconds
        """
        if base_ttl is None:
            base_ttl = self.config.performance_default_ttl

        # Longer TTL for expensive computations
        if computation_time > 60:  # > 1 minute
            time_factor = 5.0
        elif computation_time > 10:  # > 10 seconds
            time_factor = 3.0
        elif computation_time > 1:  # > 1 second
            time_factor = 2.0
        else:
            time_factor = 1.0

        calculated_ttl = int(base_ttl * time_factor)

        # Clamp to configured limits
        return max(
            self.config.min_ttl,
            min(calculated_ttl, self.config.max_ttl)
        )

    async def cached_computation(
        self,
        key: str,
        computation: Callable,
        args: Tuple[Any, ...] = (),
        kwargs: Dict[str, Any] = None,
        ttl: Optional[int] = None,
        force_refresh: bool = False,
    ) -> Any:
        """Execute computation with caching.

        Args:
            key: Cache key for the computation
            computation: Function to execute
            args: Function arguments
            kwargs: Function keyword arguments
            ttl: Custom TTL (uses adaptive calculation if None)
            force_refresh: Skip cache and recompute

        Returns:
            Computation result
        """
        if kwargs is None:
            kwargs = {}

        self.perf_metrics["total_function_calls"] += 1

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_result = await self.cache_client.get(key, self.namespace)
            if cached_result is not None:
                self.perf_metrics["cache_hits"] += 1
                logger.debug(f"Cache hit for computation: {key}")
                return cached_result["result"]

        # Cache miss - execute computation
        self.perf_metrics["cache_misses"] += 1
        start_time = time.time()

        try:
            # Execute computation
            if asyncio.iscoroutinefunction(computation):
                result = await computation(*args, **kwargs)
            else:
                result = computation(*args, **kwargs)

            computation_time = time.time() - start_time

            # Update metrics
            self.perf_metrics["total_computation_time_saved"] += computation_time
            total_calls = self.perf_metrics["total_function_calls"]
            self.perf_metrics["average_computation_time"] = (
                self.perf_metrics["total_computation_time_saved"] / total_calls
            )

            if computation_time > 1.0:  # Mark as expensive if > 1 second
                self.perf_metrics["expensive_operations_cached"] += 1

            # Calculate TTL
            if ttl is None:
                ttl = self._calculate_computation_ttl(computation_time)

            # Cache the result with metadata
            cache_value = {
                "result": result,
                "computation_time": computation_time,
                "cached_at": time.time(),
                "ttl": ttl,
            }

            await self.cache_client.set(key, cache_value, ttl, self.namespace)

            logger.info(
                f"Cached computation result: {key} "
                f"(time: {computation_time:.3f}s, TTL: {ttl}s)"
            )

            return result

        except Exception as e:
            logger.error(f"Computation failed for key {key}: {e}")
            raise

    async def memoize_function(
        self,
        func: Callable,
        args: Tuple[Any, ...] = (),
        kwargs: Dict[str, Any] = None,
        ttl: Optional[int] = None,
        key_prefix: Optional[str] = None,
    ) -> Any:
        """Memoize function call with automatic key generation.

        Args:
            func: Function to memoize
            args: Function arguments
            kwargs: Function keyword arguments
            ttl: Custom TTL
            key_prefix: Optional key prefix

        Returns:
            Function result
        """
        # Generate cache key
        cache_key = self._generate_function_key(func, args, kwargs, key_prefix)

        # Use cached_computation
        return await self.cached_computation(cache_key, func, args, kwargs, ttl)

    def cached(
        self,
        ttl: Optional[int] = None,
        key_prefix: Optional[str] = None,
        namespace: Optional[str] = None,
    ):
        """Decorator for automatic function result caching.

        Args:
            ttl: Custom TTL for cached results
            key_prefix: Optional prefix for cache keys
            namespace: Custom namespace (uses default if None)

        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            cache_namespace = namespace or self.namespace

            if asyncio.iscoroutinefunction(func):
                async def async_wrapper(*args, **kwargs):
                    cache_key = self._generate_function_key(func, args, kwargs, key_prefix)

                    # Check cache
                    cached_result = await self.cache_client.get(cache_key, cache_namespace)
                    if cached_result is not None:
                        return cached_result["result"]

                    # Execute function
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    computation_time = time.time() - start_time

                    # Cache result
                    cache_ttl = ttl or self._calculate_computation_ttl(computation_time)
                    cache_value = {
                        "result": result,
                        "computation_time": computation_time,
                        "cached_at": time.time(),
                    }

                    await self.cache_client.set(cache_key, cache_value, cache_ttl, cache_namespace)
                    return result

                return async_wrapper

            else:
                def sync_wrapper(*args, **kwargs):
                    # Convert to async and run
                    async def _async_exec():
                        return await self.memoize_function(func, args, kwargs, ttl, key_prefix)

                    try:
                        loop = asyncio.get_event_loop()
                        return loop.run_until_complete(_async_exec())
                    except RuntimeError:
                        # No event loop, create one
                        return asyncio.run(_async_exec())

                return sync_wrapper

        return decorator

    async def batch_cache_operations(
        self,
        operations: List[Dict[str, Any]],
        max_concurrent: int = 10,
    ) -> List[Any]:
        """Execute multiple cached operations in batch.

        Args:
            operations: List of operation dictionaries with keys:
                - key: Cache key
                - computation: Function to execute
                - args: Function arguments (optional)
                - kwargs: Function keyword arguments (optional)
                - ttl: Custom TTL (optional)
            max_concurrent: Maximum concurrent operations

        Returns:
            List of results in same order as operations
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _execute_operation(op: Dict[str, Any]) -> Any:
            async with semaphore:
                return await self.cached_computation(
                    key=op["key"],
                    computation=op["computation"],
                    args=op.get("args", ()),
                    kwargs=op.get("kwargs", {}),
                    ttl=op.get("ttl"),
                )

        # Execute all operations concurrently
        tasks = [_execute_operation(op) for op in operations]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions back to None or re-raise
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch operation failed: {result}")
                final_results.append(None)
            else:
                final_results.append(result)

        return final_results

    async def warm_cache_from_functions(
        self,
        function_configs: List[Dict[str, Any]],
        max_concurrent: int = 5,
    ) -> Dict[str, bool]:
        """Warm cache by pre-executing functions.

        Args:
            function_configs: List of function configuration dictionaries
            max_concurrent: Maximum concurrent warming operations

        Returns:
            Dictionary mapping function keys to success status
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}

        async def _warm_function(config: Dict[str, Any]) -> Tuple[str, bool]:
            async with semaphore:
                try:
                    func = config["function"]
                    args = config.get("args", ())
                    kwargs = config.get("kwargs", {})
                    key_prefix = config.get("key_prefix")

                    cache_key = self._generate_function_key(func, args, kwargs, key_prefix)

                    # Check if already cached
                    existing = await self.cache_client.get(cache_key, self.namespace)
                    if existing:
                        return cache_key, True

                    # Execute and cache
                    await self.memoize_function(func, args, kwargs, key_prefix=key_prefix)
                    return cache_key, True

                except Exception as e:
                    logger.error(f"Failed to warm cache for function: {e}")
                    return config.get("key", "unknown"), False

        # Execute warming operations
        tasks = [_warm_function(config) for config in function_configs]
        warming_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in warming_results:
            if isinstance(result, Exception):
                logger.error(f"Cache warming error: {result}")
            else:
                key, success = result
                results[key] = success

        return results

    async def invalidate_function_cache(
        self,
        func: Callable,
        args: Tuple[Any, ...] = None,
        kwargs: Dict[str, Any] = None,
        key_prefix: Optional[str] = None,
    ) -> bool:
        """Invalidate cached result for specific function call.

        Args:
            func: Function whose cache to invalidate
            args: Function arguments (invalidates all if None)
            kwargs: Function keyword arguments
            key_prefix: Optional key prefix

        Returns:
            True if cache was invalidated
        """
        if args is None:
            # Invalidate all cached results for this function
            pattern = f"{func.__module__}_{func.__name__}_*"
            if key_prefix:
                pattern = f"{key_prefix}_{pattern}"
            return await self.cache_client.delete_pattern(pattern, self.namespace) > 0
        else:
            # Invalidate specific function call
            cache_key = self._generate_function_key(func, args, kwargs or {}, key_prefix)
            return await self.cache_client.delete(cache_key, self.namespace)

    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance cache statistics.

        Returns:
            Performance statistics dictionary
        """
        # Calculate additional metrics
        total_calls = self.perf_metrics["total_function_calls"]
        hit_rate = (
            (self.perf_metrics["cache_hits"] / total_calls * 100) if total_calls > 0 else 0
        )

        return {
            **self.perf_metrics,
            "cache_hit_rate_percent": round(hit_rate, 2),
            "namespace": self.namespace,
            "cache_client_metrics": self.cache_client.get_metrics(),
        }

    async def cleanup_by_age(self, max_age_seconds: int) -> int:
        """Clean up cache entries older than specified age.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            Number of entries cleaned up
        """
        cleaned_count = 0
        current_time = time.time()

        async for key in self.cache_client.scan_keys("*", self.namespace):
            try:
                cached_value = await self.cache_client.get(key, self.namespace)
                if cached_value and isinstance(cached_value, dict):
                    cached_at = cached_value.get("cached_at", 0)
                    age = current_time - cached_at

                    if age > max_age_seconds:
                        await self.cache_client.delete(key, self.namespace)
                        cleaned_count += 1

            except Exception as e:
                logger.warning(f"Failed to check/clean cache entry {key}: {e}")

        logger.info(f"Cleaned up {cleaned_count} old cache entries")
        return cleaned_count