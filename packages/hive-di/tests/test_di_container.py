"""
Test suite for the dependency injection container

Tests all aspects of the DI container including service registration,
resolution, lifecycle management, and error handling.
"""

import pytest
import threading
import time
from typing import Optional
from unittest.mock import Mock, patch

from hive_di.container import DIContainer, Lifecycle
from hive_di.exceptions import (
    ServiceNotRegisteredException,
    CircularDependencyException,
    ServiceRegistrationException,
    ServiceCreationException
)


# Test classes for dependency injection
class TestInterface:
    """Test interface"""
    def get_value(self) -> str:
        pass


class TestService(TestInterface):
    """Simple test service"""
    def __init__(self, value: str = "test"):
        self.value = value

    def get_value(self) -> str:
        return self.value


class DependentService:
    """Service that depends on TestInterface"""
    def __init__(self, dependency: TestInterface):
        self.dependency = dependency

    def get_dependent_value(self) -> str:
        return f"dependent:{self.dependency.get_value()}"


class CircularServiceA:
    """Service A for circular dependency testing"""
    def __init__(self, service_b: 'CircularServiceB'):
        self.service_b = service_b


class CircularServiceB:
    """Service B for circular dependency testing"""
    def __init__(self, service_a: CircularServiceA):
        self.service_a = service_a


class DisposableService:
    """Service that implements disposal"""
    def __init__(self):
        self.disposed = False

    def dispose(self):
        self.disposed = True


