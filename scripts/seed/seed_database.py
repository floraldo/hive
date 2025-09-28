#!/usr/bin/env python3
"""
Database Seeding Script for Hive

Creates clean, sample tasks directly in the database following the "Fresh Start" approach.
This replaces the old JSON-based task files with database-native task creation.
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


def setup_sample_tasks():
    """Create sample tasks for testing the Hive system with stateful workflows."""

    # Initialize logging
    setup_logging("hive_seeder")
    logger = get_logger(__name__)

    # Initialize database
    hive_core_db.init_db()
    logger.info("Database initialized")

    # Sample tasks with workflow definitions
    sample_tasks = [
        # Complex multi-step task with review
        {
            "title": "Create Simple Hello World Script",
            "description": "Create a Python script that prints Hello World with proper structure",
            "task_type": "backend",
            "priority": 3,
            "max_retries": 3,
            "tags": ["python", "simple", "test"],
            "workflow": {
                "start": {"next_phase_on_success": "apply"},
                "apply": {
                    "command_template": "python worker.py backend --task-id {task_id} --run-id {run_id} --phase apply --one-shot",
                    "next_phase_on_success": "inspect",
                },
                "inspect": {
                    "command_template": "python scripts/inspect_run.py --run-id {run_id}",
                    "next_phase_on_success": "review_pending",
                    "next_phase_on_failure": "review_pending",
                },
                "test": {
                    "command_template": "python worker.py backend --task-id {task_id} --run-id {run_id} --phase test --one-shot",
                    "next_phase_on_success": "completed",
                    "next_phase_on_failure": "apply",
                },
            },
            "payload": {
                "requirements": ["Create hello.py", "Include main guard", "Add docstring"],
                "output": "Hello, World!",
                "framework": "Python",
            },
        },
        # Simple app task (single-step, no review needed)
        {
            "title": "Generate EcoSystemiser Health Check",
            "description": "Run the EcoSystemiser health check task to verify app functionality",
            "task_type": "app",
            "priority": 1,
            "max_retries": 2,
            "tags": ["ecosystemiser", "health-check", "app"],
            "assignee": "app:ecosystemiser:health-check",
            "workflow": {
                "start": {
                    "command_template": "python -c \"print('EcoSystemiser health check: OK')\"",
                    "next_phase_on_success": "completed",
                    "next_phase_on_failure": "failed",
                }
            },
            "payload": {"app_name": "ecosystemiser", "task_name": "health-check"},
        },
        # Standard worker task with full workflow
        {
            "title": "Implement User Authentication API",
            "description": "Create JWT-based authentication with proper testing",
            "task_type": "backend",
            "priority": 2,
            "max_retries": 2,
            "tags": ["api", "auth", "backend"],
            "workflow": {
                "start": {"next_phase_on_success": "apply"},
                "apply": {
                    "command_template": "python worker.py backend --task-id {task_id} --run-id {run_id} --phase apply --one-shot",
                    "next_phase_on_success": "inspect",
                },
                "inspect": {
                    "command_template": "python scripts/inspect_run.py --run-id {run_id}",
                    "next_phase_on_success": "review_pending",
                    "next_phase_on_failure": "review_pending",
                },
                "test": {
                    "command_template": "python worker.py backend --task-id {task_id} --run-id {run_id} --phase test --one-shot",
                    "next_phase_on_success": "completed",
                    "next_phase_on_failure": "apply",
                },
            },
            "payload": {
                "requirements": ["JWT implementation", "Login endpoint", "Logout endpoint"],
                "framework": "Flask",
            },
        },
        # Real EcoSystemiser climate data fetching task
        {
            "title": "Fetch London Climate Data - July 2023",
            "description": "Fetch real climate data for London using EcoSystemiser's climate service",
            "task_type": "app",
            "priority": 1,
            "max_retries": 1,
            "tags": ["climate", "ecosystemiser", "data", "london"],
            "assignee": "app:ecosystemiser:fetch-climate-data",
            "workflow": {
                "start": {
                    "command_template": 'python apps/ecosystemiser/hive_adapter.py --task fetch-climate-data --payload \'{{"location": "{location}", "start_date": "{start_date}", "end_date": "{end_date}", "source": "{source}", "variables": {variables}}}\'',
                    "next_phase_on_success": "completed",
                    "next_phase_on_failure": "failed",
                }
            },
            "payload": {
                "location": "51.5074,-0.1278",  # London coordinates
                "start_date": "2023-07-01",
                "end_date": "2023-07-07",
                "source": "nasa_power",
                "variables": ["temp_air", "ghi", "dni", "wind_speed", "rel_humidity"],
                "description": "Fetching real weather data for London from NASA POWER database",
            },
        },
    ]

    # Create tasks in database
    created_tasks = []
    for task_data in sample_tasks:
        try:
            # Extract workflow if present
            workflow = task_data.get("workflow", None)

            task_id = hive_core_db.create_task(
                title=task_data["title"],
                task_type=task_data["task_type"],
                description=task_data["description"],
                workflow=workflow,  # Pass workflow definition
                payload=task_data.get("payload"),
                priority=task_data.get("priority", 1),
                max_retries=task_data.get("max_retries", 3),
                tags=task_data.get("tags", []),
                current_phase="start",  # All tasks start in 'start' phase
            )

            # Handle app tasks that need assignee field set
            if "assignee" in task_data:
                success = hive_core_db.update_task_status(task_id, "queued", {"assignee": task_data["assignee"]})
                if success:
                    logger.info(f"Set assignee for app task {task_id}: {task_data['assignee']}")
                else:
                    logger.warning(f"Failed to set assignee for task {task_id}")

            created_tasks.append(task_id)
            logger.info(f"Created task: {task_id} - {task_data['title']}")
        except Exception as e:
            logger.error(f"Failed to create task '{task_data['title']}': {e}")

    logger.info(f"Database seeding completed. Created {len(created_tasks)} tasks.")
    return created_tasks


def clear_all_tasks():
    """Clear all tasks from the database for fresh start."""
    logger = get_logger(__name__)

    try:
        # Use direct database connection to clear tasks
        from hive_db import get_sqlite_connection, sqlite_transaction
        from hive_config.paths import DB_PATH

        with sqlite_transaction(DB_PATH) as conn:
            cursor = conn.cursor()
            # Delete runs first (foreign key constraint)
            cursor.execute("DELETE FROM runs")
            # Then delete tasks
            cursor.execute("DELETE FROM tasks")
            conn.commit()
            logger.info("Successfully cleared all tasks from the database")
    except Exception as e:
        logger.error(f"Failed to clear tasks: {e}")


def main():
    """Main seeding script entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Hive Database Seeding Script")
    parser.add_argument("--clear", action="store_true", help="Clear all existing tasks first")
    parser.add_argument("--sample", action="store_true", help="Create sample tasks")

    args = parser.parse_args()

    if not args.clear and not args.sample:
        parser.print_help()
        return

    if args.clear:
        print("Clearing existing tasks...")
        clear_all_tasks()

    if args.sample:
        print("Creating sample tasks...")
        created_tasks = setup_sample_tasks()
        print(f"Successfully created {len(created_tasks)} sample tasks")
        for task_id in created_tasks:
            print(f"  - {task_id}")


if __name__ == "__main__":
    main()
