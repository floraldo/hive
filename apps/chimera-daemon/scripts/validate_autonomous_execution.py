#!/usr/bin/env python
"""Validation Script - End-to-End Autonomous Execution Test.

This script validates Layer 2 (Autonomous Execution) by:
1. Starting Chimera daemon in background
2. Submitting task via REST API
3. Monitoring task execution (no human intervention)
4. Verifying autonomous completion

This is the KEY VALIDATION for Project Colossus Layer 2.
"""

from __future__ import annotations

import asyncio
import time

import httpx


async def validate_autonomous_execution() -> None:
    """Validate autonomous execution end-to-end."""
    print("\n" + "=" * 80)
    print("CHIMERA DAEMON - Layer 2 Autonomous Execution Validation")
    print("=" * 80)

    api_url = "http://localhost:8000"

    print("\n[1/5] Checking daemon status...")

    # Wait for daemon to be ready
    max_wait = 30
    for i in range(max_wait):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{api_url}/health")
                if response.status_code == 200:
                    print("   ✅ Daemon is running")
                    break
        except httpx.ConnectError:
            print(f"   Waiting for daemon... ({i+1}/{max_wait}s)")
            await asyncio.sleep(1)
    else:
        print("   ❌ Daemon not responding. Start with: chimera-daemon start-all")
        return

    print("\n[2/5] Submitting task via API...")

    # Submit task
    async with httpx.AsyncClient() as client:
        submit_response = await client.post(
            f"{api_url}/api/tasks",
            json={
                "feature": "User can view homepage",
                "target_url": "https://example.com",
                "staging_url": "https://example.com",
                "priority": 8,
            },
        )

        if submit_response.status_code != 200:
            print(f"   ❌ Failed to submit task: {submit_response.text}")
            return

        task_data = submit_response.json()
        task_id = task_data["task_id"]

        print(f"   ✅ Task submitted: {task_id}")
        print(f"   Status: {task_data['status']}")

    print("\n[3/5] Monitoring autonomous execution...")
    print("   NOTE: This requires NO human intervention")
    print("   Daemon is processing task in background...")

    # Monitor task status (autonomous execution)
    start_time = time.time()
    max_duration = 300  # 5 minutes max

    status = "queued"
    last_phase = None

    while time.time() - start_time < max_duration:
        async with httpx.AsyncClient() as client:
            status_response = await client.get(f"{api_url}/api/tasks/{task_id}")

            if status_response.status_code != 200:
                print(f"   ❌ Failed to get status: {status_response.text}")
                break

            task_status = status_response.json()
            current_status = task_status["status"]
            current_phase = task_status.get("phase")
            progress = task_status.get("progress")

            # Log phase changes
            if current_phase != last_phase:
                print(f"   Phase: {current_phase} ({progress})")
                last_phase = current_phase

            # Check if complete
            if current_status in ("completed", "failed"):
                status = current_status
                break

            await asyncio.sleep(2)  # Poll every 2 seconds

    elapsed = time.time() - start_time

    print(f"\n[4/5] Workflow execution finished ({elapsed:.1f}s)")

    # Get final result
    async with httpx.AsyncClient() as client:
        final_response = await client.get(f"{api_url}/api/tasks/{task_id}")
        final_data = final_response.json()

    print("\n[5/5] Final Result:")
    print(f"   Task ID: {task_id}")
    print(f"   Status: {final_data['status']}")
    print(f"   Phase: {final_data.get('phase')}")

    if final_data["status"] == "completed":
        print("\n   ✅ AUTONOMOUS EXECUTION SUCCESSFUL!")
        print("\n   Result:")
        result = final_data.get("result", {})
        for key, value in result.items():
            print(f"     {key}: {value}")

        duration = final_data.get("duration")
        if duration:
            print(f"\n   Duration: {duration:.1f}s")

    else:
        print("\n   ❌ WORKFLOW FAILED")
        error = final_data.get("error")
        if error:
            print(f"   Error: {error}")

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)

    if final_data["status"] == "completed":
        print("\n✅ Layer 2 (Autonomous Execution) VALIDATED")
        print("   - Task submitted via API")
        print("   - Daemon processed autonomously")
        print("   - NO human intervention required")
        print("   - Workflow completed successfully")
    else:
        print("\n⚠️  Layer 2 validation incomplete")
        print("   Check daemon logs for details")


async def main() -> None:
    """Main entry point."""
    print("\nIMPORTANT: Ensure daemon is running:")
    print("  Terminal 1: chimera-daemon start-all")
    print("  Terminal 2: python scripts/validate_autonomous_execution.py")

    input("\nPress Enter to start validation...")

    try:
        await validate_autonomous_execution()
    except KeyboardInterrupt:
        print("\n\nValidation interrupted")
    except Exception as e:
        print(f"\n\nValidation failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
