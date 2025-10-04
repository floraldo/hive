"""Tests for hive-ui API endpoints."""

import pytest
from fastapi.testclient import TestClient

from hive_ui.api.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    app = create_app()
    return TestClient(app)


def test_health_liveness(client: TestClient):
    """Test liveness endpoint."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == "hive-ui"


def test_health_readiness(client: TestClient):
    """Test readiness endpoint."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "hive-ui"


def test_create_project(client: TestClient):
    """Test project creation endpoint."""
    response = client.post(
        "/api/projects",
        json={
            "requirement": "Create a test service",
            "service_name": "test-api",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "project_id" in data
    assert data["status"] == "created"
    assert "/api/projects/" in data["status_url"]


def test_list_projects(client: TestClient):
    """Test listing projects."""
    # Create a project first
    client.post(
        "/api/projects",
        json={"requirement": "Test project"},
    )

    # List projects
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) >= 1


def test_get_project(client: TestClient):
    """Test getting project details."""
    # Create project
    create_response = client.post(
        "/api/projects",
        json={"requirement": "Test project"},
    )
    project_id = create_response.json()["project_id"]

    # Get project
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    project = response.json()
    assert project["id"] == project_id
    assert project["requirement"] == "Test project"


def test_get_project_not_found(client: TestClient):
    """Test getting non-existent project."""
    response = client.get("/api/projects/invalid-id")
    assert response.status_code == 404


def test_get_project_logs(client: TestClient):
    """Test getting project logs."""
    # Create project
    create_response = client.post(
        "/api/projects",
        json={"requirement": "Test project"},
    )
    project_id = create_response.json()["project_id"]

    # Get logs
    response = client.get(f"/api/projects/{project_id}/logs")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert "logs" in data
    assert "status" in data
