"""
Unit Tests for WorkerPoolManager

Tests worker pool auto-scaling:
- Worker registration and tracking
- Health monitoring and auto-restart
- Auto-scaling decisions
- Load balancing
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from hive_orchestrator.worker_pool import WorkerInfo, WorkerPoolManager, WorkerStatus


class TestWorkerInfo:
    """Test suite for WorkerInfo dataclass"""

    def test_worker_info_initialization(self):
        """Test WorkerInfo initializes with defaults"""
        worker = WorkerInfo(worker_id="test-worker-1", worker_type="qa")

        assert worker.worker_id == "test-worker-1"
        assert worker.worker_type == "qa"
        assert worker.status == WorkerStatus.STARTING
        assert worker.tasks_completed == 0
        assert worker.restart_count == 0
        assert worker.max_restarts == 3

    def test_uptime_seconds_property(self):
        """Test uptime calculation"""
        registered_at = datetime.now(UTC) - timedelta(seconds=100)
        worker = WorkerInfo(
            worker_id="test-1", worker_type="qa", registered_at=registered_at
        )

        uptime = worker.uptime_seconds
        assert 99 < uptime < 101  # Should be ~100 seconds

    def test_is_healthy_property(self):
        """Test health check based on heartbeat"""
        worker = WorkerInfo(worker_id="test-1", worker_type="qa")

        # Recent heartbeat - healthy
        worker.last_heartbeat = datetime.now(UTC)
        assert worker.is_healthy is True

        # Old heartbeat - unhealthy
        worker.last_heartbeat = datetime.now(UTC) - timedelta(seconds=35)
        assert worker.is_healthy is False

    def test_is_available_property(self):
        """Test worker availability"""
        worker = WorkerInfo(worker_id="test-1", worker_type="qa")

        # Idle and healthy - available
        worker.status = WorkerStatus.IDLE
        worker.last_heartbeat = datetime.now(UTC)
        assert worker.is_available is True

        # Working - not available
        worker.status = WorkerStatus.WORKING
        assert worker.is_available is False

        # Idle but unhealthy - not available
        worker.status = WorkerStatus.IDLE
        worker.last_heartbeat = datetime.now(UTC) - timedelta(seconds=35)
        assert worker.is_available is False

    def test_can_restart_property(self):
        """Test restart eligibility"""
        worker = WorkerInfo(worker_id="test-1", worker_type="qa", max_restarts=3)

        assert worker.can_restart is True

        worker.restart_count = 3
        assert worker.can_restart is False


class TestWorkerPoolManager:
    """Test suite for WorkerPoolManager"""

    @pytest.fixture
    def pool_manager(self):
        """Create worker pool manager instance"""
        return WorkerPoolManager(min_workers=1, max_workers=5, target_queue_per_worker=5)

    @pytest.mark.asyncio
    async def test_register_worker(self, pool_manager):
        """Test worker registration"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            success = await pool_manager.register_worker(
                "worker-1", "qa", {"version": "1.0"}
            )

            assert success is True
            assert pool_manager.pool_size == 1
            assert "worker-1" in pool_manager._workers

    @pytest.mark.asyncio
    async def test_register_duplicate_worker(self, pool_manager):
        """Test registering same worker twice"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")
            success = await pool_manager.register_worker("worker-1", "qa")

            assert success is False
            assert pool_manager.pool_size == 1

    @pytest.mark.asyncio
    async def test_update_heartbeat(self, pool_manager):
        """Test worker heartbeat update"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")

            success = await pool_manager.update_heartbeat(
                worker_id="worker-1",
                status="working",
                tasks_completed=5,
                violations_fixed=20,
                escalations=1,
                current_task="task-123",
            )

            assert success is True
            worker = pool_manager._workers["worker-1"]
            assert worker.status == WorkerStatus.WORKING
            assert worker.tasks_completed == 5
            assert worker.violations_fixed == 20
            assert worker.escalations == 1
            assert worker.current_task == "task-123"

    @pytest.mark.asyncio
    async def test_mark_worker_offline(self, pool_manager):
        """Test marking worker offline"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")

            success = await pool_manager.mark_worker_offline("worker-1")

            assert success is True
            worker = pool_manager._workers["worker-1"]
            assert worker.status == WorkerStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_remove_worker(self, pool_manager):
        """Test removing worker from pool"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")

            success = await pool_manager.remove_worker("worker-1")

            assert success is True
            assert pool_manager.pool_size == 0
            assert "worker-1" not in pool_manager._workers

    @pytest.mark.asyncio
    async def test_get_available_worker(self, pool_manager):
        """Test getting available worker"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")
            await pool_manager.update_heartbeat(
                "worker-1", "idle", 0, 0, 0
            )

            worker_id = await pool_manager.get_available_worker()

            assert worker_id == "worker-1"
            worker = pool_manager._workers["worker-1"]
            assert worker.status == WorkerStatus.WORKING

    @pytest.mark.asyncio
    async def test_get_available_worker_none_available(self, pool_manager):
        """Test getting available worker when none available"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")
            await pool_manager.update_heartbeat(
                "worker-1", "working", 0, 0, 0
            )

            worker_id = await pool_manager.get_available_worker()

            assert worker_id is None

    @pytest.mark.asyncio
    async def test_get_available_worker_load_balancing(self, pool_manager):
        """Test load balancing picks worker with fewest tasks"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")
            await pool_manager.register_worker("worker-2", "qa")

            # worker-1 has more tasks
            await pool_manager.update_heartbeat("worker-1", "idle", 10, 50, 0)
            # worker-2 has fewer tasks
            await pool_manager.update_heartbeat("worker-2", "idle", 2, 10, 0)

            worker_id = await pool_manager.get_available_worker()

            # Should pick worker-2 (fewer tasks)
            assert worker_id == "worker-2"

    @pytest.mark.asyncio
    async def test_check_worker_health(self, pool_manager):
        """Test worker health monitoring"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")
            await pool_manager.register_worker("worker-2", "qa")

            # Make worker-1 unhealthy (old heartbeat)
            worker1 = pool_manager._workers["worker-1"]
            worker1.last_heartbeat = datetime.now(UTC) - timedelta(seconds=35)

            # Make worker-2 healthy (recent heartbeat)
            worker2 = pool_manager._workers["worker-2"]
            worker2.last_heartbeat = datetime.now(UTC)

            offline_workers = await pool_manager.check_worker_health()

            assert "worker-1" in offline_workers
            assert "worker-2" not in offline_workers
            assert worker1.status == WorkerStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_restart_worker(self, pool_manager):
        """Test worker restart"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")

            success = await pool_manager.restart_worker("worker-1")

            assert success is True
            worker = pool_manager._workers["worker-1"]
            assert worker.restart_count == 1
            assert worker.status == WorkerStatus.STARTING
            assert pool_manager._restart_count == 1

    @pytest.mark.asyncio
    async def test_restart_worker_max_retries_exceeded(self, pool_manager):
        """Test worker restart fails after max retries"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")

            worker = pool_manager._workers["worker-1"]
            worker.restart_count = 3  # Max retries

            success = await pool_manager.restart_worker("worker-1")

            assert success is False

    @pytest.mark.asyncio
    async def test_calculate_scaling_decision_scale_up(self, pool_manager):
        """Test auto-scaling decision to scale up"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            await pool_manager.register_worker("worker-1", "qa")
            await pool_manager.update_heartbeat("worker-1", "idle", 0, 0, 0)

            # Queue depth of 10, capacity of 5 (1 worker × 5)
            # Utilization = 10/5 = 200% > 80% threshold
            action, count = await pool_manager.calculate_scaling_decision(queue_depth=10)

            assert action == "scale_up"
            assert count > 0

    @pytest.mark.asyncio
    async def test_calculate_scaling_decision_scale_down(self, pool_manager):
        """Test auto-scaling decision to scale down"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            # Register multiple workers
            for i in range(5):
                await pool_manager.register_worker(f"worker-{i}", "qa")
                await pool_manager.update_heartbeat(f"worker-{i}", "idle", 0, 0, 0)

            # Queue depth of 1, capacity of 25 (5 workers × 5)
            # Utilization = 1/25 = 4% < 20% threshold
            action, count = await pool_manager.calculate_scaling_decision(queue_depth=1)

            assert action == "scale_down"
            assert count > 0

    @pytest.mark.asyncio
    async def test_calculate_scaling_decision_no_change(self, pool_manager):
        """Test auto-scaling decision with no change needed"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            # Register 2 workers
            await pool_manager.register_worker("worker-1", "qa")
            await pool_manager.register_worker("worker-2", "qa")
            await pool_manager.update_heartbeat("worker-1", "idle", 0, 0, 0)
            await pool_manager.update_heartbeat("worker-2", "idle", 0, 0, 0)

            # Queue depth of 5, capacity of 10 (2 workers × 5)
            # Utilization = 5/10 = 50% (between 20% and 80% thresholds)
            action, count = await pool_manager.calculate_scaling_decision(queue_depth=5)

            assert action == "no_change"
            assert count == 0

    @pytest.mark.asyncio
    async def test_apply_scaling_decision_scale_up(self, pool_manager):
        """Test applying scale up decision"""
        scaled = await pool_manager.apply_scaling_decision("scale_up", 3, "qa")

        assert scaled == 3
        assert pool_manager._scale_up_count == 3

    @pytest.mark.asyncio
    async def test_apply_scaling_decision_scale_down(self, pool_manager):
        """Test applying scale down decision"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            # Register workers
            for i in range(3):
                await pool_manager.register_worker(f"worker-{i}", "qa")
                await pool_manager.update_heartbeat(f"worker-{i}", "idle", 0, 0, 0)

            scaled = await pool_manager.apply_scaling_decision("scale_down", 2, "qa")

            assert scaled == 2
            assert pool_manager._scale_down_count == 2

            # Check workers marked as stopping
            stopping_workers = [
                w for w in pool_manager._workers.values() if w.status == WorkerStatus.STOPPING
            ]
            assert len(stopping_workers) == 2

    @pytest.mark.asyncio
    async def test_get_metrics(self, pool_manager):
        """Test pool metrics calculation"""
        with patch.object(pool_manager.event_bus, "publish", new=AsyncMock()):
            # Register workers
            await pool_manager.register_worker("worker-1", "qa")
            await pool_manager.register_worker("worker-2", "qa")
            await pool_manager.update_heartbeat("worker-1", "idle", 5, 20, 1)
            await pool_manager.update_heartbeat("worker-2", "working", 3, 15, 0)

            metrics = await pool_manager.get_metrics()

            assert metrics["pool_size"] == 2
            assert metrics["active_workers"] == 2
            assert metrics["total_tasks_completed"] == 8
            assert metrics["total_violations_fixed"] == 35
            assert metrics["total_escalations"] == 1
            assert "status_distribution" in metrics
            assert "type_distribution" in metrics
            assert "worker_details" in metrics
