"""Tests for ProjectOrchestrator."""

from pathlib import Path

import pytest

from hive_ui.orchestrator import ProjectOrchestrator, ProjectStatus


@pytest.fixture
def orchestrator(tmp_path: Path) -> ProjectOrchestrator:
    """Create test orchestrator with temporary workspace."""
    return ProjectOrchestrator(workspace_dir=tmp_path)


@pytest.mark.asyncio
async def test_create_project(orchestrator: ProjectOrchestrator):
    """Test project creation."""
    project_id = await orchestrator.create_project(
        requirement="Create a test service",
        service_name="test-service",
    )

    assert project_id is not None
    assert len(project_id) == 36  # UUID format

    # Check project state
    project = orchestrator.get_project_status(project_id)
    assert project["id"] == project_id
    assert project["service_name"] == "test-service"
    assert project["requirement"] == "Create a test service"
    assert project["status"] == ProjectStatus.PENDING


@pytest.mark.asyncio
async def test_list_projects(orchestrator: ProjectOrchestrator):
    """Test listing projects."""
    # Create two projects
    await orchestrator.create_project("Test 1", "service-1")
    await orchestrator.create_project("Test 2", "service-2")

    projects = orchestrator.list_projects()
    assert len(projects) == 2
    assert all(p["status"] == ProjectStatus.PENDING for p in projects)


@pytest.mark.asyncio
async def test_get_project_status_not_found(orchestrator: ProjectOrchestrator):
    """Test getting status of non-existent project."""
    with pytest.raises(ValueError, match="not found"):
        orchestrator.get_project_status("invalid-id")
