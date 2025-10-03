"""
Unit tests for resilience module (AsyncCircuitBreaker).

Tests circuit breaker functionality:
- State transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Failure threshold enforcement
- Recovery timeout behavior
- Exception handling and blocking
- Manual reset capability
- Status reporting
"""

from __future__ import annotations

import asyncio

import pytest

from hive_async.resilience import AsyncCircuitBreaker, CircuitState
from hive_errors import CircuitBreakerOpenError


class TestCircuitState:
    """Test CircuitState enum."""

    def test_circuit_states(self):
        """Test that all circuit states are defined."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestAsyncCircuitBreakerInitialization:
    """Test AsyncCircuitBreaker initialization."""

    def test_default_initialization(self):
        """Test circuit breaker with default values."""
        cb = AsyncCircuitBreaker()

        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60
        assert cb.expected_exception is Exception
        assert cb.name == "default"
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.state == CircuitState.CLOSED

    def test_custom_initialization(self):
        """Test circuit breaker with custom values."""
        cb = AsyncCircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            expected_exception=ValueError,
            name="test_breaker",
        )

        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30
        assert cb.expected_exception is ValueError
        assert cb.name == "test_breaker"
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""

    @pytest.mark.asyncio
    async def test_closed_state_allows_calls(self):
        """Test that CLOSED state allows function calls."""
        cb = AsyncCircuitBreaker(failure_threshold=3)

        async def success_func():
            return "success"

        result = await cb.call_async(success_func)

        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_transition_to_open_after_threshold(self):
        """Test transition from CLOSED to OPEN after threshold failures."""
        cb = AsyncCircuitBreaker(failure_threshold=3)

        async def failing_func():
            raise ValueError("Test error")

        # Fail threshold times
        for _i in range(3):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)

        # Circuit should now be OPEN
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    @pytest.mark.asyncio
    async def test_open_state_blocks_calls(self):
        """Test that OPEN state blocks all calls."""
        cb = AsyncCircuitBreaker(failure_threshold=2)

        async def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)

        assert cb.state == CircuitState.OPEN

        # Try to call when open - should raise CircuitBreakerOpenError
        async def any_func():
            return "should not execute"

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await cb.call_async(any_func)

        assert "Circuit breaker is OPEN" in str(exc_info.value)
        assert exc_info.value.failure_count == 2

    @pytest.mark.asyncio
    async def test_half_open_state_allows_test_call(self):
        """Test that HALF_OPEN state allows a test call."""
        cb = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=1)

        async def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Next call should transition to HALF_OPEN
        async def success_func():
            return "success"

        result = await cb.call_async(success_func)

        assert result == "success"
        assert cb.state == CircuitState.CLOSED  # Success closes the circuit
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        """Test that failure in HALF_OPEN reopens the circuit."""
        cb = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=1)

        async def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Next call transitions to HALF_OPEN, but fails
        with pytest.raises(ValueError):
            await cb.call_async(failing_func)

        # Circuit should be OPEN again
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerFailureHandling:
    """Test circuit breaker failure handling."""

    @pytest.mark.asyncio
    async def test_incremental_failure_count(self):
        """Test that failure count increments correctly."""
        cb = AsyncCircuitBreaker(failure_threshold=5)

        async def failing_func():
            raise ValueError("Test error")

        # Fail less than threshold
        for i in range(3):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)
            assert cb.failure_count == i + 1
            assert cb.state == CircuitState.CLOSED  # Still closed

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        """Test that success resets failure count."""
        cb = AsyncCircuitBreaker(failure_threshold=5)

        async def failing_func():
            raise ValueError("Test error")

        async def success_func():
            return "success"

        # Fail a few times
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)

        assert cb.failure_count == 3

        # Success should reset
        await cb.call_async(success_func)

        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_only_expected_exceptions_count(self):
        """Test that only expected exceptions count toward threshold."""
        cb = AsyncCircuitBreaker(
            failure_threshold=3,
            expected_exception=ValueError,
        )

        async def wrong_exception_func():
            raise TypeError("Not counted")

        # TypeError should not be caught by circuit breaker
        with pytest.raises(TypeError):
            await cb.call_async(wrong_exception_func)

        # Failure count should not increase
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery behavior."""

    @pytest.mark.asyncio
    async def test_recovery_timeout_enforcement(self):
        """Test that recovery timeout is enforced."""
        cb = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=2)

        async def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)

        assert cb.state == CircuitState.OPEN

        # Try immediately - should still be blocked
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call_async(failing_func)

        # Wait for recovery timeout
        await asyncio.sleep(2.1)

        # Should now allow test call (transitions to HALF_OPEN)
        async def success_func():
            return "success"

        result = await cb.call_async(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_manual_reset(self):
        """Test manual circuit breaker reset."""
        cb = AsyncCircuitBreaker(failure_threshold=2)

        async def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 2

        # Manual reset
        await cb.reset_async()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_failure_time is None


class TestCircuitBreakerProperties:
    """Test circuit breaker properties and status."""

    @pytest.mark.asyncio
    async def test_is_open_property(self):
        """Test is_open property."""
        cb = AsyncCircuitBreaker(failure_threshold=2)

        assert not cb.is_open

        async def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)

        assert cb.is_open

    def test_get_status(self):
        """Test get_status method."""
        cb = AsyncCircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            name="test_breaker",
        )

        status = cb.get_status()

        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["failure_threshold"] == 3
        assert status["recovery_timeout"] == 30
        assert status["last_failure_time"] is None


