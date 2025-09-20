#!/usr/bin/env python3
"""
Test script to verify parallel task execution in Hive V2.0
Creates multiple tasks and verifies they are processed concurrently.
"""

import sys
import time
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-config" / "src"))

from hive_core_db import (
    init_db,
    create_task,
    get_tasks_by_status,
    get_connection,
    close_connection
)


def create_test_tasks():
    """Create multiple test tasks for parallel execution."""
    print("Creating test tasks for parallel execution...")

    # Initialize database if needed
    init_db()

    task_ids = []

    # Create 5 simple test tasks
    for i in range(1, 6):
        task_id = create_task(
            title=f"Parallel Test Task {i}",
            task_type="ecosystemiser",
            description=f"Test task {i} to verify parallel execution",
            payload={
                "operation": "health_check",
                "duration": 5  # Each task should take about 5 seconds
            },
            priority=i,
            current_phase="start"
        )
        task_ids.append(task_id)
        print(f"  Created task {i}: {task_id}")

    return task_ids


def monitor_task_progress(task_ids, duration=30):
    """Monitor task progress to verify parallel execution."""
    print("\nMonitoring task execution for parallel behavior...")
    print("If tasks are parallel, multiple should be 'in_progress' simultaneously.")
    print("-" * 60)

    start_time = time.time()
    max_concurrent = 0

    while time.time() - start_time < duration:
        conn = get_connection()
        cursor = conn.cursor()

        # Count tasks in each state
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'queued'")
        queued = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('assigned', 'in_progress')")
        in_progress = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        completed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'failed'")
        failed = cursor.fetchone()[0]

        # Track maximum concurrent tasks
        if in_progress > max_concurrent:
            max_concurrent = in_progress

        # Display status
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] Queued: {queued:2} | In Progress: {in_progress:2} | "
              f"Completed: {completed:2} | Failed: {failed:2} | Max Concurrent: {max_concurrent}")

        # Check if all tasks are done
        if queued == 0 and in_progress == 0:
            print("\nAll tasks completed!")
            break

        time.sleep(2)

    close_connection()

    # Analyze results
    print("\n" + "=" * 60)
    print("PARALLEL EXECUTION ANALYSIS:")
    print(f"  Maximum concurrent tasks observed: {max_concurrent}")

    if max_concurrent >= 3:
        print("  ✅ SUCCESS: Parallel execution confirmed! Multiple tasks ran simultaneously.")
    elif max_concurrent == 2:
        print("  ⚠️  PARTIAL: Some parallelism observed, but not at expected level.")
    else:
        print("  ❌ SERIAL: Tasks appear to be running sequentially (max concurrent = 1).")

    return max_concurrent


def main():
    """Main test execution."""
    print("=" * 60)
    print("HIVE V2.0 PARALLEL EXECUTION TEST")
    print("=" * 60)

    # Create test tasks
    task_ids = create_test_tasks()

    print("\nNOTE: You must run the Queen in another terminal for tasks to be processed:")
    print("  poetry run hive-queen")
    print("\nOr in Docker:")
    print("  docker run --rm -v C:/git/hive:/workspace -w /workspace hive-dev:latest poetry run hive-queen")

    # Monitor execution
    max_concurrent = monitor_task_progress(task_ids, duration=60)

    print("\n" + "=" * 60)
    print("TEST COMPLETE")

    if max_concurrent >= 3:
        print("Result: V2.0 PARALLEL EXECUTION VERIFIED ✅")
    else:
        print("Result: Parallel execution not confirmed. Check Queen configuration.")

    print("=" * 60)


if __name__ == "__main__":
    main()