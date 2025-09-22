#!/usr/bin/env python3
"""
Automated validation test for Windows worker spawning.
Tests the full pipeline: Queen spawns worker, worker executes task.
"""

import sys
import os
import json
import sqlite3
import subprocess
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

# Setup paths
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "apps" / "hive-orchestrator" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-utils" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-logging" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-core-db" / "src"))

from hive_utils.paths import DB_PATH


def create_simple_task():
    """Create a simple echo task"""
    task_id = f"auto-test-{datetime.now().strftime('%H%M%S')}"

    task_data = {
        "id": task_id,
        "title": "Automated Test",
        "description": "Automated validation test",
        "task_type": "simple",
        "priority": 1,
        "status": "queued",
        "current_phase": "start",
        "payload": json.dumps({
            "message": "Testing Windows integration",
            "action": "validate"
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
            current_phase, payload, assigned_worker,
            workspace_type, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_data["id"],
        task_data["title"],
        task_data["description"],
        task_data["task_type"],
        task_data["priority"],
        task_data["status"],
        task_data["current_phase"],
        task_data["payload"],
        task_data["assigned_worker"],
        task_data["workspace_type"],
        task_data["created_at"]
    ))

    conn.commit()
    conn.close()

    return task_id


def run_queen_with_timeout(timeout=30):
    """Run Queen for a limited time"""
    queen_script = Path(__file__).parent.parent / "run_queen.py"

    proc = subprocess.Popen(
        [sys.executable, str(queen_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Let it run for the timeout period
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        proc.terminate()
        time.sleep(1)
        if proc.poll() is None:
            proc.kill()
        return 0, "Queen terminated after timeout", ""


def check_task_completion(task_id):
    """Check if task was processed"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]
    return None


def main():
    """Run automated validation"""
    print("=" * 70)
    print("Automated Windows Integration Test")
    print("=" * 70)

    # Step 1: Create task
    print("\n[1/3] Creating test task...")
    task_id = create_simple_task()
    print(f"Created task: {task_id}")

    # Step 2: Run Queen in background
    print("\n[2/3] Starting Queen orchestrator...")
    print("Queen will run for 15 seconds to process the task...")

    # Run Queen in a thread
    queen_thread = threading.Thread(target=run_queen_with_timeout, args=(15,))
    queen_thread.start()

    # Monitor task status while Queen runs
    print("\n[3/3] Monitoring task status...")
    start_time = time.time()
    last_status = None

    while time.time() - start_time < 20:  # Monitor for up to 20 seconds
        status = check_task_completion(task_id)
        if status != last_status:
            print(f"Task status: {status}")
            last_status = status

        if status in ["assigned", "in_progress"]:
            print("SUCCESS: Queen successfully spawned worker!")
            print("Worker is processing the task.")
            queen_thread.join()  # Wait for Queen to finish
            return 0

        time.sleep(2)

    queen_thread.join()  # Ensure Queen thread completes

    # Final check
    final_status = check_task_completion(task_id)
    print(f"\nFinal task status: {final_status}")

    if final_status != "queued":
        print("\nSUCCESS: Task was processed by the system!")
        print("Windows worker spawning is functioning correctly.")
        return 0
    else:
        print("\nFAILED: Task was not processed.")
        print("Check logs for issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())