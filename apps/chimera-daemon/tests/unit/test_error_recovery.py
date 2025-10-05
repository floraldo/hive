"""Unit tests for error recovery components.

Tests retry policy, circuit breaker, and dead letter queue functionality.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from chimera_daemon.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
)
from chimera_daemon.dlq import DeadLetterQueue
from chimera_daemon.retry import BackoffStrategy, RetryConfig, RetryPolicy

# ============================================================================
# RetryPolicy Tests
# ============================================================================


class TestRetryPolicy:
    """Test RetryPolicy with exponential backoff and jitter."""

    @pytest.mark.asyncio
    async def test_successful_operation_no_retry(self):
        """Operation succeeds on first attempt - no retries needed."""
        policy = RetryPolicy(config=RetryConfig(max_retries=3))

        call_count = 0

        async def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await policy.execute(successful_operation)

        assert result == "success"
        assert call_count == 1  # Called only once

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Operation fails then succeeds - retries until success."""
        policy = RetryPolicy(
            config=RetryConfig(
                max_retries=3,
                base_delay_ms=10,  # Fast for testing
            )
        )

        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = await policy.execute(flaky_operation)

        assert result == "success"
        assert call_count == 3  # Failed twice, succeeded on 3rd

    @pytest.mark.asyncio
    async def test_exhaust_all_retries(self):
        """Operation fails on all retries - raises final exception."""
        policy = RetryPolicy(
            config=RetryConfig(
                max_retries=2,
                base_delay_ms=10,
            )
        )

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Persistent failure")

        with pytest.raises(RuntimeError, match="Persistent failure"):
            await policy.execute(always_fails)

        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Verify exponential backoff delays increase."""
        policy = RetryPolicy(
            config=RetryConfig(
                max_retries=3,
                base_delay_ms=100,
                backoff_strategy=BackoffStrategy.EXPONENTIAL,
            )
        )

        delays = []
        start_time = datetime.now()

        async def failing_operation():
            delays.append((datetime.now() - start_time).total_seconds() * 1000)
            raise ValueError("Test failure")

        with pytest.raises(ValueError):
            await policy.execute(failing_operation)

        # Verify delays are increasing (allowing for jitter)
        # First call: ~0ms, Second: ~100ms, Third: ~200ms, Fourth: ~400ms
        assert len(delays) == 4  # Initial + 3 retries
        assert delays[0] < 50  # First call immediate
        assert delays[1] > 50  # Second call after ~100ms delay
        assert delays[2] > 150  # Third call after ~200ms delay
        assert delays[3] > 350  # Fourth call after ~400ms delay

    @pytest.mark.asyncio
    async def test_linear_backoff(self):
        """Verify linear backoff delays increase linearly."""
        policy = RetryPolicy(
            config=RetryConfig(
                max_retries=2,
                base_delay_ms=50,
                backoff_strategy=BackoffStrategy.LINEAR,
            )
        )

        delays = []
        start_time = datetime.now()

        async def failing_operation():
            delays.append((datetime.now() - start_time).total_seconds() * 1000)
            raise ValueError("Test failure")

        with pytest.raises(ValueError):
            await policy.execute(failing_operation)

        # Linear: delay = n * base_delay
        # First: ~0ms, Second: ~50ms, Third: ~100ms
        assert len(delays) == 3
        assert delays[1] > 40  # ~50ms delay
        assert delays[2] > 90  # ~100ms delay (50 + 50)

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Verify delays are capped at max_delay_ms."""
        policy = RetryPolicy(
            config=RetryConfig(
                max_retries=5,
                base_delay_ms=1000,
                max_delay_ms=2000,  # Cap at 2 seconds
                backoff_strategy=BackoffStrategy.EXPONENTIAL,
            )
        )

        # Exponential would be: 1s, 2s, 4s, 8s, 16s
        # But capped at 2s: 1s, 2s, 2s, 2s, 2s

        delays_actual = []
        for attempt in range(1, 6):
            delay = policy._calculate_delay(attempt)
            delays_actual.append(delay)

        # All delays should be <= 2000ms (with jitter allowance)
        for delay in delays_actual:
            assert delay <= 2200  # 2000 + 10% jitter

    @pytest.mark.asyncio
    async def test_retryable_errors_filter(self):
        """Only retry errors in retryable_errors list."""
        policy = RetryPolicy(
            config=RetryConfig(
                max_retries=3,
                base_delay_ms=10,
                retryable_errors=[ValueError],  # Only retry ValueError
            )
        )

        # ValueError should be retried
        call_count_value_error = 0

        async def raises_value_error():
            nonlocal call_count_value_error
            call_count_value_error += 1
            if call_count_value_error < 2:
                raise ValueError("Retryable")
            return "success"

        result = await policy.execute(raises_value_error)
        assert result == "success"
        assert call_count_value_error == 2

        # RuntimeError should NOT be retried
        call_count_runtime_error = 0

        async def raises_runtime_error():
            nonlocal call_count_runtime_error
            call_count_runtime_error += 1
            raise RuntimeError("Non-retryable")

        with pytest.raises(RuntimeError, match="Non-retryable"):
            await policy.execute(raises_runtime_error)

        assert call_count_runtime_error == 1  # No retries


