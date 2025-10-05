from __future__ import annotations

"""
Core review logic for analyzing code quality, tests, and documentation
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

# TODO: hive_claude_bridge module doesn't exist - needs to be created or imported from correct location
# from hive_claude_bridge import ClaudeBridgeConfig, RateLimitConfig, get_claude_service
from pydantic import BaseModel, Field

from hive_bus import UnifiedEventType, create_task_event, get_global_registry
from hive_config import create_config_from_sources
from hive_logging import get_logger

from .core.errors import ReviewerError, ReviewValidationError
from .inspector_bridge import InspectorBridge

logger = get_logger(__name__)


class ReviewDecision(Enum):
    """Possible review decisions"""

    APPROVE = ("approve",)
    REJECT = ("reject",)
    REWORK = ("rework",)
    ESCALATE = "escalate"


class QualityMetrics(BaseModel):
    """Quality metrics for code review"""

    code_quality: float = Field(ge=0, le=100, description="Code quality score")
    test_coverage: float = Field(ge=0, le=100, description="Test coverage score")
    documentation: float = Field(ge=0, le=100, description="Documentation quality score")
    security: float = Field(ge=0, le=100, description="Security assessment score")
    architecture: float = Field(ge=0, le=100, description="Architecture quality score")

    @property
    def overall_score(self) -> float:
        """Calculate weighted overall score"""
        weights = {
            "code_quality": 0.3,
            "test_coverage": 0.25,
            "documentation": 0.15,
            "security": 0.2,
            "architecture": 0.1,
        }

        total = sum(getattr(self, metric) * weight for metric, weight in weights.items())
        return round(total, 2)


@dataclass
class ReviewResult:
    """Result of an AI review"""

    task_id: str
    decision: ReviewDecision
    metrics: QualityMetrics
    summary: str
    issues: list[str]
    suggestions: list[str]
    confidence: float
    escalation_reason: str | None = None
    confusion_points: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage"""
        result = {
            "task_id": self.task_id,
            "decision": self.decision.value,
            "metrics": self.metrics.model_dump(),
            "overall_score": self.metrics.overall_score,
            "summary": self.summary,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "confidence": self.confidence,
        }

        if self.escalation_reason:
            result["escalation_reason"] = self.escalation_reason

        if self.confusion_points:
            result["confusion_points"] = self.confusion_points

        return result


