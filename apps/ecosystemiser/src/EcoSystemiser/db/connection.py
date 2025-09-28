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


class ConnectionPool:
    """
    Simple connection pool for EcoSystemiser database.

    This manages a pool of database connections to improve performance
    for multi-threaded operations.
    """

    def __init__(self, pool_size: int = 5):
        """
        Initialize connection pool.

        Args:
            pool_size: Maximum number of connections in pool
        """
        self.pool_size = pool_size
        self.connections = []
        self.db_path = get_ecosystemiser_db_path()

    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool or create a new one."""
        if self.connections:
            return self.connections.pop()
        return get_db_connection(self.db_path)

    def return_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        if len(self.connections) < self.pool_size:
            self.connections.append(conn)
        else:
            conn.close()

    def close_all(self):
        """Close all connections in the pool."""
        while self.connections:
            conn = self.connections.pop()
            conn.close()


# Global connection pool instance
_connection_pool = None


def get_connection_pool() -> ConnectionPool:
    """Get the global connection pool instance."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool()
    return _connection_pool