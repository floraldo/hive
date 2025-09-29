"""API foundation module for Hive applications."""

from .base_app import HiveApp, create_hive_app
from .health import add_health_endpoints
from .metrics import add_metrics_endpoints
from .middleware import setup_middleware

__all__ = ["create_hive_app", "HiveApp", "add_health_endpoints", "add_metrics_endpoints", "setup_middleware"]
