"""
Database Connection Service Implementation

Injectable database service that replaces global connection pool singletons.
Provides both sync and async connection management with proper resource cleanup.
"""

import sqlite3
import asyncio
import threading
from contextlib import contextmanager, asynccontextmanager
from typing import Any, Dict, Optional, Union
from queue import Queue, Empty
from dataclasses import dataclass
from pathlib import Path

from ..interfaces import IDatabaseConnectionService, IConfigurationService, IDisposable

try:
    import aiosqlite
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False


@dataclass
class ConnectionPoolStats:
    """Statistics for connection pool monitoring"""
    active_connections: int
    idle_connections: int
    total_connections: int
    max_connections: int
    total_acquired: int
    total_released: int
    total_created: int
    pool_exhaustions: int


class DatabaseConnectionService(IDatabaseConnectionService, IDisposable):
    """
    Injectable database connection service

    Replaces global connection pool singletons with a proper service that can be
    configured and injected independently.
    """

    def __init__(self,
                 configuration_service: IConfigurationService,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize database connection service

        Args:
            configuration_service: Configuration service for getting DB settings
            config: Optional override configuration
        """
        self._config_service = configuration_service
        self._override_config = config or {}

        # Get database configuration
        db_config = self._config_service.get_database_config()
        self._db_config = {**db_config, **self._override_config}

        # Connection pool settings
        self.min_connections = self._db_config.get('min_connections', 2)
        self.max_connections = self._db_config.get('max_connections', 10)
        self.connection_timeout = self._db_config.get('connection_timeout', 30.0)
        self.database_path = self._db_config.get('database_path') or self._get_default_db_path()

        # Sync connection pool
        self._sync_pool = Queue(maxsize=self.max_connections)
        self._sync_active_connections = set()
        self._sync_lock = threading.RLock()

        # Async connection pool (if available)
        if ASYNC_AVAILABLE:
            self._async_pool = asyncio.Queue(maxsize=self.max_connections)
            self._async_active_connections = set()
            self._async_lock = asyncio.Lock()
        else:
            self._async_pool = None
            self._async_active_connections = set()
            self._async_lock = None

        # Statistics
        self._stats = ConnectionPoolStats(
            active_connections=0,
            idle_connections=0,
            total_connections=0,
            max_connections=self.max_connections,
            total_acquired=0,
            total_released=0,
            total_created=0,
            pool_exhaustions=0
        )

        # Initialize minimum connections
        self._initialize_pool()

    def _get_default_db_path(self) -> str:
        """Get default database path"""
        # Try to determine a reasonable default
        if hasattr(self._config_service, 'get'):
            app_dir = self._config_service.get('app_directory')
            if app_dir:
                return str(Path(app_dir) / 'hive.db')

        # Fallback to current directory
        return str(Path.cwd() / 'hive.db')

    def _initialize_pool(self) -> None:
        """Initialize the connection pool with minimum connections"""
        with self._sync_lock:
            for _ in range(self.min_connections):
                try:
                    conn = self._create_sync_connection()
                    self._sync_pool.put_nowait(conn)
                    self._stats.total_created += 1
                    self._stats.idle_connections += 1
                    self._stats.total_connections += 1
                except Exception:
                    # If we can't create minimum connections, that's a problem
                    # but we'll let the service continue and try on-demand
                    break

    def _create_sync_connection(self) -> sqlite3.Connection:
        """Create a new sync SQLite connection"""
        conn = sqlite3.connect(
            self.database_path,
            timeout=self.connection_timeout,
            check_same_thread=False  # Allow sharing across threads
        )

        # Configure connection
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA temp_store=MEMORY')
        conn.execute('PRAGMA mmap_size=268435456')  # 256MB
        conn.row_factory = sqlite3.Row  # Dict-like row access

        return conn

    async def _create_async_connection(self):
        """Create a new async SQLite connection"""
        if not ASYNC_AVAILABLE:
            raise RuntimeError("Async support not available (aiosqlite not installed)")

        conn = await aiosqlite.connect(
            self.database_path,
            timeout=self.connection_timeout
        )

        # Configure connection
        await conn.execute('PRAGMA journal_mode=WAL')
        await conn.execute('PRAGMA synchronous=NORMAL')
        await conn.execute('PRAGMA temp_store=MEMORY')
        await conn.execute('PRAGMA mmap_size=268435456')  # 256MB
        conn.row_factory = aiosqlite.Row  # Dict-like row access

        return conn

    # IDatabaseConnectionService interface implementation

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection (sync)"""
        with self._sync_lock:
            # Try to get from pool first
            try:
                conn = self._sync_pool.get_nowait()
                self._stats.idle_connections -= 1
            except Empty:
                # Pool is empty, create new connection if under limit
                if len(self._sync_active_connections) >= self.max_connections:
                    self._stats.pool_exhaustions += 1
                    raise RuntimeError(f"Connection pool exhausted (max: {self.max_connections})")

                conn = self._create_sync_connection()
                self._stats.total_created += 1
                self._stats.total_connections += 1

            # Track active connection
            self._sync_active_connections.add(conn)
            self._stats.active_connections += 1
            self._stats.total_acquired += 1

            return conn

    async def get_async_connection(self):
        """Get an async database connection"""
        if not ASYNC_AVAILABLE:
            raise RuntimeError("Async support not available (aiosqlite not installed)")

        if self._async_lock is None:
            self._async_lock = asyncio.Lock()

        async with self._async_lock:
            # Try to get from pool first
            try:
                conn = self._async_pool.get_nowait()
                self._stats.idle_connections -= 1
            except asyncio.QueueEmpty:
                # Pool is empty, create new connection if under limit
                if len(self._async_active_connections) >= self.max_connections:
                    self._stats.pool_exhaustions += 1
                    raise RuntimeError(f"Async connection pool exhausted (max: {self.max_connections})")

                conn = await self._create_async_connection()
                self._stats.total_created += 1
                self._stats.total_connections += 1

            # Track active connection
            self._async_active_connections.add(conn)
            self._stats.active_connections += 1
            self._stats.total_acquired += 1

            return conn

    @contextmanager
    def get_pooled_connection(self):
        """Get a pooled connection context manager"""
        conn = None
        try:
            conn = self.get_connection()
            yield conn
        finally:
            if conn:
                self._return_sync_connection(conn)

    @asynccontextmanager
    async def get_async_pooled_connection(self):
        """Get an async pooled connection context manager"""
        conn = None
        try:
            conn = await self.get_async_connection()
            yield conn
        finally:
            if conn:
                await self._return_async_connection(conn)

    def _return_sync_connection(self, conn: sqlite3.Connection) -> None:
        """Return a sync connection to the pool"""
        with self._sync_lock:
            if conn in self._sync_active_connections:
                self._sync_active_connections.remove(conn)
                self._stats.active_connections -= 1
                self._stats.total_released += 1

                # Check if connection is still valid
                try:
                    conn.execute('SELECT 1')
                    # Return to pool if there's space
                    try:
                        self._sync_pool.put_nowait(conn)
                        self._stats.idle_connections += 1
                    except:
                        # Pool is full, close the connection
                        conn.close()
                        self._stats.total_connections -= 1
                except:
                    # Connection is invalid, close it
                    try:
                        conn.close()
                    except:
                        pass
                    self._stats.total_connections -= 1

    async def _return_async_connection(self, conn) -> None:
        """Return an async connection to the pool"""
        if not ASYNC_AVAILABLE or self._async_lock is None:
            return

        async with self._async_lock:
            if conn in self._async_active_connections:
                self._async_active_connections.remove(conn)
                self._stats.active_connections -= 1
                self._stats.total_released += 1

                # Check if connection is still valid
                try:
                    await conn.execute('SELECT 1')
                    # Return to pool if there's space
                    try:
                        self._async_pool.put_nowait(conn)
                        self._stats.idle_connections += 1
                    except:
                        # Pool is full, close the connection
                        await conn.close()
                        self._stats.total_connections -= 1
                except:
                    # Connection is invalid, close it
                    try:
                        await conn.close()
                    except:
                        pass
                    self._stats.total_connections -= 1

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        return {
            'active_connections': self._stats.active_connections,
            'idle_connections': self._stats.idle_connections,
            'total_connections': self._stats.total_connections,
            'max_connections': self._stats.max_connections,
            'total_acquired': self._stats.total_acquired,
            'total_released': self._stats.total_released,
            'total_created': self._stats.total_created,
            'pool_exhaustions': self._stats.pool_exhaustions,
            'async_available': ASYNC_AVAILABLE
        }

    def close_all_connections(self) -> None:
        """Close all connections and clean up"""
        # Close sync connections
        with self._sync_lock:
            # Close active connections
            for conn in list(self._sync_active_connections):
                try:
                    conn.close()
                except:
                    pass
            self._sync_active_connections.clear()

            # Close idle connections
            while True:
                try:
                    conn = self._sync_pool.get_nowait()
                    try:
                        conn.close()
                    except:
                        pass
                except Empty:
                    break

        # Reset stats
        self._stats.active_connections = 0
        self._stats.idle_connections = 0
        self._stats.total_connections = 0

    # IDisposable interface implementation

    def dispose(self) -> None:
        """Clean up database service resources"""
        self.close_all_connections()

    # Additional utility methods

    def test_connection(self) -> bool:
        """Test if database connection is working"""
        try:
            with self.get_pooled_connection() as conn:
                conn.execute('SELECT 1')
                return True
        except Exception:
            return False

    async def test_async_connection(self) -> bool:
        """Test if async database connection is working"""
        if not ASYNC_AVAILABLE:
            return False

        try:
            async with self.get_async_pooled_connection() as conn:
                await conn.execute('SELECT 1')
                return True
        except Exception:
            return False

    def get_database_path(self) -> str:
        """Get the database file path"""
        return self.database_path

    def get_connection_count(self) -> int:
        """Get total number of connections"""
        return self._stats.total_connections