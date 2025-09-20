#!/usr/bin/env python3
"""
Test-Specific Database Seeding Script for Hive V2.0 Certification

Creates three specific test tasks to validate the complete autonomous workflow
including the new Human-AI escalation loop.

Test Cases:
1. High-Quality Task - Will pass AI review automatically
2. Borderline Task - Will trigger escalation for human review
3. Simple App Task - Direct execution without review
"""

import sys
import os
from pathlib import Path

# Add hive-core-db to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-core-db" / "src"))
import hive_core_db

# Add hive-logging to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-logging" / "src"))
from hive_logging import setup_logging, get_logger


def create_test_tasks():
    """Create three specific test tasks for V2.0 certification."""

    # Initialize logging
    setup_logging("test_seeder")
    logger = get_logger(__name__)

    # Initialize database
    hive_core_db.init_db()
    logger.info("Database initialized for test seeding")

    # Define our three test tasks
    test_tasks = [
        # Task 1: High-Quality Task (will pass AI review)
        {
            "title": "High-Quality: Add Function with Tests",
            "description": """Create a Python module with the following requirements:
1. Function 'add_numbers(a, b)' that adds two numbers
2. Comprehensive docstring with type hints
3. Input validation for numeric types
4. Complete test suite with edge cases
5. 100% test coverage
This should be implemented with production-quality code.""",
            "task_type": "backend",
            "priority": 5,
            "max_retries": 3,
            "tags": ["test", "high-quality", "python", "tdd"],
            "workflow": {
                "start": {
                    "next_phase_on_success": "apply"
                },
                "apply": {
                    "command_template": "python worker.py backend --task-id {task_id} --run-id {run_id} --phase apply --one-shot",
                    "next_phase_on_success": "inspect"
                },
                "inspect": {
                    "command_template": "python scripts/inspect_run.py --run-id {run_id}",
                    "next_phase_on_success": "review_pending",
                    "next_phase_on_failure": "review_pending"
                },
                "test": {
                    "command_template": "python worker.py backend --task-id {task_id} --run-id {run_id} --phase test --one-shot",
                    "next_phase_on_success": "completed",
                    "next_phase_on_failure": "apply"
                }
            },
            "payload": {
                "requirements": [
                    "Create calculator.py with add_numbers function",
                    "Use type hints: def add_numbers(a: float, b: float) -> float",
                    "Add comprehensive docstring",
                    "Validate inputs are numeric",
                    "Create test_calculator.py with pytest",
                    "Test normal cases, edge cases, and error cases",
                    "Achieve 100% test coverage"
                ],
                "expected_quality": "high",
                "framework": "Python with pytest"
            }
        },

        # Task 2: Borderline Task (will trigger escalation)
        {
            "title": "Borderline: Date Parser Function",
            "description": """Write a function that parses date strings from various formats.
Implementation should work but may have quality issues that make AI uncertain.""",
            "task_type": "backend",
            "priority": 3,
            "max_retries": 2,
            "tags": ["test", "borderline", "python", "parsing"],
            "workflow": {
                "start": {
                    "next_phase_on_success": "apply"
                },
                "apply": {
                    "command_template": "python worker.py backend --task-id {task_id} --run-id {run_id} --phase apply --one-shot",
                    "next_phase_on_success": "inspect"
                },
                "inspect": {
                    "command_template": "python scripts/inspect_run.py --run-id {run_id}",
                    "next_phase_on_success": "review_pending",
                    "next_phase_on_failure": "review_pending"
                },
                "test": {
                    "command_template": "python worker.py backend --task-id {task_id} --run-id {run_id} --phase test --one-shot",
                    "next_phase_on_success": "completed",
                    "next_phase_on_failure": "apply"
                }
            },
            "payload": {
                "requirements": [
                    "Create date_parser.py with parse_date function",
                    "Support formats: MM/DD/YYYY, DD-MM-YYYY, YYYY.MM.DD",
                    "Minimal error handling",
                    "Some test coverage but not comprehensive",
                    "Code should work but be messy"
                ],
                "expected_quality": "borderline",
                "notes": "Intentionally ambiguous requirements to trigger AI uncertainty",
                "framework": "Python"
            }
        },

        # Task 3: Simple App Task (direct execution, no review)
        {
            "title": "Simple App: EcoSystemiser Health Check",
            "description": "Execute the EcoSystemiser health check to verify app functionality",
            "task_type": "app",
            "priority": 1,
            "max_retries": 1,
            "tags": ["test", "app", "ecosystemiser", "health-check"],
            "assignee": "app:ecosystemiser:health-check",
            "workflow": {
                "start": {
                    "command_template": "echo 'EcoSystemiser Health Check: All systems operational' && echo '{\"status\": \"healthy\", \"timestamp\": \"2024-01-20T10:30:00Z\", \"components\": {\"climate_service\": \"ok\", \"solver\": \"ok\", \"database\": \"ok\"}}'",
                    "next_phase_on_success": "completed",
                    "next_phase_on_failure": "failed"
                }
            },
            "payload": {
                "app_name": "ecosystemiser",
                "task_name": "health-check",
                "expected_behavior": "Direct execution without review",
                "no_review_required": True
            }
        }
    ]

    # Create tasks in database
    created_tasks = []
    for idx, task_data in enumerate(test_tasks, 1):
        try:
            # Extract workflow
            workflow = task_data.get("workflow", None)

            task_id = hive_core_db.create_task(
                title=task_data["title"],
                task_type=task_data["task_type"],
                description=task_data["description"],
                workflow=workflow,
                payload=task_data.get("payload"),
                priority=task_data.get("priority", 1),
                max_retries=task_data.get("max_retries", 3),
                tags=task_data.get("tags", []),
                current_phase="start"
            )

            # Handle app tasks that need assignee field
            if "assignee" in task_data:
                success = hive_core_db.update_task_status(task_id, "queued", {
                    "assignee": task_data["assignee"]
                })
                if success:
                    logger.info(f"Set assignee for app task {task_id}: {task_data['assignee']}")

            created_tasks.append(task_id)
            logger.info(f"Created Test Task {idx}: {task_id} - {task_data['title']}")

            # Print expected behavior for each task
            if idx == 1:
                logger.info("  Expected: Will pass AI review with high score (>80)")
            elif idx == 2:
                logger.info("  Expected: Will escalate to human review (score 40-60)")
            elif idx == 3:
                logger.info("  Expected: Will execute directly without review")

        except Exception as e:
            logger.error(f"Failed to create task '{task_data['title']}': {e}")

    logger.info(f"\nTest seeding completed. Created {len(created_tasks)} test tasks.")
    return created_tasks


