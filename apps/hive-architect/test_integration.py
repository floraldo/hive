#!/usr/bin/env python3
"""
Integration test for Architect Agent - Manual execution test.

Tests the complete flow from natural language → execution plan
without requiring package installation.
"""

import sys
from pathlib import Path

# Add src to path for manual testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hive_architect.agent import ArchitectAgent


def test_architect_agent():
    """Test Architect Agent with 5 sample requirements"""

    # Sample requirements from Project Colossus plan
    test_requirements = [
        "Create a 'feedback-service' API that stores user feedback",
        "Build a 'notification-worker' that processes email notifications",
        "Generate a 'report-processor' batch job that runs daily analytics",
        "Create a 'user-service' REST API with authentication and profiles",
        "Build an 'event-handler' worker to process webhook events",
    ]

    print("=" * 70)
    print("ARCHITECT AGENT - Integration Test")
    print("Project Colossus - Milestone 1")
    print("=" * 70)

    agent = ArchitectAgent()
    results = []

    for i, requirement in enumerate(test_requirements, 1):
        print(f"\n[{i}/5] Testing: {requirement}")
        print("-" * 70)

        try:
            # Parse requirement
            parsed = agent.parse_requirement(requirement)
            print(f"  Service Name:  {parsed.service_name}")
            print(f"  Service Type:  {parsed.service_type.value}")
            print(f"  Database:      {parsed.enable_database}")
            print(f"  Features:      {len(parsed.features)}")
            print(f"  Confidence:    {parsed.confidence_score:.2f}")

            # Generate plan
            plan = agent.create_plan(requirement)
            print(f"  Tasks:         {len(plan.tasks)}")
            print(f"  Duration:      {plan.total_estimated_duration_minutes} min")

            # Validate plan
            validation = agent.validate_plan(plan)
            all_valid = all(validation.values())
            print(f"  Validation:    {'PASS' if all_valid else 'FAIL'}")

            results.append(
                {
                    "requirement": requirement,
                    "service_name": parsed.service_name,
                    "service_type": parsed.service_type.value,
                    "task_count": len(plan.tasks),
                    "duration_minutes": plan.total_estimated_duration_minutes,
                    "valid": all_valid,
                    "confidence": parsed.confidence_score,
                }
            )

            # Show task breakdown
            print("\n  Task Breakdown:")
            for task in plan.tasks[:3]:  # Show first 3 tasks
                print(f"    - {task.task_id}: {task.task_type.value} - {task.description}")
            if len(plan.tasks) > 3:
                print(f"    ... and {len(plan.tasks) - 3} more tasks")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append(
                {
                    "requirement": requirement,
                    "error": str(e),
                    "valid": False,
                }
            )

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    success_count = sum(1 for r in results if r.get("valid"))
    total_tasks = sum(r.get("task_count", 0) for r in results)
    total_duration = sum(r.get("duration_minutes", 0) for r in results)
    avg_confidence = sum(r.get("confidence", 0) for r in results) / len(results)

    print(f"\nSuccess Rate:       {success_count}/{len(results)} ({success_count/len(results)*100:.0f}%)")
    print(f"Total Tasks:        {total_tasks}")
    print(f"Total Duration:     {total_duration} minutes")
    print(f"Avg Duration:       {total_duration/len(results):.1f} min/service")
    print(f"Avg Confidence:     {avg_confidence:.2f}")

    print("\n" + "=" * 70)
    print("MILESTONE 1 STATUS")
    print("=" * 70)

    if success_count == len(results):
        print("\nSTATUS: COMPLETE")
        print("\nThe Architect Agent successfully:")
        print("  1. Parsed all natural language requirements")
        print("  2. Generated valid execution plans")
        print("  3. Met the 60-minute time budget per service")
        print("  4. Created comprehensive task breakdowns")
        print("\nREADY FOR: Milestone 2 - Coder Agent enhancement")
    else:
        print(f"\nSTATUS: PARTIAL ({success_count}/{len(results)} passed)")
        print("\nNeeds attention before proceeding to Milestone 2")

    return success_count == len(results)


if __name__ == "__main__":
    success = test_architect_agent()
    sys.exit(0 if success else 1)
