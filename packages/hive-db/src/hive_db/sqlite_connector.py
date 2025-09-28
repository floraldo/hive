"""
SQLite database connector for Hive applications.

Provides simple, reliable SQLite connectivity for development and lightweight production use.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from hive_logging import get_logger

logger = get_logger(__name__)


def get_sqlite_connection(
    db_path: Optional[str] = None, config: Optional[Dict[str, Any]] = None, **kwargs
) -> sqlite3.Connection:
    """
    Get a SQLite database connection.

    Args:
        db_path: Path to the SQLite database file (overrides config)
        config: Configuration dictionary with database settings
        **kwargs: Additional connection parameters

    Returns:
        SQLite connection object

    Raises:
        sqlite3.Error: If connection fails
        ValueError: If no database path is provided

    Config Structure:
        {
            'db_path': '/path/to/database.sqlite',
            'timeout': 30.0,
            'check_same_thread': False
        }
    """
    # If no config provided, create minimal config (db_path can be sufficient)
    if config is None:
        config = {}

    # Determine database path from parameter or config
    final_db_path = db_path or config.get("db_path")
    if not final_db_path:
        raise ValueError("Database path must be provided either directly or via config['db_path']")

    # Ensure parent directory exists
    db_file = Path(final_db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    # Default connection parameters for reliability
    defaults = {
        "timeout": config.get("timeout", 30.0),
        "check_same_thread": config.get("check_same_thread", False),
        "isolation_level": config.get("isolation_level", None),  # Autocommit mode
    }
    defaults.update(kwargs)

    try:
        conn = sqlite3.connect(final_db_path, **defaults)
        conn.row_factory = sqlite3.Row  # Enable row access by column name

        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")

        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys=ON")

        logger.info(f"SQLite connection established: {final_db_path}")
        return conn

    except sqlite3.Error as e:
        logger.error(f"Failed to connect to SQLite database {final_db_path}: {e}")
        raise


@contextmanager
def sqlite_transaction(db_path: Optional[str] = None, config: Optional[Dict[str, Any]] = None, **kwargs):
    """
    Context manager for SQLite transactions.

    Args:
        db_path: Path to the SQLite database file (overrides config)
        config: Configuration dictionary with database settings
        **kwargs: Additional connection parameters

    Yields:
        SQLite connection in transaction mode

    Example:
        config = {'db_path': '/path/to/db.sqlite'}
        with sqlite_transaction(config=config) as conn:
            conn.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
            conn.execute("INSERT INTO users (name) VALUES (?)", ("Bob",))
            # Transaction commits automatically on success
    """
    conn = None
    try:
        conn = get_sqlite_connection(db_path, config, **kwargs)
        conn.execute("BEGIN")
        yield conn
        conn.commit()
        logger.debug("SQLite transaction committed")

    except Exception as e:
        if conn:
            conn.rollback()
            logger.error(f"SQLite transaction rolled back: {e}")
        raise

    finally:
        if conn:
            conn.close()


# Convenience aliases
connect = get_sqlite_connection
transaction = sqlite_transaction
