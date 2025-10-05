"""Dead Letter Queue (DLQ) for permanently failed tasks.

Manages tasks that have exhausted all retry attempts and require manual intervention.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class DLQEntry:
    """Dead letter queue entry for a failed task.

    Attributes:
        task_id: Task identifier
        feature: Original feature description
        target_url: Target URL for validation
        failure_reason: Final error message
        retry_count: Number of retries attempted
        workflow_state: Final workflow state (JSON)
        created_at: When task was originally created
        failed_at: When task entered DLQ
        last_error_phase: Workflow phase where final failure occurred
    """

    task_id: str
    feature: str
    target_url: str
    failure_reason: str
    retry_count: int
    workflow_state: dict | None
    created_at: datetime
    failed_at: datetime
    last_error_phase: str | None = None


class DeadLetterQueue:
    """Dead Letter Queue for permanently failed tasks.

    Stores tasks that have exhausted all retry attempts for manual review
    and intervention.

    Example:
        dlq = DeadLetterQueue(db_path=Path("chimera_tasks.db"))
        await dlq.initialize()
        await dlq.add_entry(task_id, feature, error, retry_count, workflow_state)
        failed_tasks = await dlq.get_entries(limit=10)
    """

    def __init__(self, db_path: Path, pool_size: int = 5):
        """Initialize dead letter queue.

        Args:
            db_path: Path to SQLite database file
            pool_size: Maximum number of database connections in pool (default: 5)
        """
        self.db_path = db_path
        self.logger = logger
        self._pool_size = pool_size
        self._connection_pool: Queue = Queue(maxsize=pool_size)
        self._initialized = False

    @asynccontextmanager
    async def _get_connection(self):
        """Get database connection from pool.

        Yields:
            SQLite connection from pool
        """
        # Try to get existing connection from pool
        try:
            conn = self._connection_pool.get_nowait()
        except Exception:  # noqa: S110
            # Pool empty - create new connection
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Performance optimization

        try:
            yield conn
        finally:
            # Return connection to pool
            try:
                self._connection_pool.put_nowait(conn)
            except Exception:  # noqa: S110
                # Pool full - close connection
                conn.close()

    async def initialize(self) -> None:
        """Initialize DLQ schema and connection pool.

        Creates dlq_entries table if it doesn't exist.
        """
        async with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS dlq_entries (
                    task_id TEXT PRIMARY KEY,
                    feature TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    failure_reason TEXT NOT NULL,
                    retry_count INTEGER NOT NULL,
                    workflow_state TEXT,
                    created_at TEXT NOT NULL,
                    failed_at TEXT NOT NULL,
                    last_error_phase TEXT
                )
            """
            )

            conn.commit()

        self._initialized = True
        self.logger.info(f"DLQ schema initialized with connection pool (size={self._pool_size})")

    async def add_entry(
        self,
        task_id: str,
        feature: str,
        target_url: str,
        failure_reason: str,
        retry_count: int,
        workflow_state: dict | None = None,
        created_at: datetime | None = None,
        last_error_phase: str | None = None,
    ) -> None:
        """Add failed task to DLQ.

        Args:
            task_id: Task identifier
            feature: Feature description
            target_url: Target URL
            failure_reason: Error message
            retry_count: Number of retries attempted
            workflow_state: Final workflow state
            created_at: Original creation time (defaults to now)
            last_error_phase: Phase where failure occurred
        """
        async with self._get_connection() as conn:
            cursor = conn.cursor()

            created_at = created_at or datetime.now()
            failed_at = datetime.now()

            # Serialize workflow state to JSON
            workflow_state_json = (
                json.dumps(workflow_state) if workflow_state else None
            )

            cursor.execute(
                """
                INSERT INTO dlq_entries
                (task_id, feature, target_url, failure_reason, retry_count,
                 workflow_state, created_at, failed_at, last_error_phase)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task_id,
                    feature,
                    target_url,
                    failure_reason,
                    retry_count,
                    workflow_state_json,
                    created_at.isoformat(),
                    failed_at.isoformat(),
                    last_error_phase,
                ),
            )

            conn.commit()

        self.logger.warning(
            f"Task {task_id} added to DLQ after {retry_count} retries: {failure_reason}"
        )

    async def get_entries(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DLQEntry]:
        """Get DLQ entries.

        Args:
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of DLQ entries, newest first
        """
        async with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT task_id, feature, target_url, failure_reason, retry_count,
                       workflow_state, created_at, failed_at, last_error_phase
                FROM dlq_entries
                ORDER BY failed_at DESC, task_id DESC
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            )

            rows = cursor.fetchall()

        entries = []
        for row in rows:
            workflow_state = json.loads(row[5]) if row[5] else None

            entries.append(
                DLQEntry(
                    task_id=row[0],
                    feature=row[1],
                    target_url=row[2],
                    failure_reason=row[3],
                    retry_count=row[4],
                    workflow_state=workflow_state,
                    created_at=datetime.fromisoformat(row[6]),
                    failed_at=datetime.fromisoformat(row[7]),
                    last_error_phase=row[8],
                )
            )

        return entries

    async def get_entry(self, task_id: str) -> DLQEntry | None:
        """Get specific DLQ entry by task ID.

        Args:
            task_id: Task identifier

        Returns:
            DLQ entry if found, None otherwise
        """
        async with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT task_id, feature, target_url, failure_reason, retry_count,
                       workflow_state, created_at, failed_at, last_error_phase
                FROM dlq_entries
                WHERE task_id = ?
            """,
                (task_id,),
            )

            row = cursor.fetchone()

        if not row:
            return None

        workflow_state = json.loads(row[5]) if row[5] else None

        return DLQEntry(
            task_id=row[0],
            feature=row[1],
            target_url=row[2],
            failure_reason=row[3],
            retry_count=row[4],
            workflow_state=workflow_state,
            created_at=datetime.fromisoformat(row[6]),
            failed_at=datetime.fromisoformat(row[7]),
            last_error_phase=row[8],
        )

    async def remove_entry(self, task_id: str) -> bool:
        """Remove entry from DLQ (after manual resolution).

        Args:
            task_id: Task identifier to remove

        Returns:
            True if entry was removed, False if not found
        """
        async with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("DELETE FROM dlq_entries WHERE task_id = ?", (task_id,))

            removed = cursor.rowcount > 0
            conn.commit()

        if removed:
            self.logger.info(f"Task {task_id} removed from DLQ")
        else:
            self.logger.warning(f"Task {task_id} not found in DLQ")

        return removed

    async def count(self) -> int:
        """Get total number of entries in DLQ.

        Returns:
            Number of failed tasks in DLQ
        """
        async with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM dlq_entries")
            count = cursor.fetchone()[0]

        return count

    async def close(self) -> None:
        """Close all pooled connections.

        Should be called during shutdown to cleanup resources.
        """
        closed_count = 0
        while not self._connection_pool.empty():
            try:
                conn = self._connection_pool.get_nowait()
                conn.close()
                closed_count += 1
            except Exception:  # noqa: S110
                break

        self.logger.info(f"Closed {closed_count} pooled database connections")


__all__ = ["DeadLetterQueue", "DLQEntry"]
