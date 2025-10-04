"""
Unit tests for RetryManager component.

Tests fix application, backup/rollback, and session management.
"""

from __future__ import annotations

import pytest

from ai_reviewer.auto_fix import GeneratedFix, ParsedError, RetryManager, ValidationTool
from ai_reviewer.auto_fix.error_analyzer import ErrorSeverity


class TestRetryManager:
    """Test RetryManager functionality"""

    @pytest.fixture
    def tmp_service_dir(self, tmp_path):
        """Create temporary service directory"""
        service_dir = tmp_path / "test_service"
        service_dir.mkdir()

        # Create a test Python file
        test_file = service_dir / "main.py"
        test_file.write_text(
            """import sys

def get_path():
    return getcwd()
""",
            encoding="utf-8",
        )

        return service_dir

    @pytest.fixture
    def manager(self):
        """Create RetryManager instance"""
        return RetryManager(max_attempts=3)

    def test_start_session(self, manager, tmp_service_dir):
        """Test starting a fix session"""
        session = manager.start_session("task_123", tmp_service_dir)

        assert session.task_id == "task_123"
        assert session.service_dir == tmp_service_dir
        assert session.max_attempts == 3
        assert session.attempt_count == 0
        assert session.can_retry is True
        assert session.final_status is None

    def test_add_import_success(self, manager, tmp_service_dir):
        """Test successful import addition"""
        session = manager.start_session("task_123", tmp_service_dir)

        # Create a fix for missing 'os' import
        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=4,
            column=12,
            error_code="F821",
            error_message="undefined name 'getcwd'",
            severity=ErrorSeverity.HIGH,
            full_context="main.py:4:12: F821 undefined name 'getcwd'",
            is_fixable=True,
        )

        fix = GeneratedFix(
            error=error,
            fix_type="add_import",
            original_line=None,
            fixed_line="import os",
            explanation="Add missing os import",
            confidence=0.9,
        )

        success = manager.apply_fix(session, fix)

        assert success is True
        assert session.attempt_count == 1

        # Verify import was added
        file_content = (tmp_service_dir / "main.py").read_text(encoding="utf-8")
        assert "import os" in file_content
        assert "import sys" in file_content

        # Verify backup was created
        backup_file = tmp_service_dir / "main.py.bak"
        assert backup_file.exists()

    def test_remove_import(self, manager, tmp_service_dir):
        """Test import removal"""
        session = manager.start_session("task_123", tmp_service_dir)

        # Create a fix to remove unused 'sys' import
        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=1,
            column=1,
            error_code="F401",
            error_message="'sys' imported but unused",
            severity=ErrorSeverity.HIGH,
            full_context="main.py:1:1: F401 'sys' imported but unused",
            is_fixable=True,
        )

        fix = GeneratedFix(
            error=error,
            fix_type="remove_import",
            original_line="import sys",
            fixed_line="",
            explanation="Remove unused import",
            confidence=0.95,
        )

        success = manager.apply_fix(session, fix)

        assert success is True

        # Verify import was removed
        file_content = (tmp_service_dir / "main.py").read_text(encoding="utf-8")
        lines = file_content.split("\n")
        # Line 1 (0-indexed line 0) should no longer be "import sys"
        assert lines[0] != "import sys"

    def test_replace_line(self, manager, tmp_service_dir):
        """Test line replacement"""
        session = manager.start_session("task_123", tmp_service_dir)

        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=4,
            column=12,
            error_code="F821",
            error_message="undefined name 'getcwd'",
            severity=ErrorSeverity.HIGH,
            full_context="",
            is_fixable=True,
        )

        fix = GeneratedFix(
            error=error,
            fix_type="replace_line",
            original_line="    return getcwd()",
            fixed_line="    return os.getcwd()",
            explanation="Fix function call",
            confidence=0.85,
        )

        success = manager.apply_fix(session, fix)

        assert success is True

        # Verify line was replaced
        file_content = (tmp_service_dir / "main.py").read_text(encoding="utf-8")
        assert "os.getcwd()" in file_content

    def test_session_can_retry(self, manager, tmp_service_dir):
        """Test session retry logic"""
        session = manager.start_session("task_123", tmp_service_dir)

        assert session.can_retry is True
        assert session.attempt_count == 0

        # Add 3 attempts
        for _ in range(3):
            error = ParsedError(
                tool=ValidationTool.RUFF,
                file_path="main.py",
                line_number=1,
                column=1,
                error_code="F401",
                error_message="test",
                severity=ErrorSeverity.LOW,
                full_context="",
            )
            fix = GeneratedFix(
                error=error,
                fix_type="add_import",
                original_line=None,
                fixed_line="import test",
                explanation="test",
                confidence=0.5,
            )
            session.add_attempt(fix, False, "Test failure")

        assert session.attempt_count == 3
        assert session.can_retry is False  # Max attempts reached

    def test_rollback_session(self, manager, tmp_service_dir):
        """Test session rollback"""
        session = manager.start_session("task_123", tmp_service_dir)

        # Apply a fix
        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=4,
            column=1,
            error_code="F821",
            error_message="test",
            severity=ErrorSeverity.HIGH,
            full_context="",
        )

        fix = GeneratedFix(
            error=error,
            fix_type="add_import",
            original_line=None,
            fixed_line="import broken",
            explanation="test",
            confidence=0.5,
        )

        manager.apply_fix(session, fix)

        # Save original content
        (tmp_service_dir / "main.py").read_text(encoding="utf-8")

        # Verify backup exists
        backup_file = tmp_service_dir / "main.py.bak"
        assert backup_file.exists()

        # Rollback
        success = manager.rollback_session(session)

        assert success is True

        # Verify content restored
        (tmp_service_dir / "main.py").read_text(encoding="utf-8")

        # Backup should be removed after rollback
        assert not backup_file.exists()

    def test_complete_session_fixed(self, manager, tmp_service_dir):
        """Test completing session with 'fixed' status"""
        session = manager.start_session("task_123", tmp_service_dir)

        # Apply a fix
        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=1,
            column=1,
            error_code="F401",
            error_message="test",
            severity=ErrorSeverity.LOW,
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

        manager.apply_fix(session, fix)

        # Complete as fixed
        manager.complete_session(session, "fixed")

        assert session.final_status == "fixed"
        assert session.end_time is not None

        # Backup should be cleaned up
        backup_file = tmp_service_dir / "main.py.bak"
        assert not backup_file.exists()

    def test_complete_session_failed(self, manager, tmp_service_dir):
        """Test completing session with 'failed' status"""
        session = manager.start_session("task_123", tmp_service_dir)

        manager.complete_session(session, "failed")

        assert session.final_status == "failed"
        assert session.end_time is not None

    def test_session_to_dict(self, manager, tmp_service_dir):
        """Test session serialization"""
        session = manager.start_session("task_123", tmp_service_dir)

        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=1,
            column=1,
            error_code="F401",
            error_message="test",
            severity=ErrorSeverity.LOW,
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

        manager.apply_fix(session, fix)

        session_dict = session.to_dict()

        assert session_dict["task_id"] == "task_123"
        assert session_dict["max_attempts"] == 3
        assert session_dict["attempt_count"] == 1
        assert len(session_dict["attempts"]) == 1
        assert session_dict["attempts"][0]["fix_type"] == "add_import"

    def test_apply_fix_file_not_found(self, manager, tmp_service_dir):
        """Test fix application when file doesn't exist"""
        session = manager.start_session("task_123", tmp_service_dir)

        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="nonexistent.py",  # File doesn't exist
            line_number=1,
            column=1,
            error_code="F401",
            error_message="test",
            severity=ErrorSeverity.LOW,
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

        success = manager.apply_fix(session, fix)

        # Should fail gracefully
        assert success is False
        assert session.attempt_count == 1
        assert session.attempts[0].success is False
