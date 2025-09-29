"""
Hive Application Toolkit - Production-grade development accelerator.

Strategic Force Multiplier for the Hive Platform.
"""

__version__ = "1.0.0"
__author__ = "Hive Team"

# Core exports for easy importing
from .api.base_app import create_hive_app
from .config.app_config import HiveAppConfig
from .cost.cost_manager import CostManager
from .cost.rate_limiter import RateLimiter

__all__ = ["create_hive_app", "HiveAppConfig", "CostManager", "RateLimiter"]
