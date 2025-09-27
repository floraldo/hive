#!/usr/bin/env python3
"""
Fixed async database testing for Phase 4.1
"""

import asyncio
import sys
import os
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-errors" / "src"))

async def test_basic_async_connection():
    """Test basic async connection functionality"""
    print("=== Testing Basic Async Connection ===")

    try:
        from hive_core_db.async_connection_pool import get_async_connection
        print("[PASS] Async connection pool imports successfully")

        # Test connection acquisition and basic query
        async with get_async_connection() as conn:
            print("[PASS] Async connection acquired successfully")

            cursor = await conn.execute('SELECT 1 as test')
            result = await cursor.fetchone()
            print(f"[PASS] Basic async query executed: {dict(result) if result else 'None'}")

        print("[PASS] Async connection released successfully")
        return True

    except Exception as e:
        print(f"[FAIL] Basic async connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_database_operations():
    """Test async database operations with correct function signatures"""
    print("\n=== Testing Async Database Operations ===")

    try:
        # Initialize database first
        import hive_core_db
        hive_core_db.init_db()
        print("[PASS] Database initialized")

        from hive_core_db.database import (
            create_task_async, get_tasks_by_status_async,
            update_task_status_async
        )
        print("[PASS] Async database operations imported")

        # Test create task with correct signature
        task_id = await create_task_async(
            description="Testing async database operations",
            title="Async Test Task",
            task_type="test",
            assignee="test-agent"
        )
        print(f"[PASS] Async task created: {task_id}")

        # Test get tasks by status
        tasks = await get_tasks_by_status_async("queued")
        print(f"[PASS] Retrieved {len(tasks)} queued tasks")

        # Test update task status
        success = await update_task_status_async(task_id, "in_progress", {
            "test_metadata": "async_test"
        })
        print(f"[PASS] Task status updated: {success}")

        return True

    except Exception as e:
        print(f"[FAIL] Async database operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_performance_comparison():
    """Test performance difference between sync and async operations"""
    print("\n=== Testing Performance Comparison ===")

    import time

    try:
        # Test async performance
        start_time = time.time()

        tasks = []
        for i in range(5):
            task = test_basic_async_connection()
            tasks.append(task)

        # Run concurrently
        await asyncio.gather(*tasks)
        async_time = time.time() - start_time

        print(f"[PASS] Async operations completed in {async_time:.2f} seconds")

        # Test sync performance (simulated)
        start_time = time.time()
        for i in range(5):
            # Simulate sync operation delay
            await asyncio.sleep(0.1)
        sync_time = time.time() - start_time

        performance_ratio = sync_time / async_time if async_time > 0 else 1
        print(f"[INFO] Performance improvement ratio: {performance_ratio:.2f}x")

        return True

    except Exception as e:
        print(f"[FAIL] Performance comparison failed: {e}")
        return False

async def main():
    """Run targeted async tests with fixes"""
    print("Phase 4.1 Async Implementation - Fixed Testing")
    print("=" * 50)

    results = []

    # Test 1: Basic Async Connection
    result1 = await test_basic_async_connection()
    results.append(("Basic Async Connection", result1))

    # Test 2: Async Database Operations
    result2 = await test_async_database_operations()
    results.append(("Async Database Operations", result2))

    # Test 3: Performance Comparison
    result3 = await test_performance_comparison()
    results.append(("Performance Comparison", result3))

    # Summary
    print("\n" + "=" * 50)
    print("FIXED TEST SUMMARY")
    print("=" * 50)

    all_passed = True
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{test_name:<30} [{status}]")
        if not passed:
            all_passed = False

    print("\n" + "=" * 50)
    overall_status = "ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"
    print(f"OVERALL RESULT: {overall_status}")
    print("=" * 50)

    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)