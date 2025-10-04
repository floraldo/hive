"""Unit tests for pools module (ConnectionPool).

Tests connection pooling functionality:
- Pool initialization and configuration
- Connection acquisition and release
- Pool size limits (min/max)
- Connection health checks
- Connection reuse and cleanup
- Timeout handling
"""
from __future__ import annotations

import asyncio

import pytest

from hive_async.pools import AsyncConnectionManager, ConnectionPool, PoolConfig


class MockConnection:
    """Mock connection for testing."""

    def __init__(self, conn_id: int, healthy: bool=True):
        self.conn_id = conn_id
        self.healthy = healthy
        self.closed = False

    def __repr__(self):
        return f"MockConnection({self.conn_id})"

@pytest.mark.core
class TestPoolConfig:
    """Test PoolConfig dataclass."""

    @pytest.mark.core
    def test_pool_config_defaults(self):
        """Test PoolConfig with default values."""
        config = PoolConfig()
        assert config.min_size == 1
        assert config.max_size == 10
        assert config.acquire_timeout == 30.0
        assert config.max_inactive_time == 3600.0
        assert config.health_check_interval == 300.0

    @pytest.mark.core
    def test_pool_config_custom_values(self):
        """Test PoolConfig with custom values."""
        config = PoolConfig(min_size=2, max_size=20, acquire_timeout=10.0, max_inactive_time=1800.0, health_check_interval=60.0)
        assert config.min_size == 2
        assert config.max_size == 20
        assert config.acquire_timeout == 10.0
        assert config.max_inactive_time == 1800.0
        assert config.health_check_interval == 60.0

@pytest.mark.core
class TestConnectionPool:
    """Test ConnectionPool class."""

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test basic pool initialization."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)
        config = PoolConfig(min_size=2, max_size=5)
        pool = ConnectionPool(create_connection=create_conn, config=config)
        async with pool:
            assert conn_counter == 2

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_pool_acquire_and_release(self):
        """Test acquiring and releasing connections."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)
        config = PoolConfig(min_size=1, max_size=3)
        pool = ConnectionPool(create_connection=create_conn, config=config)
        async with pool:
            conn1 = await pool.acquire_async()
            assert conn1 is not None
            assert isinstance(conn1, MockConnection)
            await pool.release_async(conn1)
            conn2 = await pool.acquire_async()
            assert conn2 is conn1

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_pool_max_size_limit(self):
        """Test that pool respects max_size limit."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)
        config = PoolConfig(min_size=1, max_size=2, acquire_timeout=0.5)
        pool = ConnectionPool(create_connection=create_conn, config=config)
        async with pool:
            conn1 = (await pool.acquire_async(),)
            await pool.acquire_async()
            with pytest.raises(asyncio.TimeoutError):
                await pool.acquire_async()
            await pool.release_async(conn1)
            conn3 = await pool.acquire_async()
            assert conn3 is not None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_pool_with_health_check(self):
        """Test pool with connection health checking."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)

        def health_check(conn: MockConnection) -> bool:
            return conn.healthy
        config = PoolConfig(min_size=1, max_size=3)
        pool = ConnectionPool(create_connection=create_conn, close_connection=lambda c: setattr(c, "closed", True), health_check=health_check, config=config)
        async with pool:
            conn1 = await pool.acquire_async()
            assert conn1.healthy
            conn1.healthy = False
            await pool.release_async(conn1)
            conn2 = await pool.acquire_async()
            assert conn2.healthy
            assert conn2.conn_id != conn1.conn_id

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_pool_close(self):
        """Test closing the pool."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)
        config = PoolConfig(min_size=2, max_size=5)
        pool = ConnectionPool(create_connection=create_conn, close_connection=lambda c: setattr(c, "closed", True), config=config)
        await pool.initialize_async()
        await pool.acquire_async()
        await pool.close_async()
        with pytest.raises(RuntimeError, match="Pool is closed"):
            await pool.acquire_async()

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_pool_context_manager(self):
        """Test pool as async context manager."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)
        config = PoolConfig(min_size=1, max_size=3)
        pool = ConnectionPool(create_connection=create_conn, config=config)
        async with pool:
            conn = await pool.acquire_async()
            assert conn is not None
        assert pool._closed

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_pool_concurrent_acquire(self):
        """Test concurrent connection acquisition."""
        conn_counter = 0

        async def create_conn_async():
            nonlocal conn_counter
            await asyncio.sleep(0.01)
            conn_counter += 1
            return MockConnection(conn_counter)
        config = PoolConfig(min_size=0, max_size=5)
        pool = ConnectionPool(create_connection=create_conn_async, config=config)
        async with pool:
            tasks = ([pool.acquire_async() for _ in range(3)],)
            conns = await asyncio.gather(*tasks)
            assert len(conns) == 3
            assert all(isinstance(c, MockConnection) for c in conns)
            ids = [c.conn_id for c in conns]
            assert len(set(ids)) == 3

@pytest.mark.core
class TestAsyncConnectionManager:
    """Test AsyncConnectionManager class."""

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_connection_manager_basic(self):
        """Test basic connection manager functionality."""
        mock_conn = MockConnection(1)

        async def acquire():
            return mock_conn

        async def release(conn):
            conn.closed = False
        manager = AsyncConnectionManager(acquire_func=acquire, release_func=release)
        async with manager as conn:
            assert conn is mock_conn
            assert not conn.closed

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_connection_manager_exception_handling(self):
        """Test connection manager releases on exception."""
        mock_conn = (MockConnection(1),)
        release_called = False

        async def acquire():
            return mock_conn

        async def release(conn):
            nonlocal release_called
            release_called = True
            conn.closed = True
        manager = AsyncConnectionManager(acquire_func=acquire, release_func=release)
        with pytest.raises(ValueError):
            async with manager:
                raise ValueError("Test error")
        assert release_called
        assert mock_conn.closed

@pytest.mark.core
class TestPoolConnectionReuse:
    """Test connection reuse patterns."""

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_connection_reuse(self):
        """Test that connections are reused efficiently."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)
        config = PoolConfig(min_size=2, max_size=5)
        pool = ConnectionPool(create_connection=create_conn, config=config)
        async with pool:
            initial_count = conn_counter
            assert initial_count == 2
            for _ in range(10):
                conn = await pool.acquire_async()
                await pool.release_async(conn)
            assert conn_counter <= initial_count + 1

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_pool_load_handling(self):
        """Test pool handles load bursts correctly."""
        conn_counter = 0

        async def create_conn_async():
            nonlocal conn_counter
            await asyncio.sleep(0.01)
            conn_counter += 1
            return MockConnection(conn_counter)
        config = PoolConfig(min_size=1, max_size=10)
        pool = ConnectionPool(create_connection=create_conn_async, config=config)
        async with pool:

            async def simulate_request():
                conn = await pool.acquire_async()
                await asyncio.sleep(0.05)
                await pool.release_async(conn)
            tasks = [simulate_request() for _ in range(20)]
            await asyncio.gather(*tasks)
            assert conn_counter <= config.max_size
