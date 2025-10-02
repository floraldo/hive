"""
Run Models

Data models for task execution runs (execution attempts).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from hive_models import BaseModel, IdentifiableMixin, TimestampMixin


class RunStatus(str, Enum):
    """Individual run (execution attempt) states."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class Run(BaseModel, IdentifiableMixin, TimestampMixin):
    """
    Task execution run model.

    Represents a single execution attempt of a task.
    """

    task_id: str = Field(..., description="ID of the task being executed")
    worker_id: str = Field(..., description="ID of the worker executing the task")
    run_number: int = Field(..., description="Sequential run number for this task")
    status: RunStatus = Field(default=RunStatus.PENDING, description="Current run status")
    phase: str | None = Field(default=None, description="Current execution phase")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Run start timestamp")
    completed_at: datetime | None = Field(default=None, description="Run completion timestamp")
    result_data: dict[str, Any] | None = Field(default=None, description="Execution result data")
    error_message: str | None = Field(default=None, description="Error message if failed")
    output_log: str | None = Field(default=None, description="Execution output log")
    transcript: str | None = Field(default=None, description="Full execution transcript")

    def is_terminal(self) -> bool:
        """Check if run is in a terminal state."""
        return self.status in (RunStatus.SUCCESS, RunStatus.FAILURE, RunStatus.TIMEOUT, RunStatus.CANCELLED)

    def is_running(self) -> bool:
        """Check if run is currently executing."""
        return self.status == RunStatus.RUNNING

    def start(self) -> None:
        """Mark run as started."""
        self.status = RunStatus.RUNNING
        self.started_at = datetime.utcnow()

    def succeed(self, result_data: dict[str, Any] | None = None) -> None:
        """Mark run as successful."""
        self.status = RunStatus.SUCCESS
        self.completed_at = datetime.utcnow()
        if result_data:
            self.result_data = result_data

    def fail(self, error_message: str, output_log: str | None = None) -> None:
        """Mark run as failed."""
        self.status = RunStatus.FAILURE
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        if output_log:
            self.output_log = output_log

    def timeout(self) -> None:
        """Mark run as timed out."""
        self.status = RunStatus.TIMEOUT
        self.completed_at = datetime.utcnow()
        self.error_message = "Execution timed out"

    def cancel(self, reason: str | None = None) -> None:
        """Mark run as cancelled."""
        self.status = RunStatus.CANCELLED
        self.completed_at = datetime.utcnow()
        if reason:
            self.error_message = reason

    @property
    def duration(self) -> float | None:
        """Get run duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


__all__ = ["Run", "RunStatus"]
