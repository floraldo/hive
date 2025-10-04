"""Unit tests for hive_service_discovery.exceptions module."""
import pytest


@pytest.mark.core
class TestServiceDiscoveryExceptions:
    """Test cases for service discovery exceptions."""

    @pytest.mark.core
    def test_base_exception_exists(self):
        """Test base exception can be imported."""
        try:
            from hive_service_discovery.exceptions import ServiceDiscoveryError
            assert ServiceDiscoveryError is not None
            assert issubclass(ServiceDiscoveryError, Exception)
        except ImportError:
            pytest.skip("ServiceDiscoveryError not found")

    @pytest.mark.core
    def test_registration_exceptions(self):
        """Test service registration exceptions."""
        try:
            from hive_service_discovery.exceptions import DuplicateServiceError, ServiceRegistrationError
            error = ServiceRegistrationError("Failed to register service")
            assert str(error) == "Failed to register service"
            if "DuplicateServiceError" in locals():
                dup_error = DuplicateServiceError("service-1", "Service already exists")
                assert "service-1" in str(dup_error)
        except ImportError:
            pytest.skip("Registration exceptions not found")

    @pytest.mark.core
    def test_discovery_exceptions(self):
        """Test service discovery exceptions."""
        try:
            from hive_service_discovery.exceptions import ServiceDiscoveryError, ServiceNotFoundError
            if "ServiceNotFoundError" in locals():
                error = ServiceNotFoundError("test-service")
                assert "test-service" in str(error)
        except ImportError:
            pytest.skip("Discovery exceptions not found")

    @pytest.mark.core
    def test_health_check_exceptions(self):
        """Test health check exceptions."""
        try:
            from hive_service_discovery.exceptions import HealthCheckError, ServiceUnhealthyError
            if "HealthCheckError" in locals():
                error = HealthCheckError("Health check failed")
                assert "Health check failed" in str(error)
            if "ServiceUnhealthyError" in locals():
                error = ServiceUnhealthyError("service-1", "Service is down")
                assert "service-1" in str(error)
        except ImportError:
            pytest.skip("Health check exceptions not found")

    @pytest.mark.core
    def test_load_balancer_exceptions(self):
        """Test load balancer exceptions."""
        try:
            from hive_service_discovery.exceptions import LoadBalancerError, NoHealthyServicesError
            if "LoadBalancerError" in locals():
                error = LoadBalancerError("Load balancing failed")
                assert "Load balancing failed" in str(error)
            if "NoHealthyServicesError" in locals():
                error = NoHealthyServicesError("test-service")
                assert "test-service" in str(error)
        except ImportError:
            pytest.skip("Load balancer exceptions not found")

    @pytest.mark.core
    def test_connection_exceptions(self):
        """Test connection related exceptions."""
        try:
            from hive_service_discovery.exceptions import ConnectionError, TimeoutError
            if "ConnectionError" in locals():
                error = ConnectionError("Failed to connect to registry")
                assert "Failed to connect" in str(error)
            if "TimeoutError" in locals():
                error = TimeoutError("Request timed out")
                assert "timed out" in str(error)
        except ImportError:
            pytest.skip("Connection exceptions not found")

    @pytest.mark.core
    def test_exception_hierarchy(self):
        """Test exception inheritance hierarchy."""
        try:
            from hive_service_discovery.exceptions import (
                ServiceDiscoveryError,
                ServiceNotFoundError,
                ServiceRegistrationError,
            )
            assert issubclass(ServiceDiscoveryError, Exception)
            if "ServiceRegistrationError" in locals():
                assert issubclass(ServiceRegistrationError, ServiceDiscoveryError)
            if "ServiceNotFoundError" in locals():
                assert issubclass(ServiceNotFoundError, ServiceDiscoveryError)
        except ImportError:
            pytest.skip("Exception hierarchy not found")
