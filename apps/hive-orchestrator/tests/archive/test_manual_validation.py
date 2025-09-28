#!/usr/bin/env python3
"""
Manual validation test for Windows worker spawning.
Creates a simple task and verifies that Queen can spawn workers correctly.
"""

import sys
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import time

# Setup paths
project_root = Path(__file__).parent.parent.parent.parent
# No sys.path manipulation needed - use Poetry workspace imports
# No sys.path manipulation needed - use Poetry workspace imports
# No sys.path manipulation needed - use Poetry workspace imports
# No sys.path manipulation needed - use Poetry workspace imports

from hive_utils.paths import DB_PATH


def create_validation_task():
    """Create a simple validation task"""
    task_id = f"validate-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    task_data = {
        "id": task_id,
        "title": "Windows Validation Task",
        "description": "Simple task to validate Windows worker spawning",
        "task_type": "echo",
        "priority": 1,
        "status": "queued",
        "current_phase": "start",
        "workflow": json.dumps({
            "start": {
                "command_template": "echo 'Hello from Windows worker validation test'"
            }
        }),
        "payload": json.dumps({
            "message": "Testing Windows worker spawning",
            "command": "echo 'Worker successfully started and executed'"
        }),
        "assigned_worker": "backend",
        "workspace_type": "repo",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # Insert into database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tasks (
            id, title, description, task_type, priority, status,
            current_phase, workflow, payload, assigned_worker,
            workspace_type, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_data["id"],
        task_data["title"],
        task_data["description"],
        task_data["task_type"],
        task_data["priority"],
        task_data["status"],
        task_data["current_phase"],
        task_data["workflow"],
        task_data["payload"],
        task_data["assigned_worker"],
        task_data["workspace_type"],
        task_data["created_at"]
    ))

    conn.commit()
    conn.close()

    print(f"Created validation task: {task_id}")
    return task_id


def check_task_status(task_id):
    """Check the status of a task"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT status, assigned_worker FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0], row[1]
    return None, None


def main():
    """Run manual validation"""
    print("=" * 70)
    print("Windows Worker Spawning - Manual Validation Test")
    print("=" * 70)
    print()
    print("This test will:")
    print("1. Create a simple task in the database")
    print("2. Wait for you to run the Queen (python run_queen.py)")
    print("3. Monitor the task status")
    print()
    print("=" * 70)

    # Create task
    task_id = create_validation_task()
    print(f"\nTask created: {task_id}")
    print()
    print("Now run the Queen in another terminal:")
    print("  cd apps/hive-orchestrator")
    print("  python run_queen.py")
    print()
    print("Press Ctrl+C to stop monitoring")
    print()

    # Monitor task status
    last_status = None
    try:
        while True:
            status, worker = check_task_status(task_id)
            if status != last_status:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Task status: {status} (assigned to: {worker})")
                last_status = status

                if status in ["completed", "failed"]:
                    print()
                    if status == "completed":
                        print("SUCCESS: Task completed successfully!")
                        print("Windows worker spawning is working correctly!")
                    else:
                        print("FAILED: Task failed. Check logs for details.")
                    break

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopped monitoring")
        return 0

    return 0 if status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())