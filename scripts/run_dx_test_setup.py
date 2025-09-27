#!/usr/bin/env python3
"""
Live Fire DX Test Setup Script

This script prepares a controlled test environment to validate the Developer Experience
and observability of the Hive V2.1 autonomous agency platform.

The test exercises the complete autonomous workflow:
Task Creation -> Queen Execution -> AI Review -> Testing -> Completion
"""

import os
import sys
import json
import uuid
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# Setup paths
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-config" / "src"))
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))

from hive_config import setup_hive_paths
setup_hive_paths()

import hive_core_db
from hive_core_db.database import get_connection


def clean_environment():
    """Clean the environment for a fresh test"""
    print("Phase 1: Cleaning Test Environment")
    print("-" * 40)

    try:
        # Run hive-clean equivalent
        print("  Cleaning database...")

        # Initialize clean database
        hive_core_db.init_db()

        # Clean any existing tasks to avoid interference
        conn = get_connection()
        cursor = conn.cursor()

        # Remove any pending/running tasks
        cursor.execute("DELETE FROM tasks WHERE status IN ('queued', 'in_progress', 'review_pending')")
        cursor.execute("DELETE FROM runs WHERE status IN ('pending', 'running')")

        conn.commit()
        conn.close()

        print("  OK Database cleaned successfully")
        return True

    except Exception as e:
        print(f"  FAIL Failed to clean environment: {e}")
        return False


