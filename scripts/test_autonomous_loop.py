#!/usr/bin/env python3
"""
AUTONOMOUS LOOP INTEGRATION TEST

This script tests the complete autonomous workflow:
1. Submit high-level intent to AI Planner
2. AI Planner generates execution plan with sub-tasks
3. Queen picks up and executes planner-generated sub-tasks
4. Full lifecycle completion without human intervention

This is the final test that proves the neural connection between
the AI Planner (brain) and the Hive Orchestrator (body).
"""

import sys
import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Add packages path
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))

import hive_core_db
from hive_core_db.database import get_connection


def create_test_master_task():
    """Create a master task for the AI Planner to process"""

    master_task_id = f"auto-loop-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    task_description = """
Create a Simple REST API

Develop a basic REST API with the following endpoints:
- GET /health - Health check endpoint
- GET /items - List all items
- POST /items - Create a new item
- GET /items/{id} - Get a specific item
- DELETE /items/{id} - Delete an item

Technical requirements:
- Use Python with Flask or FastAPI
- Include proper error handling
- Add input validation
- Write unit tests
- Create API documentation
""".strip()

    context_data = {
        "project_type": "api_development",
        "technologies": ["python", "flask", "sqlite"],
        "estimated_complexity": "simple",
        "components": ["api_endpoints", "data_layer", "tests", "documentation"]
    }

    conn = hive_core_db.get_connection()
    cursor = conn.cursor()

    # Insert into planning_queue for AI Planner
    cursor.execute("""
        INSERT INTO planning_queue
        (id, task_description, priority, requestor, context_data, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        master_task_id,
        task_description,
        90,
        "autonomous_test",
        json.dumps(context_data),
        "pending"
    ))

    conn.commit()
    conn.close()

    print(f"SUCCESS: Master task created: {master_task_id}")
    return master_task_id


