#!/usr/bin/env python3
"""
Project Genesis - Task Monitor

Simple monitoring script for observing autonomous agent execution.
Queries the orchestration database to track task status and progress.
"""

import sqlite3
import time
from datetime import datetime
from pathlib import Path

# Database path
DB_PATH = Path.home() / ".hive" / "orchestration.db"

# Genesis task ID
GENESIS_TASK_ID = "d0725d00-c319-4a4b-87f5-9f5fe1110b6f"


def get_task_status():
    """Get current task status from database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, status, current_phase, assigned_worker,
               created_at, updated_at, priority
        FROM tasks
        WHERE id = ?
    """, (GENESIS_TASK_ID,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)


def display_status(task):
    """Display task status in a readable format."""
    print("\n" + "=" * 80)
    print(f"PROJECT GENESIS - STATUS CHECK [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print("=" * 80)

    if not task:
        print("ERROR: Genesis task not found!")
        return

    print(f"Task ID: {task['id'][:16]}...")
    print(f"Title: {task['title']}")
    print(f"Status: {task['status'].upper()}")
    print(f"Phase: {task['current_phase']}")
    print(f"Priority: {task['priority']}")
    print(f"Assigned Worker: {task['assigned_worker'] or 'UNASSIGNED (awaiting pickup)'}")
    print(f"Created: {task['created_at']}")
    print(f"Updated: {task['updated_at']}")

    # Status interpretation
    print("\nStatus Interpretation:")
    if task['status'] == 'queued':
        print("  - Task is AWAITING autonomous agent pickup")
        print("  - Next: Planner agent should analyze and decompose")
    elif task['status'] == 'assigned':
        print("  - Task has been ASSIGNED to an agent")
        print("  - Agent is preparing to begin execution")
    elif task['status'] == 'in_progress':
        print(f"  - Task is ACTIVELY RUNNING (phase: {task['current_phase']})")
        print("  - Autonomous development in progress")
    elif task['status'] == 'completed':
        print("  - Task has been COMPLETED successfully")
        print("  - Autonomous development validated!")
    elif task['status'] == 'failed':
        print("  - Task has FAILED")
        print("  - Review logs for error details")

    print("=" * 80)


def monitor_loop(interval=30):
    """Monitor task status in a loop."""
    print("\nStarting Project Genesis Monitor...")
    print(f"Refresh interval: {interval} seconds")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            task = get_task_status()
            display_status(task)

            if task and task['status'] in ['completed', 'failed', 'cancelled']:
                print("\n[!] Task reached terminal state - stopping monitor")
                break

            print(f"\n[*] Next update in {interval} seconds...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n[*] Monitor stopped by user")


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--watch':
        # Continuous monitoring mode
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        monitor_loop(interval)
    else:
        # Single status check
        task = get_task_status()
        display_status(task)
        print("\nTip: Use '--watch [interval]' for continuous monitoring")
        print("Example: python monitor_genesis.py --watch 30")


if __name__ == "__main__":
    main()