def clear_database():
    """Clear all existing tasks for a clean test environment."""
    logger = get_logger(__name__)

    try:
        from hive_core_db.database import get_connection, transaction

        conn = get_connection()
        cursor = conn.cursor()

        # Count existing records
        cursor.execute("SELECT COUNT(*) FROM tasks")
        task_count = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM runs")
        run_count = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM workers")
        worker_count = cursor.fetchone()[0] or 0

        if task_count > 0 or run_count > 0 or worker_count > 0:
            logger.info(f"Found existing data: {task_count} tasks, {run_count} runs, {worker_count} workers")

            # Clear all tables
            with transaction() as conn:
                conn.execute("DELETE FROM runs")
                conn.execute("DELETE FROM workers")
                conn.execute("DELETE FROM tasks")

            logger.info("Database cleared successfully")
        else:
            logger.info("Database already empty")

    except Exception as e:
        logger.error(f"Failed to clear database: {e}")


def main():
    """Main entry point for test seeding."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test-Specific Seeding for Hive V2.0 Certification"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear database before seeding"
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Only clear database, don't seed new tasks"
    )

    args = parser.parse_args()

    print("\n" + "="*70)
    print("HIVE V2.0 CERTIFICATION TEST SEEDING")
    print("="*70)

    # Clear database if requested
    if args.clear or not args.no_seed:
        print("\nClearing existing database...")
        clear_database()

    # Seed test tasks unless --no-seed specified
    if not args.no_seed:
        print("\nCreating test tasks...")
        created_tasks = create_test_tasks()

        print("\n" + "-"*70)
        print("TEST TASKS CREATED SUCCESSFULLY")
        print("-"*70)

        print("\nTest Task IDs:")
        for i, task_id in enumerate(created_tasks, 1):
            print(f"  Task {i}: {task_id}")

        print("\n[NEXT STEPS] Next Steps for V2.0 Certification:")
        print("\n1. Start the Queen orchestrator:")
        print("   poetry run hive-queen")
        print("\n2. Start the AI Reviewer daemon:")
        print("   cd apps/ai-reviewer && poetry run ai-reviewer-daemon")
        print("\n3. Start the Dashboard:")
        print("   poetry run hive-dashboard")
        print("\n4. Monitor the autonomous workflow and escalation system")

    print("\n" + "="*70)
    print("Ready for V2.0 Platform Certification Testing!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()