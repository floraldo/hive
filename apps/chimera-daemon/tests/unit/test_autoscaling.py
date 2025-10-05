"""Unit tests for autoscaling and scheduling components."""

from datetime import datetime, timedelta

import pytest

from chimera_daemon.autoscaler import (
    PoolAutoscaler,
    ScalingDirection,
    ScalingPolicy,
)
from chimera_daemon.metrics import PoolMetrics
from chimera_daemon.scheduler import (
    IntelligentScheduler,
    Priority,
    ScheduledTask,
    SchedulingStrategy,
)


class TestIntelligentScheduler:
    """Tests for intelligent task scheduling."""

    @pytest.fixture
    def scheduler(self):
        """Create an IntelligentScheduler instance."""
        return IntelligentScheduler(strategy=SchedulingStrategy.ADAPTIVE)

    def test_add_task(self, scheduler):
        """Test adding a task to the scheduler."""
        task = ScheduledTask(
            task_id="task_1",
            priority=Priority.NORMAL,
            created_at=datetime.now(),
        )

        scheduler.add_task(task)

        assert len(scheduler.get_pending_tasks()) == 1
        assert "NORMAL" in scheduler.get_queue_depths()
        assert scheduler.get_queue_depths()["NORMAL"] == 1

    def test_add_duplicate_task(self, scheduler):
        """Test adding duplicate task is prevented."""
        task = ScheduledTask(
            task_id="task_1",
            priority=Priority.NORMAL,
            created_at=datetime.now(),
        )

        scheduler.add_task(task)
        scheduler.add_task(task)  # Duplicate

        assert len(scheduler.get_pending_tasks()) == 1

    def test_fifo_strategy(self):
        """Test FIFO scheduling strategy."""
        scheduler = IntelligentScheduler(strategy=SchedulingStrategy.FIFO)

        # Add tasks with different priorities and times
        import time

        task1 = ScheduledTask(task_id="task_1", priority=Priority.LOW, created_at=datetime.now())
        scheduler.add_task(task1)

        time.sleep(0.01)

        task2 = ScheduledTask(task_id="task_2", priority=Priority.HIGH, created_at=datetime.now())
        scheduler.add_task(task2)

        # FIFO should return oldest first (task1), regardless of priority
        next_task = scheduler.get_next_task()
        assert next_task.task_id == "task_1"

    def test_priority_strategy(self):
        """Test priority-based scheduling strategy."""
        scheduler = IntelligentScheduler(strategy=SchedulingStrategy.PRIORITY)

        # Add tasks with different priorities
        task_low = ScheduledTask(task_id="task_low", priority=Priority.LOW, created_at=datetime.now())
        task_high = ScheduledTask(
            task_id="task_high", priority=Priority.HIGH, created_at=datetime.now()
        )

        scheduler.add_task(task_low)
        scheduler.add_task(task_high)

        # Priority strategy should return high priority first
        next_task = scheduler.get_next_task()
        assert next_task.task_id == "task_high"

    def test_edf_strategy(self):
        """Test Earliest Deadline First strategy."""
        scheduler = IntelligentScheduler(strategy=SchedulingStrategy.EDF)

        # Add tasks with different deadlines
        now = datetime.now()

        task1 = ScheduledTask(
            task_id="task_1",
            priority=Priority.NORMAL,
            created_at=now,
            deadline=now + timedelta(minutes=10),
        )

        task2 = ScheduledTask(
            task_id="task_2",
            priority=Priority.NORMAL,
            created_at=now,
            deadline=now + timedelta(minutes=5),  # Earlier deadline
        )

        scheduler.add_task(task1)
        scheduler.add_task(task2)

        # EDF should return task with earliest deadline
        next_task = scheduler.get_next_task()
        assert next_task.task_id == "task_2"

    def test_adaptive_strategy_high_load(self):
        """Test adaptive strategy under high load (>80%)."""
        scheduler = IntelligentScheduler(strategy=SchedulingStrategy.ADAPTIVE)

        # Add critical and normal tasks
        task_critical = ScheduledTask(
            task_id="task_critical", priority=Priority.CRITICAL, created_at=datetime.now()
        )
        task_normal = ScheduledTask(
            task_id="task_normal", priority=Priority.NORMAL, created_at=datetime.now()
        )

        scheduler.add_task(task_normal)
        scheduler.add_task(task_critical)

        # Under high load, should prioritize critical
        next_task = scheduler.get_next_task(current_pool_utilization=0.85)
        assert next_task.task_id == "task_critical"

    def test_adaptive_strategy_low_load(self):
        """Test adaptive strategy under low load (<50%)."""
        scheduler = IntelligentScheduler(strategy=SchedulingStrategy.ADAPTIVE)

        # Add tasks with different priorities
        task_low = ScheduledTask(task_id="task_low", priority=Priority.LOW, created_at=datetime.now())
        task_high = ScheduledTask(
            task_id="task_high", priority=Priority.HIGH, created_at=datetime.now()
        )

        scheduler.add_task(task_low)
        scheduler.add_task(task_high)

        # Under low load, use priority-based
        next_task = scheduler.get_next_task(current_pool_utilization=0.3)
        assert next_task.task_id == "task_high"

    def test_starvation_prevention(self):
        """Test low-priority task starvation prevention."""
        scheduler = IntelligentScheduler(
            strategy=SchedulingStrategy.PRIORITY,
            starvation_threshold_seconds=0.1,  # Very short for testing
        )

        # Add old low-priority task
        import time

        task_low = ScheduledTask(
            task_id="task_low",
            priority=Priority.LOW,
            created_at=datetime.now() - timedelta(seconds=1),
        )
        scheduler.add_task(task_low)

        # Wait for starvation threshold
        time.sleep(0.15)

        # Get next task (triggers starvation prevention)
        next_task = scheduler.get_next_task()

        # Task should have been boosted (LOW->NORMAL or higher)
        # Note: May be boosted multiple times if age >> threshold
        assert next_task.priority != Priority.LOW

    def test_remove_task(self, scheduler):
        """Test removing a task from scheduler."""
        task = ScheduledTask(task_id="task_1", priority=Priority.NORMAL, created_at=datetime.now())
        scheduler.add_task(task)

        assert scheduler.remove_task("task_1") is True
        assert len(scheduler.get_pending_tasks()) == 0

        # Removing non-existent task
        assert scheduler.remove_task("nonexistent") is False

    def test_task_properties(self):
        """Test task computed properties."""
        import time

        now = datetime.now()
        task = ScheduledTask(
            task_id="task_1",
            priority=Priority.NORMAL,
            created_at=now,
            deadline=now + timedelta(seconds=5),
        )

        time.sleep(0.01)

        assert task.age_seconds > 0
        assert task.time_to_deadline_seconds is not None
        assert task.time_to_deadline_seconds < 5.0
        assert task.is_overdue is False

        # Test overdue
        overdue_task = ScheduledTask(
            task_id="task_2",
            priority=Priority.NORMAL,
            created_at=now - timedelta(seconds=10),
            deadline=now - timedelta(seconds=5),
        )
        assert overdue_task.is_overdue is True

    def test_get_metrics(self, scheduler):
        """Test scheduler metrics."""
        # Add and complete tasks
        task1 = ScheduledTask(task_id="task_1", priority=Priority.NORMAL, created_at=datetime.now())
        task2 = ScheduledTask(task_id="task_2", priority=Priority.HIGH, created_at=datetime.now())

        scheduler.add_task(task1)
        scheduler.add_task(task2)

        # Get one task
        scheduler.get_next_task()
        scheduler.mark_completed("task_1", missed_deadline=False)

        metrics = scheduler.get_metrics()

        assert metrics["total_scheduled"] == 2
        assert metrics["total_completed"] == 1
        assert metrics["currently_queued"] == 1
        assert "queue_depths" in metrics

    def test_clear_scheduler(self, scheduler):
        """Test clearing all scheduled tasks."""
        for i in range(5):
            task = ScheduledTask(
                task_id=f"task_{i}", priority=Priority.NORMAL, created_at=datetime.now()
            )
            scheduler.add_task(task)

        assert len(scheduler.get_pending_tasks()) == 5

        scheduler.clear()
        assert len(scheduler.get_pending_tasks()) == 0