class ReviewEngine:
    """AI-powered code review engine using Claude CLI
    """

    def __init__(self, mock_mode: bool = False) -> None:
        """Initialize review engine

        Args:
            mock_mode: If True, use mock responses for testing

        """
        # Load configuration
        self.config = create_config_from_sources()

        # Initialize event bus for unified events
        self.event_bus = get_global_registry()

        # Initialize Claude service with rate limiting
        config = (ClaudeBridgeConfig(mock_mode=mock_mode),)
        rate_config = RateLimitConfig(
            max_calls_per_minute=15,  # Reviews are more intensive,
            max_calls_per_hour=300,
        )
        self.claude_service = get_claude_service(config=config, rate_config=rate_config)
        self.inspector = InspectorBridge()

        # Initialize error reporter,
        self.error_reporter = ErrorReporter(component_name="ai-reviewer")

        # Review thresholds,
        self.thresholds = {
            "approve_threshold": 80.0,  # Overall score needed for approval,
            "reject_threshold": 40.0,  # Below this is automatic rejection,
            "escalate_threshold": 60.0,  # Between reject and this = escalate,
            "confidence_threshold": 0.7,  # Minimum confidence for auto-decision,
        }

    def _emit_event(
        self,
        event_type: UnifiedEventType,
        task_id: str,
        correlation_id: str,
        additional_data: dict[str, Any] | None = None,
    ) -> None:
        """Emit unified event if feature flag is enabled.

        Args:
            event_type: Type of event to emit
            task_id: Task identifier
            correlation_id: Correlation ID for tracking
            additional_data: Additional event payload data
        """
        # Only emit if unified events are enabled and this agent is in the list
        if not self.config.features.enable_unified_events:
            return

        if "ai-reviewer" not in self.config.features.unified_events_agents:
            return

        # Create and emit event
        event = create_task_event(
            event_type=event_type,
            task_id=task_id,
            correlation_id=correlation_id,
            source_agent="ai-reviewer",
            additional_data=additional_data or {},
        )

        self.event_bus.emit(event)
        logger.debug(f"Emitted event: {event_type} for task {task_id}")

    def review_task(
        self,
        task_id: str,
        task_description: str,
        code_files: dict[str, str],
        test_results: dict[str, Any] | None = None,
        transcript: str | None = None,
        correlation_id: str | None = None,
    ) -> ReviewResult:
        """Perform AI review of a task

        Args:
            task_id: Unique task identifier,
            task_description: What the task was supposed to accomplish,
            code_files: Dictionary of filename -> content,
            test_results: Test execution results if available,
            transcript: Claude conversation transcript if available
            correlation_id: Optional correlation ID for event tracking

        Returns:
            ReviewResult with decision and metrics,

        """
        # Use task_id as correlation_id if not provided
        correlation_id = correlation_id or task_id

        # Emit review requested event
        self._emit_event(
            event_type=UnifiedEventType.REVIEW_REQUESTED,
            task_id=task_id,
            correlation_id=correlation_id,
            additional_data={
                "code_files_count": len(code_files),
                "has_test_results": test_results is not None,
                "has_transcript": transcript is not None,
            },
        )

        # Step 1: Run objective analysis using inspect_run.py,
        try:
            objective_analysis = self.inspector.inspect_task_run(task_id)
        except Exception as e:
            error = ReviewerError(message=f"Failed to run objective analysis for task {task_id}", original_error=e)
            self.error_reporter.report_error(error)
            objective_analysis = None

        # Step 2: Use Claude service for comprehensive review,
        try:
            claude_result = self.claude_service.review_code(
                task_id=task_id,
                task_description=task_description,
                code_files=code_files,
                test_results=test_results,
                objective_analysis=objective_analysis,
                transcript=transcript,
                use_cache=False,  # Don't cache reviews as code changes frequently
            )
        except Exception as e:
            error = ReviewerError(message=f"Failed to get Claude review for task {task_id}", original_error=e)
            self.error_reporter.report_error(error)
            # Create fallback result,
            claude_result = {
                "decision": "escalate",
                "summary": f"Review failed: {e!s}",
                "issues": ["Review process encountered an error"],
                "suggestions": ["Manual review required"],
                "confidence": 0.0,
                "escalation_reason": f"Claude review failed: {e!s}",
            }

        # Step 3: Extract validated results,
        decision_str = claude_result.get("decision", "escalate")
        try:
            decision = ReviewDecision(decision_str)
        except ValueError:
            error = ReviewValidationError(
                message=f"Invalid review decision: {decision_str}",
                field="decision",
                value=decision_str,
            )
            (self.error_reporter.report_error(error, severity="WARNING"),)
            decision = ReviewDecision.ESCALATE

        # Extract metrics from validated response,
        claude_metrics = claude_result.get("metrics", {})
        metrics = QualityMetrics(
            code_quality=claude_metrics.get("code_quality", 50),
            test_coverage=claude_metrics.get("testing", 50),
            documentation=claude_metrics.get("documentation", 50),
            security=claude_metrics.get("security", 50),
            architecture=claude_metrics.get("architecture", 50),
        )

        # Extract other fields from validated response,
        summary = claude_result.get("summary", "Review completed")
        issues = claude_result.get("issues", [])
        suggestions = claude_result.get("suggestions", [])
        confidence = claude_result.get("confidence", 0.5)

        # Check for escalation,
        escalation_reason = claude_result.get("escalation_reason"),
        confusion_points = None

        if decision == ReviewDecision.ESCALATE and escalation_reason:
            confusion_points = [escalation_reason]

        # Create review result
        result = ReviewResult(
            task_id=task_id,
            decision=decision,
            metrics=metrics,
            summary=summary,
            issues=issues,
            suggestions=suggestions,
            confidence=confidence,
            escalation_reason=escalation_reason,
            confusion_points=confusion_points,
        )

        # Emit review completed event
        self._emit_event(
            event_type=UnifiedEventType.REVIEW_COMPLETED,
            task_id=task_id,
            correlation_id=correlation_id,
            additional_data={
                "decision": decision.value[0] if isinstance(decision.value, tuple) else decision.value,
                "overall_score": metrics.overall_score,
                "confidence": confidence,
                "issues_count": len(issues),
                "suggestions_count": len(suggestions),
            },
        )

        return result
