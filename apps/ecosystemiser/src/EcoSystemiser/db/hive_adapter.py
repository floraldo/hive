"""
Hive Database Adapter for EcoSystemiser

This module provides EcoSystemiser with access to the shared Hive database
connection service while maintaining EcoSystemiser's database isolation.
"""

from pathlib import Path
from contextlib import contextmanager
from typing import Optional
import os

from EcoSystemiser.hive_logging_adapter import get_logger

# Import the shared database service from hive-orchestrator
try:
    from hive_orchestrator.core.db import get_database_connection
    HIVE_DB_AVAILABLE = True
except ImportError:
    HIVE_DB_AVAILABLE = False

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


@contextmanager
def get_ecosystemiser_connection():
    """
    Get a connection to the EcoSystemiser database using the shared service.

    This replaces the old get_db_connection and ecosystemiser_transaction functions
    with a unified interface that uses the Hive shared database service.

    Yields:
        sqlite3.Connection: Connection with proper connection pooling and cleanup
    """
    if not HIVE_DB_AVAILABLE:
        # Fallback to direct connection if Hive DB service is not available
        logger.warning("Hive database service not available, falling back to direct connection")
        import sqlite3
        db_path = get_ecosystemiser_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            yield conn
        finally:
            conn.close()
        return

    # Use the shared database service
    db_path = get_ecosystemiser_db_path()

    with get_database_connection("ecosystemiser", db_path) as conn:
        yield conn


@contextmanager
def ecosystemiser_transaction():
    """
    Context manager for EcoSystemiser database transactions.

    This provides the same interface as the old ecosystemiser_transaction
    but uses the shared database service for connection management.

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


def get_db_connection(db_path: Optional[Path] = None):
    """
    Legacy compatibility function for EcoSystemiser components.

    Args:
        db_path: Optional path to database (ignored, uses configured path)

    Returns:
        Direct connection (not recommended, use context managers instead)

    Note:
        This function is provided for backward compatibility but direct
        connection usage is discouraged. Use get_ecosystemiser_connection()
        or ecosystemiser_transaction() context managers instead.
    """
    if not HIVE_DB_AVAILABLE:
        logger.warning("Using legacy direct connection - consider migrating to context managers")
        import sqlite3
        db_path = get_ecosystemiser_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # This is not ideal but provides compatibility
    logger.warning("Direct connection requested - consider using context managers for better resource management")
    import sqlite3
    db_path = get_ecosystemiser_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def validate_hive_integration() -> bool:
    """
    Validate that the Hive database integration is working correctly.

    Returns:
        True if integration is working, False otherwise
    """
    try:
        with get_ecosystemiser_connection() as conn:
            conn.execute('SELECT 1')
        logger.info("Hive database integration validated successfully")
        return True
    except Exception as e:
        logger.error(f"Hive database integration validation failed: {e}")
        return False