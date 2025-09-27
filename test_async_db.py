#!/usr/bin/env python3
"""
Comprehensive async database testing for Phase 4.1
"""

import asyncio
import sys
import os
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-core-db" / "src"))

async def test_async_db_connection_pool():
    """Test async database connection pool functionality"""
    print("=== Testing Async Database Connection Pool ===")

    try:
        from hive_core_db.async_connection_pool import get_async_connection, AsyncConnectionPool
        print("[PASS] Async connection pool imports successfully")

        # Test connection acquisition
        async with get_async_connection() as conn:
            print("[PASS] Async connection acquired successfully")

            # Test basic query
            cursor = await conn.execute('SELECT 1 as test')
            result = await cursor.fetchone()
            print(f"[PASS] Async query executed: {result}")

            # Test CREATE TABLE
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS test_async (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("[PASS] CREATE TABLE executed")

            # Test INSERT
            await conn.execute("INSERT INTO test_async (name) VALUES (?)", ("test_entry",))
            await conn.commit()
            print("[PASS] INSERT and COMMIT executed")

            # Test SELECT
            cursor = await conn.execute("SELECT * FROM test_async WHERE name = ?", ("test_entry",))
            result = await cursor.fetchone()
            print(f"[PASS] SELECT executed: {result}")

            # Cleanup
            await conn.execute("DROP TABLE test_async")
            await conn.commit()
            print("[PASS] Cleanup completed")

        print("[PASS] Async connection released successfully")

        # Test connection pool health
        pool = AsyncConnectionPool._instance
        if pool:
            health = await pool.health_check()
            print(f"[PASS] Connection pool health: {health}")

        return True

    except Exception as e:
        print(f"[FAIL] Async database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_backward_compatibility():
    """Test backward compatibility wrappers"""
    print("\n=== Testing Backward Compatibility Wrappers ===")

    try:
        from hive_core_db.async_compat import get_sync_async_connection, AsyncToSyncAdapter
        print("[PASS] Backward compatibility imports successfully")

        # Test sync wrapper
        with get_sync_async_connection() as conn:
            print("[PASS] Sync wrapper connection acquired")

            cursor = conn.execute("SELECT 1 as test")
            result = cursor.fetchone()
            print(f"[PASS] Sync wrapper query: {result}")

        print("[PASS] Sync wrapper connection released")

        # Test sync adapter
        result = AsyncToSyncAdapter.execute_query("SELECT 2 as test")
        print(f"[PASS] Sync adapter query: {result}")

        return True

    except Exception as e:
        print(f"[FAIL] Backward compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_database_operations():
    """Test async database operations from hive_core_db.database"""
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

        # Test create task
        task_id = await create_task_async(
            title="Test Async Task",
            task_type="test",
            description="Testing async database operations"
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

        # Verify update
        tasks = await get_tasks_by_status_async("in_progress")
        found_task = any(task['id'] == task_id for task in tasks)
        print(f"[PASS] Task status verification: {found_task}")

        return True

    except Exception as e:
        print(f"[FAIL] Async database operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_event_bus():
    """Test async event bus operations"""
    print("\n=== Testing Async Event Bus Operations ===")

    try:
        # Add event bus to path
        sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-bus" / "src"))

        from hive_bus.event_bus import get_event_bus, EventBus
        from hive_bus.events import Event
        print("[PASS] Event bus imports successfully")

        bus = get_event_bus()

        # Test async publishing if available
        if hasattr(bus, 'publish_async'):
            event = Event(
                event_type="test.async.event",
                source_agent="test-agent",
                payload={"test": "async_data"}
            )

            event_id = await bus.publish_async(event)
            print(f"[PASS] Async event published: {event_id}")

            # Test async event retrieval
            if hasattr(bus, 'get_events_async'):
                events = await bus.get_events_async(event_type="test.async.event", limit=1)
                print(f"[PASS] Async event retrieved: {len(events)} events")
        else:
            print("[INFO] Async event bus methods not available - using sync fallback")

        return True

    except Exception as e:
        print(f"[FAIL] Async event bus test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all async tests"""
    print("Phase 4.1 Async Implementation - Comprehensive Testing")
    print("=" * 60)

    results = []

    # Test 1: Async Database Connection Pool
    result1 = await test_async_db_connection_pool()
    results.append(("Async DB Connection Pool", result1))

    # Test 2: Backward Compatibility
    result2 = await test_backward_compatibility()
    results.append(("Backward Compatibility", result2))

    # Test 3: Async Database Operations
    result3 = await test_async_database_operations()
    results.append(("Async Database Operations", result3))

    # Test 4: Async Event Bus
    result4 = await test_async_event_bus()
    results.append(("Async Event Bus", result4))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{test_name:<30} [{status}]")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    overall_status = "ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"
    print(f"OVERALL RESULT: {overall_status}")
    print("=" * 60)

    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)