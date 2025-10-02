"""
Worker Models

Data models for orchestration workers.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from hive_models import BaseModel, IdentifiableMixin, MetadataMixin, StatusMixin, TimestampMixin


class WorkerStatus(str, Enum):
    """Worker lifecycle states."""

    ACTIVE = "active"
    IDLE = "idle"
    OFFLINE = "offline"
    ERROR = "error"


class Worker(IdentifiableMixin, TimestampMixin, StatusMixin, MetadataMixin):
    """
    Orchestration worker model.

    Represents a worker process that executes tasks.
    """

    role: str = Field(..., description="Worker role (e.g., 'executor', 'backend', 'frontend')")
    status: WorkerStatus = Field(default=WorkerStatus.ACTIVE, description="Current worker status")
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow, description="Last heartbeat timestamp")
    capabilities: list[str] = Field(default_factory=list, description="Worker capabilities (e.g., ['python', 'bash'])")
    current_task_id: str | None = Field(default=None, description="ID of currently executing task")
    registered_at: datetime = Field(default_factory=datetime.utcnow, description="Worker registration timestamp")

    def is_active(self) -> bool:
        """Check if worker is active."""
        return self.status == WorkerStatus.ACTIVE

    def is_available(self) -> bool:
        """Check if worker is available for new tasks."""
        return self.status in (WorkerStatus.ACTIVE, WorkerStatus.IDLE) and self.current_task_id is None

    def has_capability(self, capability: str) -> bool:
        """Check if worker has a specific capability."""
        return capability in self.capabilities

    def update_heartbeat(self) -> None:
        """Update worker heartbeat timestamp."""
        self.last_heartbeat = datetime.utcnow()

    def assign_task(self, task_id: str) -> None:
        """Assign a task to this worker."""
        self.current_task_id = task_id
        self.update_status(WorkerStatus.ACTIVE.value)
        self.update_heartbeat()

    def complete_task(self) -> None:
        """Mark current task as complete and worker as idle."""
        self.current_task_id = None
        self.update_status(WorkerStatus.IDLE.value)
        self.update_heartbeat()

    def mark_offline(self, reason: str | None = None) -> None:
        """Mark worker as offline."""
        self.update_status(WorkerStatus.OFFLINE.value, reason)

    def mark_error(self, error_message: str) -> None:
        """Mark worker as having an error."""
        self.update_status(WorkerStatus.ERROR.value, error_message)


__all__ = ["Worker", "WorkerStatus"]
