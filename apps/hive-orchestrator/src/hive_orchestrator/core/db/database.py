"""
Hive Core Database - Internal state management for Hive orchestration.

This module provides the core database functionality for Hive's internal operations:
- Task definitions and lifecycle management
- Run tracking (execution attempts) with proper separation from task definitions
- Worker registration and heartbeat monitoring
- Result storage and retrieval

Extends the generic hive_db package with Hive Orchestrator-specific functionality.

Database Location: hive/db/hive-internal.db
"""
from __future__ import annotations


import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, ListTuple

from hive_db import (
    create_table_if_not_exists,
    get_sqlite_connection,
    sqlite_transaction
)
from hive_logging import get_logger

logger = get_logger(__name__)

# Use the authoritative path singleton
from hive_config.paths import DB_PATH, ensure_directory

# Import connection pool for proper connection management
from .connection_pool import close_pool, get_pooled_connection

# Import async functionality for Phase 4.1
try:
    from .async_compat import (
        async_database_enabled,
        get_sync_async_connection,
        sync_wrapper
    )
    from .async_connection_pool import (
        close_async_pool,
        get_async_connection,
        get_async_pool_stats
    )

    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False
    logger.warning("Async database support not available - install aiosqlite for Phase 4.1 features")


class TaskStatus(Enum):
    """Task lifecycle states"""

    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW_PENDING = "review_pending"  # Task awaiting intelligent review
    APPROVED = "approved"  # Passed AI review
    REJECTED = "rejected"  # Failed AI review
    REWORK_NEEDED = "rework_needed"  # Needs improvements (AI review)
    ESCALATED = "escalated"  # Requires human review
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(Enum):
    """Individual run (execution attempt) states"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class WorkerStatus(Enum):
    """Worker states"""

    ACTIVE = "active"
    IDLE = "idle"
    OFFLINE = "offline"
    ERROR = "error"


@contextmanager
def get_connection() -> None:
    """Get a database connection from the pool.

    This is a context manager that properly handles connection
    checkout and checkin from the connection pool.

    Usage:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)

    Yields:
        sqlite3.Connection: A database connection from the pool
    """
    # Use the connection pool (auto-initializes on first use)
    with get_pooled_connection() as conn:
        yield conn


def close_connection() -> None:
    """Close database connection pool.

    This closes all connections in the pool and shuts down
    the pool maintenance thread.
    """
    close_pool()
    logger.info("Hive internal database connection pool closed")


@contextmanager
def transaction() -> None:
    """Database transaction context manager."""
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database transaction rolled back: {e}")
            raise


def init_db() -> None:
    """Initialize the Hive internal database with required tables."""
    with transaction() as conn:
        # Tasks table - Task definitions (what needs to be done)
        conn.execute(
            """,
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                task_type TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'queued',
                current_phase TEXT NOT NULL DEFAULT 'start',  -- Current state in workflow,
                workflow TEXT,  -- JSON workflow definition (state machine)
                payload TEXT,  -- JSON data for the task,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assigned_worker TEXT,
                due_date TIMESTAMP,
                max_retries INTEGER DEFAULT 3,
                tags TEXT  -- JSON array of tags
            )
        """
        )

        # Runs table - Execution attempts (attempts to execute a task)
        conn.execute(
            """,
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                run_number INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                phase TEXT,  -- current execution phase,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                result_data TEXT,  -- JSON result data,
                error_message TEXT,
                output_log TEXT,  -- execution logs,
                transcript TEXT,  -- full Claude conversation transcript,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
                FOREIGN KEY (worker_id) REFERENCES workers (id)
                UNIQUE(task_id, run_number)
            )
        """
        )

        # Workers table - Worker registration and heartbeat
        conn.execute(
            """,
            CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,  -- backend, frontend, infra, etc.
                status TEXT NOT NULL DEFAULT 'active',
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                capabilities TEXT,  -- JSON array of capabilities,
                current_task_id TEXT,  -- currently executing task,
                metadata TEXT,  -- JSON worker metadata,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (current_task_id) REFERENCES tasks (id)
            )
        """
        )

        # AI Planning tables - for intelligent task planning and workflow generation

        # Planning queue - incoming requests for intelligent planning
        conn.execute(
            """,
            CREATE TABLE IF NOT EXISTS planning_queue (
                id TEXT PRIMARY KEY,
                task_description TEXT NOT NULL,
                priority INTEGER DEFAULT 50,
                requestor TEXT,
                context_data TEXT,  -- JSON context and requirements,
                status TEXT DEFAULT 'pending',
                complexity_estimate TEXT,  -- simple|medium|complex,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assigned_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                assigned_agent TEXT  -- which ai-planner instance is handling this
            )
        """
        )

        # Generated execution plans - AI-generated plans for complex tasks
        conn.execute(
            """,
            CREATE TABLE IF NOT EXISTS execution_plans (
                id TEXT PRIMARY KEY,
                planning_task_id TEXT NOT NULL,
                plan_data TEXT NOT NULL,  -- JSON plan structure with subtasks and dependencies,
                estimated_duration INTEGER,  -- estimated minutes to complete,
                estimated_complexity TEXT DEFAULT 'medium',
                generated_workflow TEXT,  -- Generated Hive workflow JSON,
                subtask_count INTEGER DEFAULT 0,
                dependency_count INTEGER DEFAULT 0,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'draft',  -- draft|approved|executing|completed|failed,
                FOREIGN KEY (planning_task_id) REFERENCES planning_queue (id) ON DELETE CASCADE
            )
        """
        )

        # Plan execution monitoring - track progress of plan execution
        conn.execute(
            """,
            CREATE TABLE IF NOT EXISTS plan_execution (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                current_phase TEXT,
                progress_percent INTEGER DEFAULT 0,
                active_subtasks TEXT,  -- JSON array of currently executing subtasks,
                completed_subtasks TEXT,  -- JSON array of completed subtasks,
                failed_subtasks TEXT,  -- JSON array of failed subtasks,
                blocked_subtasks TEXT,  -- JSON array of blocked subtasks,
                execution_notes TEXT,  -- JSON array of execution notes and adjustments,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                FOREIGN KEY (plan_id) REFERENCES execution_plans (id) ON DELETE CASCADE
            )
        """
        )

        # Indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks (priority DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON runs (task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_worker_id ON runs (worker_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workers_status ON workers (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workers_role ON workers (role)")

        # AI Planning indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_planning_queue_status ON planning_queue (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_planning_queue_priority ON planning_queue (priority DESC)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_execution_plans_planning_task_id ON execution_plans (planning_task_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_plans_status ON execution_plans (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_execution_plan_id ON plan_execution (plan_id)")

        logger.info("Hive internal database initialized successfully")


# Task Management Functions


def create_task(
    title: str,
    task_type: str,
    description: str = "",
    workflow: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    priority: int = 1,
    max_retries: int = 3,
    tags: Optional[List[str]] = None,
    current_phase: str = "start"
) -> str:
    """
    Create a new task with optional workflow definition.

    Args:
        title: Human-readable task title,
        task_type: Type of task (determines which worker can handle it)
        description: Detailed task description,
        workflow: Workflow definition (state machine as JSON)
        payload: Task-specific data (JSON serializable)
        priority: Task priority (higher numbers = higher priority)
        max_retries: Maximum retry attempts,
        tags: List of tags for categorization,
        current_phase: Initial phase of the task (default: "start")

    Returns:
        Task ID,
    """
    task_id = str(uuid.uuid4())

    with transaction() as conn:
        conn.execute(
            """,
            INSERT INTO tasks (id, title, description, task_type, priority, current_phase, workflow, payload, max_retries, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task_id,
                title,
                description,
                task_type,
                priority,
                current_phase,
                json.dumps(workflow) if workflow else None,
                json.dumps(payload) if payload else None,
                max_retries,
                json.dumps(tags) if tags else None
            )
        )

    logger.info(f"Task created: {task_id} - {title}")
    return task_id


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task by ID."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

        if row:
            task = dict(row)
            task["payload"] = json.loads(task["payload"]) if task["payload"] else None
            task["workflow"] = json.loads(task["workflow"]) if task["workflow"] else None
            task["tags"] = json.loads(task["tags"]) if task["tags"] else []
            return task

        return None


