from hive_errors import BaseError
from hive_logging import get_logger

logger = get_logger(__name__)


"""Service discovery specific exceptions."""


class ServiceDiscoveryError(Exception):
    """Base exception for service discovery errors."""

    def __init__(self, message: str, service_name: str = None, details: dict = None) -> None:
        super().__init__(message)
        self.service_name = service_name
        self.details = details or {}


class ServiceNotFoundError(BaseError):
    """Raised when a requested service is not found."""



class ServiceRegistrationError(BaseError):
    """Raised when service registration fails."""



class ServiceHealthError(BaseError):
    """Raised when service health check fails."""



class LoadBalancerError(BaseError):
    """Raised when load balancing operation fails."""



class ServiceTimeoutError(BaseError):
    """Raised when service operation times out."""

