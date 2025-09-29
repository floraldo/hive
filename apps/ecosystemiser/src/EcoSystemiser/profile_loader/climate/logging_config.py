"""
Structured logging configuration using structlog.

Provides consistent, structured logging across the platform with:
- JSON output for production
- Correlation ID tracking
- Performance metrics
- Error context preservation
"""

import sys
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog
from ecosystemiser.settings import get_settings
from hive_logging import get_logger
from structlog.types import EventDict, Processor

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class CorrelationIDProcessor:
    """Add correlation ID to all log entries"""

    def __call__(self, logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
        """Add correlation ID if available"""
        correlation_id = correlation_id_var.get()
        if correlation_id:
            event_dict["correlation_id"] = correlation_id

        request_id = request_id_var.get()
        if request_id:
            event_dict["request_id"] = request_id

        return event_dict


class PerformanceProcessor:
    """Add performance metrics to log entries"""

    def __call__(self, logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
        """Add performance context"""
        # Add memory usage if it's an error or warning
        if method_name in ["error", "critical", "warning"]:
            try:
                import psutil

                process = psutil.Process()
                event_dict["memory_mb"] = process.memory_info().rss / 1024 / 1024
                event_dict["cpu_percent"] = process.cpu_percent()
            except ImportError:
                pass  # psutil not installed

        return event_dict


class ErrorContextProcessor:
    """Enhanced error context for debugging"""

    def __call__(self, logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
        """Add error context"""
        # Extract exception info if present
        if "exc_info" in event_dict and event_dict["exc_info"]:
            exc_info = event_dict["exc_info"]
            if isinstance(exc_info, tuple) and len(exc_info) >= 2:
                exc_type, exc_value = exc_info[:2]
                event_dict["error_type"] = exc_type.__name__ if exc_type else None
                event_dict["error_message"] = str(exc_value) if exc_value else None

                # Add custom error attributes if it's a ClimateError
                if hasattr(exc_value, "code"):
                    event_dict["error_code"] = str(exc_value.code.value)
                if hasattr(exc_value, "severity"):
                    event_dict["error_severity"] = str(exc_value.severity.value)
                if hasattr(exc_value, "retriable"):
                    event_dict["error_retriable"] = exc_value.retriable

        return event_dict


class AdapterContextProcessor:
    """Add adapter context to logs"""

    def __call__(self, logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
        """Add adapter context if available"""
        # Check if logger name indicates an adapter
        logger_name = event_dict.get("logger", "")
        if "adapter" in logger_name.lower():
            parts = logger_name.split(".")
            for i, part in enumerate(parts):
                if part == "adapters" and i + 1 < len(parts):
                    event_dict["adapter"] = parts[i + 1]
                    break

        return event_dict


def setup_logging(log_level: Optional[str] = None, log_format: Optional[str] = None) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ('json' or 'console')
    """
    settings = get_settings()

    # Use provided values or fall back to settings
    level = log_level or settings.observability.log_level
    format_type = log_format or settings.observability.log_format

    # Set up stdlib logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Configure processors
    processors = [
        # Add correlation ID
        CorrelationIDProcessor(),
        # Add adapter context
        AdapterContextProcessor(),
        # Filter by level
        structlog.stdlib.filter_by_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add log level
        structlog.stdlib.add_log_level,
        # Handle positional arguments
        structlog.processors.PositionalArgumentsFormatter(),
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add call site info for errors
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            ],
            levels=["warning", "error", "critical"],
        ),
        # Add performance metrics
        PerformanceProcessor(),
        # Add enhanced error context
        ErrorContextProcessor(),
        # Format stack traces
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Decode unicode
        structlog.processors.UnicodeDecoder(),
    ]

    # Add appropriate renderer based on format
    if format_type == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Console output with colors
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                pad_event=30,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context"""
    correlation_id_var.set(correlation_id)


def set_request_id(request_id: str) -> None:
    """Set request ID for current context"""
    request_id_var.set(request_id)


def clear_context() -> None:
    """Clear logging context variables"""
    correlation_id_var.set(None)
    request_id_var.set(None)


class LoggingContext:
    """Context manager for scoped logging context"""

    def __init__(
        self,
        correlation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs,
    ):
        self.correlation_id = correlation_id
        self.request_id = request_id
        self.extra = kwargs
        self.tokens = []

    def __enter__(self):
        """Set logging context"""
        if self.correlation_id:
            token = correlation_id_var.set(self.correlation_id)
            self.tokens.append((correlation_id_var, token))

        if self.request_id:
            token = request_id_var.set(self.request_id)
            self.tokens.append((request_id_var, token))

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Reset logging context"""
        for var, token in self.tokens:
            var.reset(token)


# Convenience function for logging with context
def log_with_context(logger: structlog.stdlib.BoundLogger, level: str, message: str, **kwargs) -> None:
    """
    Log a message with additional context.

    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        **kwargs: Additional context
    """
    log_method = getattr(logger, level)
    log_method(message, **kwargs)
