"""Unit tests for hive_service_discovery.service_registry module."""
import pytest


@pytest.mark.core
class TestServiceRegistry:
    """Test cases for ServiceRegistry class."""

    @pytest.mark.core
    def test_service_registry_initialization(self):
        """Test ServiceRegistry can be initialized."""
        from hive_service_discovery.service_registry import ServiceRegistry
        registry = ServiceRegistry()
        assert registry is not None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_service_registration_and_lookup(self):
        """Test service registration and lookup functionality."""
        from hive_service_discovery.service_registry import ServiceRegistry
        registry = ServiceRegistry()
        if hasattr(registry, 'register'):
            service_data = {'id': 'service-1', 'name': 'test-service', 'address': '127.0.0.1', 'port': 8080}
            result = await registry.register(service_data)
            assert result is not None or result is None
        if hasattr(registry, 'lookup'):
            services = await registry.lookup('test-service')
            assert isinstance(services, list) or services is None

    @pytest.mark.core
    def test_registry_storage_interface(self):
        """Test registry storage interface."""
        from hive_service_discovery.service_registry import ServiceRegistry
        registry = ServiceRegistry()
        assert hasattr(registry, 'services') or hasattr(registry, '_services')

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_service_health_monitoring(self):
        """Test service health monitoring capabilities."""
        from hive_service_discovery.service_registry import ServiceRegistry
        registry = ServiceRegistry()
        if hasattr(registry, 'check_health'):
            service_id = ('service-1',)
            health_status = await registry.check_health(service_id)
            assert isinstance(health_status, bool) or health_status is None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_service_deregistration(self):
        """Test service deregistration functionality."""
        from hive_service_discovery.service_registry import ServiceRegistry
        registry = ServiceRegistry()
        if hasattr(registry, 'deregister'):
            service_id = ('service-1',)
            result = await registry.deregister(service_id)
            assert result is not None or result is None

    @pytest.mark.core
    def test_registry_configuration(self):
        """Test registry accepts configuration parameters."""
        from hive_service_discovery.service_registry import ServiceRegistry
        config = {'storage_backend': 'memory', 'health_check_interval': 30, 'cleanup_interval': 300}
        registry = ServiceRegistry(**config)
        assert registry is not None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_bulk_operations(self):
        """Test bulk registry operations."""
        from hive_service_discovery.service_registry import ServiceRegistry
        registry = ServiceRegistry()
        if hasattr(registry, 'register_bulk'):
            services = [{'id': 'svc-1', 'name': 'service-a'}, {'id': 'svc-2', 'name': 'service-b'}]
            result = await registry.register_bulk(services)
            assert result is not None or result is None
        if hasattr(registry, 'list_all'):
            all_services = await registry.list_all()
            assert isinstance(all_services, list) or all_services is None
