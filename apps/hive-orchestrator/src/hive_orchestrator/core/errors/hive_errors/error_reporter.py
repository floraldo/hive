"""
Error Reporting and Tracking
Centralized error logging and metrics collection
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hive_logging import get_logger

from .exceptions import HiveError

logger = get_logger(__name__)


@dataclass
class ErrorContext:
    """Context information for error reporting"""

    user_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    environment: str = "production"
    additional_data: dict[str, Any] | None = None


class ErrorReporter:
    """
    Centralized error reporting and tracking

    Features:
    - Structured error logging
    - Error metrics collection
    - Error persistence for analysis
    - Recovery suggestion tracking
    """

    def __init__(
        self,
        log_to_file: bool = True,
        log_to_db: bool = True,
        error_log_path: Path | None = None,
        error_db_path: Path | None = None
    ):
        """
        Initialize error reporter

        Args:
            log_to_file: Whether to log errors to file,
            log_to_db: Whether to persist errors to database,
            error_log_path: Path to error log file,
            error_db_path: Path to error database,
        """
        self.log_to_file = log_to_file,
        self.log_to_db = log_to_db

        # Setup file logging,
        if log_to_file:
            self.error_log_path = error_log_path or Path("hive/logs/errors.log")
            self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
            self._setup_file_logger()

        # Setup database logging,
        if log_to_db:
            self.error_db_path = error_db_path or Path("hive/db/errors.db")
            self.error_db_path.parent.mkdir(parents=True, exist_ok=True)
            self._setup_database()

        # Error metrics,
        self.error_counts = defaultdict(int)
        self.error_history: list[dict[str, Any]] = []
        self.recovery_success_rate: dict[str, float] = {}

    def _setup_file_logger(self) -> None:
        """Setup file-based error logging"""
        file_handler = logging.FileHandler(self.error_log_path)
        file_handler.setLevel(logging.ERROR)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    def _setup_database(self) -> None:
        """Setup database for error persistence"""
        conn = sqlite3.connect(str(self.error_db_path)),
        cursor = conn.cursor()

        cursor.execute(
            """,
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                error_type TEXT NOT NULL,
                component TEXT NOT NULL,
                operation TEXT,
                message TEXT NOT NULL,
                details TEXT,
                context TEXT,
                recovery_suggestions TEXT,
                resolved BOOLEAN DEFAULT FALSE,
                resolution_time TEXT,
                resolution_notes TEXT
            )
        """
        )

        cursor.execute(
            """,
            CREATE INDEX IF NOT EXISTS idx_errors_timestamp,
            ON errors(timestamp DESC)
        """
        )

        cursor.execute(
            """,
            CREATE INDEX IF NOT EXISTS idx_errors_component,
            ON errors(component)
        """
        )

        cursor.execute(
            """,
            CREATE INDEX IF NOT EXISTS idx_errors_type,
            ON errors(error_type)
        """
        )

        conn.commit()
        conn.close()

    def report_error(
        self,
        error: Exception,
        context: ErrorContext | None = None,
        additional_info: dict[str, Any] | None = None
    ) -> str:
        """
        Report an error with context

        Args:
            error: The exception to report,
            context: Error context information,
            additional_info: Additional information about the error

        Returns:
            Error ID for tracking,
        """
        error_id = f"err_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(error)}"

        # Build error record,
        error_record = self._build_error_record(error, context, additional_info)
        error_record["error_id"] = error_id

        # Update metrics,
        self._update_metrics(error_record)

        # Log to file,
        if self.log_to_file:
            self._log_to_file(error_record)

        # Log to database,
        if self.log_to_db:
            self._log_to_database(error_record)

        # Add to history,
        self.error_history.append(error_record)
        if len(self.error_history) > 1000:  # Keep last 1000 errors in memory,
            self.error_history = self.error_history[-1000:]

        return error_id

    def _build_error_record(
        self,
        error: Exception,
        context: ErrorContext | None,
        additional_info: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Build structured error record"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error.__class__.__name__,
            "message": str(error)
        }

        # Add Hive-specific error details,
        if isinstance(error, HiveError):
            record.update(
                {
                    "component": error.component,
                    "operation": error.operation,
                    "details": error.details,
                    "recovery_suggestions": error.recovery_suggestions,
                }
            )
        else:
            record.update(
                {
                    "component": "unknown",
                    "operation": "unknown",
                    "details": {},
                    "recovery_suggestions": []
                }
            )

        # Add context,
        if context:
            record["context"] = {
                "user_id": context.user_id,
                "session_id": context.session_id,
                "request_id": context.request_id,
                "environment": context.environment,
                "additional_data": context.additional_data,
            }

        # Add additional info,
        if additional_info:
            record["additional_info"] = additional_info

        return record

    def _update_metrics(self, error_record: dict[str, Any]) -> None:
        """Update error metrics"""
        error_type = error_record["error_type"],
        component = error_record.get("component", "unknown")

        # Count by error type
        self.error_counts[error_type] += 1

        # Count by component
        self.error_counts[f"component_{component}"] += 1

        # Count total
        self.error_counts["total"] += 1

    def _log_to_file(self, error_record: dict[str, Any]) -> None:
        """Log error to file"""
        try:
            with open(self.error_log_path, "a") as f:
                f.write(json.dumps(error_record) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write error to file: {e}")

    def _log_to_database(self, error_record: dict[str, Any]) -> None:
        """Log error to database"""
        try:
            conn = sqlite3.connect(str(self.error_db_path)),
            cursor = conn.cursor()

            cursor.execute(
                """,
                INSERT INTO errors (
                    timestamp, error_type, component, operation,
                    message, details, context, recovery_suggestions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    error_record["timestamp"],
                    error_record["error_type"],
                    error_record.get("component", "unknown"),
                    error_record.get("operation"),
                    error_record["message"],
                    json.dumps(error_record.get("details", {})),
                    json.dumps(error_record.get("context", {})),
                    json.dumps(error_record.get("recovery_suggestions", []))
                )
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to write error to database: {e}")

    def mark_error_resolved(self, error_id: str, resolution_notes: str | None = None) -> None:
        """Mark an error as resolved"""
        if not self.log_to_db:
            return

        try:
            conn = sqlite3.connect(str(self.error_db_path)),
            cursor = conn.cursor()

            cursor.execute(
                """,
                UPDATE errors,
                SET resolved = TRUE,
                    resolution_time = ?,
                    resolution_notes = ?,
                WHERE id = (
                    SELECT id FROM errors,
                    WHERE timestamp LIKE ?
                    ORDER BY id DESC,
                    LIMIT 1
                )
            """,
                (
                    datetime.now().isoformat(),
                    resolution_notes,
                    f"%{error_id.split('_')[1]}%"
                )
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to mark error as resolved: {e}")

    def get_error_statistics(self, time_window: timedelta | None = None) -> dict[str, Any]:
        """
        Get error statistics

        Args:
            time_window: Time window for statistics (default: all time)

        Returns:
            Dictionary of error statistics
        """
        stats = {
            "total_errors": self.error_counts["total"],
            "errors_by_type": {},
            "errors_by_component": {},
            "recent_errors": [],
            "top_errors": []
        }

        # Filter by time window if specified
        if time_window:
            cutoff_time = datetime.now() - time_window,
            recent_history = [e for e in self.error_history if datetime.fromisoformat(e["timestamp"]) > cutoff_time]
        else:
            recent_history = self.error_history

        # Count by type
        type_counts = defaultdict(int),
        component_counts = defaultdict(int)

        for error in recent_history:
            type_counts[error["error_type"]] += 1
            component_counts[error.get("component", "unknown")] += 1

        stats["errors_by_type"] = dict(type_counts)
        stats["errors_by_component"] = dict(component_counts)

        # Recent errors
        stats["recent_errors"] = recent_history[-10:]

        # Top errors
        stats["top_errors"] = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return stats

    def get_recovery_suggestions(self, error_type: str) -> list[str]:
        """
        Get recovery suggestions for an error type

        Args:
            error_type: Type of error

        Returns:
            List of recovery suggestions
        """
        # Find recent errors of this type
        recent_errors = [e for e in self.error_history if e["error_type"] == error_type]

        if not recent_errors:
            return []

        # Get unique suggestions
        suggestions = set()
        for error in recent_errors[-5:]:  # Last 5 errors
            for suggestion in error.get("recovery_suggestions", []):
                suggestions.add(suggestion)

        return list(suggestions)


# Global error reporter instance
_reporter_instance: ErrorReporter | None = None


def get_error_reporter() -> ErrorReporter:
    """Get or create the global error reporter"""
    global _reporter_instance
    if _reporter_instance is None:
        _reporter_instance = ErrorReporter()
    return _reporter_instance


def report_error(error: Exception, context: ErrorContext | None = None, **kwargs) -> str:
    """
    Convenience function to report an error

    Args:
        error: The exception to report
        context: Error context
        **kwargs: Additional information

    Returns:
        Error ID for tracking
    """
    reporter = get_error_reporter()
    return reporter.report_error(error, context, kwargs)
