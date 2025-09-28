"""
Dependency Injection Container

A lightweight, thread-safe dependency injection container that supports:
- Multiple lifecycle patterns (singleton, transient, scoped)
- Automatic dependency resolution
- Circular dependency detection
- Factory-based service creation
- Easy testing and mocking support
"""

import threading
import inspect
from enum import Enum
from typing import Type, TypeVar, Dict, Any, Callable, Optional, Set, List
from dataclasses import dataclass

from .exceptions import (
    ServiceNotRegisteredException,
    CircularDependencyException,
    ServiceRegistrationException,
    ServiceCreationException,
    InvalidLifecycleException
)

T = TypeVar('T')


class Lifecycle(Enum):
    """Service lifecycle management options"""
    SINGLETON = "singleton"      # One instance per container
    TRANSIENT = "transient"      # New instance every time
    SCOPED = "scoped"           # One instance per scope (useful for request scoping)


@dataclass
class ServiceRegistration:
    """Registration information for a service"""
    service_type: Type
    implementation_type: Optional[Type]
    factory: Optional[Callable[..., Any]]
    lifecycle: Lifecycle
    instance: Optional[Any] = None


class DIContainer:
    """
    Lightweight dependency injection container

    Provides service registration, resolution, and lifecycle management
    with support for automatic dependency injection and circular dependency detection.
    """

    def __init__(self):
        """Initialize a new DI container"""
        self._services: Dict[Type, ServiceRegistration] = {}
        self._lock = threading.RLock()  # Reentrant lock for nested resolution
        self._resolving: Set[Type] = set()  # Track services being resolved (circular dependency detection)

    def register(self,
                 service_type: Type[T],
                 implementation: Optional[Type[T]] = None,
                 factory: Optional[Callable[..., T]] = None,
                 lifecycle: Lifecycle = Lifecycle.TRANSIENT,
                 instance: Optional[T] = None) -> 'DIContainer':
        """
        Register a service with the container

        Args:
            service_type: The type/interface to register
            implementation: The implementation class (if different from service_type)
            factory: Factory function to create instances
            lifecycle: Lifecycle management for the service
            instance: Pre-created instance (forces SINGLETON lifecycle)

        Returns:
            Self for method chaining

        Raises:
            ServiceRegistrationException: If registration fails
        """
        with self._lock:
            # Validate registration parameters
            if instance is not None:
                if lifecycle != Lifecycle.SINGLETON:
                    lifecycle = Lifecycle.SINGLETON
                if factory is not None or implementation is not None:
                    raise ServiceRegistrationException(
                        service_type,
                        "Cannot specify factory or implementation when providing instance"
                    )
            elif factory is None and implementation is None:
                # Use service_type as implementation if no other option provided
                implementation = service_type

            # Validate lifecycle
            if not isinstance(lifecycle, Lifecycle):
                raise InvalidLifecycleException(str(lifecycle))

            # Store registration
            registration = ServiceRegistration(
                service_type=service_type,
                implementation_type=implementation,
                factory=factory,
                lifecycle=lifecycle,
                instance=instance
            )

            self._services[service_type] = registration
            return self

    def register_singleton(self, service_type: Type[T], implementation: Optional[Type[T]] = None,
                          factory: Optional[Callable[..., T]] = None) -> 'DIContainer':
        """Convenience method to register a singleton service"""
        return self.register(service_type, implementation, factory, Lifecycle.SINGLETON)

    def register_transient(self, service_type: Type[T], implementation: Optional[Type[T]] = None,
                          factory: Optional[Callable[..., T]] = None) -> 'DIContainer':
        """Convenience method to register a transient service"""
        return self.register(service_type, implementation, factory, Lifecycle.TRANSIENT)

    def register_instance(self, service_type: Type[T], instance: T) -> 'DIContainer':
        """Convenience method to register a pre-created instance"""
        return self.register(service_type, instance=instance)

    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve a service instance

        Args:
            service_type: The type to resolve

        Returns:
            Instance of the requested service

        Raises:
            ServiceNotRegisteredException: If service is not registered
            CircularDependencyException: If circular dependency is detected
            ServiceCreationException: If instance creation fails
        """
        with self._lock:
            return self._resolve_internal(service_type)

    def _resolve_internal(self, service_type: Type[T]) -> T:
        """Internal resolution method with circular dependency tracking"""
        # Check if service is registered
        if service_type not in self._services:
            raise ServiceNotRegisteredException(service_type)

        # Check for circular dependency
        if service_type in self._resolving:
            dependency_chain = list(self._resolving) + [service_type]
            raise CircularDependencyException(dependency_chain)

        registration = self._services[service_type]

        # Return existing singleton instance if available
        if registration.lifecycle == Lifecycle.SINGLETON and registration.instance is not None:
            return registration.instance

        # Mark as resolving for circular dependency detection
        self._resolving.add(service_type)

        try:
            instance = self._create_instance(registration)

            # Store singleton instance
            if registration.lifecycle == Lifecycle.SINGLETON:
                registration.instance = instance

            return instance

        except Exception as e:
            raise ServiceCreationException(service_type, e)
        finally:
            # Always remove from resolving set
            self._resolving.discard(service_type)

    def _create_instance(self, registration: ServiceRegistration):
        """Create a new instance of a service"""
        if registration.factory is not None:
            # Use factory function
            return self._call_with_injection(registration.factory)
        elif registration.implementation_type is not None:
            # Use implementation class constructor
            return self._call_with_injection(registration.implementation_type)
        else:
            raise ServiceCreationException(
                registration.service_type,
                Exception("No factory or implementation specified")
            )

    def _call_with_injection(self, callable_obj: Callable) -> Any:
        """Call a function/constructor with dependency injection"""
        # Get signature and annotations
        sig = inspect.signature(callable_obj)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            # Skip self parameter
            if param_name == 'self':
                continue

            # Get type annotation
            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                # No type annotation, skip injection
                continue

            # Check if we have a default value
            if param.default != inspect.Parameter.empty:
                # Has default, resolve if available, otherwise use default
                if param_type in self._services:
                    kwargs[param_name] = self._resolve_internal(param_type)
                # else: use default value (don't add to kwargs)
            else:
                # No default, must resolve
                kwargs[param_name] = self._resolve_internal(param_type)

        return callable_obj(**kwargs)

    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered"""
        with self._lock:
            return service_type in self._services

    def get_registrations(self) -> Dict[Type, ServiceRegistration]:
        """Get all service registrations (for debugging/testing)"""
        with self._lock:
            return self._services.copy()

    def clear_singletons(self) -> None:
        """Clear all singleton instances (useful for testing)"""
        with self._lock:
            for registration in self._services.values():
                if registration.lifecycle == Lifecycle.SINGLETON:
                    registration.instance = None

    def dispose(self) -> None:
        """Dispose of the container and clean up resources"""
        with self._lock:
            # Call dispose on any services that support it
            for registration in self._services.values():
                if registration.instance is not None:
                    instance = registration.instance
                    if hasattr(instance, 'dispose'):
                        try:
                            instance.dispose()
                        except Exception:
                            # Ignore disposal errors
                            pass

            # Clear all registrations
            self._services.clear()
            self._resolving.clear()

    def create_child_container(self) -> 'DIContainer':
        """Create a child container that inherits parent registrations"""
        child = DIContainer()
        with self._lock:
            # Copy registrations but not instances (child gets fresh instances)
            for service_type, registration in self._services.items():
                child_registration = ServiceRegistration(
                    service_type=registration.service_type,
                    implementation_type=registration.implementation_type,
                    factory=registration.factory,
                    lifecycle=registration.lifecycle,
                    instance=None  # Child container gets fresh instances
                )
                child._services[service_type] = child_registration
        return child

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - dispose of container"""
        self.dispose()