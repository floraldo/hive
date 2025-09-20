#!/usr/bin/env python3
"""
Test Stateful Workflow System

This script tests the complete stateful orchestration system:
- Database schema with workflow definitions
- Queen as state machine driver
- Inspection and review process
- Phase transitions
"""

import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

# Add package paths
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-core-db" / "src"))
import hive_core_db


def setup_test_environment():
    """Initialize test environment"""
    print("\n" + "="*60)
    print("STATEFUL WORKFLOW SYSTEM TEST")
    print("="*60)

    # Initialize database
    print("\n[1] Initializing database...")
    hive_core_db.init_db()

    # Clean up any existing test tasks
    print("[2] Cleaning up old test tasks...")
    # Note: In production, we'd have a cleanup function
    # For now, we'll just proceed

    return True


def create_test_tasks():
    """Create test tasks with workflows"""
    print("\n[3] Creating test tasks with workflows...")

    test_tasks = []

    # Simple single-phase task
    print("    - Creating simple app task...")
    simple_task_id = hive_core_db.create_task(
        title="Test App Task - Health Check",
        task_type="app",
        description="Simple single-phase task",
        workflow={
            "start": {
                "command_template": "python -c \"print('Health check OK')\"",
                "next_phase_on_success": "completed",
                "next_phase_on_failure": "failed"
            }
        },
        current_phase="start"
    )
    test_tasks.append(("simple", simple_task_id))
    print(f"      Created: {simple_task_id}")

    # Complex multi-phase task with review
    print("    - Creating complex workflow task...")
    complex_task_id = hive_core_db.create_task(
        title="Test Workflow - Multi-Phase",
        task_type="backend",
        description="Complex task with apply->inspect->review->test flow",
        workflow={
            "start": {
                "next_phase_on_success": "apply"
            },
            "apply": {
                "command_template": "python -c \"print('Applying changes...'); open('test_output.txt', 'w').write('Hello World')\"",
                "next_phase_on_success": "inspect"
            },
            "inspect": {
                "command_template": "python -c \"import json; print(json.dumps({{'quality_score': 85, 'recommendation': 'approve'}}, indent=2))\"",
                "next_phase_on_success": "review_pending",
                "next_phase_on_failure": "review_pending"
            },
            "test": {
                "command_template": "python -c \"print('Running tests...'); import sys; sys.exit(0)\"",
                "next_phase_on_success": "completed",
                "next_phase_on_failure": "apply"
            }
        },
        payload={
            "test_data": "workflow test"
        },
        current_phase="start"
    )
    test_tasks.append(("complex", complex_task_id))
    print(f"      Created: {complex_task_id}")

    return test_tasks


def monitor_task_progress(task_id: str, timeout: int = 30) -> Dict[str, Any]:
    """Monitor a task's progress through its workflow"""
    print(f"\n[4] Monitoring task {task_id[:8]}...")

    start_time = time.time()
    phase_history = []

    while time.time() - start_time < timeout:
        task = hive_core_db.get_task(task_id)
        if not task:
            return {"error": "Task not found"}

        current_status = task.get("status")
        current_phase = task.get("current_phase")

        # Log phase change
        if not phase_history or phase_history[-1] != (current_status, current_phase):
            phase_history.append((current_status, current_phase))
            print(f"    Phase transition: status={current_status}, phase={current_phase}")

        # Check if task is complete
        if current_status in ["completed", "failed"]:
            return {
                "final_status": current_status,
                "final_phase": current_phase,
                "phase_history": phase_history,
                "duration": time.time() - start_time
            }

        time.sleep(1)

    return {
        "error": "Timeout",
        "last_status": current_status,
        "last_phase": current_phase,
        "phase_history": phase_history
    }


def run_queen_for_test(duration: int = 20):
    """Run Queen in background for testing"""
    print(f"\n[5] Starting Queen orchestrator (running for {duration}s)...")

    # Start Queen as subprocess
    queen_process = subprocess.Popen(
        ["python", "queen.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    print(f"    Queen started with PID: {queen_process.pid}")

    # Let it run for specified duration
    time.sleep(duration)

    # Terminate Queen
    print("    Stopping Queen...")
    queen_process.terminate()

    try:
        queen_process.wait(timeout=5)
        print("    Queen stopped successfully")
    except subprocess.TimeoutExpired:
        queen_process.kill()
        print("    Queen force killed")

    return True


def verify_workflow_execution(test_tasks):
    """Verify that tasks executed correctly"""
    print("\n[6] Verifying workflow execution...")

    results = {}

    for task_type, task_id in test_tasks:
        print(f"\n    Checking {task_type} task {task_id[:8]}...")

        task = hive_core_db.get_task(task_id)
        if not task:
            results[task_type] = "NOT_FOUND"
            continue

        status = task.get("status")
        phase = task.get("current_phase")

        print(f"      Status: {status}")
        print(f"      Phase: {phase}")

        # Check for expected outcomes
        if task_type == "simple":
            if status == "completed":
                results[task_type] = "PASS"
                print("      [OK] Simple task completed successfully")
            else:
                results[task_type] = "FAIL"
                print(f"      [FAIL] Simple task in unexpected state")

        elif task_type == "complex":
            # Complex task might still be in progress or review_pending
            if status in ["completed", "review_pending", "in_progress"]:
                results[task_type] = "PASS"
                print(f"      [OK] Complex task progressing through workflow")

                # Check if test file was created
                test_file = Path("test_output.txt")
                if test_file.exists():
                    print(f"      [OK] Output file created: {test_file}")
                    test_file.unlink()  # Clean up
            else:
                results[task_type] = "FAIL"
                print(f"      [FAIL] Complex task in unexpected state")

    return results


def main():
    """Main test execution"""
    try:
        # Setup
        if not setup_test_environment():
            print("[ERROR] Failed to setup environment")
            return 1

        # Create test tasks
        test_tasks = create_test_tasks()
        if not test_tasks:
            print("[ERROR] Failed to create test tasks")
            return 1

        # Run Queen
        if not run_queen_for_test(duration=15):
            print("[ERROR] Failed to run Queen")
            return 1

        # Verify execution
        results = verify_workflow_execution(test_tasks)

        # Summary
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)

        all_pass = True
        for task_type, result in results.items():
            symbol = "[OK]" if result == "PASS" else "[X]"
            print(f"{symbol} {task_type.capitalize()} task: {result}")
            if result != "PASS":
                all_pass = False

        print("\n" + "="*60)
        if all_pass:
            print("ALL TESTS PASSED!")
            print("Stateful workflow orchestration is working correctly")
        else:
            print("SOME TESTS FAILED")
            print("Review the output above for details")
        print("="*60)

        return 0 if all_pass else 1

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())