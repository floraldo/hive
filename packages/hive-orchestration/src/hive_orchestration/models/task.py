"""
Task Models

Data models for orchestration tasks.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from hive_models import IdentifiableMixin, MetadataMixin, StatusMixin, TimestampMixin


class TaskStatus(str, Enum):
    """Task lifecycle states."""

    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REWORK_NEEDED = "rework_needed"
    ESCALATED = "escalated"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(IdentifiableMixin, TimestampMixin, StatusMixin, MetadataMixin):
    """
    Orchestration task model.

    Represents a unit of work to be executed by the orchestration system.
    """

    title: str = Field(..., description="Task title")
    description: str = Field(default="", description="Task description")
    task_type: str = Field(..., description="Type of task (e.g., 'deployment', 'analysis')")
    priority: int = Field(default=1, description="Task priority (higher = more important)")
    status: TaskStatus = Field(default=TaskStatus.QUEUED, description="Current task status")
    current_phase: str = Field(default="start", description="Current phase in workflow")
    workflow: dict[str, Any] | None = Field(default=None, description="JSON workflow definition (state machine)")
    payload: dict[str, Any] | None = Field(default=None, description="Task payload data")
    assigned_worker: str | None = Field(default=None, description="ID of assigned worker")
    due_date: datetime | None = Field(default=None, description="Task due date")
    max_retries: int = Field(default=3, description="Maximum number of retry attempts")
    parent_task_id: str | None = Field(default=None, description="Parent task ID for subtasks")
    plan_id: str | None = Field(default=None, description="Execution plan ID this task belongs to")
    dependencies: list[str] = Field(default_factory=list, description="List of task IDs this task depends on")

    def is_ready(self) -> bool:
        """Check if task is ready for execution (queued and dependencies met)."""
        return self.status == TaskStatus.QUEUED

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state (completed, failed, or cancelled)."""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)

    def is_active(self) -> bool:
        """Check if task is actively being worked on."""
        return self.status in (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS)

    def assign_to_worker(self, worker_id: str) -> None:
        """Assign task to a worker."""
        self.assigned_worker = worker_id
        self.update_status(TaskStatus.ASSIGNED.value)

    def start_execution(self) -> None:
        """Mark task as in progress."""
        self.update_status(TaskStatus.IN_PROGRESS.value)

    def complete(self) -> None:
        """Mark task as completed."""
        self.update_status(TaskStatus.COMPLETED.value)

    def fail(self, error_message: str | None = None) -> None:
        """Mark task as failed."""
        self.update_status(TaskStatus.FAILED.value, error_message)

    def cancel(self, reason: str | None = None) -> None:
        """Mark task as cancelled."""
        self.update_status(TaskStatus.CANCELLED.value, reason)


__all__ = ["Task", "TaskStatus"]
