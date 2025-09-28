"""Service discovery specific exceptions."""


class ServiceDiscoveryError(Exception):
    """Base exception for service discovery errors."""

    def __init__(self, message: str, service_name: str = None, details: dict = None):
        super().__init__(message)
        self.service_name = service_name
        self.details = details or {}


class ServiceNotFoundError(ServiceDiscoveryError):
    """Raised when a requested service is not found."""
    pass


class ServiceRegistrationError(ServiceDiscoveryError):
    """Raised when service registration fails."""
    pass


class ServiceHealthError(ServiceDiscoveryError):
    """Raised when service health check fails."""
    pass


class LoadBalancerError(ServiceDiscoveryError):
    """Raised when load balancing operation fails."""
    pass


class ServiceTimeoutError(ServiceDiscoveryError):
    """Raised when service operation times out."""
    pass