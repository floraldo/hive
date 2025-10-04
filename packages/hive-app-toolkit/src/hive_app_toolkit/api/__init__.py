"""API foundation module for Hive applications."""

from .base_app import HiveApp, create_hive_app
from .health import BaseHealthMonitor, HealthCheckResult, HealthStatusLevel, add_health_endpoints

# TODO: metrics and middleware modules not yet implemented
# from .metrics import add_metrics_endpoints
# from .middleware import setup_middleware

__all__ = [
    # "add_metrics_endpoints",  # TODO: implement metrics module
    # "setup_middleware",  # TODO: implement middleware module
    "BaseHealthMonitor",
    "HealthCheckResult",
    "HealthStatusLevel",
    "HiveApp",
    "add_health_endpoints",
    "create_hive_app",
]
