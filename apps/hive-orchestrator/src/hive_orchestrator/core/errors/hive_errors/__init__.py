from hive_logging import get_logger

logger = get_logger(__name__)

"""
Standardized Error Handling for Hive System
Provides consistent error types, reporting, and recovery strategies
"""

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
from .recovery import RecoveryAction, RecoveryStrategy

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
    "RecoveryAction",
]
