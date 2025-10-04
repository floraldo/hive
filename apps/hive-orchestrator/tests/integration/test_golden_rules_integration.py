"""Integration Tests for Golden Rules Worker Fleet

Tests end-to-end Golden Rules processing:
- Task creation and enqueueing
- Worker registration with pool
- Task assignment and processing
- Auto-fix workflow integration
- Escalation workflow integration
- Worker pool health monitoring
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from hive_orchestrator.golden_rules_worker import GoldenRulesWorkerCore
from hive_orchestrator.task_queue import TaskPriority, TaskQueueManager, create_golden_rules_task
from hive_orchestrator.worker_pool import WorkerPoolManager


class TestGoldenRulesFleetIntegration:
    """Integration test suite for Golden Rules Worker Fleet"""

    @pytest.fixture
    def worker_pool(self):
        """Create worker pool manager"""
        with patch("hive_orchestrator.worker_pool.get_async_event_bus", return_value=AsyncMock()):
            pool = WorkerPoolManager(min_workers=1, max_workers=5, target_queue_per_worker=5)
            pool.event_bus = AsyncMock()
            pool.event_bus.publish = AsyncMock()
            return pool

    @pytest.fixture
    def task_queue(self):
        """Create task queue manager"""
        with patch("hive_orchestrator.task_queue.get_async_event_bus", return_value=AsyncMock()):
            queue = TaskQueueManager()
            queue.event_bus = AsyncMock()
            queue.event_bus.publish = AsyncMock()
            return queue

    @pytest.fixture
    def golden_rules_worker(self, tmp_path):
        """Create Golden Rules worker instance"""
        with patch("hive_orchestrator.qa_worker.get_async_event_bus", return_value=AsyncMock()):
            worker = GoldenRulesWorkerCore(
                worker_id="gr-integration-test-1",
                workspace=tmp_path,
                config={"database": {"path": ":memory:"}},
            )
            worker.event_bus = AsyncMock()
            worker.event_bus.publish = AsyncMock()
            return worker

    @pytest.mark.asyncio
    async def test_worker_registration_with_pool(self, golden_rules_worker, worker_pool):
        """Test worker registers successfully with pool"""
        success = await golden_rules_worker.register_with_pool(worker_pool)

        assert success is True
        assert worker_pool.pool_size == 1
        assert "gr-integration-test-1" in worker_pool._workers

        worker_info = worker_pool._workers["gr-integration-test-1"]
        assert worker_info.worker_type == "golden_rules"
        assert worker_info.metadata["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_heartbeat_updates_pool(self, golden_rules_worker, worker_pool):
        """Test worker heartbeats update pool manager"""
        # Register first
        await golden_rules_worker.register_with_pool(worker_pool)

        # Emit heartbeat
        golden_rules_worker.tasks_completed = 5
        golden_rules_worker.violations_fixed = 20
        golden_rules_worker.escalations = 1

        await golden_rules_worker.emit_heartbeat(pool_manager=worker_pool)

        # Verify pool updated
        worker_info = worker_pool._workers["gr-integration-test-1"]
        assert worker_info.tasks_completed == 5
        assert worker_info.violations_fixed == 20
        assert worker_info.escalations == 1
        assert worker_info.is_healthy is True

    @pytest.mark.asyncio
    async def test_task_creation_and_enqueueing(self, task_queue):
        """Test Golden Rules task factory and enqueueing"""
        # Create task
        task = create_golden_rules_task(
            file_paths=["packages/test/pyproject.toml"],
            severity_level="ERROR",
        )

        assert task.task_type == "qa_golden_rules"
        assert task.metadata["qa_type"] == "golden_rules"
        assert task.metadata["worker_type"] == "golden_rules"
        assert task.metadata["severity_level"] == "ERROR"

        # Enqueue task
        task_id = await task_queue.enqueue(task, TaskPriority.NORMAL)

        assert task_id == task.id
        assert task_queue.queue_depth == 1

    @pytest.mark.asyncio
    async def test_task_assignment_to_worker(self, task_queue, worker_pool, golden_rules_worker):
        """Test task assignment from queue to registered worker"""
        # Register worker
        await golden_rules_worker.register_with_pool(worker_pool)

        # Emit heartbeat to make worker available (sets status to IDLE)
        await golden_rules_worker.emit_heartbeat(pool_manager=worker_pool)

        # Create and enqueue task
        task = create_golden_rules_task(file_paths=["test.py"])
        await task_queue.enqueue(task, TaskPriority.HIGH)

        # Get available worker from pool
        available_worker = await worker_pool.get_available_worker(worker_type="golden_rules")
        assert available_worker == "gr-integration-test-1"

        # Dequeue task for worker
        queued_task = await task_queue.dequeue(available_worker)

        assert queued_task is not None
        assert queued_task.task.id == task.id
        assert queued_task.assigned_worker == "gr-integration-test-1"

    @pytest.mark.asyncio
    async def test_end_to_end_auto_fix_workflow(
        self, task_queue, worker_pool, golden_rules_worker, tmp_path,
    ):
        """Test complete auto-fix workflow from queue to completion"""
        # Setup: Create pyproject.toml with violations
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.poetry]
name = "test-package"

[tool.poetry.dependencies]
requests = "^2.31.0"
""",
        )

        # Register worker
        await golden_rules_worker.register_with_pool(worker_pool)

        # Create and enqueue task
        task = create_golden_rules_task(
            file_paths=[str(pyproject)],
            severity_level="WARNING",
        )
        await task_queue.enqueue(task, TaskPriority.NORMAL)

        # Worker gets task
        queued_task = await task_queue.dequeue("gr-integration-test-1")
        await task_queue.mark_in_progress(queued_task.task.id)

        # Worker processes task (with mocked auto-fix violations)
        # Mock violations that are auto-fixable (rules 31, 32)
        mock_violations = [
            {
                "rule_id": "31",
                "rule_name": "Ruff Config Consistency",
                "file": str(pyproject),
                "message": f"{pyproject}: Missing [tool.ruff]",
                "severity": "WARNING",
                "can_autofix": True,
            },
            {
                "rule_id": "32",
                "rule_name": "Python Version Specification",
                "file": str(pyproject),
                "message": f"{pyproject}: Missing python version",
                "severity": "INFO",
                "can_autofix": True,
            },
        ]

        with patch.object(golden_rules_worker, "detect_golden_rules_violations") as mock_detect:
            mock_detect.return_value = {
                "violations": mock_violations,
                "total_count": 2,
                "auto_fixable_count": 2,
                "escalation_count": 0,
            }

            result = await golden_rules_worker.process_golden_rules_task(queued_task.task)

        # Verify task completed successfully with auto-fixes
        assert result["status"] == "success"
        assert result["violations_fixed"] == 2

        # Mark task completed
        await task_queue.mark_completed(queued_task.task.id, result)

        # Verify queue state
        assert task_queue.queue_depth == 0
        assert task_queue._total_completed == 1

        # Verify worker metrics updated
        assert golden_rules_worker.tasks_completed == 1
        assert golden_rules_worker.violations_fixed >= 2

    @pytest.mark.asyncio
    async def test_end_to_end_escalation_workflow(
        self, task_queue, worker_pool, golden_rules_worker, tmp_path,
    ):
        """Test complete escalation workflow for complex rules"""
        # Setup: Create file with complex violation
        config_file = tmp_path / "config.py"
        config_file.write_text("import os\n\nDB_PATH = os.getenv('DB_PATH')")

        # Register worker
        await golden_rules_worker.register_with_pool(worker_pool)

        # Create and enqueue task
        task = create_golden_rules_task(file_paths=[str(config_file)])
        await task_queue.enqueue(task, TaskPriority.HIGH)

        # Worker gets task
        queued_task = await task_queue.dequeue("gr-integration-test-1")
        await task_queue.mark_in_progress(queued_task.task.id)

        # Mock complex rule violation (requires escalation - not auto-fixable)
        mock_violations = [
            {
                "rule_id": "15",  # Unified Config Enforcement - NOT auto-fixable
                "rule_name": "Unified Config Enforcement",
                "file": str(config_file),
                "message": f"{config_file}: Direct os.getenv() usage",
                "severity": "ERROR",
                "can_autofix": False,
            },
        ]

        with patch.object(golden_rules_worker, "detect_golden_rules_violations") as mock_detect:
            mock_detect.return_value = {
                "violations": mock_violations,
                "total_count": 1,
                "auto_fixable_count": 0,
                "escalation_count": 1,
            }

            result = await golden_rules_worker.process_golden_rules_task(queued_task.task)

        # Verify escalation occurred
        assert result["status"] == "escalated"
        assert len(result["escalations"]) == 1

        # Mark task completed with escalations
        await task_queue.mark_completed(queued_task.task.id, result)

        # Verify worker escalation metrics
        assert golden_rules_worker.escalations == 1

    @pytest.mark.asyncio
    async def test_worker_pool_health_monitoring(self, worker_pool, golden_rules_worker):
        """Test worker pool health monitoring and offline detection"""
        # Register worker
        await golden_rules_worker.register_with_pool(worker_pool)

        # Emit heartbeat (worker is healthy)
        await golden_rules_worker.emit_heartbeat(pool_manager=worker_pool)

        # Check health
        offline_workers = await worker_pool.check_worker_health()
        assert "gr-integration-test-1" not in offline_workers

        # Simulate stale heartbeat (worker unhealthy)
        worker_info = worker_pool._workers["gr-integration-test-1"]
        from datetime import timedelta
        worker_info.last_heartbeat = datetime.now(UTC) - timedelta(seconds=35)

        # Check health again
        offline_workers = await worker_pool.check_worker_health()
        assert "gr-integration-test-1" in offline_workers

    @pytest.mark.asyncio
    async def test_worker_pool_auto_scaling(self, task_queue, worker_pool):
        """Test worker pool auto-scaling decisions based on queue depth"""
        # Enqueue multiple high-priority tasks
        for i in range(15):
            task = create_golden_rules_task(
                file_paths=[f"test{i}.py"],
                severity_level="ERROR",
            )
            await task_queue.enqueue(task, TaskPriority.HIGH)

        # Calculate scaling decision
        action, count = await worker_pool.calculate_scaling_decision(
            queue_depth=task_queue.queue_depth,
        )

        # Should scale up (queue depth 15, capacity 0 → high utilization)
        assert action == "scale_up"
        assert count > 0

    @pytest.mark.asyncio
    async def test_task_priority_ordering(self, task_queue):
        """Test high-priority tasks are processed before normal/low priority"""
        # Enqueue tasks in mixed order
        task_low = create_golden_rules_task(file_paths=["low.py"])
        task_normal = create_golden_rules_task(file_paths=["normal.py"])
        task_high = create_golden_rules_task(file_paths=["high.py"])

        await task_queue.enqueue(task_low, TaskPriority.LOW)
        await task_queue.enqueue(task_normal, TaskPriority.NORMAL)
        await task_queue.enqueue(task_high, TaskPriority.HIGH)

        # Dequeue - should get high priority first
        first_task = await task_queue.dequeue("worker-1")
        assert first_task.task.id == task_high.id

        second_task = await task_queue.dequeue("worker-2")
        assert second_task.task.id == task_normal.id

        third_task = await task_queue.dequeue("worker-3")
        assert third_task.task.id == task_low.id

    @pytest.mark.asyncio
    async def test_worker_pool_metrics(self, worker_pool, golden_rules_worker):
        """Test worker pool metrics collection"""
        # Register worker
        await golden_rules_worker.register_with_pool(worker_pool)

        # Update worker stats
        golden_rules_worker.tasks_completed = 10
        golden_rules_worker.violations_fixed = 50
        golden_rules_worker.escalations = 2

        await golden_rules_worker.emit_heartbeat(pool_manager=worker_pool)

        # Get pool metrics
        metrics = await worker_pool.get_metrics()

        assert metrics["pool_size"] == 1
        assert metrics["active_workers"] == 1
        assert metrics["total_tasks_completed"] == 10
        assert metrics["total_violations_fixed"] == 50
        assert metrics["total_escalations"] == 2
        assert "worker_details" in metrics
