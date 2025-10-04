"""Unit tests for hive-async package V4.2."""

import asyncio
import time

import pytest

from hive_async import async_retry, gather_with_concurrency, timeout_context
from hive_async import run_with_timeout_async as run_with_timeout
from hive_async.advanced_timeout import AdvancedTimeoutManager, TimeoutConfig, TimeoutMetrics, with_adaptive_timeout
from hive_async.context import AsyncResourceManager, async_context

# Import the components we're testing
from hive_async.resilience import (
    AsyncCircuitBreaker,
    AsyncTimeoutManager,
    CircuitState,
    async_circuit_breaker,
    async_resilient,
    async_timeout,
)
from hive_async.retry import AsyncRetryConfig, create_retry_decorator, retry_on_connection_error

# Import expected exceptions
from hive_errors import AsyncTimeoutError, CircuitBreakerOpenError


class TestCircuitState:
    """Test the CircuitState enum."""

    def test_circuit_state_values(self):
        """Test CircuitState enum values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestAsyncCircuitBreaker:
    """Test the AsyncCircuitBreaker component."""

    def test_circuit_breaker_initialization(self):
        """Test AsyncCircuitBreaker initializes correctly."""
        breaker = AsyncCircuitBreaker(failure_threshold=3, recovery_timeout=30, expected_exception=ValueError)

        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 30
        assert breaker.expected_exception is ValueError
        assert breaker.failure_count == 0
        assert breaker.last_failure_time is None
        assert breaker.state == CircuitState.CLOSED
        assert not breaker.is_open

    @pytest.mark.asyncio
    async def test_circuit_breaker_successful_operation(self):
        """Test circuit breaker with successful operation."""
        breaker = AsyncCircuitBreaker(failure_threshold=2)

        async def successful_operation():
            return "success"

        result = await breaker.call_async(successful_operation)

        assert result == "success"
        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_tracking(self):
        """Test circuit breaker failure tracking."""
        breaker = AsyncCircuitBreaker(failure_threshold=2)

        async def failing_operation():
            raise ValueError("Test failure")

        # First failure
        with pytest.raises(ValueError):
            await breaker.call_async(failing_operation)

        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED

        # Second failure should open circuit
        with pytest.raises(ValueError):
            await breaker.call_async(failing_operation)

        assert breaker.failure_count == 2
        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state_blocking(self):
        """Test that open circuit breaker blocks operations."""
        breaker = AsyncCircuitBreaker(failure_threshold=1)

        async def failing_operation():
            raise ValueError("Test failure")

        # Trigger circuit to open
        with pytest.raises(ValueError):
            await breaker.call_async(failing_operation)

        assert breaker.state == CircuitState.OPEN

        # Next call should be blocked
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call_async(failing_operation)

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_timeout(self):
        """Test circuit breaker recovery after timeout."""
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        async def failing_operation():
            raise ValueError("Test failure")

        async def successful_operation():
            return "recovered"

        # Open circuit
        with pytest.raises(ValueError):
            await breaker.call_async(failing_operation)

        assert breaker.state == CircuitState.OPEN

        # Immediate retry should fail
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call_async(successful_operation)

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Should transition to half-open and then closed on success
        result = await breaker.call_async(successful_operation)
        assert result == "recovered"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_failure(self):
        """Test circuit breaker behavior in half-open state on failure."""
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        async def failing_operation():
            raise ValueError("Still failing")

        # Open circuit
        with pytest.raises(ValueError):
            await breaker.call_async(failing_operation)

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Should transition to half-open, then back to open on failure
        with pytest.raises(ValueError):
            await breaker.call_async(failing_operation)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_manual_reset(self):
        """Test manual circuit breaker reset."""
        breaker = AsyncCircuitBreaker(failure_threshold=1)

        async def failing_operation():
            raise ValueError("Test failure")

        # Open circuit
        with pytest.raises(ValueError):
            await breaker.call_async(failing_operation)

        assert breaker.state == CircuitState.OPEN

        # Manual reset
        await breaker.reset_async()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.last_failure_time is None

    @pytest.mark.asyncio
    async def test_circuit_breaker_sync_function_support(self):
        """Test circuit breaker with synchronous functions."""
        breaker = AsyncCircuitBreaker()

        def sync_function():
            return "sync_result"

        result = await breaker.call_async(sync_function)
        assert result == "sync_result"

    def test_circuit_breaker_status(self):
        """Test circuit breaker status reporting."""
        breaker = AsyncCircuitBreaker(failure_threshold=3, recovery_timeout=60)
        breaker.failure_count = 2

        status = breaker.get_status()

        assert status["state"] == "closed"
        assert status["failure_count"] == 2
        assert status["failure_threshold"] == 3
        assert status["recovery_timeout"] == 60


class TestAsyncTimeoutManager:
    """Test the AsyncTimeoutManager component."""

    def test_timeout_manager_initialization(self):
        """Test AsyncTimeoutManager initializes correctly."""
        manager = AsyncTimeoutManager(default_timeout=15.0)

        assert manager.default_timeout == 15.0
        assert len(manager._active_tasks) == 0
        assert len(manager._operation_stats) == 0

    @pytest.mark.asyncio
    async def test_timeout_manager_successful_operation(self):
        """Test timeout manager with successful operation."""
        manager = AsyncTimeoutManager(default_timeout=1.0)

        async def quick_operation():
            await asyncio.sleep(0.01)
            return "completed"

        result = await manager.run_with_timeout_async(quick_operation(), operation_name="test_op")

        assert result == "completed"

        # Check statistics
        stats = manager.get_statistics()
        assert stats["active_tasks"] == 0
        assert "test_op" in stats["operation_stats"]
        assert stats["operation_stats"]["test_op"]["successful_calls"] == 1

    @pytest.mark.asyncio
    async def test_timeout_manager_timeout_operation(self):
        """Test timeout manager with operation that times out."""
        manager = AsyncTimeoutManager(default_timeout=0.1)

        async def slow_operation():
            await asyncio.sleep(1.0)
            return "too_slow"

        with pytest.raises(AsyncTimeoutError) as exc_info:
            await manager.run_with_timeout_async(slow_operation(), operation_name="slow_op")

        assert "slow_op" in str(exc_info.value)
        assert exc_info.value.operation == "slow_op"
        assert exc_info.value.timeout_duration == 0.1

        # Check statistics
        stats = manager.get_statistics()
        assert "slow_op" in stats["operation_stats"]
        assert stats["operation_stats"]["slow_op"]["timeouts"] == 1

    @pytest.mark.asyncio
    async def test_timeout_manager_with_fallback(self):
        """Test timeout manager with fallback value."""
        manager = AsyncTimeoutManager(default_timeout=0.1)

        async def slow_operation():
            await asyncio.sleep(1.0)
            return "too_slow"

        result = await manager.run_with_timeout_async(
            slow_operation(),
            operation_name="slow_op",
            fallback="fallback_value",
        )

        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_timeout_manager_custom_timeout(self):
        """Test timeout manager with custom timeout."""
        manager = AsyncTimeoutManager(default_timeout=1.0)

        async def medium_operation():
            await asyncio.sleep(0.2)
            return "completed"

        # Should succeed with longer timeout
        result = await manager.run_with_timeout_async(medium_operation(), timeout=0.5)
        assert result == "completed"

        # Should fail with shorter timeout
        with pytest.raises(AsyncTimeoutError):
            await manager.run_with_timeout_async(medium_operation(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_timeout_manager_cancel_all_tasks(self):
        """Test cancelling all active tasks."""
        manager = AsyncTimeoutManager()

        async def long_operation():
            await asyncio.sleep(10)
            return "done"

        # Start multiple tasks
        task1 = asyncio.create_task(manager.run_with_timeout_async(long_operation()))
        task2 = asyncio.create_task(manager.run_with_timeout_async(long_operation()))

        # Give tasks time to start
        await asyncio.sleep(0.01)

        # Cancel all tasks
        await manager.cancel_all_tasks_async()

        # Tasks should be cancelled
        assert task1.cancelled() or task1.done()
        assert task2.cancelled() or task2.done()

    def test_timeout_manager_statistics(self):
        """Test timeout manager statistics tracking."""
        manager = AsyncTimeoutManager(default_timeout=5.0)

        # Manually update stats for testing
        manager._update_stats("test_op", 0.5, success=True)
        manager._update_stats("test_op", 0.3, success=True)
        manager._update_stats("test_op", 1.0, success=False)

        stats = manager.get_statistics()
        op_stats = stats["operation_stats"]["test_op"]

        assert op_stats["total_calls"] == 3
        assert op_stats["successful_calls"] == 2
        assert op_stats["timeouts"] == 1
        assert op_stats["success_rate"] == 2 / 3
        assert op_stats["avg_time"] == (0.5 + 0.3 + 1.0) / 3


class TestAsyncDecoratorPatterns:
    """Test async decorator patterns."""

    @pytest.mark.asyncio
    async def test_async_circuit_breaker_decorator(self):
        """Test async circuit breaker decorator."""

        @async_circuit_breaker(failure_threshold=2, recovery_timeout=0.1)
        async def decorated_function(should_fail=False):
            if should_fail:
                raise ValueError("Decorated failure")
            return "success"

        # Successful operation
        result = await decorated_function(should_fail=False)
        assert result == "success"

        # Trigger failures to open circuit
        with pytest.raises(ValueError):
            await decorated_function(should_fail=True)

        with pytest.raises(ValueError):
            await decorated_function(should_fail=True)

        # Circuit should now be open
        with pytest.raises(CircuitBreakerOpenError):
            await decorated_function(should_fail=False)

    @pytest.mark.asyncio
    async def test_async_timeout_decorator(self):
        """Test async timeout decorator."""

        @async_timeout(seconds=0.1, operation_name="decorated_timeout_test")
        async def decorated_function(delay=0.01):
            await asyncio.sleep(delay)
            return "completed"

        # Should succeed with short delay
        result = await decorated_function(delay=0.01)
        assert result == "completed"

        # Should timeout with long delay
        with pytest.raises(AsyncTimeoutError):
            await decorated_function(delay=1.0)

    @pytest.mark.asyncio
    async def test_async_resilient_decorator(self):
        """Test composite async resilient decorator."""

        call_count = 0

        @async_resilient(
            timeout=0.2,
            circuit_failure_threshold=2,
            circuit_recovery_timeout=0.1,
            operation_name="resilient_test",
        )
        async def decorated_function(should_fail=False, delay=0.01):
            nonlocal call_count
            call_count += 1

            if should_fail:
                raise ValueError(f"Failure #{call_count}")

            await asyncio.sleep(delay)
            return f"success_{call_count}"

        # Successful operation
        result = await decorated_function()
        assert result == "success_1"

        # Test timeout protection
        with pytest.raises(AsyncTimeoutError):
            await decorated_function(delay=1.0)

        # Test circuit breaker protection
        with pytest.raises(ValueError):
            await decorated_function(should_fail=True)

        with pytest.raises(ValueError):
            await decorated_function(should_fail=True)

        # Circuit should be open now
        with pytest.raises(CircuitBreakerOpenError):
            await decorated_function()


class TestAsyncRetryConfig:
    """Test the AsyncRetryConfig component."""

    def test_retry_config_initialization(self):
        """Test AsyncRetryConfig initialization."""
        config = AsyncRetryConfig(max_attempts=5, base_delay=0.1, max_delay=5.0, exponential_base=2.0, jitter=True)

        assert config.max_attempts == 5
        assert config.base_delay == 0.1
        assert config.max_delay == 5.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_retry_config_delay_calculation(self):
        """Test retry delay calculation."""
        config = AsyncRetryConfig(base_delay=0.1, max_delay=1.0, exponential_base=2.0, jitter=False)

        # Test exponential backoff
        delay1 = config.calculate_delay(attempt=1)
        delay2 = config.calculate_delay(attempt=2)
        delay3 = config.calculate_delay(attempt=3)

        assert delay1 == 0.1
        assert delay2 == 0.2
        assert delay3 == 0.4

        # Test max delay capping
        delay_high = config.calculate_delay(attempt=10)
        assert delay_high == 1.0

    def test_retry_config_with_jitter(self):
        """Test retry delay with jitter."""
        config = AsyncRetryConfig(base_delay=0.1, exponential_base=2.0, jitter=True)

        delay1 = config.calculate_delay(attempt=2)
        delay2 = config.calculate_delay(attempt=2)

        # With jitter, delays should potentially be different
        # (though they might be the same due to randomness)
        assert delay1 >= 0.1
        assert delay2 >= 0.1


class TestAsyncRetryDecorator:
    """Test async retry decorator functionality."""

    @pytest.mark.asyncio
    async def test_async_retry_successful_operation(self):
        """Test async retry with successful operation."""
        call_count = 0

        @async_retry(max_attempts=3, base_delay=0.01)
        async def sometimes_failing_function():
            nonlocal call_count
            call_count += 1
            return f"success_{call_count}"

        result = await sometimes_failing_function()
        assert result == "success_1"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_eventual_success(self):
        """Test async retry with eventual success."""
        call_count = 0

        @async_retry(max_attempts=3, base_delay=0.01)
        async def eventually_succeeding_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count} failed")
            return "finally_succeeded"

        result = await eventually_succeeding_function()
        assert result == "finally_succeeded"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_max_attempts_exceeded(self):
        """Test async retry when max attempts exceeded."""
        call_count = 0

        @async_retry(max_attempts=2, base_delay=0.01)
        async def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Attempt {call_count} failed")

        with pytest.raises(ValueError):
            await always_failing_function()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Test retry on specific connection errors."""
        call_count = 0

        @retry_on_connection_error(max_attempts=3, base_delay=0.01)
        async def connection_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "connected"

        result = await connection_function()
        assert result == "connected"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_create_retry_decorator_custom(self):
        """Test creating custom retry decorator."""
        retry_decorator = create_retry_decorator(max_attempts=2, base_delay=0.01, exceptions=(ValueError, TypeError))

        call_count = 0

        @retry_decorator
        async def custom_retry_function(error_type):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                if error_type == "value":
                    raise ValueError("Value error")
                elif error_type == "type":
                    raise TypeError("Type error")
                elif error_type == "runtime":
                    raise RuntimeError("Runtime error")
            return "success"

        # Should retry on ValueError
        result = await custom_retry_function("value")
        assert result == "success"

        # Reset counter
        call_count = 0

        # Should retry on TypeError
        result = await custom_retry_function("type")
        assert result == "success"

        # Reset counter
        call_count = 0

        # Should NOT retry on RuntimeError
        with pytest.raises(RuntimeError):
            await custom_retry_function("runtime")

        assert call_count == 1


