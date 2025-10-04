"""Connection pooling and resource management for async operations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Generic, TypeVar

from hive_logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class PoolConfig:
    """Configuration for connection pools."""

    min_size: int = 1
    max_size: int = 10
    acquire_timeout: float = 30.0
    max_inactive_time: float = 3600.0
    health_check_interval: float = 300.0


class ConnectionPool(Generic[T]):
    """Generic async connection pool with health checking."""

    def __init__(
        self,
        create_connection: Callable[[], T],
        close_connection: Callable[[T], None] | None = None,
        health_check: Callable[[T], bool] | None = None,
        config: PoolConfig | None = None,
    ):
        self.create_connection = create_connection
        self.close_connection = close_connection
        self.health_check = health_check
        self.config = config or PoolConfig()

        self._pool: asyncio.Queue = asyncio.Queue(maxsize=self.config.max_size)
        self._connections: dict[T, float] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        self._health_check_task: asyncio.Task | None = None

    async def __aenter__(self):
        await self.initialize_async()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close_async()

    async def initialize_async(self) -> None:
        """Initialize the connection pool."""
        # Create minimum connections
        for _ in range(self.config.min_size):
            try:
                conn = await self._create_new_connection_async()
                await self._pool.put(conn)
            except Exception as e:
                logger.warning(f"Failed to create initial connection: {e}")

        # Start health check task
        if self.health_check:
            self._health_check_task = asyncio.create_task(self._health_check_loop_async())

    async def _create_new_connection_async(self) -> T:
        """Create a new connection."""
        if asyncio.iscoroutinefunction(self.create_connection):
            conn = await self.create_connection_async()
        else:
            conn = self.create_connection_async()

        self._connections[conn] = asyncio.get_event_loop().time()
        return conn

    async def acquire_async(self) -> T:
        """Acquire a connection from the pool."""
        if self._closed:
            raise RuntimeError("Pool is closed")

        try:
            # Try to get existing connection
            conn = await asyncio.wait_for(self._pool.get(), timeout=self.config.acquire_timeout)

            # Health check if available
            if self.health_check:
                if asyncio.iscoroutinefunction(self.health_check):
                    is_healthy = await self.health_check(conn)
                else:
                    is_healthy = self.health_check(conn)

                if not is_healthy:
                    await self._close_connection_async(conn)
                    conn = await self._create_new_connection_async()

            return conn

        except TimeoutError:
            # Create new connection if pool is empty and under limit
            async with self._lock:
                if len(self._connections) < self.config.max_size:
                    return await self._create_new_connection_async()
                raise RuntimeError("Pool exhausted and max size reached")

    async def release_async(self, connection: T) -> None:
        """Release a connection back to the pool."""
        if self._closed or connection not in self._connections:
            await self._close_connection_async(connection)
            return

        try:
            # Update last used time
            self._connections[connection] = asyncio.get_event_loop().time()
            await self._pool.put(connection)
        except Exception as e:
            logger.warning(f"Error releasing connection: {e}")
            await self._close_connection_async(connection)

    @asynccontextmanager
    async def connection_async(self) -> None:
        """Context manager for acquiring and releasing connections."""
        conn = await self.acquire_async()
        try:
            yield conn
        finally:
            await self.release_async(conn)

    async def _close_connection_async(self, connection: T) -> None:
        """Close a single connection."""
        try:
            if self.close_connection:
                if asyncio.iscoroutinefunction(self.close_connection):
                    await self.close_connection_async(connection)
                else:
                    self.close_connection_async(connection)
            elif hasattr(connection, "close"):
                if asyncio.iscoroutinefunction(connection.close):
                    await connection.close_async()
                else:
                    connection.close_async()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
        finally:
            self._connections.pop(connection, None)

    async def _health_check_loop_async(self) -> None:
        """Periodic health check for connections."""
        while not self._closed:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._cleanup_stale_connections_async()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in health check loop: {e}")

    async def _cleanup_stale_connections_async(self) -> None:
        """Clean up stale connections."""
        current_time = (asyncio.get_event_loop().time(),)
        stale_connections = []

        for conn, last_used in self._connections.items():
            if current_time - last_used > self.config.max_inactive_time:
                stale_connections.append(conn)

        for conn in stale_connections:
            await self._close_connection_async(conn)

    async def close_async(self) -> None:
        """Close the connection pool."""
        self._closed = True

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for conn in list(self._connections.keys()):
            await self._close_connection_async(conn)

    @property
    def size(self) -> int:
        """Current number of connections in the pool."""
        return len(self._connections)

    @property
    def available(self) -> int:
        """Number of available connections in the pool."""
        return self._pool.qsize()


class AsyncConnectionManager:
    """Manages multiple connection pools."""

    def __init__(self) -> None:
        self.pools: dict[str, ConnectionPool] = {}

    def register_pool(self, name: str, pool: ConnectionPool) -> None:
        """Register a connection pool."""
        self.pools[name] = pool

    def get_pool(self, name: str) -> ConnectionPool:
        """Get a connection pool by name."""
        if name not in self.pools:
            raise ValueError(f"Pool '{name}' not found")
        return self.pools[name]

    @asynccontextmanager
    async def connection_async(self, pool_name: str) -> None:
        """Get a connection from a specific pool."""
        pool = self.get_pool(pool_name)
        async with pool.connection_async() as conn:
            yield conn

    async def close_all_async(self) -> None:
        """Close all connection pools."""
        for pool in self.pools.values():
            await pool.close_async()
        self.pools.clear()
