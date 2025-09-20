#!/usr/bin/env python3
"""
Monitor script for V2.0 Certification Test
Shows real-time status of the three test tasks
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-core-db" / "src"))
from hive_core_db.database import get_connection


def get_task_status():
    """Get current status of all tasks"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, status, current_phase, updated_at
        FROM tasks
        ORDER BY priority DESC
    """)

    return cursor.fetchall()


def print_status():
    """Print current test status"""
    tasks = get_task_status()

    print("\n" + "="*80)
    print(f"V2.0 CERTIFICATION TEST MONITOR - {datetime.now().strftime('%H:%M:%S')}")
    print("="*80)

    test_names = {
        "High-Quality": "Test 1: Autonomous Happy Path",
        "Borderline": "Test 2: Human Escalation",
        "Simple App": "Test 3: Simple App Path"
    }

    for task in tasks:
        task_id = task[0][:12]
        title = task[1]
        status = task[2]
        phase = task[3]

        # Determine test case
        test_case = "Unknown"
        for key, value in test_names.items():
            if key in title:
                test_case = value
                break

        # Color code status
        status_display = status.upper()
        if status == "completed":
            status_display = f"✅ {status_display}"
        elif status == "escalated":
            status_display = f"🚨 {status_display}"
        elif status == "review_pending":
            status_display = f"🔍 {status_display}"
        elif status == "in_progress":
            status_display = f"⚡ {status_display}"
        elif status == "queued":
            status_display = f"⏳ {status_display}"
        elif status in ["rejected", "failed"]:
            status_display = f"❌ {status_display}"
        elif status == "approved":
            status_display = f"✅ {status_display}"
        elif status == "rework_needed":
            status_display = f"🔧 {status_display}"

        print(f"\n{test_case}")
        print(f"  ID: {task_id}")
        print(f"  Status: {status_display}")
        print(f"  Phase: {phase}")

    # Check for critical states
    print("\n" + "-"*80)
    escalated = [t for t in tasks if t[2] == "escalated"]
    if escalated:
        print(f"⚠️  {len(escalated)} TASK(S) REQUIRE HUMAN REVIEW!")
        print("   Run: python src/hive_orchestrator/cli.py list-escalated")

    completed = [t for t in tasks if t[2] == "completed"]
    if len(completed) == 3:
        print("🎉 ALL TESTS COMPLETED!")
        return True

    return False


def main():
    """Main monitoring loop"""
    print("\nStarting V2.0 Certification Test Monitor...")
    print("Press Ctrl+C to stop monitoring\n")

    try:
        while True:
            print_status()

            # Check if all completed
            if print_status():
                print("\n" + "="*80)
                print("V2.0 PLATFORM CERTIFICATION COMPLETE!")
                print("="*80)
                break

            # Wait before next check
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


if __name__ == "__main__":
    main()