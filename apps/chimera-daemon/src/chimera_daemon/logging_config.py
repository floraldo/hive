"""Structured JSON Logging Configuration.

Provides structured JSON logging format for better log aggregation and analysis.
Integrates with hive_logging while adding trace context and structured fields.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from hive_logging import get_logger


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Outputs log records as JSON with consistent fields for log aggregation tools.
    Automatically includes trace_id and span_id if present in extra fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add trace context if available
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id
        if hasattr(record, "span_id"):
            log_data["span_id"] = record.span_id
        if hasattr(record, "workflow_id"):
            log_data["workflow_id"] = record.workflow_id

        # Add any extra fields
        if hasattr(record, "extra_fields"):
            log_data["extra"] = record.extra_fields

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_data)


class StructuredLogger:
    """Wrapper around hive_logging for structured logging with trace context.

    Provides convenience methods for logging with automatic trace propagation.

    Example:
        logger = StructuredLogger(component="executor_pool")

        logger.info("Workflow started", trace_id=trace_id, extra={
            "workflow_id": "wf_123",
            "max_iterations": 10
        })
    """

    def __init__(
        self,
        component: str,
        enable_json: bool = False,
    ):
        """Initialize structured logger.

        Args:
            component: Component name for logger
            enable_json: Enable JSON formatting (default: False)
        """
        self.component = component
        self.logger = get_logger(component)
        self.enable_json = enable_json

        # Add JSON formatter if enabled
        if enable_json:
            self._configure_json_logging()

    def _configure_json_logging(self) -> None:
        """Configure JSON formatter for this logger."""
        json_formatter = JSONFormatter()

        # Replace formatter on all handlers
        for handler in self.logger.handlers:
            handler.setFormatter(json_formatter)

    def _log(
        self,
        level: int,
        message: str,
        trace_id: str | None = None,
        span_id: str | None = None,
        workflow_id: str | None = None,
        extra: dict[str, Any] | None = None,
        exc_info: bool = False,
    ) -> None:
        """Internal logging method with trace context.

        Args:
            level: Log level (logging.INFO, logging.WARNING, etc.)
            message: Log message
            trace_id: Optional trace ID for distributed tracing
            span_id: Optional span ID for distributed tracing
            workflow_id: Optional workflow ID
            extra: Additional structured fields
            exc_info: Include exception info
        """
        extra_dict = {
            "trace_id": trace_id,
            "span_id": span_id,
            "workflow_id": workflow_id,
            "extra_fields": extra or {},
        }

        # Filter out None values
        extra_dict = {k: v for k, v in extra_dict.items() if v is not None}

        self.logger.log(level, message, extra=extra_dict, exc_info=exc_info)

    def debug(
        self,
        message: str,
        trace_id: str | None = None,
        span_id: str | None = None,
        workflow_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log debug message with trace context."""
        self._log(logging.DEBUG, message, trace_id, span_id, workflow_id, extra)

    def info(
        self,
        message: str,
        trace_id: str | None = None,
        span_id: str | None = None,
        workflow_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log info message with trace context."""
        self._log(logging.INFO, message, trace_id, span_id, workflow_id, extra)

    def warning(
        self,
        message: str,
        trace_id: str | None = None,
        span_id: str | None = None,
        workflow_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log warning message with trace context."""
        self._log(logging.WARNING, message, trace_id, span_id, workflow_id, extra)

    def error(
        self,
        message: str,
        trace_id: str | None = None,
        span_id: str | None = None,
        workflow_id: str | None = None,
        extra: dict[str, Any] | None = None,
        exc_info: bool = True,
    ) -> None:
        """Log error message with trace context."""
        self._log(logging.ERROR, message, trace_id, span_id, workflow_id, extra, exc_info)

    def critical(
        self,
        message: str,
        trace_id: str | None = None,
        span_id: str | None = None,
        workflow_id: str | None = None,
        extra: dict[str, Any] | None = None,
        exc_info: bool = True,
    ) -> None:
        """Log critical message with trace context."""
        self._log(logging.CRITICAL, message, trace_id, span_id, workflow_id, extra, exc_info)


def configure_json_logging(component: str) -> StructuredLogger:
    """Configure and return a structured logger with JSON formatting.

    Args:
        component: Component name

    Returns:
        StructuredLogger instance with JSON formatting enabled
    """
    return StructuredLogger(component, enable_json=True)


__all__ = ["JSONFormatter", "StructuredLogger", "configure_json_logging"]
