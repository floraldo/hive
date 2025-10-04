"""Unit tests for hive-performance package V4.2."""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Import the components we're testing
from hive_performance.metrics_collector import (
    MetricsCollector,
    PerformanceMetrics,
    operation_tracker,
    track_performance,
)
from hive_performance.system_monitor import SystemMetrics, SystemMonitor


@pytest.fixture
def metrics_collector():
    """Create MetricsCollector instance for testing."""
    return MetricsCollector(
        collection_interval=0.1,  # Fast for testing
        max_history=10,
        enable_system_metrics=True,
        enable_async_metrics=True,
    )


@pytest.fixture
def system_monitor():
    """Create SystemMonitor instance for testing."""
    return SystemMonitor(
        collection_interval=0.1,  # Fast for testing
        max_history=10,
        enable_alerts=True,
        alert_thresholds={"cpu_percent": 80.0, "memory_percent": 85.0},
    )


class TestPerformanceMetrics:
    """Test the PerformanceMetrics data class."""

    def test_performance_metrics_initialization(self):
        """Test PerformanceMetrics initialization with defaults."""
        metrics = PerformanceMetrics()

        assert metrics.execution_time == 0.0
        assert metrics.cpu_time == 0.0
        assert metrics.memory_usage == 0
        assert metrics.operations_count == 0
        assert metrics.error_count == 0
        assert isinstance(metrics.custom_metrics, dict)
        assert isinstance(metrics.tags, dict)
        assert isinstance(metrics.timestamp, datetime)

    def test_performance_metrics_with_data(self):
        """Test PerformanceMetrics with specific data."""
        custom_data = {"test_metric": 42}
        tags = {"environment": "test", "version": "1.0"}

        metrics = PerformanceMetrics(
            execution_time=1.5,
            memory_usage=1024 * 1024,
            operations_count=5,
            error_count=1,
            custom_metrics=custom_data,
            tags=tags,
            operation_name="test_operation",
        )

        assert metrics.execution_time == 1.5
        assert metrics.memory_usage == 1024 * 1024
        assert metrics.operations_count == 5
        assert metrics.error_count == 1
        assert metrics.custom_metrics == custom_data
        assert metrics.tags == tags
        assert metrics.operation_name == "test_operation"


