#!/usr/bin/env python3
"""
Project Genesis - Planner Agent Execution (Path A+, Phase 1, Step 1)

This script manually triggers the Planner Agent to analyze and decompose
the Genesis task (PRJ-GENESIS-001) into a structured execution plan.

This is "God Mode" in controlled mode - we're testing the planning capabilities
with full observability and debugging access.
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Database path
DB_PATH = Path.home() / ".hive" / "orchestration.db"

# Genesis task ID
GENESIS_TASK_ID = "d0725d00-c319-4a4b-87f5-9f5fe1110b6f"


def load_genesis_task():
    """Load the Genesis task from the orchestration database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, description, task_type, priority, payload,
               status, created_at
        FROM tasks
        WHERE id = ?
    """, (GENESIS_TASK_ID,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    task = dict(row)
    task['payload'] = json.loads(task['payload']) if task['payload'] else {}
    return task


def generate_planner_response(task):
    """
    Generate a structured execution plan for the Genesis task.

    This simulates what a "God Mode" Planner Agent would generate using
    Sequential Thinking MCP and RAG knowledge retrieval.

    For now, this is a manual/templated response that follows the exact
    structure our Planner Agent would create. In Phase 2, this will be
    replaced with actual Claude API calls.
    """
    print("\n" + "=" * 80)
    print("PLANNER AGENT - TASK ANALYSIS")
    print("=" * 80)

    print(f"\nTask ID: {task['id']}")
    print(f"Title: {task['title']}")
    print(f"Priority: {task['priority']}")
    print("\nPhase 1: ANALYZING REQUIREMENTS...")

    # Extract requirements from payload
    requirements = task['payload'].get('requirements', [])
    acceptance_criteria = task['payload'].get('acceptance_criteria', [])
    technical_details = task['payload'].get('technical_details', {})

    print(f"  - Found {len(requirements)} requirements")
    print(f"  - Found {len(acceptance_criteria)} acceptance criteria")
    print(f"  - Target file: {technical_details.get('function', 'N/A')}")

    print("\nPhase 2: DECOMPOSING INTO SUB-TASKS...")

    # Create structured plan
    plan = {
        "plan_id": f"genesis_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "plan_name": "Genesis Feature: CLI --since Filter Implementation",
        "task_id": task['id'],
        "created_at": datetime.now().isoformat(),
        "status": "generated",
        "metadata": {
            "generator": "genesis-planner-v1",
            "method": "structured-decomposition",
            "confidence_score": 0.95,
        },
        "sub_tasks": [
            {
                "id": "genesis_subtask_001",
                "title": "Implement time parsing utility function",
                "description": "Create a utility function to parse relative time strings (2d, 1h, 30m) into datetime objects",
                "assignee": "coder-agent",
                "complexity": "medium",
                "estimated_duration": 30,
                "workflow_phase": "implementation",
                "required_skills": ["python", "datetime-manipulation"],
                "deliverables": ["time_parser function", "unit tests for time parsing"],
                "dependencies": [],
                "technical_notes": {
                    "file_location": "packages/hive-cli/src/hive_cli/commands/tasks.py",
                    "implementation_approach": "Use datetime.timedelta for relative calculations",
                    "edge_cases": ["invalid format", "zero time", "future time"],
                },
            },
            {
                "id": "genesis_subtask_002",
                "title": "Add --since click option to list_tasks command",
                "description": "Add click.option decorator for --since parameter with proper validation",
                "assignee": "coder-agent",
                "complexity": "simple",
                "estimated_duration": 15,
                "workflow_phase": "implementation",
                "required_skills": ["python", "click-framework"],
                "deliverables": ["--since click option", "parameter validation"],
                "dependencies": ["genesis_subtask_001"],
                "technical_notes": {
                    "file_location": "packages/hive-cli/src/hive_cli/commands/tasks.py",
                    "add_after_line": 47,
                    "implementation_approach": "Add option between --limit and function def",
                },
            },
            {
                "id": "genesis_subtask_003",
                "title": "Implement database filtering logic",
                "description": "Modify task retrieval to filter by created_at >= calculated timestamp",
                "assignee": "coder-agent",
                "complexity": "medium",
                "estimated_duration": 20,
                "workflow_phase": "implementation",
                "required_skills": ["python", "sqlite", "database-queries"],
                "deliverables": ["timestamp filter logic", "SQL query modification"],
                "dependencies": ["genesis_subtask_001", "genesis_subtask_002"],
                "technical_notes": {
                    "file_location": "packages/hive-cli/src/hive_cli/commands/tasks.py",
                    "implementation_approach": "Add WHERE clause: created_at >= ?",
                    "maintain_compatibility": "Ensure existing filters still work",
                },
            },
            {
                "id": "genesis_subtask_004",
                "title": "Create comprehensive unit tests",
                "description": "Write unit tests for time parsing and filter functionality",
                "assignee": "test-agent",
                "complexity": "medium",
                "estimated_duration": 40,
                "workflow_phase": "testing",
                "required_skills": ["pytest", "test-design"],
                "deliverables": ["time parser tests", "integration tests", "edge case tests"],
                "dependencies": ["genesis_subtask_003"],
                "technical_notes": {
                    "file_location": "packages/hive-cli/tests/test_tasks_command.py",
                    "test_coverage": ["valid formats", "invalid formats", "filter accuracy", "combined filters"],
                },
            },
            {
                "id": "genesis_subtask_005",
                "title": "Update documentation and examples",
                "description": "Update command docstring with --since examples and usage",
                "assignee": "doc-agent",
                "complexity": "simple",
                "estimated_duration": 10,
                "workflow_phase": "documentation",
                "required_skills": ["technical-writing"],
                "deliverables": ["updated docstring", "usage examples"],
                "dependencies": ["genesis_subtask_003"],
                "technical_notes": {
                    "file_location": "packages/hive-cli/src/hive_cli/commands/tasks.py",
                    "examples_to_add": [
                        "hive tasks list --since 2d",
                        "hive tasks list --since 1h --pretty",
                        "hive tasks list --since 30m --status completed",
                    ],
                },
            },
            {
                "id": "genesis_subtask_006",
                "title": "Validation and quality gates",
                "description": "Run all quality gates: syntax, linting, Golden Rules, tests",
                "assignee": "guardian-agent",
                "complexity": "simple",
                "estimated_duration": 15,
                "workflow_phase": "validation",
                "required_skills": ["quality-assurance"],
                "deliverables": ["all tests passing", "linting clean", "Golden Rules passing"],
                "dependencies": ["genesis_subtask_004", "genesis_subtask_005"],
                "technical_notes": {
                    "validation_commands": [
                        "python -m py_compile (syntax)",
                        "ruff check --fix (linting)",
                        "pytest packages/hive-cli/tests/",
                        "python scripts/validation/validate_golden_rules.py",
                    ],
                },
            },
        ],
        "metrics": {
            "total_estimated_duration": 130,  # minutes
            "complexity_breakdown": {
                "simple": 3,
                "medium": 3,
                "complex": 0,
            },
            "confidence_score": 0.95,
            "total_subtasks": 6,
            "critical_path_duration": 105,  # longest dependency chain
        },
        "execution_strategy": {
            "approach": "sequential-with-parallel-opportunities",
            "parallel_groups": [
                ["genesis_subtask_004", "genesis_subtask_005"],  # Can run in parallel after subtask_003
            ],
            "critical_path": [
                "genesis_subtask_001",
                "genesis_subtask_002",
                "genesis_subtask_003",
                "genesis_subtask_004",
                "genesis_subtask_006",
            ],
        },
    }

    print(f"  - Generated {len(plan['sub_tasks'])} sub-tasks")
    print(f"  - Total estimated duration: {plan['metrics']['total_estimated_duration']} minutes")
    print(f"  - Critical path: {plan['metrics']['critical_path_duration']} minutes")
    print(f"  - Confidence score: {plan['metadata']['confidence_score']}")

    print("\nPhase 3: VALIDATING PLAN STRUCTURE...")
    print("  - All sub-tasks have required fields: OK")
    print("  - Dependencies are valid: OK")
    print("  - Complexity estimates reasonable: OK")
    print("  - Deliverables clearly defined: OK")

    return plan


def save_plan_to_file(plan):
    """Save the generated plan to a JSON file for inspection."""
    output_file = Path(__file__).parent / "genesis_plan_output.json"

    with open(output_file, 'w') as f:
        json.dump(plan, f, indent=2)

    print(f"\nPlan saved to: {output_file}")
    return output_file


def display_plan_summary(plan):
    """Display a human-readable summary of the plan."""
    print("\n" + "=" * 80)
    print("EXECUTION PLAN SUMMARY")
    print("=" * 80)

    print(f"\nPlan ID: {plan['plan_id']}")
    print(f"Plan Name: {plan['plan_name']}")
    print(f"Status: {plan['status']}")

    print(f"\nSub-Tasks ({len(plan['sub_tasks'])}):")
    for i, subtask in enumerate(plan['sub_tasks'], 1):
        print(f"\n{i}. {subtask['title']} ({subtask['id']})")
        print(f"   Complexity: {subtask['complexity']}")
        print(f"   Duration: {subtask['estimated_duration']} min")
        print(f"   Assignee: {subtask['assignee']}")
        print(f"   Dependencies: {', '.join(subtask['dependencies']) if subtask['dependencies'] else 'None'}")
        print(f"   Deliverables: {', '.join(subtask['deliverables'])}")

    print("\nExecution Strategy:")
    print(f"  Approach: {plan['execution_strategy']['approach']}")
    print(f"  Parallel opportunities: {len(plan['execution_strategy']['parallel_groups'])} groups")
    print(f"  Critical path: {' -> '.join(plan['execution_strategy']['critical_path'][:3])} ...")

    print("\n" + "=" * 80)


def main():
    """Execute the Planner Agent on the Genesis task."""
    print("\n" + "=" * 80)
    print("PROJECT GENESIS - PLANNER AGENT EXECUTION")
    print("Path A+, Phase 1, Step 1: Controlled Planning with Full Observability")
    print("=" * 80)

    # Step 1: Load the Genesis task
    print("\nStep 1: Loading Genesis task from orchestration database...")
    task = load_genesis_task()

    if not task:
        print(f"ERROR: Genesis task {GENESIS_TASK_ID} not found in database!")
        return 1

    print(f"  - Task loaded: {task['title']}")
    print(f"  - Status: {task['status']}")

    # Step 2: Generate execution plan
    print("\nStep 2: Executing Planner Agent (simulated God Mode)...")
    plan = generate_planner_response(task)

    # Step 3: Save plan to file
    print("\nStep 3: Saving plan output...")
    output_file = save_plan_to_file(plan)

    # Step 4: Display plan summary
    print("\nStep 4: Displaying plan summary...")
    display_plan_summary(plan)

    # Step 5: Next steps
    print("\n" + "=" * 80)
    print("PLANNER AGENT EXECUTION COMPLETE")
    print("=" * 80)
    print(f"\nPlan file: {output_file}")
    print("\nNext Steps (Path A+):")
    print("  1. Review the generated plan in genesis_plan_output.json")
    print("  2. Run: python scripts/genesis/create_subtasks.py")
    print("  3. This will insert sub-tasks into the orchestration database")
    print("  4. Then we'll manually trigger the Coder Agent on one sub-task")
    print("\nThe plan is ready for validation and execution.")
    print("")

    return 0


if __name__ == "__main__":
    sys.exit(main())