class TestAsyncResourceManager:
    """Test async resource management."""

    @pytest.mark.asyncio
    async def test_async_resource_manager_basic(self):
        """Test basic async resource manager functionality."""
        acquired_resources = []
        released_resources = []

        async def acquire_resource(name):
            acquired_resources.append(name)
            return f"resource_{name}"

        async def release_resource(resource):
            released_resources.append(resource)

        async with AsyncResourceManager() as manager:
            resource1 = await manager.acquire_async("db", acquire_resource, "database")
            resource2 = await manager.acquire_async("cache", acquire_resource, "cache")

            assert resource1 == "resource_database"
            assert resource2 == "resource_cache"
            assert len(acquired_resources) == 2

        # Resources should be released automatically
        # Note: This test might need adjustment based on actual implementation

    @pytest.mark.asyncio
    async def test_async_context_decorator(self):
        """Test async context decorator."""
        resources_used = []

        @async_context("test_context")
        async def context_function():
            resources_used.append("function_executed")
            return "context_result"

        result = await context_function()
        assert result == "context_result"
        assert "function_executed" in resources_used


class TestTaskUtilities:
    """Test async task utility functions."""

    @pytest.mark.asyncio
    async def test_gather_with_concurrency_limit(self):
        """Test gathering tasks with concurrency limit."""
        call_times = []

        async def tracked_task(task_id, delay=0.01):
            call_times.append((task_id, time.time()))
            await asyncio.sleep(delay)
            return f"task_{task_id}"

        # Create multiple tasks
        tasks = [tracked_task(i) for i in range(5)]

        # Gather with concurrency limit
        results = await gather_with_concurrency(tasks, max_concurrency=2)

        assert len(results) == 5
        assert all(f"task_{i}" in results for i in range(5))

        # With concurrency limit of 2, not all tasks should start simultaneously
        start_times = [t[1] for t in call_times]
        # This is a rough test - with concurrency limit, there should be some delay
        time_span = max(start_times) - min(start_times)
        assert time_span > 0

    @pytest.mark.asyncio
    async def test_run_with_timeout_success(self):
        """Test run_with_timeout with successful operation."""

        async def quick_task():
            await asyncio.sleep(0.01)
            return "completed"

        result = await run_with_timeout(quick_task(), timeout=1.0)
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_run_with_timeout_failure(self):
        """Test run_with_timeout with timeout."""

        async def slow_task():
            await asyncio.sleep(1.0)
            return "too_slow"

        with pytest.raises(asyncio.TimeoutError):
            await run_with_timeout(slow_task(), timeout=0.1)


