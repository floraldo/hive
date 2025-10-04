"""Escalation Logic for determining when to flag fixes for human review.

Analyzes fix session history and determines when autonomous fixes
are no longer viable and human intervention is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from hive_logging import get_logger

from .retry_manager import FixSession

logger = get_logger(__name__)


class EscalationReason(str, Enum):
    """Reasons for escalation to human review"""

    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    LOW_CONFIDENCE_FIXES = "low_confidence_fixes"
    COMPLEX_ERROR_PATTERN = "complex_error_pattern"
    CRITICAL_SEVERITY = "critical_severity"
    FIX_REGRESSION = "fix_regression"  # Fix made things worse


@dataclass
class EscalationDecision:
    """Decision about whether to escalate to human review"""

    should_escalate: bool
    reason: EscalationReason | None
    confidence: float  # 0.0-1.0 confidence in decision
    recommendation: str
    diagnostic_summary: dict


class EscalationLogic:
    """Determines when to escalate failed fixes to human review.

    Analyzes:
    - Number of retry attempts
    - Fix confidence scores
    - Error severity levels
    - Fix success/failure patterns
    - Regression detection
    """

    def __init__(self, max_attempts: int = 3, min_confidence_threshold: float = 0.7) -> None:
        """Initialize escalation logic.

        Args:
            max_attempts: Maximum retry attempts before escalation
            min_confidence_threshold: Minimum average confidence for auto-fixing

        """
        self.max_attempts = max_attempts
        self.min_confidence_threshold = min_confidence_threshold
        self.logger = logger

    def should_escalate(self, session: FixSession) -> EscalationDecision:
        """Determine if session should be escalated to human review.

        Args:
            session: Current fix session

        Returns:
            EscalationDecision with escalation recommendation

        """
        self.logger.info(f"Evaluating escalation for task {session.task_id}")

        # Check 1: Max retries exceeded
        if session.attempt_count >= self.max_attempts:
            return self._create_decision(
                should_escalate=True,
                reason=EscalationReason.MAX_RETRIES_EXCEEDED,
                confidence=1.0,
                recommendation=f"All {self.max_attempts} fix attempts failed. Human review required.",
                session=session,
            )

        # Check 2: Low confidence fixes
        if session.attempt_count > 0:
            avg_confidence = sum(a.fix.confidence for a in session.attempts) / session.attempt_count
            if avg_confidence < self.min_confidence_threshold:
                return self._create_decision(
                    should_escalate=True,
                    reason=EscalationReason.LOW_CONFIDENCE_FIXES,
                    confidence=0.9,
                    recommendation=f"Average fix confidence ({avg_confidence:.2f}) below threshold ({self.min_confidence_threshold}). Consider human review.",
                    session=session,
                )

        # Check 3: Critical severity errors
        critical_errors = [a for a in session.attempts if a.fix.error.severity.value == "critical"]
        if critical_errors and session.attempt_count >= 2:
            return self._create_decision(
                should_escalate=True,
                reason=EscalationReason.CRITICAL_SEVERITY,
                confidence=0.95,
                recommendation="Critical severity errors with multiple failed attempts. Human review recommended.",
                session=session,
            )

        # Check 4: Fix regression (fix made things worse)
        if self._detect_regression(session):
            return self._create_decision(
                should_escalate=True,
                reason=EscalationReason.FIX_REGRESSION,
                confidence=0.85,
                recommendation="Fix appears to have introduced new errors. Human review needed.",
                session=session,
            )

        # No escalation needed
        return self._create_decision(
            should_escalate=False,
            reason=None,
            confidence=0.8,
            recommendation="Continue with auto-fix attempts." if session.can_retry else "Session complete.",
            session=session,
        )

    def _detect_regression(self, session: FixSession) -> bool:
        """Detect if fixes are making the situation worse.

        Args:
            session: Fix session to analyze

        Returns:
            True if regression detected

        """
        # Simple heuristic: If we had a successful attempt followed by failures
        if session.attempt_count < 2:
            return False

        # Check if first attempt succeeded but later ones failed
        attempts = session.attempts
        if len(attempts) >= 2:
            if attempts[0].success and not attempts[-1].success:
                self.logger.warning("Potential regression detected: earlier success, recent failures")
                return True

        return False

    def _create_decision(
        self,
        should_escalate: bool,
        reason: EscalationReason | None,
        confidence: float,
        recommendation: str,
        session: FixSession,
    ) -> EscalationDecision:
        """Create escalation decision with diagnostic summary.

        Args:
            should_escalate: Whether to escalate
            reason: Escalation reason
            confidence: Confidence in decision
            recommendation: Human-readable recommendation
            session: Fix session

        Returns:
            Complete EscalationDecision

        """
        diagnostic_summary = self._create_diagnostic_summary(session)

        decision = EscalationDecision(
            should_escalate=should_escalate,
            reason=reason,
            confidence=confidence,
            recommendation=recommendation,
            diagnostic_summary=diagnostic_summary,
        )

        self.logger.info(
            f"Escalation decision for {session.task_id}: "
            f"escalate={should_escalate}, reason={reason}, confidence={confidence:.2f}",
        )

        return decision

    def _create_diagnostic_summary(self, session: FixSession) -> dict:
        """Create diagnostic summary for human review.

        Args:
            session: Fix session

        Returns:
            Dictionary with diagnostic information

        """
        summary = {
            "task_id": session.task_id,
            "service_dir": str(session.service_dir),
            "total_attempts": session.attempt_count,
            "max_attempts": session.max_attempts,
            "can_retry": session.can_retry,
            "attempts_summary": [],
        }

        # Summarize each attempt
        for attempt in session.attempts:
            attempt_summary = {
                "attempt_number": attempt.attempt_number,
                "timestamp": attempt.timestamp.isoformat(),
                "fix_type": attempt.fix.fix_type,
                "error_code": attempt.fix.error.error_code,
                "error_message": attempt.fix.error.error_message,
                "fix_confidence": attempt.fix.confidence,
                "success": attempt.success,
                "error": attempt.error_message,
            }
            summary["attempts_summary"].append(attempt_summary)

        # Calculate statistics
        if session.attempt_count > 0:
            summary["success_rate"] = sum(1 for a in session.attempts if a.success) / session.attempt_count
            summary["avg_confidence"] = sum(a.fix.confidence for a in session.attempts) / session.attempt_count
            summary["error_codes_encountered"] = list({a.fix.error.error_code for a in session.attempts})

        return summary

    def create_escalation_report(self, session: FixSession, decision: EscalationDecision) -> dict:
        """Create detailed escalation report for human review.

        Args:
            session: Fix session
            decision: Escalation decision

        Returns:
            Detailed report dictionary

        """
        report = {
            "task_id": session.task_id,
            "service_directory": str(session.service_dir),
            "escalation_decision": {
                "should_escalate": decision.should_escalate,
                "reason": decision.reason.value if decision.reason else None,
                "confidence": decision.confidence,
                "recommendation": decision.recommendation,
            },
            "session_summary": {
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "final_status": session.final_status,
                "total_attempts": session.attempt_count,
                "max_attempts": session.max_attempts,
            },
            "diagnostic_summary": decision.diagnostic_summary,
            "next_steps": self._recommend_next_steps(decision),
        }

        self.logger.info(f"Created escalation report for task {session.task_id}")

        return report

    def _recommend_next_steps(self, decision: EscalationDecision) -> list[str]:
        """Recommend next steps based on escalation decision.

        Args:
            decision: Escalation decision

        Returns:
            List of recommended next steps

        """
        if not decision.should_escalate:
            return ["Continue with autonomous fix attempts", "Monitor for regression"]

        # Escalation-specific recommendations
        recommendations = {
            EscalationReason.MAX_RETRIES_EXCEEDED: [
                "Review error patterns across all attempts",
                "Consider manual code inspection",
                "Check for systemic issues in generated code",
            ],
            EscalationReason.LOW_CONFIDENCE_FIXES: [
                "Review fix generator logic for this error type",
                "Consider LLM-based fix generation for complex cases",
                "Manual review of proposed fixes",
            ],
            EscalationReason.CRITICAL_SEVERITY: [
                "Immediate human review required",
                "Do not deploy until resolved",
                "Check for security implications",
            ],
            EscalationReason.FIX_REGRESSION: [
                "Rollback all attempted fixes",
                "Analyze why fixes introduced new errors",
                "Review fix application logic",
            ],
            EscalationReason.COMPLEX_ERROR_PATTERN: [
                "Manual analysis of error root cause",
                "Consider architectural changes",
                "Escalate to senior engineer",
            ],
        }

        return recommendations.get(
            decision.reason,
            ["Human review recommended", "Investigate error patterns", "Consider alternative approaches"],
        )
