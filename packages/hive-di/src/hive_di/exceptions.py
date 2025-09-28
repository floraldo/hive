"""
Dependency Injection Exception Classes

Custom exceptions for the DI container to provide clear error messages
and proper error handling during service resolution and registration.
"""

from typing import Type, List


class DIException(Exception):
    """Base exception for dependency injection errors"""
    pass


class ServiceNotRegisteredException(DIException):
    """Raised when attempting to resolve a service that hasn't been registered"""

    def __init__(self, service_type: Type):
        self.service_type = service_type
        super().__init__(f"Service {service_type.__name__} is not registered in the container")


class CircularDependencyException(DIException):
    """Raised when a circular dependency is detected during service resolution"""

    def __init__(self, dependency_chain: List[Type]):
        self.dependency_chain = dependency_chain
        chain_names = " -> ".join(t.__name__ for t in dependency_chain)
        super().__init__(f"Circular dependency detected: {chain_names}")


class ServiceRegistrationException(DIException):
    """Raised when there's an error during service registration"""

    def __init__(self, service_type: Type, reason: str):
        self.service_type = service_type
        self.reason = reason
        super().__init__(f"Failed to register service {service_type.__name__}: {reason}")


class ServiceCreationException(DIException):
    """Raised when there's an error creating a service instance"""

    def __init__(self, service_type: Type, cause: Exception):
        self.service_type = service_type
        self.cause = cause
        super().__init__(f"Failed to create instance of {service_type.__name__}: {str(cause)}")


class InvalidLifecycleException(DIException):
    """Raised when an invalid lifecycle is specified"""

    def __init__(self, lifecycle: str):
        self.lifecycle = lifecycle
        super().__init__(f"Invalid lifecycle: {lifecycle}")