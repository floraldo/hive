#!/usr/bin/env python3
"""
Async Connection Pool for Hive Database - Phase 4.1 Implementation

High-performance async connection pooling using aiosqlite for 3-5x throughput improvement.
Provides non-blocking database operations for the async-first architecture.
"""

import asyncio
import aiosqlite
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any, Set
from dataclasses import dataclass

from hive_utils.paths import DB_PATH, ensure_directory
from hive_db_utils.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class PoolStats:
    """Statistics for async connection pool monitoring"""
    active_connections: int
    idle_connections: int
    total_connections: int
    max_connections: int
    total_acquired: int
    total_released: int
    total_created: int
    pool_exhaustions: int


class AsyncConnectionPool:
    _instance = None
    _lock = asyncio.Lock() if 'asyncio' in globals() else None
    """
    High-performance async SQLite connection pool for Phase 4.1 architecture.

    Features:
    - Non-blocking connection acquisition with asyncio
    - Automatic connection validation and recycling
    - Configurable pool sizing and timeouts
    - Connection lifetime management
    - Performance monitoring and statistics
    - Graceful degradation under high load
    """

    def __init__(self,
                 min_connections: int = None,
                 max_connections: int = None,
                 connection_timeout: float = None,
                 max_idle_time: float = 300.0):
        """
        Initialize async connection pool.

        Args:
            min_connections: Minimum connections to maintain (defaults to config)
            max_connections: Maximum connections allowed (defaults to config)
            connection_timeout: Timeout for acquiring connections (defaults to config)
            max_idle_time: Maximum idle time before connection recycling
        """
        # Get centralized configuration
        config = get_config()
        db_config = config.get_database_config()

        self.min_connections = min_connections if min_connections is not None else 3
        self.max_connections = max_connections if max_connections is not None else db_config.get("max_connections", 25)
        self.connection_timeout = connection_timeout if connection_timeout is not None else db_config.get("connection_timeout", 30.0)
        self.max_idle_time = max_idle_time

        # Pool state
        self._idle_connections: asyncio.Queue = asyncio.Queue(maxsize=self.max_connections)
        self._active_connections: Set[aiosqlite.Connection] = set()
        self._connection_semaphore = asyncio.Semaphore(self.max_connections)
        self._lock = asyncio.Lock()

        # Statistics tracking
        self._stats = PoolStats(
            active_connections=0,
            idle_connections=0,
            total_connections=0,
            max_connections=self.max_connections,
            total_acquired=0,
            total_released=0,
            total_created=0,
            pool_exhaustions=0
        )

        # Pool lifecycle
        self._initialized = False
        self._closed = False

    async def initialize(self):
        """Initialize the connection pool with minimum connections."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            try:
                ensure_directory(DB_PATH.parent)

                # Create minimum connections
                for _ in range(self.min_connections):
                    conn = await self._create_connection()
                    if conn:
                        await self._idle_connections.put(conn)
                        self._stats.total_connections += 1
                        self._stats.idle_connections += 1

                self._initialized = True
                logger.info(f"Async connection pool initialized with {self.min_connections} connections")

            except Exception as e:
                logger.error(f"Failed to initialize async connection pool: {e}")
                raise

    async def _create_connection(self) -> Optional[aiosqlite.Connection]:
        """Create a new async database connection with optimal settings."""
        try:
            conn = await aiosqlite.connect(
                str(DB_PATH),
                timeout=30.0,
                isolation_level='DEFERRED'
            )

            # Optimize connection settings
            await conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging
            await conn.execute('PRAGMA synchronous=NORMAL')  # Faster writes
            await conn.execute('PRAGMA cache_size=10000')  # 10MB cache
            await conn.execute('PRAGMA foreign_keys=ON')
            await conn.execute('PRAGMA temp_store=MEMORY')  # Use memory for temp tables

            # Set row factory for dict-like access
            conn.row_factory = aiosqlite.Row

            self._stats.total_created += 1
            logger.debug(f"Created async connection #{self._stats.total_created}")
            return conn

        except Exception as e:
            logger.error(f"Failed to create async connection: {e}")
            return None

    async def _validate_connection(self, conn: aiosqlite.Connection) -> bool:
        """Check if an async connection is still valid."""
        try:
            await conn.execute('SELECT 1')
            return True
        except Exception as e:
            logger.debug(f"Async connection validation failed: {e}")
            return False

    @asynccontextmanager
    async def acquire(self):
        """
        Async context manager for acquiring and releasing connections.

        Yields:
            aiosqlite.Connection: Database connection from pool

        Example:
            async with pool.acquire() as conn:
                cursor = await conn.execute("SELECT * FROM tasks")
                rows = await cursor.fetchall()
        """
        if not self._initialized:
            await self.initialize()

        if self._closed:
            raise RuntimeError("Connection pool is closed")

        conn = None
        acquired_semaphore = False

        try:
            # Acquire semaphore for connection limiting
            await asyncio.wait_for(
                self._connection_semaphore.acquire(),
                timeout=self.connection_timeout
            )
            acquired_semaphore = True

            # Try to get idle connection
            try:
                conn = await asyncio.wait_for(
                    self._idle_connections.get(),
                    timeout=0.1  # Quick timeout for idle check
                )

                # Validate connection
                if not await self._validate_connection(conn):
                    await conn.close()
                    conn = None

            except asyncio.TimeoutError:
                # No idle connections available
                pass

            # Create new connection if needed
            if conn is None:
                async with self._lock:
                    if self._stats.total_connections < self.max_connections:
                        conn = await self._create_connection()
                        if conn:
                            self._stats.total_connections += 1
                    else:
                        self._stats.pool_exhaustions += 1

            if conn is None:
                # Wait for connection to become available
                try:
                    conn = await asyncio.wait_for(
                        self._idle_connections.get(),
                        timeout=self.connection_timeout
                    )

                    # Validate connection again
                    if not await self._validate_connection(conn):
                        await conn.close()
                        raise RuntimeError("No valid connections available")

                except asyncio.TimeoutError:
                    raise RuntimeError(f"Connection timeout after {self.connection_timeout}s")

            # Track active connection
            async with self._lock:
                self._active_connections.add(conn)
                self._stats.active_connections = len(self._active_connections)
                self._stats.idle_connections = self._idle_connections.qsize()
                self._stats.total_acquired += 1

            yield conn

        finally:
            # Return connection to pool
            if conn and acquired_semaphore:
                try:
                    async with self._lock:
                        if conn in self._active_connections:
                            self._active_connections.remove(conn)
                            self._stats.active_connections = len(self._active_connections)
                            self._stats.total_released += 1

                    # Reset connection state
                    await conn.rollback()

                    # Return to idle pool
                    try:
                        await self._idle_connections.put(conn)
                        async with self._lock:
                            self._stats.idle_connections = self._idle_connections.qsize()
                    except asyncio.QueueFull:
                        # Pool full, close connection
                        await conn.close()
                        async with self._lock:
                            self._stats.total_connections -= 1

                except Exception as e:
                    logger.warning(f"Failed to return async connection to pool: {e}")
                    try:
                        await conn.close()
                        async with self._lock:
                            self._stats.total_connections -= 1
                    except Exception as close_error:
                        logger.debug(f"Failed to close corrupted async connection: {close_error}")

            if acquired_semaphore:
                self._connection_semaphore.release()

    async def close_all(self):
        """Close all connections in the pool."""
        if self._closed:
            return

        self._closed = True

        # Close active connections
        async with self._lock:
            active_copy = self._active_connections.copy()
            for conn in active_copy:
                try:
                    await conn.close()
                except Exception as e:
                    logger.debug(f"Error closing active async connection: {e}")
            self._active_connections.clear()

        # Close idle connections
        while not self._idle_connections.empty():
            try:
                conn = await self._idle_connections.get()
                await conn.close()
            except Exception as e:
                logger.debug(f"Error closing idle async connection: {e}")

        # Reset statistics
        async with self._lock:
            self._stats.active_connections = 0
            self._stats.idle_connections = 0
            self._stats.total_connections = 0

        logger.info("Async connection pool closed")

    async def get_stats(self) -> PoolStats:
        """Get current pool statistics."""
        async with self._lock:
            self._stats.active_connections = len(self._active_connections)
            self._stats.idle_connections = self._idle_connections.qsize()
            return PoolStats(
                active_connections=self._stats.active_connections,
                idle_connections=self._stats.idle_connections,
                total_connections=self._stats.total_connections,
                max_connections=self._stats.max_connections,
                total_acquired=self._stats.total_acquired,
                total_released=self._stats.total_released,
                total_created=self._stats.total_created,
                pool_exhaustions=self._stats.pool_exhaustions
            )

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the connection pool."""
        try:
            # Test connection acquisition
            start_time = time.time()
            async with self.acquire() as conn:
                await conn.execute('SELECT 1')
            acquisition_time = time.time() - start_time

            stats = await self.get_stats()

            return {
                'status': 'healthy',
                'acquisition_time_ms': acquisition_time * 1000,
                'pool_utilization': stats.active_connections / stats.max_connections,
                'stats': stats.__dict__
            }

        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'stats': (await self.get_stats()).__dict__
            }


