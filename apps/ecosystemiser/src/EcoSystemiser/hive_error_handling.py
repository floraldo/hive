"""
Hive error handling integration for EcoSystemiser.

This module provides error handling utilities that integrate with
the broader Hive ecosystem's error management system.

When the full hive-error-handling package is available, this will import from there.
For now, it provides a working stub implementation.
"""

from hive_logging import get_logger
import traceback
from typing import Optional, Dict, Any, Type
from datetime import datetime, timezone

logger = get_logger(__name__)

# Try to import from the real hive-error-handling if available
try:
    from hive_error_handling import BaseError, ErrorSeverity, ErrorContext
    REAL_ERROR_HANDLING = True
except ImportError:
    REAL_ERROR_HANDLING = False
    logger.info("Using stub hive_error_handling implementation. Real implementation not yet available.")


class ErrorSeverity:
    """Error severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorContext:
    """Context information for errors."""

    def __init__(
        self,
        agent_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        task_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.agent_id = agent_id
        self.workflow_id = workflow_id
        self.task_id = task_id
        self.correlation_id = correlation_id
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "agent_id": self.agent_id,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


class BaseError(Exception):
    """
    Base error class for Hive ecosystem.

    All Hive errors should inherit from this class to ensure
    consistent error handling across the system.
    """

    def __init__(
        self,
        message: str,
        severity: str = ErrorSeverity.ERROR,
        error_code: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None
    ):
        """
        Initialize a Hive error.

        Args:
            message: Human-readable error message
            severity: Error severity level
            error_code: Machine-readable error code
            context: Error context information
            cause: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.error_code = error_code or self.__class__.__name__
        self.context = context or ErrorContext()
        self.cause = cause
        self.stack_trace = traceback.format_exc() if cause else None

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "severity": self.severity,
            "context": self.context.to_dict() if self.context else None,
            "cause": str(self.cause) if self.cause else None,
            "stack_trace": self.stack_trace
        }

    def log(self):
        """Log the error with appropriate severity."""
        log_message = f"[{self.error_code}] {self.message}"

        if self.severity == ErrorSeverity.DEBUG:
            logger.debug(log_message)
        elif self.severity == ErrorSeverity.INFO:
            logger.info(log_message)
        elif self.severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        elif self.severity == ErrorSeverity.ERROR:
            logger.error(log_message)
        elif self.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        else:
            logger.error(log_message)

        # Also log the stack trace if available
        if self.stack_trace:
            logger.debug(f"Stack trace:\n{self.stack_trace}")


class ValidationError(BaseError):
    """Error raised when validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            severity=ErrorSeverity.WARNING,
            **kwargs
        )
        self.field = field


class ConfigurationError(BaseError):
    """Error raised when configuration is invalid."""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            **kwargs
        )
        self.config_key = config_key


class ResourceError(BaseError):
    """Error raised when a resource is unavailable or fails."""

    def __init__(self, message: str, resource_type: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            **kwargs
        )
        self.resource_type = resource_type


class TimeoutError(BaseError):
    """Error raised when an operation times out."""

    def __init__(self, message: str, timeout_seconds: Optional[float] = None, **kwargs):
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            **kwargs
        )
        self.timeout_seconds = timeout_seconds


class RetryableError(BaseError):
    """Base class for errors that can be retried."""

    def __init__(
        self,
        message: str,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
        **kwargs
    ):
        super().__init__(message=message, **kwargs)
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.retry_count = 0

    def can_retry(self) -> bool:
        """Check if the operation can be retried."""
        return self.retry_count < self.max_retries

    def increment_retry(self):
        """Increment the retry count."""
        self.retry_count += 1


def handle_error(
    error: Exception,
    context: Optional[ErrorContext] = None,
    reraise: bool = True
) -> Optional[BaseError]:
    """
    Handle an error in a consistent way.

    Args:
        error: The error to handle
        context: Optional error context
        reraise: Whether to re-raise the error after handling

    Returns:
        BaseError instance if error was wrapped, None otherwise
    """
    # If it's already a BaseError, just add context and log
    if isinstance(error, BaseError):
        if context:
            error.context = context
        error.log()
        if reraise:
            raise error
        return error

    # Wrap non-Hive errors
    hive_error = BaseError(
        message=str(error),
        severity=ErrorSeverity.ERROR,
        context=context,
        cause=error
    )
    hive_error.log()

    if reraise:
        raise hive_error from error

    return hive_error


# Export the main classes and functions
__all__ = [
    "BaseError",
    "ErrorSeverity",
    "ErrorContext",
    "ValidationError",
    "ConfigurationError",
    "ResourceError",
    "TimeoutError",
    "RetryableError",
    "handle_error"
]