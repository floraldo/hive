#!/usr/bin/env python3
"""
V2.0 Certification Test Monitor

Monitors the autonomous execution of test tasks and validates expected transitions.
"""

import sys
import time
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-utils" / "src"))

from hive_utils.paths import DB_PATH

# Test task IDs from seed script
TEST_TASK_IDS = {
    "high_quality": "9569c482-01bc-4a7e-b986-829bb7df02e2",
    "borderline": "d16d82b0-6bc0-4333-b6bb-2b398d9e8186",
    "simple_app": "a25a1791-31e4-46df-8002-07b736578826"
}

# Expected final states
EXPECTED_FINAL_STATES = {
    "high_quality": "completed",
    "borderline": "escalated",
    "simple_app": "completed"
}

# Track state transitions
transitions: Dict[str, List[Tuple[str, str]]] = {
    "high_quality": [],
    "borderline": [],
    "simple_app": []
}


def get_task_states() -> Dict[str, Dict]:
    """Get current state of all test tasks"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    states = {}
    for name, task_id in TEST_TASK_IDS.items():
        cursor.execute("""
            SELECT id, title, status, current_phase, assignee
            FROM tasks WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()
        if row:
            states[name] = dict(row)
        else:
            states[name] = {"status": "NOT_FOUND"}

    conn.close()
    return states


def print_status(states: Dict[str, Dict], elapsed: int):
    """Print current status of all tasks"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Elapsed: {elapsed}s")
    print("-" * 70)

    for name in TEST_TASK_IDS.keys():
        state = states.get(name, {})
        status = state.get("status", "UNKNOWN")
        phase = state.get("current_phase", "")
        assignee = state.get("assignee", "")

        # Get last transition
        last_transition = ""
        if transitions[name]:
            last_transition = f" [{transitions[name][-1][0]} -> {transitions[name][-1][1]}]"

        print(f"  {name.ljust(15)}: {status.ljust(20)} Phase: {phase or 'N/A'.ljust(10)} {last_transition}")


def track_transitions(prev_states: Dict, curr_states: Dict):
    """Track state transitions"""
    for name in TEST_TASK_IDS.keys():
        prev = prev_states.get(name, {})
        curr = curr_states.get(name, {})

        prev_status = prev.get("status", "")
        curr_status = curr.get("status", "")

        if prev_status != curr_status and curr_status:
            transitions[name].append((prev_status or "initial", curr_status))
            print(f"\n  🔄 {name}: {prev_status or 'initial'} -> {curr_status}")


def verify_final_states(states: Dict) -> Tuple[bool, List[str]]:
    """Verify if all tasks reached expected final states"""
    all_complete = True
    errors = []

    for name, expected_state in EXPECTED_FINAL_STATES.items():
        actual_state = states.get(name, {}).get("status", "UNKNOWN")

        # Check if task has reached a terminal state
        if actual_state in ["completed", "failed", "escalated", "rejected"]:
            if actual_state != expected_state:
                errors.append(f"{name}: Expected '{expected_state}', got '{actual_state}'")
                all_complete = False
        else:
            # Not yet in terminal state
            all_complete = False

    return all_complete, errors


def verify_no_review_for_app(name: str = "simple_app") -> bool:
    """Verify that simple app task never entered review_pending state"""
    for prev_status, curr_status in transitions[name]:
        if curr_status == "review_pending":
            return False
    return True


def main():
    """Monitor the certification test"""
    print("=" * 70)
    print("V2.0 CERTIFICATION TEST MONITOR")
    print("=" * 70)
    print("\nMonitoring test tasks...")
    print(f"  High-Quality Task: {TEST_TASK_IDS['high_quality']}")
    print(f"  Borderline Task:   {TEST_TASK_IDS['borderline']}")
    print(f"  Simple App Task:   {TEST_TASK_IDS['simple_app']}")
    print("\nExpected outcomes:")
    print("  High-Quality: queued -> in_progress -> review_pending -> completed")
    print("  Borderline:   queued -> in_progress -> review_pending -> escalated")
    print("  Simple App:   queued -> in_progress -> completed (no review)")
    print("=" * 70)

    start_time = time.time()
    timeout = 300  # 5 minutes
    poll_interval = 3  # seconds

    prev_states = {}

    while True:
        elapsed = int(time.time() - start_time)

        # Get current states
        curr_states = get_task_states()

        # Track transitions
        if prev_states:
            track_transitions(prev_states, curr_states)

        # Print status
        print_status(curr_states, elapsed)

        # Check if all tasks reached final states
        complete, errors = verify_final_states(curr_states)

        if complete:
            print("\n" + "=" * 70)
            print("ALL TASKS REACHED TERMINAL STATES")
            print("=" * 70)

            # Verify expectations
            success = True

            # Check for errors in final states
            if errors:
                print("\n❌ FAILURES:")
                for error in errors:
                    print(f"  - {error}")
                success = False

            # Verify simple app never went to review
            if not verify_no_review_for_app():
                print("\n❌ FAILURE: Simple app task entered review_pending (should bypass review)")
                success = False

            # Print transitions summary
            print("\n📊 TRANSITION SUMMARY:")
            for name in TEST_TASK_IDS.keys():
                print(f"\n  {name}:")
                for prev, curr in transitions[name]:
                    print(f"    {prev} -> {curr}")

            # Final result
            print("\n" + "=" * 70)
            if success:
                print("✅ CERTIFICATION TEST PASSED!")
                print("All tasks completed with expected outcomes.")
            else:
                print("❌ CERTIFICATION TEST FAILED")
                print("Some tasks did not reach expected states.")
            print("=" * 70)

            return 0 if success else 1

        # Check timeout
        if elapsed > timeout:
            print("\n" + "=" * 70)
            print("⏱️  TIMEOUT - Test did not complete within 5 minutes")
            print("=" * 70)
            print("\nFinal states:")
            for name in TEST_TASK_IDS.keys():
                state = curr_states.get(name, {})
                print(f"  {name}: {state.get('status', 'UNKNOWN')}")
            return 2

        prev_states = curr_states
        time.sleep(poll_interval)


if __name__ == "__main__":
    sys.exit(main())