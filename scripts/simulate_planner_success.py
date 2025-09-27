#!/usr/bin/env python3
"""
Simulate a successful AI Planner operation for testing the autonomous loop.
This creates a mock execution plan and sub-tasks to verify the Queen integration.
"""

import sys
import json
import uuid
from pathlib import Path
from datetime import datetime

# Add packages path
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))

import hive_core_db


def simulate_planner_success(master_task_id: str = None):
    """Simulate AI Planner successfully processing a task"""

    if not master_task_id:
        # Find the most recent pending task in planning_queue
        conn = hive_core_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM planning_queue
            WHERE status IN ('pending', 'failed')
            ORDER BY created_at DESC
            LIMIT 1
        """)
        result = cursor.fetchone()

        if not result:
            print("No pending tasks found in planning_queue")
            cursor.close()
            conn.close()
            return False

        master_task_id = result[0]
        cursor.close()
        conn.close()

    print(f"Simulating AI Planner success for task: {master_task_id}")

    conn = hive_core_db.get_connection()
    cursor = conn.cursor()

    # Update planning_queue status to planned
    cursor.execute("""
        UPDATE planning_queue
        SET status = 'planned',
            assigned_agent = 'simulator',
            assigned_at = CURRENT_TIMESTAMP,
            completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (master_task_id,))

    # Create a mock execution plan
    plan_id = f"plan-{uuid.uuid4().hex[:8]}"
    plan_data = {
        "version": "1.0",
        "created_by": "simulator",
        "workflow_phases": ["apply", "inspect", "review", "test"],
        "sub_tasks": [
            {
                "id": "task-001",
                "title": "Create API endpoint structure",
                "description": "Set up the basic API endpoint at /api/health",
                "assignee": "worker:backend",
                "priority": 90,
                "complexity": "simple",
                "estimated_duration": "10 minutes",
                "workflow_phase": "apply",
                "dependencies": [],
                "deliverables": ["API endpoint code"]
            },
            {
                "id": "task-002",
                "title": "Add timestamp functionality",
                "description": "Add current timestamp to the health response",
                "assignee": "worker:backend",
                "priority": 85,
                "complexity": "simple",
                "estimated_duration": "5 minutes",
                "workflow_phase": "apply",
                "dependencies": ["task-001"],
                "deliverables": ["Timestamp logic"]
            },
            {
                "id": "task-003",
                "title": "Write unit tests",
                "description": "Create tests for the health endpoint",
                "assignee": "worker:backend",
                "priority": 80,
                "complexity": "simple",
                "estimated_duration": "15 minutes",
                "workflow_phase": "test",
                "dependencies": ["task-002"],
                "deliverables": ["Test suite"]
            }
        ]
    }

    cursor.execute("""
        INSERT INTO execution_plans (
            id, planning_task_id, plan_data, status,
            estimated_duration, estimated_complexity,
            subtask_count, dependency_count, generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        plan_id,
        master_task_id,
        json.dumps(plan_data),
        "generated",
        30,  # estimated duration in minutes
        "simple",  # complexity
        len(plan_data["sub_tasks"]),
        2  # number of dependencies
    ))

    # Create sub-tasks in tasks table
    for sub_task in plan_data["sub_tasks"]:
        task_id = f"subtask_{plan_id}_{sub_task['id']}"

        payload = {
            "parent_plan_id": plan_id,
            "subtask_id": sub_task["id"],
            "complexity": sub_task["complexity"],
            "estimated_duration": sub_task["estimated_duration"],
            "workflow_phase": sub_task["workflow_phase"],
            "required_skills": [],
            "deliverables": sub_task["deliverables"],
            "dependencies": sub_task["dependencies"]
        }

        cursor.execute("""
            INSERT INTO tasks (
                id, title, task_type, status, priority,
                assignee, description, created_at, updated_at, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
        """, (
            task_id,
            sub_task["title"],
            "planned_subtask",
            "queued",
            sub_task["priority"],
            sub_task["assignee"],
            sub_task["description"],
            json.dumps(payload)
        ))

    conn.commit()

    # Verify the results
    cursor.execute("SELECT COUNT(*) FROM execution_plans WHERE planning_task_id = ?", (master_task_id,))
    plan_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE task_type = 'planned_subtask'")
    task_count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    print(f"SUCCESS: Simulated AI Planner completion")
    print(f"  - Planning task status: planned")
    print(f"  - Execution plans created: {plan_count}")
    print(f"  - Sub-tasks created: {len(plan_data['sub_tasks'])}")
    print(f"  - Total planned_subtask tasks in database: {task_count}")

    return True


def main():
    """Main entry point"""
    import sys

    master_task_id = sys.argv[1] if len(sys.argv) > 1 else None

    success = simulate_planner_success(master_task_id)

    if success:
        print("\nSimulation complete. The Queen should now be able to pick up these tasks.")
    else:
        print("\nSimulation failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()