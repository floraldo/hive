"""
EcoSystemiser database connection management.

This module provides database connection utilities specific to EcoSystemiser,
maintaining a separate database instance from other Hive components.
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
from EcoSystemiser.hive_logging_adapter import get_logger

logger = get_logger(__name__)


def get_ecosystemiser_db_path() -> Path:
    """
    Get the path to the EcoSystemiser database.

    Returns:
        Path to ecosystemiser.db
    """
    # Check for environment variable override
    db_path_env = os.environ.get('ECOSYSTEMISER_DB_PATH')
    if db_path_env:
        return Path(db_path_env)

    # Default to data directory relative to project root
    project_root = Path(__file__).parent.parent.parent.parent
    data_dir = project_root / 'data' / 'ecosystemiser'
    data_dir.mkdir(parents=True, exist_ok=True)

    return data_dir / 'ecosystemiser.db'


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Get a connection to the EcoSystemiser database.

    Args:
        db_path: Optional path to database. If None, uses default.

    Returns:
        SQLite connection with row factory enabled
    """
    if db_path is None:
        db_path = get_ecosystemiser_db_path()

    # Ensure the database directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # Enable column access by name

    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


@contextmanager
def ecosystemiser_transaction(db_path: Optional[Path] = None):
    """
    Context manager for EcoSystemiser database transactions.

    Args:
        db_path: Optional path to database

    Yields:
        SQLite connection with transaction
    """
    conn = get_db_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Transaction failed: {e}")
        raise
    finally:
        conn.close()


# DEPRECATED: Custom ConnectionPool class removed
# EcoSystemiser now uses the shared Hive database service for connection management.
# This provides better resource management, connection validation, and thread safety.
#
# For new code, use:
# - get_ecosystemiser_connection() for context-managed connections
# - ecosystemiser_transaction() for transactional operations
#
# These functions are available from EcoSystemiser.db and use the shared
# connection pooling service from hive-orchestrator/core/db.

# Legacy connection pool functionality has been moved to the shared service.
# If you need the old ConnectionPool interface, consider refactoring to use
# the new context manager approach for better resource management.