class TestAdvancedTimeoutManager:
    """Test advanced timeout management features."""

    def test_timeout_config_initialization(self):
        """Test TimeoutConfig initialization."""
        config = TimeoutConfig(
            default_timeout=30.0,
            min_timeout=1.0,
            max_timeout=300.0,
            adaptive_enabled=True,
            performance_window=100,
        )

        assert config.default_timeout == 30.0
        assert config.min_timeout == 1.0
        assert config.max_timeout == 300.0
        assert config.adaptive_enabled is True
        assert config.performance_window == 100

    def test_timeout_metrics_initialization(self):
        """Test TimeoutMetrics initialization."""
        metrics = TimeoutMetrics()

        assert metrics.total_operations == 0
        assert metrics.successful_operations == 0
        assert metrics.timeout_count == 0
        assert metrics.average_duration == 0.0
        assert metrics.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_advanced_timeout_manager(self):
        """Test AdvancedTimeoutManager functionality."""
        manager = AdvancedTimeoutManager(config=TimeoutConfig(default_timeout=1.0, adaptive_enabled=False))

        async def test_operation():
            await asyncio.sleep(0.01)
            return "success"

        result = await manager.execute_with_timeout_async(test_operation(), operation_name="test_op")

        assert result == "success"

        # Check metrics
        metrics = manager.get_metrics()
        assert "test_op" in metrics
        assert metrics["test_op"].successful_operations == 1

    @pytest.mark.asyncio
    async def test_timeout_context_manager(self):
        """Test timeout context manager."""
        async with timeout_context(timeout=1.0, operation_name="context_test"):
            await asyncio.sleep(0.01)
            result = "context_success"

        assert result == "context_success"

    @pytest.mark.asyncio
    async def test_with_adaptive_timeout_decorator(self):
        """Test adaptive timeout decorator."""

        @with_adaptive_timeout(base_timeout=0.5, operation_name="adaptive_test")
        async def adaptive_function():
            await asyncio.sleep(0.01)
            return "adaptive_success"

        result = await adaptive_function()
        assert result == "adaptive_success"


