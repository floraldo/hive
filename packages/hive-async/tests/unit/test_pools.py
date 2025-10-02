"""
Unit tests for pools module (ConnectionPool).

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

    def __init__(self, conn_id: int, healthy: bool = True):
        self.conn_id = conn_id
        self.healthy = healthy
        self.closed = False

    def __repr__(self):
        return f"MockConnection({self.conn_id})"


class TestPoolConfig:
    """Test PoolConfig dataclass."""

    def test_pool_config_defaults(self):
        """Test PoolConfig with default values."""
        config = PoolConfig()

        assert config.min_size == 1
        assert config.max_size == 10
        assert config.acquire_timeout == 30.0
        assert config.max_inactive_time == 3600.0
        assert config.health_check_interval == 300.0

    def test_pool_config_custom_values(self):
        """Test PoolConfig with custom values."""
        config = PoolConfig(
            min_size=2,
            max_size=20,
            acquire_timeout=10.0,
            max_inactive_time=1800.0,
            health_check_interval=60.0,
        )

        assert config.min_size == 2
        assert config.max_size == 20
        assert config.acquire_timeout == 10.0
        assert config.max_inactive_time == 1800.0
        assert config.health_check_interval == 60.0


class TestConnectionPool:
    """Test ConnectionPool class."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test basic pool initialization."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)

        config = PoolConfig(min_size=2, max_size=5)
        pool = ConnectionPool(
            create_connection=create_conn,
            config=config,
        )

        async with pool:
            # Should create min_size connections during initialization
            assert conn_counter == 2

    @pytest.mark.asyncio
    async def test_pool_acquire_and_release(self):
        """Test acquiring and releasing connections."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)

        config = PoolConfig(min_size=1, max_size=3)
        pool = ConnectionPool(
            create_connection=create_conn,
            config=config,
        )

        async with pool:
            # Acquire a connection
            conn1 = await pool.acquire_async()
            assert conn1 is not None
            assert isinstance(conn1, MockConnection)

            # Release it back
            await pool.release_async(conn1)

            # Acquire again - should get the same connection (reuse)
            conn2 = await pool.acquire_async()
            assert conn2 is conn1  # Same object reused

    @pytest.mark.asyncio
    async def test_pool_max_size_limit(self):
        """Test that pool respects max_size limit."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)

        config = PoolConfig(min_size=1, max_size=2, acquire_timeout=0.5)
        pool = ConnectionPool(
            create_connection=create_conn,
            config=config,
        )

        async with pool:
            # Acquire up to max_size
            conn1 = await pool.acquire_async(),
            conn2 = await pool.acquire_async()

            # Try to acquire beyond max_size - should timeout
            with pytest.raises(asyncio.TimeoutError):
                await pool.acquire_async()

            # Release one and try again - should succeed
            await pool.release_async(conn1)
            conn3 = await pool.acquire_async()
            assert conn3 is not None

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
        pool = ConnectionPool(
            create_connection=create_conn,
            close_connection=lambda c: setattr(c, "closed", True),
            health_check=health_check,
            config=config,
        )

        async with pool:
            # Acquire a connection
            conn1 = await pool.acquire_async()
            assert conn1.healthy

            # Mark it unhealthy and release
            conn1.healthy = False
            await pool.release_async(conn1)

            # Acquire again - should get a NEW healthy connection
            conn2 = await pool.acquire_async()
            assert conn2.healthy
            assert conn2.conn_id != conn1.conn_id  # Different connection

    @pytest.mark.asyncio
    async def test_pool_close(self):
        """Test closing the pool."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)

        config = PoolConfig(min_size=2, max_size=5)
        pool = ConnectionPool(
            create_connection=create_conn,
            close_connection=lambda c: setattr(c, "closed", True),
            config=config,
        )

        await pool.initialize_async()

        # Acquire a connection
        conn1 = await pool.acquire_async()

        # Close the pool
        await pool.close_async()

        # Try to acquire after close - should fail
        with pytest.raises(RuntimeError, match="Pool is closed"):
            await pool.acquire_async()

    @pytest.mark.asyncio
    async def test_pool_context_manager(self):
        """Test pool as async context manager."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)

        config = PoolConfig(min_size=1, max_size=3)
        pool = ConnectionPool(
            create_connection=create_conn,
            config=config,
        )

        # Use as context manager
        async with pool:
            conn = await pool.acquire_async()
            assert conn is not None

        # Pool should be closed after exiting context
        assert pool._closed

    @pytest.mark.asyncio
    async def test_pool_concurrent_acquire(self):
        """Test concurrent connection acquisition."""
        conn_counter = 0

        async def create_conn_async():
            nonlocal conn_counter
            await asyncio.sleep(0.01)  # Simulate async creation
            conn_counter += 1
            return MockConnection(conn_counter)

        config = PoolConfig(min_size=0, max_size=5)
        pool = ConnectionPool(
            create_connection=create_conn_async,
            config=config,
        )

        async with pool:
            # Acquire multiple connections concurrently
            tasks = [pool.acquire_async() for _ in range(3)],
            conns = await asyncio.gather(*tasks)

            assert len(conns) == 3
            assert all(isinstance(c, MockConnection) for c in conns)

            # All should have unique IDs
            ids = [c.conn_id for c in conns]
            assert len(set(ids)) == 3


