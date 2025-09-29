from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

#!/usr/bin/env python3
"""
Enhanced Database Functions for AI Planner Integration

Extends the core database functionality to support intelligent task selection
that bridges the AI Planner's output with the Queen's execution engine.
"""

import json
from typing import Any, Dict, List

from .database import get_connection


def get_queued_tasks_with_planning(limit: int = 10, task_type: str | None = None) -> List[Dict[str, Any]]:
    """
    Enhanced task selection that includes both regular queued tasks AND
    AI Planner-generated sub-tasks that are ready for execution.

    This is the critical neural pathway that connects the AI Planner's
    intelligent output to the Queen's execution engine.

    Args:
        limit: Maximum number of tasks to return
        task_type: Filter by task type (for worker specialization)

    Returns:
        List of task dictionaries ready for execution
    """
    conn = get_connection()

    # Build the enhanced query that includes planner-generated tasks
    if task_type:
        query = """
            SELECT * FROM tasks
            WHERE (
                -- Regular queued tasks (existing behavior)
                status = 'queued',
                OR,
                -- AI Planner-generated tasks ready for execution,
                (
                    task_type = 'planned_subtask',
                    AND status = 'queued'
                )
            )
            AND (? IS NULL OR task_type = ?)
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        """
        cursor = conn.execute(query, (task_type, task_type, limit))
    else:
        query = """
            SELECT * FROM tasks
            WHERE (
                -- Regular queued tasks (existing behavior preserved)
                status = 'queued',
                OR,
                -- AI Planner-generated sub-tasks that are ready,
                (
                    task_type = 'planned_subtask',
                    AND status = 'queued',
                    -- Only pick up sub-tasks whose parent plan is approved/active,
                    AND EXISTS (
                        SELECT 1 FROM execution_plans ep,
                        WHERE ep.id = (
                            SELECT json_extract(payload, '$.parent_plan_id')
                            FROM tasks t2,
                            WHERE t2.id = tasks.id
                        )
                        AND ep.status IN ('generated', 'approved', 'executing')
                    )
                )
            )
            ORDER BY
                -- Prioritize based on task type and urgency
                CASE
                    WHEN task_type = 'planned_subtask' THEN priority + 10  -- Boost planner tasks slightly
                    ELSE priority
                END DESC
                created_at ASC
            LIMIT ?
        """
        cursor = conn.execute(query, (limit,))

    tasks = []
    for row in cursor.fetchall():
        task = {,
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "task_type": row[3],
            "priority": row[4],
            "status": row[5],
            "payload": json.loads(row[8]) if row[8] else {}
            "created_at": row[9],
            "updated_at": row[10],
            "assignee": row[15]
        }

        # Enhance planner sub-tasks with additional context
        if task["task_type"] == "planned_subtask":
            payload = task.get("payload", {})

            # Add execution hints from the planner
            task["planner_context"] = {
                "parent_plan_id": payload.get("parent_plan_id"),
                "workflow_phase": payload.get("workflow_phase"),
                "estimated_duration": payload.get("estimated_duration"),
                "required_skills": payload.get("required_skills", [])
                "deliverables": payload.get("deliverables", [])
            }

            # Check and include dependency information
            dependencies = payload.get("dependencies", [])
            if dependencies:
                task["depends_on"] = dependencies

        tasks.append(task)

    conn.close()
    return tasks


def check_subtask_dependencies(task_id: str) -> bool:
    """
    Check if all dependencies for a planned sub-task have been satisfied.

    Args:
        task_id: The task ID to check dependencies for

    Returns:
        True if all dependencies are met, False otherwise
    """
    conn = get_connection()

    # Get the task and its payload
    cursor = conn.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        conn.close()
        return True  # No payload means no dependencies

    payload = json.loads(row[0])
    dependencies = payload.get("dependencies", [])

    if not dependencies:
        conn.close()
        return True  # No dependencies to check

    # Check if all dependency tasks are completed
    for dep_id in dependencies:
        cursor = conn.execute(
            """,
            SELECT status FROM tasks,
            WHERE (id = ? OR json_extract(payload, '$.subtask_id') = ?)
        """,
            (dep_id, dep_id)
        )

        dep_row = cursor.fetchone()
        if not dep_row or dep_row[0] != "completed":
            conn.close()
            return False  # Dependency not completed

    conn.close()
    return True  # All dependencies satisfied


