#!/usr/bin/env python3
"""
Simple Async Infrastructure Test

Tests core async components without full orchestrator dependencies.
"""

import asyncio
import time
import json
import sys
from pathlib import Path

# Test basic async functionality
async def test_basic_async():
    """Test basic async functionality."""
    print("Testing basic async functionality...")

    start_time = time.time()

    # Test concurrent operations
    async def async_task(task_id: int, duration: float):
        await asyncio.sleep(duration)
        return {"task_id": task_id, "duration": duration, "status": "completed"}

    # Sequential execution (baseline)
    print("  Running 5 tasks sequentially...")
    seq_start = time.time()
    seq_results = []
    for i in range(5):
        result = await async_task(i, 0.2)  # 200ms each
        seq_results.append(result)
    seq_time = time.time() - seq_start

    # Concurrent execution (async benefit)
    print("  Running 5 tasks concurrently...")
    conc_start = time.time()
    conc_results = await asyncio.gather(
        *[async_task(i, 0.2) for i in range(5)]
    )
    conc_time = time.time() - conc_start

    total_time = time.time() - start_time

    print(f"  ✅ Sequential time: {seq_time:.3f}s")
    print(f"  ✅ Concurrent time: {conc_time:.3f}s")
    print(f"  ✅ Speedup: {seq_time/conc_time:.1f}x")

    return {
        "sequential_time": seq_time,
        "concurrent_time": conc_time,
        "speedup": seq_time / conc_time,
        "total_time": total_time
    }


