#!/usr/bin/env python3
"""Test transcript storage functionality."""

import sys
import time
from pathlib import Path

# Add package to path
sys.path.append(str(Path(__file__).parent.parent))

import hive_core_db
from datetime import datetime, timezone


def test_transcript_storage():
    """Test that transcripts are properly stored in the database."""
    print("\n" + "="*60)
    print("TRANSCRIPT STORAGE TEST")
    print("="*60)

    # Initialize database
    print("\n[1] Initializing database...")
    hive_core_db.init_db()

    # Create a test task
    print("[2] Creating test task...")
    created_task_id = hive_core_db.create_task(
        title="Test Transcript Storage",
        task_type="test",
        description="Testing if transcripts are stored properly"
    )
    print(f"    Created task_id: {created_task_id}")

    if not created_task_id:
        print("[X] Failed to create task!")
        return False

    task_id = created_task_id

    # Register a worker (required for foreign key constraint)
    print("[3] Registering test worker...")
    worker_id = "test-worker"
    hive_core_db.register_worker(
        worker_id=worker_id,
        role="test",
        capabilities=["testing"]
    )

    # Create a run for this task
    print("[4] Creating test run...")
    run_id = hive_core_db.create_run(
        task_id=task_id,
        worker_id=worker_id,
        phase="test"
    )
    print(f"    Created run_id: {run_id}")

    # Simulate a transcript
    sample_transcript = """
    [CLAUDE] Starting task execution...
    [CLAUDE] Analyzing the requirements...
    [CLAUDE] Writing code to solve the problem...
    def hello_world():
        print("Hello, World!")
    [CLAUDE] Code written successfully.
    [CLAUDE] Running tests...
    [CLAUDE] All tests passed!
    === EXIT CODE: 0 ===
    """

    print("[5] Storing transcript in database...")
    success = hive_core_db.log_run_result(
        run_id=run_id,
        status="success",
        result_data={"test": "data"},
        error_message=None,
        transcript=sample_transcript
    )

    if not success:
        print("[X] Failed to store transcript!")
        return False

    print("[6] Retrieving run with transcript...")
    run = hive_core_db.get_run(run_id)

    if not run:
        print("[X] Failed to retrieve run!")
        return False

    transcript = run.get('transcript')

    if not transcript:
        print("[X] Transcript not found in run record!")
        print(f"Run data keys: {list(run.keys())}")
        return False

    print("[7] Verifying transcript content...")
    if "Hello, World!" in transcript and "EXIT CODE: 0" in transcript:
        print("[OK] Transcript stored and retrieved successfully!")
        print("\n[Sample of stored transcript]")
        print("-"*40)
        print(transcript[:200] + "..." if len(transcript) > 200 else transcript)
        print("-"*40)
        return True
    else:
        print("[X] Transcript content doesn't match!")
        return False


if __name__ == "__main__":
    try:
        if test_transcript_storage():
            print("\n" + "="*60)
            print("[OK] TRANSCRIPT STORAGE TEST PASSED!")
            print("="*60)
            sys.exit(0)
        else:
            print("\n" + "="*60)
            print("[X] TRANSCRIPT STORAGE TEST FAILED!")
            print("="*60)
            sys.exit(1)
    except Exception as e:
        print(f"\n[X] Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)