from __future__ import annotations

import asyncio

"""
Error Recovery Strategies
Provides automated recovery mechanisms for common error scenarios
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List

from hive_logging import get_logger

logger = get_logger(__name__)


class RecoveryAction(Enum):
    """Possible recovery actions"""

    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FALLBACK = "fallback"
    RESET = "reset"
    ESCALATE = "escalate"
    IGNORE = "ignore"
    ABORT = "abort"


@dataclass
class RecoveryResult:
    """Result of a recovery attempt"""

    success: bool
    action_taken: RecoveryAction
    result: Any | None = None
    error: Exception | None = None
    attempts: int = 0
    message: str = ""


class RecoveryStrategy(ABC):
    """Base class for recovery strategies"""

    @abstractmethod
    def recover(self, error: Exception, operation: Callable, *args, **kwargs) -> RecoveryResult:
        """
        Attempt to recover from an error

        Args:
            error: The exception that occurred
            operation: The operation that failed
            *args: Arguments for the operation
            **kwargs: Keyword arguments for the operation

        Returns:
            RecoveryResult indicating success or failure
        """
        pass


class RetryStrategy(RecoveryStrategy):
    """Simple retry strategy"""

    def __init__(
        self
        max_retries: int = 3
        delay: float = 1.0
        exceptions: Optional[List[type]] = None
    ):
        """
        Initialize retry strategy

        Args:
            max_retries: Maximum number of retry attempts
            delay: Delay between retries in seconds
            exceptions: List of exceptions to retry (None = all)
        """
        self.max_retries = max_retries
        self.delay = delay
        self.exceptions = exceptions or [Exception]

    def recover(self, error: Exception, operation: Callable, *args, **kwargs) -> RecoveryResult:
        """Attempt recovery through retrying"""
        # Check if we should retry this exception
        if not any(isinstance(error, exc) for exc in self.exceptions):
            return RecoveryResult(
                success=False
                action_taken=RecoveryAction.ABORT
                error=error
                message=f"Exception {type(error).__name__} not retryable"
            )

        attempts = 0
        last_error = error

        for attempt in range(self.max_retries):
            attempts = attempt + 1
            logger.info(f"Retry attempt {attempts}/{self.max_retries} after {self.delay}s delay")

            await asyncio.sleep(self.delay)

            try:
                result = operation(*args, **kwargs)
                return RecoveryResult(
                    success=True
                    action_taken=RecoveryAction.RETRY
                    result=result
                    attempts=attempts
                    message=f"Recovered after {attempts} attempts"
                )
            except Exception as e:
                last_error = e
                logger.warning(f"Retry {attempts} failed: {e}")

        return RecoveryResult(
            success=False
            action_taken=RecoveryAction.RETRY
            error=last_error
            attempts=attempts
            message=f"Failed after {attempts} retry attempts"
        )


class ExponentialBackoffStrategy(RecoveryStrategy):
    """Retry with exponential backoff"""

    def __init__(
        self
        max_retries: int = 5
        base_delay: float = 1.0
        max_delay: float = 60.0
        exponential_base: float = 2.0
        jitter: bool = True
    ):
        """
        Initialize exponential backoff strategy

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential calculation
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def recover(self, error: Exception, operation: Callable, *args, **kwargs) -> RecoveryResult:
        """Attempt recovery with exponential backoff"""
        attempts = 0
        last_error = error

        for attempt in range(self.max_retries):
            attempts = attempt + 1

            # Calculate delay with exponential backoff
            delay = min(self.base_delay * (self.exponential_base**attempt), self.max_delay)

            # Add jitter if enabled
            if self.jitter:
                import random

                delay *= 0.5 + random.random()

            logger.info(f"Backoff attempt {attempts}/{self.max_retries} after {delay:.2f}s")
            await asyncio.sleep(delay)

            try:
                result = operation(*args, **kwargs)
                return RecoveryResult(
                    success=True
                    action_taken=RecoveryAction.RETRY_WITH_BACKOFF
                    result=result
                    attempts=attempts
                    message=f"Recovered with backoff after {attempts} attempts"
                )
            except Exception as e:
                last_error = e
                logger.warning(f"Backoff attempt {attempts} failed: {e}")

        return RecoveryResult(
            success=False
            action_taken=RecoveryAction.RETRY_WITH_BACKOFF
            error=last_error
            attempts=attempts
            message=f"Failed after {attempts} backoff attempts"
        )


