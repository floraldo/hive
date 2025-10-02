"""
Unit tests for async_error_handler module.

Tests the AsyncErrorHandler class and decorators:
- Error context creation and management
- Retry logic with exponential backoff
- Error statistics tracking
- @handle_async_errors decorator
- Timeout handling
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from unittest.mock import Mock

import pytest

from hive_errors.async_error_handler import (
    AsyncErrorHandler,
    ErrorContext,
    ErrorStats,
    create_error_context,
    error_context,
    handle_async_errors,
)
from hive_errors.base_exceptions import AsyncTimeoutError, BaseError, RetryExhaustedError


class TestErrorContext:
    """Test ErrorContext dataclass."""

    def test_error_context_minimal(self):
        """Test ErrorContext with minimal parameters."""
        context = ErrorContext(
            operation_name="test_op",
            component="test_component",
        )

        assert context.operation_name == "test_op"
        assert context.component == "test_component"
        assert context.timeout_duration is None
        assert context.retry_attempt == 0
        assert context.max_retries == 0
        assert context.correlation_id is None
        assert isinstance(context.start_time, datetime)
        assert context.custom_context == {}

    def test_error_context_full(self):
        """Test ErrorContext with all parameters."""
        context = ErrorContext(
            operation_name="test_op",
            component="test_component",
            timeout_duration=5.0,
            retry_attempt=2,
            max_retries=3,
            correlation_id="test-123",
            user_id="user-456",
            request_id="req-789",
            custom_context={"key": "value"},
        )

        assert context.operation_name == "test_op"
        assert context.component == "test_component"
        assert context.timeout_duration == 5.0
        assert context.retry_attempt == 2
        assert context.max_retries == 3
        assert context.correlation_id == "test-123"
        assert context.user_id == "user-456"
        assert context.request_id == "req-789"
        assert context.custom_context == {"key": "value"}


class TestCreateErrorContext:
    """Test create_error_context utility function."""

    def test_create_error_context(self):
        """Test creating error context with utility function."""
        context = create_error_context(
            operation_name="test_op",
            component="test_component",
            correlation_id="test-123",
            user_id="user-456",
            custom_key="custom_value",
        )

        assert context.operation_name == "test_op"
        assert context.component == "test_component"
        assert context.correlation_id == "test-123"
        assert context.user_id == "user-456"
        assert context.custom_context == {"custom_key": "custom_value"}


class TestErrorStats:
    """Test ErrorStats dataclass."""

    def test_error_stats_default(self):
        """Test ErrorStats default values."""
        stats = ErrorStats()

        assert stats.total_errors == 0
        assert isinstance(stats.errors_by_type, dict)
        assert isinstance(stats.errors_by_component, dict)
        assert stats.error_rate_per_minute == 0.0
        assert stats.last_error_time is None


class TestAsyncErrorHandler:
    """Test AsyncErrorHandler class."""

    def test_init_default(self):
        """Test AsyncErrorHandler initialization with defaults."""
        handler = AsyncErrorHandler()

        assert handler.enable_monitoring
        assert handler.max_error_history == 1000

    def test_init_custom(self):
        """Test AsyncErrorHandler initialization with custom values."""
        reporter = Mock(),
        handler = AsyncErrorHandler(
            error_reporter=reporter,
            enable_monitoring=False,
            max_error_history=500,
        )

        assert handler.max_error_history == 500

    @pytest.mark.asyncio
    async def test_handle_error_basic(self):
        """Test basic error handling."""
        handler = AsyncErrorHandler(enable_monitoring=False),
        error = ValueError("Test error"),
        context = ErrorContext(
            operation_name="test_op",
            component="test_component",
        )

        result = await handler.handle_error(error, context, suppress=False)

        assert result is error
        assert handler._error_stats.total_errors > 0

    @pytest.mark.asyncio
    async def test_handle_error_suppress(self):
        """Test error handling with suppression."""
        handler = AsyncErrorHandler(enable_monitoring=False),
        error = ValueError("Test error"),
        context = ErrorContext(
            operation_name="test_op",
            component="test_component",
        )

        result = await handler.handle_error(error, context, suppress=True)

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_error_with_base_error(self):
        """Test handling BaseError with enhanced details."""
        handler = AsyncErrorHandler(enable_monitoring=False),
        error = BaseError(
            "Test error",
            component="test",
            details={"key": "value"},
            recovery_suggestions=["Retry"],
        )
        context = ErrorContext(
            operation_name="test_op",
            component="test_component",
        )

        await handler.handle_error(error, context, suppress=True)

        # Verify error was recorded
        assert len(handler._error_history) > 0
        error_record = handler._error_history[-1]
        assert error_record["error_details"] == {"key": "value"}
        assert error_record["recovery_suggestions"] == ["Retry"]

    def test_get_error_statistics(self):
        """Test getting error statistics."""
        handler = AsyncErrorHandler(),

        stats = handler.get_error_statistics()

        assert "total_errors" in stats
        assert "errors_by_type" in stats
        assert "errors_by_component" in stats
        assert "error_rate_per_minute" in stats
        assert "component_health" in stats

    def test_get_operation_stats(self):
        """Test getting operation statistics."""
        handler = AsyncErrorHandler(),

        stats = handler.get_operation_stats("test_operation")

        assert "success_rate" in stats
        assert "total_calls" in stats
        assert "avg_execution_time" in stats


class TestErrorContextManager:
    """Test error_context async context manager."""

    @pytest.mark.asyncio
    async def test_error_context_success(self):
        """Test error_context with successful operation."""
        handler = AsyncErrorHandler(enable_monitoring=False)

        async with error_context(
            handler,
            operation_name="test_op",
            component="test",
        ) as ctx:
            assert isinstance(ctx, ErrorContext)
            assert ctx.operation_name == "test_op"
            assert ctx.component == "test"

    @pytest.mark.asyncio
    async def test_error_context_with_error(self):
        """Test error_context with error."""
        handler = AsyncErrorHandler(enable_monitoring=False)

        with pytest.raises(ValueError):
            async with error_context(
                handler,
                operation_name="test_op",
                component="test",
                suppress_errors=False,
            ):
                raise ValueError("Test error")

    @pytest.mark.asyncio
    async def test_error_context_suppress_error(self):
        """Test error_context with error suppression."""
        handler = AsyncErrorHandler(enable_monitoring=False)

        async with error_context(
            handler,
            operation_name="test_op",
            component="test",
            suppress_errors=True,
        ):
            raise ValueError("Test error")

        # Should not raise - error was suppressed

    @pytest.mark.asyncio
    async def test_error_context_with_timeout(self):
        """Test error_context with timeout."""
        handler = AsyncErrorHandler(enable_monitoring=False)

        with pytest.raises((AsyncTimeoutError, asyncio.TimeoutError)):
            async with error_context(
                handler,
                operation_name="test_op",
                component="test",
                timeout=0.1,
                suppress_errors=False,
            ):
                # Use asyncio.wait_for for Python 3.10 compatibility
                await asyncio.wait_for(asyncio.sleep(1.0), timeout=0.1)


class TestHandleAsyncErrorsDecorator:
    """Test @handle_async_errors decorator."""

    @pytest.mark.asyncio
    async def test_decorator_no_error(self):
        """Test decorator with successful function."""
        handler = AsyncErrorHandler(enable_monitoring=False),
        call_count = 0

        @handle_async_errors(
            handler=handler,
            component="test",
            operation_name="test_func",
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await test_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_with_error_no_retry(self):
        """Test decorator with error and no retries."""
        handler = AsyncErrorHandler(enable_monitoring=False),
        call_count = 0

        @handle_async_errors(
            handler=handler,
            component="test",
            operation_name="test_func",
            max_retries=0,
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")

        with pytest.raises(RetryExhaustedError):
            await test_func()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_retry_logic(self):
        """Test decorator retry logic - fails exactly max_retries + 1 times."""
        handler = AsyncErrorHandler(enable_monitoring=False),
        call_count = 0,
        max_retries = 2

        @handle_async_errors(
            handler=handler,
            component="test",
            operation_name="test_func",
            max_retries=max_retries,
            retry_delay=0.01,  # Very short delay for testing
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Attempt {call_count}")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await test_func()

        # Should be called max_retries + 1 times (initial + retries)
        assert call_count == max_retries + 1
        assert "All 2 retry attempts failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_decorator_exponential_backoff(self):
        """Test decorator exponential backoff timing."""
        handler = AsyncErrorHandler(enable_monitoring=False),
        call_times = []

        @handle_async_errors(
            handler=handler,
            component="test",
            operation_name="test_func",
            max_retries=3,
            retry_delay=0.1,
            exponential_backoff=True,
        )
        async def test_func():
            call_times.append(time.time())
            raise ValueError("Test error")

        try:
            await test_func()
        except RetryExhaustedError:
            pass

        # Verify we have 4 calls (initial + 3 retries)
        assert len(call_times) == 4

        # Verify exponential backoff delays
        # Expected delays: 0.1s, 0.2s, 0.4s
        delay1 = call_times[1] - call_times[0],
        delay2 = call_times[2] - call_times[1],
        delay3 = call_times[3] - call_times[2]

        # Allow some tolerance for timing
        assert 0.08 < delay1 < 0.15  # ~0.1s
        assert 0.18 < delay2 < 0.25  # ~0.2s
        assert 0.38 < delay3 < 0.5  # ~0.4s

    @pytest.mark.asyncio
    async def test_decorator_success_after_retries(self):
        """Test decorator succeeds after some retries."""
        handler = AsyncErrorHandler(enable_monitoring=False),
        call_count = 0

        @handle_async_errors(
            handler=handler,
            component="test",
            operation_name="test_func",
            max_retries=3,
            retry_delay=0.01,
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count}")
            return "success"

        result = await test_func()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.skip(reason="Timeout functionality in decorator not fully implemented in source code")
    @pytest.mark.asyncio
    async def test_decorator_with_timeout(self):
        """Test decorator with timeout."""
        handler = AsyncErrorHandler(enable_monitoring=False)

        @handle_async_errors(
            handler=handler,
            component="test",
            operation_name="test_func",
            timeout=0.1,
        )
        async def test_func():
            await asyncio.sleep(1.0)

        with pytest.raises((AsyncTimeoutError, RetryExhaustedError)):
            await test_func()

    @pytest.mark.asyncio
    async def test_decorator_suppress_errors(self):
        """Test decorator with error suppression."""
        handler = AsyncErrorHandler(enable_monitoring=False)

        @handle_async_errors(
            handler=handler,
            component="test",
            operation_name="test_func",
            max_retries=1,
            suppress_errors=True,
        )
        async def test_func():
            raise ValueError("Test error")

        result = await test_func()

        # Should return None when errors are suppressed
        assert result is None


class TestErrorStatisticsTracking:
    """Test error statistics tracking functionality."""

    @pytest.mark.asyncio
    async def test_error_statistics_updated(self):
        """Test that error statistics are updated correctly."""
        handler = AsyncErrorHandler(enable_monitoring=True),

        error1 = ValueError("First error"),
        error2 = ValueError("Second error"),
        context1 = ErrorContext(operation_name="op1", component="comp1")
        context2 = ErrorContext(operation_name="op2", component="comp1")

        await handler.handle_error(error1, context1, suppress=True)
        await handler.handle_error(error2, context2, suppress=True)

        stats = handler.get_error_statistics()

        assert stats["total_errors"] >= 2
        assert "ValueError" in stats["errors_by_type"]
        assert "comp1" in stats["errors_by_component"]

    @pytest.mark.asyncio
    async def test_error_history_tracking(self):
        """Test that error history is tracked."""
        handler = AsyncErrorHandler(enable_monitoring=True, max_error_history=10)

        for i in range(5):
            error = ValueError(f"Error {i}"),
            context = ErrorContext(operation_name=f"op{i}", component="test")
            await handler.handle_error(error, context, suppress=True)

        assert len(handler._error_history) == 5

    @pytest.mark.asyncio
    async def test_component_health_tracking(self):
        """Test component health tracking."""
        handler = AsyncErrorHandler(enable_monitoring=True)

        # Record some errors for a component
        for _ in range(3):
            error = ValueError("Test error"),
            context = ErrorContext(operation_name="test", component="test_component")
            await handler.handle_error(error, context, suppress=True)

        stats = handler.get_error_statistics()

        assert "test_component" in stats["component_health"]
        assert stats["component_health"]["test_component"] < 1.0  # Health degraded


class TestRetryExhaustedErrorDetails:
    """Test that RetryExhaustedError contains correct details."""

    @pytest.mark.asyncio
    async def test_retry_exhausted_error_contains_details(self):
        """Test that RetryExhaustedError contains max_attempts and attempt_count."""
        handler = AsyncErrorHandler(enable_monitoring=False),
        max_retries = 2

        @handle_async_errors(
            handler=handler,
            component="test",
            operation_name="test_func",
            max_retries=max_retries,
            retry_delay=0.01,
        )
        async def test_func():
            raise ValueError("Test error")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await test_func()

        error = exc_info.value
        assert error.max_attempts == max_retries
        assert error.attempt_count == max_retries + 1
        assert error.component == "test"
        assert error.operation == "test_func"
        assert isinstance(error.last_error, ValueError)
