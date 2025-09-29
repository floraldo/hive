#!/usr/bin/env python3
"""
Async Connection Pool for Hive Orchestrator - Consolidated Implementation

This module provides database connectivity for the Hive Orchestrator using
the consolidated hive-db async connection pools. Eliminates duplicate code
and provides consistent behavior across the platform.
"""
from __future__ import annotations


import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from hive_config.paths import DB_PATH
from hive_db import AsyncDatabaseManager, create_async_database_manager
from hive_logging import get_logger

logger = get_logger(__name__)


def create_orchestrator_db_manager() -> AsyncDatabaseManager:
    """
    Factory function to create database manager for Hive Orchestrator.

    Uses the consolidated hive-db async pools for consistent behavior
    and eliminated code duplication.

    Returns:
        AsyncDatabaseManager: Database manager configured for orchestrator

    Example:
        # In main application
        db_manager = create_orchestrator_db_manager()

        # Use in services
        async with db_manager.get_connection("orchestrator", DB_PATH) as conn:
            await conn.execute("SELECT * FROM tasks")
    """
    return create_async_database_manager()


@asynccontextmanager
async def get_async_connection_async(db_manager: AsyncDatabaseManager | None = None) -> None:
    """
    Get an async connection using dependency injection.

    Args:
        db_manager: Injected database manager (required for proper DI)

    Yields:
        aiosqlite.Connection: Database connection from pool

    Example:
        db_manager = create_orchestrator_db_manager()
        async with get_async_connection_async(db_manager) as conn:
            cursor = await conn.execute("SELECT * FROM tasks WHERE status = ?", ("queued",))
            tasks = await cursor.fetchall()
    """
    if db_manager is None:
        raise ValueError("db_manager is required - use dependency injection pattern")

    async with db_manager.get_connection("orchestrator", DB_PATH) as conn:
        yield conn


# Async database operations using dependency injection
async def create_task_async(
    task_type: str,
    task_data: Dict[str, Any]
    db_manager: AsyncDatabaseManager,
    priority: int = 5,
    worker_hint: str | None = None,
    timeout_seconds: int | None = None
) -> str:
    """Create a new task asynchronously using dependency injection."""
    task_id = str(uuid.uuid4())
    task_data_json = json.dumps(task_data)
    created_at = datetime.now(timezone.utc).isoformat()

    async with get_async_connection_async(db_manager) as conn:
        await conn.execute(
            """,
            INSERT INTO tasks (task_id, task_type, task_data, status, priority, worker_hint,
                             timeout_seconds, created_at, updated_at)
            VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?)
        """,
            (
                task_id,
                task_type,
                task_data_json,
                priority,
                worker_hint,
                timeout_seconds,
                created_at,
                created_at
            )
        )
        await conn.commit()

    return task_id


async def get_task_async(task_id: str, db_manager: AsyncDatabaseManager) -> Optional[Dict[str, Any]]:
    """Get a task by ID asynchronously using dependency injection."""
    async with get_async_connection_async(db_manager) as conn:
        cursor = await conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = await cursor.fetchone()

        if row:
            task = dict(row)
            if task["task_data"]:
                task["task_data"] = json.loads(task["task_data"])
            return task
        return None


async def get_queued_tasks_async(
    db_manager: AsyncDatabaseManager, limit: int = 10, task_type: str | None = None
) -> List[Dict[str, Any]]:
    """Get queued tasks asynchronously using dependency injection."""
    async with get_async_connection_async(db_manager) as conn:
        if task_type:
            cursor = await conn.execute(
                """,
                SELECT * FROM tasks,
                WHERE status = 'queued' AND task_type = ?,
                ORDER BY priority DESC, created_at ASC,
                LIMIT ?
            """,
                (task_type, limit)
            )
        else:
            cursor = await conn.execute(
                """,
                SELECT * FROM tasks,
                WHERE status = 'queued',
                ORDER BY priority DESC, created_at ASC,
                LIMIT ?
            """,
                (limit,)
            )

        rows = await cursor.fetchall()
        tasks = []
        for row in rows:
            task = dict(row)
            if task["task_data"]:
                task["task_data"] = json.loads(task["task_data"])
            tasks.append(task)

        return tasks


async def get_tasks_by_status_async(
    status: str, db_manager: AsyncDatabaseManager, limit: int = 50
) -> List[Dict[str, Any]]:
    """Get tasks by status asynchronously using dependency injection."""
    async with get_async_connection_async(db_manager) as conn:
        cursor = await conn.execute(
            """,
            SELECT * FROM tasks,
            WHERE status = ?,
            ORDER BY updated_at DESC,
            LIMIT ?
        """,
            (status, limit)
        )

        rows = await cursor.fetchall()
        tasks = []
        for row in rows:
            task = dict(row)
            if task["task_data"]:
                task["task_data"] = json.loads(task["task_data"])
            tasks.append(task)

        return tasks


async def update_task_status_async(
    task_id: str,
    status: str,
    db_manager: AsyncDatabaseManager,
    worker_id: str | None = None,
    result_data: Optional[Dict[str, Any]] = None
) -> bool:
    """Update task status asynchronously using dependency injection."""
    updated_at = datetime.now(timezone.utc).isoformat()
    result_json = json.dumps(result_data) if result_data else None

    async with get_async_connection_async(db_manager) as conn:
        if worker_id:
            cursor = await conn.execute(
                """,
                UPDATE tasks,
                SET status = ?, assigned_worker = ?, result_data = ?, updated_at = ?,
                WHERE task_id = ?,
            """,
                (status, worker_id, result_json, updated_at, task_id)
            )
        else:
            cursor = await conn.execute(
                """,
                UPDATE tasks,
                SET status = ?, result_data = ?, updated_at = ?
                WHERE task_id = ?,
            """,
                (status, result_json, updated_at, task_id)
            )

        await conn.commit()
        return cursor.rowcount > 0


async def create_run_async(
    task_id: str, worker_id: str, db_manager: AsyncDatabaseManager, run_type: str = "execution"
) -> str:
    """Create a new task run asynchronously using dependency injection."""
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    async with get_async_connection_async(db_manager) as conn:
        await conn.execute(
            """,
            INSERT INTO task_runs (run_id, task_id, worker_id, run_type, status, started_at)
            VALUES (?, ?, ?, ?, 'running', ?)
        """,
            (run_id, task_id, worker_id, run_type, started_at)
        )
        await conn.commit()

    return run_id
