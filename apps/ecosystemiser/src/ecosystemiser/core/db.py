"""
EcoSystemiser Core Database Service.

This module extends the generic hive-db package with EcoSystemiser-specific
database functionality, following the inherit→extend pattern.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from hive_db import get_sqlite_connection, sqlite_transaction
from hive_logging import get_logger

logger = get_logger(__name__)


def get_ecosystemiser_db_path() -> Path:
    """
    Get the path to the EcoSystemiser database.

    Returns:
        Path to ecosystemiser.db in the EcoSystemiser data directory.
    """
    # Check for environment variable override
    db_path_env = os.environ.get("ECOSYSTEMISER_DB_PATH")
    if db_path_env:
        return Path(db_path_env)

    # Default to data directory relative to project root
    project_root = Path(__file__).parent.parent.parent.parent.parent
    data_dir = project_root / "data" / "ecosystemiser"
    data_dir.mkdir(parents=True, exist_ok=True)

    return data_dir / "ecosystemiser.db"


@contextmanager
def get_ecosystemiser_connection():
    """
    Get a context-managed connection to the EcoSystemiser database.

    This extends hive_db's get_sqlite_connection with EcoSystemiser-specific
    configuration and path management.

    Yields:
        sqlite3.Connection: Database connection with row factory enabled.
    """
    db_path = get_ecosystemiser_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Use hive_db's connection manager with EcoSystemiser's path
    with get_sqlite_connection(str(db_path)) as conn:
        # Enable foreign keys for data integrity
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn


@contextmanager
def ecosystemiser_transaction():
    """
    Context manager for EcoSystemiser database transactions.

    This extends hive_db's sqlite_transaction with EcoSystemiser-specific
    database path and configuration.

    Yields:
        sqlite3.Connection: Connection with transaction support.
    """
    db_path = get_ecosystemiser_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Use hive_db's transaction manager
    with sqlite_transaction(str(db_path)) as conn:
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        except Exception as e:
            logger.error(f"EcoSystemiser transaction failed: {e}")
            raise


def get_db_connection(db_path: Path | None = None):
    """
    Legacy direct connection function.

    Args:
        db_path: Optional path to database (ignored, uses configured path)

    Returns:
        Direct SQLite connection

    Note:
        This function is provided for backward compatibility.
        Use get_ecosystemiser_connection() context manager for new code.
    """
    logger.warning("Direct connection requested - consider using context managers")
    actual_db_path = get_ecosystemiser_db_path()
    actual_db_path.parent.mkdir(parents=True, exist_ok=True)

    # Use hive_db's connection, but return it directly (not context-managed)
    # This maintains backward compatibility while using hive_db under the hood
    import sqlite3

    conn = sqlite3.connect(str(actual_db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def validate_ecosystemiser_database() -> bool:
    """
    Validate that the EcoSystemiser database is accessible and working.

    Returns:
        True if database is accessible, False otherwise.
    """
    try:
        with get_ecosystemiser_connection() as conn:
            conn.execute("SELECT 1")
        logger.info("EcoSystemiser database validation successful")
        return True
    except Exception as e:
        logger.error(f"EcoSystemiser database validation failed: {e}")
        return False
