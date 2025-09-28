#!/usr/bin/env python3
"""
Test script to validate the database connection pool fixes.

This test validates that:
1. EcoSystemiser uses the shared database service correctly
2. Connections are properly pooled and cleaned up
3. No connection leaks occur under concurrent access
4. The integration with Hive orchestrator works correctly
"""

import pytest
import sqlite3
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

# Import EcoSystemiser database functions
from EcoSystemiser.db import (
    get_ecosystemiser_connection,
    ecosystemiser_transaction,
    get_ecosystemiser_db_path,
    validate_hive_integration,
    ensure_database_schema
)

# Import shared database service
try:
    from hive_orchestrator.core.db import (
        get_database_stats,
        database_health_check,
        close_all_database_pools
    )
    HIVE_DB_AVAILABLE = True
except ImportError:
    HIVE_DB_AVAILABLE = False


class TestDatabaseConnectionFix:
    """Test cases for database connection pool fixes."""

    def setup_method(self):
        """Set up test environment."""
        # Ensure clean test environment
        if HIVE_DB_AVAILABLE:
            close_all_database_pools()

    def teardown_method(self):
        """Clean up after tests."""
        if HIVE_DB_AVAILABLE:
            close_all_database_pools()

    def test_basic_connection(self):
        """Test basic database connection works."""
        with get_ecosystemiser_connection() as conn:
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_transaction_management(self):
        """Test transaction context manager works correctly."""
        # Ensure schema exists
        ensure_database_schema()

        # Clean up any existing test data
        with get_ecosystemiser_connection() as conn:
            conn.execute("DROP TABLE IF EXISTS test_transactions")
            conn.commit()

        with ecosystemiser_transaction() as conn:
            # Create a test table
            conn.execute("""
                CREATE TABLE test_transactions (
                    id INTEGER PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("INSERT INTO test_transactions (value) VALUES ('test')")

        # Verify data was committed
        with get_ecosystemiser_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM test_transactions WHERE value = 'test'")
            count = cursor.fetchone()[0]
            assert count == 1

        # Test rollback on exception
        try:
            with ecosystemiser_transaction() as conn:
                conn.execute("INSERT INTO test_transactions (value) VALUES ('rollback_test')")
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify rollback occurred
        with get_ecosystemiser_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM test_transactions WHERE value = 'rollback_test'")
            count = cursor.fetchone()[0]
            assert count == 0

        # Clean up
        with get_ecosystemiser_connection() as conn:
            conn.execute("DROP TABLE test_transactions")
            conn.commit()

    def test_concurrent_access(self):
        """Test concurrent database access works correctly."""
        ensure_database_schema()

        def worker_function(worker_id):
            """Worker function for concurrent testing."""
            results = []
            for i in range(10):
                with get_ecosystemiser_connection() as conn:
                    # Simulate some database work
                    cursor = conn.execute("SELECT ? as worker_id, ? as iteration", (worker_id, i))
                    result = cursor.fetchone()
                    results.append((result[0], result[1]))
                    time.sleep(0.01)  # Small delay to increase concurrency
            return results

        # Run multiple workers concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_function, i) for i in range(5)]
            results = [future.result() for future in futures]

        # Verify all workers completed successfully
        assert len(results) == 5
        for worker_results in results:
            assert len(worker_results) == 10

    def test_connection_cleanup(self):
        """Test that connections are properly cleaned up."""
        if not HIVE_DB_AVAILABLE:
            pytest.skip("Hive database service not available")

        initial_stats = get_database_stats()

        # Perform multiple connection operations
        for i in range(50):
            with get_ecosystemiser_connection() as conn:
                conn.execute("SELECT 1")

        # Allow some time for cleanup
        time.sleep(0.5)

        final_stats = get_database_stats()

        # Check that we're not leaking connections
        ecosystemiser_stats = final_stats.get("ecosystemiser", {})
        if ecosystemiser_stats:
            # Should have reasonable number of idle connections
            assert ecosystemiser_stats.get("pool_size", 0) <= 10
            print(f"Pool stats after operations: {ecosystemiser_stats}")

    def test_hive_integration(self):
        """Test Hive database service integration."""
        integration_ok = validate_hive_integration()
        if HIVE_DB_AVAILABLE:
            assert integration_ok, "Hive integration should work when service is available"

        # Should work even without Hive service (fallback mode)
        assert integration_ok or not HIVE_DB_AVAILABLE

    def test_health_check(self):
        """Test database health check functionality."""
        if not HIVE_DB_AVAILABLE:
            pytest.skip("Hive database service not available")

        health = database_health_check()
        assert isinstance(health, dict)

        # Should have ecosystemiser database entry if we've used it
        with get_ecosystemiser_connection() as conn:
            conn.execute("SELECT 1")

        health = database_health_check()
        if "ecosystemiser" in health:
            assert health["ecosystemiser"]["status"] in ["healthy", "unhealthy"]

    def test_schema_initialization(self):
        """Test that schema initialization works correctly."""
        ensure_database_schema()

        with get_ecosystemiser_connection() as conn:
            # Check that expected tables exist
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name LIKE 'eco_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            # Should have some EcoSystemiser tables
            assert len(tables) > 0, "Schema initialization should create tables"

    def test_database_path_configuration(self):
        """Test that database path configuration works."""
        db_path = get_ecosystemiser_db_path()
        assert isinstance(db_path, Path)
        assert db_path.name == "ecosystemiser.db"

        # Ensure parent directory exists
        assert db_path.parent.exists()

    def test_error_handling(self):
        """Test error handling in database operations."""
        with get_ecosystemiser_connection() as conn:
            # Test that SQL errors are properly handled
            with pytest.raises(sqlite3.Error):
                conn.execute("SELECT * FROM nonexistent_table")

        # Test transaction rollback on error
        try:
            with ecosystemiser_transaction() as conn:
                conn.execute("INSERT INTO nonexistent_table VALUES (1)")
        except sqlite3.Error:
            pass  # Expected error

        # Database should still be accessible after error
        with get_ecosystemiser_connection() as conn:
            cursor = conn.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1


def run_load_test():
    """Run a load test to verify connection pool behavior under stress."""
    print("Running database connection load test...")

    ensure_database_schema()

    def stress_worker(worker_id, iterations=100):
        """Stress test worker function."""
        for i in range(iterations):
            try:
                with ecosystemiser_transaction() as conn:
                    # Create test table if it doesn't exist
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS load_test (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            worker_id INTEGER,
                            iteration INTEGER,
                            timestamp REAL
                        )
                    """)

                    # Insert test data
                    conn.execute(
                        "INSERT INTO load_test (worker_id, iteration, timestamp) VALUES (?, ?, ?)",
                        (worker_id, i, time.time())
                    )

                    # Read some data
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM load_test WHERE worker_id = ?",
                        (worker_id,)
                    )
                    count = cursor.fetchone()[0]

                    if i % 20 == 0:
                        print(f"Worker {worker_id}: iteration {i}, total records: {count}")

            except Exception as e:
                print(f"Worker {worker_id} error at iteration {i}: {e}")
                raise

    # Run stress test with multiple workers
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(stress_worker, i, 50) for i in range(8)]
        results = [future.result() for future in futures]

    duration = time.time() - start_time
    print(f"Load test completed in {duration:.2f} seconds")

    # Check final state
    with get_ecosystemiser_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM load_test")
        total_records = cursor.fetchone()[0]
        print(f"Total records created: {total_records}")

    if HIVE_DB_AVAILABLE:
        stats = get_database_stats()
        print(f"Final pool stats: {stats}")

        health = database_health_check()
        print(f"Health check: {health}")


if __name__ == "__main__":
    # Run basic tests
    test_instance = TestDatabaseConnectionFix()
    test_instance.setup_method()

    try:
        print("Testing basic connection...")
        test_instance.test_basic_connection()
        print("✅ Basic connection test passed")

        print("Testing transaction management...")
        test_instance.test_transaction_management()
        print("✅ Transaction management test passed")

        print("Testing concurrent access...")
        test_instance.test_concurrent_access()
        print("✅ Concurrent access test passed")

        print("Testing Hive integration...")
        test_instance.test_hive_integration()
        print("✅ Hive integration test passed")

        print("Testing schema initialization...")
        test_instance.test_schema_initialization()
        print("✅ Schema initialization test passed")

        print("Testing error handling...")
        test_instance.test_error_handling()
        print("✅ Error handling test passed")

        # Run load test
        run_load_test()
        print("✅ Load test completed")

        print("\n🎉 All database connection tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
    finally:
        test_instance.teardown_method()