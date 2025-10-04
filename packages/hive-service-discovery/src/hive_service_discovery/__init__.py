from hive_logging import get_logger

logger = get_logger(__name__)

"""
Hive Service Discovery - Intelligent service registry and load balancing.

This package provides service discovery capabilities for the Hive platform,
enabling automatic service registration, health monitoring, and intelligent
load balancing across distributed services.
"""

from .config import ServiceDiscoveryConfig
from .discovery_client import DiscoveryClient
from .exceptions import ServiceDiscoveryError, ServiceHealthError, ServiceNotFoundError, ServiceRegistrationError
from .health_monitor import HealthMonitor, HealthStatus
from .load_balancer import LoadBalancer, LoadBalancingStrategy
from .service_registry import ServiceInfo, ServiceRegistry

__version__ = "1.0.0"
__all__ = [
    "DiscoveryClient",
    "HealthMonitor",
    "HealthStatus",
    "LoadBalancer",
    "LoadBalancingStrategy",
    "ServiceDiscoveryConfig",
    "ServiceDiscoveryError",
    "ServiceHealthError",
    "ServiceInfo",
    "ServiceNotFoundError",
    "ServiceRegistrationError",
    "ServiceRegistry",
]
