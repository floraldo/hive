"""
Generic error reporting base class.

Provides reusable patterns for error reporting and metrics
that can be extended for any system.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from hive_logging import get_logger

from .base_exceptions import BaseError


class BaseErrorReporter(ABC):
    """
    Generic base error reporter.

    Provides fundamental error reporting patterns:
    - Error metrics collection
    - Recovery tracking
    - Error history management

    Subclasses must implement storage mechanisms.
    """

    def __init__(self):
        """Initialize the base error reporter"""
        self.error_counts = defaultdict(int)
        self.error_history: List[Dict[str, Any]] = []
        self.recovery_success_rate: Dict[str, float] = {}

    @abstractmethod
    def report_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Report an error with context.

        Args:
            error: The exception to report
            context: Error context information
            additional_info: Additional information about the error

        Returns:
            Error ID for tracking
        """
        pass

    def _build_error_record(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]],
        additional_info: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build structured error record"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error.__class__.__name__,
            "message": str(error),
        }

        # Add structured error details if available
        if isinstance(error, BaseError):
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
                    "recovery_suggestions": [],
                }
            )

        # Add context
        if context:
            record["context"] = context

        # Add additional info
        if additional_info:
            record["additional_info"] = additional_info

        return record

    def _update_metrics(self, error_record: Dict[str, Any]):
        """Update error metrics"""
        error_type = error_record["error_type"]
        component = error_record.get("component", "unknown")

        # Count by error type
        self.error_counts[error_type] += 1

        # Count by component
        self.error_counts[f"component_{component}"] += 1

        # Count total
        self.error_counts["total"] += 1

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            "total_errors": self.error_counts["total"],
            "errors_by_type": {
                k: v for k, v in self.error_counts.items() if not k.startswith("component_") and k != "total"
            },
            "errors_by_component": {
                k.replace("component_", ""): v for k, v in self.error_counts.items() if k.startswith("component_")
            },
            "recent_errors": self.error_history[-10:],
        }

    def get_recovery_suggestions(self, error_type: str) -> List[str]:
        """Get recovery suggestions for an error type"""
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
