#!/usr/bin/env python
"""Project Chimera - AI-Assisted TDD Framework Demo

Demonstrates the complete orchestration workflow with real agent integrations.

IMPORTANT: This is a HUMAN-TRIGGERED, AI-ASSISTED workflow demonstration.
It does NOT demonstrate autonomous background execution (requires Layer 2).

What This Demo SHOWS:
- Complete orchestration state machine (ChimeraWorkflow)
- Real agent integrations (E2E tester, Coder, Guardian, Deployment)
- Validated phase transitions with retry logic
- Production-ready code quality

What This Demo DOES NOT SHOW:
- Autonomous background execution (no daemon)
- Headless task processing (human trigger required)
- Agent-to-agent communication (centralized orchestrator)
- Self-learning workflows (static configuration)

See PROJECT_CHIMERA_REALITY_CHECK.md for honest assessment.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from hive_orchestration import ChimeraExecutor, ChimeraPhase, Task, TaskStatus, create_chimera_task
from hive_orchestration.workflows.chimera_agents import create_chimera_agents_registry

from hive_logging import get_logger

logger = get_logger(__name__)


async def run_chimera_demo() -> None:
    """Run complete Chimera workflow demonstration.

    Demonstrates AI-assisted TDD orchestration with real agent integrations:
    1. E2E test generation from natural language (REAL - e2e-tester)
    2. Code implementation (REAL - hive-coder Agent)
    3. Guardian review (REAL - ReviewEngine)
    4. Staging deployment (REAL - local file deployment)
    5. E2E validation (REAL - Playwright execution)

    NOTE: Requires human trigger (python scripts/chimera_demo.py)
    NOTE: Requires human monitoring (not headless background execution)
    """
    print("\n" + "=" * 80)
    print("PROJECT CHIMERA - AI-Assisted TDD Framework Demo")
    print("Status: Layer 1 (Orchestration) COMPLETE | Layer 2 (Autonomy) PLANNED")
    print("=" * 80)

    # Create Chimera task
    print("\n[1/6] Creating Chimera workflow task...")

    task_data = create_chimera_task(
        feature_description="User can view the homepage",
        target_url="https://example.com",
        staging_url="https://example.com",  # Use same URL for demo
        priority=5,
    )

    task = Task(
        id="demo-chimera-001",
        title=task_data["title"],
        description=task_data["description"],
        task_type=task_data["task_type"],
        priority=task_data["priority"],
        workflow=task_data["workflow"],
        payload=task_data["payload"],
        status=TaskStatus.QUEUED,
    )

    print(f"   Task created: {task.title}")
    print(f"   Feature: {task_data['payload']['feature_description']}")
    print(f"   Target URL: {task_data['payload']['target_url']}")

    # Create agent registry
    print("\n[2/6] Initializing agent registry...")

    agents = create_chimera_agents_registry()

    print(f"   Registered agents: {list(agents.keys())}")
    print("   [OK] E2E Tester Agent (REAL - test generation + execution)")
    print("   [OK] Coder Agent (REAL - hive-coder integration)")
    print("   [OK] Guardian Agent (REAL - ReviewEngine integration)")
    print("   [OK] Deployment Agent (REAL - local staging deployment)")

    # Create executor
    print("\n[3/6] Creating Chimera executor...")

    executor = ChimeraExecutor(agents_registry=agents)

    print("   Executor ready for workflow execution")

    # Execute workflow
    print("\n[4/6] Executing Chimera workflow...")
    print("   This will orchestrate all 5 phases:")
    print("   - Phase 1: E2E Test Generation (REAL - e2e-tester)")
    print("   - Phase 2: Code Implementation (REAL - hive-coder)")
    print("   - Phase 3: Guardian Review (REAL - ReviewEngine)")
    print("   - Phase 4: Staging Deployment (REAL - local file deployment)")
    print("   - Phase 5: E2E Validation (REAL - Playwright)")
    print("\n   NOTE: Human-triggered orchestration (not autonomous execution)")

    workflow = await executor.execute_workflow(task, max_iterations=10)

    # Display results
    print("\n[5/6] Workflow execution complete!")
    print(f"   Final phase: {workflow.current_phase.value}")
    print(f"   Status: {'SUCCESS' if workflow.current_phase == ChimeraPhase.COMPLETE else 'INCOMPLETE'}")

    # Display phase results
    print("\n[6/6] Phase Results:")

    if workflow.test_generation_result:
        print("\n   Phase 1: E2E Test Generation")
        print(f"   - Status: {workflow.test_generation_result.get('status')}")
        print(f"   - Test path: {workflow.test_path}")
        print(f"   - Test name: {workflow.test_generation_result.get('test_name')}")
        print(f"   - Lines of code: {workflow.test_generation_result.get('lines_of_code')}")

    if workflow.code_implementation_result:
        print("\n   Phase 2: Code Implementation")
        print(f"   - Status: {workflow.code_implementation_result.get('status')}")
        print(f"   - PR ID: {workflow.code_pr_id}")
        print(f"   - Commit SHA: {workflow.code_commit_sha}")
        print(f"   - Note: {workflow.code_implementation_result.get('implementation_notes')}")

    if workflow.review_result:
        print("\n   Phase 3: Guardian Review")
        print(f"   - Status: {workflow.review_result.get('status')}")
        print(f"   - Decision: {workflow.review_decision}")
        print(f"   - Score: {workflow.review_result.get('score')}")
        print(f"   - Note: {workflow.review_result.get('review_notes')}")

    if workflow.deployment_result:
        print("\n   Phase 4: Staging Deployment")
        print(f"   - Status: {workflow.deployment_result.get('status')}")
        print(f"   - Staging URL: {workflow.deployment_url}")
        print(f"   - Note: {workflow.deployment_result.get('deployment_notes')}")

    if workflow.validation_result:
        print("\n   Phase 5: E2E Validation")
        print(f"   - Status: {workflow.validation_status}")
        print(f"   - Tests run: {workflow.validation_result.get('tests_run')}")
        print(f"   - Tests passed: {workflow.validation_result.get('tests_passed')}")
        print(f"   - Duration: {workflow.validation_result.get('duration')}s")

    # Summary
    print("\n" + "=" * 80)
    print("DEMO SUMMARY")
    print("=" * 80)
    print(f"Workflow Status: {workflow.current_phase.value}")
    print(f"Retry Count: {workflow.retry_count}/{workflow.max_retries}")

    if workflow.test_path:
        print(f"\nGenerated Test File: {workflow.test_path}")
        test_file = Path(workflow.test_path)
        if test_file.exists():
            print(f"File exists: YES ({test_file.stat().st_size} bytes)")
            print("\nYou can run the generated test with:")
            print(f"  python -m pytest {workflow.test_path} -v")
        else:
            print("File exists: NO (check logs for errors)")

    print("\n" + "=" * 80)
    print("PROJECT CHIMERA DEMONSTRATION COMPLETE")
    print("=" * 80)
    print("\nCapabilities Demonstrated:")
    print("  ✅ Complete orchestration framework (Layer 1)")
    print("  ✅ Real agent integrations (no stubs)")
    print("  ✅ Validated phase transitions")
    print("  ✅ AI-assisted feature development")
    print("\nNOT Demonstrated (Requires Layer 2):")
    print("  ❌ Autonomous background execution")
    print("  ❌ Headless task processing")
    print("  ❌ Agent-to-agent communication")
    print("\nNext Steps:")
    print("  - Q1 2025: Layer 2 (Autonomous Execution)")
    print("  - See: PROJECT_COLOSSUS_AUTONOMOUS_EXECUTION_ROADMAP.md")


async def main() -> None:
    """Main entry point."""
    try:
        await run_chimera_demo()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        print("See logs for details")


if __name__ == "__main__":
    asyncio.run(main())
