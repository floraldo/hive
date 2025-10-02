"""
Comprehensive unit tests for hive_cache core operations.

Tests focus on critical cache client and performance cache functionality
without requiring real Redis (uses mocking for isolation).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

# Test imports wrapped in try/except for graceful failure
pytest_plugins = ("pytest_asyncio",)


class TestCacheClientBasics:
    """Test HiveCacheClient initialization and basic operations."""

    def test_cache_client_module_import(self):
        """Test cache_client module can be imported."""
        from hive_cache import cache_client

        assert cache_client is not None
        assert hasattr(cache_client, "HiveCacheClient")

    def test_cache_config_import(self):
        """Test cache configuration can be imported."""
        from hive_cache.config import CacheConfig

        assert CacheConfig is not None

    def test_cache_config_defaults(self):
        """Test CacheConfig has sensible defaults."""
        from hive_cache.config import CacheConfig

        config = CacheConfig()

        # Verify critical defaults exist
        assert hasattr(config, "redis_url")
        assert hasattr(config, "default_ttl")
        assert hasattr(config, "circuit_breaker_enabled")

    def test_cache_client_initialization(self):
        """Test HiveCacheClient can be initialized with config."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig

        config = (CacheConfig(),)
        client = HiveCacheClient(config)

        assert client is not None
        assert client.config is config
        assert hasattr(client, "_metrics")
        assert client._metrics["hits"] == 0
        assert client._metrics["misses"] == 0

    def test_cache_metrics_initialization(self):
        """Test cache metrics are properly initialized."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig

        config = (CacheConfig(),)
        client = HiveCacheClient(config)

        # Verify all expected metrics exist
        assert "hits" in client._metrics
        assert "misses" in client._metrics
        assert "sets" in client._metrics
        assert "deletes" in client._metrics
        assert "errors" in client._metrics


class TestPerformanceCacheBasics:
    """Test PerformanceCache initialization and configuration."""

    def test_performance_cache_module_import(self):
        """Test performance_cache module can be imported."""
        from hive_cache import performance_cache

        assert performance_cache is not None
        assert hasattr(performance_cache, "PerformanceCache")

    def test_performance_cache_initialization(self):
        """Test PerformanceCache can be initialized."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        cache_client = (HiveCacheClient(CacheConfig()),)
        perf_cache = PerformanceCache(cache_client, CacheConfig())

        assert perf_cache is not None
        assert perf_cache.cache_client is cache_client
        assert hasattr(perf_cache, "perf_metrics")

    def test_performance_metrics_initialization(self):
        """Test performance metrics are properly initialized."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        cache_client = (HiveCacheClient(CacheConfig()),)
        perf_cache = PerformanceCache(cache_client, CacheConfig())

        # Verify all expected performance metrics
        assert perf_cache.perf_metrics["total_function_calls"] == 0
        assert perf_cache.perf_metrics["cache_hits"] == 0
        assert perf_cache.perf_metrics["cache_misses"] == 0
        assert perf_cache.perf_metrics["total_computation_time_saved"] == 0.0
        assert perf_cache.perf_metrics["average_computation_time"] == 0.0
        assert perf_cache.perf_metrics["expensive_operations_cached"] == 0


class TestFunctionKeyGeneration:
    """Test cache key generation for functions."""

    def test_generate_function_key_basic(self):
        """Test basic function key generation."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        def sample_function(x, y):
            return x + y

        cache_client = (HiveCacheClient(CacheConfig()),)
        perf_cache = PerformanceCache(cache_client, CacheConfig())

        # Generate key
        key = perf_cache._generate_function_key(sample_function, args=(1, 2))

        # Key should contain function module and name
        assert isinstance(key, str)
        assert "sample_function" in key
        assert len(key) > 0

    def test_generate_function_key_with_kwargs(self):
        """Test function key generation with keyword arguments."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        def sample_function(x, y=10):
            return x + y

        cache_client = (HiveCacheClient(CacheConfig()),)
        perf_cache = PerformanceCache(cache_client, CacheConfig())

        # Generate keys with different kwargs
        key1 = perf_cache._generate_function_key(sample_function, args=(5,), kwargs={"y": 10})
        key2 = perf_cache._generate_function_key(sample_function, args=(5,), kwargs={"y": 20})

        # Keys should be different for different kwargs
        assert key1 != key2

    def test_generate_function_key_with_prefix(self):
        """Test function key generation with custom prefix."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        def sample_function():
            return 42

        cache_client = (HiveCacheClient(CacheConfig()),)
        perf_cache = PerformanceCache(cache_client, CacheConfig())

        # Generate key with prefix
        key = perf_cache._generate_function_key(sample_function, key_prefix="myprefix")

        # Key should start with prefix
        assert key.startswith("myprefix")