# ============================================================================
# CircuitBreaker Tests
# ============================================================================


class TestCircuitBreaker:
    """Test CircuitBreaker state transitions and failure protection."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        """Circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker(name="test")

        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
        assert not breaker.is_half_open

    @pytest.mark.asyncio
    async def test_successful_calls_stay_closed(self):
        """Successful calls keep circuit CLOSED."""
        breaker = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(failure_threshold=3),
        )

        async def successful_operation():
            return "success"

        for _ in range(5):
            result = await breaker.call(successful_operation)
            assert result == "success"

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_threshold_opens_circuit(self):
        """Circuit opens after reaching failure threshold."""
        breaker = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                timeout_seconds=1,
            ),
        )

        async def failing_operation():
            raise RuntimeError("Operation failed")

        # Fail 3 times to reach threshold
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_operation)

        # Circuit should now be OPEN
        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open

    @pytest.mark.asyncio
    async def test_open_circuit_blocks_requests(self):
        """OPEN circuit blocks all requests immediately."""
        breaker = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(
                failure_threshold=2,
                timeout_seconds=10,
            ),
        )

        async def failing_operation():
            raise RuntimeError("Failure")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_operation)

        assert breaker.is_open

        # Next call should be blocked immediately
        with pytest.raises(CircuitBreakerError, match="OPEN - blocking request"):
            await breaker.call(failing_operation)

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        """Circuit transitions to HALF_OPEN after timeout."""
        breaker = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(
                failure_threshold=2,
                timeout_seconds=0.1,  # 100ms timeout
            ),
        )

        async def failing_operation():
            raise RuntimeError("Failure")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_operation)

        assert breaker.is_open

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Check state - should be HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        """Successful calls in HALF_OPEN close the circuit."""
        breaker = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(
                failure_threshold=2,
                success_threshold=2,
                timeout_seconds=0.1,
            ),
        )

        async def failing_then_succeeding():
            return "success"

        # Open the circuit
        async def failing():
            raise RuntimeError("Fail")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing)

        assert breaker.is_open

        # Wait for timeout to HALF_OPEN
        await asyncio.sleep(0.15)
        assert breaker.is_half_open

        # Succeed twice to close
        for _ in range(2):
            result = await breaker.call(failing_then_succeeding)
            assert result == "success"

        # Should be CLOSED now
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        """Failure in HALF_OPEN immediately reopens circuit."""
        breaker = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(
                failure_threshold=2,
                timeout_seconds=0.1,
            ),
        )

        async def failing():
            raise RuntimeError("Fail")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing)

        assert breaker.is_open

        # Wait for HALF_OPEN
        await asyncio.sleep(0.15)
        assert breaker.is_half_open

        # Fail once - should immediately reopen
        with pytest.raises(RuntimeError):
            await breaker.call(failing)

        assert breaker.is_open

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """Circuit breaker works with async context manager."""
        breaker = CircuitBreaker(name="test")

        async with breaker:
            result = "operation succeeded"

        assert result == "operation succeeded"
        assert breaker.is_closed

    @pytest.mark.asyncio
    async def test_context_manager_failure(self):
        """Circuit breaker context manager handles failures."""
        breaker = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(failure_threshold=2),
        )

        # Fail twice to open circuit
        for _ in range(2):
            try:
                async with breaker:
                    raise ValueError("Operation failed")
            except ValueError:
                pass

        assert breaker.is_open

        # Next attempt should be blocked
        with pytest.raises(CircuitBreakerError):
            async with breaker:
                pass

    @pytest.mark.asyncio
    async def test_get_metrics(self):
        """Circuit breaker provides accurate metrics."""
        breaker = CircuitBreaker(
            name="test_circuit",
            config=CircuitBreakerConfig(failure_threshold=3),
        )

        async def operation(should_fail: bool):
            if should_fail:
                raise RuntimeError("Failed")
            return "success"

        # 2 successes
        await breaker.call(operation, False)
        await breaker.call(operation, False)

        # 1 failure
        try:
            await breaker.call(operation, True)
        except RuntimeError:
            pass

        metrics = breaker.get_metrics()

        assert metrics["name"] == "test_circuit"
        assert metrics["state"] == "closed"
        assert metrics["failure_count"] == 1
        assert metrics["failure_rate"] == pytest.approx(0.333, abs=0.01)  # 1/3
        assert metrics["recent_calls"] == 3


