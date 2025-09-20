"""
Hive Core Database - Internal state management for Hive orchestration.

This module provides the core database functionality for Hive's internal operations:
- Task definitions and lifecycle management
- Run tracking (execution attempts) with proper separation from task definitions
- Worker registration and heartbeat monitoring
- Result storage and retrieval

Database Location: hive/db/hive-internal.db
"""

import sqlite3
import logging
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager
from enum import Enum

logger = logging.getLogger(__name__)

# Database file location (cleaner than root directory)
DB_PATH = Path("hive/db/hive-internal.db")

# Global connection for reuse
_connection = None


class TaskStatus(Enum):
    """Task lifecycle states"""
    QUEUED = "queued"
    ASSIGNED = "assigned"
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


def get_connection() -> sqlite3.Connection:
    """Get or create database connection."""
    global _connection

    if _connection is None:
        # Ensure database directory exists
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        _connection = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _connection.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrency
        _connection.execute('PRAGMA journal_mode=WAL')
        _connection.execute('PRAGMA foreign_keys=ON')

        logger.info(f"Hive internal database connected: {DB_PATH}")

    return _connection


def close_connection():
    """Close database connection."""
    global _connection
    if _connection:
        _connection.close()
        _connection = None
        logger.info("Hive internal database connection closed")


@contextmanager
def transaction():
    """Database transaction context manager."""
    conn = get_connection()
    try:
        conn.execute('BEGIN')
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
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                task_type TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'queued',
                payload TEXT,  -- JSON data for the task
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assigned_worker TEXT,
                due_date TIMESTAMP,
                max_retries INTEGER DEFAULT 3,
                tags TEXT  -- JSON array of tags
            )
        ''')

        # Runs table - Execution attempts (attempts to execute a task)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                run_number INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                phase TEXT,  -- current execution phase
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                result_data TEXT,  -- JSON result data
                error_message TEXT,
                output_log TEXT,  -- execution logs
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
                FOREIGN KEY (worker_id) REFERENCES workers (id),
                UNIQUE(task_id, run_number)
            )
        ''')

        # Workers table - Worker registration and heartbeat
        conn.execute('''
            CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,  -- backend, frontend, infra, etc.
                status TEXT NOT NULL DEFAULT 'active',
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                capabilities TEXT,  -- JSON array of capabilities
                current_task_id TEXT,  -- currently executing task
                metadata TEXT,  -- JSON worker metadata
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (current_task_id) REFERENCES tasks (id)
            )
        ''')

        # Indexes for performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks (priority DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_runs_task_id ON runs (task_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_runs_worker_id ON runs (worker_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_workers_status ON workers (status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_workers_role ON workers (role)')

        logger.info("Hive internal database initialized successfully")


# Task Management Functions

