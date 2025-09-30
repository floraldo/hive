"""
Hive System Exception Hierarchy
Provides structured exceptions for all components
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hive_errors import BaseError
from hive_logging import get_logger

logger = get_logger(__name__)


class HiveError(Exception):
    """
    Base exception for all Hive system errors

    Attributes:
        component: Component where error occurred,
        operation: Operation being performed,
        details: Additional error details,
        timestamp: When error occurred,
        recovery_suggestions: Suggested recovery actions
    """

    def __init__(
        self,
        message: str,
        component: str | None = None,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
        recovery_suggestions: list[str] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.component = component or "unknown"
        self.operation = operation or "unknown"
        self.details = details or {}
        self.timestamp = datetime.now()
        self.recovery_suggestions = recovery_suggestions or []

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/storage"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "component": self.component,
            "operation": self.operation,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "recovery_suggestions": self.recovery_suggestions,
        }

    def __str__(self) -> str:
        """Human-readable error representation"""
        base = f"[{self.component}] {self.message}"
        if self.operation:
            base = f"{base} (during {self.operation})"
        return base


class HiveConfigError(BaseError):
    """Configuration-related errors"""

    def __init__(self, message: str, config_key: str | None = None, config_file: str | None = None, **kwargs):
        super().__init__(message, component="configuration", **kwargs)
        self.details["config_key"] = config_key
        self.details["config_file"] = config_file

        # Add recovery suggestions
        self.recovery_suggestions = [
            "Check configuration file exists and is valid JSON",
            "Verify all required configuration keys are present",
            "Check environment variables for overrides",
            "Use default configuration as fallback",
        ]


class HiveDatabaseError(BaseError):
    """Database operation errors"""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        table: str | None = None,
        error_code: str | None = None,
        **kwargs,
    ):
        super().__init__(message, component="database", **kwargs)
        self.details["query"] = query
        self.details["table"] = table
        self.details["error_code"] = error_code

        # Add recovery suggestions based on error type
        if "locked" in message.lower():
            self.recovery_suggestions = [
                "Wait for current operation to complete",
                "Check for zombie processes holding locks",
                "Consider using WAL mode for better concurrency",
            ]
        elif "connection" in message.lower():
            self.recovery_suggestions = (
                [
                    "Check database file exists and is accessible",
                    "Verify database path is correct",
                    "Check file permissions",
                ],
            )
        else:
            self.recovery_suggestions = [
                "Check SQL syntax if query was provided",
                "Verify table schema matches expected structure",
                "Check database integrity with PRAGMA integrity_check",
            ]


class HiveTaskError(BaseError):
    """Task execution errors"""

    def __init__(
        self,
        message: str,
        task_id: str | None = None,
        task_type: str | None = None,
        phase: str | None = None,
        **kwargs,
    ):
        super().__init__(message, component="task", **kwargs)
        self.details["task_id"] = task_id
        self.details["task_type"] = task_type
        self.details["phase"] = phase

        self.recovery_suggestions = [
            "Check task dependencies are satisfied",
            "Verify worker availability for task type",
            "Review task configuration and parameters",
            "Check logs for detailed error information",
        ]


class HiveWorkerError(BaseError):
    """Worker process errors"""

    def __init__(
        self,
        message: str,
        worker_id: str | None = None,
        worker_type: str | None = None,
        exit_code: int | None = None,
        **kwargs,
    ):
        super().__init__(message, component="worker", **kwargs)
        self.details["worker_id"] = worker_id
        self.details["worker_type"] = worker_type
        self.details["exit_code"] = exit_code

        # Add recovery suggestions based on exit code
        if exit_code and exit_code < 0:
            self.recovery_suggestions = (
                [
                    "Worker was terminated by signal",
                    "Check system resources (memory, CPU)",
                    "Review worker timeout settings",
                ],
            )
        else:
            self.recovery_suggestions = [
                "Check worker script for errors",
                "Verify worker environment and dependencies",
                "Review worker logs for detailed errors",
                "Consider restarting the worker",
            ]


class HiveAPIError(BaseError):
    """External API errors (e.g., Claude API)"""

    def __init__(
        self,
        message: str,
        api_name: str | None = None,
        status_code: int | None = None,
        response_body: str | None = None,
        **kwargs,
    ):
        super().__init__(message, component="api", **kwargs)
        self.details["api_name"] = api_name
        self.details["status_code"] = status_code
        self.details["response_body"] = response_body

        # Add recovery suggestions based on status code
        if status_code == 401:
            self.recovery_suggestions = [
                "Check API credentials are valid",
                "Verify API key is set in configuration",
                "Check API key permissions",
            ]
        elif status_code == 429:
            self.recovery_suggestions = [
                "Rate limit exceeded - wait before retrying",
                "Implement exponential backoff",
                "Consider request batching",
            ]
        elif status_code and status_code >= 500:
            self.recovery_suggestions = [
                "API service error - wait and retry",
                "Check API service status",
                "Use fallback mechanism if available",
            ]
        else:
            self.recovery_suggestions = [
                "Check API request format",
                "Verify API endpoint is correct",
                "Review API documentation",
            ]


class HiveTimeoutError(BaseError):
    """Operation timeout errors"""

    def __init__(self, message: str, timeout_seconds: int | None = None, operation_type: str | None = None, **kwargs):
        super().__init__(message, component="timeout", **kwargs)
        self.details["timeout_seconds"] = timeout_seconds
        self.details["operation_type"] = operation_type

        self.recovery_suggestions = [
            "Increase timeout duration for this operation",
            "Check if operation is stuck or deadlocked",
            "Break operation into smaller chunks",
            "Verify system resources are not exhausted",
        ]


class HiveValidationError(BaseError):
    """Data validation errors"""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        validation_rule: str | None = None,
        **kwargs,
    ):
        super().__init__(message, component="validation", **kwargs)
        self.details["field"] = field
        self.details["value"] = str(value) if value is not None else None
        self.details["validation_rule"] = validation_rule

        self.recovery_suggestions = [
            "Check input data format and types",
            "Verify data meets validation requirements",
            "Review validation rules for correctness",
            "Sanitize input data before validation",
        ]


class HiveResourceError(BaseError):
    """Resource availability errors"""

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        required: Any | None = None,
        available: Any | None = None,
        **kwargs,
    ):
        super().__init__(message, component="resource", **kwargs)
        self.details["resource_type"] = resource_type
        self.details["required"] = required
        self.details["available"] = available

        self.recovery_suggestions = [
            "Free up resources by stopping unused processes",
            "Increase resource limits if possible",
            "Queue operation for when resources are available",
            "Use resource pooling for better efficiency",
        ]


class HiveStateError(BaseError):
    """System state errors"""

    def __init__(
        self,
        message: str,
        current_state: str | None = None,
        expected_state: str | None = None,
        transition: str | None = None,
        **kwargs,
    ):
        super().__init__(message, component="state", **kwargs)
        self.details["current_state"] = current_state
        self.details["expected_state"] = expected_state
        self.details["transition"] = transition

        self.recovery_suggestions = [
            "Check system state consistency",
            "Verify state transition is valid",
            "Reset to known good state if needed",
            "Review state machine logic",
        ]


class EventBusError(BaseError):
    """Base event bus errors"""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(message, component="event_bus", **kwargs)
        self.recovery_suggestions = [
            "Check event bus connection and configuration",
            "Verify event bus service is running",
            "Review event format and structure",
            "Check database connectivity for persistent events",
        ]


class EventPublishError(BaseError):
    """Event publishing errors"""

    def __init__(self, message: str, event_type: str | None = None, event_id: str | None = None, **kwargs):
        super().__init__(message, operation="publish", **kwargs)
        self.details["event_type"] = event_type
        self.details["event_id"] = event_id

        self.recovery_suggestions = [
            "Check event data format and serialization",
            "Verify database connection for persistent events",
            "Check event bus capacity and queue status",
            "Retry with exponential backoff",
        ]


class EventSubscribeError(BaseError):
    """Event subscription errors"""

    def __init__(self, message: str, pattern: str | None = None, subscriber_name: str | None = None, **kwargs):
        super().__init__(message, operation="subscribe", **kwargs)
        self.details["pattern"] = pattern
        self.details["subscriber_name"] = subscriber_name

        self.recovery_suggestions = [
            "Check subscription pattern syntax",
            "Verify subscriber callback function",
            "Check event bus subscription limits",
            "Review subscription permissions",
        ]