class TestMetricsCollector:
    """Test the MetricsCollector component."""

    def test_metrics_collector_initialization(self, metrics_collector):
        """Test MetricsCollector initializes correctly."""
        assert metrics_collector.collection_interval == 0.1
        assert metrics_collector.max_history == 10
        assert metrics_collector.enable_system_metrics is True
        assert metrics_collector.enable_async_metrics is True
        assert not metrics_collector._collecting
        assert metrics_collector._collection_task is None

    @pytest.mark.asyncio
    async def test_start_stop_collection(self, metrics_collector):
        """Test starting and stopping metrics collection."""
        # Start collection
        await metrics_collector.start_collection()
        assert metrics_collector._collecting is True
        assert metrics_collector._collection_task is not None

        # Wait a bit for collection to run
        await asyncio.sleep(0.2)

        # Stop collection
        await metrics_collector.stop_collection()
        assert metrics_collector._collecting is False

    @pytest.mark.asyncio
    async def test_operation_tracking_basic(self, metrics_collector):
        """Test basic operation tracking functionality."""
        operation_name = "test_operation"
        tags = {"test": "value"}

        # Start operation
        operation_id = metrics_collector.start_operation(operation_name, tags)
        assert operation_id is not None
        assert operation_name in operation_id

        # Simulate some work
        await asyncio.sleep(0.01)

        # End operation
        metrics = metrics_collector.end_operation(operation_id, success=True, bytes_processed=1024)

        assert metrics.operation_name == operation_name
        assert metrics.execution_time > 0
        assert metrics.bytes_processed == 1024
        assert metrics.error_count == 0
        assert metrics.tags == tags

    @pytest.mark.asyncio
    async def test_operation_tracking_with_error(self, metrics_collector):
        """Test operation tracking with error condition."""
        operation_name = "failing_operation"

        operation_id = metrics_collector.start_operation(operation_name)
        metrics = metrics_collector.end_operation(operation_id, success=False)

        assert metrics.operation_name == operation_name
        assert metrics.error_count == 1
        assert metrics.error_rate > 0

    @pytest.mark.asyncio
    async def test_operation_tracking_multiple_operations(self, metrics_collector):
        """Test tracking multiple operations concurrently."""
        operation_ids = []

        # Start multiple operations
        for i in range(3):
            op_id = metrics_collector.start_operation(f"operation_{i}")
            operation_ids.append(op_id)

        # End all operations
        results = []
        for op_id in operation_ids:
            metrics = metrics_collector.end_operation(op_id, success=True)
            results.append(metrics)

        assert len(results) == 3
        assert all(m.execution_time >= 0 for m in results)

    def test_get_metrics_empty(self, metrics_collector):
        """Test getting metrics when none collected."""
        metrics = metrics_collector.get_metrics()
        assert metrics == []

        aggregated = metrics_collector.get_aggregated_metrics()
        assert aggregated.operations_count == 0

    @pytest.mark.asyncio
    async def test_get_metrics_with_data(self, metrics_collector):
        """Test getting metrics after operations."""
        # Perform some operations
        for _i in range(3):
            op_id = metrics_collector.start_operation("test_op")
            await asyncio.sleep(0.001)  # Small delay
            metrics_collector.end_operation(op_id, success=True)

        # Get metrics
        all_metrics = metrics_collector.get_metrics()
        assert len(all_metrics) == 3

        # Get aggregated metrics
        aggregated = metrics_collector.get_aggregated_metrics("test_op")
        assert aggregated.operations_count == 3
        assert aggregated.execution_time > 0

    @pytest.mark.asyncio
    async def test_metrics_time_window_filtering(self, metrics_collector):
        """Test time window filtering for metrics."""
        # Create old operation
        op_id = metrics_collector.start_operation("old_op")
        old_metrics = metrics_collector.end_operation(op_id)

        # Modify timestamp to be old
        old_metrics.timestamp = datetime.utcnow() - timedelta(hours=2)
        metrics_collector._metrics_history["old_op"][-1] = old_metrics

        # Create recent operation
        op_id = metrics_collector.start_operation("recent_op")
        metrics_collector.end_operation(op_id)

        # Test time window filtering
        recent_only = metrics_collector.get_metrics(time_window=timedelta(hours=1))
        assert len(recent_only) == 1
        assert recent_only[0].operation_name == "recent_op"

    def test_baseline_functionality(self, metrics_collector):
        """Test performance baseline setting and comparison."""
        operation_name = "baseline_test"

        # Create some metrics
        op_id = metrics_collector.start_operation(operation_name)
        metrics_collector.end_operation(op_id, success=True)

        # Set baseline
        metrics_collector.set_baseline(operation_name)
        assert operation_name in metrics_collector._baselines

        # Create more metrics for comparison
        op_id = metrics_collector.start_operation(operation_name)
        metrics_collector.end_operation(op_id, success=True)

        # Compare to baseline
        comparison = metrics_collector.compare_to_baseline(operation_name)
        assert comparison is not None
        assert "execution_time_change" in comparison
        assert "memory_change" in comparison
        assert "throughput_change" in comparison

    def test_export_metrics_json(self, metrics_collector):
        """Test JSON export functionality."""
        # Create operation
        op_id = metrics_collector.start_operation("export_test")
        metrics_collector.end_operation(op_id, success=True)

        # Export as JSON
        json_data = metrics_collector.export_metrics(format="json")
        assert isinstance(json_data, str)

        import json

        parsed = json.loads(json_data)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["operation_name"] == "export_test"

    def test_export_metrics_dict(self, metrics_collector):
        """Test dictionary export functionality."""
        # Create operation
        op_id = metrics_collector.start_operation("export_test")
        metrics_collector.end_operation(op_id, success=True)

        # Export as dict
        dict_data = metrics_collector.export_metrics(format="dict")
        assert isinstance(dict_data, dict)
        assert "metrics" in dict_data
        assert "summary" in dict_data
        assert dict_data["summary"]["total_operations"] == 1

    def test_clear_metrics(self, metrics_collector):
        """Test clearing metrics functionality."""
        # Create operations
        op_id1 = metrics_collector.start_operation("op1")
        metrics_collector.end_operation(op_id1)

        op_id2 = metrics_collector.start_operation("op2")
        metrics_collector.end_operation(op_id2)

        # Clear specific operation
        metrics_collector.clear_metrics("op1")
        assert len(metrics_collector.get_metrics("op1")) == 0
        assert len(metrics_collector.get_metrics("op2")) == 1

        # Clear all metrics
        metrics_collector.clear_metrics()
        assert len(metrics_collector.get_metrics()) == 0

    @patch("hive_performance.metrics_collector.psutil.Process")
    def test_memory_usage_tracking(self, mock_process, metrics_collector):
        """Test memory usage tracking functionality."""
        # Mock memory info
        mock_memory = MagicMock()
        mock_memory.rss = 1024 * 1024 * 100  # 100MB
        mock_process.return_value.memory_info.return_value = mock_memory

        memory_usage = metrics_collector._get_memory_usage()
        assert memory_usage == 1024 * 1024 * 100

    def test_error_rate_calculation(self, metrics_collector):
        """Test error rate calculation."""
        operation_name = "error_test"

        # Create successful operations
        for _ in range(8):
            op_id = metrics_collector.start_operation(operation_name)
            metrics_collector.end_operation(op_id, success=True)

        # Create failed operations
        for _ in range(2):
            op_id = metrics_collector.start_operation(operation_name)
            metrics_collector.end_operation(op_id, success=False)

        # Check error rate
        error_rate = metrics_collector._calculate_error_rate(operation_name)
        assert error_rate == 0.2  # 2 errors out of 10 operations