class TestAsyncConnectionManager:
    """Test AsyncConnectionManager class."""

    @pytest.mark.asyncio
    async def test_connection_manager_basic(self):
        """Test basic connection manager functionality."""
        mock_conn = MockConnection(1)

        async def acquire():
            return mock_conn

        async def release(conn):
            conn.closed = False

        manager = AsyncConnectionManager(
            acquire_func=acquire,
            release_func=release,
        )

        # Use as context manager
        async with manager as conn:
            assert conn is mock_conn
            assert not conn.closed

    @pytest.mark.asyncio
    async def test_connection_manager_exception_handling(self):
        """Test connection manager releases on exception."""
        mock_conn = MockConnection(1),
        release_called = False

        async def acquire():
            return mock_conn

        async def release(conn):
            nonlocal release_called
            release_called = True
            conn.closed = True

        manager = AsyncConnectionManager(
            acquire_func=acquire,
            release_func=release,
        )

        # Exception should still trigger release
        with pytest.raises(ValueError):
            async with manager as conn:
                raise ValueError("Test error")

        assert release_called
        assert mock_conn.closed


class TestPoolConnectionReuse:
    """Test connection reuse patterns."""

    @pytest.mark.asyncio
    async def test_connection_reuse(self):
        """Test that connections are reused efficiently."""
        conn_counter = 0

        def create_conn():
            nonlocal conn_counter
            conn_counter += 1
            return MockConnection(conn_counter)

        config = PoolConfig(min_size=2, max_size=5)
        pool = ConnectionPool(
            create_connection=create_conn,
            config=config,
        )

        async with pool:
            # Initial connections created (min_size=2)
            initial_count = conn_counter
            assert initial_count == 2

            # Acquire and release multiple times
            for _ in range(10):
                conn = await pool.acquire_async()
                await pool.release_async(conn)

            # Should not have created many new connections
            assert conn_counter <= initial_count + 1  # At most 1 new connection

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
        pool = ConnectionPool(
            create_connection=create_conn_async,
            config=config,
        )

        async with pool:
            # Simulate burst of requests
            async def simulate_request():
                conn = await pool.acquire_async()
                await asyncio.sleep(0.05)  # Simulate work
                await pool.release_async(conn)

            # Launch many concurrent requests
            tasks = [simulate_request() for _ in range(20)]
            await asyncio.gather(*tasks)

            # Pool should have created connections as needed but not exceed max
            assert conn_counter <= config.max_size
