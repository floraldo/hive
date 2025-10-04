"""SQLite Connection Factory for Hive Platform.

Provides SQLite-specific connection management using the canonical
hive-async connection pool with SQLite optimizations.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from hive_async.pools import ConnectionPool, PoolConfig
from hive_logging import get_logger

logger = get_logger(__name__)


class SQLiteConnectionFactory:
    """Factory for creating SQLite connections with optimal settings.

    Uses the canonical hive-async ConnectionPool with SQLite-specific
    configuration and connection creation logic.
    """

    def __init__(
        self,
        db_path: Path | str,
        min_connections: int = 2,
        max_connections: int = 10,
        connection_timeout: float = 30.0,
    ):
        """Initialize SQLite connection factory.

        Args:
            db_path: Path to SQLite database file
            min_connections: Minimum pool size
            max_connections: Maximum pool size
            connection_timeout: Timeout for acquiring connections

        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create pool config
        config = PoolConfig(
            min_size=min_connections,
            max_size=max_connections,
            acquire_timeout=connection_timeout,
            max_inactive_time=3600.0,  # 1 hour
            health_check_interval=300.0,  # 5 minutes
        )

        # Create connection pool with SQLite-specific handlers
        self._pool = ConnectionPool(
            create_connection=self._create_sqlite_connection,
            close_connection=self._close_sqlite_connection,
            health_check=self._health_check_connection,
            config=config,
        )

        logger.info(f"SQLite connection factory initialized for {self.db_path.name}")

    def _create_sqlite_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with optimal settings.

        Returns:
            Configured SQLite connection

        """
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30.0,
            isolation_level="DEFERRED",  # Better concurrency
        )

        # Optimize connection settings
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
        conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
        conn.execute("PRAGMA cache_size=10000")  # 10MB cache
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA temp_store=MEMORY")  # Memory temp tables

        logger.debug(f"Created SQLite connection for {self.db_path.name}")
        return conn

    def _close_sqlite_connection(self, conn: sqlite3.Connection) -> None:
        """Close a SQLite connection gracefully.

        Args:
            conn: Connection to close

        """
        try:
            conn.close()
            logger.debug(f"Closed SQLite connection for {self.db_path.name}")
        except Exception as e:
            logger.warning(f"Error closing SQLite connection: {e}")

    def _health_check_connection(self, conn: sqlite3.Connection) -> bool:
        """Check if SQLite connection is healthy.

        Args:
            conn: Connection to check

        Returns:
            True if connection is healthy

        """
        try:
            conn.execute("SELECT 1")
            return True
        except (sqlite3.Error, sqlite3.ProgrammingError, AttributeError):
            return False

    async def initialize_async(self) -> None:
        """Initialize the connection pool."""
        await self._pool.initialize_async()
        logger.info(f"Connection pool initialized for {self.db_path.name}")

    async def acquire_async(self) -> sqlite3.Connection:
        """Acquire a connection from the pool.

        Returns:
            SQLite connection from pool

        """
        return await self._pool.acquire_async()

    async def release_async(self, connection: sqlite3.Connection) -> None:
        """Release a connection back to the pool.

        Args:
            connection: Connection to release

        """
        await self._pool.release_async(connection)

    async def connection_async(self):
        """Context manager for acquiring and releasing connections.

        Usage:
            async with factory.connection_async() as conn:
                cursor = conn.execute("SELECT * FROM table"),
                results = cursor.fetchall()
        """
        return self._pool.connection_async()

    async def close_async(self) -> None:
        """Close all connections in the pool."""
        await self._pool.close_async()
        logger.info(f"Connection pool closed for {self.db_path.name}")

    @property
    def size(self) -> int:
        """Current number of connections in the pool."""
        return self._pool.size

    @property
    def available(self) -> int:
        """Number of available connections."""
        return self._pool.available

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dictionary with pool statistics

        """
        return {
            "db_path": str(self.db_path),
            "pool_size": self.size,
            "available": self.available,
            "max_connections": self._pool.config.max_size,
            "min_connections": self._pool.config.min_size,
        }


class SQLiteConnectionManager:
    """Manager for multiple SQLite database connection pools.

    Provides a unified interface for managing connections to multiple
    SQLite databases with automatic pooling.
    """

    def __init__(self):
        """Initialize the connection manager."""
        self._factories: dict[str, SQLiteConnectionFactory] = {}
        logger.info("SQLite connection manager initialized")

    def get_factory(
        self,
        db_name: str,
        db_path: Path | str,
        **factory_kwargs,
    ) -> SQLiteConnectionFactory:
        """Get or create a connection factory for a database.

        Args:
            db_name: Unique identifier for the database
            db_path: Path to the SQLite database file
            **factory_kwargs: Additional arguments for SQLiteConnectionFactory

        Returns:
            SQLiteConnectionFactory for the database

        """
        if db_name not in self._factories:
            self._factories[db_name] = SQLiteConnectionFactory(db_path, **factory_kwargs)
            logger.info(f"Created connection factory for database: {db_name}")

        return self._factories[db_name]

    async def connection_async(self, db_name: str, db_path: Path | str, **factory_kwargs):
        """Get a connection for a specific database.

        Args:
            db_name: Unique identifier for the database
            db_path: Path to the SQLite database file
            **factory_kwargs: Additional arguments for factory

        Yields:
            SQLite connection from appropriate pool

        """
        factory = self.get_factory(db_name, db_path, **factory_kwargs)
        async with factory.connection_async() as conn:
            yield conn

    async def close_all_async(self) -> None:
        """Close all connection pools."""
        for db_name, factory in list(self._factories.items()):
            try:
                await factory.close_async()
                logger.info(f"Closed factory for database: {db_name}")
            except Exception as e:
                logger.error(f"Error closing factory for {db_name}: {e}")

        self._factories.clear()

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all connection factories.

        Returns:
            Dictionary mapping database names to statistics

        """
        return {db_name: factory.get_stats() for db_name, factory in self._factories.items()}

    async def health_check_async(self) -> dict[str, Any]:
        """Perform health check on all connection pools.

        Returns:
            Dictionary with health status for each database

        """
        results = {}
        for db_name, factory in self._factories.items():
            try:
                # Test connection acquisition
                async with factory.connection_async() as conn:
                    conn.execute("SELECT 1")
                results[db_name] = {"status": "healthy", "stats": factory.get_stats()}
            except Exception as e:
                results[db_name] = {"status": "unhealthy", "error": str(e)}

        return results


def create_sqlite_manager() -> SQLiteConnectionManager:
    """Factory function to create a new SQLiteConnectionManager.

    Following dependency injection principles, applications should
    create one manager instance and inject it where needed.

    Returns:
        SQLiteConnectionManager: New manager instance

    Example:
        # In main application
        db_manager = create_sqlite_manager()

        # Pass to services
        service = MyService(db_manager=db_manager)

    """
    manager = SQLiteConnectionManager()
    logger.info("SQLite connection manager created")
    return manager
