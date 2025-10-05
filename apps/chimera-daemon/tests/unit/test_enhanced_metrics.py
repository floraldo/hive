"""Unit tests for enhanced metrics system.

Tests MetricsCollector, HealthMonitor, and percentile calculations.
"""

from __future__ import annotations

from chimera_daemon.health import HealthMonitor, HealthStatus, HealthThresholds
from chimera_daemon.metrics import MetricsCollector, PoolMetrics


class TestMetricsCollector:
    """Test MetricsCollector percentile and trend calculations."""

    def test_empty_metrics(self):
        """Test metrics with no workflows recorded."""
        collector = MetricsCollector()
        metrics = collector.get_metrics(pool_size=5, active_workflows=0, queue_depth=0)

        assert metrics.pool_size == 5
        assert metrics.active_workflows == 0
        assert metrics.total_workflows_processed == 0
        assert metrics.p50_workflow_duration_ms == 0.0
        assert metrics.p95_workflow_duration_ms == 0.0
        assert metrics.p99_workflow_duration_ms == 0.0

    def test_single_workflow_metrics(self):
        """Test metrics with single workflow."""
        collector = MetricsCollector()
        collector.record_workflow(
            workflow_id="test-1",
            duration_ms=1000.0,
            success=True,
            phase="COMPLETE",
        )

        metrics = collector.get_metrics(pool_size=5, active_workflows=1, queue_depth=0)

        assert metrics.total_workflows_processed == 1
        assert metrics.total_workflows_succeeded == 1
        assert metrics.success_rate == 100.0
        assert metrics.avg_workflow_duration_ms == 1000.0
        assert metrics.p50_workflow_duration_ms == 1000.0

    def test_percentile_calculations(self):
        """Test P50/P95/P99 percentile calculations."""
        collector = MetricsCollector()

        # Record 100 workflows with durations 1000-100000ms
        for i in range(100):
            collector.record_workflow(
                workflow_id=f"test-{i}",
                duration_ms=float((i + 1) * 1000),
                success=True,
                phase="COMPLETE",
            )

        metrics = collector.get_metrics(pool_size=5, active_workflows=2, queue_depth=0)

        # Verify percentiles are in expected ranges
        assert 45000 <= metrics.p50_workflow_duration_ms <= 55000  # Around 50th percentile
        assert 90000 <= metrics.p95_workflow_duration_ms <= 100000  # Around 95th percentile
        assert 95000 <= metrics.p99_workflow_duration_ms <= 100000  # Around 99th percentile

        # Average should be around middle of range
        assert 45000 <= metrics.avg_workflow_duration_ms <= 55000

    def test_success_rate_calculation(self):
        """Test success rate with mixed successes and failures."""
        collector = MetricsCollector()

        # Record 8 successes and 2 failures
        for i in range(8):
            collector.record_workflow(
                workflow_id=f"success-{i}",
                duration_ms=1000.0,
                success=True,
            )

        for i in range(2):
            collector.record_workflow(
                workflow_id=f"failure-{i}",
                duration_ms=1000.0,
                success=False,
            )

        metrics = collector.get_metrics(pool_size=5, active_workflows=0, queue_depth=0)

        assert metrics.total_workflows_processed == 10
        assert metrics.total_workflows_succeeded == 8
        assert metrics.total_workflows_failed == 2
        assert metrics.success_rate == 80.0

    def test_failure_rate_by_phase(self):
        """Test failure rate analysis by phase."""
        collector = MetricsCollector()

        # E2E_TEST_GENERATION: 8 success, 2 failures (20% failure rate)
        for i in range(8):
            collector.record_workflow(
                workflow_id=f"e2e-success-{i}",
                duration_ms=1000.0,
                success=True,
                phase="E2E_TEST_GENERATION",
            )

        for i in range(2):
            collector.record_workflow(
                workflow_id=f"e2e-failure-{i}",
                duration_ms=1000.0,
                success=False,
                phase="E2E_TEST_GENERATION",
            )

        # CODE_IMPLEMENTATION: 9 success, 1 failure (10% failure rate)
        for i in range(9):
            collector.record_workflow(
                workflow_id=f"code-success-{i}",
                duration_ms=1000.0,
                success=True,
                phase="CODE_IMPLEMENTATION",
            )

        collector.record_workflow(
            workflow_id="code-failure-1",
            duration_ms=1000.0,
            success=False,
            phase="CODE_IMPLEMENTATION",
        )

        metrics = collector.get_metrics(pool_size=5, active_workflows=0, queue_depth=0)

        assert metrics.failure_rate_by_phase["E2E_TEST_GENERATION"] == 20.0
        assert metrics.failure_rate_by_phase["CODE_IMPLEMENTATION"] == 10.0

    def test_queue_depth_trend_detection(self):
        """Test queue depth trend detection (increasing/stable/decreasing)."""
        collector = MetricsCollector()

        # Record increasing queue depths
        for depth in [1, 2, 3, 5, 8, 13, 21, 34, 55, 89]:
            collector.record_queue_depth(depth)

        metrics = collector.get_metrics(pool_size=5, active_workflows=0, queue_depth=89)

        assert metrics.queue_depth_trend == "increasing"

        # Record decreasing queue depths
        collector2 = MetricsCollector()
        for depth in [89, 55, 34, 21, 13, 8, 5, 3, 2, 1]:
            collector2.record_queue_depth(depth)

        metrics2 = collector2.get_metrics(pool_size=5, active_workflows=0, queue_depth=1)

        assert metrics2.queue_depth_trend == "decreasing"

    def test_retry_success_rate(self):
        """Test retry success rate tracking."""
        collector = MetricsCollector()

        # Record 3 workflows that succeeded after retry
        for i in range(3):
            collector.record_workflow(
                workflow_id=f"retry-success-{i}",
                duration_ms=2000.0,
                success=True,
                retry_count=1,
            )

        # Record 1 workflow that failed even after retry
        collector.record_workflow(
            workflow_id="retry-failure",
            duration_ms=1000.0,
            success=False,
            retry_count=1,
        )

        metrics = collector.get_metrics(pool_size=5, active_workflows=0, queue_depth=0)

        # 3 out of 4 retries succeeded = 75%
        assert metrics.retry_success_rate == 75.0

    def test_sliding_window_limit(self):
        """Test that sliding window limits to max size."""
        collector = MetricsCollector(window_size=10)

        # Record 20 workflows (should only keep last 10)
        for i in range(20):
            collector.record_workflow(
                workflow_id=f"test-{i}",
                duration_ms=float((i + 1) * 1000),
                success=True,
            )

        metrics = collector.get_metrics(pool_size=5, active_workflows=0, queue_depth=0)

        # Should only count last 10 workflows in percentile calculations
        # Average of 11000-20000 is 15500
        assert 14500 <= metrics.avg_workflow_duration_ms <= 16500

    def test_peak_utilization_tracking(self):
        """Test peak utilization tracking across multiple measurements."""
        collector = MetricsCollector()

        # Record some workflows and check peak utilization
        collector.record_workflow("test-1", 1000.0, True)
        metrics1 = collector.get_metrics(pool_size=10, active_workflows=8, queue_depth=0)

        assert metrics1.pool_utilization_pct == 80.0
        assert metrics1.peak_utilization_pct == 80.0

        # Check with lower utilization - peak should remain at 80%
        collector.record_workflow("test-2", 1000.0, True)
        metrics2 = collector.get_metrics(pool_size=10, active_workflows=5, queue_depth=0)

        assert metrics2.pool_utilization_pct == 50.0
        assert metrics2.peak_utilization_pct == 80.0  # Peak unchanged

        # Check with higher utilization - peak should update
        collector.record_workflow("test-3", 1000.0, True)
        metrics3 = collector.get_metrics(pool_size=10, active_workflows=9, queue_depth=0)

        assert metrics3.pool_utilization_pct == 90.0
        assert metrics3.peak_utilization_pct == 90.0  # Peak updated


