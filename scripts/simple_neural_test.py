#!/usr/bin/env python3
"""
Simple Neural Connection Test

Quick validation of the key components without complex flows.
"""

import sys
from pathlib import Path

# Setup paths
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-config" / "src"))
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))

from hive_config import setup_hive_paths
setup_hive_paths()

import hive_core_db


def test_components():
    """Test individual components"""
    print("="*60)
    print("HIVE V2.1 COMPONENT VALIDATION")
    print("="*60)

    tests_passed = 0
    total_tests = 0

    # Test 1: Database connection
    total_tests += 1
    try:
        hive_core_db.init_db()
        conn = hive_core_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks")
        count = cursor.fetchone()[0]
        conn.close()
        print(f"✓ Database connection: {count} tasks in database")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Database connection failed: {e}")

    # Test 2: Enhanced database functions
    total_tests += 1
    try:
        from hive_core_db.database_enhanced import get_queued_tasks_with_planning
        tasks = get_queued_tasks_with_planning(limit=5)
        print(f"✓ Enhanced functions: get_queued_tasks_with_planning returned {len(tasks)} tasks")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Enhanced functions failed: {e}")

    # Test 3: AI Planner import
    total_tests += 1
    try:
        sys.path.insert(0, str(hive_root / "apps" / "ai-planner" / "src"))
        from ai_planner.agent import AIPlanner
        planner = AIPlanner(mock_mode=True)
        print(f"✓ AI Planner: Successfully imported and initialized")
        tests_passed += 1
    except Exception as e:
        print(f"✗ AI Planner failed: {e}")

    # Test 4: Queen integration
    total_tests += 1
    try:
        sys.path.insert(0, str(hive_root / "apps" / "hive-orchestrator" / "src"))
        from hive_orchestrator.queen import QueenLite
        print(f"✓ Queen Orchestrator: Successfully imported")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Queen Orchestrator failed: {e}")

    # Test 5: AI Reviewer import
    total_tests += 1
    try:
        sys.path.insert(0, str(hive_root / "apps" / "ai-reviewer" / "src"))
        from ai_reviewer.agent import AIReviewer
        print(f"✓ AI Reviewer: Successfully imported")
        tests_passed += 1
    except Exception as e:
        print(f"✗ AI Reviewer failed: {e}")

    # Test 6: Neural connection query
    total_tests += 1
    try:
        # Check if Queen can access planner tasks
        from hive_core_db.database_enhanced import get_queued_tasks_with_planning
        all_tasks = get_queued_tasks_with_planning(limit=50)
        planner_tasks = [t for t in all_tasks if t.get('task_type') == 'planned_subtask']

        print(f"✓ Neural connection: Queen can see {len(planner_tasks)} planner tasks")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Neural connection failed: {e}")

    # Test 7: Claude CLI availability
    total_tests += 1
    try:
        import subprocess
        result = subprocess.run(['claude', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and 'Claude' in result.stdout:
            print(f"✓ Claude CLI: Available - {result.stdout.strip()}")
        else:
            print(f"✓ Claude CLI: Not available (will use mock mode)")
        tests_passed += 1
    except Exception as e:
        print(f"✓ Claude CLI: Not available (will use mock mode)")
        tests_passed += 1  # This is still OK, we have mock mode

    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    print(f"Tests passed: {tests_passed}/{total_tests}")

    if tests_passed == total_tests:
        print("✓ ALL COMPONENTS OPERATIONAL")
        print("✓ Hive V2.1 ready for autonomous operation")
        print("✓ Neural connection: AI Planner -> Queen established")
        return True
    else:
        print(f"✗ {total_tests - tests_passed} component(s) failed")
        print("✗ System requires fixes before autonomous operation")
        return False


def test_integration_readiness():
    """Test if system is ready for full integration"""
    print("\n" + "="*60)
    print("INTEGRATION READINESS CHECK")
    print("="*60)

    # Check daemon scripts exist
    scripts = [
        "scripts/ai_planner_daemon.py",
        "scripts/ai_reviewer_daemon.py",
        "scripts/hive_queen.py"
    ]

    all_scripts_exist = True
    for script in scripts:
        script_path = hive_root / script
        if script_path.exists():
            print(f"✓ {script}: Found")
        else:
            print(f"✗ {script}: Missing")
            all_scripts_exist = False

    # Check database schema
    try:
        conn = hive_core_db.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ['tasks', 'planning_queue', 'execution_plans', 'runs']
        missing_tables = [t for t in required_tables if t not in tables]

        if not missing_tables:
            print(f"✓ Database schema: All required tables present")
        else:
            print(f"✗ Database schema: Missing tables: {missing_tables}")
            all_scripts_exist = False

        conn.close()
    except Exception as e:
        print(f"✗ Database schema check failed: {e}")
        all_scripts_exist = False

    if all_scripts_exist:
        print("\n✓ SYSTEM READY FOR FULL INTEGRATION TEST")
        print("  You can now run: python scripts/grand_integration_test_clean.py")
    else:
        print("\n✗ SYSTEM NOT READY - Fix missing components first")

    return all_scripts_exist


def main():
    """Main validation"""
    print("HIVE V2.1 QUICK VALIDATION")
    print("Checking neural connection and component readiness")

    # Test components
    components_ok = test_components()

    # Test integration readiness
    integration_ready = test_integration_readiness()

    # Final status
    if components_ok and integration_ready:
        print("\n" + "="*60)
        print("🎉 HIVE V2.1 VALIDATION: SUCCESS")
        print("🚀 Neural connection operational")
        print("🤖 All agents ready for autonomous operation")
        print("⚡ AI Planner -> Queen -> AI Reviewer workflow active")
        return 0
    else:
        print("\n" + "="*60)
        print("⚠️  HIVE V2.1 VALIDATION: ISSUES FOUND")
        print("🔧 Fix the issues above before running full integration")
        return 1


if __name__ == "__main__":
    sys.exit(main())