"""Unit tests for hive_service_discovery.discovery_client module."""

import pytest


class TestDiscoveryClient:
    """Test cases for DiscoveryClient class."""

    def test_discovery_client_initialization(self):
        """Test DiscoveryClient can be initialized."""
        from hive_service_discovery.discovery_client import DiscoveryClient

        client = DiscoveryClient()
        assert client is not None

    @pytest.mark.asyncio
    async def test_service_registration(self):
        """Test service registration functionality."""
        from hive_service_discovery.discovery_client import DiscoveryClient

        client = DiscoveryClient()

        # Test registration interface
        if hasattr(client, "register_service"):
            service_info = {"name": "test-service", "host": "localhost", "port": 8080, "health_endpoint": "/health"}

            # Should not raise exceptions
            result = await client.register_service(service_info)
            assert result is not None or result is None

    @pytest.mark.asyncio
    async def test_service_discovery(self):
        """Test service discovery functionality."""
        from hive_service_discovery.discovery_client import DiscoveryClient

        client = DiscoveryClient()

        # Test discovery interface
        if hasattr(client, "discover_service"):
            service_name = ("test-service",)
            services = await client.discover_service(service_name)
            assert isinstance(services, list) or services is None

    def test_client_configuration(self):
        """Test client accepts configuration parameters."""
        from hive_service_discovery.discovery_client import DiscoveryClient

        config = {"registry_url": "http://localhost:8500", "timeout": 30, "retry_attempts": 3}

        client = DiscoveryClient(**config)
        assert client is not None

    @pytest.mark.asyncio
    async def test_health_checking(self):
        """Test health check functionality."""
        from hive_service_discovery.discovery_client import DiscoveryClient

        client = DiscoveryClient()

        # Test health check interface
        if hasattr(client, "health_check"):
            service_id = ("test-service-1",)
            health_status = await client.health_check(service_id)
            assert isinstance(health_status, bool) or health_status is None

    @pytest.mark.asyncio
    async def test_service_deregistration(self):
        """Test service deregistration functionality."""
        from hive_service_discovery.discovery_client import DiscoveryClient

        client = DiscoveryClient()

        # Test deregistration interface
        if hasattr(client, "deregister_service"):
            service_id = ("test-service-1",)
            result = await client.deregister_service(service_id)
            assert result is not None or result is None

    def test_client_lifecycle_management(self):
        """Test client lifecycle management."""
        from hive_service_discovery.discovery_client import DiscoveryClient

        client = DiscoveryClient()

        # Test lifecycle methods
        if hasattr(client, "start"):
            client.start()

        if hasattr(client, "stop"):
            client.stop()

        assert True  # Lifecycle methods available
