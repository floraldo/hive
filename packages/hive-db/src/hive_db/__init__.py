"""
Hive DB package - Database utilities and connection management for Hive applications.

Provides both sync and async database operations, connection pooling,
and utility functions following the Hive inherit-extend pattern.
"""

from hive_logging import get_logger

from .async_pool import AsyncDatabaseManager, create_async_sqlite_pool
from .async_pool import create_async_database_manager_async as create_async_database_manager

# DEPRECATED: pool module removed - use SQLiteConnectionFactory instead
# from .pool import ConnectionPool, DatabaseManager, create_database_manager
from .postgres_connector import create_connection_pool, get_postgres_connection, get_postgres_info, postgres_transaction
from .sqlite_connector import get_sqlite_connection, sqlite_transaction
from .sqlite_factory import SQLiteConnectionFactory, SQLiteConnectionManager, create_sqlite_manager
from .utils import (
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

logger = get_logger(__name__)

# SQLAlchemy async session support
try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    AsyncSession = None  # type: ignore
    async_sessionmaker = None  # type: ignore
    create_async_engine = None  # type: ignore
    SQLALCHEMY_AVAILABLE = False

# Async session factory (to be configured by applications)
_async_session_factory = None


def configure_async_session(database_url: str, **engine_kwargs):
    """Configure async session factory for SQLAlchemy.

    Args:
        database_url: Async database URL (e.g., 'sqlite+aiosqlite:///db.sqlite')
        **engine_kwargs: Additional arguments for create_async_engine
    """
    global _async_session_factory
    if not SQLALCHEMY_AVAILABLE:
        raise ImportError("SQLAlchemy not available. Install with: pip install sqlalchemy[asyncio]")

    engine = create_async_engine(database_url, **engine_kwargs)
    _async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


def get_async_session():
    """Get async session context manager.

    Returns:
        Async context manager for database session

    Raises:
        RuntimeError: If async session factory not configured
    """
    if _async_session_factory is None:
        raise RuntimeError("Async session factory not configured. Call configure_async_session() first.")
    return _async_session_factory()

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
    # Connection pooling (legacy - DEPRECATED, removed)
    # "ConnectionPool",  # Use SQLiteConnectionFactory instead
    # "DatabaseManager",  # Use SQLiteConnectionManager instead
    # "create_database_manager",  # Use create_sqlite_manager instead
    # Async connection pooling
    "AsyncDatabaseManager",
    "create_async_database_manager",
    "create_async_sqlite_pool",
    # Modern SQLite pooling (canonical hive-async based)
    "SQLiteConnectionFactory",
    "SQLiteConnectionManager",
    "create_sqlite_manager",
    # SQLAlchemy async session support
    "AsyncSession",
    "get_async_session",
    "configure_async_session",
    "SQLALCHEMY_AVAILABLE",
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
]