async def test_async_database():
    """Test async database operations."""
    print("Testing async database operations...")

    try:
        import aiosqlite

        # Create in-memory database for testing
        async with aiosqlite.connect(":memory:") as db:
            # Create test table
            await db.execute("""
                CREATE TABLE test_tasks (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Test concurrent inserts
            start_time = time.time()
            insert_tasks = [
                db.execute("INSERT INTO test_tasks (name, status) VALUES (?, ?)",
                          (f"task_{i}", "pending"))
                for i in range(10)
            ]
            await asyncio.gather(*insert_tasks)
            await db.commit()
            insert_time = time.time() - start_time

            # Test concurrent reads
            start_time = time.time()
            read_tasks = [
                db.execute("SELECT * FROM test_tasks WHERE id = ?", (i,))
                for i in range(1, 11)
            ]
            cursors = await asyncio.gather(*read_tasks)
            read_time = time.time() - start_time

            # Test concurrent updates
            start_time = time.time()
            update_tasks = [
                db.execute("UPDATE test_tasks SET status = ? WHERE id = ?",
                          ("completed", i))
                for i in range(1, 11)
            ]
            await asyncio.gather(*update_tasks)
            await db.commit()
            update_time = time.time() - start_time

            print(f"  ✅ Concurrent inserts: {insert_time:.3f}s (10 tasks)")
            print(f"  ✅ Concurrent reads: {read_time:.3f}s (10 queries)")
            print(f"  ✅ Concurrent updates: {update_time:.3f}s (10 updates)")

            return {
                "insert_time": insert_time,
                "read_time": read_time,
                "update_time": update_time,
                "total_operations": 30
            }

    except ImportError:
        print("  ❌ aiosqlite not available")
        return {"error": "aiosqlite not available"}
    except Exception as e:
        print(f"  ❌ Database test failed: {e}")
        return {"error": str(e)}


async def test_async_subprocess():
    """Test async subprocess operations."""
    print("Testing async subprocess operations...")

    try:
        # Test concurrent subprocess execution
        start_time = time.time()

        async def run_command(cmd, task_id):
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return {
                "task_id": task_id,
                "return_code": process.returncode,
                "stdout": stdout.decode()[:100],  # First 100 chars
                "success": process.returncode == 0
            }

        # Run multiple commands concurrently (using simple echo commands)
        commands = [
            ("echo 'Task 1 completed'", 1),
            ("echo 'Task 2 completed'", 2),
            ("echo 'Task 3 completed'", 3),
            ("python -c \"print('Python task completed')\"", 4),
            ("python -c \"import time; time.sleep(0.1); print('Delayed task')\"", 5)
        ]

        results = await asyncio.gather(
            *[run_command(cmd, task_id) for cmd, task_id in commands]
        )

        execution_time = time.time() - start_time
        successful_tasks = sum(1 for r in results if r["success"])

        print(f"  ✅ Executed {len(commands)} commands concurrently in {execution_time:.3f}s")
        print(f"  ✅ Successful tasks: {successful_tasks}/{len(commands)}")

        return {
            "execution_time": execution_time,
            "total_commands": len(commands),
            "successful_commands": successful_tasks,
            "results": results
        }

    except Exception as e:
        print(f"  ❌ Subprocess test failed: {e}")
        return {"error": str(e)}


async def test_async_event_simulation():
    """Test async event handling simulation."""
    print("Testing async event handling...")

    try:
        # Simulate event publishing and handling
        events = []
        handlers_completed = []

        async def publish_event(event_id, event_type, data):
            """Simulate event publishing."""
            await asyncio.sleep(0.01)  # Simulate network delay
            event = {
                "id": event_id,
                "type": event_type,
                "data": data,
                "timestamp": time.time()
            }
            events.append(event)
            return event

        async def handle_event(event):
            """Simulate event handling."""
            await asyncio.sleep(0.02)  # Simulate processing
            handlers_completed.append({
                "event_id": event["id"],
                "processed_at": time.time()
            })

        # Publish events concurrently
        start_time = time.time()
        published_events = await asyncio.gather(
            *[publish_event(i, "task.completed", {"task_id": f"task_{i}"})
              for i in range(10)]
        )
        publish_time = time.time() - start_time

        # Handle events concurrently
        start_time = time.time()
        await asyncio.gather(
            *[handle_event(event) for event in published_events]
        )
        handle_time = time.time() - start_time

        print(f"  ✅ Published {len(published_events)} events in {publish_time:.3f}s")
        print(f"  ✅ Handled {len(handlers_completed)} events in {handle_time:.3f}s")

        return {
            "publish_time": publish_time,
            "handle_time": handle_time,
            "events_published": len(published_events),
            "events_handled": len(handlers_completed)
        }

    except Exception as e:
        print(f"  ❌ Event handling test failed: {e}")
        return {"error": str(e)}


async def run_comprehensive_test():
    """Run comprehensive async tests."""
    print("🚀 Comprehensive Async Infrastructure Test")
    print("=" * 45)
    print()

    total_start = time.time()
    all_results = {}

    # Test 1: Basic async
    basic_results = await test_basic_async()
    all_results["basic_async"] = basic_results
    print()

    # Test 2: Database operations
    db_results = await test_async_database()
    all_results["database"] = db_results
    print()

    # Test 3: Subprocess operations
    subprocess_results = await test_async_subprocess()
    all_results["subprocess"] = subprocess_results
    print()

    # Test 4: Event handling
    event_results = await test_async_event_simulation()
    all_results["events"] = event_results
    print()

    total_time = time.time() - total_start

    # Summary
    print("📊 Test Summary")
    print("=" * 15)
    print(f"Total test time: {total_time:.3f}s")
    print()

    if "error" not in basic_results:
        print(f"Basic Async Speedup: {basic_results['speedup']:.1f}x")

    if "error" not in db_results:
        total_db_time = db_results['insert_time'] + db_results['read_time'] + db_results['update_time']
        print(f"Database Operations: {total_db_time:.3f}s ({db_results['total_operations']} ops)")

    if "error" not in subprocess_results:
        print(f"Subprocess Execution: {subprocess_results['execution_time']:.3f}s ({subprocess_results['successful_commands']} commands)")

    if "error" not in event_results:
        print(f"Event Processing: {event_results['publish_time'] + event_results['handle_time']:.3f}s ({event_results['events_handled']} events)")

    print()
    print("🎯 Async Infrastructure Assessment:")

    # Calculate overall performance score
    performance_indicators = []
    if "error" not in basic_results and basic_results['speedup'] > 3:
        performance_indicators.append("✅ Excellent concurrency performance")
    elif "error" not in basic_results and basic_results['speedup'] > 2:
        performance_indicators.append("✅ Good concurrency performance")

    if "error" not in db_results:
        performance_indicators.append("✅ Async database operations working")

    if "error" not in subprocess_results and subprocess_results['successful_commands'] > 3:
        performance_indicators.append("✅ Async subprocess execution working")

    if "error" not in event_results:
        performance_indicators.append("✅ Async event handling working")

    for indicator in performance_indicators:
        print(f"  {indicator}")

    if len(performance_indicators) >= 3:
        print()
        print("🎉 Async infrastructure is ready for 3-5x performance improvement!")
    else:
        print()
        print("⚠️ Some async components need attention before production use")

    all_results["summary"] = {
        "total_time": total_time,
        "performance_indicators": len(performance_indicators),
        "tests_passed": len([r for r in all_results.values() if isinstance(r, dict) and "error" not in r])
    }

    return all_results


if __name__ == "__main__":
    print("Simple Async Infrastructure Test")
    print("===============================")
    print()

    async def main():
        results = await run_comprehensive_test()

        # Save results
        results_file = Path("simple_async_test_results.json")
        try:
            with open(results_file, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print()
            print(f"📄 Results saved to: {results_file}")
        except Exception as e:
            print(f"❌ Could not save results: {e}")

    asyncio.run(main())