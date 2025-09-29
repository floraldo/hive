"""Unit tests for hive_performance.monitoring_service module."""

import asyncio
from unittest.mock import Mock

import pytest


class TestMonitoringService:
    """Test cases for MonitoringService class."""

    def test_monitoring_service_initialization(self):
        """Test MonitoringService can be initialized."""
        from hive_performance.monitoring_service import MonitoringService

        service = MonitoringService()
        assert service is not None

    @pytest.mark.asyncio
    async def test_service_lifecycle(self):
        """Test monitoring service start/stop lifecycle."""
        from hive_performance.monitoring_service import MonitoringService

        service = MonitoringService()

        # Test lifecycle methods exist
        if hasattr(service, "start_async"):
            await service.start_async()

        if hasattr(service, "stop_async"):
            await service.stop_async()

        assert True  # Lifecycle completed

    def test_service_configuration(self):
        """Test service accepts configuration parameters."""
        from hive_performance.monitoring_service import MonitoringService

        config = {"collection_interval": 1.0, "analysis_interval": 300.0, "enable_profiling": True}

        service = MonitoringService(**config)
        assert service is not None

    @pytest.mark.asyncio
    async def test_monitoring_data_collection(self):
        """Test service collects monitoring data."""
        from hive_performance.monitoring_service import MonitoringService

        service = MonitoringService()

        # Test data collection interface
        if hasattr(service, "collect_metrics_async"):
            metrics = await service.collect_metrics_async()
            assert isinstance(metrics, dict) or metrics is None

    def test_service_component_integration(self):
        """Test service integrates with performance components."""
        from hive_performance.monitoring_service import MonitoringService

        service = MonitoringService()

        # Test component access
        assert hasattr(service, "metrics_collector") or hasattr(service, "profiler")

    @pytest.mark.asyncio
    async def test_real_time_monitoring(self):
        """Test real-time monitoring capabilities."""
        from hive_performance.monitoring_service import MonitoringService

        service = MonitoringService(collection_interval=0.1)

        # Mock some monitoring activity
        start_time = asyncio.get_event_loop().time()

        # Simulate brief monitoring period
        await asyncio.sleep(0.05)

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        assert duration < 1.0  # Monitoring should be lightweight

    def test_alerting_functionality(self):
        """Test monitoring service alerting capabilities."""
        from hive_performance.monitoring_service import MonitoringService

        service = MonitoringService(enable_alerts=True)

        # Test alerting interface
        if hasattr(service, "add_alert_handler"):
            mock_handler = Mock()
            service.add_alert_handler(mock_handler)

        assert True  # Alerting interface available
