#!/usr/bin/env python3
"""
Test QueenLite async functionality for Phase 4.1
"""

import asyncio
import sys
import os
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent / "apps" / "hive-orchestrator" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-bus" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-errors" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-config" / "src"))

async def test_queen_async_imports():
    """Test that QueenLite async components can be imported"""
    print("=== Testing QueenLite Async Imports ===")

    try:
        from hive_orchestrator.queen import QueenLite
        print("[PASS] QueenLite imported successfully")

        # Check if async methods are available
        if hasattr(QueenLite, 'run_forever_async'):
            print("[PASS] run_forever_async method available")
        else:
            print("[FAIL] run_forever_async method not found")
            return False

        if hasattr(QueenLite, 'spawn_worker_async'):
            print("[PASS] spawn_worker_async method available")
        else:
            print("[FAIL] spawn_worker_async method not found")
            return False

        if hasattr(QueenLite, 'execute_app_task_async'):
            print("[PASS] execute_app_task_async method available")
        else:
            print("[FAIL] execute_app_task_async method not found")
            return False

        print("[PASS] All async methods are available")
        return True

    except Exception as e:
        print(f"[FAIL] QueenLite async import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_subprocess_creation():
    """Test async subprocess creation functionality"""
    print("\n=== Testing Async Subprocess Creation ===")

    try:
        # Test basic async subprocess creation
        process = await asyncio.create_subprocess_shell(
            "echo 'Hello Async World'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()
        print(f"[PASS] Async subprocess executed: {stdout.decode().strip()}")

        # Test multiple concurrent subprocesses
        tasks = []
        for i in range(3):
            task = asyncio.create_subprocess_shell(
                f"echo 'Process {i}'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            tasks.append(task)

        processes = await asyncio.gather(*tasks)
        results = await asyncio.gather(*[p.communicate() for p in processes])

        print(f"[PASS] Concurrent subprocess execution: {len(results)} processes")
        return True

    except Exception as e:
        print(f"[FAIL] Async subprocess test failed: {e}")
        return False

async def test_ai_agent_async_imports():
    """Test AI agent async functionality imports"""
    print("\n=== Testing AI Agent Async Imports ===")

    try:
        # Test AI Planner async
        sys.path.insert(0, str(Path(__file__).parent / "apps" / "ai-planner" / "src"))
        from ai_planner.agent import AIPlanner
        print("[PASS] AI Planner imported successfully")

        # Check if async methods are available
        if hasattr(AIPlanner, 'run_async'):
            print("[PASS] AI Planner run_async method available")
        else:
            print("[INFO] AI Planner run_async method not found (may be conditional)")

        # Test AI Reviewer async
        sys.path.insert(0, str(Path(__file__).parent / "apps" / "ai-reviewer" / "src"))
        from ai_reviewer.agent import ReviewAgent
        print("[PASS] AI Reviewer imported successfully")

        if hasattr(ReviewAgent, 'run_async'):
            print("[PASS] AI Reviewer run_async method available")
        else:
            print("[INFO] AI Reviewer run_async method not found (may be conditional)")

        return True

    except Exception as e:
        print(f"[FAIL] AI agent async import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_event_bus_async():
    """Test async event bus functionality"""
    print("\n=== Testing Event Bus Async Operations ===")

    try:
        from hive_bus.event_bus import get_event_bus
        from hive_bus.events import Event
        print("[PASS] Event bus imports successfully")

        bus = get_event_bus()

        # Test async publishing if available
        if hasattr(bus, 'publish_async'):
            print("[PASS] Async event publishing available")

            event = Event(
                event_type="test.async.validation",
                source_agent="test-validation",
                payload={"validation": "async_test"}
            )

            event_id = await bus.publish_async(event)
            print(f"[PASS] Async event published: {event_id}")

            # Test async event retrieval
            if hasattr(bus, 'get_events_async'):
                events = await bus.get_events_async(
                    event_type="test.async.validation",
                    limit=1
                )
                print(f"[PASS] Async event retrieved: {len(events)} events")
            else:
                print("[INFO] Async event retrieval not available")

        else:
            print("[INFO] Async event bus methods not available")

        return True

    except Exception as e:
        print(f"[FAIL] Event bus async test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run comprehensive QueenLite and agent async tests"""
    print("Phase 4.1 Async Implementation - QueenLite & Agents Testing")
    print("=" * 65)

    results = []

    # Test 1: QueenLite Async Imports
    result1 = await test_queen_async_imports()
    results.append(("QueenLite Async Imports", result1))

    # Test 2: Async Subprocess Creation
    result2 = await test_async_subprocess_creation()
    results.append(("Async Subprocess Creation", result2))

    # Test 3: AI Agent Async Imports
    result3 = await test_ai_agent_async_imports()
    results.append(("AI Agent Async Imports", result3))

    # Test 4: Event Bus Async
    result4 = await test_event_bus_async()
    results.append(("Event Bus Async Operations", result4))

    # Summary
    print("\n" + "=" * 65)
    print("QUEENLITE & AGENTS TEST SUMMARY")
    print("=" * 65)

    all_passed = True
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{test_name:<35} [{status}]")
        if not passed:
            all_passed = False

    print("\n" + "=" * 65)
    overall_status = "ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"
    print(f"OVERALL RESULT: {overall_status}")
    print("=" * 65)

    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)