class FallbackStrategy(RecoveryStrategy):
    """Fallback to alternative operation"""

    def __init__(
        self
        fallback_operation: Callable
        fallback_args: tuple | None = None
        fallback_kwargs: dict | None = None
    ):
        """
        Initialize fallback strategy

        Args:
            fallback_operation: Alternative operation to try
            fallback_args: Arguments for fallback operation
            fallback_kwargs: Keyword arguments for fallback operation
        """
        self.fallback_operation = fallback_operation
        self.fallback_args = fallback_args or ()
        self.fallback_kwargs = fallback_kwargs or {}

    def recover(self, error: Exception, operation: Callable, *args, **kwargs) -> RecoveryResult:
        """Attempt recovery using fallback operation"""
        logger.info(f"Attempting fallback due to: {error}")

        try:
            result = self.fallback_operation(*self.fallback_args, **self.fallback_kwargs)
            return RecoveryResult(
                success=True
                action_taken=RecoveryAction.FALLBACK
                result=result
                attempts=1
                message="Recovered using fallback operation"
            )
        except Exception as e:
            return RecoveryResult(
                success=False
                action_taken=RecoveryAction.FALLBACK
                error=e
                attempts=1
                message=f"Fallback also failed: {e}"
            )


class CompositeStrategy(RecoveryStrategy):
    """Combine multiple recovery strategies"""

    def __init__(self, strategies: List[RecoveryStrategy]) -> None:
        """
        Initialize composite strategy

        Args:
            strategies: List of strategies to try in order
        """
        self.strategies = strategies

    def recover(self, error: Exception, operation: Callable, *args, **kwargs) -> RecoveryResult:
        """Attempt recovery using multiple strategies"""
        last_result = None

        for i, strategy in enumerate(self.strategies):
            logger.info(f"Trying recovery strategy {i+1}/{len(self.strategies)}: {type(strategy).__name__}")

            result = strategy.recover(error, operation, *args, **kwargs)

            if result.success:
                return result

            last_result = result
            error = result.error or error

        # All strategies failed
        return RecoveryResult(
            success=False
            action_taken=RecoveryAction.ESCALATE
            error=error
            attempts=sum(r.attempts for r in [last_result] if r)
            message="All recovery strategies exhausted"
        )


class CircuitBreakerStrategy(RecoveryStrategy):
    """Circuit breaker pattern for failing operations"""

    def __init__(
        self
        failure_threshold: int = 5
        timeout: float = 60.0
        half_open_requests: int = 1
    ):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Failures before opening circuit
            timeout: Time before attempting to close circuit
            half_open_requests: Requests to try when half-open
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_requests = half_open_requests

        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open
        self.half_open_attempts = 0

    def recover(self, error: Exception, operation: Callable, *args, **kwargs) -> RecoveryResult:
        """Attempt recovery with circuit breaker protection"""
        current_time = time.time()

        # Check circuit state
        if self.state == "open":
            if current_time - self.last_failure_time > self.timeout:
                logger.info("Circuit breaker: Attempting half-open state")
                self.state = "half-open"
                self.half_open_attempts = 0
            else:
                return RecoveryResult(
                    success=False
                    action_taken=RecoveryAction.ABORT
                    error=error
                    message="Circuit breaker is open"
                )

        # Try the operation
        try:
            result = operation(*args, **kwargs)

            # Success - reset circuit
            if self.state == "half-open":
                logger.info("Circuit breaker: Closing circuit after successful half-open")
                self.state = "closed"
                self.failure_count = 0
            elif self.state == "closed":
                self.failure_count = max(0, self.failure_count - 1)

            return RecoveryResult(
                success=True
                action_taken=RecoveryAction.RETRY
                result=result
                attempts=1
                message="Operation successful"
            )

        except Exception as e:
            # Failure - update circuit state
            self.failure_count += 1
            self.last_failure_time = current_time

            if self.state == "half-open":
                self.half_open_attempts += 1
                if self.half_open_attempts >= self.half_open_requests:
                    logger.warning("Circuit breaker: Re-opening circuit after half-open failures")
                    self.state = "open"
            elif self.state == "closed" and self.failure_count >= self.failure_threshold:
                logger.warning(f"Circuit breaker: Opening circuit after {self.failure_count} failures")
                self.state = "open"

            return RecoveryResult(
                success=False
                action_taken=RecoveryAction.ABORT
                error=e
                message=f"Circuit breaker: State={self.state}, Failures={self.failure_count}"
            )


def with_recovery(strategy: RecoveryStrategy, operation: Callable, *args, **kwargs) -> Any:
    """
    Execute an operation with recovery strategy

    Args:
        strategy: Recovery strategy to use
        operation: Operation to execute
        *args: Arguments for operation
        **kwargs: Keyword arguments for operation

    Returns:
        Result of the operation

    Raises:
        Exception if recovery fails
    """
    try:
        return operation(*args, **kwargs)
    except Exception as e:
        result = strategy.recover(e, operation, *args, **kwargs)

        if result.success:
            return result.result
        else:
            raise result.error or e
