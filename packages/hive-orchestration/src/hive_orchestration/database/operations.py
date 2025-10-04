"""Database Operations for Hive Orchestration

Provides connection management and transaction utilities.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any

from hive_db import get_sqlite_connection
from hive_logging import get_logger

logger = get_logger(__name__)


def _get_default_db_path() -> Path:
    """Get the default database path for orchestration.

    Returns:
        Path: Path to hive-internal.db in the hive/db directory

    """
    # Default to hive/db/hive-internal.db (same as orchestrator)
    base_dir = Path.cwd()

    # Try to find hive directory
    if (base_dir / "db").exists():
        db_dir = base_dir / "db"
    elif (base_dir.parent / "db").exists():
        db_dir = base_dir.parent / "db"
    else:
        # Create db directory if it doesn't exist
        db_dir = base_dir / "db"
        db_dir.mkdir(parents=True, exist_ok=True)

    db_path = db_dir / "hive-internal.db"
    logger.debug(f"Using orchestration database: {db_path}")
    return db_path


@contextmanager
def get_connection(db_path: str | Path | None = None):
    """Get a database connection for orchestration operations.

    Args:
        db_path: Optional database path. If not provided, uses default hive-internal.db

    Yields:
        sqlite3.Connection: Database connection

    Example:
        >>> with get_connection() as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT * FROM tasks")

    """
    if db_path is None:
        db_path = _get_default_db_path()

    with get_sqlite_connection(str(db_path)) as conn:
        yield conn


@contextmanager
def transaction(db_path: str | Path | None = None):
    """Database transaction context manager.

    Automatically commits on success or rolls back on error.

    Args:
        db_path: Optional database path

    Yields:
        sqlite3.Connection: Database connection in transaction

    Example:
        >>> with transaction() as conn:
        ...     conn.execute("INSERT INTO tasks ...")
        ...     # Auto-commits on exit, rolls back on exception

    """
    with get_connection(db_path) as conn:
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back: {e}")
            raise


def _row_to_dict(cursor, row) -> dict[str, Any]:
    """Convert a database row to a dictionary.

    Args:
        cursor: Database cursor with description
        row: Database row tuple

    Returns:
        dict: Row as dictionary with column names as keys

    """
    if row is None:
        return None
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


__all__ = [
    "_get_default_db_path",
    "_row_to_dict",
    "get_connection",
    "transaction",
]
