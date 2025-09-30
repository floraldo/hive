"""
AI Reviewer-specific error handling implementation.

Extends the generic error handling toolkit with AI Reviewer capabilities:
- Code review errors
- Analysis errors
- Claude service errors
- AI Reviewer-specific error reporting
"""
from __future__ import annotations


import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from hive_errors import BaseError, BaseErrorReporter, RecoveryStrategy
from hive_logging import get_logger

logger = get_logger(__name__)


class ReviewerError(BaseError):
    """
    Base error class for all AI Reviewer-specific errors.

    Extends the generic BaseError with code review context and additional
    metadata specific to the AI Reviewer service.
    """

    def __init__(
        self,
        message: str,
        component: str = "ai-reviewer",
        operation: str | None = None,
        review_id: str | None = None,
        file_path: str | None = None,
        review_phase: str | None = None,
        details: Optional[Dict[str, Any]] = None,
        recovery_suggestions: Optional[List[str]] = None,
        original_error: Exception | None = None
    ):
        """
        Initialize an AI Reviewer error with review context.

        Args:
            message: Human-readable error message,
            component: Component where error occurred,
            operation: Operation being performed,
            review_id: Active review ID if applicable,
            file_path: File being reviewed if applicable,
            review_phase: Review phase when error occurred,
            details: Additional error details,
            recovery_suggestions: Steps to recover from error,
            original_error: Original exception if wrapped,
        """
        # Build details with AI Reviewer context,
        reviewer_details = details or {}

        if review_id:
            reviewer_details["review_id"] = review_id,
        if file_path:
            reviewer_details["file_path"] = file_path,
        if review_phase:
            reviewer_details["review_phase"] = review_phase

        super().__init__(
            message=message,
            component=component,
            operation=operation,
            details=reviewer_details,
            recovery_suggestions=recovery_suggestions,
            original_error=original_error
        )

        # Store AI Reviewer-specific attributes,
        self.review_id = review_id,
        self.file_path = file_path,
        self.review_phase = review_phase,
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with AI Reviewer context"""
        data = super().to_dict()
        data["timestamp"] = self.timestamp.isoformat()
        return data


# ===============================================================================
# CODE ANALYSIS ERRORS
# ===============================================================================


class CodeAnalysisError(BaseError):
    """Base class for code analysis errors"""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(
            message=message,
            component=kwargs.get("component", "code_analyzer")
            **kwargs
        )


class FileAccessError(BaseError):
    """Error accessing or reading files for review"""

    def __init__(self, message: str, file_path: str | None = None, **kwargs) -> None:
        kwargs["file_path"] = file_path
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Check file exists and is readable",
                "Verify file permissions",
                "Ensure file is not locked",
                "Check disk space availability"
            ]
        )

        super().__init__(message=message, operation="file_access", **kwargs)


class SyntaxAnalysisError(BaseError):
    """Error parsing or analyzing code syntax"""

    def __init__(self, message: str, syntax_errors: Optional[List[str]] = None, **kwargs) -> None:
        details = kwargs.get("details", {})
        if syntax_errors:
            details["syntax_errors"] = syntax_errors

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Check code syntax for errors",
                "Verify file encoding",
                "Ensure complete code blocks",
                "Use syntax-specific analysis tools"
            ]
        )

        super().__init__(message=message, operation="syntax_analysis", **kwargs)


# ===============================================================================
# REVIEW GENERATION ERRORS
# ===============================================================================


class ReviewGenerationError(BaseError):
    """Base class for review generation errors"""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(
            message=message,
            component=kwargs.get("component", "review_generator")
            **kwargs
        )


class ClaudeServiceError(BaseError):
    """Error with Claude AI service during review generation"""

    def __init__(
        self,
        message: str,
        api_status_code: int | None = None,
        api_response: str | None = None,
        rate_limit_info: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if api_status_code:
            details["api_status_code"] = api_status_code,
        if api_response:
            details["api_response"] = api_response[:500]  # Truncate long responses,
        if rate_limit_info:
            details["rate_limit_info"] = rate_limit_info

        kwargs["details"] = details

        # Add status-specific recovery suggestions,
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
            kwargs["recovery_suggestions"] = kwargs.get(
                "recovery_suggestions",
                [
                    "Check Claude API connectivity",
                    "Verify request format",
                    "Use fallback review mechanism",
                    "Retry with exponential backoff"
                ]
            )

        super().__init__(message=message, operation="claude_service", **kwargs)


class ReviewValidationError(BaseError):
    """Error validating generated review"""

    def __init__(
        self,
        message: str,
        validation_issues: Optional[List[str]] = None,
        missing_sections: Optional[List[str]] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if validation_issues:
            details["validation_issues"] = validation_issues,
        if missing_sections:
            details["missing_sections"] = missing_sections

        kwargs["details"] = details,
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Check review format structure",
                "Verify all required sections are present",
                "Validate review completeness",
                "Review schema requirements"
            ]
        )

        super().__init__(message=message, operation="review_validation", **kwargs)


# ===============================================================================,
# DATABASE ERRORS,
# ===============================================================================


class DatabaseConnectionError(BaseError):
    """Error connecting to AI Reviewer database"""

    def __init__(
        self,
        message: str,
        db_path: str | None = None,
        retry_count: int = 0,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if db_path:
            details["db_path"] = db_path,
        details["retry_count"] = retry_count

        kwargs["details"] = details,
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Check database file exists",
                "Verify file permissions",
                "Ensure database is not locked",
                "Check disk space availability",
                "Use connection pooling"
            ]
        )

        super().__init__(message=message, component="database", operation="connection", **kwargs)
        self.retry_count = retry_count


# ===============================================================================,
# ERROR REPORTER,
# ===============================================================================


class ReviewerErrorReporter(BaseErrorReporter):
    """
    AI Reviewer-specific error reporter.

    Extends the base error reporter with review context tracking
    and AI Reviewer-specific reporting patterns.
    """

    def __init__(self) -> None:
        """Initialize the AI Reviewer error reporter"""
        super().__init__()
        self.analysis_errors: List[CodeAnalysisError] = []
        self.review_errors: List[ReviewGenerationError] = []
        self.claude_errors: List[ClaudeServiceError] = []

    def report_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Report an error with AI Reviewer-specific handling.

        Args:
            error: The error to report,
            context: Error context information,
            additional_info: Additional information about the error

        Returns:
            Error ID for tracking,
        """
        # Generate error ID,
        error_id = str(uuid.uuid4())

        # Build error record using parent method
        error_record = self._build_error_record(error, context, additional_info)
        error_record["error_id"] = error_id

        # Update metrics
        self._update_metrics(error_record)

        # Add to history
        self.error_history.append(error_record)

        # Log the error
        log_record = {k: v for k, v in error_record.items() if k != "message"}
        logger.error(f"AI Reviewer Error: {error}", extra=log_record)

        # AI Reviewer-specific categorization and handling
        if isinstance(error, CodeAnalysisError):
            self.analysis_errors.append(error)
            self._handle_analysis_error(error)
        elif isinstance(error, ReviewGenerationError):
            self.review_errors.append(error)
            self._handle_review_error(error)
        elif isinstance(error, ClaudeServiceError):
            self.claude_errors.append(error)
            self._handle_claude_error(error)

        return error_id

    def _handle_analysis_error(self, error: CodeAnalysisError) -> None:
        """Handle code analysis error reporting"""
        if error.file_path:
            logger.error(f"Code analysis failed for {error.file_path}: {error.message}")

    def _handle_review_error(self, error: ReviewGenerationError) -> None:
        """Handle review generation error reporting"""
        if error.review_id:
            logger.error(f"Review {error.review_id} generation failed: {error.message}")

    def _handle_claude_error(self, error: ClaudeServiceError) -> None:
        """Handle Claude service error reporting"""
        if hasattr(error, "details") and error.details.get("api_status_code") == 429:
            logger.warning(f"Claude API rate limit hit: {error.message}")
        else:
            logger.error(f"Claude service error: {error.message}")

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all reported errors"""
        return {
            "total_errors": self.error_counts.get("total", 0),
            "analysis_errors": len(self.analysis_errors),
            "review_errors": len(self.review_errors),
            "claude_errors": len(self.claude_errors),
            "latest_errors": self.error_history[-10:]
        }


# Global error reporter instance
_error_reporter: ReviewerErrorReporter | None = None


def get_error_reporter() -> ReviewerErrorReporter:
    """Get or create the global AI Reviewer error reporter"""
    global _error_reporter

    if _error_reporter is None:
        _error_reporter = ReviewerErrorReporter()
        logger.info("AI Reviewer error reporter initialized")

    return _error_reporter


# Export main classes and functions
__all__ = [
    # Base classes,
    "ReviewerError",
    # Code analysis errors,
    "CodeAnalysisError",
    "FileAccessError",
    "SyntaxAnalysisError",
    # Review generation errors,
    "ReviewGenerationError",
    "ClaudeServiceError",
    "ReviewValidationError",
    # Database errors,
    "DatabaseConnectionError",
    # Reporter,
    "ReviewerErrorReporter",
    "get_error_reporter"
]
