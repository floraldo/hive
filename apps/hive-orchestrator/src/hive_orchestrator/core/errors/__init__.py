"""
Hive Error Management - Orchestration Error Handling.

Extends generic error handling toolkit with Hive-specific error management:
- Orchestration-specific error types
- Agent error correlation
- Task failure tracking
- Workflow error analysis
"""

from hive_errors import BaseError, BaseErrorReporter, RecoveryStrategy

from .hive_exceptions import (
    HiveError,
    TaskError, TaskCreationError, TaskExecutionError, TaskTimeoutError,
    WorkerError, WorkerSpawnError, WorkerCommunicationError, WorkerOverloadError,
    EventBusError, EventPublishError, EventSubscribeError,
    ClaudeError, ClaudeRateLimitError, ClaudeServiceError
)
from .hive_error_reporter import HiveErrorReporter, get_hive_error_reporter, report_hive_error

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
    "report_hive_error"
]