class TestDIContainer:
    """Test the dependency injection container"""

    def test_container_creation(self):
        """Test basic container creation"""
        container = DIContainer()
        assert container is not None
        assert len(container.get_registrations()) == 0

    def test_register_simple_service(self):
        """Test registering a simple service"""
        container = DIContainer()
        container.register(TestInterface, TestService)

        registrations = container.get_registrations()
        assert TestInterface in registrations
        assert registrations[TestInterface].service_type == TestInterface
        assert registrations[TestInterface].implementation_type == TestService
        assert registrations[TestInterface].lifecycle == Lifecycle.TRANSIENT

    def test_register_singleton_service(self):
        """Test registering a singleton service"""
        container = DIContainer()
        container.register_singleton(TestInterface, TestService)

        registrations = container.get_registrations()
        assert registrations[TestInterface].lifecycle == Lifecycle.SINGLETON

    def test_register_with_factory(self):
        """Test registering a service with factory function"""
        def create_service() -> TestInterface:
            return TestService("factory_created")

        container = DIContainer()
        container.register(TestInterface, factory=create_service)

        service = container.resolve(TestInterface)
        assert isinstance(service, TestService)
        assert service.get_value() == "factory_created"

    def test_register_instance(self):
        """Test registering a pre-created instance"""
        instance = TestService("pre_created")
        container = DIContainer()
        container.register_instance(TestInterface, instance)

        service = container.resolve(TestInterface)
        assert service is instance
        assert service.get_value() == "pre_created"

    def test_resolve_simple_service(self):
        """Test resolving a simple service"""
        container = DIContainer()
        container.register(TestInterface, TestService)

        service = container.resolve(TestInterface)
        assert isinstance(service, TestService)
        assert service.get_value() == "test"

    def test_resolve_dependency_injection(self):
        """Test resolving service with dependencies"""
        container = DIContainer()
        container.register(TestInterface, TestService)
        container.register(DependentService, DependentService)

        service = container.resolve(DependentService)
        assert isinstance(service, DependentService)
        assert service.get_dependent_value() == "dependent:test"

    def test_singleton_lifecycle(self):
        """Test singleton lifecycle behavior"""
        container = DIContainer()
        container.register_singleton(TestInterface, TestService)

        service1 = container.resolve(TestInterface)
        service2 = container.resolve(TestInterface)

        assert service1 is service2  # Same instance

    def test_transient_lifecycle(self):
        """Test transient lifecycle behavior"""
        container = DIContainer()
        container.register_transient(TestInterface, TestService)

        service1 = container.resolve(TestInterface)
        service2 = container.resolve(TestInterface)

        assert service1 is not service2  # Different instances
        assert isinstance(service1, TestService)
        assert isinstance(service2, TestService)

    def test_service_not_registered_exception(self):
        """Test exception when resolving unregistered service"""
        container = DIContainer()

        with pytest.raises(ServiceNotRegisteredException) as exc_info:
            container.resolve(TestInterface)

        assert exc_info.value.service_type == TestInterface

    def test_circular_dependency_detection(self):
        """Test circular dependency detection"""
        container = DIContainer()
        container.register(CircularServiceA, CircularServiceA)
        container.register(CircularServiceB, CircularServiceB)

        with pytest.raises(CircularDependencyException) as exc_info:
            container.resolve(CircularServiceA)

        assert CircularServiceA in exc_info.value.dependency_chain
        assert CircularServiceB in exc_info.value.dependency_chain

    def test_service_registration_exception(self):
        """Test service registration validation"""
        container = DIContainer()
        instance = TestService()

        with pytest.raises(ServiceRegistrationException):
            container.register(
                TestInterface,
                implementation=TestService,
                factory=lambda: TestService(),
                instance=instance
            )

    def test_service_creation_exception(self):
        """Test service creation error handling"""
        def failing_factory():
            raise ValueError("Factory failed")

        container = DIContainer()
        container.register(TestInterface, factory=failing_factory)

        with pytest.raises(ServiceCreationException) as exc_info:
            container.resolve(TestInterface)

        assert exc_info.value.service_type == TestInterface
        assert isinstance(exc_info.value.cause, ValueError)

    def test_optional_dependencies(self):
        """Test handling of optional dependencies"""
        class OptionalDependentService:
            def __init__(self, required: TestInterface, optional: Optional[str] = None):
                self.required = required
                self.optional = optional or "default"

        container = DIContainer()
        container.register(TestInterface, TestService)
        container.register(OptionalDependentService, OptionalDependentService)

        service = container.resolve(OptionalDependentService)
        assert isinstance(service.required, TestService)
        assert service.optional == "default"

    def test_thread_safety(self):
        """Test thread safety of container operations"""
        container = DIContainer()
        container.register_singleton(TestInterface, TestService)

        results = []
        errors = []

        def resolve_service():
            try:
                service = container.resolve(TestInterface)
                results.append(service)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=resolve_service)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify results
        assert len(errors) == 0
        assert len(results) == 10
        # All results should be the same instance (singleton)
        for result in results:
            assert result is results[0]

    def test_container_disposal(self):
        """Test container disposal and cleanup"""
        container = DIContainer()
        disposable_service = DisposableService()
        container.register_instance(DisposableService, disposable_service)

        # Resolve service
        resolved = container.resolve(DisposableService)
        assert resolved is disposable_service
        assert not disposable_service.disposed

        # Dispose container
        container.dispose()
        assert disposable_service.disposed

    def test_context_manager(self):
        """Test container as context manager"""
        disposable_service = DisposableService()

        with DIContainer() as container:
            container.register_instance(DisposableService, disposable_service)
            resolved = container.resolve(DisposableService)
            assert resolved is disposable_service
            assert not disposable_service.disposed

        # Should be disposed after context exit
        assert disposable_service.disposed

    def test_clear_singletons(self):
        """Test clearing singleton instances"""
        container = DIContainer()
        container.register_singleton(TestInterface, TestService)

        # Resolve once
        service1 = container.resolve(TestInterface)

        # Clear singletons
        container.clear_singletons()

        # Resolve again - should get new instance
        service2 = container.resolve(TestInterface)

        assert service1 is not service2
        assert isinstance(service1, TestService)
        assert isinstance(service2, TestService)

    def test_child_container(self):
        """Test child container inheritance"""
        parent = DIContainer()
        parent.register_singleton(TestInterface, TestService)

        child = parent.create_child_container()

        # Child should inherit registrations but get fresh instances
        parent_service = parent.resolve(TestInterface)
        child_service = child.resolve(TestInterface)

        assert parent_service is not child_service
        assert isinstance(parent_service, TestService)
        assert isinstance(child_service, TestService)

    def test_is_registered(self):
        """Test checking if service is registered"""
        container = DIContainer()

        assert not container.is_registered(TestInterface)

        container.register(TestInterface, TestService)

        assert container.is_registered(TestInterface)

    def test_method_chaining(self):
        """Test method chaining for registration"""
        container = DIContainer()

        result = (container
                 .register(TestInterface, TestService)
                 .register_singleton(DependentService, DependentService))

        assert result is container
        assert container.is_registered(TestInterface)
        assert container.is_registered(DependentService)

    def test_complex_dependency_graph(self):
        """Test complex dependency resolution"""
        class ServiceA:
            def __init__(self, b: 'ServiceB', c: 'ServiceC'):
                self.b = b
                self.c = c

        class ServiceB:
            def __init__(self, c: 'ServiceC'):
                self.c = c

        class ServiceC:
            def __init__(self):
                pass

        container = DIContainer()
        container.register(ServiceA, ServiceA)
        container.register(ServiceB, ServiceB)
        container.register(ServiceC, ServiceC)

        service_a = container.resolve(ServiceA)

        assert isinstance(service_a, ServiceA)
        assert isinstance(service_a.b, ServiceB)
        assert isinstance(service_a.c, ServiceC)
        assert isinstance(service_a.b.c, ServiceC)
        # B and A should have different instances of C (transient)
        assert service_a.c is not service_a.b.c


if __name__ == "__main__":
    pytest.main([__file__])