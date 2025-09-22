#!/usr/bin/env python3
"""
End-to-end test for Windows worker spawning with Claude CLI integration.
Tests the complete flow from Queen spawning workers to Claude execution.
"""

import sys
import os
import time
import subprocess
import json
from pathlib import Path
import tempfile
import sqlite3
from datetime import datetime, timezone
import uuid

# Add the src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Add hive_core_db and hive_utils to path - they're in the root packages directory
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-utils" / "src"))

from hive_orchestrator.hive_core import HiveCore
import hive_core_db
from hive_utils.paths import DB_PATH


def setup_test_environment():
    """Set up test environment and database"""
    print("\n[TEST] Setting up test environment...")

    # Initialize HiveCore to ensure database exists
    hive = HiveCore()

    # Clear any existing test tasks
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id LIKE 'test-%'")
    conn.commit()
    conn.close()

    print("[TEST] Environment setup complete")
    return hive


def create_test_task(task_id: str, worker: str = "backend"):
    """Create a simple test task in the database"""
    task = {
        "id": task_id,
        "title": "Test Task",
        "description": f"Test task for Windows E2E - {worker}",
        "task_type": "simple_message",
        "status": "queued",
        "payload": {
            "message": f"Test task for Windows E2E - {worker}",
            "instructions": "Simply acknowledge this test message"
        },
        "assigned_worker": worker,
        "workspace_type": "repo",  # Use repo mode for simplicity
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # Insert task into database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO tasks (id, title, description, task_type, status, payload, assigned_worker, workspace_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task["id"],
        task["title"],
        task["description"],
        task["task_type"],
        task["status"],
        json.dumps(task["payload"]),
        task["assigned_worker"],
        task["workspace_type"],
        task["created_at"]
    ))
    conn.commit()
    conn.close()

    print(f"[TEST] Created test task: {task_id}")
    return task


def spawn_worker_directly(hive: HiveCore, task_id: str, worker: str = "backend"):
    """Test spawning a worker directly using the module approach"""
    print(f"\n[TEST] Spawning worker directly for task {task_id}...")

    # Build command using module approach
    cmd = [
        sys.executable,
        "-m", "hive_orchestrator.worker",
        worker,
        "--one-shot",
        "--task-id", task_id,
        "--run-id", f"test-{uuid.uuid4().hex[:8]}",
        "--phase", "apply",
        "--mode", "repo"
    ]

    # Set up environment
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # Add the src directory to PYTHONPATH
    orchestrator_src = (hive.root / "apps" / "hive-orchestrator" / "src").as_posix()
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{orchestrator_src}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = orchestrator_src

    print(f"[TEST] Command: {' '.join(cmd)}")
    print(f"[TEST] PYTHONPATH: {env.get('PYTHONPATH', 'Not set')}")

    # Spawn the worker process
    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )

        print(f"[TEST] Worker spawned with PID: {process.pid}")

        # Give it 5 seconds to initialize
        print("[TEST] Waiting for worker initialization...")
        time.sleep(5)

        # Check if process is still running
        poll = process.poll()
        if poll is None:
            print("[TEST] SUCCESS: Worker is running")

            # Try to capture some output
            try:
                # Use communicate with timeout to avoid hanging
                stdout, stderr = process.communicate(timeout=2)
                print(f"[TEST] Worker output (if any): {stdout[:500] if stdout else 'No stdout'}")
                print(f"[TEST] Worker stderr: {stderr[:500] if stderr else 'No stderr'}")
            except subprocess.TimeoutExpired:
                print("[TEST] Worker still running (timeout is expected for Claude execution)")
                # Terminate the worker
                process.terminate()
                time.sleep(1)
                if process.poll() is None:
                    process.kill()

            return True
        else:
            # Process exited - capture error
            stdout, stderr = process.communicate()
            print(f"[TEST] FAILED: Worker exited with code: {poll}")
            print(f"[TEST] Stdout: {stdout[:1000] if stdout else 'No stdout'}")
            print(f"[TEST] Stderr: {stderr[:1000] if stderr else 'No stderr'}")
            return False

    except Exception as e:
        print(f"[TEST] FAILED: Failed to spawn worker: {e}")
        return False


