"""
Standardized Error Handling for Hive System
Provides consistent error types, reporting, and recovery strategies
"""

from .exceptions import (
    HiveError,
    HiveConfigError,
    HiveDatabaseError,
    HiveTaskError,
    HiveWorkerError,
    HiveAPIError,
    HiveTimeoutError,
    HiveValidationError,
    HiveResourceError,
    HiveStateError,
    EventBusError,
    EventPublishError,
    EventSubscribeError
)
from .error_reporter import ErrorReporter, ErrorContext
from .recovery import RecoveryStrategy, RecoveryAction

__version__ = "1.0.0"

__all__ = [
    "HiveError",
    "HiveConfigError",
    "HiveDatabaseError",
    "HiveTaskError",
    "HiveWorkerError",
    "HiveAPIError",
    "HiveTimeoutError",
    "HiveValidationError",
    "HiveResourceError",
    "HiveStateError",
    "EventBusError",
    "EventPublishError",
    "EventSubscribeError",
    "ErrorReporter",
    "ErrorContext",
    "RecoveryStrategy",
    "RecoveryAction"
]