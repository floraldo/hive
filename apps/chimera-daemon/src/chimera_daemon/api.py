"""REST API - Task submission and status retrieval.

Provides HTTP endpoints for interacting with Chimera daemon.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from hive_config import HiveConfig, create_config_from_sources
from hive_logging import get_logger
from pydantic import BaseModel

from .task_queue import TaskQueue, TaskStatus

logger = get_logger(__name__)


# Request/Response models
class TaskSubmitRequest(BaseModel):
    """Request to submit new task."""

    feature: str
    target_url: str
    staging_url: str | None = None
    priority: int = 5


class TaskSubmitResponse(BaseModel):
    """Response for task submission."""

    task_id: str
    status: str
    created_at: datetime


class TaskStatusResponse(BaseModel):
    """Response for task status query."""

    task_id: str
    status: str
    phase: str | None = None
    progress: str | None = None
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None


class HealthResponse(BaseModel):
    """Response for health check."""

    status: str
    uptime: float
    tasks_queued: int
    tasks_running: int
    tasks_completed: int
    tasks_failed: int


class MetricsResponse(BaseModel):
    """Response for pool metrics."""

    pool_size: int
    active_workflows: int
    available_slots: int
    total_workflows_processed: int
    total_workflows_succeeded: int
    total_workflows_failed: int
    avg_workflow_duration_ms: float
    success_rate: float


# FastAPI app
def create_app(config: HiveConfig | None = None) -> FastAPI:
    """Create FastAPI application.

    Args:
        config: Hive configuration

    Returns:
        Configured FastAPI app
    """
    config = config or create_config_from_sources()

    app = FastAPI(
        title="Chimera Daemon API",
        description="REST API for autonomous Chimera workflow execution",
        version="0.1.0",
    )

    # Task queue
    db_path = config.database.path.parent / "chimera_tasks.db"
    task_queue = TaskQueue(db_path=db_path)

    # Startup time for uptime calculation
    startup_time = datetime.now()

    # Note: on_event is deprecated but still works for now
    # TODO: Migrate to lifespan context manager in future
    @app.on_event("startup")
    async def startup() -> None:
        """Initialize on startup."""
        try:
            await task_queue.initialize()
            logger.info("Chimera API started")
        except Exception as e:
            logger.error(f"Failed to initialize task queue: {e}", exc_info=True)
            raise

    @app.post("/api/tasks", response_model=TaskSubmitResponse)
    async def submit_task(request: TaskSubmitRequest) -> TaskSubmitResponse:
        """Submit new Chimera workflow task.

        Args:
            request: Task submission request

        Returns:
            Task submission response with task_id

        Example:
            POST /api/tasks
            {
                "feature": "User can login with Google OAuth",
                "target_url": "https://myapp.dev/login",
                "staging_url": "https://staging.myapp.dev/login",
                "priority": 8
            }
        """
        # Generate task ID
        task_id = f"chimera-{uuid.uuid4().hex[:12]}"

        # Enqueue task
        await task_queue.enqueue(
            task_id=task_id,
            feature=request.feature,
            target_url=request.target_url,
            staging_url=request.staging_url,
            priority=request.priority,
        )

        logger.info(f"Task submitted via API: {task_id}")

        return TaskSubmitResponse(
            task_id=task_id,
            status=TaskStatus.QUEUED.value,
            created_at=datetime.now(),
        )

    @app.get("/api/tasks/{task_id}", response_model=TaskStatusResponse)
    async def get_task_status(task_id: str) -> TaskStatusResponse:
        """Get task execution status.

        Args:
            task_id: Task identifier

        Returns:
            Task status and result

        Raises:
            HTTPException: If task not found

        Example:
            GET /api/tasks/chimera-abc123
        """
        task = await task_queue.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        # Calculate progress
        progress = None
        phase = None

        if task.workflow_state:
            current_phase = task.workflow_state.get("current_phase")
            phase = current_phase

            # Estimate progress (simplified)
            phase_map = {
                "E2E_TEST_GENERATION": "1/7",
                "CODE_IMPLEMENTATION": "2/7",
                "GUARDIAN_REVIEW": "3/7",
                "STAGING_DEPLOYMENT": "4/7",
                "E2E_VALIDATION": "5/7",
                "COMPLETE": "7/7",
                "FAILED": "N/A",
            }
            progress = phase_map.get(current_phase, "Unknown")

        # Calculate duration
        duration = None
        if task.completed_at and task.started_at:
            duration = (task.completed_at - task.started_at).total_seconds()

        return TaskStatusResponse(
            task_id=task.task_id,
            status=task.status.value,
            phase=phase,
            progress=progress,
            result=task.result,
            error=task.error,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            duration=duration,
        )

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """Health check endpoint.

        Returns:
            Daemon health status and metrics

        Example:
            GET /health
        """
        uptime = (datetime.now() - startup_time).total_seconds()

        tasks_queued = await task_queue.count_by_status(TaskStatus.QUEUED)
        tasks_running = await task_queue.count_by_status(TaskStatus.RUNNING)
        tasks_completed = await task_queue.count_by_status(TaskStatus.COMPLETED)
        tasks_failed = await task_queue.count_by_status(TaskStatus.FAILED)

        return HealthResponse(
            status="healthy",
            uptime=uptime,
            tasks_queued=tasks_queued,
            tasks_running=tasks_running,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
        )

    return app


__all__ = [
    "create_app",
    "TaskSubmitRequest",
    "TaskSubmitResponse",
    "TaskStatusResponse",
    "HealthResponse",
    "MetricsResponse",
]
