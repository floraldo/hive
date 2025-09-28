"""
Database utilities and helper functions for Hive applications.

Provides common database operations, migrations, and utility functions.
"""

import asyncio
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from hive_logging import get_logger

logger = get_logger(__name__)


def create_table_if_not_exists(conn: sqlite3.Connection, table_name: str, schema: str):
    """
    Create a table if it doesn't exist.

    Args:
        conn: Database connection
        table_name: Name of the table to create
        schema: SQL schema definition for the table
    """
    try:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})")
        conn.commit()
        logger.debug(f"Ensured table {table_name} exists")
    except sqlite3.Error as e:
        logger.error(f"Failed to create table {table_name}: {e}")
        raise


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """
    Check if a table exists in the database.

    Args:
        conn: Database connection
        table_name: Name of the table to check

    Returns:
        True if table exists, False otherwise
    """
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"Failed to check if table {table_name} exists: {e}")
        return False


def get_table_schema(conn: sqlite3.Connection, table_name: str) -> List[Dict[str, Any]]:
    """
    Get the schema information for a table.

    Args:
        conn: Database connection
        table_name: Name of the table

    Returns:
        List of column information dictionaries
    """
    try:
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

        schema = []
        for col in columns:
            schema.append(
                {
                    "name": col[1],
                    "type": col[2],
                    "not_null": bool(col[3]),
                    "default_value": col[4],
                    "primary_key": bool(col[5]),
                }
            )

        return schema
    except sqlite3.Error as e:
        logger.error(f"Failed to get schema for table {table_name}: {e}")
        return []


def execute_script(conn: sqlite3.Connection, script_path: Path):
    """
    Execute a SQL script file.

    Args:
        conn: Database connection
        script_path: Path to the SQL script file
    """
    try:
        with open(script_path, "r") as f:
            script = f.read()

        conn.executescript(script)
        conn.commit()
        logger.info(f"Executed SQL script: {script_path}")
    except (sqlite3.Error, IOError) as e:
        logger.error(f"Failed to execute script {script_path}: {e}")
        raise


def backup_database(source_db: Path, backup_path: Path):
    """
    Create a backup of a SQLite database.

    Args:
        source_db: Path to the source database
        backup_path: Path where backup should be created
    """
    try:
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(source_db) as source_conn:
            with sqlite3.connect(backup_path) as backup_conn:
                source_conn.backup(backup_conn)

        logger.info(f"Database backed up from {source_db} to {backup_path}")
    except sqlite3.Error as e:
        logger.error(f"Failed to backup database: {e}")
        raise


def vacuum_database(conn: sqlite3.Connection):
    """
    Vacuum a database to reclaim space and optimize performance.

    Args:
        conn: Database connection
    """
    try:
        conn.execute("VACUUM")
        logger.info("Database vacuumed successfully")
    except sqlite3.Error as e:
        logger.error(f"Failed to vacuum database: {e}")
        raise


