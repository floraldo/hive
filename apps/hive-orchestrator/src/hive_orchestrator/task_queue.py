"""Task Queue Manager - Priority-Based Task Scheduling

Manages QA task queue with:
- Priority-based scheduling (high/normal/low)
- Worker assignment and load balancing
- Task timeout and retry management
- Queue metrics and monitoring
- Integration with worker pool
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from hive_logging import get_logger
from hive_orchestration.events import QATaskEvent, get_async_event_bus
from hive_orchestration.models.task import Task

logger = get_logger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels"""

    HIGH = "high"  # Blocking issues, syntax errors
    NORMAL = "normal"  # Standard violations
    LOW = "low"  # Style improvements, optional checks


class TaskQueueStatus(str, Enum):
    """Task queue status"""

    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class QueuedTask:
    """Task in queue with metadata"""

    task: Task
    priority: TaskPriority = TaskPriority.NORMAL
    queued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    assigned_worker: str | None = None
    assigned_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: TaskQueueStatus = TaskQueueStatus.QUEUED
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        """Time since task was queued"""
        return (datetime.now(UTC) - self.queued_at).total_seconds()

    @property
    def is_timeout(self) -> bool:
        """Check if task has timed out"""
        if self.started_at is None:
            return False
        elapsed = (datetime.now(UTC) - self.started_at).total_seconds()
        return elapsed > self.timeout_seconds

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried"""
        return self.retry_count < self.max_retries


def create_golden_rules_task(
    file_paths: list[str] | list[Path] | None = None,
    severity_level: str = "ERROR",
    description: str | None = None,
) -> Task:
    """Create a Golden Rules validation task.

    Args:
        file_paths: Optional list of file paths to validate (None = all files)
        severity_level: Severity level for validation (CRITICAL, ERROR, WARNING, INFO)
        description: Optional task description override

    Returns:
        Task configured for Golden Rules Worker processing

    """
    import uuid

    # Convert Paths to strings
    str_file_paths = [str(p) for p in file_paths] if file_paths else None

    # Generate description if not provided
    if description is None:
        if str_file_paths:
            file_count = len(str_file_paths)
            description = f"Validate Golden Rules compliance for {file_count} file(s) (severity: {severity_level})"
        else:
            description = f"Validate Golden Rules compliance for all files (severity: {severity_level})"

    return Task(
        id=str(uuid.uuid4()),  # Must be valid UUID
        task_type="qa_golden_rules",
        title="Golden Rules Validation",
        description=description,
        metadata={
            "qa_type": "golden_rules",
            "file_paths": str_file_paths,
            "severity_level": severity_level,
            "worker_type": "golden_rules",
        },
    )


class TaskQueueManager:
    """Priority-based task queue with worker assignment.

    Features:
    - Three priority levels (high/normal/low)
    - Worker load balancing
    - Task timeout and retry management
    - Queue metrics and statistics
    - Event-driven status updates
    """

    def __init__(self, db_path: Path | str | None = None):
        """Initialize task queue manager.

        Args:
            db_path: Path to database for persistence (optional)

        """
        self.db_path = db_path

        # Priority queues
        self._queues: dict[TaskPriority, list[QueuedTask]] = {
            TaskPriority.HIGH: [],
            TaskPriority.NORMAL: [],
            TaskPriority.LOW: [],
        }

        # Task tracking
        self._tasks: dict[str, QueuedTask] = {}  # task_id -> QueuedTask
        self._worker_assignments: dict[str, list[str]] = defaultdict(list)  # worker_id -> [task_ids]

        # Metrics
        self._total_queued = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_timeout = 0

        # Event bus
        self.event_bus = get_async_event_bus()

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info("TaskQueueManager initialized")

    async def enqueue(
        self,
        task: Task,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_seconds: int = 60,
        max_retries: int = 3,
    ) -> str:
        """Add task to queue.

        Args:
            task: Task to enqueue
            priority: Task priority level
            timeout_seconds: Task execution timeout
            max_retries: Maximum retry attempts

        Returns:
            Task ID

        """
        async with self._lock:
            # Create queued task
            queued_task = QueuedTask(
                task=task,
                priority=priority,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )

            # Add to queue
            self._queues[priority].append(queued_task)
            self._tasks[task.id] = queued_task
            self._total_queued += 1

            logger.info(
                f"Task {task.id} enqueued with {priority} priority "
                f"(queue depth: {self.queue_depth})",
            )

            # Emit event
            await self.event_bus.publish(
                QATaskEvent(
                    task_id=task.id,
                    qa_type=task.metadata.get("qa_type", "ruff"),
                    event_type="queued",
                    payload={
                        "priority": priority,
                        "queue_depth": self.queue_depth,
                        "queued_at": queued_task.queued_at.isoformat(),
                    },
                ),
            )

            return task.id

    async def dequeue(self, worker_id: str) -> QueuedTask | None:
        """Dequeue highest priority task and assign to worker.

        Args:
            worker_id: Worker requesting task

        Returns:
            Queued task or None if queue is empty

        """
        async with self._lock:
            # Check queues in priority order
            for priority in [TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW]:
                queue = self._queues[priority]

                if queue:
                    # Get oldest task in this priority level
                    queued_task = queue.pop(0)

                    # Assign to worker
                    queued_task.assigned_worker = worker_id
                    queued_task.assigned_at = datetime.now(UTC)
                    queued_task.status = TaskQueueStatus.ASSIGNED
                    self._worker_assignments[worker_id].append(queued_task.task.id)

                    logger.info(
                        f"Task {queued_task.task.id} assigned to {worker_id} "
                        f"(priority: {priority}, age: {queued_task.age_seconds:.1f}s)",
                    )

                    # Emit event
                    await self.event_bus.publish(
                        QATaskEvent(
                            task_id=queued_task.task.id,
                            qa_type=queued_task.task.metadata.get("qa_type", "ruff"),
                            event_type="assigned",
                            payload={
                                "worker_id": worker_id,
                                "priority": priority,
                                "age_seconds": queued_task.age_seconds,
                            },
                        ),
                    )

                    return queued_task

            return None

    async def mark_in_progress(self, task_id: str) -> bool:
        """Mark task as in progress.

        Args:
            task_id: Task ID

        Returns:
            True if status updated, False otherwise

        """
        async with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"Task {task_id} not found")
                return False

            queued_task = self._tasks[task_id]
            queued_task.status = TaskQueueStatus.IN_PROGRESS
            queued_task.started_at = datetime.now(UTC)

            logger.info(f"Task {task_id} marked in progress")
            return True

    async def mark_completed(self, task_id: str, result: dict[str, Any]) -> bool:
        """Mark task as completed.

        Args:
            task_id: Task ID
            result: Task execution result

        Returns:
            True if status updated, False otherwise

        """
        async with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"Task {task_id} not found")
                return False

            queued_task = self._tasks[task_id]
            queued_task.status = TaskQueueStatus.COMPLETED
            queued_task.completed_at = datetime.now(UTC)
            queued_task.metadata["result"] = result

            # Remove from worker assignments
            if queued_task.assigned_worker:
                worker_tasks = self._worker_assignments[queued_task.assigned_worker]
                if task_id in worker_tasks:
                    worker_tasks.remove(task_id)

            self._total_completed += 1

            execution_time = 0
            if queued_task.started_at:
                execution_time = (queued_task.completed_at - queued_task.started_at).total_seconds()

            logger.info(
                f"Task {task_id} completed in {execution_time:.1f}s "
                f"(total completed: {self._total_completed})",
            )

            return True

    async def mark_failed(self, task_id: str, error: str, retry: bool = True) -> bool:
        """Mark task as failed and optionally retry.

        Args:
            task_id: Task ID
            error: Error message
            retry: Whether to retry the task

        Returns:
            True if status updated, False otherwise

        """
        async with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"Task {task_id} not found")
                return False

            queued_task = self._tasks[task_id]
            queued_task.retry_count += 1

            # Check if can retry
            if retry and queued_task.can_retry:
                # Re-enqueue with higher priority
                new_priority = (
                    TaskPriority.HIGH
                    if queued_task.priority == TaskPriority.NORMAL
                    else queued_task.priority
                )

                queued_task.status = TaskQueueStatus.QUEUED
                queued_task.assigned_worker = None
                queued_task.assigned_at = None
                queued_task.started_at = None
                self._queues[new_priority].append(queued_task)

                logger.info(
                    f"Task {task_id} failed (retry {queued_task.retry_count}/{queued_task.max_retries}), "
                    f"re-queued with {new_priority} priority",
                )

            else:
                # Mark as permanently failed
                queued_task.status = TaskQueueStatus.FAILED
                queued_task.metadata["error"] = error
                self._total_failed += 1

                # Remove from worker assignments
                if queued_task.assigned_worker:
                    worker_tasks = self._worker_assignments[queued_task.assigned_worker]
                    if task_id in worker_tasks:
                        worker_tasks.remove(task_id)

                logger.error(
                    f"Task {task_id} permanently failed after {queued_task.retry_count} retries: {error}",
                )

            return True

    async def check_timeouts(self) -> list[str]:
        """Check for timed out tasks and handle them.

        Returns:
            List of timed out task IDs

        """
        timed_out = []

        async with self._lock:
            for task_id, queued_task in self._tasks.items():
                if queued_task.status == TaskQueueStatus.IN_PROGRESS and queued_task.is_timeout:
                    queued_task.status = TaskQueueStatus.TIMEOUT
                    self._total_timeout += 1
                    timed_out.append(task_id)

                    logger.warning(
                        f"Task {task_id} timed out after {queued_task.timeout_seconds}s, "
                        f"assigned to {queued_task.assigned_worker}",
                    )

                    # Re-enqueue if retries available
                    await self.mark_failed(task_id, "Task timeout", retry=True)

        return timed_out

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get task status and metadata.

        Args:
            task_id: Task ID

        Returns:
            Task status dict or None if not found

        """
        async with self._lock:
            if task_id not in self._tasks:
                return None

            queued_task = self._tasks[task_id]

            return {
                "task_id": task_id,
                "status": queued_task.status,
                "priority": queued_task.priority,
                "assigned_worker": queued_task.assigned_worker,
                "queued_at": queued_task.queued_at.isoformat(),
                "started_at": queued_task.started_at.isoformat() if queued_task.started_at else None,
                "completed_at": queued_task.completed_at.isoformat()
                if queued_task.completed_at
                else None,
                "age_seconds": queued_task.age_seconds,
                "retry_count": queued_task.retry_count,
                "metadata": queued_task.metadata,
            }

    async def get_worker_load(self, worker_id: str) -> int:
        """Get number of tasks assigned to worker.

        Args:
            worker_id: Worker ID

        Returns:
            Number of assigned tasks

        """
        async with self._lock:
            return len(self._worker_assignments[worker_id])

    @property
    def queue_depth(self) -> int:
        """Total number of tasks in all queues"""
        return sum(len(queue) for queue in self._queues.values())

    @property
    def queue_depths_by_priority(self) -> dict[str, int]:
        """Queue depths by priority level"""
        return {priority.value: len(queue) for priority, queue in self._queues.items()}

    async def get_metrics(self) -> dict[str, Any]:
        """Get queue metrics.

        Returns:
            Queue metrics dictionary

        """
        async with self._lock:
            # Calculate average wait time
            wait_times = []
            for queued_task in self._tasks.values():
                if queued_task.assigned_at:
                    wait_time = (queued_task.assigned_at - queued_task.queued_at).total_seconds()
                    wait_times.append(wait_time)

            avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0

            # Calculate average execution time
            exec_times = []
            for queued_task in self._tasks.values():
                if queued_task.started_at and queued_task.completed_at:
                    exec_time = (queued_task.completed_at - queued_task.started_at).total_seconds()
                    exec_times.append(exec_time)

            avg_exec_time = sum(exec_times) / len(exec_times) if exec_times else 0

            return {
                "queue_depth": self.queue_depth,
                "queue_depths_by_priority": self.queue_depths_by_priority,
                "total_queued": self._total_queued,
                "total_completed": self._total_completed,
                "total_failed": self._total_failed,
                "total_timeout": self._total_timeout,
                "avg_wait_time_seconds": avg_wait_time,
                "avg_execution_time_seconds": avg_exec_time,
                "active_workers": len(self._worker_assignments),
                "worker_loads": {
                    worker_id: len(tasks)
                    for worker_id, tasks in self._worker_assignments.items()
                },
            }

    async def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """Remove completed tasks older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours for completed tasks

        Returns:
            Number of tasks cleaned up

        """
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        cleaned = 0

        async with self._lock:
            tasks_to_remove = []

            for task_id, queued_task in self._tasks.items():
                if queued_task.status in [TaskQueueStatus.COMPLETED, TaskQueueStatus.FAILED]:
                    if queued_task.completed_at and queued_task.completed_at < cutoff:
                        tasks_to_remove.append(task_id)

            for task_id in tasks_to_remove:
                del self._tasks[task_id]
                cleaned += 1

            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} old tasks (older than {max_age_hours}h)")

        return cleaned