def get_queued_tasks(limit: int = 10, task_type: str | None = None) -> List[Dict[str, Any]]:
    """
    Get queued tasks ordered by priority.

    Args:
        limit: Maximum number of tasks to return
        task_type: Filter by task type (for worker specialization)

    Returns:
        List of task dictionaries
    """
    with get_connection() as conn:
        if task_type:
            cursor = conn.execute(
                """,
                SELECT * FROM tasks,
                WHERE status = 'queued' AND task_type = ?,
                ORDER BY priority DESC, created_at ASC,
                LIMIT ?
            """,
                (task_type, limit)
            )
        else:
            cursor = conn.execute(
                """,
                SELECT * FROM tasks,
                WHERE status = 'queued',
                ORDER BY priority DESC, created_at ASC,
                LIMIT ?
            """,
                (limit,)
            )

        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            task["payload"] = json.loads(task["payload"]) if task["payload"] else None
            task["workflow"] = json.loads(task["workflow"]) if task["workflow"] else None
            task["tags"] = json.loads(task["tags"]) if task["tags"] else []
            tasks.append(task)

        return tasks


def update_task_status(task_id: str, status: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Update task status and optional metadata fields."""
    with transaction() as conn:
        # Start with base fields
        fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        values = [status]

        # Add metadata fields if provided
        if metadata:
            for key, value in metadata.items():
                if key in [
                    "assignee",
                    "assigned_at",
                    "current_phase",
                    "started_at",
                    "failure_reason",
                    "retry_count",
                    "worktree",
                    "workspace_type"
                ]:
                    fields.append(f"{key} = ?")
                    values.append(value)

        values.append(task_id)

        # Check if we need to add missing columns
        cursor = conn.execute("PRAGMA table_info(tasks)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Add missing columns if needed
        required_columns = {
            "assignee": "TEXT",
            "assigned_at": "TEXT",
            "current_phase": "TEXT DEFAULT 'start'",
            "workflow": "TEXT",  # JSON workflow definition,
            "started_at": "TEXT",
            "failure_reason": "TEXT",
            "retry_count": "INTEGER DEFAULT 0",
            "worktree": "TEXT",
            "workspace_type": "TEXT",
            "depends_on": "TEXT",  # JSON array of dependency task IDs
        }

        for column, column_type in required_columns.items():
            if column not in existing_columns:
                # Validate column name to prevent SQL injection
                if not all(c.isalnum() or c == '_' for c in column):
                    logger.error(f"Invalid column name: {column}")
                    continue
                try:
                    conn.execute(f"ALTER TABLE tasks ADD COLUMN {column} {column_type}")
                    logger.info(f"Added column {column} to tasks table")
                except sqlite3.OperationalError:
                    # Column might already exist from concurrent update
                    pass

        cursor = conn.execute(
            f""",
            UPDATE tasks,
            SET {', '.join(fields)}
            WHERE id = ?,
        """,
            values
        )

        success = cursor.rowcount > 0
        if success:
            logger.info(f"Task {task_id} status updated to {status}")

        return success


# Run Management Functions (Execution Tracking)


def create_run(task_id: str, worker_id: str, phase: str = "init") -> str:
    """
    Create a new run (execution attempt) for a task.

    Args:
        task_id: ID of the task being executed
        worker_id: ID of the worker executing the task
        phase: Current execution phase

    Returns:
        Run ID
    """
    run_id = str(uuid.uuid4())

    with transaction() as conn:
        # Get the next run number for this task
        cursor = conn.execute(
            "SELECT COALESCE(MAX(run_number), 0) + 1 FROM runs WHERE task_id = ?",
            (task_id,)
        )
        run_number = cursor.fetchone()[0]

        conn.execute(
            """,
            INSERT INTO runs (id, task_id, worker_id, run_number, phase, status)
            VALUES (?, ?, ?, ?, ?, 'running')
        """,
            (run_id, task_id, worker_id, run_number, phase)
        )

    logger.info(f"Run created: {run_id} for task {task_id} by worker {worker_id}")
    return run_id


def update_run_status(
    run_id: str,
    status: str,
    phase: str | None = None,
    result_data: Optional[Dict[str, Any]] = None,
    error_message: str | None = None,
    output_log: str | None = None,
    transcript: str | None = None
) -> bool:
    """Update run status and execution details."""
    with transaction() as conn:
        fields = ["status = ?"]
        values = [status]

        if status in ["success", "failure", "timeout", "cancelled"]:
            fields.append("completed_at = CURRENT_TIMESTAMP")

        if phase:
            fields.append("phase = ?")
            values.append(phase)

        if result_data:
            fields.append("result_data = ?")
            values.append(json.dumps(result_data))

        if error_message:
            fields.append("error_message = ?")
            values.append(error_message)

        if output_log:
            fields.append("output_log = ?")
            values.append(output_log)

        if transcript:
            fields.append("transcript = ?")
            values.append(transcript)

        values.append(run_id)

        cursor = conn.execute(
            f""",
            UPDATE runs,
            SET {', '.join(fields)}
            WHERE id = ?,
        """,
            values
        )

        success = cursor.rowcount > 0,
        if success:
            logger.info(f"Run {run_id} status updated to {status}")

        return success


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Get run by ID."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        row = cursor.fetchone()

        if row:
            run = dict(row)
            result_data = json.loads(run["result_data"]) if run["result_data"] else {}

            # Structure the return to match what Queen expects
            # Queen looks for run_data.get("result", {}).get("status", "failed")
            run["result"] = {
                "status": run.get("status", "failed"),
                "data": result_data,
                "error_message": run.get("error_message"),
                "output_log": run.get("output_log"),
            }
            return run

        return None


def get_task_runs(task_id: str) -> List[Dict[str, Any]]:
    """Get all runs for a task, ordered by run number."""
    with get_connection() as conn:
        cursor = conn.execute(
            """,
            SELECT * FROM runs,
            WHERE task_id = ?,
            ORDER BY run_number ASC,
        """,
            (task_id,)
        )

        runs = []
        for row in cursor.fetchall():
            run = dict(row)
            run["result_data"] = json.loads(run["result_data"]) if run["result_data"] else None
            runs.append(run)

        return runs


def get_tasks_by_status(status: str) -> List[Dict[str, Any]]:
    """
    Get all tasks with a specific status.

    Args:
        status: Task status to filter by (e.g., 'in_progress', 'queued', 'completed')

    Returns:
        List of task dictionaries with the specified status
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """,
            SELECT * FROM tasks,
            WHERE status = ?,
            ORDER BY created_at ASC,
        """,
            (status,)
        )

        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            task["payload"] = json.loads(task["payload"]) if task["payload"] else {}
            task["workflow"] = json.loads(task["workflow"]) if task["workflow"] else None
            task["tags"] = json.loads(task["tags"]) if task["tags"] else []
            tasks.append(task)

        return tasks


