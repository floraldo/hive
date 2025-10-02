"""
Integration tests for hive-orchestration package.

Tests the full workflow of task and worker orchestration operations.
"""

import os
import tempfile

import pytest


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Initialize the database
    from hive_orchestration.database import init_db
    from hive_orchestration.database.operations import get_connection

    # Override default path for testing
    os.environ["HIVE_ORCHESTRATION_DB"] = db_path

    with get_connection(db_path) as conn:
        # Initialize directly on this connection
        from hive_orchestration.database import transaction
        from hive_orchestration.database.schema import init_db

        with transaction(db_path) as conn:
            # Just ensure connection works
            pass

    init_db()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_full_task_workflow(test_db):
    """Test complete task lifecycle."""
    from hive_orchestration.operations import (
        create_task,
        get_queued_tasks,
        get_task,
        get_tasks_by_status,
        update_task_status,
    )

    # Create a task
    task_id = create_task(
        title="Test Task",
        task_type="test",
        description="Integration test task",
        payload={"data": "test"},
        priority=5,
    )

    assert task_id is not None

    # Retrieve the task
    task = get_task(task_id)
    assert task is not None
    assert task["title"] == "Test Task"
    assert task["status"] == "queued"
    assert task["payload"] == {"data": "test"}

    # Get queued tasks
    queued = get_queued_tasks()
    assert len(queued) == 1
    assert queued[0]["id"] == task_id

    # Update task status
    success = update_task_status(task_id, "in_progress")
    assert success is True

    # Verify status update
    task = get_task(task_id)
    assert task["status"] == "in_progress"

    # Get tasks by status
    in_progress_tasks = get_tasks_by_status("in_progress")
    assert len(in_progress_tasks) == 1
    assert in_progress_tasks[0]["id"] == task_id

    # Complete the task
    success = update_task_status(task_id, "completed")
    assert success is True


def test_worker_registration_and_heartbeat(test_db):
    """Test worker registration and heartbeat."""
    from hive_orchestration.operations import (
        get_active_workers,
        get_worker,
        register_worker,
        update_worker_heartbeat,
    )

    # Register a worker
    success = register_worker(
        worker_id="worker-test-1",
        role="executor",
        capabilities=["python", "bash"],
        metadata={"version": "1.0"},
    )
    assert success is True

    # Get the worker
    worker = get_worker("worker-test-1")
    assert worker is not None
    assert worker["role"] == "executor"
    assert "python" in worker["capabilities"]

    # Update heartbeat
    success = update_worker_heartbeat("worker-test-1", status="active")
    assert success is True

    # Get active workers
    workers = get_active_workers()
    assert len(workers) == 1
    assert workers[0]["id"] == "worker-test-1"

    # Get workers by role
    executors = get_active_workers(role="executor")
    assert len(executors) == 1


def test_client_sdk(test_db):
    """Test the client SDK."""
    from hive_orchestration import get_client

    client = get_client()

    # Create task via client
    task_id = client.create_task(
        title="SDK Test",
        task_type="test",
        payload={"sdk": True},
    )
    assert task_id is not None

    # Get task
    task = client.get_task(task_id)
    assert task is not None
    assert task["title"] == "SDK Test"

    # Register worker
    success = client.register_worker(
        worker_id="sdk-worker",
        role="test",
        capabilities=["sdk"],
    )
    assert success is True

    # Get pending tasks
    pending = client.get_pending_tasks()
    assert len(pending) >= 1

    # Update status
    success = client.update_task_status(task_id, "completed")
    assert success is True


def test_task_priority_ordering(test_db):
    """Test that queued tasks are ordered by priority."""
    from hive_orchestration.operations import create_task, get_queued_tasks

    # Create tasks with different priorities
    task1 = create_task("Low Priority", "test", priority=1)
    task2 = create_task("High Priority", "test", priority=10)
    task3 = create_task("Medium Priority", "test", priority=5)

    # Get queued tasks (should be ordered by priority DESC)
    queued = get_queued_tasks()

    assert len(queued) == 3
    assert queued[0]["id"] == task2  # Highest priority first
    assert queued[1]["id"] == task3  # Medium priority second
    assert queued[2]["id"] == task1  # Lowest priority last


def test_multiple_workers(test_db):
    """Test managing multiple workers."""
    from hive_orchestration.operations import get_active_workers, register_worker

    # Register multiple workers
    register_worker("worker-1", "executor", ["python"])
    register_worker("worker-2", "executor", ["bash"])
    register_worker("worker-3", "deployer", ["docker"])

    # Get all active workers
    all_workers = get_active_workers()
    assert len(all_workers) == 3

    # Get workers by role
    executors = get_active_workers(role="executor")
    assert len(executors) == 2

    deployers = get_active_workers(role="deployer")
    assert len(deployers) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