def create_task(
    title: str,
    task_type: str,
    description: str = "",
    payload: Optional[Dict[str, Any]] = None,
    priority: int = 1,
    max_retries: int = 3,
    tags: Optional[List[str]] = None
) -> str:
    """
    Create a new task.

    Args:
        title: Human-readable task title
        task_type: Type of task (determines which worker can handle it)
        description: Detailed task description
        payload: Task-specific data (JSON serializable)
        priority: Task priority (higher numbers = higher priority)
        max_retries: Maximum retry attempts
        tags: List of tags for categorization

    Returns:
        Task ID
    """
    task_id = str(uuid.uuid4())

    with transaction() as conn:
        conn.execute('''
            INSERT INTO tasks (id, title, description, task_type, priority, payload, max_retries, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_id,
            title,
            description,
            task_type,
            priority,
            json.dumps(payload) if payload else None,
            max_retries,
            json.dumps(tags) if tags else None
        ))

    logger.info(f"Task created: {task_id} - {title}")
    return task_id


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task by ID."""
    conn = get_connection()
    cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    row = cursor.fetchone()

    if row:
        task = dict(row)
        task['payload'] = json.loads(task['payload']) if task['payload'] else None
        task['tags'] = json.loads(task['tags']) if task['tags'] else []
        return task

    return None


def get_queued_tasks(limit: int = 10, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get queued tasks ordered by priority.

    Args:
        limit: Maximum number of tasks to return
        task_type: Filter by task type (for worker specialization)

    Returns:
        List of task dictionaries
    """
    conn = get_connection()

    if task_type:
        cursor = conn.execute('''
            SELECT * FROM tasks
            WHERE status = 'queued' AND task_type = ?
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        ''', (task_type, limit))
    else:
        cursor = conn.execute('''
            SELECT * FROM tasks
            WHERE status = 'queued'
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        ''', (limit,))

    tasks = []
    for row in cursor.fetchall():
        task = dict(row)
        task['payload'] = json.loads(task['payload']) if task['payload'] else None
        task['tags'] = json.loads(task['tags']) if task['tags'] else []
        tasks.append(task)

    return tasks


def update_task_status(task_id: str, status: str, assigned_worker: Optional[str] = None) -> bool:
    """Update task status and optional worker assignment."""
    with transaction() as conn:
        if assigned_worker:
            cursor = conn.execute('''
                UPDATE tasks
                SET status = ?, assigned_worker = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, assigned_worker, task_id))
        else:
            cursor = conn.execute('''
                UPDATE tasks
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, task_id))

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
        cursor = conn.execute('SELECT COALESCE(MAX(run_number), 0) + 1 FROM runs WHERE task_id = ?', (task_id,))
        run_number = cursor.fetchone()[0]

        conn.execute('''
            INSERT INTO runs (id, task_id, worker_id, run_number, phase, status)
            VALUES (?, ?, ?, ?, ?, 'running')
        ''', (run_id, task_id, worker_id, run_number, phase))

    logger.info(f"Run created: {run_id} for task {task_id} by worker {worker_id}")
    return run_id


def update_run_status(
    run_id: str,
    status: str,
    phase: Optional[str] = None,
    result_data: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    output_log: Optional[str] = None
) -> bool:
    """Update run status and execution details."""
    with transaction() as conn:
        fields = ['status = ?']
        values = [status]

        if status in ['success', 'failure', 'timeout', 'cancelled']:
            fields.append('completed_at = CURRENT_TIMESTAMP')

        if phase:
            fields.append('phase = ?')
            values.append(phase)

        if result_data:
            fields.append('result_data = ?')
            values.append(json.dumps(result_data))

        if error_message:
            fields.append('error_message = ?')
            values.append(error_message)

        if output_log:
            fields.append('output_log = ?')
            values.append(output_log)

        values.append(run_id)

        cursor = conn.execute(f'''
            UPDATE runs
            SET {', '.join(fields)}
            WHERE id = ?
        ''', values)

        success = cursor.rowcount > 0
        if success:
            logger.info(f"Run {run_id} status updated to {status}")

        return success


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Get run by ID."""
    conn = get_connection()
    cursor = conn.execute('SELECT * FROM runs WHERE id = ?', (run_id,))
    row = cursor.fetchone()

    if row:
        run = dict(row)
        run['result_data'] = json.loads(run['result_data']) if run['result_data'] else None
        return run

    return None


def get_task_runs(task_id: str) -> List[Dict[str, Any]]:
    """Get all runs for a task, ordered by run number."""
    conn = get_connection()
    cursor = conn.execute('''
        SELECT * FROM runs
        WHERE task_id = ?
        ORDER BY run_number ASC
    ''', (task_id,))

    runs = []
    for row in cursor.fetchall():
        run = dict(row)
        run['result_data'] = json.loads(run['result_data']) if run['result_data'] else None
        runs.append(run)

    return runs


# Worker Management Functions

def register_worker(
    worker_id: str,
    role: str,
    capabilities: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Register a new worker or update existing worker registration."""
    with transaction() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO workers (id, role, capabilities, metadata, last_heartbeat)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            worker_id,
            role,
            json.dumps(capabilities) if capabilities else None,
            json.dumps(metadata) if metadata else None
        ))

    logger.info(f"Worker registered: {worker_id} ({role})")
    return True


def update_worker_heartbeat(worker_id: str, status: Optional[str] = None) -> bool:
    """Update worker heartbeat and optional status."""
    with transaction() as conn:
        if status:
            cursor = conn.execute('''
                UPDATE workers
                SET last_heartbeat = CURRENT_TIMESTAMP, status = ?
                WHERE id = ?
            ''', (status, worker_id))
        else:
            cursor = conn.execute('''
                UPDATE workers
                SET last_heartbeat = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (worker_id,))

        return cursor.rowcount > 0


def get_active_workers(role: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get active workers, optionally filtered by role."""
    conn = get_connection()

    if role:
        cursor = conn.execute('''
            SELECT * FROM workers
            WHERE role = ? AND status = 'active'
            ORDER BY last_heartbeat DESC
        ''', (role,))
    else:
        cursor = conn.execute('''
            SELECT * FROM workers
            WHERE status = 'active'
            ORDER BY last_heartbeat DESC
        ''')

    workers = []
    for row in cursor.fetchall():
        worker = dict(row)
        worker['capabilities'] = json.loads(worker['capabilities']) if worker['capabilities'] else []
        worker['metadata'] = json.loads(worker['metadata']) if worker['metadata'] else {}
        workers.append(worker)

    return workers


def log_run_result(run_id: str, status: str, result_data: Dict[str, Any], error_message: Optional[str] = None) -> bool:
    """
    Log the final result of a worker execution to the database.

    This is a convenience wrapper around update_run_status for Worker result reporting.

    Args:
        run_id: ID of the run to update
        status: Final status ('success', 'failure', 'timeout', 'cancelled')
        result_data: Dictionary containing execution results
        error_message: Optional error message if status is failure

    Returns:
        True if the result was logged successfully, False otherwise
    """
    try:
        success = update_run_status(
            run_id=run_id,
            status=status,
            result_data=result_data,
            error_message=error_message
        )

        if success:
            logger.info(f"Logged result for run {run_id}: status={status}")
        else:
            logger.error(f"Failed to log result for run {run_id}")

        return success

    except Exception as e:
        logger.error(f"Error logging result for run {run_id}: {e}")
        return False