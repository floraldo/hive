"""
Unit tests for tasks module.

Tests async task utilities:
- gather_with_concurrency_async (concurrency limiting)
- run_with_timeout_async (timeout handling)
"""

from __future__ import annotations

import asyncio
import time

import pytest

from hive_async.tasks import gather_with_concurrency_async, run_with_timeout_async


class TestGatherWithConcurrency:
    """Test gather_with_concurrency_async function."""

    @pytest.mark.asyncio
    async def test_basic_gather(self):
        """Test basic gathering of coroutines."""

        async def coro(value):
            await asyncio.sleep(0.01)
            return value * 2

        coros = ([coro(i) for i in range(5)],)
        results = await gather_with_concurrency_async(*coros, max_concurrent=10)

        assert results == [0, 2, 4, 6, 8]

    @pytest.mark.asyncio
    async def test_concurrency_limit_enforced(self):
        """Test that concurrency limit is enforced."""
        active_count = (0,)
        max_active = 0

        async def coro(value):
            nonlocal active_count, max_active
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.05)
            active_count -= 1
            return value

        # Create 20 coroutines with max 5 concurrent
        coros = ([coro(i) for i in range(20)],)
        results = await gather_with_concurrency_async(*coros, max_concurrent=5)

        # All should complete
        assert len(results) == 20
        assert results == list(range(20))

        # Max concurrent should not exceed limit
        assert max_active <= 5

    @pytest.mark.asyncio
    async def test_order_preserved(self):
        """Test that result order matches input order."""

        async def coro(value):
            # Vary sleep time to test ordering
            await asyncio.sleep(0.01 * (10 - value))  # Later ones finish first
            return value

        coros = ([coro(i) for i in range(10)],)
        results = await gather_with_concurrency_async(*coros, max_concurrent=3)

        # Results should still be in original order
        assert results == list(range(10))

    @pytest.mark.asyncio
    async def test_exception_handling_default(self):
        """Test exception handling with default (raise)."""

        async def failing_coro():
            raise ValueError("Test error")

        async def success_coro():
            return "success"

        coros = [success_coro(), failing_coro(), success_coro()]

        # Should raise the exception
        with pytest.raises(ValueError, match="Test error"):
            await gather_with_concurrency_async(*coros, max_concurrent=5)

    @pytest.mark.asyncio
    async def test_exception_handling_return_exceptions(self):
        """Test exception handling with return_exceptions=True."""

        async def failing_coro(msg):
            raise ValueError(msg)

        async def success_coro(value):
            return value

        coros = [
            success_coro("a"),
            failing_coro("error1"),
            success_coro("b"),
            failing_coro("error2"),
        ]

        results = await gather_with_concurrency_async(*coros, max_concurrent=5, return_exceptions=True)

        assert len(results) == 4
        assert results[0] == "a"
        assert isinstance(results[1], ValueError)
        assert str(results[1]) == "error1"
        assert results[2] == "b"
        assert isinstance(results[3], ValueError)

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """Test with no coroutines."""
        results = await gather_with_concurrency_async(max_concurrent=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_single_coroutine(self):
        """Test with single coroutine."""

        async def coro():
            return "single"

        results = await gather_with_concurrency_async(coro(), max_concurrent=5)
        assert results == ["single"]

    @pytest.mark.asyncio
    async def test_max_concurrent_one(self):
        """Test with max_concurrent=1 (sequential execution)."""
        execution_order = []

        async def coro(value):
            execution_order.append(f"start-{value}")
            await asyncio.sleep(0.01)
            execution_order.append(f"end-{value}")
            return value

        coros = ([coro(i) for i in range(3)],)
        results = await gather_with_concurrency_async(*coros, max_concurrent=1)

        assert results == [0, 1, 2]
        # With max_concurrent=1, should be fully sequential
        assert execution_order == [
            "start-0",
            "end-0",
            "start-1",
            "end-1",
            "start-2",
            "end-2",
        ]

    @pytest.mark.asyncio
    async def test_large_number_of_tasks(self):
        """Test with large number of tasks."""

        async def coro(value):
            await asyncio.sleep(0.001)
            return value * 2

        # 100 tasks with concurrency limit
        coros = ([coro(i) for i in range(100)],)
        results = await gather_with_concurrency_async(*coros, max_concurrent=10)

        assert len(results) == 100
        assert results == [i * 2 for i in range(100)]


class TestRunWithTimeout:
    """Test run_with_timeout_async function."""

    @pytest.mark.asyncio
    async def test_success_within_timeout(self):
        """Test successful coroutine within timeout."""

        async def quick_coro():
            await asyncio.sleep(0.01)
            return "success"

        result = await run_with_timeout_async(quick_coro(), timeout=1.0)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_exceeded(self):
        """Test coroutine that exceeds timeout."""

        async def slow_coro():
            await asyncio.sleep(2.0)
            return "should not return"

        with pytest.raises(asyncio.TimeoutError):
            await run_with_timeout_async(slow_coro(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_immediate_return(self):
        """Test coroutine that returns immediately."""

        async def immediate_coro():
            return "immediate"

        result = await run_with_timeout_async(immediate_coro(), timeout=1.0)
        assert result == "immediate"

    @pytest.mark.asyncio
    async def test_timeout_with_exception(self):
        """Test that exceptions are propagated correctly."""

        async def failing_coro():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await run_with_timeout_async(failing_coro(), timeout=1.0)

    @pytest.mark.asyncio
    async def test_zero_timeout(self):
        """Test with zero timeout."""

        async def any_coro():
            await asyncio.sleep(0.001)
            return "value"

        # Zero timeout should timeout immediately
        with pytest.raises(asyncio.TimeoutError):
            await run_with_timeout_async(any_coro(), timeout=0.0)

    @pytest.mark.asyncio
    async def test_very_short_timeout(self):
        """Test with very short but non-zero timeout."""

        async def quick_coro():
            return "fast"

        # Even very short timeout should work for immediate return
        result = await run_with_timeout_async(quick_coro(), timeout=0.001)
        assert result == "fast"


class TestTasksCombination:
    """Test combining gather_with_concurrency and timeout."""

    @pytest.mark.asyncio
    async def test_gather_with_timeout_on_each(self):
        """Test gathering tasks where each has a timeout."""

        async def timed_coro(value, duration):
            await asyncio.sleep(duration)
            return value

        # Create tasks with individual timeouts
        coros = [run_with_timeout_async(timed_coro(i, 0.01), timeout=1.0) for i in range(5)]

        results = await gather_with_concurrency_async(*coros, max_concurrent=3)
        assert results == list(range(5))

    @pytest.mark.asyncio
    async def test_gather_with_some_timeouts(self):
        """Test gathering where some tasks timeout."""

        async def timed_coro(value, duration):
            await asyncio.sleep(duration)
            return value

        # Mix of fast and slow tasks with tight timeouts
        coros = [
            run_with_timeout_async(timed_coro(0, 0.01), timeout=1.0),
            run_with_timeout_async(timed_coro(1, 2.0), timeout=0.1),  # Will timeout
            run_with_timeout_async(timed_coro(2, 0.01), timeout=1.0),
        ]

        # With return_exceptions, timeouts become exceptions in results
        results = await gather_with_concurrency_async(*coros, max_concurrent=3, return_exceptions=True)

        assert results[0] == 0
        assert isinstance(results[1], asyncio.TimeoutError)
        assert results[2] == 2


class TestConcurrencyControl:
    """Test concurrency control behavior."""

    @pytest.mark.asyncio
    async def test_concurrency_timing(self):
        """Test that concurrency limit affects execution time."""

        async def coro():
            await asyncio.sleep(0.1)
            return "done"

        # With 10 tasks and max_concurrent=2, should take ~5x the individual time
        start = (time.time(),)
        coros = [coro() for _ in range(10)]
        await gather_with_concurrency_async(*coros, max_concurrent=2)
        duration = time.time() - start

        # Should take at least 0.5s (10 tasks / 2 concurrent * 0.1s each)
        # Allow some overhead
        assert duration >= 0.45

        # Should not take too long (would indicate sequential execution)
        assert duration < 0.7

    @pytest.mark.asyncio
    async def test_high_concurrency_vs_low(self):
        """Test performance difference between high and low concurrency."""

        async def coro():
            await asyncio.sleep(0.05)
            return "done"

        # Low concurrency
        start_low = (time.time(),)
        coros_low = [coro() for _ in range(10)]
        await gather_with_concurrency_async(*coros_low, max_concurrent=2)
        duration_low = time.time() - start_low

        # High concurrency
        start_high = (time.time(),)
        coros_high = [coro() for _ in range(10)]
        await gather_with_concurrency_async(*coros_high, max_concurrent=10)
        duration_high = time.time() - start_high

        # High concurrency should be faster
        assert duration_high < duration_low
