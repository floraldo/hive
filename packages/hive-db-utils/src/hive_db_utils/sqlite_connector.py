"""
SQLite database connector for Hive applications.

Provides simple, reliable SQLite connectivity for development and lightweight production use.
"""

import sqlite3
from hive_logging import get_logger
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = get_logger(__name__)


def get_sqlite_connection(db_path: str, **kwargs) -> sqlite3.Connection:
    """
    Get a SQLite database connection.

    Args:
        db_path: Path to the SQLite database file
        **kwargs: Additional connection parameters

    Returns:
        SQLite connection object

    Raises:
        sqlite3.Error: If connection fails
    """
    # Ensure parent directory exists
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    # Default connection parameters for reliability
    defaults = {
        'timeout': 30.0,
        'check_same_thread': False,
        'isolation_level': None  # Autocommit mode
    }
    defaults.update(kwargs)

    try:
        conn = sqlite3.connect(db_path, **defaults)
        conn.row_factory = sqlite3.Row  # Enable row access by column name

        # Enable WAL mode for better concurrency
        conn.execute('PRAGMA journal_mode=WAL')

        # Enable foreign key constraints
        conn.execute('PRAGMA foreign_keys=ON')

        logger.info(f"SQLite connection established: {db_path}")
        return conn

    except sqlite3.Error as e:
        logger.error(f"Failed to connect to SQLite database {db_path}: {e}")
        raise


@contextmanager
def sqlite_transaction(db_path: str, **kwargs):
    """
    Context manager for SQLite transactions.

    Args:
        db_path: Path to the SQLite database file
        **kwargs: Additional connection parameters

    Yields:
        SQLite connection in transaction mode

    Example:
        with sqlite_transaction("/path/to/db.sqlite") as conn:
            conn.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
            conn.execute("INSERT INTO users (name) VALUES (?)", ("Bob",))
            # Transaction commits automatically on success
    """
    conn = None
    try:
        conn = get_sqlite_connection(db_path, **kwargs)
        conn.execute('BEGIN')
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


def create_table_if_not_exists(conn: sqlite3.Connection, table_name: str, schema: str) -> None:
    """
    Create a table if it doesn't exist.

    Args:
        conn: SQLite connection
        table_name: Name of the table to create
        schema: SQL schema definition for the table

    Example:
        schema = '''
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        '''
        create_table_if_not_exists(conn, "users", schema)
    """
    try:
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})"
        conn.execute(sql)
        logger.debug(f"Table {table_name} created or verified")

    except sqlite3.Error as e:
        logger.error(f"Failed to create table {table_name}: {e}")
        raise


def get_sqlite_info(db_path: str) -> Dict[str, Any]:
    """
    Get information about a SQLite database.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Dictionary with database information
    """
    try:
        with sqlite_transaction(db_path) as conn:
            # Get database size
            db_file = Path(db_path)
            file_size = db_file.stat().st_size if db_file.exists() else 0

            # Get table count
            cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]

            # Get SQLite version
            cursor = conn.execute("SELECT sqlite_version()")
            sqlite_version = cursor.fetchone()[0]

            return {
                'db_path': str(db_path),
                'file_size_bytes': file_size,
                'table_count': table_count,
                'sqlite_version': sqlite_version,
                'exists': db_file.exists()
            }

    except sqlite3.Error as e:
        logger.error(f"Failed to get SQLite info for {db_path}: {e}")
        raise


# Convenience aliases
connect = get_sqlite_connection
transaction = sqlite_transaction
create_table = create_table_if_not_exists
info = get_sqlite_info