class TestOperationTracker:
    """Test the operation_tracker context manager."""

    @pytest.mark.asyncio
    async def test_operation_tracker_success(self, metrics_collector):
        """Test operation tracker with successful operation."""
        operation_name = "tracked_operation"
        tags = {"type": "test"}

        with operation_tracker(metrics_collector, operation_name, tags) as tracker:
            assert tracker.operation_id is not None
            await asyncio.sleep(0.001)  # Simulate work

        # Check metrics were recorded
        metrics = metrics_collector.get_metrics(operation_name)
        assert len(metrics) == 1
        assert metrics[0].operation_name == operation_name
        assert metrics[0].tags == tags
        assert metrics[0].error_count == 0

    @pytest.mark.asyncio
    async def test_operation_tracker_with_exception(self, metrics_collector):
        """Test operation tracker with exception."""
        operation_name = "failing_operation"

        try:
            with operation_tracker(metrics_collector, operation_name):
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Check metrics were recorded with error
        metrics = metrics_collector.get_metrics(operation_name)
        assert len(metrics) == 1
        assert metrics[0].error_count == 1

    @pytest.mark.asyncio
    async def test_operation_tracker_with_custom_metrics(self, metrics_collector):
        """Test operation tracker with custom metrics."""
        operation_name = "custom_operation"
        custom_data = {"processing_items": 50}

        with operation_tracker(metrics_collector, operation_name, bytes_processed=2048, custom_metrics=custom_data):
            await asyncio.sleep(0.001)

        metrics = metrics_collector.get_metrics(operation_name)
        assert len(metrics) == 1
        assert metrics[0].bytes_processed == 2048
        assert metrics[0].custom_metrics == custom_data


class TestPerformanceDecorator:
    """Test the track_performance decorator."""

    @pytest.mark.asyncio
    async def test_async_function_tracking(self, metrics_collector):
        """Test tracking async functions."""

        @track_performance(metrics_collector, "async_test")
        async def async_test_function(x, y):
            await asyncio.sleep(0.001)
            return x + y

        result = await async_test_function(5, 3)
        assert result == 8

        metrics = metrics_collector.get_metrics("async_test")
        assert len(metrics) == 1
        assert metrics[0].execution_time > 0

    def test_sync_function_tracking(self, metrics_collector):
        """Test tracking sync functions."""

        @track_performance(metrics_collector, "sync_test")
        def sync_test_function(x, y):
            time.sleep(0.001)
            return x * y

        result = sync_test_function(4, 5)
        assert result == 20

        metrics = metrics_collector.get_metrics("sync_test")
        assert len(metrics) == 1
        assert metrics[0].execution_time > 0

    @pytest.mark.asyncio
    async def test_decorator_automatic_naming(self, metrics_collector):
        """Test decorator with automatic operation naming."""

        @track_performance(metrics_collector)
        async def test_auto_named_function():
            await asyncio.sleep(0.001)
            return "done"

        await test_auto_named_function()

        # Should use module.function_name
        metrics = metrics_collector.get_metrics()
        assert len(metrics) == 1
        assert "test_auto_named_function" in metrics[0].operation_name


