"""
Async database operations for Hive Orchestrator

High-performance async database operations with connection pooling,
batching, and caching support.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import aiosqlite
from hive_db.async_pool import AsyncDatabaseManager, create_async_database_manager_async
from hive_config.paths import DB_PATH
from hive_logging import get_logger

logger = get_logger(__name__)


class AsyncDatabaseOperations:
    """
    High-performance async database operations for Hive Orchestrator

    Features:
    - Connection pooling with backpressure
    - Batch operations for efficiency
    - Query result caching
    - Prepared statements
    - Circuit breaker pattern
    """

    def __init__(self, db_manager: Optional[AsyncDatabaseManager] = None):
        """Initialize async database operations"""
        self.db_manager = db_manager
        self.db_path = DB_PATH
        self._prepared_statements: Dict[str, str] = {}
        self._circuit_breaker_open = False
        self._failure_count = 0
        self._failure_threshold = 5
        self._initialize_prepared_statements()

    def _initialize_prepared_statements(self):
        """Initialize commonly used prepared statements"""
        self._prepared_statements = {
            "get_task": "SELECT * FROM tasks WHERE task_id = ?",
            "get_queued_tasks": """
                SELECT * FROM tasks
                WHERE status = 'queued'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """,
            "update_task_status": """
                UPDATE tasks
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            """,
            "create_task": """
                INSERT INTO tasks (task_id, type, description, status, priority, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            "get_tasks_by_status": """
                SELECT * FROM tasks
                WHERE status = ?
                ORDER BY created_at DESC
            """,
            "batch_update_status": """
                UPDATE tasks
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE task_id IN ({})
            """,
        }

    async def initialize(self):
        """Initialize the database manager if not provided"""
        if not self.db_manager:
            self.db_manager = await create_async_database_manager_async()

    async def _check_circuit_breaker(self):
        """Check if circuit breaker is open"""
        if self._circuit_breaker_open:
            raise Exception("Circuit breaker is open - too many database failures")

    async def _handle_failure(self):
        """Handle database operation failure"""
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._circuit_breaker_open = True
            logger.error("Circuit breaker opened due to repeated failures")
            # Reset after 30 seconds
            asyncio.create_task(self._reset_circuit_breaker())

    async def _reset_circuit_breaker(self):
        """Reset circuit breaker after cooldown"""
        await asyncio.sleep(30)
        self._circuit_breaker_open = False
        self._failure_count = 0
        logger.info("Circuit breaker reset")

    async def _handle_success(self):
        """Handle successful operation"""
        self._failure_count = max(0, self._failure_count - 1)

    # Core Database Operations

    async def create_task_async(
        self,
        task_type: str,
        description: str,
        priority: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new task asynchronously

        Returns:
            Task ID of created task
        """
        await self._check_circuit_breaker()

        try:
            task_id = str(uuid4())
            metadata_json = json.dumps(metadata) if metadata else "{}"

            async with self.db_manager.get_connection_async("hive", self.db_path) as conn:
                await conn.execute(
                    self._prepared_statements["create_task"],
                    (
                        task_id,
                        task_type,
                        description,
                        "queued",
                        priority,
                        metadata_json,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                await conn.commit()

            await self._handle_success()
            logger.debug(f"Created task {task_id} asynchronously")
            return task_id

        except Exception as e:
            await self._handle_failure()
            logger.error(f"Failed to create task: {e}")
            raise

    async def get_task_async(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID asynchronously"""
        await self._check_circuit_breaker()

        try:
            async with self.db_manager.get_connection_async("hive", self.db_path) as conn:
                async with conn.execute(
                    self._prepared_statements["get_task"], (task_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        task = dict(row)
                        if "metadata" in task and task["metadata"]:
                            task["metadata"] = json.loads(task["metadata"])
                        await self._handle_success()
                        return task

            await self._handle_success()
            return None

        except Exception as e:
            await self._handle_failure()
            logger.error(f"Failed to get task {task_id}: {e}")
            raise

    async def get_queued_tasks_async(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get queued tasks asynchronously"""
        await self._check_circuit_breaker()

        try:
            async with self.db_manager.get_connection_async("hive", self.db_path) as conn:
                async with conn.execute(
                    self._prepared_statements["get_queued_tasks"], (limit,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    tasks = []
                    for row in rows:
                        task = dict(row)
                        if "metadata" in task and task["metadata"]:
                            task["metadata"] = json.loads(task["metadata"])
                        tasks.append(task)

            await self._handle_success()
            return tasks

        except Exception as e:
            await self._handle_failure()
            logger.error(f"Failed to get queued tasks: {e}")
            raise

    async def update_task_status_async(
        self, task_id: str, status: str
    ) -> bool:
        """Update task status asynchronously"""
        await self._check_circuit_breaker()

        try:
            async with self.db_manager.get_connection_async("hive", self.db_path) as conn:
                await conn.execute(
                    self._prepared_statements["update_task_status"],
                    (status, task_id),
                )
                await conn.commit()

            await self._handle_success()
            logger.debug(f"Updated task {task_id} status to {status}")
            return True

        except Exception as e:
            await self._handle_failure()
            logger.error(f"Failed to update task {task_id} status: {e}")
            raise

    async def get_tasks_by_status_async(self, status: str) -> List[Dict[str, Any]]:
        """Get all tasks with a specific status"""
        await self._check_circuit_breaker()

        try:
            async with self.db_manager.get_connection_async("hive", self.db_path) as conn:
                async with conn.execute(
                    self._prepared_statements["get_tasks_by_status"], (status,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    tasks = []
                    for row in rows:
                        task = dict(row)
                        if "metadata" in task and task["metadata"]:
                            task["metadata"] = json.loads(task["metadata"])
                        tasks.append(task)

            await self._handle_success()
            return tasks

        except Exception as e:
            await self._handle_failure()
            logger.error(f"Failed to get tasks by status {status}: {e}")
            raise

    # Batch Operations for Performance

    async def batch_create_tasks_async(
        self, tasks: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Create multiple tasks in a single batch operation

        Args:
            tasks: List of task dictionaries with type, description, priority, metadata

        Returns:
            List of created task IDs
        """
        await self._check_circuit_breaker()

        try:
            task_ids = []
            batch_data = []

            for task in tasks:
                task_id = str(uuid4())
                task_ids.append(task_id)
                metadata_json = json.dumps(task.get("metadata", {}))
                batch_data.append((
                    task_id,
                    task["type"],
                    task["description"],
                    "queued",
                    task.get("priority", 5),
                    metadata_json,
                    datetime.now(timezone.utc).isoformat(),
                ))

            async with self.db_manager.get_connection_async("hive", self.db_path) as conn:
                await conn.executemany(
                    self._prepared_statements["create_task"],
                    batch_data,
                )
                await conn.commit()

            await self._handle_success()
            logger.info(f"Batch created {len(task_ids)} tasks")
            return task_ids

        except Exception as e:
            await self._handle_failure()
            logger.error(f"Failed to batch create tasks: {e}")
            raise

    async def batch_update_status_async(
        self, task_ids: List[str], status: str
    ) -> bool:
        """
        Update status for multiple tasks in a single operation

        Args:
            task_ids: List of task IDs to update
            status: New status for all tasks

        Returns:
            True if successful
        """
        await self._check_circuit_breaker()

        if not task_ids:
            return True

        try:
            placeholders = ",".join("?" * len(task_ids))
            query = self._prepared_statements["batch_update_status"].format(placeholders)

            async with self.db_manager.get_connection_async("hive", self.db_path) as conn:
                await conn.execute(query, [status] + task_ids)
                await conn.commit()

            await self._handle_success()
            logger.info(f"Batch updated {len(task_ids)} tasks to status {status}")
            return True

        except Exception as e:
            await self._handle_failure()
            logger.error(f"Failed to batch update task statuses: {e}")
            raise

    # Concurrent Operations

    async def get_tasks_concurrent_async(
        self, task_ids: List[str]
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Get multiple tasks concurrently

        Args:
            task_ids: List of task IDs to fetch

        Returns:
            List of task dictionaries (None for not found)
        """
        tasks = await asyncio.gather(
            *[self.get_task_async(task_id) for task_id in task_ids],
            return_exceptions=True,
        )

        # Convert exceptions to None
        return [
            task if not isinstance(task, Exception) else None
            for task in tasks
        ]

    # Performance Statistics

    async def get_performance_stats_async(self) -> Dict[str, Any]:
        """Get database performance statistics"""
        stats = await self.db_manager.get_all_stats_async()
        stats["circuit_breaker"] = {
            "open": self._circuit_breaker_open,
            "failure_count": self._failure_count,
            "threshold": self._failure_threshold,
        }
        return stats

    # Cleanup

    async def close(self):
        """Close all database connections"""
        if self.db_manager:
            await self.db_manager.close_all_pools_async()
            logger.info("Closed async database operations")


# Global instance (lazy initialization)
_async_db_ops: Optional[AsyncDatabaseOperations] = None


async def get_async_db_operations() -> AsyncDatabaseOperations:
    """Get or create the global async database operations instance"""
    global _async_db_ops
    if _async_db_ops is None:
        _async_db_ops = AsyncDatabaseOperations()
        await _async_db_ops.initialize()
    return _async_db_ops