class TestPoolAutoscaler:
    """Tests for pool autoscaling."""

    @pytest.fixture
    def autoscaler(self):
        """Create a PoolAutoscaler instance."""
        policy = ScalingPolicy(
            min_pool_size=2,
            max_pool_size=10,
            scale_up_threshold=0.85,
            scale_down_threshold=0.5,
            cooldown_seconds=0.1,  # Short cooldown for testing
        )
        return PoolAutoscaler(policy=policy)

    @pytest.fixture
    def base_metrics(self):
        """Create base pool metrics."""
        return PoolMetrics(
            pool_size=5,
            active_workflows=3,
            available_slots=2,
            pool_utilization_pct=60.0,
            peak_utilization_pct=75.0,
            queue_depth=5,
            queue_depth_trend="stable",
            avg_slot_wait_time_ms=500.0,
            total_workflows_processed=100,
            total_workflows_succeeded=95,
            total_workflows_failed=5,
            success_rate=0.95,
            p50_workflow_duration_ms=1000.0,
            p95_workflow_duration_ms=2000.0,
            p99_workflow_duration_ms=3000.0,
            avg_workflow_duration_ms=1500.0,
            failure_rate_by_phase={},
            retry_success_rate=0.95,
            throughput_trend="stable",
            latency_trend="stable",
        )

    def test_scale_up_on_high_utilization(self, autoscaler, base_metrics):
        """Test scaling up when utilization exceeds threshold."""
        base_metrics.pool_utilization_pct = 90.0  # Above 85% threshold

        decision = autoscaler.evaluate_scaling(base_metrics, current_pool_size=5)

        assert decision.direction == ScalingDirection.SCALE_UP
        assert decision.target_size == 7  # 5 + 2 (scale_up_increment)
        assert "utilization" in decision.reason.lower()

    def test_scale_down_on_low_utilization(self, autoscaler, base_metrics):
        """Test scaling down when utilization below threshold."""
        base_metrics.pool_utilization_pct = 40.0  # Below 50% threshold

        decision = autoscaler.evaluate_scaling(base_metrics, current_pool_size=5)

        assert decision.direction == ScalingDirection.SCALE_DOWN
        assert decision.target_size == 4  # 5 - 1 (scale_down_decrement)
        assert "utilization" in decision.reason.lower()

    def test_respect_min_pool_size(self, autoscaler, base_metrics):
        """Test autoscaler respects minimum pool size."""
        base_metrics.pool_utilization_pct = 10.0  # Very low

        decision = autoscaler.evaluate_scaling(base_metrics, current_pool_size=2)

        assert decision.direction == ScalingDirection.MAINTAIN
        assert decision.target_size == 2
        # Accept any maintain decision at min size

    def test_respect_max_pool_size(self, autoscaler, base_metrics):
        """Test autoscaler respects maximum pool size."""
        base_metrics.pool_utilization_pct = 95.0  # Very high

        decision = autoscaler.evaluate_scaling(base_metrics, current_pool_size=10)

        assert decision.direction == ScalingDirection.MAINTAIN
        assert decision.target_size == 10
        # Accept any maintain decision at max size

    def test_scale_up_on_queue_depth(self, autoscaler, base_metrics):
        """Test scaling up based on queue depth."""
        base_metrics.queue_depth = 15  # Above threshold (10)
        base_metrics.queue_depth_trend = "increasing"

        decision = autoscaler.evaluate_scaling(base_metrics, current_pool_size=5)

        assert decision.direction == ScalingDirection.SCALE_UP
        assert decision.triggered_by == "queue_depth"

    def test_scale_up_on_latency_increase(self, autoscaler, base_metrics):
        """Test scaling up based on increasing latency."""
        base_metrics.p50_workflow_duration_ms = 1000.0
        base_metrics.p95_workflow_duration_ms = 3000.0  # 3x P50
        base_metrics.latency_trend = "increasing"

        decision = autoscaler.evaluate_scaling(base_metrics, current_pool_size=5)

        assert decision.direction == ScalingDirection.SCALE_UP
        assert decision.triggered_by == "latency"

    def test_cooldown_period(self, autoscaler, base_metrics):
        """Test cooldown period between scaling actions."""
        import time

        base_metrics.pool_utilization_pct = 90.0

        # First scaling action
        decision1 = autoscaler.evaluate_scaling(base_metrics, current_pool_size=5)
        assert decision1.direction == ScalingDirection.SCALE_UP

        # Immediate second action should be blocked by cooldown
        decision2 = autoscaler.evaluate_scaling(base_metrics, current_pool_size=7)
        assert decision2.direction == ScalingDirection.MAINTAIN
        assert "cooldown" in decision2.reason.lower()

        # Wait for cooldown to expire
        time.sleep(0.15)

        # Should allow scaling again
        decision3 = autoscaler.evaluate_scaling(base_metrics, current_pool_size=7)
        assert decision3.direction == ScalingDirection.SCALE_UP

    def test_scaling_history(self, autoscaler, base_metrics):
        """Test scaling decision history tracking."""
        base_metrics.pool_utilization_pct = 90.0

        # Trigger scaling action
        autoscaler.evaluate_scaling(base_metrics, current_pool_size=5)

        history = autoscaler.get_scaling_history(limit=5)
        assert len(history) == 1
        assert history[0].direction == ScalingDirection.SCALE_UP

    def test_scaling_metrics(self, autoscaler, base_metrics):
        """Test autoscaler metrics."""
        import time

        base_metrics.pool_utilization_pct = 90.0
        autoscaler.evaluate_scaling(base_metrics, current_pool_size=5)

        time.sleep(0.15)  # Wait for cooldown

        base_metrics.pool_utilization_pct = 40.0
        autoscaler.evaluate_scaling(base_metrics, current_pool_size=7)

        metrics = autoscaler.get_scaling_metrics()

        assert metrics["total_scaling_actions"] == 2
        assert metrics["scale_ups"] == 1
        assert metrics["scale_downs"] == 1
        assert "policy" in metrics

    def test_default_policy(self):
        """Test autoscaler with default policy."""
        autoscaler = PoolAutoscaler()

        assert autoscaler.policy.min_pool_size == 2
        assert autoscaler.policy.max_pool_size == 10
        assert autoscaler.policy.target_utilization == 0.7


