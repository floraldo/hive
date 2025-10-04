"""Unit tests for TaskQueue."""

import tempfile
from pathlib import Path

import pytest

from chimera_daemon.task_queue import TaskQueue, TaskStatus


@pytest.fixture
async def task_queue():
    """Create temporary task queue for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_tasks.db"
        queue = TaskQueue(db_path=db_path)
        await queue.initialize()
        yield queue


@pytest.mark.asyncio
async def test_task_queue_initialization(task_queue):
    """Test task queue initializes database."""
    assert task_queue.db_path.exists()


@pytest.mark.asyncio
async def test_enqueue_task(task_queue):
    """Test enqueueing new task."""
    task_id = await task_queue.enqueue(
        task_id="test-001",
        feature="User login",
        target_url="https://app.dev",
        priority=5,
    )

    assert task_id == "test-001"

    # Verify task in queue
    task = await task_queue.get_task("test-001")
    assert task is not None
    assert task.feature_description == "User login"
    assert task.target_url == "https://app.dev"
    assert task.status == TaskStatus.QUEUED


@pytest.mark.asyncio
async def test_get_next_task_priority(task_queue):
    """Test get_next_task returns highest priority first."""
    # Enqueue tasks with different priorities
    await task_queue.enqueue("task-low", "Low priority", "https://app.dev", priority=3)
    await task_queue.enqueue("task-high", "High priority", "https://app.dev", priority=9)
    await task_queue.enqueue("task-med", "Medium priority", "https://app.dev", priority=5)

    # Should return highest priority
    next_task = await task_queue.get_next_task()
    assert next_task is not None
    assert next_task.task_id == "task-high"
    assert next_task.priority == 9


@pytest.mark.asyncio
async def test_mark_running(task_queue):
    """Test marking task as running."""
    await task_queue.enqueue("test-002", "Feature", "https://app.dev")

    await task_queue.mark_running("test-002")

    task = await task_queue.get_task("test-002")
    assert task.status == TaskStatus.RUNNING
    assert task.started_at is not None


@pytest.mark.asyncio
async def test_mark_completed(task_queue):
    """Test marking task as completed."""
    await task_queue.enqueue("test-003", "Feature", "https://app.dev")

    workflow_state = {"phase": "COMPLETE"}
    result = {"test_path": "tests/e2e/test.py"}

    await task_queue.mark_completed("test-003", workflow_state, result)

    task = await task_queue.get_task("test-003")
    assert task.status == TaskStatus.COMPLETED
    assert task.workflow_state == workflow_state
    assert task.result == result
    assert task.completed_at is not None


@pytest.mark.asyncio
async def test_mark_failed(task_queue):
    """Test marking task as failed."""
    await task_queue.enqueue("test-004", "Feature", "https://app.dev")

    workflow_state = {"phase": "CODE_IMPLEMENTATION"}
    error = "Code generation failed"

    await task_queue.mark_failed("test-004", workflow_state, error)

    task = await task_queue.get_task("test-004")
    assert task.status == TaskStatus.FAILED
    assert task.error == error
    assert task.completed_at is not None


@pytest.mark.asyncio
async def test_count_by_status(task_queue):
    """Test counting tasks by status."""
    await task_queue.enqueue("task-1", "Feature 1", "https://app.dev")
    await task_queue.enqueue("task-2", "Feature 2", "https://app.dev")
    await task_queue.enqueue("task-3", "Feature 3", "https://app.dev")

    await task_queue.mark_running("task-1")
    await task_queue.mark_completed("task-2", {}, {})

    queued_count = await task_queue.count_by_status(TaskStatus.QUEUED)
    running_count = await task_queue.count_by_status(TaskStatus.RUNNING)
    completed_count = await task_queue.count_by_status(TaskStatus.COMPLETED)

    assert queued_count == 1
    assert running_count == 1
    assert completed_count == 1
