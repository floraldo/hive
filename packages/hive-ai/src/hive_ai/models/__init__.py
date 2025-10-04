from hive_logging import get_logger

logger = get_logger(__name__)

"""
Model Management System for Hive AI.

Provides unified interface for AI model operations with
multi-provider support, connection pooling, and metrics.
"""

from .client import ModelClient
from .metrics import ModelMetrics, ModelPerformanceStats, ModelUsageRecord
from .pool import ModelPool, PoolStats
from .registry import ModelRegistry

__all__ = [
    "ModelClient",
    "ModelMetrics",
    "ModelPerformanceStats",
    "ModelPool",
    # Core model management
    "ModelRegistry",
    "ModelUsageRecord",
    # Data classes and statistics
    "PoolStats",
]