def get_database_info(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Get information about the database.

    Args:
        conn: Database connection

    Returns:
        Dictionary containing database information
    """
    try:
        info = {}

        # Get page count and size
        cursor = conn.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]

        cursor = conn.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]

        info["page_count"] = page_count
        info["page_size"] = page_size
        info["database_size_bytes"] = page_count * page_size

        # Get journal mode
        cursor = conn.execute("PRAGMA journal_mode")
        info["journal_mode"] = cursor.fetchone()[0]

        # Get synchronous setting
        cursor = conn.execute("PRAGMA synchronous")
        info["synchronous"] = cursor.fetchone()[0]

        # Get foreign keys setting
        cursor = conn.execute("PRAGMA foreign_keys")
        info["foreign_keys"] = bool(cursor.fetchone()[0])

        # Get cache size
        cursor = conn.execute("PRAGMA cache_size")
        info["cache_size"] = cursor.fetchone()[0]

        # Get table count
        cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        info["table_count"] = cursor.fetchone()[0]

        return info
    except sqlite3.Error as e:
        logger.error(f"Failed to get database info: {e}")
        return {}


@contextmanager
def database_transaction(
    conn: sqlite3.Connection, isolation_level: Optional[str] = None
):
    """
    Context manager for database transactions with automatic rollback on error.

    Args:
        conn: Database connection
        isolation_level: Transaction isolation level (DEFERRED, IMMEDIATE, EXCLUSIVE)

    Example:
        with database_transaction(conn) as cursor:
            cursor.execute("INSERT INTO users (name) VALUES (?)", ("John",))
            cursor.execute("UPDATE users SET age = ? WHERE name = ?", (30, "John"))
    """
    if isolation_level:
        conn.execute(f"BEGIN {isolation_level}")
    else:
        conn.execute("BEGIN")

    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
        logger.debug("Transaction committed successfully")
    except Exception as e:
        conn.rollback()
        logger.warning(f"Transaction rolled back due to error: {e}")
        raise
    finally:
        cursor.close()


def insert_or_update(
    conn: sqlite3.Connection,
    table: str,
    data: Dict[str, Any],
    conflict_columns: List[str],
) -> str:
    """
    Insert or update a record using UPSERT (INSERT ... ON CONFLICT).

    Args:
        conn: Database connection
        table: Table name
        data: Dictionary of column names and values
        conflict_columns: Columns that define the conflict condition

    Returns:
        "inserted" or "updated" depending on what happened
    """
    try:
        columns = list(data.keys())
        placeholders = ["?" for _ in columns]
        values = list(data.values())

        # Build the INSERT statement
        insert_sql = f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """

        # Build the ON CONFLICT clause
        conflict_sql = f"ON CONFLICT({', '.join(conflict_columns)}) DO UPDATE SET"
        update_clauses = [
            f"{col} = excluded.{col}" for col in columns if col not in conflict_columns
        ]

        if update_clauses:
            sql = f"{insert_sql} {conflict_sql} {', '.join(update_clauses)}"
        else:
            sql = f"{insert_sql} {conflict_sql} NOTHING"

        cursor = conn.cursor()
        cursor.execute(sql, values)

        # Check if row was inserted or updated
        if cursor.rowcount == 1:
            return "inserted"
        else:
            return "updated"

    except sqlite3.Error as e:
        logger.error(f"Failed to insert or update in table {table}: {e}")
        raise


def batch_insert(
    conn: sqlite3.Connection,
    table: str,
    data: List[Dict[str, Any]],
    chunk_size: int = 1000,
):
    """
    Insert multiple records in batches for better performance.

    Args:
        conn: Database connection
        table: Table name
        data: List of dictionaries containing data to insert
        chunk_size: Number of records to insert per batch
    """
    if not data:
        return

    try:
        columns = list(data[0].keys())
        placeholders = ["?" for _ in columns]
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"

        # Process in chunks
        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            values = [list(record.values()) for record in chunk]

            conn.executemany(sql, values)

        conn.commit()
        logger.info(f"Batch inserted {len(data)} records into {table}")

    except sqlite3.Error as e:
        logger.error(f"Failed to batch insert into table {table}: {e}")
        conn.rollback()
        raise


def migrate_database(
    conn: sqlite3.Connection, migrations_dir: Path, target_version: Optional[int] = None
):
    """
    Apply database migrations from a directory.

    Args:
        conn: Database connection
        migrations_dir: Directory containing migration files
        target_version: Target migration version (applies all if None)
    """
    try:
        # Ensure migrations table exists
        create_table_if_not_exists(
            conn,
            "migrations",
            "version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        )

        # Get applied migrations
        cursor = conn.execute("SELECT version FROM migrations ORDER BY version")
        applied = {row[0] for row in cursor.fetchall()}

        # Find migration files
        migration_files = sorted(
            [f for f in migrations_dir.glob("*.sql") if f.stem.isdigit()],
            key=lambda x: int(x.stem),
        )

        # Apply migrations
        for migration_file in migration_files:
            version = int(migration_file.stem)

            if version in applied:
                continue

            if target_version and version > target_version:
                break

            logger.info(f"Applying migration {version}: {migration_file.name}")
            execute_script(conn, migration_file)

            # Record migration
            conn.execute("INSERT INTO migrations (version) VALUES (?)", (version,))
            conn.commit()

        logger.info("Database migrations completed")

    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Failed to migrate database: {e}")
        conn.rollback()
        raise


# Async versions of utility functions
async def async_table_exists(conn, table_name: str) -> bool:
    """Async version of table_exists."""
    try:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        result = await cursor.fetchone()
        return result is not None
    except Exception as e:
        logger.error(f"Failed to check if table {table_name} exists: {e}")
        return False


async def async_get_database_info(conn) -> Dict[str, Any]:
    """Async version of get_database_info."""
    try:
        info = {}

        # Get page count and size
        cursor = await conn.execute("PRAGMA page_count")
        page_count = (await cursor.fetchone())[0]

        cursor = await conn.execute("PRAGMA page_size")
        page_size = (await cursor.fetchone())[0]

        info["page_count"] = page_count
        info["page_size"] = page_size
        info["database_size_bytes"] = page_count * page_size

        # Get journal mode
        cursor = await conn.execute("PRAGMA journal_mode")
        info["journal_mode"] = (await cursor.fetchone())[0]

        # Get synchronous setting
        cursor = await conn.execute("PRAGMA synchronous")
        info["synchronous"] = (await cursor.fetchone())[0]

        # Get foreign keys setting
        cursor = await conn.execute("PRAGMA foreign_keys")
        info["foreign_keys"] = bool((await cursor.fetchone())[0])

        # Get cache size
        cursor = await conn.execute("PRAGMA cache_size")
        info["cache_size"] = (await cursor.fetchone())[0]

        # Get table count
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        )
        info["table_count"] = (await cursor.fetchone())[0]

        return info
    except Exception as e:
        logger.error(f"Failed to get async database info: {e}")
        return {}