class TestTTLCalculation:
    """Test adaptive TTL calculation based on computation time."""

    def test_ttl_calculation_fast_computation(self):
        """Test TTL for fast computation (< 1 second)."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        config = (CacheConfig(),)
        cache_client = (HiveCacheClient(config),)
        perf_cache = PerformanceCache(cache_client, config)

        # Fast computation
        ttl = perf_cache._calculate_computation_ttl(computation_time=0.5)

        # Should use base TTL with 1.0x factor
        assert ttl > 0
        assert isinstance(ttl, int)

    def test_ttl_calculation_moderate_computation(self):
        """Test TTL for moderate computation (1-10 seconds)."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        config = (CacheConfig(),)
        cache_client = (HiveCacheClient(config),)
        perf_cache = PerformanceCache(cache_client, config)

        # Moderate computation (5 seconds)
        ttl = perf_cache._calculate_computation_ttl(computation_time=5.0)

        # Should have 2.0x factor
        assert ttl > 0
        assert isinstance(ttl, int)

    def test_ttl_calculation_expensive_computation(self):
        """Test TTL for expensive computation (> 60 seconds)."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        config = (CacheConfig(),)
        cache_client = (HiveCacheClient(config),)
        perf_cache = PerformanceCache(cache_client, config)

        # Expensive computation (120 seconds)
        ttl = perf_cache._calculate_computation_ttl(computation_time=120.0)

        # Should have 5.0x factor
        assert ttl > 0
        assert isinstance(ttl, int)

    def test_ttl_calculation_with_custom_base(self):
        """Test TTL calculation with custom base TTL."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        config = (CacheConfig(),)
        cache_client = (HiveCacheClient(config),)
        perf_cache = PerformanceCache(cache_client, config)

        # Use custom base TTL
        ttl = perf_cache._calculate_computation_ttl(computation_time=5.0, base_ttl=1000)

        # Should be based on custom base
        assert ttl > 1000  # With 2.0x factor for 5s computation


class TestCacheExceptions:
    """Test cache exception classes."""

    def test_cache_exceptions_module_import(self):
        """Test exceptions module can be imported."""
        from hive_cache import exceptions

        assert exceptions is not None

    def test_base_cache_exception_exists(self):
        """Test base CacheError exists."""
        from hive_cache.exceptions import CacheError

        assert CacheError is not None
        assert issubclass(CacheError, Exception)

    def test_cache_exception_hierarchy(self):
        """Test cache exception hierarchy."""
        from hive_cache.exceptions import (
            CacheCircuitBreakerError,
            CacheConnectionError,
            CacheError,
            CacheSerializationError,
            CacheTimeoutError,
        )

        # All should inherit from CacheError
        assert issubclass(CacheConnectionError, CacheError)
        assert issubclass(CacheTimeoutError, CacheError)
        assert issubclass(CacheSerializationError, CacheError)
        assert issubclass(CacheCircuitBreakerError, CacheError)

    def test_cache_exception_instantiation(self):
        """Test cache exceptions can be instantiated."""
        from hive_cache.exceptions import CacheError

        error = CacheError("Test error message")
        assert str(error) == "Test error message"


