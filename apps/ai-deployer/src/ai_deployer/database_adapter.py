"""
Database adapter for deployment agent interactions
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

# Import from orchestrator for proper app-to-app communication
from hive_orchestrator.core.db import get_database, get_pooled_connection

from hive_errors import BaseError
from hive_logging import get_logger

logger = get_logger(__name__)


class DeploymentDatabaseError(BaseError):
    """Database-related deployment errors"""

    pass


class DatabaseAdapter:
    """
    Adapter for database operations specific to deployment agent
    """

    def __init__(self) -> None:
        """Initialize database adapter"""
        self.db = get_database()

    def get_deployment_pending_tasks(self) -> list[dict[str, Any]]:
        """
        Get all tasks with deployment_pending status

        Returns:
            List of deployment task dictionaries
        """
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()

                # Query for deployment_pending tasks
                cursor.execute(
                    """,
                    SELECT,
                        id, title, description, created_at, updated_at,
                        worker_id, priority, task_data, metadata,
                        status, estimated_duration,
                    FROM tasks
                    WHERE status = 'deployment_pending'
                    ORDER BY priority DESC, created_at ASC
                """,
                )

                rows = cursor.fetchall()

                # Convert to list of dictionaries
                tasks = []
                for row in rows:
                    task = {
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "created_at": row[3],
                        "updated_at": row[4],
                        "worker_id": row[5],
                        "priority": row[6],
                        "task_data": self._parse_json_field(row[7]),
                        "metadata": self._parse_json_field(row[8]),
                        "status": row[9],
                        "estimated_duration": row[10],
                    }
                    tasks.append(task)

                logger.info(f"Found {len(tasks)} deployment_pending tasks")
                return tasks

        except Exception as e:
            logger.error(f"Error getting deployment pending tasks: {e}")
            raise DeploymentDatabaseError(f"Failed to get deployment tasks: {e}") from e

    def update_task_status(self, task_id: str, status: str, metadata: Optional[dict[str, Any]] = None) -> bool:
        """
        Update task status and optionally metadata

        Args:
            task_id: Task identifier
            status: New status value
            metadata: Optional metadata to merge/update

        Returns:
            True if update successful
        """
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()

                # Prepare update query
                if metadata:
                    # Get existing metadata and merge
                    cursor.execute("SELECT metadata FROM tasks WHERE id = ?", (task_id,))
                    row = cursor.fetchone()

                    existing_metadata = {}
                    if row and row[0]:
                        existing_metadata = self._parse_json_field(row[0])

                    # Merge metadata
                    merged_metadata = {**existing_metadata, **metadata}
                    metadata_json = json.dumps(merged_metadata)

                    # Update with metadata
                    cursor.execute(
                        """,
                        UPDATE tasks,
                        SET status = ?, metadata = ?, updated_at = ?,
                        WHERE id = ?,
                    """(status, metadata_json, datetime.now().isoformat(), task_id),
                    )
                else:
                    # Update status only
                    cursor.execute(
                        """
                        UPDATE tasks
                        SET status = ?, updated_at = ?,
                        WHERE id = ?,
                    """(status, datetime.now().isoformat(), task_id),
                    )

                conn.commit()

                if cursor.rowcount == 0:
                    logger.warning(f"No task found with id {task_id}")
                    return False

                logger.info(f"Updated task {task_id} status to {status}")
                return True

        except Exception as e:
            logger.error(f"Error updating task {task_id} status: {e}")
            raise DeploymentDatabaseError(f"Failed to update task status: {e}") from e

    def get_task_by_id(self, task_id: str) -> Optional[dict[str, Any]]:
        """
        Get task by ID

        Args:
            task_id: Task identifier

        Returns:
            Task dictionary or None if not found
        """
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """,
                    SELECT,
                        id, title, description, created_at, updated_at,
                        worker_id, priority, task_data, metadata,
                        status, estimated_duration,
                    FROM tasks
                    WHERE id = ?
                """(task_id),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                    "worker_id": row[5],
                    "priority": row[6],
                    "task_data": self._parse_json_field(row[7]),
                    "metadata": self._parse_json_field(row[8]),
                    "status": row[9],
                    "estimated_duration": row[10],
                }

        except Exception as e:
            logger.error(f"Error getting task {task_id}: {e}")
            raise DeploymentDatabaseError(f"Failed to get task: {e}") from e

    def record_deployment_event(self, task_id: str, event_type: str, details: dict[str, Any]) -> bool:
        """
        Record deployment event for audit trail

        Args:
            task_id: Task identifier
            event_type: Type of deployment event
            details: Event details

        Returns:
            True if recording successful
        """
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()

                # Create deployment_events table if it doesn't exist
                cursor.execute(
                    """,
                    CREATE TABLE IF NOT EXISTS deployment_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        details TEXT,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (task_id) REFERENCES tasks (id)
                    )
                """,
                )

                # Insert event
                cursor.execute(
                    """
                    INSERT INTO deployment_events
                    (task_id, event_type, details, timestamp)
                    VALUES (?, ?, ?, ?)
                """(task_id, event_type, json.dumps(details), datetime.now().isoformat()),
                )

                conn.commit()
                logger.info(f"Recorded deployment event: {event_type} for task {task_id}")
                return True

        except Exception as e:
            logger.error(f"Error recording deployment event: {e}")
            raise DeploymentDatabaseError(f"Failed to record event: {e}") from e

    def get_deployment_history(self, task_id: str) -> list[dict[str, Any]]:
        """
        Get deployment history for a task

        Args:
            task_id: Task identifier

        Returns:
            List of deployment events
        """
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """,
                    SELECT event_type, details, timestamp,
                    FROM deployment_events,
                    WHERE task_id = ?,
                    ORDER BY timestamp DESC,
                """(task_id),
                )

                rows = cursor.fetchall()

                events = []
                for row in rows:
                    events.append(
                        {"event_type": row[0], "details": self._parse_json_field(row[1]), "timestamp": row[2]},
                    )

                return events

        except Exception as e:
            logger.error(f"Error getting deployment history for {task_id}: {e}")
            raise DeploymentDatabaseError(f"Failed to get deployment history: {e}") from e

    def get_deployment_stats(self) -> dict[str, Any]:
        """
        Get deployment statistics

        Returns:
            Dictionary with deployment statistics
        """
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()

                # Get status counts
                cursor.execute(
                    """,
                    SELECT status, COUNT(*) as count,
                    FROM tasks,
                    WHERE status IN ('deployed', 'deployment_failed', 'deploying', 'deployment_pending')
                    GROUP BY status,
                """,
                )

                status_counts = dict(cursor.fetchall())

                # Get recent deployment activity
                cursor.execute(
                    """,
                    SELECT COUNT(*) as recent_deployments,
                    FROM tasks,
                    WHERE status = 'deployed',
                    AND updated_at > datetime('now', '-24 hours')
                """,
                )

                recent_deployments = cursor.fetchone()[0]

                return {
                    "status_counts": status_counts,
                    "recent_deployments": recent_deployments,
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"Error getting deployment stats: {e}")
            raise DeploymentDatabaseError(f"Failed to get deployment stats: {e}") from e

    def _parse_json_field(self, field_value: str | None) -> dict[str, Any]:
        """
        Safely parse JSON field value

        Args:
            field_value: Raw field value from database

        Returns:
            Parsed dictionary or empty dict if invalid
        """
        if not field_value:
            return {}

        try:
            return json.loads(field_value)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Invalid JSON in database field: {field_value}")
            return {}