class TestScheduledTask:
    """Tests for ScheduledTask dataclass."""

    def test_task_creation(self):
        """Test creating a scheduled task."""
        now = datetime.now()
        task = ScheduledTask(
            task_id="task_1",
            priority=Priority.HIGH,
            created_at=now,
            deadline=now + timedelta(minutes=5),
            estimated_duration_ms=3000.0,
            metadata={"feature": "login"},
        )

        assert task.task_id == "task_1"
        assert task.priority == Priority.HIGH
        assert task.metadata["feature"] == "login"

    def test_task_age(self):
        """Test task age calculation."""
        import time

        task = ScheduledTask(
            task_id="task_1",
            priority=Priority.NORMAL,
            created_at=datetime.now(),
        )

        time.sleep(0.05)

        assert task.age_seconds >= 0.05


class TestScalingPolicy:
    """Tests for ScalingPolicy configuration."""

    def test_default_policy(self):
        """Test default scaling policy."""
        policy = ScalingPolicy()

        assert policy.min_pool_size == 2
        assert policy.max_pool_size == 10
        assert policy.target_utilization == 0.7
        assert policy.cooldown_seconds == 60.0

    def test_custom_policy(self):
        """Test custom scaling policy."""
        policy = ScalingPolicy(
            min_pool_size=5,
            max_pool_size=50,
            target_utilization=0.8,
            cooldown_seconds=120.0,
        )

        assert policy.min_pool_size == 5
        assert policy.max_pool_size == 50
        assert policy.target_utilization == 0.8
        assert policy.cooldown_seconds == 120.0
