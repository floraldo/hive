"""
Hive DB package - Database utilities and connection management for Hive applications.

Provides both sync and async database operations, connection pooling,
and utility functions following the Hive inherit-extend pattern.
"""

from .async_pool import (
    AsyncConnectionPool,
    AsyncDatabaseManager,
    async_pool_health_check,
    close_all_async_pools,
    get_async_connection,
    get_async_database_manager,
    get_async_pool_stats,
)
from .pool import (
    ConnectionPool,
    DatabaseManager,
    close_all_pools,
    get_database_manager,
    get_pool_stats,
    get_pooled_connection,
    pool_health_check,
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
    "get_pooled_connection",
    "get_database_manager",
    "close_all_pools",
    "get_pool_stats",
    "pool_health_check",
    # Async connection pooling
    "AsyncConnectionPool",
    "AsyncDatabaseManager",
    "get_async_connection",
    "get_async_database_manager",
    "close_all_async_pools",
    "get_async_pool_stats",
    "async_pool_health_check",
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
