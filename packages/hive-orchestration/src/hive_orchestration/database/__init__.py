"""
Database Layer for Hive Orchestration

Provides database schema, connection management, and core database operations
for the orchestration system.
"""

from hive_logging import get_logger

logger = get_logger(__name__)

from .operations import get_connection, transaction
from .schema import init_db

__all__ = [
    "init_db",
    "get_connection",
    "transaction",
]
