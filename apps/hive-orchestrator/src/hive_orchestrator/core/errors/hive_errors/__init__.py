# ruff: noqa: E402
from hive_logging import get_logger

logger = get_logger(__name__)

"""
Standardized Error Handling for Hive System
Provides consistent error types, reporting, and recovery strategies
"""

# Use canonical recovery patterns from hive-errors
from hive_errors import RecoveryStatus as RecoveryAction
from hive_errors import RecoveryStrategy

from .error_reporter import ErrorContext, ErrorReporter
from .exceptions import (
    EventBusError,
    EventPublishError,
    EventSubscribeError,
    HiveAPIError,
    HiveConfigError,
    HiveDatabaseError,
    HiveError,
    HiveResourceError,
    HiveStateError,
    HiveTaskError,
    HiveTimeoutError,
    HiveValidationError,
    HiveWorkerError,
)

__version__ = ("1.0.0",)

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
    "RecoveryAction",
]
