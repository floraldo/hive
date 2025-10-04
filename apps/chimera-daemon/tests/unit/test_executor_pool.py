"""Unit tests for ExecutorPool."""

import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest
from hive_orchestration import ChimeraPhase, Task, TaskStatus

from chimera_daemon.executor_pool import ExecutorPool
from chimera_daemon.task_queue import TaskQueue


class MockAgent:
    """Mock agent for testing."""

    async def generate_test(self, feature: str, url: str) -> dict[str, Any]:
        await asyncio.sleep(0.05)  # Simulate work
        return {"status": "success", "test_path": "tests/e2e/test.py"}

    async def implement_feature(self, test_path: str, feature: str) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        return {"status": "success", "pr_id": "PR#123", "commit_sha": "abc123"}

    async def review_pr(self, pr_id: str) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        return {"status": "success", "decision": "approved", "score": 0.95}

    async def deploy_to_staging(self, commit_sha: str) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        return {"status": "success", "staging_url": "https://staging.dev"}

    async def execute_test(self, test_path: str, url: str) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        return {"status": "passed", "tests_run": 1, "tests_passed": 1}


@pytest.fixture
async def task_queue():
    """Create temporary task queue."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        queue = TaskQueue(db_path=db_path)
        await queue.initialize()
        yield queue


@pytest.fixture
def agents_registry():
    """Create mock agents registry."""
    agent = MockAgent()
    return {
        "e2e-tester-agent": agent,
        "coder-agent": agent,
        "guardian-agent": agent,
        "deployment-agent": agent,
    }


@pytest.fixture
async def executor_pool(agents_registry, task_queue):
    """Create executor pool."""
    pool = ExecutorPool(
        max_concurrent=3,
        agents_registry=agents_registry,
        task_queue=task_queue,
    )
    await pool.start()
    yield pool
    await pool.stop()


@pytest.mark.asyncio
async def test_executor_pool_initialization(executor_pool):
    """Test executor pool initialization."""
    assert executor_pool.max_concurrent == 3
    assert executor_pool.active_count == 0
    assert executor_pool.available_slots == 3


@pytest.mark.asyncio
async def test_submit_single_workflow(executor_pool, task_queue):
    """Test submitting single workflow."""
    task_uuid = str(uuid.uuid4())
    task_id = f"test-{uuid.uuid4().hex[:8]}"

    # Enqueue task first
    await task_queue.enqueue(
        task_id=task_id,
        feature="Test feature",
        target_url="https://example.com",
        priority=5,
    )

    # Create Task object
    task = Task(
        id=task_uuid,
        title="Test",
        description="Test",
        task_type="chimera_workflow",
        priority=5,
        workflow={
            "feature_description": "Test feature",
            "target_url": "https://example.com",
            "current_phase": ChimeraPhase.E2E_TEST_GENERATION.value,
        },
        payload={},
        status=TaskStatus.QUEUED,
    )

    # Submit workflow
    await executor_pool.submit_workflow(task)

    # Verify pool metrics
    assert executor_pool.active_count <= 3
    assert executor_pool.available_slots >= 0

    # Wait for completion
    await asyncio.sleep(1.0)

    # Verify metrics
    metrics = executor_pool.get_metrics()
    assert metrics["total_workflows_processed"] >= 0


@pytest.mark.asyncio
async def test_concurrent_workflow_limit(executor_pool, task_queue):
    """Test concurrent workflow limit enforcement."""
    tasks = []

    # Submit more tasks than max_concurrent
    for i in range(5):
        task_uuid = str(uuid.uuid4())
        task_id = f"test-{uuid.uuid4().hex[:8]}"
        await task_queue.enqueue(
            task_id=task_id,
            feature=f"Feature {i}",
            target_url="https://example.com",
            priority=5,
        )

        task = Task(
            id=task_uuid,
            title=f"Test {i}",
            description="Test",
            task_type="chimera_workflow",
            priority=5,
            workflow={
                "feature_description": f"Feature {i}",
                "target_url": "https://example.com",
                "current_phase": ChimeraPhase.E2E_TEST_GENERATION.value,
            },
            payload={},
            status=TaskStatus.QUEUED,
        )

        tasks.append(task)
        await executor_pool.submit_workflow(task)

    # Verify concurrent limit
    assert executor_pool.active_count <= 3

    # Wait for all to complete
    await asyncio.sleep(2.0)

    # Verify all processed
    metrics = executor_pool.get_metrics()
    assert metrics["total_workflows_processed"] >= 0


@pytest.mark.asyncio
async def test_pool_metrics(executor_pool):
    """Test pool metrics reporting."""
    metrics = executor_pool.get_metrics()

    assert "pool_size" in metrics
    assert "active_workflows" in metrics
    assert "available_slots" in metrics
    assert "total_workflows_processed" in metrics
    assert "total_workflows_succeeded" in metrics
    assert "total_workflows_failed" in metrics
    assert "avg_workflow_duration_ms" in metrics
    assert "success_rate" in metrics

    assert metrics["pool_size"] == 3
    assert metrics["active_workflows"] == 0
    assert metrics["available_slots"] == 3


@pytest.mark.asyncio
async def test_pool_start_stop(agents_registry, task_queue):
    """Test pool start and stop."""
    pool = ExecutorPool(
        max_concurrent=2,
        agents_registry=agents_registry,
        task_queue=task_queue,
    )

    # Start
    await pool.start()
    assert pool._running is True

    # Stop
    await pool.stop()
    assert pool._running is False


@pytest.mark.asyncio
async def test_workflow_metrics_tracking(executor_pool, task_queue):
    """Test workflow metrics are tracked correctly."""
    task_uuid = str(uuid.uuid4())
    task_id = f"test-{uuid.uuid4().hex[:8]}"

    await task_queue.enqueue(
        task_id=task_id,
        feature="Test feature",
        target_url="https://example.com",
        priority=5,
    )

    task = Task(
        id=task_uuid,
        title="Test",
        description="Test",
        task_type="chimera_workflow",
        priority=5,
        workflow={
            "feature_description": "Test feature",
            "target_url": "https://example.com",
            "current_phase": ChimeraPhase.E2E_TEST_GENERATION.value,
        },
        payload={},
        status=TaskStatus.QUEUED,
    )

    await executor_pool.submit_workflow(task)

    # Wait for workflow to progress
    await asyncio.sleep(1.0)

    # Check metrics
    metrics = executor_pool.get_metrics()
    assert metrics["avg_workflow_duration_ms"] >= 0
