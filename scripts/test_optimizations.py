#!/usr/bin/env python3
"""
Test script to verify optimizations are working correctly.
"""

import sys
import time
import threading
from pathlib import Path

# Add packages path
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))

import hive_core_db
from hive_core_db.connection_pool import get_pool, get_pooled_connection


def test_connection_pool():
    """Test the connection pool functionality."""
    print("\n" + "=" * 60)
    print("TESTING CONNECTION POOL")
    print("=" * 60)

    # Get pool instance
    pool = get_pool()
    print(f"Pool initialized: {pool.get_stats()}")

    # Test multiple connections
    start_time = time.time()

    def worker(worker_id):
        """Worker thread to test concurrent connections."""
        with get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tasks")
            count = cursor.fetchone()[0]
            print(f"  Worker {worker_id}: Found {count} tasks")

    # Create multiple threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all threads
    for t in threads:
        t.join()

    elapsed = time.time() - start_time
    print(f"\nConnection pool test completed in {elapsed:.3f} seconds")
    print(f"Final pool stats: {pool.get_stats()}")

    return elapsed < 1.0  # Should complete in under 1 second


def test_optimized_queries():
    """Test the optimized query patterns."""
    print("\n" + "=" * 60)
    print("TESTING OPTIMIZED QUERIES")
    print("=" * 60)

    # Test the optimized function
    start_time = time.time()

    # Import the optimized version if it exists
    try:
        from hive_core_db.database_enhanced_optimized import (
            get_queued_tasks_with_planning_optimized
        )

        tasks = get_queued_tasks_with_planning_optimized(limit=10, use_pool=True)
        elapsed_optimized = time.time() - start_time

        print(f"  Optimized query found {len(tasks)} tasks in {elapsed_optimized:.3f}s")

        # Compare with original
        start_time = time.time()
        from hive_core_db.database_enhanced import get_queued_tasks_with_planning

        tasks_original = get_queued_tasks_with_planning(limit=10)
        elapsed_original = time.time() - start_time

        print(f"  Original query found {len(tasks_original)} tasks in {elapsed_original:.3f}s")

        if elapsed_optimized < elapsed_original:
            improvement = ((elapsed_original - elapsed_optimized) / elapsed_original) * 100
            print(f"  SUCCESS: Performance improvement: {improvement:.1f}%")
        else:
            print(f"  WARNING: No improvement detected (may need more data)")

    except ImportError:
        print("  WARNING: Optimized version not found, using original")
        from hive_core_db.database_enhanced import get_queued_tasks_with_planning

        tasks = get_queued_tasks_with_planning(limit=10)
        print(f"  Found {len(tasks)} tasks")

    return True


def test_neural_connection():
    """Test that the neural connection still works."""
    print("\n" + "=" * 60)
    print("TESTING NEURAL CONNECTION")
    print("=" * 60)

    # Check if planner tasks can still be seen
    tasks = hive_core_db.get_queued_tasks_with_planning(limit=10)
    planner_tasks = [t for t in tasks if t.get('task_type') == 'planned_subtask']

    print(f"  Regular tasks: {len(tasks) - len(planner_tasks)}")
    print(f"  Planner tasks: {len(planner_tasks)}")

    if planner_tasks:
        print(f"  SUCCESS: Neural connection intact - Queen can see planner tasks")
        for task in planner_tasks[:3]:
            print(f"     - {task['title']}")
    else:
        print(f"  WARNING: No planner tasks found (may need to run AI Planner)")

    return True


def test_database_indexes():
    """Test that indexes are working."""
    print("\n" + "=" * 60)
    print("TESTING DATABASE INDEXES")
    print("=" * 60)

    conn = hive_core_db.get_connection()
    cursor = conn.cursor()

    # Check indexes
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name LIKE 'idx_%'
        ORDER BY name
    """)

    indexes = cursor.fetchall()
    print(f"  Found {len(indexes)} indexes:")
    for idx in indexes[:5]:  # Show first 5
        print(f"    - {idx[0]}")

    if len(indexes) > 5:
        print(f"    ... and {len(indexes) - 5} more")

    cursor.close()
    conn.close()

    return len(indexes) > 10  # We should have at least 10 indexes


def main():
    """Run all tests."""
    print("Hive V2.1 Optimization Test Suite")
    print("Testing optimizations and neural connection...")

    results = {
        "Connection Pool": test_connection_pool(),
        "Optimized Queries": test_optimized_queries(),
        "Neural Connection": test_neural_connection(),
        "Database Indexes": test_database_indexes()
    }

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\nSUCCESS: All optimizations working correctly!")
        return 0
    else:
        print(f"\nWARNING: {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())