class TestCircuitBreakerConcurrency:
    """Test circuit breaker under concurrent load."""

    @pytest.mark.asyncio
    async def test_concurrent_failures(self):
        """Test circuit breaker with concurrent failures."""
        cb = AsyncCircuitBreaker(failure_threshold=5)

        async def failing_func():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")

        # Launch concurrent failing calls
        tasks = []
        for _ in range(10):
            tasks.append(cb.call_async(failing_func))

        # Gather results (all should fail)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should be exceptions
        assert all(isinstance(r, (ValueError, CircuitBreakerOpenError)) for r in results)

        # Circuit should be open
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_concurrent_success_and_failure(self):
        """Test circuit breaker with mixed concurrent calls."""
        cb = AsyncCircuitBreaker(failure_threshold=10)

        async def success_func():
            await asyncio.sleep(0.01)
            return "success"

        async def failing_func():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")

        # Launch mixed concurrent calls
        tasks = []
        for i in range(10):
            if i % 2 == 0:
                tasks.append(cb.call_async(success_func))
            else:
                tasks.append(cb.call_async(failing_func))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should have mix of successes and failures
        successes = [r for r in results if r == "success"],
        failures = [r for r in results if isinstance(r, ValueError)]

        assert len(successes) == 5
        assert len(failures) == 5
        assert cb.state == CircuitState.CLOSED  # Not enough failures


class TestCircuitBreakerFailureHistory:
    """Test circuit breaker failure history tracking."""

    @pytest.mark.asyncio
    async def test_failure_history_recorded(self):
        """Test that failure history is recorded."""
        cb = AsyncCircuitBreaker(failure_threshold=3)

        async def failing_func():
            raise ValueError("Test error")

        # Generate some failures
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)

        # Check failure history
        assert len(cb._failure_history) == 3
        for failure in cb._failure_history:
            assert "timestamp" in failure
            assert failure["error_type"] == "ValueError"
            assert "state_before" in failure

    @pytest.mark.asyncio
    async def test_state_transitions_recorded(self):
        """Test that state transitions are recorded."""
        cb = AsyncCircuitBreaker(failure_threshold=2)

        async def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call_async(failing_func)

        # Check state transitions
        assert len(cb._state_transitions) >= 1
        transition = cb._state_transitions[-1]
        assert transition["to_state"] == "open"
        assert transition["failure_count"] == 2
        assert "timestamp" in transition