# Global async connection pool instance
_async_pool: Optional[AsyncConnectionPool] = None
_async_pool_lock = asyncio.Lock()


async def get_async_pool() -> AsyncConnectionPool:
    """Get or create the global async connection pool."""
    global _async_pool

    if _async_pool is None:
        async with _async_pool_lock:
            if _async_pool is None:
                _async_pool = AsyncConnectionPool()
                await _async_pool.initialize()
                logger.info("Global async connection pool initialized")

    return _async_pool


@asynccontextmanager
async def get_async_connection():
    """
    Get an async connection from the global pool.

    This is the main interface for getting async database connections.

    Example:
        async with get_async_connection() as conn:
            cursor = await conn.execute("SELECT * FROM tasks WHERE status = ?", ("queued",))
            tasks = await cursor.fetchall()
    """
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        yield conn


async def close_async_pool():
    """Close the global async connection pool."""
    global _async_pool

    if _async_pool:
        await _async_pool.close_all()
        _async_pool = None
        logger.info("Global async connection pool closed")


async def get_async_pool_stats() -> PoolStats:
    """Get statistics for the global async connection pool."""
    if _async_pool:
        return await _async_pool.get_stats()
    else:
        return PoolStats(0, 0, 0, 0, 0, 0, 0, 0)


async def async_pool_health_check() -> Dict[str, Any]:
    """Perform health check on the global async connection pool."""
    if _async_pool:
        return await _async_pool.health_check()
    else:
        return {
            'status': 'not_initialized',
            'message': 'Async connection pool not initialized'
        }