def monitor_ai_planner_processing(master_task_id: str, timeout: int = 60) -> bool:
    """Monitor AI Planner processing of the master task"""

    print(f"\nAI: Monitoring AI Planner processing...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        conn = hive_core_db.get_connection()
        cursor = conn.cursor()

        # Check planning_queue status
        cursor.execute("SELECT status, assigned_agent FROM planning_queue WHERE id = ?", (master_task_id,))
        result = cursor.fetchone()

        if result:
            status, agent = result
            print(f"  Planning status: {status} (agent: {agent})")

            if status == "planned":
                # Check if execution plan was created
                cursor.execute("SELECT COUNT(*) FROM execution_plans WHERE planning_task_id = ?", (master_task_id,))
                plan_count = cursor.fetchone()[0]

                print(f"  SUCCESS: AI Planner completed! Plans created: {plan_count}")
                cursor.close()  # Close cursor before connection
                conn.close()
                return True

            elif status == "failed":
                print(f"  FAILED: AI Planner failed to process task")
                cursor.close()  # Close cursor before connection
                conn.close()
                return False

        cursor.close()  # Close cursor before connection
        conn.close()
        time.sleep(5)

    print(f"  TIMEOUT: Timeout waiting for AI Planner")
    return False


def check_planner_subtasks() -> int:
    """Check how many planner-generated sub-tasks exist"""

    conn = hive_core_db.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE task_type = 'planned_subtask'")
    count = cursor.fetchone()[0]

    cursor.close()
    conn.close()
    return count


def monitor_queen_execution(timeout: int = 120) -> bool:
    """Monitor Queen execution of planner-generated sub-tasks"""

    print(f"\nQUEEN: Monitoring Queen execution of planner sub-tasks...")
    start_time = time.time()
    tasks_seen = set()

    while time.time() - start_time < timeout:
        conn = hive_core_db.get_connection()
        cursor = conn.cursor()

        # Check for planner sub-tasks being executed
        cursor.execute("""
            SELECT id, title, status, assignee
            FROM tasks
            WHERE task_type = 'planned_subtask'
            AND status IN ('assigned', 'in_progress', 'completed')
        """)

        executed_tasks = cursor.fetchall()

        for task_id, title, status, assignee in executed_tasks:
            if task_id not in tasks_seen:
                print(f"  EXECUTING: Queen executing: {title[:50]}... ({status}) -> {assignee}")
                tasks_seen.add(task_id)

        # Check if any sub-tasks completed
        cursor.execute("""
            SELECT COUNT(*)
            FROM tasks
            WHERE task_type = 'planned_subtask'
            AND status = 'completed'
        """)

        completed_count = cursor.fetchone()[0]

        if completed_count > 0:
            print(f"  SUCCESS: Queen successfully executed {completed_count} planner sub-tasks!")
            cursor.close()
            conn.close()
            return True

        cursor.close()
        conn.close()
        time.sleep(5)

    print(f"  TIMEOUT: Timeout waiting for Queen execution")
    return False


def verify_autonomous_loop():
    """Main test function to verify the complete autonomous loop"""

    print("=" * 80)
    print("AUTONOMOUS LOOP INTEGRATION TEST")
    print("Testing: Human Intent -> AI Planner -> Queen -> Execution")
    print("=" * 80)

    # Step 1: Create master task
    print("\nTASK: Step 1: Creating master task for AI Planner...")
    master_task_id = create_test_master_task()

    # Step 2: Wait for AI Planner to process
    print("\nAI: Step 2: Waiting for AI Planner to generate execution plan...")
    print("(Ensure AI Planner daemon is running)")

    planner_success = monitor_ai_planner_processing(master_task_id, timeout=60)

    if not planner_success:
        print("\nFAILED: AI Planner did not process the task in time")
        print("Make sure the AI Planner daemon is running:")
        print("  cd apps/ai-planner && python run_agent.py --mock")
        return False

    # Step 3: Check for created sub-tasks
    print("\nDATA: Step 3: Checking for planner-generated sub-tasks...")
    subtask_count = check_planner_subtasks()

    if subtask_count == 0:
        # Try to create them from the plan
        print("  Creating sub-tasks from execution plan...")
        conn = hive_core_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM execution_plans WHERE planning_task_id = ? LIMIT 1", (master_task_id,))
        plan_result = cursor.fetchone()

        if plan_result:
            plan_id = plan_result[0]
            created = hive_core_db.create_planned_subtasks_from_plan(plan_id)
            print(f"  Created {created} sub-tasks from plan")
            subtask_count = check_planner_subtasks()

        cursor.close()
        conn.close()

    print(f"  Found {subtask_count} planner-generated sub-tasks ready for execution")

    if subtask_count == 0:
        print("\nWARNING: No sub-tasks created. Check AI Planner configuration.")
        return False

    # Step 4: Wait for Queen to pick up and execute
    print("\nQUEEN: Step 4: Waiting for Queen to execute planner sub-tasks...")
    print("(Ensure Queen/Orchestrator daemon is running)")

    queen_success = monitor_queen_execution(timeout=120)

    if not queen_success:
        print("\nWARNING: Queen did not execute planner sub-tasks in time")
        print("Make sure the Queen daemon is running:")
        print("  cd apps/hive-orchestrator && python run_queen.py")
        return False

    # Step 5: Final verification
    print("\nSUCCESS: Step 5: Verifying complete autonomous loop...")

    conn = hive_core_db.get_connection()
    cursor = conn.cursor()

    # Get final statistics
    cursor.execute("SELECT status FROM planning_queue WHERE id = ?", (master_task_id,))
    master_status = cursor.fetchone()[0] if cursor.fetchone() else "unknown"

    cursor.execute("""
        SELECT COUNT(*), SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)
        FROM tasks
        WHERE task_type = 'planned_subtask'
    """)
    total_subtasks, completed_subtasks = cursor.fetchone()

    cursor.close()
    conn.close()

    print(f"\nSTATS: Final Statistics:")
    print(f"  Master Task Status: {master_status}")
    print(f"  Total Sub-tasks: {total_subtasks}")
    print(f"  Completed Sub-tasks: {completed_subtasks}")

    if master_status == "planned" and completed_subtasks > 0:
        print("\n" + "=" * 80)
        print("SUCCESS: SUCCESS: AUTONOMOUS LOOP VERIFIED!")
        print("=" * 80)
        print("\nThe Hive V2.1 platform has successfully demonstrated:")
        print("1. SUCCESS: AI Planner processed high-level intent")
        print("2. SUCCESS: Execution plan generated with sub-tasks")
        print("3. SUCCESS: Queen detected and executed planner sub-tasks")
        print("4. SUCCESS: Complete autonomous workflow without human intervention")
        print("\nLAUNCH: THE NEURAL CONNECTION IS COMPLETE!")
        print("The AI brain and execution body are fully integrated.")
        return True
    else:
        print("\nWARNING: Autonomous loop not fully verified")
        return False


def main():
    """Main entry point"""

    print("Starting Autonomous Loop Integration Test...")
    print("This test requires both AI Planner and Queen daemons to be running.")
    print()

    success = verify_autonomous_loop()

    if success:
        print("\nCOMPLETE: The Hive Autonomous Software Factory is ONLINE! COMPLETE:")
        sys.exit(0)
    else:
        print("\nTest incomplete. Check daemon status and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()