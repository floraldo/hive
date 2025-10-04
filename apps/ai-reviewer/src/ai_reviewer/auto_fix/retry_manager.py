"""
Retry Management for applying fixes and tracking attempts.

Manages the fix-retry loop with intelligent backoff and tracking.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from hive_logging import get_logger

from .error_analyzer import ParsedError
from .fix_generator import GeneratedFix

logger = get_logger(__name__)


@dataclass
class FixAttempt:
    """Record of a single fix attempt"""

    attempt_number: int
    timestamp: datetime
    fix: GeneratedFix
    success: bool
    error_message: str | None = None


@dataclass
class FixSession:
    """Complete fix session for a task"""

    task_id: str
    service_dir: Path
    max_attempts: int = 3
    attempts: list[FixAttempt] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
    final_status: str | None = None  # "fixed", "failed", "escalated"

    @property
    def attempt_count(self) -> int:
        """Current number of attempts"""
        return len(self.attempts)

    @property
    def can_retry(self) -> bool:
        """Check if more retries are allowed"""
        return self.attempt_count < self.max_attempts

    def add_attempt(self, fix: GeneratedFix, success: bool, error_message: str | None = None) -> None:
        """Record a fix attempt"""
        attempt = FixAttempt(
            attempt_number=self.attempt_count + 1,
            timestamp=datetime.now(UTC),
            fix=fix,
            success=success,
            error_message=error_message,
        )
        self.attempts.append(attempt)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            "task_id": self.task_id,
            "service_dir": str(self.service_dir),
            "max_attempts": self.max_attempts,
            "attempt_count": self.attempt_count,
            "attempts": [
                {
                    "number": a.attempt_number,
                    "timestamp": a.timestamp.isoformat(),
                    "fix_type": a.fix.fix_type,
                    "success": a.success,
                    "error": a.error_message,
                }
                for a in self.attempts
            ],
            "final_status": self.final_status,
        }


class RetryManager:
    """
    Manages the fix application and retry loop.

    Responsibilities:
    - Apply generated fixes to files
    - Create backups before modifications
    - Track retry attempts
    - Determine when to escalate
    """

    def __init__(self, max_attempts: int = 3) -> None:
        """
        Initialize retry manager.

        Args:
            max_attempts: Maximum number of fix attempts per task
        """
        self.max_attempts = max_attempts
        self.logger = logger
        self.active_sessions: dict[str, FixSession] = {}

    def start_session(self, task_id: str, service_dir: Path) -> FixSession:
        """
        Start a new fix session for a task.

        Args:
            task_id: Task identifier
            service_dir: Directory containing the service code

        Returns:
            New FixSession instance
        """
        session = FixSession(task_id=task_id, service_dir=service_dir, max_attempts=self.max_attempts)

        self.active_sessions[task_id] = session
        self.logger.info(f"Started fix session for task {task_id}")

        return session

    def apply_fix(self, session: FixSession, fix: GeneratedFix) -> bool:
        """
        Apply a generated fix to the appropriate file.

        Args:
            session: Current fix session
            fix: Generated fix to apply

        Returns:
            True if fix applied successfully, False otherwise
        """
        self.logger.info(f"Applying {fix.fix_type} fix for {fix.error.error_code}")

        try:
            # Determine target file
            file_path = session.service_dir / fix.error.file_path

            # Handle different fix types
            if fix.fix_type == "add_import":
                success = self._add_import(file_path, fix)
            elif fix.fix_type == "remove_import":
                success = self._remove_line(file_path, fix)
            elif fix.fix_type == "replace_line":
                success = self._replace_line(file_path, fix)
            else:
                self.logger.warning(f"Unknown fix type: {fix.fix_type}")
                success = False

            # Record attempt
            error_msg = None if success else f"Failed to apply {fix.fix_type}"
            session.add_attempt(fix, success, error_msg)

            return success

        except Exception as e:
            self.logger.error(f"Error applying fix: {e}")
            session.add_attempt(fix, False, str(e))
            return False

    def _add_import(self, file_path: Path, fix: GeneratedFix) -> bool:
        """
        Add an import statement to the file.

        Strategy: Add import after any existing imports, or at top of file
        """
        if not file_path.exists():
            self.logger.error(f"File not found: {file_path}")
            return False

        # Create backup
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)

        try:
            lines = file_path.read_text(encoding="utf-8").split("\n")

            # Find insertion point (after last import or at top)
            insert_index = 0
            for i, line in enumerate(lines):
                if line.strip().startswith(("import ", "from ")):
                    insert_index = i + 1

            # Insert the import
            lines.insert(insert_index, fix.fixed_line)

            # Write back
            file_path.write_text("\n".join(lines), encoding="utf-8")

            self.logger.info(f"Added import: {fix.fixed_line}")
            return True

        except Exception as e:
            # Restore backup on error
            shutil.copy2(backup_path, file_path)
            self.logger.error(f"Failed to add import: {e}")
            return False

    def _remove_line(self, file_path: Path, fix: GeneratedFix) -> bool:
        """Remove a line from the file"""
        if not file_path.exists() or fix.error.line_number is None:
            return False

        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)

        try:
            lines = file_path.read_text(encoding="utf-8").split("\n")

            # Remove the line (line numbers are 1-indexed)
            if 0 < fix.error.line_number <= len(lines):
                del lines[fix.error.line_number - 1]

            file_path.write_text("\n".join(lines), encoding="utf-8")
            self.logger.info(f"Removed line {fix.error.line_number}")
            return True

        except Exception as e:
            shutil.copy2(backup_path, file_path)
            self.logger.error(f"Failed to remove line: {e}")
            return False

    def _replace_line(self, file_path: Path, fix: GeneratedFix) -> bool:
        """Replace a specific line in the file"""
        if not file_path.exists() or fix.error.line_number is None or fix.original_line is None:
            return False

        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)

        try:
            lines = file_path.read_text(encoding="utf-8").split("\n")

            # Replace the line (line numbers are 1-indexed)
            if 0 < fix.error.line_number <= len(lines):
                lines[fix.error.line_number - 1] = fix.fixed_line

            file_path.write_text("\n".join(lines), encoding="utf-8")
            self.logger.info(f"Replaced line {fix.error.line_number}")
            return True

        except Exception as e:
            shutil.copy2(backup_path, file_path)
            self.logger.error(f"Failed to replace line: {e}")
            return False

    def rollback_session(self, session: FixSession) -> bool:
        """
        Rollback all changes made in a session.

        Args:
            session: Session to rollback

        Returns:
            True if rollback successful
        """
        self.logger.warning(f"Rolling back session for task {session.task_id}")

        success = True
        # Find all .bak files and restore them
        for backup_file in session.service_dir.rglob("*.bak"):
            try:
                original_file = backup_file.with_suffix("")
                shutil.copy2(backup_file, original_file)
                backup_file.unlink()  # Remove backup
            except Exception as e:
                self.logger.error(f"Failed to restore {backup_file}: {e}")
                success = False

        return success

    def complete_session(self, session: FixSession, status: str) -> None:
        """
        Mark a session as complete.

        Args:
            session: Session to complete
            status: Final status ("fixed", "failed", "escalated")
        """
        session.end_time = datetime.now(UTC)
        session.final_status = status

        # Clean up backup files if successful
        if status == "fixed":
            for backup_file in session.service_dir.rglob("*.bak"):
                try:
                    backup_file.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to remove backup {backup_file}: {e}")

        self.logger.info(f"Completed session for task {session.task_id}: {status}")

    def get_session(self, task_id: str) -> FixSession | None:
        """Get active session for a task"""
        return self.active_sessions.get(task_id)

    def cleanup_session(self, task_id: str) -> None:
        """Remove session from active sessions"""
        if task_id in self.active_sessions:
            del self.active_sessions[task_id]
