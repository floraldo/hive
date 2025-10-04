"""Unit tests for EscalationLogic component.

Tests escalation decision making and reporting.
"""

from __future__ import annotations

import pytest

from ai_reviewer.auto_fix import (
    EscalationLogic,
    EscalationReason,
    GeneratedFix,
    ParsedError,
    RetryManager,
    ValidationTool,
)
from ai_reviewer.auto_fix.error_analyzer import ErrorSeverity


class TestEscalationLogic:
    """Test EscalationLogic functionality"""

    @pytest.fixture
    def escalation(self):
        """Create EscalationLogic instance"""
        return EscalationLogic(max_attempts=3, min_confidence_threshold=0.7)

    @pytest.fixture
    def retry_manager(self):
        """Create RetryManager instance"""
        return RetryManager(max_attempts=3)

    @pytest.fixture
    def tmp_service_dir(self, tmp_path):
        """Create temporary service directory"""
        service_dir = tmp_path / "test_service"
        service_dir.mkdir()
        return service_dir

    def test_should_escalate_max_retries_exceeded(self, escalation, retry_manager, tmp_service_dir):
        """Test escalation when max retries exceeded"""
        session = retry_manager.start_session("task_123", tmp_service_dir)

        # Add 3 failed attempts
        for i in range(3):
            error = ParsedError(
                tool=ValidationTool.RUFF,
                file_path="main.py",
                line_number=1,
                column=1,
                error_code="F821",
                error_message=f"error {i}",
                severity=ErrorSeverity.HIGH,
                full_context="",
            )

            fix = GeneratedFix(
                error=error,
                fix_type="add_import",
                original_line=None,
                fixed_line="import test",
                explanation="test",
                confidence=0.8,
            )

            session.add_attempt(fix, False, f"Failed attempt {i+1}")

        decision = escalation.should_escalate(session)

        assert decision.should_escalate is True
        assert decision.reason == EscalationReason.MAX_RETRIES_EXCEEDED
        assert decision.confidence == 1.0
        assert "3 fix attempts failed" in decision.recommendation

    def test_should_escalate_low_confidence(self, escalation, retry_manager, tmp_service_dir):
        """Test escalation when fix confidence is low"""
        session = retry_manager.start_session("task_123", tmp_service_dir)

        # Add 2 attempts with low confidence (< 0.7 threshold)
        for _i in range(2):
            error = ParsedError(
                tool=ValidationTool.RUFF,
                file_path="main.py",
                line_number=1,
                column=1,
                error_code="F821",
                error_message="unknown module",
                severity=ErrorSeverity.HIGH,
                full_context="",
            )

            fix = GeneratedFix(
                error=error,
                fix_type="add_import",
                original_line=None,
                fixed_line="import unknown",
                explanation="test",
                confidence=0.5,  # Low confidence
            )

            session.add_attempt(fix, False, "Failed")

        decision = escalation.should_escalate(session)

        assert decision.should_escalate is True
        assert decision.reason == EscalationReason.LOW_CONFIDENCE_FIXES
        assert decision.confidence == 0.9

    def test_should_escalate_critical_severity(self, escalation, retry_manager, tmp_service_dir):
        """Test escalation for critical errors with multiple failures"""
        session = retry_manager.start_session("task_123", tmp_service_dir)

        # Add 2 attempts with critical severity
        for _i in range(2):
            error = ParsedError(
                tool=ValidationTool.PYTEST,
                file_path="main.py",
                line_number=1,
                column=1,
                error_code="ImportError",
                error_message="critical import failure",
                severity=ErrorSeverity.CRITICAL,  # Critical severity
                full_context="",
            )

            fix = GeneratedFix(
                error=error,
                fix_type="add_import",
                original_line=None,
                fixed_line="import critical",
                explanation="test",
                confidence=0.8,
            )

            session.add_attempt(fix, False, "Failed")

        decision = escalation.should_escalate(session)

        assert decision.should_escalate is True
        assert decision.reason == EscalationReason.CRITICAL_SEVERITY
        assert decision.confidence == 0.95

    def test_should_not_escalate_can_retry(self, escalation, retry_manager, tmp_service_dir):
        """Test no escalation when can still retry"""
        session = retry_manager.start_session("task_123", tmp_service_dir)

        # Add only 1 attempt
        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=1,
            column=1,
            error_code="F821",
            error_message="error",
            severity=ErrorSeverity.MEDIUM,
            full_context="",
        )

        fix = GeneratedFix(
            error=error,
            fix_type="add_import",
            original_line=None,
            fixed_line="import test",
            explanation="test",
            confidence=0.8,  # Good confidence
        )

        session.add_attempt(fix, False, "Failed")

        decision = escalation.should_escalate(session)

        assert decision.should_escalate is False
        assert decision.reason is None
        assert "Continue with auto-fix" in decision.recommendation

    def test_detect_regression(self, escalation, retry_manager, tmp_service_dir):
        """Test regression detection"""
        session = retry_manager.start_session("task_123", tmp_service_dir)

        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=1,
            column=1,
            error_code="F821",
            error_message="error",
            severity=ErrorSeverity.MEDIUM,
            full_context="",
        )

        fix = GeneratedFix(
            error=error,
            fix_type="add_import",
            original_line=None,
            fixed_line="import test",
            explanation="test",
            confidence=0.8,
        )

        # First attempt succeeds
        session.add_attempt(fix, True, None)

        # Second attempt fails (regression)
        session.add_attempt(fix, False, "New error")

        regression = escalation._detect_regression(session)

        assert regression is True

    def test_create_diagnostic_summary(self, escalation, retry_manager, tmp_service_dir):
        """Test diagnostic summary creation"""
        session = retry_manager.start_session("task_123", tmp_service_dir)

        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=1,
            column=1,
            error_code="F821",
            error_message="undefined name",
            severity=ErrorSeverity.HIGH,
            full_context="",
        )

        fix = GeneratedFix(
            error=error,
            fix_type="add_import",
            original_line=None,
            fixed_line="import test",
            explanation="test",
            confidence=0.8,
        )

        session.add_attempt(fix, False, "Failed")
        session.add_attempt(fix, True, None)

        summary = escalation._create_diagnostic_summary(session)

        assert summary["task_id"] == "task_123"
        assert summary["total_attempts"] == 2
        assert summary["max_attempts"] == 3
        assert summary["can_retry"] is True
        assert len(summary["attempts_summary"]) == 2
        assert summary["success_rate"] == 0.5  # 1 success out of 2
        assert summary["avg_confidence"] == 0.8
        assert "F821" in summary["error_codes_encountered"]

    def test_create_escalation_report(self, escalation, retry_manager, tmp_service_dir):
        """Test escalation report creation"""
        session = retry_manager.start_session("task_123", tmp_service_dir)

        # Add 3 failed attempts to trigger escalation
        for i in range(3):
            error = ParsedError(
                tool=ValidationTool.RUFF,
                file_path="main.py",
                line_number=1,
                column=1,
                error_code="F821",
                error_message="error",
                severity=ErrorSeverity.HIGH,
                full_context="",
            )

            fix = GeneratedFix(
                error=error,
                fix_type="add_import",
                original_line=None,
                fixed_line="import test",
                explanation="test",
                confidence=0.8,
            )

            session.add_attempt(fix, False, f"Failed {i+1}")

        decision = escalation.should_escalate(session)
        report = escalation.create_escalation_report(session, decision)

        assert report["task_id"] == "task_123"
        assert report["escalation_decision"]["should_escalate"] is True
        assert report["escalation_decision"]["reason"] == "max_retries_exceeded"
        assert report["session_summary"]["total_attempts"] == 3
        assert "next_steps" in report
        assert len(report["next_steps"]) > 0

    def test_recommend_next_steps_max_retries(self, escalation):
        """Test next steps recommendation for max retries"""
        from ai_reviewer.auto_fix.escalation import EscalationDecision

        decision = EscalationDecision(
            should_escalate=True,
            reason=EscalationReason.MAX_RETRIES_EXCEEDED,
            confidence=1.0,
            recommendation="test",
            diagnostic_summary={},
        )

        next_steps = escalation._recommend_next_steps(decision)

        assert "Review error patterns" in next_steps[0]
        assert len(next_steps) >= 3

    def test_recommend_next_steps_low_confidence(self, escalation):
        """Test next steps recommendation for low confidence"""
        from ai_reviewer.auto_fix.escalation import EscalationDecision

        decision = EscalationDecision(
            should_escalate=True,
            reason=EscalationReason.LOW_CONFIDENCE_FIXES,
            confidence=0.9,
            recommendation="test",
            diagnostic_summary={},
        )

        next_steps = escalation._recommend_next_steps(decision)

        assert any("fix generator" in step.lower() for step in next_steps)

    def test_escalation_with_no_attempts(self, escalation, retry_manager, tmp_service_dir):
        """Test escalation logic with no attempts yet"""
        session = retry_manager.start_session("task_123", tmp_service_dir)

        decision = escalation.should_escalate(session)

        # Should not escalate if no attempts made yet
        assert decision.should_escalate is False
        assert "Continue with auto-fix" in decision.recommendation