class TestSystemMetrics:
    """Test the SystemMetrics data class."""

    def test_system_metrics_initialization(self):
        """Test SystemMetrics initialization."""
        metrics = SystemMetrics()

        assert metrics.cpu_percent == 0.0
        assert metrics.memory_total == 0
        assert metrics.disk_total == 0
        assert metrics.active_tasks == 0
        assert isinstance(metrics.load_average, list)
        assert isinstance(metrics.timestamp, datetime)

    def test_system_metrics_with_data(self):
        """Test SystemMetrics with specific data."""
        metrics = SystemMetrics(
            cpu_percent=45.5,
            memory_total=8 * 1024 * 1024 * 1024,  # 8GB
            memory_percent=60.0,
            disk_percent=75.0,
            active_tasks=10,
            hostname="test-host",
            platform="linux",
        )

        assert metrics.cpu_percent == 45.5
        assert metrics.memory_total == 8 * 1024 * 1024 * 1024
        assert metrics.memory_percent == 60.0
        assert metrics.disk_percent == 75.0
        assert metrics.active_tasks == 10
        assert metrics.hostname == "test-host"
        assert metrics.platform == "linux"


class TestSystemMonitor:
    """Test the SystemMonitor component."""

    def test_system_monitor_initialization(self, system_monitor):
        """Test SystemMonitor initializes correctly."""
        assert system_monitor.collection_interval == 0.1
        assert system_monitor.max_history == 10
        assert system_monitor.enable_alerts is True
        assert system_monitor.alert_thresholds["cpu_percent"] == 80.0
        assert not system_monitor._monitoring

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, system_monitor):
        """Test starting and stopping system monitoring."""
        # Start monitoring
        await system_monitor.start_monitoring()
        assert system_monitor._monitoring is True
        assert system_monitor._monitor_task is not None

        # Wait for some collection
        await asyncio.sleep(0.2)

        # Stop monitoring
        await system_monitor.stop_monitoring()
        assert system_monitor._monitoring is False

    @pytest.mark.asyncio
    @patch("hive_performance.system_monitor.psutil.cpu_percent")
    @patch("hive_performance.system_monitor.psutil.virtual_memory")
    @patch("hive_performance.system_monitor.psutil.disk_usage")
    @patch("hive_performance.system_monitor.psutil.disk_io_counters")
    @patch("hive_performance.system_monitor.psutil.net_io_counters")
    async def test_collect_system_metrics(
        self,
        mock_net,
        mock_disk_io,
        mock_disk,
        mock_memory,
        mock_cpu,
        system_monitor,
    ):
        """Test system metrics collection."""
        # Setup mocks
        mock_cpu.return_value = 45.5

        mock_mem = MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024
        mock_mem.available = 4 * 1024 * 1024 * 1024
        mock_mem.used = 4 * 1024 * 1024 * 1024
        mock_mem.percent = 50.0
        mock_memory.return_value = mock_mem

        mock_disk_usage.return_value = MagicMock(
            total=1024 * 1024 * 1024 * 1024,
            used=512 * 1024 * 1024 * 1024,
            free=512 * 1024 * 1024 * 1024,
        )

        mock_disk_io.return_value = MagicMock(
            read_bytes=1024 * 1024,
            write_bytes=2 * 1024 * 1024,
            read_count=100,
            write_count=200,
        )

        mock_net.return_value = MagicMock(
            bytes_sent=1024 * 1024 * 10,
            bytes_recv=1024 * 1024 * 20,
            packets_sent=1000,
            packets_recv=2000,
            errin=0,
            errout=0,
        )

        # Collect metrics
        metrics = await system_monitor._collect_system_metrics()

        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent == 45.5
        assert metrics.memory_total == 8 * 1024 * 1024 * 1024
        assert metrics.memory_percent == 50.0

    @pytest.mark.asyncio
    async def test_alert_system(self, system_monitor):
        """Test alert system functionality."""
        alert_triggered = []

        async def alert_callback(alerts, metrics):
            alert_triggered.extend(alerts)

        system_monitor.add_alert_callback(alert_callback)

        # Create metrics that trigger alerts
        high_cpu_metrics = SystemMetrics(
            cpu_percent=90.0,  # Above 80% threshold
            memory_percent=90.0,  # Above 85% threshold
            disk_percent=95.0,  # Above 90% threshold
            swap_percent=60.0,  # Above 50% threshold
        )

        await system_monitor._check_alerts(high_cpu_metrics)

        assert len(alert_triggered) == 4  # All thresholds exceeded
        assert any("High CPU usage: 90.0%" in alert for alert in alert_triggered)
        assert any("High memory usage: 90.0%" in alert for alert in alert_triggered)

    @pytest.mark.asyncio
    async def test_get_current_metrics(self, system_monitor):
        """Test getting current metrics."""
        # Initially no metrics
        current = system_monitor.get_current_metrics()
        assert current is None

        # Add a metric manually
        test_metrics = SystemMetrics(cpu_percent=25.0)
        system_monitor._metrics_history.append(test_metrics)

        current = system_monitor.get_current_metrics()
        assert current is not None
        assert current.cpu_percent == 25.0

    def test_metrics_history_filtering(self, system_monitor):
        """Test metrics history filtering by time window."""
        # Add some metrics with different timestamps
        old_metrics = SystemMetrics(cpu_percent=30.0)
        old_metrics.timestamp = datetime.utcnow() - timedelta(hours=2)

        recent_metrics = SystemMetrics(cpu_percent=40.0)
        recent_metrics.timestamp = datetime.utcnow() - timedelta(minutes=30)

        system_monitor._metrics_history.extend([old_metrics, recent_metrics])

        # Get recent metrics only
        recent_only = system_monitor.get_metrics_history(timedelta(hours=1))
        assert len(recent_only) == 1
        assert recent_only[0].cpu_percent == 40.0

    def test_average_metrics_calculation(self, system_monitor):
        """Test average metrics calculation."""
        # Add sample metrics
        metrics1 = SystemMetrics(cpu_percent=20.0, memory_percent=30.0)
        metrics2 = SystemMetrics(cpu_percent=40.0, memory_percent=50.0)
        metrics3 = SystemMetrics(cpu_percent=30.0, memory_percent=40.0)

        system_monitor._metrics_history.extend([metrics1, metrics2, metrics3])

        avg_metrics = system_monitor.get_average_metrics(timedelta(hours=1))

        assert avg_metrics is not None
        assert avg_metrics.cpu_percent == 30.0  # (20+40+30)/3
        assert avg_metrics.memory_percent == 40.0  # (30+50+40)/3

    def test_peak_metrics_calculation(self, system_monitor):
        """Test peak metrics calculation."""
        # Add sample metrics
        metrics1 = SystemMetrics(cpu_percent=20.0, memory_percent=30.0, active_tasks=5)
        metrics2 = SystemMetrics(cpu_percent=60.0, memory_percent=70.0, active_tasks=10)
        metrics3 = SystemMetrics(cpu_percent=40.0, memory_percent=50.0, active_tasks=8)

        system_monitor._metrics_history.extend([metrics1, metrics2, metrics3])

        peak_metrics = system_monitor.get_peak_metrics(timedelta(hours=1))

        assert peak_metrics is not None
        assert peak_metrics.cpu_percent == 60.0
        assert peak_metrics.memory_percent == 70.0
        assert peak_metrics.active_tasks == 10

    def test_trend_analysis(self, system_monitor):
        """Test performance trend analysis."""
        # Add metrics showing increasing trend
        for i in range(5):
            metrics = SystemMetrics(
                cpu_percent=20.0 + i * 10,  # 20, 30, 40, 50, 60
                memory_percent=30.0 + i * 5,  # 30, 35, 40, 45, 50
            )
            system_monitor._metrics_history.append(metrics)

        trends = system_monitor.analyze_trends(timedelta(hours=1))

        assert "cpu_trend" in trends
        assert "memory_trend" in trends
        assert trends["cpu_trend"] > 0  # Increasing trend
        assert trends["memory_trend"] > 0  # Increasing trend

    def test_resource_exhaustion_prediction(self, system_monitor):
        """Test resource exhaustion prediction."""
        # Add metrics showing increasing CPU trend
        for i in range(3):
            metrics = SystemMetrics(cpu_percent=70.0 + i * 5)  # 70, 75, 80
            system_monitor._metrics_history.append(metrics)

        predictions = system_monitor.predict_resource_exhaustion(timedelta(hours=1))

        assert "cpu_exhaustion" in predictions
        # Should predict CPU exhaustion since trend is positive and current < 100

    def test_export_metrics_json(self, system_monitor):
        """Test JSON export of system metrics."""
        # Add sample metrics
        metrics = SystemMetrics(cpu_percent=45.0, memory_percent=60.0)
        system_monitor._metrics_history.append(metrics)

        json_data = system_monitor.export_metrics(format="json")
        assert isinstance(json_data, str)

        import json

        parsed = json.loads(json_data)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["cpu_percent"] == 45.0

    def test_export_metrics_csv(self, system_monitor):
        """Test CSV export of system metrics."""
        # Add sample metrics
        metrics = SystemMetrics(cpu_percent=45.0, memory_percent=60.0)
        system_monitor._metrics_history.append(metrics)

        csv_data = system_monitor.export_metrics(format="csv")
        assert isinstance(csv_data, str)
        assert "timestamp,cpu_percent,memory_percent" in csv_data
        assert "45.0" in csv_data

    def test_clear_history(self, system_monitor):
        """Test clearing metrics history."""
        # Add sample metrics
        metrics = SystemMetrics(cpu_percent=45.0)
        system_monitor._metrics_history.append(metrics)

        assert len(system_monitor._metrics_history) == 1

        system_monitor.clear_history()
        assert len(system_monitor._metrics_history) == 0


