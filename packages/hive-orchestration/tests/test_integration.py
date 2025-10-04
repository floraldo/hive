"""Integration tests for hive-orchestration package.

Tests the full workflow of task and worker orchestration operations.
"""
import os
import tempfile

import pytest


@pytest.mark.core
@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    from hive_orchestration.database import init_db
    from hive_orchestration.database.operations import get_connection
    os.environ["HIVE_ORCHESTRATION_DB"] = db_path
    with get_connection(db_path):
        from hive_orchestration.database import transaction
        from hive_orchestration.database.schema import init_db
        with transaction(db_path):
            pass
    init_db()
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.mark.core
def test_full_task_workflow(test_db):
    """Test complete task lifecycle."""
    from hive_orchestration.operations import (
        create_task,
        get_queued_tasks,
        get_task,
        get_tasks_by_status,
        update_task_status,
    )
    task_id = create_task(title="Test Task", task_type="test", description="Integration test task", payload={"data": "test"}, priority=5)
    assert task_id is not None
    task = get_task(task_id)
    assert task is not None
    assert task["title"] == "Test Task"
    assert task["status"] == "queued"
    assert task["payload"] == {"data": "test"}
    queued = get_queued_tasks()
    assert len(queued) == 1
    assert queued[0]["id"] == task_id
    success = update_task_status(task_id, "in_progress")
    assert success is True
    task = get_task(task_id)
    assert task["status"] == "in_progress"
    in_progress_tasks = get_tasks_by_status("in_progress")
    assert len(in_progress_tasks) == 1
    assert in_progress_tasks[0]["id"] == task_id
    success = update_task_status(task_id, "completed")
    assert success is True

@pytest.mark.core
def test_worker_registration_and_heartbeat(test_db):
    """Test worker registration and heartbeat."""
    from hive_orchestration.operations import get_active_workers, get_worker, register_worker, update_worker_heartbeat
    success = register_worker(worker_id="worker-test-1", role="executor", capabilities=["python", "bash"], metadata={"version": "1.0"})
    assert success is True
    worker = get_worker("worker-test-1")
    assert worker is not None
    assert worker["role"] == "executor"
    assert "python" in worker["capabilities"]
    success = update_worker_heartbeat("worker-test-1", status="active")
    assert success is True
    workers = get_active_workers()
    assert len(workers) == 1
    assert workers[0]["id"] == "worker-test-1"
    executors = get_active_workers(role="executor")
    assert len(executors) == 1

@pytest.mark.core
def test_client_sdk(test_db):
    """Test the client SDK."""
    from hive_orchestration import get_client
    client = get_client()
    task_id = client.create_task(title="SDK Test", task_type="test", payload={"sdk": True})
    assert task_id is not None
    task = client.get_task(task_id)
    assert task is not None
    assert task["title"] == "SDK Test"
    success = client.register_worker(worker_id="sdk-worker", role="test", capabilities=["sdk"])
    assert success is True
    pending = client.get_pending_tasks()
    assert len(pending) >= 1
    success = client.update_task_status(task_id, "completed")
    assert success is True

@pytest.mark.core
def test_task_priority_ordering(test_db):
    """Test that queued tasks are ordered by priority."""
    from hive_orchestration.operations import create_task, get_queued_tasks
    task1 = create_task("Low Priority", "test", priority=1)
    task2 = create_task("High Priority", "test", priority=10)
    task3 = create_task("Medium Priority", "test", priority=5)
    queued = get_queued_tasks()
    assert len(queued) == 3
    assert queued[0]["id"] == task2
    assert queued[1]["id"] == task3
    assert queued[2]["id"] == task1

@pytest.mark.core
def test_multiple_workers(test_db):
    """Test managing multiple workers."""
    from hive_orchestration.operations import get_active_workers, register_worker
    register_worker("worker-1", "executor", ["python"])
    register_worker("worker-2", "executor", ["bash"])
    register_worker("worker-3", "deployer", ["docker"])
    all_workers = get_active_workers()
    assert len(all_workers) == 3
    executors = get_active_workers(role="executor")
    assert len(executors) == 2
    deployers = get_active_workers(role="deployer")
    assert len(deployers) == 1
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
