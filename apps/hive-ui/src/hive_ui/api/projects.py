"""Project management endpoints for Colossus Command Center."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from hive_ui.orchestrator import ProjectOrchestrator

router = APIRouter()

# Global orchestrator instance
orchestrator = ProjectOrchestrator(workspace_dir=Path("./workspaces"))


class CreateProjectRequest(BaseModel):
    """Request to create new autonomous development project."""

    requirement: str = Field(
        ...,
        description="Natural language requirement description",
        examples=["Create a user authentication API with JWT tokens"],
    )
    service_name: str | None = Field(
        None,
        description="Optional service name (auto-generated if not provided)",
        examples=["auth-api"],
    )


class ProjectResponse(BaseModel):
    """Project status response."""

    id: str
    service_name: str
    requirement: str
    status: str
    workspace: str
    plan_file: str | None
    service_dir: str | None
    logs: list[str]
    created_at: str | None


@router.post("/projects", response_model=dict[str, str])
async def create_project(
    request: CreateProjectRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Create new autonomous development project.

    This initiates the Colossus pipeline:
    1. Architect generates ExecutionPlan from requirement
    2. Coder implements service from plan
    3. Guardian validates and auto-fixes issues

    Args:
        request: Project creation request with requirement
        background_tasks: FastAPI background task runner

    Returns:
        Project ID and status URL
    """
    # Create project
    project_id = await orchestrator.create_project(
        requirement=request.requirement,
        service_name=request.service_name,
    )

    # Execute pipeline in background
    background_tasks.add_task(orchestrator.execute_project, project_id)

    return {
        "project_id": project_id,
        "status": "created",
        "status_url": f"/api/projects/{project_id}",
    }


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str) -> ProjectResponse:
    """
    Get project status and details.

    Args:
        project_id: Project identifier

    Returns:
        Complete project state including logs and status

    Raises:
        HTTPException: If project not found
    """
    try:
        project = orchestrator.get_project_status(project_id)
        return ProjectResponse(**project)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects() -> list[ProjectResponse]:
    """
    List all projects.

    Returns:
        List of all projects with their current status
    """
    projects = orchestrator.list_projects()
    return [ProjectResponse(**p) for p in projects]


@router.get("/projects/{project_id}/logs")
async def get_project_logs(project_id: str) -> dict[str, Any]:
    """
    Get project execution logs.

    Args:
        project_id: Project identifier

    Returns:
        Project logs and metadata

    Raises:
        HTTPException: If project not found
    """
    try:
        project = orchestrator.get_project_status(project_id)
        return {
            "project_id": project_id,
            "status": project["status"],
            "logs": project["logs"],
            "plan_file": project.get("plan_file"),
            "service_dir": project.get("service_dir"),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
