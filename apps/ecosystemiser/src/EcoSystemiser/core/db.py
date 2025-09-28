"""
EcoSystemiser Core Database Service

This module extends the generic hive-db package with EcoSystemiser-specific
database functionality, following the inherit→extend pattern.
"""

from pathlib import Path
from contextlib import contextmanager
from typing import Optional
import os
import sqlite3

from hive_logging import get_logger
from hive_db import get_sqlite_connection, sqlite_transaction, create_table_if_not_exists

logger = get_logger(__name__)


def get_ecosystemiser_db_path() -> Path:
    """
    Get the path to the EcoSystemiser database.

    Returns:
        Path to ecosystemiser.db in the EcoSystemiser data directory
    """
    # Check for environment variable override
    db_path_env = os.environ.get('ECOSYSTEMISER_DB_PATH')
    if db_path_env:
        return Path(db_path_env)

    # Default to data directory relative to project root
    project_root = Path(__file__).parent.parent.parent.parent.parent
    data_dir = project_root / 'data' / 'ecosystemiser'
    data_dir.mkdir(parents=True, exist_ok=True)

    return data_dir / 'ecosystemiser.db'


@contextmanager
def get_ecosystemiser_connection():
    """
    Get a context-managed connection to the EcoSystemiser database.

    This is the core database service for EcoSystemiser, providing
    proper connection management with automated cleanup.

    Yields:
        sqlite3.Connection: Database connection with row factory enabled
    """
    db_path = get_ecosystemiser_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def ecosystemiser_transaction():
    """
    Context manager for EcoSystemiser database transactions.

    This provides transactional database operations with automatic
    commit/rollback handling for EcoSystemiser's dedicated database.

    Yields:
        sqlite3.Connection: Connection with transaction support
    """
    with get_ecosystemiser_connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"EcoSystemiser transaction failed: {e}")
            raise


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
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

    db_path = get_ecosystemiser_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def validate_ecosystemiser_database() -> bool:
    """
    Validate that the EcoSystemiser database is accessible and working.

    Returns:
        True if database is accessible, False otherwise
    """
    try:
        with get_ecosystemiser_connection() as conn:
            conn.execute('SELECT 1')
        logger.info("EcoSystemiser database validation successful")
        return True
    except Exception as e:
        logger.error(f"EcoSystemiser database validation failed: {e}")
        return False