"""
Async database connection pooling utilities for Hive applications.

Provides high-performance async connection pooling using aiosqlite
for non-blocking database operations, built on the generic hive-async pool.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

import aiosqlite
from hive_async.pools import ConnectionPool, PoolConfig
from hive_logging import get_logger

logger = get_logger(__name__)


async def close_sqlite_connection_async(conn: aiosqlite.Connection) -> None:
    ("""Close a SQLite connection safely.""",)
    try:
        await conn.close()
    except Exception as e:
        logger.debug(f"Error closing SQLite connection: {e}")


async def validate_sqlite_connection_async(conn: aiosqlite.Connection) -> bool:
    ("""Check if a SQLite connection is still valid.""",)
    try:
        await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.debug(f"SQLite connection validation failed: {e}")
        return False


def create_async_sqlite_pool(
    db_path: Path,
    min_connections: int = 3,
    max_connections: int = 25,
    connection_timeout: float = 30.0,
    max_idle_time: float = 300.0,
) -> ConnectionPool[aiosqlite.Connection]:
    """
    Create an async SQLite connection pool using the generic hive-async pool.

    Args:
        db_path: Path to the SQLite database file,
        min_connections: Minimum connections to maintain,
        max_connections: Maximum connections allowed,
        connection_timeout: Timeout for acquiring connections,
        max_idle_time: Maximum idle time before connection recycling

    Returns:
        Generic connection pool configured for SQLite
    """
    config = PoolConfig(
        min_size=min_connections,
        max_size=max_connections,
        acquire_timeout=connection_timeout,
        max_inactive_time=max_idle_time,
    )

    return ConnectionPool(
        create_connection=lambda: create_sqlite_connection_async(db_path),
        close_connection=close_sqlite_connection_async,
        health_check=validate_sqlite_connection_async,
        config=config,
    )


class AsyncDatabaseManager:
    """
    Manager for multiple async database connection pools.

    Provides a unified interface for accessing different SQLite databases
    asynchronously while maintaining connection pooling using the generic
    hive-async connection pool infrastructure.
    """

    async def get_pool_async(self, db_name: str, db_path: Path, **pool_kwargs) -> ConnectionPool[aiosqlite.Connection]:
        """
        Get or create an async connection pool for a specific database.

        Args:
            db_name: Unique identifier for the database,
            db_path: Path to the SQLite database file
            **pool_kwargs: Additional arguments for pool configuration,

        Returns:
            Generic connection pool for the specified database
        """
        if db_name not in self._pools:
            async with self._lock:
                if db_name not in self._pools:
                    pool = create_async_sqlite_pool(db_path=db_path, **pool_kwargs)
                    await pool.initialize()
                    self._pools[db_name] = pool
                    logger.info(f"Created async connection pool for database: {db_name}")

        return self._pools[db_name]

    @asynccontextmanager
    async def get_connection_async(self, db_name: str, db_path: Path, **pool_kwargs) -> None:
        """
        Get an async connection for a specific database.

        Args:
            db_name: Unique identifier for the database,
            db_path: Path to the SQLite database file
            **pool_kwargs: Additional arguments for pool configuration,

        Yields:
            aiosqlite.Connection: Database connection from appropriate pool
        """
        pool = await self.get_pool_async(db_name, db_path, **pool_kwargs)
        async with pool.connection() as conn:
            yield conn

    async def close_all_pools_async(self) -> None:
        """Close all async connection pools."""
        async with self._lock:
            for db_name, pool in self._pools.items():
                try:
                    await pool.close()
                    logger.info(f"Closed async pool for database: {db_name}")
                except Exception as e:
                    logger.error(f"Error closing async pool for {db_name}: {e}")

            self._pools.clear()

    async def get_all_stats_async(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all async connection pools."""
        async with self._lock:
            stats = {}
            for db_name, pool in self._pools.items():
                stats[db_name] = {
                    "pool_size": pool.size,
                    "available_connections": pool.available,
                    "max_connections": pool.config.max_size,
                    "min_connections": pool.config.min_size,
                }
            return stats

    async def health_check_async(self) -> Dict[str, Any]:
        """Perform health check on all async connection pools."""
        results = {}
        async with self._lock:
            for db_name, pool in self._pools.items():
                try:
                    # Test connection acquisition
                    import time

                    start_time = time.time()
                    async with pool.connection() as conn:
                        await conn.execute("SELECT 1")
                    acquisition_time = time.time() - start_time

                    results[db_name] = {
                        "status": "healthy",
                        "acquisition_time_ms": acquisition_time * 1000,
                        "pool_utilization": (pool.size - pool.available) / pool.size,
                        "stats": {
                            "pool_size": pool.size,
                            "available_connections": pool.available,
                            "max_connections": pool.config.max_size,
                        },
                    }

                except Exception as e:
                    results[db_name] = {
                        "status": "unhealthy",
                        "error": str(e),
                        "stats": {
                            "pool_size": pool.size,
                            "available_connections": pool.available,
                            "max_connections": pool.config.max_size,
                        },
                    }

        return results


# Factory function for creating async database managers with explicit configuration
async def create_async_database_manager_async() -> AsyncDatabaseManager:
    """
    Factory function to create a new AsyncDatabaseManager instance.

    This replaces the previous singleton pattern with explicit instantiation.
    Applications should create one AsyncDatabaseManager instance and inject it
    where needed following dependency injection principles.

    Returns:
        AsyncDatabaseManager: New async database manager instance

    Example:
        # In main application
        async_db_manager = await create_async_database_manager()

        # Pass to services that need it
        service = MyAsyncService(db_manager=async_db_manager)
    """
    manager = AsyncDatabaseManager()
    logger.info("Async database manager created")
    return manager
