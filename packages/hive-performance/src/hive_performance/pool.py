"""Enhanced connection pool configuration"""

from typing import Optional
from dataclasses import dataclass

@dataclass
class PoolConfig:
    """Connection pool configuration"""
    min_size: int = 5
    max_size: int = 20
    max_idle_time: int = 300  # seconds
    connection_timeout: int = 10  # seconds
    retry_attempts: int = 3
    retry_delay: float = 0.5

    # Monitoring
    enable_metrics: bool = True
    log_slow_queries: bool = True
    slow_query_threshold: float = 1.0  # seconds


"""Enhanced async connection pool with monitoring"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from hive_logging import get_logger

logger = get_logger(__name__)


class EnhancedAsyncPool:
    """Async connection pool with monitoring and metrics"""

    def __init__(self, config: PoolConfig):
        self.config = config
        self._pool = []
        self._in_use = set()
        self._metrics = {
            "connections_created": 0,
            "connections_reused": 0,
            "connections_closed": 0,
            "slow_queries": 0,
            "errors": 0,
        }
        self._lock = asyncio.Lock()

    async def acquire_async(self) -> Any:
        """Acquire connection with timeout and monitoring"""
        start_time = time.time()

        async with self._lock:
            # Try to get from pool
            if self._pool:
                conn = self._pool.pop()
                self._metrics["connections_reused"] += 1
            else:
                # Create new connection
                conn = await self._create_connection_async()
                self._metrics["connections_created"] += 1

            self._in_use.add(conn)

        acquisition_time = time.time() - start_time
        if acquisition_time > self.config.connection_timeout / 2:
            logger.warning(f"Slow connection acquisition: {acquisition_time:.2f}s")

        return conn

    async def release_async(self, conn: Any) -> None:
        """Release connection back to pool"""
        async with self._lock:
            self._in_use.discard(conn)

            if len(self._pool) < self.config.max_size:
                self._pool.append(conn)
            else:
                await self._close_connection_async(conn)
                self._metrics["connections_closed"] += 1

    async def _create_connection_async(self) -> Any:
        """Create new connection with retry logic"""
        for attempt in range(self.config.retry_attempts):
            try:
                # Actual connection creation would go here
                return await asyncio.sleep(0)  # Placeholder
            except Exception as e:
                if attempt == self.config.retry_attempts - 1:
                    self._metrics["errors"] += 1
                    raise
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))

    async def _close_connection_async(self, conn: Any) -> None:
        """Close connection gracefully"""
        try:
            # Actual connection closing would go here
            await asyncio.sleep(0)  # Placeholder
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

    @asynccontextmanager
    async def connection(self):
        """Context manager for connection acquisition"""
        conn = await self.acquire_async()
        try:
            yield conn
        finally:
            await self.release_async(conn)

    def get_metrics(self) -> Dict[str, int]:
        """Get pool metrics"""
        return {
            **self._metrics,
            "pool_size": len(self._pool),
            "in_use": len(self._in_use),
        }

    async def cleanup_async(self) -> None:
        """Cleanup all connections on shutdown"""
        async with self._lock:
            for conn in self._pool:
                await self._close_connection_async(conn)
            self._pool.clear()

            for conn in self._in_use:
                logger.warning("Force closing in-use connection")
                await self._close_connection_async(conn)
            self._in_use.clear()