class TestHealthMonitor:
    """Test HealthMonitor threshold-based alerting."""

    def test_healthy_status(self):
        """Test healthy status with all metrics within thresholds."""
        monitor = HealthMonitor()

        # Create metrics with all values healthy
        metrics = PoolMetrics(
            pool_size=5,
            active_workflows=2,
            available_slots=3,
            pool_utilization_pct=40.0,
            peak_utilization_pct=60.0,
            queue_depth=5,
            queue_depth_trend="stable",
            avg_slot_wait_time_ms=0.0,
            total_workflows_processed=100,
            total_workflows_succeeded=95,
            total_workflows_failed=5,
            success_rate=95.0,
            p50_workflow_duration_ms=10000.0,
            p95_workflow_duration_ms=25000.0,
            p99_workflow_duration_ms=35000.0,
            avg_workflow_duration_ms=15000.0,
            failure_rate_by_phase={},
            retry_success_rate=80.0,
            throughput_trend="stable",
            latency_trend="stable",
        )

        report = monitor.assess_health(metrics)

        assert report.status == HealthStatus.HEALTHY
        assert len(report.alerts) == 0
        assert report.metrics_summary["pool_utilization_pct"] == 40.0

    def test_pool_utilization_warning(self):
        """Test warning alert for high pool utilization."""
        monitor = HealthMonitor()

        metrics = PoolMetrics(
            pool_size=5,
            active_workflows=4,
            available_slots=1,
            pool_utilization_pct=85.0,  # Above 80% warning threshold
            peak_utilization_pct=85.0,
            queue_depth=0,
            queue_depth_trend="stable",
            avg_slot_wait_time_ms=0.0,
            total_workflows_processed=100,
            total_workflows_succeeded=95,
            total_workflows_failed=5,
            success_rate=95.0,
            p50_workflow_duration_ms=10000.0,
            p95_workflow_duration_ms=25000.0,
            p99_workflow_duration_ms=35000.0,
            avg_workflow_duration_ms=15000.0,
            failure_rate_by_phase={},
            retry_success_rate=80.0,
            throughput_trend="stable",
            latency_trend="stable",
        )

        report = monitor.assess_health(metrics)

        assert report.status == HealthStatus.WARNING
        assert len(report.alerts) == 1
        assert report.alerts[0].severity == "warning"
        assert report.alerts[0].metric == "pool_utilization"
        assert "consider scaling up" in report.alerts[0].recommendation.lower()

    def test_pool_utilization_critical(self):
        """Test critical alert for very high pool utilization."""
        monitor = HealthMonitor()

        metrics = PoolMetrics(
            pool_size=5,
            active_workflows=5,
            available_slots=0,
            pool_utilization_pct=100.0,  # Above 95% critical threshold
            peak_utilization_pct=100.0,
            queue_depth=0,
            queue_depth_trend="stable",
            avg_slot_wait_time_ms=0.0,
            total_workflows_processed=100,
            total_workflows_succeeded=95,
            total_workflows_failed=5,
            success_rate=95.0,
            p50_workflow_duration_ms=10000.0,
            p95_workflow_duration_ms=25000.0,
            p99_workflow_duration_ms=35000.0,
            avg_workflow_duration_ms=15000.0,
            failure_rate_by_phase={},
            retry_success_rate=80.0,
            throughput_trend="stable",
            latency_trend="stable",
        )

        report = monitor.assess_health(metrics)

        assert report.status == HealthStatus.CRITICAL
        assert len(report.alerts) == 1
        assert report.alerts[0].severity == "critical"
        assert report.alerts[0].metric == "pool_utilization"

    def test_low_success_rate_alert(self):
        """Test alert for low success rate."""
        monitor = HealthMonitor()

        metrics = PoolMetrics(
            pool_size=5,
            active_workflows=2,
            available_slots=3,
            pool_utilization_pct=40.0,
            peak_utilization_pct=60.0,
            queue_depth=0,
            queue_depth_trend="stable",
            avg_slot_wait_time_ms=0.0,
            total_workflows_processed=100,
            total_workflows_succeeded=70,
            total_workflows_failed=30,
            success_rate=70.0,  # Below 75% critical threshold
            p50_workflow_duration_ms=10000.0,
            p95_workflow_duration_ms=25000.0,
            p99_workflow_duration_ms=35000.0,
            avg_workflow_duration_ms=15000.0,
            failure_rate_by_phase={},
            retry_success_rate=50.0,
            throughput_trend="stable",
            latency_trend="stable",
        )

        report = monitor.assess_health(metrics)

        assert report.status == HealthStatus.CRITICAL
        success_rate_alerts = [a for a in report.alerts if a.metric == "success_rate"]
        assert len(success_rate_alerts) == 1
        assert success_rate_alerts[0].severity == "critical"

    def test_high_latency_alert(self):
        """Test alert for high P95 latency."""
        monitor = HealthMonitor()

        metrics = PoolMetrics(
            pool_size=5,
            active_workflows=2,
            available_slots=3,
            pool_utilization_pct=40.0,
            peak_utilization_pct=60.0,
            queue_depth=0,
            queue_depth_trend="stable",
            avg_slot_wait_time_ms=0.0,
            total_workflows_processed=100,
            total_workflows_succeeded=95,
            total_workflows_failed=5,
            success_rate=95.0,
            p50_workflow_duration_ms=30000.0,
            p95_workflow_duration_ms=150000.0,  # Above 120s critical threshold
            p99_workflow_duration_ms=180000.0,
            avg_workflow_duration_ms=45000.0,
            failure_rate_by_phase={},
            retry_success_rate=80.0,
            throughput_trend="stable",
            latency_trend="degrading",
        )

        report = monitor.assess_health(metrics)

        assert report.status == HealthStatus.CRITICAL
        latency_alerts = [a for a in report.alerts if a.metric == "p95_latency"]
        assert len(latency_alerts) == 1
        assert latency_alerts[0].severity == "critical"

    def test_queue_depth_increasing_trend_alert(self):
        """Test alert for increasing queue depth trend."""
        monitor = HealthMonitor()

        metrics = PoolMetrics(
            pool_size=5,
            active_workflows=2,
            available_slots=3,
            pool_utilization_pct=40.0,
            peak_utilization_pct=60.0,
            queue_depth=12,  # Above 10 warning threshold
            queue_depth_trend="increasing",  # Triggers alert only if increasing
            avg_slot_wait_time_ms=0.0,
            total_workflows_processed=100,
            total_workflows_succeeded=95,
            total_workflows_failed=5,
            success_rate=95.0,
            p50_workflow_duration_ms=10000.0,
            p95_workflow_duration_ms=25000.0,
            p99_workflow_duration_ms=35000.0,
            avg_workflow_duration_ms=15000.0,
            failure_rate_by_phase={},
            retry_success_rate=80.0,
            throughput_trend="stable",
            latency_trend="stable",
        )

        report = monitor.assess_health(metrics)

        assert report.status == HealthStatus.WARNING
        queue_alerts = [a for a in report.alerts if a.metric == "queue_depth"]
        assert len(queue_alerts) == 1
        assert "increasing" in queue_alerts[0].message.lower()

    def test_failure_rate_by_phase_alert(self):
        """Test alert for high failure rate in specific phase."""
        monitor = HealthMonitor()

        metrics = PoolMetrics(
            pool_size=5,
            active_workflows=2,
            available_slots=3,
            pool_utilization_pct=40.0,
            peak_utilization_pct=60.0,
            queue_depth=0,
            queue_depth_trend="stable",
            avg_slot_wait_time_ms=0.0,
            total_workflows_processed=100,
            total_workflows_succeeded=80,
            total_workflows_failed=20,
            success_rate=80.0,
            p50_workflow_duration_ms=10000.0,
            p95_workflow_duration_ms=25000.0,
            p99_workflow_duration_ms=35000.0,
            avg_workflow_duration_ms=15000.0,
            failure_rate_by_phase={
                "E2E_TEST_GENERATION": 30.0,  # Above 25% critical threshold
                "CODE_IMPLEMENTATION": 5.0,
            },
            retry_success_rate=60.0,
            throughput_trend="stable",
            latency_trend="stable",
        )

        report = monitor.assess_health(metrics)

        assert report.status == HealthStatus.CRITICAL
        phase_alerts = [
            a for a in report.alerts if "E2E_TEST_GENERATION" in a.metric
        ]
        assert len(phase_alerts) == 1
        assert phase_alerts[0].severity == "critical"

    def test_custom_thresholds(self):
        """Test custom threshold configuration."""
        custom_thresholds = HealthThresholds(
            pool_utilization_warning=60.0,  # Lower warning threshold
            pool_utilization_critical=85.0,  # Lower critical threshold
        )

        monitor = HealthMonitor(thresholds=custom_thresholds)

        metrics = PoolMetrics(
            pool_size=5,
            active_workflows=3,
            available_slots=2,
            pool_utilization_pct=70.0,  # Above custom 60% warning
            peak_utilization_pct=70.0,
            queue_depth=0,
            queue_depth_trend="stable",
            avg_slot_wait_time_ms=0.0,
            total_workflows_processed=100,
            total_workflows_succeeded=95,
            total_workflows_failed=5,
            success_rate=95.0,
            p50_workflow_duration_ms=10000.0,
            p95_workflow_duration_ms=25000.0,
            p99_workflow_duration_ms=35000.0,
            avg_workflow_duration_ms=15000.0,
            failure_rate_by_phase={},
            retry_success_rate=80.0,
            throughput_trend="stable",
            latency_trend="stable",
        )

        report = monitor.assess_health(metrics)

        assert report.status == HealthStatus.WARNING
        assert len(report.alerts) >= 1

    def test_multiple_alerts_prioritization(self):
        """Test that critical alerts are prioritized over warnings."""
        monitor = HealthMonitor()

        metrics = PoolMetrics(
            pool_size=5,
            active_workflows=5,
            available_slots=0,
            pool_utilization_pct=100.0,  # Critical
            peak_utilization_pct=100.0,
            queue_depth=12,  # Warning (if increasing)
            queue_depth_trend="increasing",
            avg_slot_wait_time_ms=0.0,
            total_workflows_processed=100,
            total_workflows_succeeded=85,
            total_workflows_failed=15,
            success_rate=85.0,  # Warning
            p50_workflow_duration_ms=10000.0,
            p95_workflow_duration_ms=25000.0,
            p99_workflow_duration_ms=35000.0,
            avg_workflow_duration_ms=15000.0,
            failure_rate_by_phase={},
            retry_success_rate=70.0,
            throughput_trend="stable",
            latency_trend="stable",
        )

        report = monitor.assess_health(metrics)

        # Should be CRITICAL due to pool utilization
        assert report.status == HealthStatus.CRITICAL

        # Should have multiple alerts
        assert len(report.alerts) >= 2

        # Recommendations should prioritize critical issues
        assert len(report.recommendations) > 0
        assert any("CRITICAL" in rec for rec in report.recommendations)
