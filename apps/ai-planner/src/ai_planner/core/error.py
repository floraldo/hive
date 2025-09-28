"""
AI Planner-specific error handling implementation.

Extends the generic error handling toolkit with AI Planner capabilities:
- Planning-specific errors
- Task processing errors
- Claude service errors
- AI Planner-specific error reporting
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from hive_error_handling import BaseError, BaseErrorReporter, RecoveryStrategy
from hive_logging import get_logger

logger = get_logger(__name__)


class PlannerError(BaseError):
    """
    Base error class for all AI Planner-specific errors.

    Extends the generic BaseError with planning context and additional
    metadata specific to the AI Planner service.
    """

    def __init__(
        self,
        message: str,
        component: str = "ai-planner",
        operation: Optional[str] = None,
        task_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        planning_phase: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recovery_suggestions: Optional[List[str]] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize an AI Planner error with planning context.

        Args:
            message: Human-readable error message
            component: Component where error occurred
            operation: Operation being performed
            task_id: Active task ID if applicable
            plan_id: Active plan ID if applicable
            planning_phase: Planning phase when error occurred
            details: Additional error details
            recovery_suggestions: Steps to recover from error
            original_error: Original exception if wrapped
        """
        # Build details with AI Planner context
        planner_details = details or {}

        if task_id:
            planner_details["task_id"] = task_id
        if plan_id:
            planner_details["plan_id"] = plan_id
        if planning_phase:
            planner_details["planning_phase"] = planning_phase

        super().__init__(
            message=message,
            component=component,
            operation=operation,
            details=planner_details,
            recovery_suggestions=recovery_suggestions,
            original_error=original_error
        )

        # Store AI Planner-specific attributes
        self.task_id = task_id
        self.plan_id = plan_id
        self.planning_phase = planning_phase
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with AI Planner context"""
        data = super().to_dict()
        data["timestamp"] = self.timestamp.isoformat()
        return data


# ===============================================================================
# TASK PROCESSING ERRORS
# ===============================================================================

class TaskProcessingError(PlannerError):
    """Base class for task processing errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            component=kwargs.get("component", "task_processor"),
            **kwargs
        )


