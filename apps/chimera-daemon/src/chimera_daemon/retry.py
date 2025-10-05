"""Retry policy with exponential backoff and jitter.

Implements intelligent retry strategies for failed workflows with:
- Exponential backoff with configurable base delay
- Random jitter to prevent thundering herd
- Max retry limits
- Configurable backoff strategies
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from hive_logging import get_logger

logger = get_logger(__name__)


class BackoffStrategy(Enum):
    """Backoff calculation strategies."""

    EXPONENTIAL = "exponential"  # 2^n * base_delay
    LINEAR = "linear"  # n * base_delay
    FIBONACCI = "fibonacci"  # fib(n) * base_delay


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay_ms: Base delay in milliseconds (default: 1000)
        max_delay_ms: Maximum delay cap in milliseconds (default: 60000)
        backoff_strategy: Strategy for calculating delay (default: EXPONENTIAL)
        jitter_factor: Random jitter as fraction of delay (default: 0.1 = 10%)
        retryable_errors: List of error types that should trigger retry
    """

    max_retries: int = 3
    base_delay_ms: float = 1000.0
    max_delay_ms: float = 60000.0  # 1 minute max
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    jitter_factor: float = 0.1
    retryable_errors: list[type[Exception]] | None = None

    def __post_init__(self):
        """Validate retry configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {self.max_retries}")

        if self.base_delay_ms < 0:
            raise ValueError(f"base_delay_ms must be >= 0, got {self.base_delay_ms}")

        if self.max_delay_ms < self.base_delay_ms:
            raise ValueError(
                f"max_delay_ms ({self.max_delay_ms}) must be >= "
                f"base_delay_ms ({self.base_delay_ms})"
            )

        if not (0.0 <= self.jitter_factor <= 1.0):
            raise ValueError(f"jitter_factor must be 0.0-1.0, got {self.jitter_factor}")


class RetryPolicy:
    """Intelligent retry policy with exponential backoff and jitter.

    Handles retry logic for failed operations with configurable strategies.

    Example:
        policy = RetryPolicy(config=RetryConfig(max_retries=5))
        result = await policy.execute(async_operation, arg1, arg2)
    """

    def __init__(self, config: RetryConfig | None = None):
        """Initialize retry policy.

        Args:
            config: Retry configuration (uses defaults if None)
        """
        self.config = config or RetryConfig()
        self.logger = logger

    async def execute(
        self,
        operation: Callable,
        *args,
        **kwargs,
    ) -> any:
        """Execute operation with retry logic.

        Args:
            operation: Async callable to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation

        Returns:
            Result from successful operation execution

        Raises:
            Exception: Last exception if all retries exhausted
        """
        last_exception = None
        attempt = 0

        while attempt <= self.config.max_retries:
            try:
                if attempt > 0:
                    self.logger.info(
                        f"Retry attempt {attempt}/{self.config.max_retries}"
                    )

                # Execute operation
                result = await operation(*args, **kwargs)

                if attempt > 0:
                    self.logger.info(
                        f"Operation succeeded on retry attempt {attempt}"
                    )

                return result

            except Exception as e:
                last_exception = e

                # Check if error is retryable
                if not self._is_retryable(e):
                    self.logger.warning(
                        f"Non-retryable error encountered: {type(e).__name__}"
                    )
                    raise

                # Check if we have retries left
                if attempt >= self.config.max_retries:
                    self.logger.error(
                        f"All {self.config.max_retries} retries exhausted"
                    )
                    raise

                # Calculate delay with jitter
                delay_ms = self._calculate_delay(attempt + 1)
                self.logger.warning(
                    f"Operation failed (attempt {attempt + 1}): {e}. "
                    f"Retrying in {delay_ms:.0f}ms..."
                )

                # Wait before retry
                await asyncio.sleep(delay_ms / 1000.0)
                attempt += 1

        # Should never reach here, but handle edge case
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry logic error: no exception raised")

    def _is_retryable(self, error: Exception) -> bool:
        """Check if error type is retryable.

        Args:
            error: Exception that occurred

        Returns:
            True if error should trigger retry, False otherwise
        """
        # If no specific retryable errors configured, retry all
        if self.config.retryable_errors is None:
            return True

        # Check if error type matches configured retryable errors
        return any(
            isinstance(error, error_type)
            for error_type in self.config.retryable_errors
        )

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate retry delay with backoff and jitter.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in milliseconds
        """
        # Calculate base delay based on strategy
        if self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.base_delay_ms * (2 ** (attempt - 1))
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.base_delay_ms * attempt
        elif self.config.backoff_strategy == BackoffStrategy.FIBONACCI:
            delay = self.config.base_delay_ms * self._fibonacci(attempt)
        else:
            delay = self.config.base_delay_ms

        # Cap at max delay
        delay = min(delay, self.config.max_delay_ms)

        # Add random jitter
        jitter = delay * self.config.jitter_factor * (random.random() - 0.5) * 2
        delay_with_jitter = delay + jitter

        # Ensure non-negative
        return max(0.0, delay_with_jitter)

    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number.

        Args:
            n: Position in Fibonacci sequence (1-indexed)

        Returns:
            Fibonacci number at position n
        """
        if n <= 1:
            return 1

        a, b = 1, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return a


__all__ = ["RetryPolicy", "RetryConfig", "BackoffStrategy"]
