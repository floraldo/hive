#!/usr/bin/env python3
"""
Shared Database Connection Service

Provides connection pooling for multiple SQLite databases across the Hive platform.
Consolidates connection management while maintaining database isolation.
"""
from __future__ import annotations


import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any, Dict

from hive_config.paths import ensure_directory
from hive_logging import get_logger

logger = get_logger(__name__)


class DatabaseConnectionPool:
    """
    Thread-safe SQLite connection pool for a specific database file.

    Features:
    - Configurable pool size
    - Automatic connection validation
    - Thread-safe operations
    - Connection recycling
    - Graceful degradation under load
    """

    def __init__(
        self
        db_path: Path
        min_connections: int = 2
        max_connections: int = 10
        connection_timeout: float = 30.0
    ):
        """
        Initialize connection pool for a specific database.

        Args:
            db_path: Path to the SQLite database file
            min_connections: Minimum connections to maintain
            max_connections: Maximum connections allowed
            connection_timeout: Timeout for acquiring connections
        """
        self.db_path = Path(db_path)
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout

        self._pool = Queue(maxsize=self.max_connections)
        self._connections_created = 0
        self._lock = threading.RLock()

        # Initialize minimum connections
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Create initial connections for the pool."""
        for _ in range(self.min_connections):
            conn = self._create_connection()
            if conn:
                self._pool.put(conn)

    def _create_connection(self) -> sqlite3.Connection | None:
        """Create a new database connection with optimal settings."""
        try:
            ensure_directory(self.db_path.parent)

            conn = sqlite3.connect(
                str(self.db_path)
                check_same_thread=False
                timeout=30.0,  # 30 second timeout for locks
                isolation_level="DEFERRED",  # Better concurrency
            )

            # Optimize connection settings
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
            conn.execute("PRAGMA cache_size=10000")  # 10MB cache
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables

            with self._lock:
                self._connections_created += 1

            logger.debug(f"Created connection #{self._connections_created} for {self.db_path.name}")
            return conn

        except Exception as e:
            logger.error(f"Failed to create connection for {self.db_path}: {e}")
            return None

    def _validate_connection(self, conn: sqlite3.Connection) -> bool:
        """Check if a connection is still valid."""
        try:
            conn.execute("SELECT 1")
            return True
        except (sqlite3.Error, sqlite3.ProgrammingError, AttributeError) as e:
            logger.debug(f"Connection validation failed for {self.db_path.name}: {e}")
            return False

    @contextmanager
    def get_connection(self) -> None:
        """
        Context manager for acquiring and releasing connections.

        Yields:
            sqlite3.Connection: Database connection from pool
        """
        conn = None
        try:
            # Try to get from pool
            try:
                conn = self._pool.get(timeout=self.connection_timeout)

                # Validate connection
                if not self._validate_connection(conn):
                    conn.close()
                    conn = self._create_connection()

            except Empty:
                # Pool exhausted, create new if under limit
                with self._lock:
                    if self._connections_created < self.max_connections:
                        conn = self._create_connection()
                    else:
                        # Wait longer for a connection
                        conn = self._pool.get(timeout=self.connection_timeout * 2)

            if not conn:
                raise RuntimeError(f"Failed to acquire database connection for {self.db_path}")

            yield conn

        finally:
            # Return connection to pool with proper cleanup
            if conn:
                try:
                    # Reset connection state
                    conn.rollback()
                    self._pool.put(conn)
                except (Full, sqlite3.Error) as e:
                    # Connection corrupted, close it
                    logger.warning(f"Failed to return connection to pool for {self.db_path.name}: {e}")
                    try:
                        conn.close()
                    except (sqlite3.Error, AttributeError) as close_error:
                        logger.debug(f"Failed to close corrupted connection: {close_error}")
                    with self._lock:
                        self._connections_created -= 1

    def close_all(self) -> None:
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Empty:
                break
            except (sqlite3.Error, AttributeError) as e:
                logger.debug(f"Error closing connection during pool shutdown: {e}")

        with self._lock:
            self._connections_created = 0

        logger.info(f"Connection pool closed for {self.db_path.name}")

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "db_path": str(self.db_path)
            "pool_size": self._pool.qsize()
            "connections_created": self._connections_created
            "max_connections": self.max_connections
            "min_connections": self.min_connections
        }


class SharedDatabaseService:
    """
    Service managing multiple database connection pools.

    Provides a unified interface for accessing different SQLite databases
    while maintaining connection pooling and proper resource management.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the shared database service with DI support.

        Args:
            config: Optional configuration dictionary for database settings
        """
        self._pools: Dict[str, DatabaseConnectionPool] = {}
        self._lock = threading.RLock()
        self._config = config or {}

    def get_pool(self, db_name: str, db_path: Path) -> DatabaseConnectionPool:
        """
        Get or create a connection pool for a specific database.

        Args:
            db_name: Unique identifier for the database
            db_path: Path to the SQLite database file

        Returns:
            DatabaseConnectionPool for the specified database
        """
        if db_name not in self._pools:
            with self._lock:
                if db_name not in self._pools:
                    # Get database-specific configuration from config dict
                    db_config = self._config.get("database", {})

                    self._pools[db_name] = DatabaseConnectionPool(
                        db_path=db_path
                        min_connections=2
                        max_connections=db_config.get("max_connections", 10)
                        connection_timeout=db_config.get("connection_timeout", 30.0)
                    )
                    logger.info(f"Created connection pool for database: {db_name}")

        return self._pools[db_name]

    @contextmanager
    def get_connection(self, db_name: str, db_path: Path) -> None:
        """
        Get a connection for a specific database.

        Args:
            db_name: Unique identifier for the database
            db_path: Path to the SQLite database file

        Yields:
            sqlite3.Connection: Database connection from appropriate pool
        """
        pool = self.get_pool(db_name, db_path)
        with pool.get_connection() as conn:
            yield conn

    def close_all_pools(self) -> None:
        """Close all connection pools."""
        with self._lock:
            for db_name, pool in self._pools.items():
                try:
                    pool.close_all()
                    logger.info(f"Closed pool for database: {db_name}")
                except Exception as e:
                    logger.error(f"Error closing pool for {db_name}: {e}")

            self._pools.clear()

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all connection pools."""
        with self._lock:
            return {db_name: pool.get_stats() for db_name, pool in self._pools.items()}

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all connection pools."""
        results = {}
        with self._lock:
            for db_name, pool in self._pools.items():
                try:
                    # Test connection acquisition
                    with pool.get_connection() as conn:
                        conn.execute("SELECT 1")
                    results[db_name] = {"status": "healthy", "stats": pool.get_stats()}
                except Exception as e:
                    results[db_name] = {"status": "unhealthy", "error": str(e)}

        return results


# Global shared database service instance
_shared_service: SharedDatabaseService | None = None
_service_lock = threading.Lock()


def get_shared_database_service(
    config: Optional[Dict[str, Any]] = None
) -> SharedDatabaseService:
    """Get or create the global shared database service with DI support.

    Args:
        config: Optional configuration dictionary for database settings
    """
    global _shared_service

    if _shared_service is None:
        with _service_lock:
            if _shared_service is None:
                _shared_service = SharedDatabaseService(config)
                logger.info("Shared database service initialized")

    return _shared_service


@contextmanager
def get_database_connection(db_name: str, db_path: Path) -> None:
    """
    Get a connection from the shared database service.

    This is the main interface for getting database connections.

    Args:
        db_name: Unique identifier for the database
        db_path: Path to the SQLite database file

    Example:
        with get_database_connection("ecosystemiser", ecosystemiser_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM components")
    """
    service = get_shared_database_service()
    with service.get_connection(db_name, db_path) as conn:
        yield conn


def close_all_database_pools() -> None:
    """Close all database connection pools."""
    global _shared_service

    if _shared_service:
        _shared_service.close_all_pools()
        _shared_service = None
        logger.info("All database connection pools closed")


def get_database_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all database connection pools."""
    service = get_shared_database_service()
    return service.get_all_stats()


def database_health_check() -> Dict[str, Any]:
    """Perform health check on all database connection pools."""
    service = get_shared_database_service()
    return service.health_check()
