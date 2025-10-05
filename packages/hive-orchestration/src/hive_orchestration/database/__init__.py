"""Database Layer for Hive Orchestration

Provides database schema, connection management, and core database operations
for the orchestration system.
"""

from hive_logging import get_logger

logger = get_logger(__name__)

# Dual-write repository for safe migration
from .dual_writer import DualWriteTaskRepository
from .operations import get_connection, transaction
from .schema import init_db

# Unified schema models for migration
from .unified_schema import (
    TaskStatus,
    TaskType,
    UnifiedDeploymentTask,
    UnifiedReviewTask,
    UnifiedTask,
    UnifiedWorkflowTask,
)

__all__ = [
    "get_connection",
    "init_db",
    "transaction",
    # Unified schema
    "UnifiedTask",
    "UnifiedReviewTask",
    "UnifiedWorkflowTask",
    "UnifiedDeploymentTask",
    "TaskStatus",
    "TaskType",
    # Migration infrastructure
    "DualWriteTaskRepository",
]
