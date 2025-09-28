"""
Hive DB package - Database utilities and connection management for Hive applications.

Provides both sync and async database operations, connection pooling,
and utility functions following the Hive inherit-extend pattern.
"""

from .sqlite_connector import (
    get_sqlite_connection,
    sqlite_transaction
)

from .postgres_connector import (
    get_postgres_connection,
    postgres_transaction,
    create_connection_pool,
    get_postgres_info
)

from .pool import (
    ConnectionPool,
    DatabaseManager,
    get_pooled_connection,
    get_database_manager,
    close_all_pools,
    get_pool_stats,
    pool_health_check
)

from .async_pool import (
    AsyncConnectionPool,
    AsyncDatabaseManager,
    get_async_connection,
    get_async_database_manager,
    close_all_async_pools,
    get_async_pool_stats,
    async_pool_health_check
)

from .utils import (
    table_exists,
    create_table_if_not_exists,
    get_table_schema,
    execute_script,
    backup_database,
    vacuum_database,
    get_database_info,
    database_transaction,
    insert_or_update,
    batch_insert,
    migrate_database,
    async_table_exists,
    async_get_database_info
)

# Convenience imports
connect_sqlite = get_sqlite_connection
connect_postgres = get_postgres_connection

__all__ = [
    # SQLite utilities
    'get_sqlite_connection',
    'sqlite_transaction',
    'connect_sqlite',

    # PostgreSQL utilities
    'get_postgres_connection',
    'postgres_transaction',
    'create_connection_pool',
    'get_postgres_info',
    'connect_postgres',

    # Connection pooling
    'ConnectionPool',
    'DatabaseManager',
    'get_pooled_connection',
    'get_database_manager',
    'close_all_pools',
    'get_pool_stats',
    'pool_health_check',

    # Async connection pooling
    'AsyncConnectionPool',
    'AsyncDatabaseManager',
    'get_async_connection',
    'get_async_database_manager',
    'close_all_async_pools',
    'get_async_pool_stats',
    'async_pool_health_check',

    # Database utilities
    'table_exists',
    'create_table_if_not_exists',
    'get_table_schema',
    'execute_script',
    'backup_database',
    'vacuum_database',
    'get_database_info',
    'database_transaction',
    'insert_or_update',
    'batch_insert',
    'migrate_database',
    'async_table_exists',
    'async_get_database_info',
]