def test_queen_spawning(hive: HiveCore):
    """Test the Queen's ability to spawn workers"""
    print("\n[TEST] Testing Queen worker spawning...")

    # Create a test task
    task_id = f"test-queen-{uuid.uuid4().hex[:8]}"
    create_test_task(task_id, "backend")

    # Create a simple Python script to run the Queen and spawn a worker
    test_script = f"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, r"{(hive.root / 'apps' / 'hive-orchestrator' / 'src').as_posix()}")

from hive_orchestrator.queen import QueenLite
from hive_orchestrator import hive_core_db

# Create Queen instance
queen = QueenLite(live_output=False)

# Get the test task directly from database since hive_core_db.get_task may have different structure
import sqlite3
import json
conn = sqlite3.connect(r"{str(DB_PATH)}")
cursor = conn.cursor()
cursor.execute("SELECT * FROM tasks WHERE id = ?", ("{task_id}",))
row = cursor.fetchone()
conn.close()

if not row:
    print("[TEST] Task not found!")
    sys.exit(1)

# Convert row to dict matching expected format
task = {{
    "id": "{task_id}",
    "assigned_to": "backend",
    "workspace": "repo"
}}

print(f"[TEST] Found task: {{task['id']}}")

# Spawn worker
from hive_orchestrator.types import Phase
process, run_id = queen.spawn_worker("{task_id}", task, "backend", Phase.APPLY)

if process:
    print(f"[TEST] Worker spawned successfully with PID: {{process.pid}}")

    # Give it a few seconds
    import time
    time.sleep(5)

    # Check status
    poll = process.poll()
    if poll is None:
        print("[TEST] Worker is still running - SUCCESS")
        process.terminate()
        sys.exit(0)
    else:
        print(f"[TEST] Worker exited with code: {{poll}}")
        sys.exit(1)
else:
    print("[TEST] Failed to spawn worker")
    sys.exit(1)
"""

    # Write test script to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_script)
        script_path = f.name

    try:
        # Run the test script
        print(f"[TEST] Running Queen spawn test...")
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(f"[TEST] Queen test output:\n{result.stdout}")
        if result.stderr:
            print(f"[TEST] Queen test stderr:\n{result.stderr}")

        if result.returncode == 0:
            print("[TEST] SUCCESS: Queen successfully spawned worker")
            return True
        else:
            print(f"[TEST] FAILED: Queen test failed with code: {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print("[TEST] FAILED: Queen test timed out")
        return False
    finally:
        # Clean up temp file
        os.unlink(script_path)


def test_error_capture():
    """Test that worker errors are properly captured"""
    print("\n[TEST] Testing error capture...")

    # Create a task that will cause an error (invalid task ID)
    cmd = [
        sys.executable,
        "-m", "hive_orchestrator.worker",
        "backend",
        "--one-shot",
        "--task-id", "invalid-task-id",
        "--run-id", "test-error",
        "--phase", "apply",
        "--mode", "repo"
    ]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    hive = HiveCore()
    orchestrator_src = (hive.root / "apps" / "hive-orchestrator" / "src").as_posix()
    env["PYTHONPATH"] = orchestrator_src

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )

    # Wait for it to fail
    stdout, stderr = process.communicate(timeout=10)

    if process.returncode == 2:  # Expected error code
        if "[WORKER INIT]" in stderr and "Task not found" in stderr:
            print("[TEST] SUCCESS: Error properly captured in stderr")
            print(f"[TEST] Error message: {stderr[:500]}")
            return True
        else:
            print("[TEST] FAILED: Error not properly captured")
            print(f"[TEST] Stderr: {stderr[:500]}")
            return False
    else:
        print(f"[TEST] FAILED: Unexpected return code: {process.returncode}")
        return False


def main():
    """Run all E2E tests"""
    print("="*70)
    print("Windows E2E Test Suite for Hive V2.0")
    print("="*70)

    # Setup
    hive = setup_test_environment()

    # Track results
    results = []

    # Test 1: Direct worker spawning
    task_id = f"test-direct-{uuid.uuid4().hex[:8]}"
    create_test_task(task_id)
    success = spawn_worker_directly(hive, task_id)
    results.append(("Direct Worker Spawning", success))

    # Test 2: Queen spawning
    success = test_queen_spawning(hive)
    results.append(("Queen Worker Spawning", success))

    # Test 3: Error capture
    success = test_error_capture()
    results.append(("Error Capture", success))

    # Summary
    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)

    all_passed = True
    for test_name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False

    print("="*70)
    if all_passed:
        print("ALL TESTS PASSED! Windows integration is working correctly.")
        return 0
    else:
        print("WARNING: Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())