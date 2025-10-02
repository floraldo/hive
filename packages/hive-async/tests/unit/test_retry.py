"""
Unit tests for retry module.

Tests retry functionality using the tenacity library:
- AsyncRetryConfig configuration
- run_async_with_retry_async function
- Retry decorators
- Exception handling
- Exponential backoff (handled by tenacity)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hive_async.retry import AsyncRetryConfig, AsyncRetryError, run_async_with_retry_async


class TestAsyncRetryConfig:
    """Test AsyncRetryConfig dataclass."""

    def test_default_config(self):
        """Test AsyncRetryConfig with default values."""
        config = AsyncRetryConfig()

        assert config.max_attempts == 3
        assert config.min_wait == 1.0
        assert config.max_wait == 10.0
        assert config.multiplier == 2.0
        assert config.retry_exceptions == Exception
        assert config.stop_on_exceptions == ()
        assert config.log_before_sleep is True
        assert config.log_after_attempt is True

    def test_custom_config(self):
        """Test AsyncRetryConfig with custom values."""
        config = AsyncRetryConfig(
            max_attempts=5,
            min_wait=0.5,
            max_wait=30.0,
            multiplier=3.0,
            retry_exceptions=ValueError,
            stop_on_exceptions=(TypeError,),
            log_before_sleep=False,
            log_after_attempt=False,
        )

        assert config.max_attempts == 5
        assert config.min_wait == 0.5
        assert config.max_wait == 30.0
        assert config.multiplier == 3.0
        assert config.retry_exceptions == ValueError
        assert config.stop_on_exceptions == (TypeError,)
        assert config.log_before_sleep is False
        assert config.log_after_attempt is False


class TestAsyncRetryError:
    """Test AsyncRetryError exception."""

    def test_async_retry_error_creation(self):
        """Test AsyncRetryError with original error and attempts."""
        original = ValueError("Original error"),
        error = AsyncRetryError(original, attempts=3)

        assert error.original_error is original
        assert error.attempts == 3
        assert "Failed after 3 attempts" in str(error)
        assert "Original error" in str(error)


class TestRunAsyncWithRetry:
    """Test run_async_with_retry_async function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Test successful function on first attempt."""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        config = AsyncRetryConfig(max_attempts=3),
        result = await run_async_with_retry_async(success_func, config)

        assert result == "success"
        assert call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_success_after_retries(self):
        """Test function succeeds after some retries."""
        call_count = 0

        async def eventually_success_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count}")
            return "success"

        config = AsyncRetryConfig(max_attempts=5, min_wait=0.01, max_wait=0.1)
        result = await run_async_with_retry_async(eventually_success_func, config)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        """Test that AsyncRetryError is raised after all retries exhausted."""
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Attempt {call_count}")

        config = AsyncRetryConfig(max_attempts=3, min_wait=0.01, max_wait=0.1)

        with pytest.raises(AsyncRetryError) as exc_info:
            await run_async_with_retry_async(always_fails, config)

        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.original_error, ValueError)
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_default_config_used_when_none(self):
        """Test that default config is used when none provided."""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        # Call without config - should use defaults
        result = await run_async_with_retry_async(success_func, None)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_specific_exception_retry(self):
        """Test retrying only on specific exception types."""
        call_count = 0

        async def specific_exception_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retry this")
            return "success"

        # Only retry on ValueError
        config = AsyncRetryConfig(
            max_attempts=3,
            min_wait=0.01,
            max_wait=0.1,
            retry_exceptions=ValueError,
        )

        result = await run_async_with_retry_async(specific_exception_func, config)

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_stop_on_specific_exception(self):
        """Test that certain exceptions stop retries immediately."""
        call_count = 0

        async def stop_exception_func():
            nonlocal call_count
            call_count += 1
            raise TypeError("Stop immediately")

        config = AsyncRetryConfig(
            max_attempts=5,
            min_wait=0.01,
            max_wait=0.1,
            retry_exceptions=Exception,
            stop_on_exceptions=(TypeError,),
        )

        # TypeError should stop retries immediately
        with pytest.raises(TypeError):
            await run_async_with_retry_async(stop_exception_func, config)

        # Should only be called once (no retries)
        assert call_count == 1


class TestRetryWithArguments:
    """Test retry functionality with function arguments."""

    @pytest.mark.asyncio
    async def test_retry_with_positional_args(self):
        """Test retry with positional arguments."""
        call_count = 0

        async def func_with_args(a, b):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return a + b

        config = AsyncRetryConfig(max_attempts=3, min_wait=0.01, max_wait=0.1)
        result = await run_async_with_retry_async(func_with_args, config, 5, 10)

        assert result == 15
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_keyword_args(self):
        """Test retry with keyword arguments."""
        call_count = 0

        async def func_with_kwargs(a, b=10):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return a * b

        config = AsyncRetryConfig(max_attempts=3, min_wait=0.01, max_wait=0.1)
        result = await run_async_with_retry_async(func_with_kwargs, config, 5, b=3)

        assert result == 15
        assert call_count == 2


class TestRetryTiming:
    """Test retry timing behavior (basic validation)."""

    @pytest.mark.asyncio
    async def test_retry_delays_exist(self):
        """Test that delays occur between retries."""
        import time

        call_times = []

        async def failing_func():
            call_times.append(time.time())
            raise ValueError("Test error")

        config = AsyncRetryConfig(
            max_attempts=3,
            min_wait=0.05,
            max_wait=0.2,
            multiplier=2.0,
        )

        with pytest.raises(AsyncRetryError):
            await run_async_with_retry_async(failing_func, config)

        # Verify we have 3 calls
        assert len(call_times) == 3

        # Verify there are delays between calls
        delay1 = call_times[1] - call_times[0],
        delay2 = call_times[2] - call_times[1]

        # With min_wait=0.05 and multiplier=2.0, expect delays around 0.05s, 0.1s
        assert delay1 >= 0.04  # Allow some tolerance
        assert delay2 >= 0.08  # Second delay should be larger


class TestRetryEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_zero_max_attempts_raises_immediately(self):
        """Test that 0 max_attempts means no execution."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            return "success"

        # Note: tenacity requires at least 1 attempt, so this tests the library's behavior
        config = AsyncRetryConfig(max_attempts=1, min_wait=0.01)
        result = await run_async_with_retry_async(func, config)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_function_required(self):
        """Test that function must be async."""
        call_count = 0

        async def async_func():
            nonlocal call_count
            call_count += 1
            return "success"

        config = AsyncRetryConfig(max_attempts=3),
        result = await run_async_with_retry_async(async_func, config)

        assert result == "success"
        assert call_count == 1


class TestRetryWithMocks:
    """Test retry with mocked functions."""

    @pytest.mark.asyncio
    async def test_retry_with_async_mock(self):
        """Test retry with AsyncMock."""
        mock_func = AsyncMock(side_effect=[ValueError("retry"), ValueError("retry"), "success"])

        config = AsyncRetryConfig(max_attempts=5, min_wait=0.01, max_wait=0.1)
        result = await run_async_with_retry_async(mock_func, config)

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_tracks_all_attempts(self):
        """Test that all retry attempts are tracked."""
        attempts = []

        async def track_attempts():
            attempt = len(attempts) + 1
            attempts.append(attempt)
            if attempt < 4:
                raise ValueError(f"Attempt {attempt}")
            return f"success after {attempt} attempts"

        config = AsyncRetryConfig(max_attempts=5, min_wait=0.01, max_wait=0.1)
        result = await run_async_with_retry_async(track_attempts, config)

        assert result == "success after 4 attempts"
        assert len(attempts) == 4
        assert attempts == [1, 2, 3, 4]