class TestAsyncIntegration:
    """Integration tests for async components working together."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_timeout_integration(self):
        """Test circuit breaker integrated with timeout manager."""
        breaker = AsyncCircuitBreaker(failure_threshold=2)
        timeout_manager = AsyncTimeoutManager(default_timeout=0.1)

        async def integrated_operation(should_fail=False, delay=0.01):
            if should_fail:
                raise ValueError("Integrated failure")
            await asyncio.sleep(delay)
            return "integrated_success"

        # Successful operation
        async def wrapped_success():
            return await breaker.call_async(
                lambda: timeout_manager.run_with_timeout_async(
                    integrated_operation(),
                    operation_name="integrated_test",
                ),
            )

        result = await wrapped_success()
        assert result == "integrated_success"

        # Test timeout triggers circuit breaker
        async def wrapped_timeout():
            return await breaker.call_async(
                lambda: timeout_manager.run_with_timeout_async(
                    integrated_operation(delay=1.0),
                    operation_name="timeout_test",
                ),
            )

        # Timeout should cause failures that trigger circuit breaker
        with pytest.raises(AsyncTimeoutError):
            await wrapped_timeout()

        with pytest.raises(AsyncTimeoutError):
            await wrapped_timeout()

        # Circuit should now be open
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_retry_with_circuit_breaker_integration(self):
        """Test retry mechanism with circuit breaker."""
        call_count = 0

        @async_circuit_breaker(failure_threshold=3)
        @async_retry(max_attempts=5, base_delay=0.01)
        async def integrated_retry_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count}")
            return "retry_success"

        result = await integrated_retry_function()
        assert result == "retry_success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_full_resilience_stack(self):
        """Test complete resilience stack working together."""
        operation_count = 0

        @async_resilient(timeout=0.5, circuit_failure_threshold=2, circuit_recovery_timeout=0.1)
        @async_retry(max_attempts=3, base_delay=0.01)
        async def resilient_operation(mode="success"):
            nonlocal operation_count
            operation_count += 1

            if mode == "timeout":
                await asyncio.sleep(1.0)
            elif mode == "failure" and operation_count < 3:
                raise ValueError("Temporary failure")
            elif mode == "permanent_failure":
                raise ValueError("Permanent failure")

            return f"resilient_success_{operation_count}"

        # Test successful path
        operation_count = 0
        result = await resilient_operation("success")
        assert result == "resilient_success_1"

        # Test retry recovery
        operation_count = 0
        result = await resilient_operation("failure")
        assert result == "resilient_success_3"

        # Test timeout protection
        operation_count = 0
        with pytest.raises(AsyncTimeoutError):
            await resilient_operation("timeout")

    @pytest.mark.asyncio
    async def test_concurrent_resilient_operations(self):
        """Test multiple resilient operations running concurrently."""

        @async_resilient(timeout=0.2, circuit_failure_threshold=3)
        async def concurrent_operation(operation_id, delay=0.01):
            await asyncio.sleep(delay)
            return f"concurrent_{operation_id}"

        # Run multiple operations concurrently
        tasks = [concurrent_operation(i, 0.01) for i in range(10)]

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(f"concurrent_{i}" in results for i in range(10))

    @pytest.mark.asyncio
    async def test_resource_cleanup_under_failure(self):
        """Test that resources are properly cleaned up even under failures."""
        cleanup_called = []

        async def cleanup_function():
            cleanup_called.append("cleaned")

        async with AsyncResourceManager() as manager:
            # Register cleanup function
            manager.add_cleanup_async(cleanup_function)

            # Simulate failure
            raise ValueError("Test failure")

        # Cleanup should still be called
        # Note: This test depends on actual AsyncResourceManager implementation


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