# Worker Management Functions


def register_worker(
    worker_id: str,
    role: str,
    capabilities: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Register a new worker or update existing worker registration."""
    with transaction() as conn:
        conn.execute(
            """,
            INSERT OR REPLACE INTO workers (id, role, capabilities, metadata, last_heartbeat)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                worker_id,
                role,
                json.dumps(capabilities) if capabilities else None,
                json.dumps(metadata) if metadata else None
            )
        )

    logger.info(f"Worker registered: {worker_id} ({role})")
    return True


def update_worker_heartbeat(worker_id: str, status: str | None = None) -> bool:
    """Update worker heartbeat and optional status."""
    with transaction() as conn:
        if status:
            cursor = conn.execute(
                """,
                UPDATE workers,
                SET last_heartbeat = CURRENT_TIMESTAMP, status = ?,
                WHERE id = ?,
            """,
                (status, worker_id)
            )
        else:
            cursor = conn.execute(
                """,
                UPDATE workers,
                SET last_heartbeat = CURRENT_TIMESTAMP,
                WHERE id = ?,
            """,
                (worker_id,)
            )

        return cursor.rowcount > 0


def get_active_workers(role: str | None = None) -> List[Dict[str, Any]]:
    """Get active workers, optionally filtered by role."""
    with get_connection() as conn:
        if role:
            cursor = conn.execute(
                """,
                SELECT * FROM workers,
                WHERE role = ? AND status = 'active',
                ORDER BY last_heartbeat DESC,
            """,
                (role,)
            )
        else:
            cursor = conn.execute(
                """,
                SELECT * FROM workers,
                WHERE status = 'active',
                ORDER BY last_heartbeat DESC,
            """
            )

        workers = []
        for row in cursor.fetchall():
            worker = dict(row)
            worker["capabilities"] = json.loads(worker["capabilities"]) if worker["capabilities"] else []
            worker["metadata"] = json.loads(worker["metadata"]) if worker["metadata"] else {}
            workers.append(worker)

        return workers