class TaskValidationError(TaskProcessingError):
    """Error validating task data"""

    def __init__(
        self,
        message: str,
        validation_type: Optional[str] = None,
        failed_fields: Optional[List[str]] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if validation_type:
            details["validation_type"] = validation_type
        if failed_fields:
            details["failed_fields"] = failed_fields

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get("recovery_suggestions", [
            "Check task description format",
            "Verify required fields are present",
            "Ensure task priority is valid",
            "Review task dependencies"
        ])

        super().__init__(message=message, operation="validation", **kwargs)


class TaskQueueError(TaskProcessingError):
    """Error with task queue operations"""

    def __init__(
        self,
        message: str,
        queue_operation: Optional[str] = None,
        queue_size: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if queue_operation:
            details["queue_operation"] = queue_operation
        if queue_size is not None:
            details["queue_size"] = queue_size

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get("recovery_suggestions", [
            "Check database connectivity",
            "Verify queue table exists",
            "Check for table locks",
            "Retry queue operation"
        ])

        super().__init__(message=message, operation="queue", **kwargs)


# ===============================================================================
# PLAN GENERATION ERRORS
# ===============================================================================

class PlanGenerationError(PlannerError):
    """Base class for plan generation errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            component=kwargs.get("component", "plan_generator"),
            **kwargs
        )


class ClaudeServiceError(PlanGenerationError):
    """Error with Claude AI service"""

    def __init__(
        self,
        message: str,
        api_status_code: Optional[int] = None,
        api_response: Optional[str] = None,
        rate_limit_info: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if api_status_code:
            details["api_status_code"] = api_status_code
        if api_response:
            details["api_response"] = api_response[:500]  # Truncate long responses
        if rate_limit_info:
            details["rate_limit_info"] = rate_limit_info

        kwargs["details"] = details

        # Add status-specific recovery suggestions
        if api_status_code == 429:
            kwargs["recovery_suggestions"] = [
                "Rate limit exceeded - wait before retrying",
                "Implement exponential backoff",
                "Check rate limit configuration"
            ]
        elif api_status_code == 401:
            kwargs["recovery_suggestions"] = [
                "Check Claude API credentials",
                "Verify API key is valid",
                "Check API key permissions"
            ]
        else:
            kwargs["recovery_suggestions"] = kwargs.get("recovery_suggestions", [
                "Check Claude API connectivity",
                "Verify request format",
                "Use fallback planning mechanism",
                "Retry with exponential backoff"
            ])

        super().__init__(message=message, operation="claude_service", **kwargs)


class PlanValidationError(PlanGenerationError):
    """Error validating generated plan"""

    def __init__(
        self,
        message: str,
        plan_structure_issues: Optional[List[str]] = None,
        missing_fields: Optional[List[str]] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if plan_structure_issues:
            details["plan_structure_issues"] = plan_structure_issues
        if missing_fields:
            details["missing_fields"] = missing_fields

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get("recovery_suggestions", [
            "Check plan JSON structure",
            "Verify all required fields are present",
            "Validate subtask dependencies",
            "Review plan schema requirements"
        ])

        super().__init__(message=message, operation="plan_validation", **kwargs)


# ===============================================================================
# DATABASE ERRORS
# ===============================================================================

class DatabaseConnectionError(PlannerError):
    """Error connecting to AI Planner database"""

    def __init__(
        self,
        message: str,
        db_path: Optional[str] = None,
        retry_count: int = 0,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if db_path:
            details["db_path"] = db_path
        details["retry_count"] = retry_count

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get("recovery_suggestions", [
            "Check database file exists",
            "Verify file permissions",
            "Ensure database is not locked",
            "Check disk space availability",
            "Use connection pooling"
        ])

        super().__init__(
            message=message,
            component="database",
            operation="connection",
            **kwargs
        )
        self.retry_count = retry_count


# ===============================================================================
# ERROR REPORTER
# ===============================================================================

class PlannerErrorReporter(BaseErrorReporter):
    """
    AI Planner-specific error reporter.

    Extends the base error reporter with planning context tracking
    and AI Planner-specific reporting patterns.
    """

    def __init__(self):
        """Initialize the AI Planner error reporter"""
        super().__init__()
        self.task_errors: List[TaskProcessingError] = []
        self.plan_errors: List[PlanGenerationError] = []
        self.claude_errors: List[ClaudeServiceError] = []

    def report_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Report an error with AI Planner-specific handling.

        Args:
            error: The error to report
            context: Error context information
            additional_info: Additional information about the error

        Returns:
            Error ID for tracking
        """
        # Generate error ID
        error_id = str(uuid.uuid4())

        # Build error record using parent method
        error_record = self._build_error_record(error, context, additional_info)
        error_record["error_id"] = error_id

        # Update metrics
        self._update_metrics(error_record)

        # Add to history
        self.error_history.append(error_record)

        # Log the error
        log_record = {k: v for k, v in error_record.items() if k != 'message'}
        logger.error(f"AI Planner Error: {error}", extra=log_record)

        # AI Planner-specific categorization and handling
        if isinstance(error, TaskProcessingError):
            self.task_errors.append(error)
            self._handle_task_error(error)
        elif isinstance(error, PlanGenerationError):
            self.plan_errors.append(error)
            self._handle_plan_error(error)
        elif isinstance(error, ClaudeServiceError):
            self.claude_errors.append(error)
            self._handle_claude_error(error)

        return error_id

    def _handle_task_error(self, error: TaskProcessingError) -> None:
        """Handle task-specific error reporting"""
        if error.task_id:
            logger.error(f"Task {error.task_id} processing failed: {error.message}")

    def _handle_plan_error(self, error: PlanGenerationError) -> None:
        """Handle plan generation error reporting"""
        if error.plan_id:
            logger.error(f"Plan {error.plan_id} generation failed: {error.message}")

    def _handle_claude_error(self, error: ClaudeServiceError) -> None:
        """Handle Claude service error reporting"""
        if hasattr(error, 'details') and error.details.get('api_status_code') == 429:
            logger.warning(f"Claude API rate limit hit: {error.message}")
        else:
            logger.error(f"Claude service error: {error.message}")

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all reported errors"""
        return {
            "total_errors": self.error_counts.get("total", 0),
            "task_errors": len(self.task_errors),
            "plan_errors": len(self.plan_errors),
            "claude_errors": len(self.claude_errors),
            "latest_errors": self.error_history[-10:]
        }


# Global error reporter instance
_error_reporter: Optional[PlannerErrorReporter] = None


def get_error_reporter() -> PlannerErrorReporter:
    """Get or create the global AI Planner error reporter"""
    global _error_reporter

    if _error_reporter is None:
        _error_reporter = PlannerErrorReporter()
        logger.info("AI Planner error reporter initialized")

    return _error_reporter


# Export main classes and functions
__all__ = [
    # Base classes
    "PlannerError",

    # Task processing errors
    "TaskProcessingError",
    "TaskValidationError",
    "TaskQueueError",

    # Plan generation errors
    "PlanGenerationError",
    "ClaudeServiceError",
    "PlanValidationError",

    # Database errors
    "DatabaseConnectionError",

    # Reporter
    "PlannerErrorReporter",
    "get_error_reporter"
]