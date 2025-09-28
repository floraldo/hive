"""
Hive DB package - Database utilities and connection management for Hive applications.

Provides both sync and async database operations, connection pooling,
and utility functions following the Hive inherit-extend pattern.
"""

from .async_pool import (
    AsyncDatabaseManager,
    create_async_database_manager,
    create_async_sqlite_pool,
)
from .pool import (
    ConnectionPool,
    DatabaseManager,
    create_database_manager,
)
from .postgres_connector import (
    create_connection_pool,
    get_postgres_connection,
    get_postgres_info,
    postgres_transaction,
)
from .sqlite_connector import get_sqlite_connection, sqlite_transaction
from .utils import (
    async_get_database_info,
    async_table_exists,
    backup_database,
    batch_insert,
    create_table_if_not_exists,
    database_transaction,
    execute_script,
    get_database_info,
    get_table_schema,
    insert_or_update,
    migrate_database,
    table_exists,
    vacuum_database,
)

# Convenience imports
connect_sqlite = get_sqlite_connection
connect_postgres = get_postgres_connection

__all__ = [
    # SQLite utilities
    "get_sqlite_connection",
    "sqlite_transaction",
    "connect_sqlite",
    # PostgreSQL utilities
    "get_postgres_connection",
    "postgres_transaction",
    "create_connection_pool",
    "get_postgres_info",
    "connect_postgres",
    # Connection pooling
    "ConnectionPool",
    "DatabaseManager",
    "create_database_manager",
    # Async connection pooling
    "AsyncDatabaseManager",
    "create_async_database_manager",
    "create_async_sqlite_pool",
    # Database utilities
    "table_exists",
    "create_table_if_not_exists",
    "get_table_schema",
    "execute_script",
    "backup_database",
    "vacuum_database",
    "get_database_info",
    "database_transaction",
    "insert_or_update",
    "batch_insert",
    "migrate_database",
    "async_table_exists",
    "async_get_database_info",
]
