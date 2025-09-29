"""Async retry utilities with configurable strategies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tenacity import (
    AsyncRetrying,
    RetryError,
    after_log,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class AsyncRetryConfig:
    """Configuration for async retry behavior."""

    max_attempts: int = 3
    min_wait: float = 1.0
    max_wait: float = 10.0
    multiplier: float = 2.0
    retry_exceptions: tuple = Exception
    stop_on_exceptions: tuple = ()
    log_before_sleep: bool = True
    log_after_attempt: bool = True


class AsyncRetryError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, original_error: Exception, attempts: int) -> None:
        self.original_error = original_error
        self.attempts = attempts
        super().__init__(f"Failed after {attempts} attempts: {original_error}")


async def run_async_with_retry_async(func: Callable, config: AsyncRetryConfig | None = None, *args, **kwargs) -> Any:
    """
    Retry an async function with configurable strategy.

    Args:
        func: Async function to retry
        config: Retry configuration
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the function call

    Raises:
        AsyncRetryError: When all retry attempts are exhausted
    """
    if config is None:
        config = AsyncRetryConfig()

    # Build retry conditions
    retry_condition = retry_if_exception_type(config.retry_exceptions)
    if config.stop_on_exceptions:
        retry_condition = retry_condition & ~retry_if_exception_type(config.stop_on_exceptions)

    # Build retry strategy
    retry_strategy = AsyncRetrying(
        stop=stop_after_attempt(config.max_attempts),
        wait=wait_exponential(multiplier=config.multiplier, min=config.min_wait, max=config.max_wait),
        retry=retry_condition,
        before_sleep=(before_sleep_log(logger, "WARNING") if config.log_before_sleep else None),
        after=after_log(logger, "INFO") if config.log_after_attempt else None,
    )

    try:
        return await retry_strategy(func, *args, **kwargs)
    except RetryError as e:
        if e.last_attempt.failed:
            original_error = e.last_attempt.exception()
            raise AsyncRetryError(original_error, config.max_attempts) from original_error
        raise


def create_retry_decorator(config: AsyncRetryConfig | None = None) -> None:
    """
    Create a decorator for automatic retry of async functions.

    Args:
        config: Retry configuration

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Dict[str, Any]:
        async def wrapper_async(*args, **kwargs):
            return await run_async_with_retry_async(func, config, *args, **kwargs)

        return wrapper

    return decorator


# Convenience decorators for common scenarios
retry_on_connection_error = create_retry_decorator(
    AsyncRetryConfig(
        max_attempts=5, min_wait=0.5, max_wait=30.0, retry_exceptions=(ConnectionError, OSError, TimeoutError),
    ),
)

retry_on_http_error = create_retry_decorator(
    AsyncRetryConfig(
        max_attempts=3,
        min_wait=1.0,
        max_wait=10.0,
        retry_exceptions=(Exception),  # Will be refined based on HTTP client used
    ),
)
