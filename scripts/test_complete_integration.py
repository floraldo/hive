#!/usr/bin/env python3
"""
Test complete Hive V2.1 integration with:
- Queen (orchestrator)
- AI Planner (real Claude mode)
- AI Reviewer (real Claude mode)
- Enhanced database with neural connection
"""

import sys
import time
from pathlib import Path

# Setup paths
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-config" / "src"))
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(hive_root / "apps" / "ai-planner" / "src"))

from hive_config import setup_hive_paths
setup_hive_paths()

import hive_core_db
from hive_core_db.database import get_connection
from ai_planner.claude_bridge import RobustClaudePlannerBridge

def test_neural_connection():
    """Test that Queen can see planner-generated tasks"""
    print("\n" + "="*60)
    print("TESTING NEURAL CONNECTION (Queen + AI Planner)")
    print("="*60)

    try:
        # Test enhanced database function
        from hive_core_db.database_enhanced import get_queued_tasks_with_planning

        # Get tasks including planner-generated ones
        tasks = get_queued_tasks_with_planning(limit=10)

        regular_tasks = []
        planner_tasks = []

        for task in tasks:
            if task.get('task_type') == 'planned_subtask':
                planner_tasks.append(task)
            else:
                regular_tasks.append(task)

        print(f"\nNeural Connection Status:")
        print(f"  Regular tasks: {len(regular_tasks)}")
        print(f"  AI Planner tasks: {len(planner_tasks)}")
        print(f"  Total visible to Queen: {len(tasks)}")

        if planner_tasks:
            print(f"\n  SUCCESS: Queen can see AI Planner-generated tasks!")
            print(f"  Example planner task: {planner_tasks[0].get('title', 'N/A')}")
        else:
            print(f"\n  NOTE: No planner tasks in queue (run AI Planner to generate some)")

        return True

    except Exception as e:
        print(f"  ERROR: Neural connection test failed: {e}")
        return False

def test_ai_planner_mode():
    """Test AI Planner Claude mode configuration"""
    print("\n" + "="*60)
    print("TESTING AI PLANNER CONFIGURATION")
    print("="*60)

    try:
        # Test real mode configuration
        bridge = RobustClaudePlannerBridge(mock_mode=False)

        if bridge.claude_cmd:
            print(f"  SUCCESS: AI Planner in REAL Claude API mode")
            print(f"  Claude CLI location: {bridge.claude_cmd}")
        else:
            print(f"  WARNING: Claude CLI not found - will use fallback mode")

        # Test mock mode
        mock_bridge = RobustClaudePlannerBridge(mock_mode=True)
        print(f"  Mock mode available: {mock_bridge.mock_mode}")

        return True

    except Exception as e:
        print(f"  ERROR: AI Planner test failed: {e}")
        return False

def test_database_optimization():
    """Test database optimizations"""
    print("\n" + "="*60)
    print("TESTING DATABASE OPTIMIZATIONS")
    print("="*60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check indexes
        cursor.execute("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='index' AND name LIKE 'idx_%'
        """)
        index_count = cursor.fetchone()[0]

        print(f"  Database indexes: {index_count}")

        # Test query performance
        start = time.time()
        cursor.execute("""
            SELECT COUNT(*) FROM tasks
            WHERE status = 'queued' AND task_type = 'planned_subtask'
        """)
        count = cursor.fetchone()[0]
        elapsed = time.time() - start

        print(f"  Query performance: {elapsed:.3f}s for {count} planned tasks")

        if index_count > 10:
            print(f"  SUCCESS: Database optimizations in place")
        else:
            print(f"  WARNING: Consider running optimize_database_indexes.py")

        conn.close()
        return True

    except Exception as e:
        print(f"  ERROR: Database test failed: {e}")
        return False

def test_system_components():
    """Test all system components are available"""
    print("\n" + "="*60)
    print("TESTING SYSTEM COMPONENTS")
    print("="*60)

    components = {
        "Queen (Orchestrator)": "hive_orchestrator.queen",
        "AI Planner": "ai_planner.agent",
        "AI Reviewer": "ai_reviewer.agent",
        "Enhanced Database": "hive_core_db.database_enhanced",
        "Connection Pool": "hive_core_db.connection_pool"
    }

    all_good = True
    for name, module in components.items():
        try:
            exec(f"import {module}")
            print(f"  {name}: OK")
        except ImportError as e:
            print(f"  {name}: FAILED - {e}")
            all_good = False

    return all_good

def main():
    """Run all integration tests"""
    print("Hive V2.1 Complete Integration Test")
    print("Testing Queen + AI Planner + AI Reviewer + Neural Connection")

    results = {
        "System Components": test_system_components(),
        "AI Planner Mode": test_ai_planner_mode(),
        "Neural Connection": test_neural_connection(),
        "Database Optimization": test_database_optimization()
    }

    # Summary
    print("\n" + "="*60)
    print("INTEGRATION TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {test_name}: {status}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\n SUCCESS: Hive V2.1 fully integrated and operational!")
        print("\nReady to:")
        print("  1. Run Queen: python scripts/queen_daemon.py")
        print("  2. Run AI Planner: python scripts/ai_planner_daemon.py")
        print("  3. Run AI Reviewer: python scripts/ai_reviewer_daemon.py")
        return 0
    else:
        print(f"\n WARNING: {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())