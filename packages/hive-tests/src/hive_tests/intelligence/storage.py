"""
SQLite storage layer for test intelligence data.

Provides persistence for test runs, results, and analytics.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from hive_logging import get_logger

from .models import TestResult, TestRun

logger = get_logger(__name__)


class TestIntelligenceStorage:
    """SQLite-based storage for test intelligence data."""

    def __init__(self, db_path: Path | str = "data/test_intelligence.db"):
        """
        Initialize storage with database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        """
        Create database connection with optimizations and proper cleanup.

        Uses context manager for automatic connection cleanup and transaction management.
        """
        conn = None
        try:
            conn = sqlite3.Connection(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA cache_size=-64000")
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS test_runs (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    total_tests INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    failed INTEGER NOT NULL,
                    errors INTEGER NOT NULL,
                    skipped INTEGER NOT NULL,
                    duration_seconds REAL NOT NULL,
                    git_commit TEXT,
                    git_branch TEXT,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS test_results (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    test_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    error_message TEXT,
                    error_traceback TEXT,
                    package_name TEXT NOT NULL,
                    test_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER,
                    FOREIGN KEY (run_id) REFERENCES test_runs(id)
                );

                CREATE TABLE IF NOT EXISTS flaky_tests (
                    test_id TEXT PRIMARY KEY,
                    total_runs INTEGER NOT NULL,
                    passed_runs INTEGER NOT NULL,
                    failed_runs INTEGER NOT NULL,
                    error_runs INTEGER NOT NULL,
                    fail_rate REAL NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    error_messages TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS failure_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    error_signature TEXT NOT NULL,
                    affected_tests TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    packages_affected TEXT NOT NULL,
                    suggested_root_cause TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_test_results_run_id ON test_results(run_id);
                CREATE INDEX IF NOT EXISTS idx_test_results_test_id ON test_results(test_id);
                CREATE INDEX IF NOT EXISTS idx_test_results_package ON test_results(package_name);
                CREATE INDEX IF NOT EXISTS idx_test_runs_timestamp ON test_runs(timestamp);
            """
            )
            conn.commit()

    def save_test_run(self, run: TestRun) -> None:
        """Save a test run to the database."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO test_runs (
                    id, timestamp, total_tests, passed, failed, errors, skipped,
                    duration_seconds, git_commit, git_branch, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run.id,
                    run.timestamp.isoformat(),
                    run.total_tests,
                    run.passed,
                    run.failed,
                    run.errors,
                    run.skipped,
                    run.duration_seconds,
                    run.git_commit,
                    run.git_branch,
                    json.dumps(run.metadata),
                ),
            )
            conn.commit()

    def save_test_result(self, result: TestResult) -> None:
        """Save a test result to the database."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO test_results (
                    id, run_id, test_id, status, duration_ms, error_message,
                    error_traceback, package_name, test_type, file_path, line_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    result.id,
                    result.run_id,
                    result.test_id,
                    result.status.value,
                    result.duration_ms,
                    result.error_message,
                    result.error_traceback,
                    result.package_name,
                    result.test_type.value,
                    result.file_path,
                    result.line_number,
                ),
            )
            conn.commit()

    def get_recent_runs(self, limit: int = 30) -> list[TestRun]:
        """Retrieve most recent test runs."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM test_runs
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            ).fetchall()

            return [self._row_to_test_run(row) for row in rows]

    def get_test_results_for_run(self, run_id: str) -> list[TestResult]:
        """Retrieve all test results for a specific run."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM test_results
                WHERE run_id = ?
            """,
                (run_id,),
            ).fetchall()

            return [self._row_to_test_result(row) for row in rows]

    def get_test_history(self, test_id: str, limit: int = 30) -> list[TestResult]:
        """Retrieve historical results for a specific test."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT tr.* FROM test_results tr
                JOIN test_runs r ON tr.run_id = r.id
                WHERE tr.test_id = ?
                ORDER BY r.timestamp DESC
                LIMIT ?
            """,
                (test_id, limit),
            ).fetchall()

            return [self._row_to_test_result(row) for row in rows]

    def _row_to_test_run(self, row: sqlite3.Row) -> TestRun:
        """Convert database row to TestRun model."""
        return TestRun(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            total_tests=row["total_tests"],
            passed=row["passed"],
            failed=row["failed"],
            errors=row["errors"],
            skipped=row["skipped"],
            duration_seconds=row["duration_seconds"],
            git_commit=row["git_commit"],
            git_branch=row["git_branch"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def _row_to_test_result(self, row: sqlite3.Row) -> TestResult:
        """Convert database row to TestResult model."""
        from .models import TestStatus, TestType

        return TestResult(
            id=row["id"],
            run_id=row["run_id"],
            test_id=row["test_id"],
            status=TestStatus(row["status"]),
            duration_ms=row["duration_ms"],
            error_message=row["error_message"],
            error_traceback=row["error_traceback"],
            package_name=row["package_name"],
            test_type=TestType(row["test_type"]),
            file_path=row["file_path"],
            line_number=row["line_number"],
        )
