"""
Hive DB Utils package - Generic database connectivity utilities for Hive applications
"""

from .sqlite_connector import (
    get_sqlite_connection,
    sqlite_transaction,
    create_table_if_not_exists,
    get_sqlite_info
)

from .postgres_connector import (
    get_postgres_connection,
    postgres_transaction,
    create_connection_pool,
    get_postgres_info
)

# Convenience imports
connect_sqlite = get_sqlite_connection
connect_postgres = get_postgres_connection

__all__ = [
    # SQLite utilities
    'get_sqlite_connection',
    'sqlite_transaction',
    'create_table_if_not_exists',
    'get_sqlite_info',
    'connect_sqlite',

    # PostgreSQL utilities
    'get_postgres_connection',
    'postgres_transaction',
    'create_connection_pool',
    'get_postgres_info',
    'connect_postgres'
]
