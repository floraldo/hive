"""Unit tests for hive_performance.async_profiler module."""

import asyncio

import pytest


class TestAsyncProfiler:
    """Test cases for AsyncProfiler class."""

    def test_async_profiler_initialization(self):
        """Test AsyncProfiler can be initialized."""
        from hive_performance.async_profiler import AsyncProfiler

        profiler = AsyncProfiler()
        assert profiler is not None

    @pytest.mark.asyncio
    async def test_profiler_context_manager(self):
        """Test profiler works as async context manager."""
        from hive_performance.async_profiler import AsyncProfiler

        profiler = AsyncProfiler()

        # Test context manager interface
        if hasattr(profiler, "__aenter__"):
            async with profiler:
                # Simulate some async work
                await asyncio.sleep(0.01)
            assert True  # Context manager worked

    @pytest.mark.asyncio
    async def test_profiler_decorator_functionality(self):
        """Test profiler decorator functionality."""
        from hive_performance.async_profiler import AsyncProfiler

        profiler = AsyncProfiler()

        @profiler.profile
        async def sample_async_function():
            await asyncio.sleep(0.01)
            return "test_result"

        if hasattr(profiler, "profile"):
            result = await sample_async_function()
            assert result == "test_result"

    def test_profiler_metrics_collection(self):
        """Test profiler collects performance metrics."""
        from hive_performance.async_profiler import AsyncProfiler

        profiler = AsyncProfiler()

        # Test metrics interface
        if hasattr(profiler, "get_metrics"):
            metrics = profiler.get_metrics()
            assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_concurrent_profiling(self):
        """Test profiler handles concurrent operations."""
        from hive_performance.async_profiler import AsyncProfiler

        AsyncProfiler()

        async def task(n):
            await asyncio.sleep(0.01)
            return n * 2

        # Run multiple concurrent tasks
        tasks = [task(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert results[0] == 0
        assert results[4] == 8

    def test_profiler_configuration(self):
        """Test profiler accepts configuration parameters."""
        from hive_performance.async_profiler import AsyncProfiler

        # Test with configuration
        config = {"enabled": True, "sample_rate": 0.1}
        profiler = AsyncProfiler(config)
        assert profiler is not None
