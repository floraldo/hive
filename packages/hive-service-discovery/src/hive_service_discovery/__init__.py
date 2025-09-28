"""
Hive Service Discovery - Intelligent service registry and load balancing.

This package provides service discovery capabilities for the Hive platform,
enabling automatic service registration, health monitoring, and intelligent
load balancing across distributed services.
"""

from .service_registry import ServiceRegistry, ServiceInfo
from .discovery_client import DiscoveryClient
from .load_balancer import LoadBalancer, LoadBalancingStrategy
from .health_monitor import HealthMonitor, HealthStatus
from .config import ServiceDiscoveryConfig
from .exceptions import (
    ServiceDiscoveryError,
    ServiceNotFoundError,
    ServiceRegistrationError,
    ServiceHealthError,
)

__version__ = "1.0.0"
__all__ = [
    "ServiceRegistry",
    "ServiceInfo",
    "DiscoveryClient",
    "LoadBalancer",
    "LoadBalancingStrategy",
    "HealthMonitor",
    "HealthStatus",
    "ServiceDiscoveryConfig",
    "ServiceDiscoveryError",
    "ServiceNotFoundError",
    "ServiceRegistrationError",
    "ServiceHealthError",
]