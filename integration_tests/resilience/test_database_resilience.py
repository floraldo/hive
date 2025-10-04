"""
Database Resilience Tests

Chaos engineering tests to validate database connection resilience:
- Connection pool exhaustion scenarios
- Database unavailability simulation
- Transaction rollback behavior
- Connection recovery validation

Part of the Production Shield Initiative for foundational chaos engineering.
"""
import asyncio
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

try:
    from hive_async import AsyncExecutor, get_async_connection
    from hive_db.async_pool import AsyncConnectionPool
    from hive_db.sqlite_connector import SQLiteConnector
    async_executor = AsyncExecutor()
except ImportError:

    class AsyncConnectionPool:

        def __init__(self, database_url: str, min_connections: int=1, max_connections: int=10):
            self.database_url = database_url
            self.min_connections = min_connections
            self.max_connections = max_connections
            self.active_connections = 0
            self.available_connections = []
            self.is_healthy = True

        async def get_connection(self):
            if not self.is_healthy:
                raise Exception('Database pool is unhealthy')
            if self.active_connections >= self.max_connections:
                raise Exception('Connection pool exhausted')
            self.active_connections += 1
            return MockDatabaseConnection()

        async def return_connection(self, conn):
            self.active_connections -= 1

        async def close(self):
            self.active_connections = 0

    class SQLiteConnector:

        def __init__(self, database_path: str):
            self.database_path = database_path

        async def execute_query(self, query: str, params: tuple=()):
            await asyncio.sleep(0.01)
            return []

class MockDatabaseConnection:
    """Mock database connection for testing"""

    def __init__(self, should_fail: bool=False, delay: float=0.0):
        self.should_fail = should_fail
        self.delay = delay
        self.is_closed = False
        self.transaction_active = False

    async def execute(self, query: str, params: tuple=()):
        """Execute a database query"""
        if self.is_closed:
            raise Exception('Connection is closed')
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        if self.should_fail:
            raise sqlite3.OperationalError('Database operation failed')
        return MockCursor()

    async def begin_transaction(self):
        """Begin a database transaction"""
        if self.transaction_active:
            raise Exception('Transaction already active')
        self.transaction_active = True

    async def commit(self):
        """Commit the current transaction"""
        if not self.transaction_active:
            raise Exception('No active transaction')
        self.transaction_active = False

    async def rollback(self):
        """Rollback the current transaction"""
        if not self.transaction_active:
            raise Exception('No active transaction')
        self.transaction_active = False

    async def close(self):
        """Close the connection"""
        self.is_closed = True

class MockCursor:
    """Mock database cursor"""

    def __init__(self, rows: list[tuple]=None):
        self.rows = rows or []
        self.rowcount = len(self.rows)

    async def fetchall(self):
        return self.rows

    async def fetchone(self):
        return self.rows[0] if self.rows else None

class ResilientDatabaseService:
    """Database service with resilience patterns"""

    def __init__(self, connection_pool: AsyncConnectionPool):
        self.pool = connection_pool
        self.retry_attempts = 3
        self.retry_delay = 0.1
        self.circuit_breaker_failures = 0
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_open = False
        self.circuit_breaker_last_failure = None
        self.circuit_breaker_timeout = 10

    async def execute_with_resilience(self, query: str, params: tuple=()) -> list[tuple]:
        """Execute query with resilience patterns"""
        if self.circuit_breaker_open:
            if time.time() - self.circuit_breaker_last_failure < self.circuit_breaker_timeout:
                raise Exception('Circuit breaker is open - database unavailable')
            else:
                self.circuit_breaker_open = False
        last_exception = None
        for attempt in range(self.retry_attempts):
            try:
                conn = await self.pool.get_connection()
                try:
                    cursor = await conn.execute(query, params)
                    result = await cursor.fetchall()
                    self.circuit_breaker_failures = 0
                    return result
                finally:
                    await self.pool.return_connection(conn)
            except Exception as e:
                last_exception = e
                self.circuit_breaker_failures += 1
                if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
                    self.circuit_breaker_open = True
                    self.circuit_breaker_last_failure = time.time()
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * 2 ** attempt)
        raise last_exception

    async def execute_transaction(self, queries: list[tuple]) -> bool:
        """Execute multiple queries in a transaction with rollback on failure"""
        conn = await self.pool.get_connection()
        try:
            await conn.begin_transaction()
            for query, params in queries:
                await conn.execute(query, params)
            await conn.commit()
            return True
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await self.pool.return_connection(conn)

