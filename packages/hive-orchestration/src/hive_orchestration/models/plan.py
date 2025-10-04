"""Execution Plan Models

Data models for execution plans and subtask orchestration.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from hive_models import BaseModel, IdentifiableMixin, MetadataMixin, StatusMixin, TimestampMixin


class PlanStatus(str, Enum):
    """Execution plan states."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionPlan(IdentifiableMixin, TimestampMixin, StatusMixin, MetadataMixin):
    """Execution plan model.

    Represents a multi-step execution plan with dependencies.
    """

    title: str = Field(..., description="Plan title")
    description: str = Field(default="", description="Plan description")
    parent_task_id: str | None = Field(default=None, description="Parent task ID if this is a subtask plan")
    status: PlanStatus = Field(default=PlanStatus.PENDING, description="Current plan status")
    total_subtasks: int = Field(default=0, description="Total number of subtasks in plan")
    completed_subtasks: int = Field(default=0, description="Number of completed subtasks")
    failed_subtasks: int = Field(default=0, description="Number of failed subtasks")
    subtask_ids: list[str] = Field(default_factory=list, description="IDs of subtasks in execution order")
    dependency_graph: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Dependency graph mapping subtask_id -> list of dependency task_ids",
    )

    def is_complete(self) -> bool:
        """Check if plan is complete."""
        return self.status == PlanStatus.COMPLETED

    def is_failed(self) -> bool:
        """Check if plan has failed."""
        return self.status == PlanStatus.FAILED

    def is_in_progress(self) -> bool:
        """Check if plan is currently executing."""
        return self.status == PlanStatus.IN_PROGRESS

    def get_progress_percentage(self) -> float:
        """Get plan completion percentage."""
        if self.total_subtasks == 0:
            return 0.0
        return (self.completed_subtasks / self.total_subtasks) * 100.0

    def increment_completed(self) -> None:
        """Increment completed subtask counter."""
        self.completed_subtasks += 1
        self.update_timestamp()

    def increment_failed(self) -> None:
        """Increment failed subtask counter."""
        self.failed_subtasks += 1
        self.update_timestamp()

    def start_execution(self) -> None:
        """Mark plan as in progress."""
        self.update_status(PlanStatus.IN_PROGRESS.value)

    def complete(self) -> None:
        """Mark plan as completed."""
        self.update_status(PlanStatus.COMPLETED.value)

    def fail(self, reason: str | None = None) -> None:
        """Mark plan as failed."""
        self.update_status(PlanStatus.FAILED.value, reason)

    def cancel(self, reason: str | None = None) -> None:
        """Mark plan as cancelled."""
        self.update_status(PlanStatus.CANCELLED.value, reason)

    def get_dependencies(self, subtask_id: str) -> list[str]:
        """Get list of dependencies for a specific subtask."""
        return self.dependency_graph.get(subtask_id, [])

    def add_dependency(self, subtask_id: str, depends_on: str) -> None:
        """Add a dependency relationship."""
        if subtask_id not in self.dependency_graph:
            self.dependency_graph[subtask_id] = []
        if depends_on not in self.dependency_graph[subtask_id]:
            self.dependency_graph[subtask_id].append(depends_on)


class SubTask(BaseModel):
    """Subtask definition within an execution plan.

    Lighter weight than full Task model, used for plan definition.
    """

    id: str = Field(..., description="Subtask identifier")
    title: str = Field(..., description="Subtask title")
    description: str = Field(default="", description="Subtask description")
    task_type: str = Field(..., description="Type of task")
    priority: int = Field(default=1, description="Task priority")
    payload: dict[str, Any] | None = Field(default=None, description="Task payload")
    dependencies: list[str] = Field(default_factory=list, description="List of subtask IDs this depends on")
    estimated_duration: int | None = Field(default=None, description="Estimated duration in seconds")

    def has_dependencies(self) -> bool:
        """Check if subtask has dependencies."""
        return len(self.dependencies) > 0


__all__ = ["ExecutionPlan", "PlanStatus", "SubTask"]
