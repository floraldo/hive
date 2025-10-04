"""
Hive Application Toolkit - Production-grade development accelerator.

Strategic Force Multiplier for the Hive Platform.
"""

__version__ = "1.0.0"
__author__ = "Hive Team"

# Core exports for easy importing
from .api.base_app import create_hive_app
from .base_application import BaseApplication
from .config.app_config import HiveAppConfig

# from .cost.cost_manager import CostManager  # Temporarily disabled
# from .cost.rate_limiter import RateLimiter  # Temporarily disabled

__all__ = [
    "BaseApplication",  # Project Launchpad - unified application lifecycle
    "create_hive_app",  # FastAPI app factory
    "HiveAppConfig",  # Configuration dataclass
]  # CostManager and RateLimiter temp disabled
