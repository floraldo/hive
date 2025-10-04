#!/usr/bin/env python3
"""Project Genesis - Task Creation Script

This script creates the first autonomous development validation task (PRJ-GENESIS-001)
in the hive-orchestration system. This task serves as the final exam for the entire
"God Mode" architecture, testing end-to-end autonomous development capabilities.

Mission: Validate that the Hive platform can autonomously complete a real-world
software development task from planning to implementation to validation.

Task: Enhance hive-cli tasks list command with --since filter
"""

import json
import sys
from pathlib import Path

# Add packages to Python path for import
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages" / "hive-orchestration" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "hive-logging" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "hive-db" / "src"))

from hive_orchestration import get_client
from hive_orchestration.database import init_db

from hive_logging import get_logger

logger = get_logger(__name__)

# Task specification for PRJ-GENESIS-001
GENESIS_TASK = {
    "title": "Enhance hive-cli tasks list command with --since filter",
    "task_type": "feature_development",
    "description": """
    Modify the hive-cli tasks list command to accept a --since option for filtering
    tasks by their creation date. The option should accept relative timeframes like
    2d (2 days), 1h (1 hour), etc.

    This is PROJECT GENESIS - the autonomous development validation task.
    This task tests the entire "God Mode" architecture including:
    - Sequential Thinking MCP for advanced reasoning
    - RAG knowledge archive with retrieval
    - Event bus coordination
    - Golden Rules architectural validation
    - End-to-end autonomous development
    """.strip(),
    "priority": 5,  # High priority
    "payload": {
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
    },
    "tags": ["project-genesis", "autonomous-validation", "cli-enhancement"],
}


def main():
    """Create the Project Genesis task and initialize autonomous development.

    Steps:
    1. Initialize orchestration database
    2. Create PRJ-GENESIS-001 task
    3. Display task details
    4. Provide observer instructions
    """
    logger.info("========================================")
    logger.info("PROJECT GENESIS - AUTONOMOUS VALIDATION")
    logger.info("========================================")

    # Step 1: Initialize database
    logger.info("Step 1: Initializing orchestration database...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return 1

    # Step 2: Create genesis task
    logger.info("Step 2: Creating PRJ-GENESIS-001 task...")
    try:
        client = get_client()
        task_id = client.create_task(
            title=GENESIS_TASK["title"],
            task_type=GENESIS_TASK["task_type"],
            description=GENESIS_TASK["description"],
            payload=GENESIS_TASK["payload"],
            priority=GENESIS_TASK["priority"],
            tags=GENESIS_TASK["tags"],
        )

        logger.info(f"Task created successfully: {task_id}")

    except Exception as e:
        logger.error(f"Task creation failed: {e}")
        return 1

    # Step 3: Retrieve and display task
    logger.info("Step 3: Retrieving task details...")
    try:
        task = client.get_task(task_id)

        if not task:
            logger.error("Failed to retrieve created task")
            return 1

        logger.info("Task Details:")
        logger.info("=" * 80)
        logger.info(f"ID: {task['id']}")
        logger.info(f"Title: {task['title']}")
        logger.info(f"Type: {task['task_type']}")
        logger.info(f"Priority: {task['priority']}")
        logger.info(f"Status: {task['status']}")
        logger.info(f"Created: {task['created_at']}")
        logger.info("")
        logger.info("Payload:")
        logger.info(json.dumps(task["payload"], indent=2))
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Task retrieval failed: {e}")
        return 1

    # Step 4: Observer instructions
    logger.info("")
    logger.info("========================================")
    logger.info("GENESIS TASK CREATED - ENTERING OBSERVER MODE")
    logger.info("========================================")
    logger.info("")
    logger.info("The autonomous development validation task has been created.")
    logger.info("The system is now ready for autonomous agent execution.")
    logger.info("")
    logger.info("Monitor task progress with:")
    logger.info("  hive tasks list --pretty")
    logger.info(f"  hive tasks show {task_id} --pretty")
    logger.info("")
    logger.info("Autonomous agents will:")
    logger.info("  1. Planner: Decompose feature into subtasks")
    logger.info("  2. Coder: Implement --since filter")
    logger.info("  3. Tester: Create and validate tests")
    logger.info("  4. Guardian: Validate architectural compliance")
    logger.info("  5. Integration: Create PR and validate")
    logger.info("")
    logger.info("This is the final exam for 'God Mode' architecture.")
    logger.info("Observe, validate, and analyze the autonomous development process.")
    logger.info("")

    return 0


if __name__ == "__main__":
    sys.exit(main())
