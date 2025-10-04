"""Worker Operations

Core worker management operations for the Hive orchestration system.
These functions provide the public API for worker registration, heartbeat,
and coordination.
"""

from __future__ import annotations

from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


def register_worker(
    worker_id: str,
    role: str,
    capabilities: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Register a new worker in the orchestration system.

    Args:
        worker_id: Unique worker identifier
        role: Worker role (e.g., 'executor', 'backend', 'frontend')
        capabilities: List of worker capabilities (e.g., ['python', 'bash'])
        metadata: Additional worker metadata

    Returns:
        bool: True if registration succeeded, False otherwise

    Example:
        >>> success = register_worker(
        ...     worker_id="worker-123",
        ...     role="executor",
        ...     capabilities=["python", "bash", "docker"],
        ... )

    """
    import json

    from ..database import transaction

    with transaction() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO workers (id, role, capabilities, metadata, last_heartbeat)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                worker_id,
                role,
                json.dumps(capabilities) if capabilities else None,
                json.dumps(metadata) if metadata else None,
            ),
        )

    logger.info(f"Worker registered: {worker_id} ({role})")
    return True


def update_worker_heartbeat(
    worker_id: str,
    status: str | None = None,
) -> bool:
    """Update worker heartbeat timestamp and optional status.

    This should be called periodically by workers to indicate they are alive.

    Args:
        worker_id: Worker identifier
        status: Optional status update (e.g., 'active', 'idle', 'offline')

    Returns:
        bool: True if update succeeded, False otherwise

    Example:
        >>> success = update_worker_heartbeat("worker-123", status="active")

    """
    from ..database import transaction

    with transaction() as conn:
        if status:
            cursor = conn.execute(
                """
                UPDATE workers
                SET last_heartbeat = CURRENT_TIMESTAMP, status = ?
                WHERE id = ?
                """,
                (status, worker_id),
            )
        else:
            cursor = conn.execute(
                """
                UPDATE workers
                SET last_heartbeat = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (worker_id,),
            )

        return cursor.rowcount > 0


def get_active_workers(role: str | None = None) -> list[dict[str, Any]]:
    """Get all active workers, optionally filtered by role.

    Workers are considered active if they have sent a heartbeat within
    the configured timeout period.

    Args:
        role: Optional role filter (e.g., 'executor', 'backend')

    Returns:
        list[dict]: List of active workers

    Example:
        >>> workers = get_active_workers(role="executor")
        >>> for worker in workers:
        ...     print(f"Worker {worker['id']}: {worker['capabilities']}")

    """
    import json

    from ..database import get_connection

    with get_connection() as conn:
        if role:
            cursor = conn.execute(
                """
                SELECT * FROM workers
                WHERE role = ? AND status = 'active'
                ORDER BY last_heartbeat DESC
                """,
                (role,),
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM workers
                WHERE status = 'active'
                ORDER BY last_heartbeat DESC
                """,
            )

        workers = []
        for row in cursor.fetchall():
            worker = dict(row)
            worker["capabilities"] = json.loads(worker["capabilities"]) if worker["capabilities"] else []
            worker["metadata"] = json.loads(worker["metadata"]) if worker["metadata"] else {}
            workers.append(worker)

        return workers


def get_worker(worker_id: str) -> dict[str, Any] | None:
    """Get worker information by ID.

    Args:
        worker_id: Worker identifier

    Returns:
        Optional[dict]: Worker data or None if not found

    Example:
        >>> worker = get_worker("worker-123")
        >>> if worker:
        ...     print(f"Worker status: {worker['status']}")

    """
    import json

    from ..database import get_connection

    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
        row = cursor.fetchone()

        if row:
            worker = dict(row)
            worker["capabilities"] = json.loads(worker["capabilities"]) if worker["capabilities"] else []
            worker["metadata"] = json.loads(worker["metadata"]) if worker["metadata"] else {}
            return worker

        return None


def unregister_worker(worker_id: str) -> bool:
    """Unregister a worker from the orchestration system.

    Args:
        worker_id: Worker identifier

    Returns:
        bool: True if unregistration succeeded, False otherwise

    Example:
        >>> success = unregister_worker("worker-123")

    """
    from ..database import transaction

    with transaction() as conn:
        cursor = conn.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
        success = cursor.rowcount > 0

    if success:
        logger.info(f"Worker unregistered: {worker_id}")
    else:
        logger.warning(f"Worker {worker_id} not found for unregistration")

    return success


__all__ = [
    "get_active_workers",
    "get_worker",
    "register_worker",
    "unregister_worker",
    "update_worker_heartbeat",
]