def create_test_task():
    """Create a simple, observable test task"""
    print("\nPhase 2: Creating Test Task")
    print("-" * 40)

    try:
        test_id = f"dx-test-{uuid.uuid4().hex[:8]}"

        # Create a simple but complete task that exercises the full workflow
        task_data = {
            "id": test_id,
            "title": "Create String Reverse Function",
            "description": """Create a Python function that takes a string and returns its reverse.

Requirements:
1. Function name: reverse_string(text: str) -> str
2. Handle empty strings and None values gracefully
3. Include proper docstring with example usage
4. Create comprehensive unit tests with pytest
5. Follow PEP 8 style guidelines

Deliverables:
- Implementation file: string_utils.py
- Test file: test_string_utils.py
- Both files should be properly formatted and documented""",
            "task_type": "development",
            "priority": 80,
            "status": "queued",
            "assignee": "worker:backend",
            "payload": {
                "test_type": "dx_validation",
                "complexity": "simple",
                "expected_files": ["string_utils.py", "test_string_utils.py"],
                "workflow_phases": ["apply", "inspect", "review", "test"],
                "estimated_duration": 5  # 5 minutes for quick testing
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        # Insert the task
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tasks (
                id, title, description, task_type, priority, status,
                assignee, payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_data["id"],
            task_data["title"],
            task_data["description"],
            task_data["task_type"],
            task_data["priority"],
            task_data["status"],
            task_data["assignee"],
            json.dumps(task_data["payload"]),
            task_data["created_at"],
            task_data["updated_at"]
        ))

        conn.commit()
        conn.close()

        print(f"  OK Created test task: {test_id}")
        print(f"    Title: {task_data['title']}")
        print(f"    Type: {task_data['task_type']} -> {task_data['assignee']}")
        print(f"    Expected workflow: apply -> inspect -> review -> test -> completed")

        return test_id

    except Exception as e:
        print(f"  FAIL Failed to create test task: {e}")
        return None


def verify_test_setup():
    """Verify the test environment is properly configured"""
    print("\nPhase 3: Verifying Test Setup")
    print("-" * 40)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check for our test task
        cursor.execute("SELECT id, title, status FROM tasks WHERE status = 'queued'")
        queued_tasks = cursor.fetchall()

        if not queued_tasks:
            print("  FAIL No queued tasks found")
            return False

        print(f"  OK Found {len(queued_tasks)} queued task(s)")
        for task_id, title, status in queued_tasks:
            print(f"    {task_id}: {title} ({status})")

        # Verify database tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ['tasks', 'runs', 'workers']
        missing_tables = [t for t in required_tables if t not in tables]

        if missing_tables:
            print(f"  FAIL Missing required tables: {missing_tables}")
            return False

        print(f"  OK All required database tables present")

        conn.close()
        return True

    except Exception as e:
        print(f"  FAIL Verification failed: {e}")
        return False


def print_live_fire_instructions():
    """Print instructions for the human operator"""
    print("\n" + "=" * 60)
    print("LIVE FIRE DX TEST READY")
    print("=" * 60)

    print("""
SUCCESS **Test Environment is Ready.**

A single, simple 'string reverse' task has been seeded into the database.

To begin the Live Fire DX Test, please open **three separate terminals**
and run the following commands, one in each:

**Terminal 1 (The Dashboard - Your Primary View):**
```bash
poetry run hive-dashboard
```

**Terminal 2 (The Queen - The Engine Room):**
```bash
poetry run hive-queen
```

**Terminal 3 (The Reviewer - The QA Robot):**
```bash
poetry run ai-reviewer-daemon
```

Once all three services are running, your primary focus should be the
**Dashboard in Terminal 1.** You are about to witness the entire
autonomous lifecycle in real-time.

🔍 **Observability Checklist:**

As the system runs, please verify that you can see the following events
happen on your dashboard **in real-time**:

1.  **[ ] Queued:** The 'string reverse' task initially appears in the
    "Recent Tasks" table with a `queued` status.

2.  **[ ] In Progress:** The task's status changes to `in_progress`.
    The "Active Workers" table shows a new `worker:backend` process
    has been spawned.

3.  **[ ] Awaiting Review:** After a minute or two, the `worker:backend`
    disappears from the "Active Workers" table, and the task's status
    changes to `review_pending`.

4.  **[ ] AI Review:** The `ai-reviewer` daemon's log (in Terminal 3)
    shows that it has picked up the task.

5.  **[ ] Review Approved:** The task's status on the dashboard changes
    from `review_pending` back to `queued`, and its `current_phase` is
    now `test`.

6.  **[ ] Testing:** The task's status changes to `in_progress` again
    as the `Queen` launches the `test` phase.

7.  **[ ] Completed:** The task's final status becomes `completed`.

**This entire process should happen autonomously without any human interaction.**

SUCCESS **If you can successfully check off all these boxes, the DX and
observability of the Hive V2.1 platform is officially certified.**

📊 **Dashboard Focus Areas:**
- Recent Tasks table (watch status changes)
- Active Workers table (watch processes spawn/complete)
- System Statistics (task completion rates)
- Real-time updates (should refresh automatically)

🎯 **Success Criteria:**
- Complete autonomous execution from queued -> completed
- Clear visibility of each workflow phase
- Real-time dashboard updates
- AI Reviewer integration working
- No manual intervention required

Expected Duration  **Expected Duration:** 3-5 minutes for complete workflow

🚀 **Ready to launch? Start with Terminal 1 (Dashboard), then Terminals 2 & 3!**
""")


def main():
    """Main test setup function"""
    print("HIVE V2.1 LIVE FIRE DX TEST SETUP")
    print("Preparing autonomous agency observability validation")
    print("=" * 60)

    # Phase 1: Clean environment
    if not clean_environment():
        print("\nFAIL SETUP FAILED: Could not clean environment")
        return 1

    # Phase 2: Create test task
    test_id = create_test_task()
    if not test_id:
        print("\nFAIL SETUP FAILED: Could not create test task")
        return 1

    # Phase 3: Verify setup
    if not verify_test_setup():
        print("\nFAIL SETUP FAILED: Environment verification failed")
        return 1

    # Print instructions for live fire test
    print_live_fire_instructions()

    print("\n" + "=" * 60)
    print("SUCCESS SETUP COMPLETE - READY FOR LIVE FIRE DX TEST")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())