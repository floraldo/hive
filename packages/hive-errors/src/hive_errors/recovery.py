from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Generic recovery strategy patterns.

Provides reusable recovery mechanisms that can be used
to build resilient systems.
"""

from abc import ABC
from enum import Enum


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

    def reset(self) -> None:
        """Reset recovery attempt counter"""
        self.attempt_count = 0


class RetryStrategy(RecoveryStrategy):
    """Generic retry recovery strategy"""

    def attempt_recovery(self, error: Exception, context: dict | None = None) -> RecoveryStatus:
        """Attempt recovery by retrying the operation"""
        import time

        if not self.can_attempt_recovery():
            return RecoveryStatus.FAILED

        self.attempt_count += 1

        try:
            # Wait before retry
            if self.delay_seconds > 0:
                time.sleep(self.delay_seconds)

            # Retry the operation
            self.operation()
            return RecoveryStatus.SUCCESS

        except Exception:
            if self.attempt_count >= self.max_attempts:
                return RecoveryStatus.FAILED
            else:
                return RecoveryStatus.PARTIAL
