#!/usr/bin/env python3
"""
Project Genesis - Simplified Task Creation

Direct database approach to create PRJ-GENESIS-001 without complex imports.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

# Database path (standard Hive location)
DB_PATH = Path.home() / ".hive" / "orchestration.db"

# Task specification for PRJ-GENESIS-001
GENESIS_TASK = {
    "id": str(uuid.uuid4()),
    "title": "Enhance hive-cli tasks list command with --since filter",
    "task_type": "feature_development",
    "description": """Modify the hive-cli tasks list command to accept a --since option for filtering
tasks by their creation date. The option should accept relative timeframes like
2d (2 days), 1h (1 hour), etc.

This is PROJECT GENESIS - the autonomous development validation task.
This task tests the entire "God Mode" architecture including:
- Sequential Thinking MCP for advanced reasoning
- RAG knowledge archive with retrieval
- Event bus coordination
- Golden Rules architectural validation
- End-to-end autonomous development""",
    "priority": 5,
    "status": "queued",
    "current_phase": "start",
    "payload": json.dumps({
        "component": "hive-cli",
        "file_path": "packages/hive-cli/src/hive_cli/commands/tasks.py",
        "requirements": [
            "Add --since option to list_tasks command (click.option)",
            "Support relative time parsing: 2d (days), 1h (hours), 30m (minutes)",
            "Parse relative time to absolute timestamp",
            "Filter tasks WHERE created_at >= calculated_timestamp",
            "Maintain API-first design (JSON default, --pretty for human)",
            "Add unit tests for time parsing",
            "Add integration tests for filter functionality",
            "Update command docstring with examples",
        ],
        "acceptance_criteria": [
            "hive tasks list --since 2d returns tasks from last 2 days",
            "hive tasks list --since 1h --pretty shows human-readable table",
            "Invalid time format shows clear error message",
            "All existing tests continue to pass",
            "Golden Rules validation passes",
            "Code follows Boy Scout Rule (clean linting)",
        ],
        "technical_details": {
            "function": "list_tasks (line 53)",
            "add_option_after_line": 47,
            "time_parsing_library": "Built-in datetime/timedelta",
            "database_filter": "created_at >= timestamp",
            "test_file": "packages/hive-cli/tests/test_tasks_command.py",
        },
    }),
    "tags": json.dumps(["project-genesis", "autonomous-validation", "cli-enhancement"]),
}


def init_database():
    """Initialize the orchestration database with tasks table."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Create tasks table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            task_type TEXT NOT NULL,
            priority INTEGER DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'queued',
            current_phase TEXT NOT NULL DEFAULT 'start',
            workflow TEXT,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assigned_worker TEXT,
            due_date TIMESTAMP,
            max_retries INTEGER DEFAULT 3,
            tags TEXT,
            summary TEXT,
            generated_artifacts TEXT,
            related_document_ids TEXT,
            knowledge_fragments TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at: {DB_PATH}")


def create_task():
    """Create the genesis task in the database."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tasks (
            id, title, description, task_type, priority, status,
            current_phase, payload, max_retries, tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        GENESIS_TASK["id"],
        GENESIS_TASK["title"],
        GENESIS_TASK["description"],
        GENESIS_TASK["task_type"],
        GENESIS_TASK["priority"],
        GENESIS_TASK["status"],
        GENESIS_TASK["current_phase"],
        GENESIS_TASK["payload"],
        3,  # max_retries
        GENESIS_TASK["tags"],
    ))

    conn.commit()
    conn.close()

    print(f"Task created successfully: {GENESIS_TASK['id']}")
    return GENESIS_TASK["id"]


def display_task(task_id):
    """Retrieve and display the created task."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()

    if not row:
        print("ERROR: Task not found!")
        return

    task = dict(row)
    conn.close()

    print("")
    print("=" * 80)
    print("TASK DETAILS")
    print("=" * 80)
    print(f"ID: {task['id']}")
    print(f"Title: {task['title']}")
    print(f"Type: {task['task_type']}")
    print(f"Priority: {task['priority']}")
    print(f"Status: {task['status']}")
    print(f"Created: {task['created_at']}")
    print("")
    print("Payload:")
    payload = json.loads(task['payload'])
    print(json.dumps(payload, indent=2))
    print("=" * 80)


def main():
    """Execute Project Genesis task creation."""
    print("")
    print("=" * 80)
    print("PROJECT GENESIS - AUTONOMOUS VALIDATION")
    print("=" * 80)
    print("")

    # Step 1: Initialize database
    print("Step 1: Initializing orchestration database...")
    init_database()

    # Step 2: Create genesis task
    print("")
    print("Step 2: Creating PRJ-GENESIS-001 task...")
    task_id = create_task()

    # Step 3: Display task
    print("")
    print("Step 3: Retrieving task details...")
    display_task(task_id)

    # Step 4: Observer instructions
    print("")
    print("=" * 80)
    print("GENESIS TASK CREATED - ENTERING OBSERVER MODE")
    print("=" * 80)
    print("")
    print("The autonomous development validation task has been created.")
    print("The system is now ready for autonomous agent execution.")
    print("")
    print("Monitor task progress with:")
    print("  hive tasks list --pretty")
    print(f"  hive tasks show {task_id} --pretty")
    print("")
    print("Autonomous agents will:")
    print("  1. Planner: Decompose feature into subtasks")
    print("  2. Coder: Implement --since filter")
    print("  3. Tester: Create and validate tests")
    print("  4. Guardian: Validate architectural compliance")
    print("  5. Integration: Create PR and validate")
    print("")
    print("This is the final exam for 'God Mode' architecture.")
    print("Observe, validate, and analyze the autonomous development process.")
    print("")


if __name__ == "__main__":
    main()
