from hive_logging import get_logger

logger = get_logger(__name__)

"""
Hive Error Management - Orchestration Error Handling.

Extends generic error handling toolkit with Hive-specific error management:
- Orchestration-specific error types
- Agent error correlation
- Task failure tracking
- Workflow error analysis
"""

# Import from infrastructure package (Inherit-Extend pattern)
from hive_errors import BaseError, BaseErrorReporter

from .hive_error_reporter import HiveErrorReporter, get_hive_error_reporter, report_hive_error
from .hive_exceptions import (
    ClaudeError,
    ClaudeRateLimitError,
    ClaudeServiceError,
    EventBusError,
    EventPublishError,
    EventSubscribeError,
    HiveError,
    TaskCreationError,
    TaskError,
    TaskExecutionError,
    TaskTimeoutError,
    WorkerCommunicationError,
    WorkerError,
    WorkerOverloadError,
    WorkerSpawnError,
)

__all__ = [
    # Base Hive error
    "HiveError",
    # Task errors
    "TaskError",
    "TaskCreationError",
    "TaskExecutionError",
    "TaskTimeoutError",
    # Worker errors
    "WorkerError",
    "WorkerSpawnError",
    "WorkerCommunicationError",
    "WorkerOverloadError",
    # Event bus errors
    "EventBusError",
    "EventPublishError",
    "EventSubscribeError",
    # Claude integration errors
    "ClaudeError",
    "ClaudeRateLimitError",
    "ClaudeServiceError",
    # Error reporting
    "HiveErrorReporter",
    "get_hive_error_reporter",
    "report_hive_error",
]
