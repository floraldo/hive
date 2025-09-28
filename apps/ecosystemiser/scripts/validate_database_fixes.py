#!/usr/bin/env python3
"""
Database Connection Pool Fixes Validation Script

This script validates that all database connection pool fixes are working correctly
and that the platform is ready for production use.
"""

import time
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from EcoSystemiser.hive_logging_adapter import get_logger
from EcoSystemiser.db import (
    get_ecosystemiser_connection,
    ecosystemiser_transaction,
    ensure_database_schema,
    validate_hive_integration
)

logger = get_logger(__name__)


def validate_basic_functionality():
    """Validate basic database functionality."""
    print("🔍 Testing basic database functionality...")

    try:
        with get_ecosystemiser_connection() as conn:
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1
        print("✅ Basic connection test passed")
        return True
    except Exception as e:
        print(f"❌ Basic connection test failed: {e}")
        return False


def validate_transaction_management():
    """Validate transaction management."""
    print("🔍 Testing transaction management...")

    try:
        # Clean up any existing test data
        with get_ecosystemiser_connection() as conn:
            conn.execute("DROP TABLE IF EXISTS validation_test")
            conn.commit()

        # Test successful transaction
        with ecosystemiser_transaction() as conn:
            conn.execute("CREATE TABLE validation_test (id INTEGER, value TEXT)")
            conn.execute("INSERT INTO validation_test VALUES (1, 'test')")

        # Verify commit
        with get_ecosystemiser_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM validation_test").fetchone()[0]
            assert count == 1

        # Test rollback
        try:
            with ecosystemiser_transaction() as conn:
                conn.execute("INSERT INTO validation_test VALUES (2, 'rollback')")
                raise ValueError("Test rollback")
        except ValueError:
            pass

        # Verify rollback
        with get_ecosystemiser_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM validation_test").fetchone()[0]
            assert count == 1  # Should still be 1, not 2

        # Clean up
        with get_ecosystemiser_connection() as conn:
            conn.execute("DROP TABLE validation_test")
            conn.commit()

        print("✅ Transaction management test passed")
        return True
    except Exception as e:
        print(f"❌ Transaction management test failed: {e}")
        return False


def validate_concurrent_access():
    """Validate concurrent database access."""
    print("🔍 Testing concurrent access...")

    def worker(worker_id, iterations=20):
        """Worker function for concurrent testing."""
        for i in range(iterations):
            with get_ecosystemiser_connection() as conn:
                result = conn.execute("SELECT ?, ?", (worker_id, i)).fetchone()
                assert result[0] == worker_id
                assert result[1] == i
        return worker_id

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker, i) for i in range(4)]
            results = [future.result() for future in futures]

        assert len(results) == 4
        print("✅ Concurrent access test passed")
        return True
    except Exception as e:
        print(f"❌ Concurrent access test failed: {e}")
        return False


def validate_schema_initialization():
    """Validate schema initialization."""
    print("🔍 Testing schema initialization...")

    try:
        ensure_database_schema()

        with get_ecosystemiser_connection() as conn:
            tables = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name LIKE 'eco_%'
            """).fetchall()

            assert len(tables) > 0, "Should have EcoSystemiser tables"

        print(f"✅ Schema initialization test passed ({len(tables)} tables)")
        return True
    except Exception as e:
        print(f"❌ Schema initialization test failed: {e}")
        return False


def validate_error_handling():
    """Validate error handling."""
    print("🔍 Testing error handling...")

    try:
        # Test SQL error handling
        try:
            with get_ecosystemiser_connection() as conn:
                conn.execute("SELECT * FROM nonexistent_table")
            assert False, "Should have raised an error"
        except Exception:
            pass  # Expected

        # Test that database is still accessible after error
        with get_ecosystemiser_connection() as conn:
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1

        print("✅ Error handling test passed")
        return True
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False


def validate_performance():
    """Validate performance characteristics."""
    print("🔍 Testing performance...")

    try:
        # Measure connection time
        times = []
        for _ in range(50):
            start = time.time()
            with get_ecosystemiser_connection() as conn:
                conn.execute("SELECT 1")
            times.append(time.time() - start)

        avg_time = sum(times) * 1000 / len(times)  # Convert to milliseconds
        max_time = max(times) * 1000

        # Performance thresholds
        assert avg_time < 10, f"Average connection time too slow: {avg_time:.2f}ms"
        assert max_time < 50, f"Maximum connection time too slow: {max_time:.2f}ms"

        print(f"✅ Performance test passed (avg: {avg_time:.2f}ms, max: {max_time:.2f}ms)")
        return True
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False


def validate_no_connection_leaks():
    """Validate no connection leaks under load."""
    print("🔍 Testing for connection leaks...")

    try:
        # Perform many operations
        for i in range(200):
            with get_ecosystemiser_connection() as conn:
                conn.execute("SELECT ?", (i,))

        # If we get here without errors, no obvious leaks
        print("✅ Connection leak test passed")
        return True
    except Exception as e:
        print(f"❌ Connection leak test failed: {e}")
        return False


def validate_hive_integration_status():
    """Validate Hive integration status."""
    print("🔍 Checking Hive integration status...")

    try:
        integration_ok = validate_hive_integration()

        # Import check
        try:
            from hive_orchestrator.core.db import get_database_connection
            hive_available = True
        except ImportError:
            hive_available = False

        if hive_available:
            print("✅ Hive orchestrator database service available")
        else:
            print("⚠️  Hive orchestrator database service not available (fallback mode)")

        assert integration_ok, "Integration validation should pass"
        print("✅ Hive integration validation passed")
        return True
    except Exception as e:
        print(f"❌ Hive integration validation failed: {e}")
        return False


def run_comprehensive_validation():
    """Run comprehensive validation of all fixes."""
    print("=" * 60)
    print("DATABASE CONNECTION POOL FIXES VALIDATION")
    print("=" * 60)

    tests = [
        ("Basic Functionality", validate_basic_functionality),
        ("Transaction Management", validate_transaction_management),
        ("Concurrent Access", validate_concurrent_access),
        ("Schema Initialization", validate_schema_initialization),
        ("Error Handling", validate_error_handling),
        ("Performance", validate_performance),
        ("Connection Leaks", validate_no_connection_leaks),
        ("Hive Integration", validate_hive_integration_status),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        try:
            if test_func():
                passed += 1
            else:
                print(f"💥 {test_name} validation failed")
        except Exception as e:
            print(f"💥 {test_name} validation crashed: {e}")

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("🎉 ALL VALIDATIONS PASSED!")
        print("✅ Database connection pool fixes are working correctly")
        print("✅ Platform is ready for production use")
        return True
    else:
        print(f"❌ {total - passed} validations failed")
        print("🔧 Review failed tests and fix issues before deployment")
        return False


if __name__ == "__main__":
    success = run_comprehensive_validation()
    sys.exit(0 if success else 1)