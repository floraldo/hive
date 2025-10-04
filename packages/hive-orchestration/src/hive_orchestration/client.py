"""Orchestration Client SDK

Simplified client interface for apps to interact with the orchestration system.
Provides high-level operations for task management, worker coordination, and
execution plan handling.
"""

from __future__ import annotations

from typing import Any

from hive_logging import get_logger

from .operations import (
    check_subtask_dependencies,
    create_planned_subtasks_from_plan,
    create_task,
    get_active_workers,
    get_execution_plan_status,
    get_next_planned_subtask,
    get_queued_tasks,
    get_task,
    get_tasks_by_status,
    mark_plan_execution_started,
    register_worker,
    update_task_status,
    update_worker_heartbeat,
)

logger = get_logger(__name__)


class OrchestrationClient:
    """High-level client for orchestration operations.

    Provides a simplified interface for task management, worker coordination,
    and execution plan handling. This is the recommended way for apps to
    interact with the orchestration system.

    Example:
        >>> client = OrchestrationClient()
        >>> task_id = client.create_task(
        ...     title="Deploy to production",
        ...     task_type="deployment",
        ...     payload={"env": "production"},
        ... )
        >>> tasks = client.get_pending_tasks()

    """

    def __init__(self) -> None:
        """Initialize orchestration client."""
        logger.info("Initialized OrchestrationClient")

    # Task Operations

    def create_task(
        self,
        title: str,
        task_type: str,
        description: str = "",
        payload: dict[str, Any] | None = None,
        priority: int = 1,
        **kwargs: Any,
    ) -> str:
        """Create a new orchestration task.

        Args:
            title: Task title
            task_type: Type of task (e.g., 'deployment', 'analysis')
            description: Task description
            payload: Task payload data
            priority: Task priority (default: 1)
            **kwargs: Additional task metadata

        Returns:
            str: Created task ID

        Example:
            >>> client = OrchestrationClient()
            >>> task_id = client.create_task(
            ...     title="Run analysis",
            ...     task_type="analysis",
            ...     payload={"dataset": "prod"},
            ...     priority=5,
            ... )

        """
        return create_task(
            title=title,
            task_type=task_type,
            description=description,
            payload=payload,
            priority=priority,
            **kwargs,
        )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Get task by ID.

        Args:
            task_id: Task identifier

        Returns:
            Optional[dict]: Task data or None if not found

        """
        return get_task(task_id)

    def update_task_status(
        self,
        task_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update task status.

        Args:
            task_id: Task identifier
            status: New status
            metadata: Optional metadata updates

        Returns:
            bool: True if successful

        """
        return update_task_status(task_id, status, metadata)

    def get_pending_tasks(self, task_type: str | None = None) -> list[dict[str, Any]]:
        """Get all pending (queued) tasks.

        Args:
            task_type: Optional task type filter

        Returns:
            list[dict]: List of pending tasks

        """
        return get_queued_tasks(task_type=task_type)

    def get_tasks_by_status(self, status: str) -> list[dict[str, Any]]:
        """Get all tasks with a specific status.

        Args:
            status: Task status to filter by

        Returns:
            list[dict]: List of matching tasks

        """
        return get_tasks_by_status(status)

    # Worker Operations

    def register_worker(
        self,
        worker_id: str,
        role: str,
        capabilities: list[str] | None = None,
    ) -> bool:
        """Register a worker.

        Args:
            worker_id: Worker identifier
            role: Worker role
            capabilities: List of worker capabilities

        Returns:
            bool: True if successful

        """
        return register_worker(worker_id, role, capabilities)

    def heartbeat(self, worker_id: str, status: str | None = None) -> bool:
        """Send worker heartbeat.

        Args:
            worker_id: Worker identifier
            status: Optional status update

        Returns:
            bool: True if successful

        """
        return update_worker_heartbeat(worker_id, status)

    def get_available_workers(self, role: str | None = None) -> list[dict[str, Any]]:
        """Get all active workers.

        Args:
            role: Optional role filter

        Returns:
            list[dict]: List of active workers

        """
        return get_active_workers(role)

    # Execution Plan Operations

    def start_plan_execution(self, plan_id: str) -> bool:
        """Mark an execution plan as started.

        Args:
            plan_id: Execution plan ID

        Returns:
            bool: True if successful

        """
        return mark_plan_execution_started(plan_id)

    def get_plan_status(self, plan_id: str) -> str | None:
        """Get execution plan status.

        Args:
            plan_id: Execution plan ID

        Returns:
            Optional[str]: Plan status or None if not found

        """
        return get_execution_plan_status(plan_id)

    def get_next_subtask(self, plan_id: str) -> dict[str, Any] | None:
        """Get next ready subtask from a plan.

        Args:
            plan_id: Execution plan ID

        Returns:
            Optional[dict]: Next subtask or None

        """
        return get_next_planned_subtask(plan_id)

    def check_dependencies(self, subtask_id: str) -> bool:
        """Check if subtask dependencies are satisfied.

        Args:
            subtask_id: Subtask identifier

        Returns:
            bool: True if all dependencies met

        """
        return check_subtask_dependencies(subtask_id)

    def create_subtasks_from_plan(self, plan_id: str) -> int:
        """Create executable subtasks from an execution plan.

        Args:
            plan_id: Execution plan ID

        Returns:
            int: Number of subtasks created

        """
        return create_planned_subtasks_from_plan(plan_id)


# Convenience function for getting a client instance
def get_client() -> OrchestrationClient:
    """Get an orchestration client instance.

    Returns:
        OrchestrationClient: Client instance

    Example:
        >>> from hive_orchestration import get_client
        >>> client = get_client()
        >>> task_id = client.create_task("My Task", "analysis")

    """
    return OrchestrationClient()


__all__ = ["OrchestrationClient", "get_client"]
