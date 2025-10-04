"""
ExecutionPlan model - The contract between Architect and Coder agents.

This is the machine-readable task list that the Architect generates
and the Coder Agent consumes to produce production code.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Type of task to execute"""

    SCAFFOLD = "scaffold"  # Generate project structure
    API_ENDPOINT = "api_endpoint"  # Create API route
    DATABASE_MODEL = "database_model"  # Define database schema
    SERVICE_LOGIC = "service_logic"  # Business logic implementation
    TEST_SUITE = "test_suite"  # Test generation
    DEPLOYMENT = "deployment"  # K8s/Docker configuration
    DOCUMENTATION = "documentation"  # README/API docs


class TaskDependency(BaseModel):
    """Dependency relationship between tasks"""

    task_id: str = Field(..., description="ID of the dependent task")
    dependency_type: str = Field(
        default="sequential",
        description="Type of dependency (sequential, parallel, optional)",
    )


class ExecutionTask(BaseModel):
    """A single task in the execution plan"""

    task_id: str = Field(..., description="Unique task identifier")
    task_type: TaskType = Field(..., description="Type of task")
    description: str = Field(..., description="Human-readable task description")
    template: str | None = Field(
        None,
        description="Template to use (from hive-app-toolkit)",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific parameters",
    )
    dependencies: list[TaskDependency] = Field(
        default_factory=list,
        description="Tasks that must complete before this one",
    )
    estimated_duration_minutes: int = Field(
        default=5,
        description="Estimated time to complete",
    )


class ExecutionPlan(BaseModel):
    """
    Complete execution plan for generating a service.

    This is the contract between Architect and Coder:
    - Architect generates this from natural language requirements
    - Coder executes tasks to produce production code
    """

    plan_id: str = Field(..., description="Unique plan identifier")
    service_name: str = Field(..., description="Name of service to generate")
    service_type: str = Field(
        ...,
        description="Type of service (api, worker, batch)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Plan creation timestamp",
    )
    tasks: list[ExecutionTask] = Field(
        default_factory=list,
        description="Ordered list of tasks to execute",
    )
    total_estimated_duration_minutes: int = Field(
        default=0,
        description="Sum of all task durations",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional plan metadata",
    )

    def model_post_init(self, __context: Any) -> None:
        """Calculate total duration after initialization"""
        if not self.total_estimated_duration_minutes:
            self.total_estimated_duration_minutes = sum(
                task.estimated_duration_minutes for task in self.tasks
            )

    def to_json_file(self, filepath: str) -> None:
        """Write plan to JSON file for Coder Agent consumption"""
        from pathlib import Path

        Path(filepath).write_text(
            self.model_dump_json(indent=2),
            encoding="utf-8",
        )

    @classmethod
    def from_json_file(cls, filepath: str) -> ExecutionPlan:
        """Load plan from JSON file"""
        import json
        from pathlib import Path

        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        return cls(**data)
