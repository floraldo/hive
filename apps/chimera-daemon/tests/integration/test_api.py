"""Integration tests for REST API."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hive_config import HiveConfig

from chimera_daemon.api import create_app


@pytest.fixture
def test_app():
    """Create test API app with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test config
        config = HiveConfig(
            environment="test",
            database={"path": Path(tmpdir) / "test.db"},
        )

        app = create_app(config=config)

        # Manually initialize task queue for testing
        # (TestClient doesn't trigger async startup events)
        from chimera_daemon.task_queue import TaskQueue
        db_path = config.database.path.parent / "chimera_tasks.db"
        queue = TaskQueue(db_path=db_path)

        # Run async initialization in sync context
        asyncio.run(queue.initialize())

        client = TestClient(app)

        yield client


def test_submit_task(test_app):
    """Test submitting task via API."""
    response = test_app.post(
        "/api/tasks",
        json={
            "feature": "User can login with Google OAuth",
            "target_url": "https://myapp.dev/login",
            "staging_url": "https://staging.myapp.dev/login",
            "priority": 8,
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["task_id"].startswith("chimera-")


def test_get_task_status(test_app):
    """Test getting task status via API."""
    # Submit task
    submit_response = test_app.post(
        "/api/tasks",
        json={
            "feature": "User login",
            "target_url": "https://app.dev",
            "priority": 5,
        },
    )

    task_id = submit_response.json()["task_id"]

    # Get status
    status_response = test_app.get(f"/api/tasks/{task_id}")

    assert status_response.status_code == 200

    data = status_response.json()
    assert data["task_id"] == task_id
    assert data["status"] == "queued"
    assert data["created_at"] is not None


def test_get_nonexistent_task(test_app):
    """Test getting status of nonexistent task."""
    response = test_app.get("/api/tasks/nonexistent-task-id")

    assert response.status_code == 404


def test_health_check(test_app):
    """Test health check endpoint."""
    response = test_app.get("/health")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime" in data
    assert "tasks_queued" in data
    assert "tasks_running" in data
    assert "tasks_completed" in data
    assert "tasks_failed" in data


def test_submit_multiple_tasks(test_app):
    """Test submitting multiple tasks."""
    task_ids = []

    for i in range(5):
        response = test_app.post(
            "/api/tasks",
            json={
                "feature": f"Feature {i}",
                "target_url": f"https://app.dev/feature{i}",
                "priority": i + 1,
            },
        )

        assert response.status_code == 200
        task_ids.append(response.json()["task_id"])

    # Verify all tasks created
    assert len(task_ids) == 5
    assert len(set(task_ids)) == 5  # All unique

    # Verify health check shows queued tasks
    health_response = test_app.get("/health")
    health_data = health_response.json()

    assert health_data["tasks_queued"] == 5