# ============================================================================
# DeadLetterQueue Tests
# ============================================================================


class TestDeadLetterQueue:
    """Test Dead Letter Queue functionality."""

    @pytest.fixture
    async def dlq(self, tmp_path: Path):
        """Create DLQ with temporary database."""
        db_path = tmp_path / "test_dlq.db"
        queue = DeadLetterQueue(db_path=db_path)
        await queue.initialize()
        return queue

    @pytest.mark.asyncio
    async def test_add_and_get_entry(self, dlq: DeadLetterQueue):
        """Add entry to DLQ and retrieve it."""
        await dlq.add_entry(
            task_id="task-123",
            feature="Test feature",
            target_url="https://example.com",
            failure_reason="All retries exhausted",
            retry_count=3,
            workflow_state={"phase": "E2E_VALIDATION"},
            last_error_phase="E2E_VALIDATION",
        )

        entry = await dlq.get_entry("task-123")

        assert entry is not None
        assert entry.task_id == "task-123"
        assert entry.feature == "Test feature"
        assert entry.target_url == "https://example.com"
        assert entry.failure_reason == "All retries exhausted"
        assert entry.retry_count == 3
        assert entry.workflow_state == {"phase": "E2E_VALIDATION"}
        assert entry.last_error_phase == "E2E_VALIDATION"

    @pytest.mark.asyncio
    async def test_get_entries_newest_first(self, dlq: DeadLetterQueue):
        """Get entries returns newest first."""
        # Add 3 entries with small delay
        for i in range(3):
            await dlq.add_entry(
                task_id=f"task-{i}",
                feature=f"Feature {i}",
                target_url="https://example.com",
                failure_reason="Failed",
                retry_count=3,
            )
            await asyncio.sleep(0.01)  # Ensure different timestamps

        entries = await dlq.get_entries(limit=10)

        assert len(entries) == 3
        # Newest first (task-2, task-1, task-0)
        assert entries[0].task_id == "task-2"
        assert entries[1].task_id == "task-1"
        assert entries[2].task_id == "task-0"

    @pytest.mark.asyncio
    async def test_get_entries_pagination(self, dlq: DeadLetterQueue):
        """Get entries supports limit and offset."""
        # Add 5 entries
        for i in range(5):
            await dlq.add_entry(
                task_id=f"task-{i}",
                feature=f"Feature {i}",
                target_url="https://example.com",
                failure_reason="Failed",
                retry_count=3,
            )

        # Get first 2
        page1 = await dlq.get_entries(limit=2, offset=0)
        assert len(page1) == 2
        assert page1[0].task_id == "task-4"  # Newest
        assert page1[1].task_id == "task-3"

        # Get next 2
        page2 = await dlq.get_entries(limit=2, offset=2)
        assert len(page2) == 2
        assert page2[0].task_id == "task-2"
        assert page2[1].task_id == "task-1"

    @pytest.mark.asyncio
    async def test_remove_entry(self, dlq: DeadLetterQueue):
        """Remove entry from DLQ."""
        await dlq.add_entry(
            task_id="task-remove",
            feature="Test",
            target_url="https://example.com",
            failure_reason="Failed",
            retry_count=3,
        )

        # Verify it exists
        entry = await dlq.get_entry("task-remove")
        assert entry is not None

        # Remove it
        removed = await dlq.remove_entry("task-remove")
        assert removed is True

        # Verify it's gone
        entry = await dlq.get_entry("task-remove")
        assert entry is None

        # Remove non-existent
        removed = await dlq.remove_entry("nonexistent")
        assert removed is False

    @pytest.mark.asyncio
    async def test_count(self, dlq: DeadLetterQueue):
        """Count total entries in DLQ."""
        assert await dlq.count() == 0

        # Add 3 entries
        for i in range(3):
            await dlq.add_entry(
                task_id=f"task-{i}",
                feature="Test",
                target_url="https://example.com",
                failure_reason="Failed",
                retry_count=3,
            )

        assert await dlq.count() == 3

        # Remove one
        await dlq.remove_entry("task-1")

        assert await dlq.count() == 2

    @pytest.mark.asyncio
    async def test_entry_preserves_creation_time(self, dlq: DeadLetterQueue):
        """DLQ preserves original task creation time."""
        original_created = datetime(2025, 1, 1, 12, 0, 0)

        await dlq.add_entry(
            task_id="task-time",
            feature="Test",
            target_url="https://example.com",
            failure_reason="Failed",
            retry_count=3,
            created_at=original_created,
        )

        entry = await dlq.get_entry("task-time")

        assert entry.created_at == original_created
        assert entry.failed_at > original_created  # Failed later
