import asyncio

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Generic recovery strategy patterns.

Provides reusable recovery mechanisms that can be used
to build resilient systems.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Optional


class RecoveryStatus(Enum):
    """Recovery attempt status"""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class RecoveryStrategy(ABC):
    """
    Generic base recovery strategy.

    Provides fundamental recovery patterns that can be extended
    for any system's specific recovery needs.
    """

    def __init__(self, strategy_name: str, max_attempts: int = 3) -> None:
        self.strategy_name = strategy_name
        self.max_attempts = max_attempts
        self.attempt_count = 0

    @abstractmethod
    def attempt_recovery(self, error: Exception, context: Optional[dict] = None) -> RecoveryStatus:
        """
        Attempt recovery from an error.

        Args:
            error: The exception that occurred
            context: Additional context for recovery

        Returns:
            Recovery status
        """
        pass

    def can_attempt_recovery(self) -> bool:
        """Check if recovery can be attempted"""
        return self.attempt_count < self.max_attempts

    def reset(self) -> None:
        """Reset recovery attempt counter"""
        self.attempt_count = 0


class RetryStrategy(RecoveryStrategy):
    """Generic retry recovery strategy"""

    def __init__(self, operation: Callable, max_attempts: int = 3, delay_seconds: float = 1.0) -> None:
        super().__init__("retry", max_attempts)
        self.operation = operation
        self.delay_seconds = delay_seconds

    def attempt_recovery(self, error: Exception, context: Optional[dict] = None) -> RecoveryStatus:
        """Attempt recovery by retrying the operation"""
        import time

        if not self.can_attempt_recovery():
            return RecoveryStatus.FAILED

        self.attempt_count += 1

        try:
            # Wait before retry
            if self.delay_seconds > 0:
                await asyncio.sleep(self.delay_seconds)

            # Retry the operation
            self.operation()
            return RecoveryStatus.SUCCESS

        except Exception as e:
            if self.attempt_count >= self.max_attempts:
                return RecoveryStatus.FAILED
            else:
                return RecoveryStatus.PARTIAL
