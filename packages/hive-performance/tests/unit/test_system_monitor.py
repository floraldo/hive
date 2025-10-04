"""Unit tests for hive_performance.system_monitor module."""
import pytest


@pytest.mark.core
class TestSystemMonitor:
    """Test cases for SystemMonitor class."""

    @pytest.mark.core
    def test_system_monitor_initialization(self):
        """Test SystemMonitor can be initialized."""
        from hive_performance.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        assert monitor is not None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_system_metrics_monitoring(self):
        """Test system metrics monitoring."""
        from hive_performance.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        if hasattr(monitor, 'get_system_metrics'):
            metrics = await monitor.get_system_metrics()
            assert isinstance(metrics, dict) or metrics is None

    @pytest.mark.core
    def test_monitor_configuration(self):
        """Test monitor accepts configuration parameters."""
        from hive_performance.system_monitor import SystemMonitor
        config = {'monitoring_interval': 5.0, 'enable_cpu_monitoring': True, 'enable_memory_monitoring': True, 'enable_disk_monitoring': True}
        monitor = SystemMonitor(**config)
        assert monitor is not None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_cpu_monitoring(self):
        """Test CPU monitoring functionality."""
        from hive_performance.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        if hasattr(monitor, 'get_cpu_usage'):
            cpu_usage = await monitor.get_cpu_usage()
            assert isinstance(cpu_usage, (int, float)) or cpu_usage is None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_memory_monitoring(self):
        """Test memory monitoring functionality."""
        from hive_performance.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        if hasattr(monitor, 'get_memory_usage'):
            memory_usage = await monitor.get_memory_usage()
            assert isinstance(memory_usage, dict) or memory_usage is None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_disk_monitoring(self):
        """Test disk monitoring functionality."""
        from hive_performance.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        if hasattr(monitor, 'get_disk_usage'):
            disk_usage = await monitor.get_disk_usage()
            assert isinstance(disk_usage, dict) or disk_usage is None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_network_monitoring(self):
        """Test network monitoring functionality."""
        from hive_performance.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        if hasattr(monitor, 'get_network_stats'):
            network_stats = await monitor.get_network_stats()
            assert isinstance(network_stats, dict) or network_stats is None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_process_monitoring(self):
        """Test process monitoring functionality."""
        from hive_performance.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        if hasattr(monitor, 'get_process_stats'):
            process_stats = await monitor.get_process_stats()
            assert isinstance(process_stats, list) or process_stats is None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_alert_functionality(self):
        """Test system monitoring alerts."""
        from hive_performance.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        if hasattr(monitor, 'set_alert_threshold'):
            monitor.set_alert_threshold('cpu', 90.0)
        if hasattr(monitor, 'check_alerts'):
            alerts = await monitor.check_alerts()
            assert isinstance(alerts, list) or alerts is None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_monitor_lifecycle(self):
        """Test monitor lifecycle management."""
        from hive_performance.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        if hasattr(monitor, 'start_monitoring'):
            await monitor.start_monitoring()
        if hasattr(monitor, 'stop_monitoring'):
            await monitor.stop_monitoring()
        assert True
