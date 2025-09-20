#!/usr/bin/env python3
"""
Seed database with test tasks for parallel execution verification.
Creates multiple simple tasks that should execute concurrently.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-core-db" / "src"))

from hive_core_db import (
    init_db,
    create_task,
    close_connection
)
from hive_core_db.database import get_connection


def clean_database():
    """Clean existing tasks from database."""
    print("Cleaning database...")
    conn = get_connection()
    cursor = conn.cursor()

    # Clear all tables
    cursor.execute("DELETE FROM runs")
    cursor.execute("DELETE FROM workers")
    cursor.execute("DELETE FROM tasks")

    conn.commit()
    print("Database cleaned.")


def seed_parallel_tasks():
    """Seed database with tasks for parallel testing."""
    print("\n" + "="*60)
    print("SEEDING DATABASE FOR PARALLEL EXECUTION TEST")
    print("="*60)

    # Initialize database
    init_db()

    # Clean existing data
    clean_database()

    # Create 5 EcoSystemiser health check tasks
    task_ids = []
    print("\nCreating EcoSystemiser health check tasks...")
    for i in range(1, 6):
        task_id = create_task(
            title=f"EcoSystemiser Health Check {i}",
            task_type="ecosystemiser",
            description=f"Quick health check task {i} for parallel execution test",
            payload={
                "operation": "health_check",
                "test_id": i,
                "expected_duration": 5
            },
            priority=5 - i,  # Higher priority for first tasks
            current_phase="start"
        )
        task_ids.append(task_id)
        print(f"  [OK] Created task {i}: {task_id[:8]}...")

    # Create 2 backend API tasks
    print("\nCreating Backend API tasks...")
    for i in range(1, 3):
        task_id = create_task(
            title=f"Backend API Task {i}",
            task_type="backend",
            description=f"Simple API endpoint task {i}",
            payload={
                "operation": "create_endpoint",
                "endpoint": f"/api/test{i}",
                "method": "GET"
            },
            priority=3,
            current_phase="start"
        )
        task_ids.append(task_id)
        print(f"  [OK] Created backend task {i}: {task_id[:8]}...")

    # Create 2 frontend UI tasks
    print("\nCreating Frontend UI tasks...")
    for i in range(1, 3):
        task_id = create_task(
            title=f"Frontend UI Task {i}",
            task_type="frontend",
            description=f"Simple UI component task {i}",
            payload={
                "operation": "create_component",
                "component": f"TestComponent{i}",
                "type": "functional"
            },
            priority=2,
            current_phase="start"
        )
        task_ids.append(task_id)
        print(f"  [OK] Created frontend task {i}: {task_id[:8]}...")

    # Verify tasks were created
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]

    print("\n" + "="*60)
    print(f"SEEDING COMPLETE")
    print(f"Total tasks created: {total_tasks}")
    print("="*60)

    print("\nExpected behavior when Queen runs:")
    print("  1. Multiple tasks should transition to 'in_progress' simultaneously")
    print("  2. Dashboard should show 3+ active workers at once")
    print("  3. Tasks should complete in parallel, not sequentially")

    print("\nTo test:")
    print("  Terminal 1: poetry run hive-dashboard")
    print("  Terminal 2: poetry run hive-queen")

    close_connection()
    return task_ids


if __name__ == "__main__":
    task_ids = seed_parallel_tasks()