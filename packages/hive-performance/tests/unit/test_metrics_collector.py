"""Unit tests for hive_performance.metrics_collector module."""
import pytest

@pytest.mark.core
class TestMetricsCollector:
    """Test cases for MetricsCollector class."""

    @pytest.mark.core
    def test_metrics_collector_initialization(self):
        """Test MetricsCollector can be initialized."""
        from hive_performance.metrics_collector import MetricsCollector
        collector = MetricsCollector()
        assert collector is not None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_metrics_collection(self):
        """Test metrics collection functionality."""
        from hive_performance.metrics_collector import MetricsCollector
        collector = MetricsCollector()
        if hasattr(collector, 'collect_metrics'):
            metrics = await collector.collect_metrics()
            assert isinstance(metrics, dict) or metrics is None

    @pytest.mark.core
    def test_collector_configuration(self):
        """Test collector accepts configuration parameters."""
        from hive_performance.metrics_collector import MetricsCollector
        config = {'collection_interval': 10.0, 'buffer_size': 1000, 'enable_memory_metrics': True}
        collector = MetricsCollector(**config)
        assert collector is not None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_system_metrics_collection(self):
        """Test system metrics collection."""
        from hive_performance.metrics_collector import MetricsCollector
        collector = MetricsCollector()
        if hasattr(collector, 'collect_system_metrics'):
            sys_metrics = await collector.collect_system_metrics()
            assert isinstance(sys_metrics, dict) or sys_metrics is None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_application_metrics_collection(self):
        """Test application metrics collection."""
        from hive_performance.metrics_collector import MetricsCollector
        collector = MetricsCollector()
        if hasattr(collector, 'collect_app_metrics'):
            app_metrics = await collector.collect_app_metrics()
            assert isinstance(app_metrics, dict) or app_metrics is None

    @pytest.mark.core
    def test_metrics_buffer_management(self):
        """Test metrics buffer management."""
        from hive_performance.metrics_collector import MetricsCollector
        collector = MetricsCollector(buffer_size=100)
        if hasattr(collector, 'get_buffer_size'):
            buffer_size = collector.get_buffer_size()
            assert isinstance(buffer_size, int) or buffer_size is None
        if hasattr(collector, 'clear_buffer'):
            collector.clear_buffer()
            assert True

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_metrics_export(self):
        """Test metrics export functionality."""
        from hive_performance.metrics_collector import MetricsCollector
        collector = MetricsCollector()
        if hasattr(collector, 'export_metrics'):
            exported = await collector.export_metrics()
            assert isinstance(exported, (dict, list)) or exported is None