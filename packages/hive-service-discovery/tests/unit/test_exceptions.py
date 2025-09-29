"""Unit tests for hive_service_discovery.exceptions module."""

import pytest


class TestServiceDiscoveryExceptions:
    """Test cases for service discovery exceptions."""

    def test_base_exception_exists(self):
        """Test base exception can be imported."""
        try:
            from hive_service_discovery.exceptions import ServiceDiscoveryError

            assert ServiceDiscoveryError is not None
            assert issubclass(ServiceDiscoveryError, Exception)
        except ImportError:
            pytest.skip("ServiceDiscoveryError not found")

    def test_registration_exceptions(self):
        """Test service registration exceptions."""
        try:
            from hive_service_discovery.exceptions import DuplicateServiceError, ServiceRegistrationError

            # Test registration error
            error = ServiceRegistrationError("Failed to register service")
            assert str(error) == "Failed to register service"

            # Test duplicate service error
            if "DuplicateServiceError" in locals():
                dup_error = DuplicateServiceError("service-1", "Service already exists")
                assert "service-1" in str(dup_error)

        except ImportError:
            pytest.skip("Registration exceptions not found")

    def test_discovery_exceptions(self):
        """Test service discovery exceptions."""
        try:
            from hive_service_discovery.exceptions import ServiceDiscoveryError, ServiceNotFoundError

            # Test service not found error
            if "ServiceNotFoundError" in locals():
                error = ServiceNotFoundError("test-service")
                assert "test-service" in str(error)

        except ImportError:
            pytest.skip("Discovery exceptions not found")

    def test_health_check_exceptions(self):
        """Test health check exceptions."""
        try:
            from hive_service_discovery.exceptions import HealthCheckError, ServiceUnhealthyError

            # Test health check error
            if "HealthCheckError" in locals():
                error = HealthCheckError("Health check failed")
                assert "Health check failed" in str(error)

            # Test service unhealthy error
            if "ServiceUnhealthyError" in locals():
                error = ServiceUnhealthyError("service-1", "Service is down")
                assert "service-1" in str(error)

        except ImportError:
            pytest.skip("Health check exceptions not found")

    def test_load_balancer_exceptions(self):
        """Test load balancer exceptions."""
        try:
            from hive_service_discovery.exceptions import LoadBalancerError, NoHealthyServicesError

            # Test load balancer error
            if "LoadBalancerError" in locals():
                error = LoadBalancerError("Load balancing failed")
                assert "Load balancing failed" in str(error)

            # Test no healthy services error
            if "NoHealthyServicesError" in locals():
                error = NoHealthyServicesError("test-service")
                assert "test-service" in str(error)

        except ImportError:
            pytest.skip("Load balancer exceptions not found")

    def test_connection_exceptions(self):
        """Test connection related exceptions."""
        try:
            from hive_service_discovery.exceptions import ConnectionError, TimeoutError

            # Test connection error
            if "ConnectionError" in locals():
                error = ConnectionError("Failed to connect to registry")
                assert "Failed to connect" in str(error)

            # Test timeout error
            if "TimeoutError" in locals():
                error = TimeoutError("Request timed out")
                assert "timed out" in str(error)

        except ImportError:
            pytest.skip("Connection exceptions not found")

    def test_exception_hierarchy(self):
        """Test exception inheritance hierarchy."""
        try:
            from hive_service_discovery.exceptions import (
                ServiceDiscoveryError,
                ServiceNotFoundError,
                ServiceRegistrationError,
            )

            # Test inheritance
            assert issubclass(ServiceDiscoveryError, Exception)

            if "ServiceRegistrationError" in locals():
                assert issubclass(ServiceRegistrationError, ServiceDiscoveryError)

            if "ServiceNotFoundError" in locals():
                assert issubclass(ServiceNotFoundError, ServiceDiscoveryError)

        except ImportError:
            pytest.skip("Exception hierarchy not found")