@pytest.mark.crust
class TestDatabaseResilience:
    """Test suite for database resilience under failure conditions"""

    @pytest.fixture
    async def temp_database(self):
        """Create a temporary SQLite database for testing"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        db_path = Path(temp_file.name)
        async with get_async_connection(str(db_path)) as conn:
            await conn.execute(',\n                CREATE TABLE test_table (\n                    id INTEGER PRIMARY KEY,\n                    name TEXT NOT NULL,\n                    value INTEGER\n                )\n            ')
            await conn.commit()
        yield str(db_path)
        db_path.unlink()

    @pytest.fixture
    def connection_pool(self, temp_database):
        """Create a connection pool for testing"""
        return AsyncConnectionPool(temp_database, min_connections=2, max_connections=5)

    @pytest.fixture
    def resilient_service(self, connection_pool):
        """Create a resilient database service"""
        return ResilientDatabaseService(connection_pool)

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_connection_pool_normal_operation(self, connection_pool):
        """Test connection pool under normal conditions"""
        connections = []
        for _i in range(3):
            conn = await connection_pool.get_connection()
            connections.append(conn)
            assert not conn.is_closed
        assert connection_pool.active_connections == 3
        for conn in connections:
            await connection_pool.return_connection(conn)
        assert connection_pool.active_connections == 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self, connection_pool):
        """Test connection pool behavior when exhausted"""
        connections = []
        for _i in range(connection_pool.max_connections):
            conn = await connection_pool.get_connection()
            connections.append(conn)
        with pytest.raises(Exception, match='Connection pool exhausted'):
            await connection_pool.get_connection()
        await connection_pool.return_connection(connections[0])
        new_conn = await connection_pool.get_connection()
        assert new_conn is not None
        await connection_pool.return_connection(new_conn)
        for conn in connections[1:]:
            await connection_pool.return_connection(conn)

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_database_retry_mechanism(self, resilient_service):
        """Test retry mechanism for transient database failures"""
        call_count = 0

        async def failing_get_connection():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise sqlite3.OperationalError('Temporary database error')
            else:
                return MockDatabaseConnection()
        resilient_service.pool.get_connection = failing_get_connection
        result = await resilient_service.execute_with_resilience('SELECT 1')
        assert result is not None
        assert call_count == 3

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_database_circuit_breaker(self, resilient_service):
        """Test circuit breaker opens after repeated failures"""

        async def always_failing_get_connection():
            raise sqlite3.OperationalError('Database is down')
        resilient_service.pool.get_connection = always_failing_get_connection
        for _i in range(6):
            with pytest.raises(Exception):
                await resilient_service.execute_with_resilience('SELECT 1')
        assert resilient_service.circuit_breaker_open
        start_time = time.time()
        with pytest.raises(Exception, match='Circuit breaker is open'):
            await resilient_service.execute_with_resilience('SELECT 1')
        end_time = time.time()
        assert end_time - start_time < 0.1

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_transaction_rollback_on_failure(self, resilient_service):
        """Test transaction rollback behavior on failure"""
        call_count = 0

        class FailingConnection(MockDatabaseConnection):

            async def execute(self, query, params=()):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise sqlite3.OperationalError('Query failed')
                return MockCursor()

        async def get_failing_connection():
            return FailingConnection()
        resilient_service.pool.get_connection = get_failing_connection
        queries = [('INSERT INTO test_table (name, value) VALUES (?, ?)', ('test1', 100)), ('INSERT INTO test_table (name, value) VALUES (?, ?)', ('test2', 200)), ('INSERT INTO test_table (name, value) VALUES (?, ?)', ('test3', 300))]
        with pytest.raises(sqlite3.OperationalError):
            await resilient_service.execute_transaction(queries)
        assert call_count == 2

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_concurrent_database_operations(self, resilient_service):
        """Test database resilience under concurrent load"""
        slow_connection_count = 0

        async def mixed_speed_connections():
            nonlocal slow_connection_count
            slow_connection_count += 1
            delay = 0.1 if slow_connection_count % 3 == 0 else 0.0
            return MockDatabaseConnection(delay=delay)
        resilient_service.pool.get_connection = mixed_speed_connections
        tasks = []
        for i in range(20):
            task = await async_executor.submit(resilient_service.execute_with_resilience(f'SELECT {i}'))
            tasks.append(task)
        start_time = time.time()
        results = await async_executor.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == 20
        total_time = end_time - start_time
        assert total_time < 2.0
        print(f'Completed 20 concurrent operations in {total_time:.2f} seconds')

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_database_recovery_after_failure(self, resilient_service):
        """Test database service recovery after temporary failure"""
        failure_mode = True

        async def intermittent_failing_connection():
            if failure_mode:
                raise sqlite3.OperationalError('Database temporarily unavailable')
            else:
                return MockDatabaseConnection()
        resilient_service.pool.get_connection = intermittent_failing_connection
        for _i in range(6):
            with pytest.raises(Exception):
                await resilient_service.execute_with_resilience('SELECT 1')
        assert resilient_service.circuit_breaker_open
        failure_mode = False
        await asyncio.sleep(0.1)
        resilient_service.circuit_breaker_timeout = 0.05
        result = await resilient_service.execute_with_resilience('SELECT 1')
        assert result is not None
        assert not resilient_service.circuit_breaker_open
        assert resilient_service.circuit_breaker_failures == 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_database_connection_cleanup(self, connection_pool):
        """Test proper cleanup of database connections"""
        connections = []
        for _i in range(3):
            conn = await connection_pool.get_connection()
            connections.append(conn)
        await connection_pool.close()
        assert connection_pool.active_connections == 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_database_metrics_collection(self, resilient_service):
        """Test collection of database operation metrics"""
        operation_count = 0
        total_duration = 0

        class MetricsConnection(MockDatabaseConnection):

            async def execute(self, query, params=()):
                nonlocal operation_count, total_duration
                start_time = time.time()
                result = await super().execute(query, params)
                end_time = time.time()
                operation_count += 1
                total_duration += end_time - start_time
                return result

        async def get_metrics_connection():
            return MetricsConnection()
        resilient_service.pool.get_connection = get_metrics_connection
        for i in range(10):
            await resilient_service.execute_with_resilience(f'SELECT {i}')
        assert operation_count == 10
        assert total_duration > 0
        avg_duration = total_duration / operation_count
        print(f'Average operation duration: {avg_duration:.4f} seconds')
        print(f'Total operations: {operation_count}')
        print(f'Circuit breaker failures: {resilient_service.circuit_breaker_failures}')
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--asyncio-mode=auto'])
