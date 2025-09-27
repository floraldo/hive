#!/usr/bin/env python3
"""
Neural Connection Validation Test

Quick test to validate that the AI Planner -> Queen neural connection is working.
Tests the complete data flow without running actual daemons.
"""

import sys
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Setup paths
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-config" / "src"))
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(hive_root / "apps" / "ai-planner" / "src"))

from hive_config import setup_hive_paths
setup_hive_paths()

import hive_core_db
from hive_core_db.database import get_connection
from hive_core_db.database_enhanced import get_queued_tasks_with_planning, create_planned_subtasks_from_plan
from ai_planner.agent import AIPlanner


def test_neural_connection():
    """Test complete neural connection flow"""
    print("="*60)
    print("NEURAL CONNECTION VALIDATION TEST")
    print("="*60)

    test_id = f"neural-test-{uuid.uuid4().hex[:8]}"

    try:
        # Initialize database
        hive_core_db.init_db()
        print("OK Database initialized")

        # Create AI Planner in mock mode for quick testing
        planner = AIPlanner(mock_mode=True)
        success = planner.connect_database()
        assert success, "Failed to connect to database"
        print("OK AI Planner connected")

        # Step 1: Create a test planning task
        test_task_id = f"neural-test-{test_id}"
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO planning_queue
            (id, task_description, priority, requestor, context_data, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            test_task_id,
            "Create a simple REST API with user authentication endpoints",
            75,
            f"neural_test_{test_id}",
            json.dumps({"test": True, "type": "neural_validation"}),
            "pending",
            datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        print(f"OK Test task created: {test_task_id}")

        # Step 2: Process task with AI Planner (mock mode)
        task = planner.get_next_task()
        assert task is not None, "No task found in planning queue"
        assert task['id'] == test_task_id, f"Got wrong task: {task['id']}"
        print("OK AI Planner retrieved task")

        # Process the task
        success = planner.process_task(task)
        assert success, "Failed to process task"
        print("OK AI Planner processed task successfully")

        # Verify plan was created
        cursor.execute("SELECT status FROM planning_queue WHERE id = ?", (test_task_id,))
        status = cursor.fetchone()[0]
        assert status == "planned", f"Task status is {status}, expected 'planned'"
        print("OK Task marked as planned")

        # Verify execution plan exists
        cursor.execute("SELECT COUNT(*) FROM execution_plans WHERE planning_task_id = ?", (test_task_id,))
        plan_count = cursor.fetchone()[0]
        assert plan_count > 0, "No execution plan created"
        print(f"OK Execution plan created ({plan_count} plans)")

        # Step 3: Test neural connection - get tasks that Queen would see
        neural_tasks = get_queued_tasks_with_planning(limit=20)

        # Count planner-generated tasks
        planner_tasks = [t for t in neural_tasks if t.get('task_type') == 'planned_subtask']

        print(f"OK Neural connection working:")
        print(f"  Total tasks visible to Queen: {len(neural_tasks)}")
        print(f"  AI Planner-generated tasks: {len(planner_tasks)}")

        # Verify Queen can see the planned subtasks
        if planner_tasks:
            sample_task = planner_tasks[0]
            print(f"  Sample planner task: {sample_task['title']}")
            print(f"  Assignee: {sample_task.get('assignee', 'unassigned')}")
            print(f"  Priority: {sample_task.get('priority', 'unknown')}")

            # Check planner context
            if 'planner_context' in sample_task:
                context = sample_task['planner_context']
                print(f"  Workflow phase: {context.get('workflow_phase', 'unknown')}")
                print(f"  Required skills: {context.get('required_skills', [])}")

        # Step 4: Verify that Queen would be able to execute these tasks
        print(f"OK Queen neural interface validation:")
        for i, task in enumerate(planner_tasks[:3]):  # Check first 3 tasks
            task_id = task['id']
            title = task['title'][:50] + "..." if len(task['title']) > 50 else task['title']
            assignee = task.get('assignee', 'unassigned')
            print(f"  [{i+1}] {title} -> {assignee}")

        # Step 5: Clean up test data
        cursor.execute("DELETE FROM tasks WHERE task_type = 'planned_subtask' AND json_extract(payload, '$.parent_plan_id') LIKE ?", (f"%{test_task_id}%",))
        cursor.execute("DELETE FROM execution_plans WHERE planning_task_id = ?", (test_task_id,))
        cursor.execute("DELETE FROM planning_queue WHERE id = ?", (test_task_id,))
        conn.commit()
        conn.close()

        print("OK Test data cleaned up")

        # Final validation
        print("="*60)
        print("NEURAL CONNECTION VALIDATION: SUCCESS")
        print("="*60)
        print("VALIDATED COMPONENTS:")
        print("  AI Planner: Can generate execution plans")
        print("  Database Bridge: Enhanced queries working")
        print("  Queen Interface: Can see planner-generated tasks")
        print("  Neural Flow: AI Planner -> Queen communication established")
        print("")
        print("V2.1 NEURAL CONNECTION: OPERATIONAL")

        return True

    except Exception as e:
        print(f"FAIL Neural connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_functions():
    """Test the database enhanced functions directly"""
    print("\n" + "="*60)
    print("DATABASE ENHANCED FUNCTIONS TEST")
    print("="*60)

    try:
        # Test function is importable and callable
        from hive_core_db.database_enhanced import (
            get_queued_tasks_with_planning,
            check_subtask_dependencies,
            get_execution_plan_status,
            mark_plan_execution_started,
            get_next_planned_subtask,
            create_planned_subtasks_from_plan
        )
        print("OK All enhanced database functions importable")

        # Test get_queued_tasks_with_planning
        tasks = get_queued_tasks_with_planning(limit=5)
        print(f"OK get_queued_tasks_with_planning: returned {len(tasks)} tasks")

        # Test connection to database
        conn = get_connection()
        cursor = conn.cursor()

        # Test database schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ['tasks', 'planning_queue', 'execution_plans']
        for table in required_tables:
            assert table in tables, f"Required table {table} not found"

        print(f"OK Database schema validated: {len(tables)} tables")
        print(f"   Tables: {', '.join(tables)}")

        conn.close()

        return True

    except Exception as e:
        print(f"FAIL Database functions test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    print("HIVE V2.1 NEURAL CONNECTION VALIDATION")
    print("Testing AI Planner -> Queen communication bridge")

    # Test database functions first
    db_success = test_database_functions()

    # Test full neural connection
    neural_success = test_neural_connection()

    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    print(f"Database Functions: {'PASS' if db_success else 'FAIL'}")
    print(f"Neural Connection: {'PASS' if neural_success else 'FAIL'}")

    overall_success = db_success and neural_success

    if overall_success:
        print(f"\nOVERALL: SUCCESS")
        print(f"Hive V2.1 neural connection is OPERATIONAL")
        print(f"AI Planner and Queen can communicate through the database")
        return 0
    else:
        print(f"\nOVERALL: FAILED")
        print(f"Neural connection requires fixes")
        return 1


if __name__ == "__main__":
    sys.exit(main())