"""Unit Tests for TaskQueueManager

Tests priority-based task scheduling:
- Task enqueue/dequeue with priorities
- Worker assignment and load balancing
- Task timeout and retry management
- Queue metrics and monitoring
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from hive_orchestration.models.task import Task
from hive_orchestrator.task_queue import QueuedTask, TaskPriority, TaskQueueManager, TaskQueueStatus


class TestQueuedTask:
    """Test suite for QueuedTask dataclass"""

    def test_queued_task_initialization(self):
        """Test QueuedTask initializes with defaults"""
        task = Task(id="test-123", title="Test Task", description="Test")
        queued_task = QueuedTask(task=task)

        assert queued_task.task == task
        assert queued_task.priority == TaskPriority.NORMAL
        assert queued_task.status == TaskQueueStatus.QUEUED
        assert queued_task.assigned_worker is None
        assert queued_task.retry_count == 0
        assert queued_task.max_retries == 3

    def test_age_seconds_property(self):
        """Test age_seconds calculates correctly"""
        task = Task(id="test-123", title="Test", description="Test")
        queued_at = datetime.now(UTC) - timedelta(seconds=10)
        queued_task = QueuedTask(task=task, queued_at=queued_at)

        age = queued_task.age_seconds
        assert 9 < age < 11  # Should be ~10 seconds

    def test_is_timeout_property(self):
        """Test timeout detection"""
        task = Task(id="test-123", title="Test", description="Test")
        started_at = datetime.now(UTC) - timedelta(seconds=70)
        queued_task = QueuedTask(
            task=task, started_at=started_at, timeout_seconds=60,
        )

        assert queued_task.is_timeout is True

        # Not timed out
        started_at_recent = datetime.now(UTC) - timedelta(seconds=30)
        queued_task.started_at = started_at_recent
        assert queued_task.is_timeout is False

    def test_can_retry_property(self):
        """Test retry check"""
        task = Task(id="test-123", title="Test", description="Test")
        queued_task = QueuedTask(task=task, max_retries=3)

        assert queued_task.can_retry is True

        queued_task.retry_count = 3
        assert queued_task.can_retry is False


class TestTaskQueueManager:
    """Test suite for TaskQueueManager"""

    @pytest.fixture
    def queue_manager(self):
        """Create task queue manager instance"""
        return TaskQueueManager()

    @pytest.fixture
    def sample_task(self):
        """Create sample task"""
        return Task(
            id="task-123",
            title="Fix ruff violations",
            description="Auto-fix ruff violations in test.py",
            metadata={"qa_type": "ruff", "file_paths": ["test.py"]},
        )

    @pytest.mark.asyncio
    async def test_enqueue_task(self, queue_manager, sample_task):
        """Test task enqueueing"""
        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            task_id = await queue_manager.enqueue(sample_task, TaskPriority.NORMAL)

            assert task_id == "task-123"
            assert queue_manager.queue_depth == 1
            assert queue_manager._total_queued == 1

    @pytest.mark.asyncio
    async def test_enqueue_with_different_priorities(self, queue_manager):
        """Test tasks enqueue with different priorities"""
        tasks = [
            Task(id=f"task-{i}", title=f"Task {i}", description=f"Task {i}")
            for i in range(3)
        ]

        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            await queue_manager.enqueue(tasks[0], TaskPriority.LOW)
            await queue_manager.enqueue(tasks[1], TaskPriority.NORMAL)
            await queue_manager.enqueue(tasks[2], TaskPriority.HIGH)

            assert queue_manager.queue_depth == 3
            assert queue_manager.queue_depths_by_priority["high"] == 1
            assert queue_manager.queue_depths_by_priority["normal"] == 1
            assert queue_manager.queue_depths_by_priority["low"] == 1

    @pytest.mark.asyncio
    async def test_dequeue_respects_priority(self, queue_manager):
        """Test dequeue returns highest priority task first"""
        tasks = [
            Task(id="task-low", title="Low", description="Low"),
            Task(id="task-normal", title="Normal", description="Normal"),
            Task(id="task-high", title="High", description="High"),
        ]

        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            # Enqueue in reverse priority order
            await queue_manager.enqueue(tasks[0], TaskPriority.LOW)
            await queue_manager.enqueue(tasks[1], TaskPriority.NORMAL)
            await queue_manager.enqueue(tasks[2], TaskPriority.HIGH)

            # Dequeue should return HIGH first
            queued_task = await queue_manager.dequeue("worker-1")
            assert queued_task.task.id == "task-high"
            assert queued_task.assigned_worker == "worker-1"
            assert queued_task.status == TaskQueueStatus.ASSIGNED

    @pytest.mark.asyncio
    async def test_dequeue_empty_queue(self, queue_manager):
        """Test dequeue returns None when queue is empty"""
        queued_task = await queue_manager.dequeue("worker-1")
        assert queued_task is None

    @pytest.mark.asyncio
    async def test_mark_in_progress(self, queue_manager, sample_task):
        """Test marking task as in progress"""
        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            await queue_manager.enqueue(sample_task)
            await queue_manager.dequeue("worker-1")

            success = await queue_manager.mark_in_progress(sample_task.id)

            assert success is True
            queued_task = queue_manager._tasks[sample_task.id]
            assert queued_task.status == TaskQueueStatus.IN_PROGRESS
            assert queued_task.started_at is not None

    @pytest.mark.asyncio
    async def test_mark_completed(self, queue_manager, sample_task):
        """Test marking task as completed"""
        result = {"status": "success", "violations_fixed": 5}

        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            await queue_manager.enqueue(sample_task)
            await queue_manager.dequeue("worker-1")
            await queue_manager.mark_in_progress(sample_task.id)

            success = await queue_manager.mark_completed(sample_task.id, result)

            assert success is True
            assert queue_manager._total_completed == 1
            queued_task = queue_manager._tasks[sample_task.id]
            assert queued_task.status == TaskQueueStatus.COMPLETED
            assert queued_task.metadata["result"] == result

    @pytest.mark.asyncio
    async def test_mark_failed_with_retry(self, queue_manager, sample_task):
        """Test marking task as failed with retry"""
        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            await queue_manager.enqueue(sample_task, TaskPriority.NORMAL)
            await queue_manager.dequeue("worker-1")
            await queue_manager.mark_in_progress(sample_task.id)

            success = await queue_manager.mark_failed(
                sample_task.id, "Test error", retry=True,
            )

            assert success is True
            queued_task = queue_manager._tasks[sample_task.id]
            assert queued_task.retry_count == 1
            assert queued_task.status == TaskQueueStatus.QUEUED
            # Should be re-queued with higher priority
            assert queue_manager.queue_depths_by_priority["high"] == 1

    @pytest.mark.asyncio
    async def test_mark_failed_no_retry(self, queue_manager, sample_task):
        """Test marking task as permanently failed"""
        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            await queue_manager.enqueue(sample_task)
            await queue_manager.dequeue("worker-1")
            await queue_manager.mark_in_progress(sample_task.id)

            success = await queue_manager.mark_failed(
                sample_task.id, "Test error", retry=False,
            )

            assert success is True
            assert queue_manager._total_failed == 1
            queued_task = queue_manager._tasks[sample_task.id]
            assert queued_task.status == TaskQueueStatus.FAILED

    @pytest.mark.asyncio
    async def test_mark_failed_max_retries_exceeded(self, queue_manager, sample_task):
        """Test task fails permanently after max retries"""
        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            await queue_manager.enqueue(sample_task)

            # Fail 3 times (max_retries)
            for i in range(3):
                await queue_manager.dequeue("worker-1")
                await queue_manager.mark_in_progress(sample_task.id)
                await queue_manager.mark_failed(sample_task.id, f"Error {i}", retry=True)

            # 4th failure should be permanent
            await queue_manager.dequeue("worker-1")
            await queue_manager.mark_in_progress(sample_task.id)
            await queue_manager.mark_failed(sample_task.id, "Final error", retry=True)

            queued_task = queue_manager._tasks[sample_task.id]
            assert queued_task.status == TaskQueueStatus.FAILED
            assert queue_manager._total_failed == 1

    @pytest.mark.asyncio
    async def test_check_timeouts(self, queue_manager, sample_task):
        """Test timeout detection"""
        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            await queue_manager.enqueue(sample_task, timeout_seconds=1)
            await queue_manager.dequeue("worker-1")
            await queue_manager.mark_in_progress(sample_task.id)

            # Simulate timeout by setting started_at in the past
            queued_task = queue_manager._tasks[sample_task.id]
            queued_task.started_at = datetime.now(UTC) - timedelta(seconds=5)

            timed_out = await queue_manager.check_timeouts()

            assert sample_task.id in timed_out
            assert queue_manager._total_timeout == 1

    @pytest.mark.asyncio
    async def test_get_task_status(self, queue_manager, sample_task):
        """Test getting task status"""
        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            await queue_manager.enqueue(sample_task)

            status = await queue_manager.get_task_status(sample_task.id)

            assert status is not None
            assert status["task_id"] == sample_task.id
            assert status["status"] == TaskQueueStatus.QUEUED
            assert status["priority"] == TaskPriority.NORMAL

    @pytest.mark.asyncio
    async def test_get_worker_load(self, queue_manager):
        """Test getting worker load"""
        tasks = [Task(id=f"task-{i}", title=f"Task {i}", description="Test") for i in range(3)]

        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            for task in tasks:
                await queue_manager.enqueue(task)
                await queue_manager.dequeue("worker-1")

            load = await queue_manager.get_worker_load("worker-1")
            assert load == 3

    @pytest.mark.asyncio
    async def test_get_metrics(self, queue_manager):
        """Test queue metrics calculation"""
        tasks = [Task(id=f"task-{i}", title=f"Task {i}", description="Test") for i in range(5)]

        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            # Enqueue and complete some tasks
            for _i, task in enumerate(tasks[:3]):
                await queue_manager.enqueue(task)
                await queue_manager.dequeue("worker-1")
                await queue_manager.mark_in_progress(task.id)
                await queue_manager.mark_completed(task.id, {"status": "success"})

            # Enqueue remaining tasks
            for task in tasks[3:]:
                await queue_manager.enqueue(task)

            metrics = await queue_manager.get_metrics()

            assert metrics["queue_depth"] == 2
            assert metrics["total_queued"] == 5
            assert metrics["total_completed"] == 3
            assert metrics["total_failed"] == 0
            assert "avg_wait_time_seconds" in metrics
            assert "avg_execution_time_seconds" in metrics

    @pytest.mark.asyncio
    async def test_cleanup_old_tasks(self, queue_manager, sample_task):
        """Test cleanup of old completed tasks"""
        with patch.object(queue_manager.event_bus, "publish", new=AsyncMock()):
            await queue_manager.enqueue(sample_task)
            await queue_manager.dequeue("worker-1")
            await queue_manager.mark_in_progress(sample_task.id)
            await queue_manager.mark_completed(sample_task.id, {"status": "success"})

            # Simulate old completion time
            queued_task = queue_manager._tasks[sample_task.id]
            queued_task.completed_at = datetime.now(UTC) - timedelta(hours=25)

            cleaned = await queue_manager.cleanup_old_tasks(max_age_hours=24)

            assert cleaned == 1
            assert sample_task.id not in queue_manager._tasks
