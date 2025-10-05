"""Intelligent Task Scheduling for ExecutorPool.

Provides priority-based scheduling with deadline awareness and resource optimization.
"""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class Priority(Enum):
    """Task priority levels."""

    CRITICAL = 1  # System-critical tasks
    HIGH = 2  # User-facing, time-sensitive
    NORMAL = 3  # Standard tasks
    LOW = 4  # Background, can be deferred


@dataclass
class ScheduledTask:
    """Task with scheduling metadata."""

    task_id: str
    priority: Priority
    created_at: datetime
    deadline: datetime | None = None
    estimated_duration_ms: float | None = None
    dependencies: list[str] | None = None
    metadata: dict[str, Any] | None = None

    @property
    def age_seconds(self) -> float:
        """Get task age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()

    @property
    def time_to_deadline_seconds(self) -> float | None:
        """Get remaining time until deadline in seconds."""
        if self.deadline is None:
            return None
        return (self.deadline - datetime.now()).total_seconds()

    @property
    def is_overdue(self) -> bool:
        """Check if task has passed its deadline."""
        if self.deadline is None:
            return False
        return datetime.now() > self.deadline


class SchedulingStrategy(Enum):
    """Task scheduling strategies."""

    FIFO = "fifo"  # First In First Out
    PRIORITY = "priority"  # Priority-based
    EDF = "edf"  # Earliest Deadline First
    ADAPTIVE = "adaptive"  # Adaptive based on system load


class IntelligentScheduler:
    """Intelligent task scheduler with multiple strategies.

    Provides priority-based scheduling, deadline awareness, and adaptive
    queue management based on system load.

    Example:
        scheduler = IntelligentScheduler(strategy=SchedulingStrategy.ADAPTIVE)

        # Add task
        scheduler.add_task(ScheduledTask(
            task_id="task_1",
            priority=Priority.HIGH,
            created_at=datetime.now(),
            deadline=datetime.now() + timedelta(minutes=5),
        ))

        # Get next task to execute
        next_task = scheduler.get_next_task(
            current_pool_utilization=0.75,
            avg_execution_time_ms=5000,
        )
    """

    def __init__(
        self,
        strategy: SchedulingStrategy = SchedulingStrategy.ADAPTIVE,
        starvation_threshold_seconds: float = 300.0,  # 5 minutes
    ):
        """Initialize intelligent scheduler.

        Args:
            strategy: Scheduling strategy to use
            starvation_threshold_seconds: Max time a task can wait before priority boost
        """
        self.strategy = strategy
        self.starvation_threshold = starvation_threshold_seconds
        self.logger = logger

        # Task queues by priority
        self._queues: dict[Priority, deque[ScheduledTask]] = {
            Priority.CRITICAL: deque(),
            Priority.HIGH: deque(),
            Priority.NORMAL: deque(),
            Priority.LOW: deque(),
        }

        # Task lookup
        self._tasks: dict[str, ScheduledTask] = {}

        # Deadline heap for O(log n) EDF scheduling
        # Each entry: (deadline_timestamp, task_id) for tasks with deadlines
        self._deadline_heap: list[tuple[float, str]] = []

        # Scheduling metrics
        self._total_scheduled = 0
        self._total_completed = 0
        self._total_deadline_misses = 0

    def add_task(self, task: ScheduledTask) -> None:
        """Add a task to the scheduler.

        Args:
            task: Task to schedule
        """
        # Check for duplicates
        if task.task_id in self._tasks:
            self.logger.warning(f"Task {task.task_id} already scheduled")
            return

        # Add to appropriate priority queue
        self._queues[task.priority].append(task)
        self._tasks[task.task_id] = task
        self._total_scheduled += 1

        # Add to deadline heap if task has deadline
        if task.deadline is not None:
            deadline_timestamp = task.deadline.timestamp()
            heapq.heappush(self._deadline_heap, (deadline_timestamp, task.task_id))

        self.logger.debug(
            f"Scheduled task {task.task_id}",
            extra={
                "priority": task.priority.name,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "queue_depth": sum(len(q) for q in self._queues.values()),
            },
        )

    def get_next_task(
        self,
        current_pool_utilization: float = 0.0,
        avg_execution_time_ms: float = 0.0,
    ) -> ScheduledTask | None:
        """Get the next task to execute based on scheduling strategy.

        Args:
            current_pool_utilization: Current pool utilization (0.0-1.0)
            avg_execution_time_ms: Average task execution time

        Returns:
            Next task to execute or None if no tasks available
        """
        if self.strategy == SchedulingStrategy.FIFO:
            return self._get_next_fifo()
        elif self.strategy == SchedulingStrategy.PRIORITY:
            return self._get_next_priority()
        elif self.strategy == SchedulingStrategy.EDF:
            return self._get_next_edf()
        else:  # ADAPTIVE
            return self._get_next_adaptive(current_pool_utilization, avg_execution_time_ms)

    def _get_next_fifo(self) -> ScheduledTask | None:
        """Get next task using FIFO strategy."""
        # Find oldest task across all queues
        oldest_task: ScheduledTask | None = None
        oldest_queue: Priority | None = None

        for priority, queue in self._queues.items():
            if queue and (oldest_task is None or queue[0].created_at < oldest_task.created_at):
                oldest_task = queue[0]
                oldest_queue = priority

        if oldest_task and oldest_queue:
            self._queues[oldest_queue].popleft()
            del self._tasks[oldest_task.task_id]
            return oldest_task

        return None

    def _get_next_priority(self) -> ScheduledTask | None:
        """Get next task using priority-based strategy."""
        # Apply starvation prevention
        self._prevent_starvation()

        # Get from highest priority non-empty queue
        for priority in [Priority.CRITICAL, Priority.HIGH, Priority.NORMAL, Priority.LOW]:
            if self._queues[priority]:
                task = self._queues[priority].popleft()
                del self._tasks[task.task_id]
                return task

        return None

    def _get_next_edf(self) -> ScheduledTask | None:
        """Get next task using Earliest Deadline First strategy.

        Uses min-heap for O(log n) performance instead of O(n) linear scan.
        """
        # Pop from heap until we find a valid task (not already removed)
        while self._deadline_heap:
            deadline_timestamp, task_id = heapq.heappop(self._deadline_heap)

            # Check if task still exists (may have been removed)
            if task_id not in self._tasks:
                continue

            task = self._tasks[task_id]

            # Remove from priority queue
            try:
                self._queues[task.priority].remove(task)
                del self._tasks[task_id]
            except ValueError:
                # Task not in queue (shouldn't happen, but defensive)
                continue

            # Track deadline misses
            if task.is_overdue:
                self._total_deadline_misses += 1
                self.logger.warning(
                    f"Task {task.task_id} missed deadline by "
                    f"{-task.time_to_deadline_seconds:.1f}s"
                )

            return task

        # Fallback to priority if no deadlines
        return self._get_next_priority()

    def _get_next_adaptive(
        self,
        current_pool_utilization: float,
        avg_execution_time_ms: float,
    ) -> ScheduledTask | None:
        """Get next task using adaptive strategy based on system load.

        Args:
            current_pool_utilization: Current pool utilization (0.0-1.0)
            avg_execution_time_ms: Average task execution time

        Returns:
            Next task to execute
        """
        # Under high load (>80%), prioritize critical and deadline-sensitive tasks
        if current_pool_utilization > 0.8:
            # Check for critical tasks first
            if self._queues[Priority.CRITICAL]:
                task = self._queues[Priority.CRITICAL].popleft()
                del self._tasks[task.task_id]
                return task

            # Then check for tasks approaching deadline
            urgent_task = self._get_most_urgent_task(threshold_seconds=60.0)
            if urgent_task:
                return urgent_task

            # Fall back to high priority
            if self._queues[Priority.HIGH]:
                task = self._queues[Priority.HIGH].popleft()
                del self._tasks[task.task_id]
                return task

        # Under moderate load (50-80%), use EDF for deadline-aware scheduling
        elif current_pool_utilization > 0.5:
            return self._get_next_edf()

        # Under low load (<50%), use priority-based to ensure fairness
        else:
            return self._get_next_priority()

        return None

    def _get_most_urgent_task(self, threshold_seconds: float) -> ScheduledTask | None:
        """Get task with deadline within threshold.

        Args:
            threshold_seconds: Deadline threshold in seconds

        Returns:
            Most urgent task or None
        """
        urgent_task: ScheduledTask | None = None
        urgent_queue: Priority | None = None
        min_time_to_deadline: float | None = None

        for priority, queue in self._queues.items():
            for task in queue:
                time_to_deadline = task.time_to_deadline_seconds
                if time_to_deadline is None:
                    continue

                if time_to_deadline <= threshold_seconds:
                    if min_time_to_deadline is None or time_to_deadline < min_time_to_deadline:
                        urgent_task = task
                        urgent_queue = priority
                        min_time_to_deadline = time_to_deadline

        if urgent_task and urgent_queue:
            self._queues[urgent_queue].remove(urgent_task)
            del self._tasks[urgent_task.task_id]
            return urgent_task

        return None

    def _prevent_starvation(self) -> None:
        """Prevent low-priority task starvation by boosting aged tasks."""
        # Check LOW priority queue
        for task in list(self._queues[Priority.LOW]):
            if task.age_seconds > self.starvation_threshold:
                self._queues[Priority.LOW].remove(task)
                task.priority = Priority.NORMAL
                self._queues[Priority.NORMAL].append(task)
                self.logger.info(f"Boosted task {task.task_id} from LOW to NORMAL (starvation prevention)")

        # Check NORMAL priority queue
        for task in list(self._queues[Priority.NORMAL]):
            if task.age_seconds > self.starvation_threshold * 1.5:
                self._queues[Priority.NORMAL].remove(task)
                task.priority = Priority.HIGH
                self._queues[Priority.HIGH].append(task)
                self.logger.info(f"Boosted task {task.task_id} from NORMAL to HIGH (starvation prevention)")

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the scheduler.

        Args:
            task_id: Task ID to remove

        Returns:
            True if task was removed, False if not found
        """
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        self._queues[task.priority].remove(task)
        del self._tasks[task_id]

        self.logger.debug(f"Removed task {task_id} from scheduler")
        return True

    def get_queue_depths(self) -> dict[str, int]:
        """Get current queue depths by priority.

        Returns:
            Dictionary mapping priority to queue depth
        """
        return {priority.name: len(queue) for priority, queue in self._queues.items()}

    def get_metrics(self) -> dict[str, Any]:
        """Get scheduling metrics.

        Returns:
            Dictionary with scheduling statistics
        """
        total_queued = sum(len(q) for q in self._queues.values())

        return {
            "total_scheduled": self._total_scheduled,
            "total_completed": self._total_completed,
            "total_deadline_misses": self._total_deadline_misses,
            "currently_queued": total_queued,
            "queue_depths": self.get_queue_depths(),
            "deadline_miss_rate": (
                self._total_deadline_misses / self._total_completed
                if self._total_completed > 0
                else 0.0
            ),
        }

    def mark_completed(self, task_id: str, missed_deadline: bool = False) -> None:
        """Mark a task as completed for metrics tracking.

        Args:
            task_id: Task ID that was completed
            missed_deadline: Whether the task missed its deadline
        """
        self._total_completed += 1
        if missed_deadline:
            self._total_deadline_misses += 1

    def get_pending_tasks(self) -> list[ScheduledTask]:
        """Get all pending tasks across all queues.

        Returns:
            List of all pending tasks
        """
        tasks = []
        for queue in self._queues.values():
            tasks.extend(queue)
        return tasks

    def clear(self) -> None:
        """Clear all queued tasks."""
        for queue in self._queues.values():
            queue.clear()
        self._tasks.clear()
        self._deadline_heap.clear()
        self.logger.info("Cleared all scheduled tasks")


__all__ = ["IntelligentScheduler", "ScheduledTask", "Priority", "SchedulingStrategy"]