def log_run_result(
    run_id: str,
    status: str,
    result_data: Dict[str, Any]
    error_message: str | None = None,
    transcript: str | None = None
) -> bool:
    """
    Log the final result of a worker execution to the database.

    This is a convenience wrapper around update_run_status for Worker result reporting.

    Args:
        run_id: ID of the run to update,
        status: Final status ('success', 'failure', 'timeout', 'cancelled')
        result_data: Dictionary containing execution results,
        error_message: Optional error message if status is failure,
        transcript: Optional full transcript of Claude execution

    Returns:
        True if the result was logged successfully, False otherwise,
    """
    try:
        success = update_run_status(
            run_id=run_id,
            status=status,
            result_data=result_data,
            error_message=error_message,
            transcript=transcript
        )

        if success:
            logger.info(f"Logged result for run {run_id}: status={status}")
        else:
            logger.error(f"Failed to log result for run {run_id}")

        return success

    except Exception as e:
        logger.error(f"Error logging result for run {run_id}: {e}")
        return False


def get_tasks_by_status(status: str) -> List[Dict[str, Any]]:
    """
    Get all tasks with a specific status.

    Args:
        status: The task status to filter by

    Returns:
        List of task dictionaries
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC",
                (status,)
            )
            rows = cursor.fetchall()

            tasks = []
            for row in rows:
                task_dict = dict(row)
                # Parse JSON fields
                if task_dict.get("tags"):
                    task_dict["tags"] = json.loads(task_dict["tags"])
                if task_dict.get("depends_on"):
                    task_dict["depends_on"] = json.loads(task_dict["depends_on"])
                if task_dict.get("metadata"):
                    task_dict["metadata"] = json.loads(task_dict["metadata"])
                tasks.append(task_dict)

            return tasks

    except Exception as e:
        logger.error(f"Error getting tasks by status {status}: {e}")
        return []


# ================================================================================
# ASYNC DATABASE OPERATIONS - Phase 4.1 Implementation
# ================================================================================

if ASYNC_AVAILABLE:

    async def create_task_async(
        description: str,
        title: str = None,
        assignee: str = None,
        priority: int = None,
        tags: List[str] = None,
        context_data: Dict[str, Any] = None,
        depends_on: List[str] = None,
        workspace: str = "repo",
        task_type: str = "user_request",
        requestor: str = "unknown",
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Async version of create_task for Phase 4.1 performance improvement.

        Args:
            task_description: Human-readable task description
            assignee: Worker/agent assigned to task (optional)
            priority: Task priority (1-10, higher = more important)
            tags: List of tags for categorization
            context_data: Additional context for task execution
            depends_on: List of task IDs this task depends on
            workspace: Workspace type ("repo", "isolated", "temp")
            task_type: Type of task ("user_request", "planned_subtask", etc.)
            requestor: Who requested the task
            metadata: Additional metadata

        Returns:
            Task ID of created task
        """
        task_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        # Set defaults
        priority = priority or 5
        tags = tags or []
        context_data = context_data or {}
        depends_on = depends_on or []
        metadata = metadata or {}

        async with get_async_connection() as conn:
            await conn.execute(
                """,
                INSERT INTO tasks (
                    id, title, description, assignee, priority, status, tags,
                    payload, workspace_type, task_type, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task_id,
                    title or description[:50]
                    description,
                    assignee,
                    priority,
                    TaskStatus.QUEUED.value,
                    json.dumps(tags)
                    json.dumps(
                        {
                            "context_data": context_data,
                            "depends_on": depends_on,
                            "metadata": metadata,
                            "requestor": requestor
                        }
                    )
                    workspace,
                    task_type,
                    created_at,
                    created_at
                )
            )
            await conn.commit()

        logger.info(f"Created async task {task_id}: {description[:100]}...")
        return task_id

    async def get_task_async(task_id: str) -> Optional[Dict[str, Any]]:
        """Async version of get_task."""
        async with get_async_connection() as conn:
            cursor = await conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = await cursor.fetchone()

            if row:
                task_dict = dict(row)
                # Parse JSON fields
                if task_dict.get("tags"):
                    task_dict["tags"] = json.loads(task_dict["tags"])
                if task_dict.get("context_data"):
                    task_dict["context_data"] = json.loads(task_dict["context_data"])
                if task_dict.get("depends_on"):
                    task_dict["depends_on"] = json.loads(task_dict["depends_on"])
                if task_dict.get("metadata"):
                    task_dict["metadata"] = json.loads(task_dict["metadata"])
                return task_dict

            return None

    async def get_queued_tasks_async(limit: int = 10, task_type: str | None = None) -> List[Dict[str, Any]]:
        """
        Async version of get_queued_tasks for high-performance task retrieval.

        Args:
            limit: Maximum number of tasks to return
            task_type: Optional filter by task type

        Returns:
            List of queued task dictionaries
        """
        async with get_async_connection() as conn:
            if task_type:
                cursor = await conn.execute(
                    """,
                    SELECT * FROM tasks,
                    WHERE status = ? AND task_type = ?,
                    ORDER BY priority DESC, created_at ASC,
                    LIMIT ?
                """,
                    (TaskStatus.QUEUED.value, task_type, limit)
                )
            else:
                cursor = await conn.execute(
                    """,
                    SELECT * FROM tasks,
                    WHERE status = ?
                    ORDER BY priority DESC, created_at ASC,
                    LIMIT ?
                """,
                    (TaskStatus.QUEUED.value, limit)
                )

            rows = await cursor.fetchall()
            tasks = []

            for row in rows:
                task_dict = dict(row)
                # Parse JSON fields
                if task_dict.get("tags"):
                    task_dict["tags"] = json.loads(task_dict["tags"])
                if task_dict.get("context_data"):
                    task_dict["context_data"] = json.loads(task_dict["context_data"])
                if task_dict.get("depends_on"):
                    task_dict["depends_on"] = json.loads(task_dict["depends_on"])
                if task_dict.get("metadata"):
                    task_dict["metadata"] = json.loads(task_dict["metadata"])
                tasks.append(task_dict)

            return tasks

    async def update_task_status_async(task_id: str, status: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Async version of update_task_status for non-blocking updates.

        Args:
            task_id: Task identifier
            status: New status
            metadata: Optional metadata to merge with existing

        Returns:
            True if update successful, False otherwise
        """
        try:
            updated_at = datetime.now(timezone.utc).isoformat()

            async with get_async_connection() as conn:
                if metadata:
                    # Get existing metadata and merge
                    cursor = await conn.execute("SELECT metadata FROM tasks WHERE id = ?", (task_id,))
                    row = await cursor.fetchone()

                    if row:
                        existing_metadata = json.loads(row["metadata"] or "{}")
                        existing_metadata.update(metadata)
                        merged_metadata = json.dumps(existing_metadata)
                    else:
                        merged_metadata = json.dumps(metadata)

                    await conn.execute(
                        """,
                        UPDATE tasks,
                        SET status = ?, metadata = ?, updated_at = ?,
                        WHERE id = ?,
                    """,
                        (status, merged_metadata, updated_at, task_id)
                    )
                else:
                    await conn.execute(
                        """,
                        UPDATE tasks,
                        SET status = ?, updated_at = ?
                        WHERE id = ?,
                    """,
                        (status, updated_at, task_id)
                    )

                await conn.commit()

            logger.debug(f"Updated async task {task_id} status to {status}")
            return True

        except Exception as e:
            logger.error(f"Error updating async task {task_id} status: {e}")
            return False

    async def get_tasks_by_status_async(status: str) -> List[Dict[str, Any]]:
        """Async version of get_tasks_by_status."""
        try:
            async with get_async_connection() as conn:
                cursor = await conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                )
                rows = await cursor.fetchall()

                tasks = []
                for row in rows:
                    task_dict = dict(row)
                    # Parse JSON fields
                    if task_dict.get("tags"):
                        task_dict["tags"] = json.loads(task_dict["tags"])
                    if task_dict.get("context_data"):
                        task_dict["context_data"] = json.loads(task_dict["context_data"])
                    if task_dict.get("depends_on"):
                        task_dict["depends_on"] = json.loads(task_dict["depends_on"])
                    if task_dict.get("metadata"):
                        task_dict["metadata"] = json.loads(task_dict["metadata"])
                    tasks.append(task_dict)

                return tasks

        except Exception as e:
            logger.error(f"Error getting async tasks by status {status}: {e}")
            return []

    async def create_run_async(task_id: str, worker_id: str, phase: str = "init") -> str:
        """
        Async version of create_run for non-blocking run creation.

        Args:
            task_id: Associated task ID
            worker_id: Worker performing the run
            phase: Execution phase

        Returns:
            Run ID
        """
        run_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        async with get_async_connection() as conn:
            await conn.execute(
                """,
                INSERT INTO runs (
                    id, task_id, worker_id, phase, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_id,
                    task_id,
                    worker_id,
                    phase,
                    RunStatus.PENDING.value,
                    created_at,
                    created_at
                )
            )
            await conn.commit()

        logger.debug(f"Created async run {run_id} for task {task_id}")
        return run_id

    # Provide sync wrappers for backward compatibility
    def create_task_sync_wrapper(*args, **kwargs) -> str:
        """Sync wrapper for async create_task."""
        return sync_wrapper(create_task_async)(*args, **kwargs)

    def get_task_sync_wrapper(*args, **kwargs) -> Optional[Dict[str, Any]]:
        """Sync wrapper for async get_task."""
        return sync_wrapper(get_task_async)(*args, **kwargs)

    def get_queued_tasks_sync_wrapper(*args, **kwargs) -> List[Dict[str, Any]]:
        """Sync wrapper for async get_queued_tasks."""
        return sync_wrapper(get_queued_tasks_async)(*args, **kwargs)

    def update_task_status_sync_wrapper(*args, **kwargs) -> bool:
        """Sync wrapper for async update_task_status."""
        return sync_wrapper(update_task_status_async)(*args, **kwargs)