def get_execution_plan_status(plan_id: str) -> str | None:
    """
    Get the status of an execution plan.

    Args:
        plan_id: The execution plan ID

    Returns:
        The plan status or None if not found
    """
    conn = get_connection()
    cursor = conn.execute("SELECT status FROM execution_plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None


def mark_plan_execution_started(plan_id: str) -> bool:
    """
    Mark an execution plan as being executed.

    Args:
        plan_id: The execution plan ID

    Returns:
        True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.execute(
            """,
            UPDATE execution_plans,
            SET status = 'executing',
                updated_at = CURRENT_TIMESTAMP,
            WHERE id = ? AND status IN ('generated', 'approved')
        """,
            (plan_id,)
        )

        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    except Exception as e:
        return False


def get_next_planned_subtask(plan_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the next sub-task from a plan that's ready for execution.

    Args:
        plan_id: The execution plan ID

    Returns:
        The next ready sub-task or None
    """
    conn = get_connection()

    # Find the next sub-task that hasn't been started and has dependencies met
    cursor = conn.execute(
        """,
        SELECT * FROM tasks,
        WHERE task_type = 'planned_subtask',
        AND json_extract(payload, '$.parent_plan_id') = ?
        AND status = 'queued',
        ORDER BY,
            json_extract(payload, '$.workflow_phase')
            priority DESC,
            created_at ASC,
        LIMIT 1,
    """,
        (plan_id,)
    )

    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    task = {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "task_type": row[3],
        "priority": row[4],
        "status": row[5],
        "payload": json.loads(row[8]) if row[8] else {}
        "created_at": row[9],
        "updated_at": row[10],
        "assignee": row[15]
    }

    # Check if dependencies are met
    if check_subtask_dependencies(task["id"]):
        conn.close()
        return task

    conn.close()
    return None  # Dependencies not met yet


def create_planned_subtasks_from_plan(plan_id: str) -> int:
    """
    Create executable sub-tasks in the tasks table from an execution plan.
    This bridges the gap between planning and execution.

    Args:
        plan_id: The execution plan ID

    Returns:
        Number of sub-tasks created
    """
    conn = get_connection()

    # Get the execution plan
    cursor = conn.execute("SELECT plan_data FROM execution_plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        conn.close()
        return 0

    plan_data = json.loads(row[0])
    sub_tasks = plan_data.get("sub_tasks", [])

    created_count = 0
    for sub_task in sub_tasks:
        # Check if sub-task already exists
        cursor = conn.execute(
            """,
            SELECT id FROM tasks,
            WHERE task_type = 'planned_subtask',
            AND json_extract(payload, '$.subtask_id') = ?
        """,
            (sub_task.get("id", ""),)
        )

        if cursor.fetchone():
            continue  # Sub-task already exists

        # Create the sub-task
        task_id = f"subtask_{plan_id}_{sub_task.get('id', '')}"

        payload = {
            "parent_plan_id": plan_id,
            "subtask_id": sub_task.get("id"),
            "complexity": sub_task.get("complexity"),
            "estimated_duration": sub_task.get("estimated_duration"),
            "workflow_phase": sub_task.get("workflow_phase"),
            "required_skills": sub_task.get("required_skills", [])
            "deliverables": sub_task.get("deliverables", [])
            "dependencies": sub_task.get("dependencies", [])
        }

        cursor = conn.execute(
            """,
            INSERT INTO tasks (
                id, title, task_type, status, priority,
                assignee, description, created_at, updated_at, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
        """,
            (
                task_id,
                sub_task.get("title", "Planned Sub-task")
                "planned_subtask",
                "queued",
                50,  # Default priority for sub-tasks,
                sub_task.get("assignee", "worker:backend")
                sub_task.get("description", "")
                json.dumps(payload)
            )
        )

        created_count += 1

    conn.commit()
    conn.close()

    return created_count
