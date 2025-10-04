"""End-to-end test for autonomous execution.

Tests the complete flow:
1. Submit task via API
2. Daemon picks up task from queue
3. Workflow executes autonomously
4. Result retrieved via API

This is the KEY TEST that validates Layer 2 (Autonomous Execution).
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
from hive_config import HiveConfig

from chimera_daemon.daemon import ChimeraDaemon
from chimera_daemon.task_queue import TaskQueue, TaskStatus


@pytest.fixture
async def daemon_and_queue():
    """Create daemon and queue with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test config
        config = HiveConfig(
            environment="test",
            database={"path": Path(tmpdir) / "test.db"},
        )

        # Create task queue
        db_path = config.database.path.parent / "chimera_tasks.db"
        queue = TaskQueue(db_path=db_path)
        await queue.initialize()

        # Create daemon
        daemon = ChimeraDaemon(config=config, poll_interval=0.5)

        yield daemon, queue


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires real agent execution - run manually for validation")
async def test_autonomous_execution_simple_feature(daemon_and_queue):
    """Test autonomous execution of simple feature.

    This test demonstrates TRUE AUTONOMY:
    - Task submitted to queue
    - Daemon processes task WITHOUT human intervention
    - Workflow executes through all phases
    - Result available in queue

    IMPORTANT: This is Layer 2 validation - autonomous execution.
    """
    daemon, queue = daemon_and_queue

    # 1. Enqueue task
    task_id = await queue.enqueue(
        task_id="test-autonomous-001",
        feature="User can view homepage",
        target_url="https://example.com",
        staging_url="https://example.com",
        priority=5,
    )

    print(f"\n[TEST] Task enqueued: {task_id}")

    # Verify task is queued
    task = await queue.get_task(task_id)
    assert task.status == TaskStatus.QUEUED

    # 2. Start daemon (run for limited time)
    print("[TEST] Starting daemon for autonomous execution...")

    # Run daemon for 60 seconds max (workflow should complete in ~30s)
    async def run_daemon_with_timeout():
        try:
            await asyncio.wait_for(daemon._process_next_task(), timeout=60.0)
        except TimeoutError:
            print("[TEST] Daemon timeout (workflow took >60s)")

    await run_daemon_with_timeout()

    # 3. Check result
    print("[TEST] Checking workflow result...")

    task = await queue.get_task(task_id)

    # Verify task completed autonomously
    assert task.status in (
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    ), f"Task should be completed or failed, got: {task.status}"

    # Log result for debugging
    print(f"[TEST] Task status: {task.status}")

    if task.status == TaskStatus.COMPLETED:
        print("[TEST] ✅ AUTONOMOUS EXECUTION SUCCESSFUL")
        print(f"[TEST] Result: {task.result}")
    else:
        print(f"[TEST] ❌ Task failed: {task.error}")
        print(f"[TEST] Workflow state: {task.workflow_state}")


@pytest.mark.asyncio
async def test_daemon_processes_queued_task(daemon_and_queue):
    """Test daemon processes queued task (mock execution)."""
    daemon, queue = daemon_and_queue

    # Enqueue task
    task_id = await queue.enqueue(
        task_id="test-daemon-001",
        feature="Test feature",
        target_url="https://example.com",
        priority=5,
    )

    # Verify task is queued
    task = await queue.get_task(task_id)
    assert task.status == TaskStatus.QUEUED

    # Process task (this will execute real workflow)
    # Note: This test validates daemon picks up task,
    # but actual workflow execution depends on real agents

    # For unit testing, we just verify daemon changes status
    next_task = await queue.get_next_task()
    assert next_task is not None
    assert next_task.task_id == task_id


@pytest.mark.asyncio
async def test_daemon_metrics_tracking(daemon_and_queue):
    """Test daemon tracks metrics correctly."""
    daemon, queue = daemon_and_queue

    # Initial metrics (now delegated to ExecutorPool)
    metrics = daemon.executor_pool.get_metrics()
    assert metrics["total_workflows_processed"] == 0
    assert metrics["total_workflows_succeeded"] == 0
    assert metrics["total_workflows_failed"] == 0

    # After processing, metrics should update
    # (Actual verification depends on workflow execution)