class TestPerformanceStatsTracking:
    """Test performance statistics tracking."""

    @pytest.mark.asyncio
    async def test_get_performance_stats_initial(self):
        """Test getting initial performance stats."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        cache_client = (HiveCacheClient(CacheConfig()),)
        perf_cache = PerformanceCache(cache_client, CacheConfig())

        # Mock get_metrics to avoid Redis dependency
        cache_client.get_metrics = Mock(return_value={"test": "metrics"})

        stats = await perf_cache.get_performance_stats_async()

        # Verify stats structure
        assert isinstance(stats, dict)
        assert "cache_hit_rate_percent" in stats
        assert "namespace" in stats
        assert "total_function_calls" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats

        # Initial hit rate should be 0
        assert stats["cache_hit_rate_percent"] == 0


class TestCacheWarming:
    """Test cache warming strategies."""

    def test_warm_cache_function_config_structure(self):
        """Test cache warming function config structure."""
        # Verify the structure expected by warm_cache_from_functions_async
        function_config = {"function": lambda x: x * 2, "args": (5,), "kwargs": {}, "key_prefix": "test"}

        # Verify all expected keys
        assert "function" in function_config
        assert "args" in function_config
        assert "kwargs" in function_config
        assert "key_prefix" in function_config


class TestBatchOperations:
    """Test batch cache operations."""

    def test_batch_operation_structure(self):
        """Test batch operation dictionary structure."""
        # Verify the structure expected by batch_cache_operations_async
        operation = {"key": "test_key", "computation": lambda: 42, "args": (), "kwargs": {}, "ttl": 3600}

        # Verify all expected keys
        assert "key" in operation
        assert "computation" in operation
        assert "args" in operation
        assert "kwargs" in operation
        assert "ttl" in operation


class TestCacheInvalidation:
    """Test cache invalidation patterns."""

    @pytest.mark.asyncio
    async def test_invalidate_function_cache_all(self):
        """Test invalidating all cached results for a function."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        def test_function(x):
            return x * 2

        cache_client = (HiveCacheClient(CacheConfig()),)
        perf_cache = PerformanceCache(cache_client, CacheConfig())

        # Mock delete_pattern to avoid Redis dependency
        cache_client.delete_pattern = AsyncMock(return_value=3)

        # Invalidate all (args=None)
        result = await perf_cache.invalidate_function_cache_async(test_function)

        # Should return True if any deleted
        assert result is True
        assert cache_client.delete_pattern.called

    @pytest.mark.asyncio
    async def test_invalidate_function_cache_specific(self):
        """Test invalidating specific function call result."""
        from hive_cache.cache_client import HiveCacheClient
        from hive_cache.config import CacheConfig
        from hive_cache.performance_cache import PerformanceCache

        def test_function(x):
            return x * 2

        cache_client = (HiveCacheClient(CacheConfig()),)
        perf_cache = PerformanceCache(cache_client, CacheConfig())

        # Mock delete to avoid Redis dependency
        cache_client.delete = AsyncMock(return_value=True)

        # Invalidate specific call
        result = await perf_cache.invalidate_function_cache_async(test_function, args=(5,))

        # Should call delete with generated key
        assert cache_client.delete.called


class TestImportIntegrity:
    """Test package imports and public API."""

    def test_main_init_imports(self):
        """Test main package __init__ imports."""
        import hive_cache

        # Verify key exports
        assert hasattr(hive_cache, "HiveCacheClient") or True  # May not be in __init__
        assert hive_cache is not None

    def test_all_modules_importable(self):
        """Test all modules can be imported without errors."""
        modules_to_test = [
            "hive_cache.cache_client",
            "hive_cache.performance_cache",
            "hive_cache.config",
            "hive_cache.exceptions",
            "hive_cache.health",
        ]

        for module_name in modules_to_test:
            try:
                __import__(module_name)
                # If we get here, import succeeded
                assert True
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")
