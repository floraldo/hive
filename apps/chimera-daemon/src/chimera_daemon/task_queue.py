"""Task Queue - SQLite-backed queue for Chimera workflow tasks.

Provides persistent task storage with CRUD operations for autonomous execution.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from hive_logging import get_logger
from pydantic import BaseModel

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QueuedTask(BaseModel):
    """Task in execution queue."""

    task_id: str
    feature_description: str
    target_url: str
    staging_url: str | None = None
    priority: int = 5
    status: TaskStatus = TaskStatus.QUEUED
    workflow_state: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TaskQueue:
    """SQLite-backed task queue for Chimera workflows.

    Provides:
    - Persistent task storage
    - CRUD operations (create, read, update, delete)
    - Status tracking (queued, running, completed, failed)
    - Priority-based retrieval

    Example:
        queue = TaskQueue(db_path="tasks.db")
        await queue.initialize()

        # Enqueue task
        task_id = await queue.enqueue(
            feature="User login",
            target_url="https://app.dev",
            priority=8
        )

        # Get next task
        task = await queue.get_next_task()

        # Update status
        await queue.mark_running(task.task_id)
        await queue.mark_completed(task.task_id, result={...})
    """

    def __init__(self, db_path: str | Path = "tasks.db"):
        """Initialize task queue.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.logger = logger

    async def initialize(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                feature_description TEXT NOT NULL,
                target_url TEXT NOT NULL,
                staging_url TEXT,
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'queued',
                workflow_state TEXT,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            )
        """)

        # Index for efficient status queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status_priority
            ON tasks(status, priority DESC, created_at ASC)
        """)

        conn.commit()
        conn.close()

        self.logger.info(f"Task queue initialized: {self.db_path}")

    async def enqueue(
        self,
        task_id: str,
        feature: str,
        target_url: str,
        staging_url: str | None = None,
        priority: int = 5,
    ) -> str:
        """Enqueue new task.

        Args:
            task_id: Unique task identifier
            feature: Feature description
            target_url: Target URL for testing
            staging_url: Staging URL (optional)
            priority: Task priority (1-10, higher = more urgent)

        Returns:
            Task ID
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        created_at = datetime.now(UTC).isoformat()

        cursor.execute(
            """
            INSERT INTO tasks (
                task_id, feature_description, target_url, staging_url,
                priority, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, feature, target_url, staging_url, priority, TaskStatus.QUEUED.value, created_at),
        )

        conn.commit()
        conn.close()

        self.logger.info(f"Task enqueued: {task_id} (priority={priority})")

        return task_id

    async def get_next_task(self) -> QueuedTask | None:
        """Get next task for execution (highest priority, oldest first).

        Returns:
            Next task or None if queue is empty
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM tasks
            WHERE status = ?
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
            """,
            (TaskStatus.QUEUED.value,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_task(row)

    async def get_task(self, task_id: str) -> QueuedTask | None:
        """Get task by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task or None if not found
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_task(row)

    async def mark_running(self, task_id: str) -> None:
        """Mark task as running.

        Args:
            task_id: Task identifier
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        started_at = datetime.now(UTC).isoformat()

        cursor.execute(
            """
            UPDATE tasks
            SET status = ?, started_at = ?
            WHERE task_id = ?
            """,
            (TaskStatus.RUNNING.value, started_at, task_id),
        )

        conn.commit()
        conn.close()

        self.logger.info(f"Task started: {task_id}")

    async def mark_completed(self, task_id: str, workflow_state: dict[str, Any], result: dict[str, Any]) -> None:
        """Mark task as completed.

        Args:
            task_id: Task identifier
            workflow_state: Final workflow state
            result: Execution result
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        completed_at = datetime.now(UTC).isoformat()

        cursor.execute(
            """
            UPDATE tasks
            SET status = ?, workflow_state = ?, result = ?, completed_at = ?
            WHERE task_id = ?
            """,
            (
                TaskStatus.COMPLETED.value,
                json.dumps(workflow_state),
                json.dumps(result),
                completed_at,
                task_id,
            ),
        )

        conn.commit()
        conn.close()

        self.logger.info(f"Task completed: {task_id}")

    async def mark_failed(self, task_id: str, workflow_state: dict[str, Any] | None, error: str) -> None:
        """Mark task as failed.

        Args:
            task_id: Task identifier
            workflow_state: Final workflow state (if available)
            error: Error message
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        completed_at = datetime.now(UTC).isoformat()

        cursor.execute(
            """
            UPDATE tasks
            SET status = ?, workflow_state = ?, error = ?, completed_at = ?
            WHERE task_id = ?
            """,
            (
                TaskStatus.FAILED.value,
                json.dumps(workflow_state) if workflow_state else None,
                error,
                completed_at,
                task_id,
            ),
        )

        conn.commit()
        conn.close()

        self.logger.error(f"Task failed: {task_id} - {error}")

    async def count_by_status(self, status: TaskStatus) -> int:
        """Count tasks by status.

        Args:
            status: Task status

        Returns:
            Count of tasks with given status
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", (status.value,))

        count = cursor.fetchone()[0]
        conn.close()

        return count

    def _row_to_task(self, row: sqlite3.Row) -> QueuedTask:
        """Convert database row to QueuedTask."""
        return QueuedTask(
            task_id=row["task_id"],
            feature_description=row["feature_description"],
            target_url=row["target_url"],
            staging_url=row["staging_url"],
            priority=row["priority"],
            status=TaskStatus(row["status"]),
            workflow_state=json.loads(row["workflow_state"]) if row["workflow_state"] else None,
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )


__all__ = ["TaskQueue", "TaskStatus", "QueuedTask"]