class TestPerformanceIntegration:
    """Integration tests for performance monitoring components."""

    @pytest.mark.asyncio
    async def test_metrics_and_system_monitor_integration(self):
        """Test integration between MetricsCollector and SystemMonitor."""
        metrics_collector = MetricsCollector(collection_interval=0.1, max_history=5)
        system_monitor = SystemMonitor(collection_interval=0.1, max_history=5)

        try:
            # Start both monitors
            await metrics_collector.start_collection()
            await system_monitor.start_monitoring()

            # Perform some operations while monitoring
            for i in range(3):
                with operation_tracker(metrics_collector, f"integration_test_{i}"):
                    await asyncio.sleep(0.01)

            # Let monitors collect data
            await asyncio.sleep(0.3)

            # Verify metrics were collected
            operation_metrics = metrics_collector.get_metrics()
            assert len(operation_metrics) >= 3

            system_metrics = system_monitor.get_current_metrics()
            assert system_metrics is not None
            assert system_metrics.cpu_percent >= 0

        finally:
            # Clean shutdown
            await metrics_collector.stop_collection()
            await system_monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """Test performance monitoring under simulated load."""
        metrics_collector = MetricsCollector(max_history=50)

        # Simulate concurrent operations
        async def worker(worker_id):
            for _i in range(5):
                with operation_tracker(metrics_collector, f"worker_{worker_id}"):
                    await asyncio.sleep(0.001)

        # Run concurrent workers
        workers = [worker(i) for i in range(5)]
        await asyncio.gather(*workers)

        # Verify all operations were tracked
        all_metrics = metrics_collector.get_metrics()
        assert len(all_metrics) == 25  # 5 workers * 5 operations each

        # Check aggregated performance
        aggregated = metrics_collector.get_aggregated_metrics()
        assert aggregated.operations_count == 25
        assert aggregated.error_count == 0

    @pytest.mark.asyncio
    async def test_error_tracking_accuracy(self):
        """Test accuracy of error tracking across components."""
        metrics_collector = MetricsCollector()

        # Mix of successful and failed operations
        success_count = 0
        error_count = 0

        for i in range(10):
            op_id = metrics_collector.start_operation("mixed_operation")
            success = i % 3 != 0  # Fail every 3rd operation

            if success:
                success_count += 1
            else:
                error_count += 1

            metrics_collector.end_operation(op_id, success=success)

        # Verify error tracking
        aggregated = metrics_collector.get_aggregated_metrics("mixed_operation")
        assert aggregated.operations_count == 10
        assert aggregated.error_count == error_count
        assert abs(aggregated.error_rate - (error_count / 10)) < 0.01

    @pytest.mark.asyncio
    async def test_memory_and_performance_correlation(self, metrics_collector):
        """Test correlation between memory usage and performance metrics."""
        # Simulate memory-intensive operation
        big_data = []

        with operation_tracker(metrics_collector, "memory_test"):
            # Allocate memory
            for _i in range(1000):
                big_data.append([0] * 1000)

            await asyncio.sleep(0.01)

        metrics = metrics_collector.get_metrics("memory_test")
        assert len(metrics) == 1

        # Memory usage should be recorded
        assert metrics[0].memory_usage > 0
        assert metrics[0].execution_time > 0


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
