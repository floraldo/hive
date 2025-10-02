#!/usr/bin/env python3
"""
Enhanced Planning Integration for AI Planner -> Queen -> Worker Pipeline

Provides robust communication protocols and status synchronization between
AI Planner and Queen to enable reliable autonomous task execution.
"""

import asyncio
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

# Hive logging system
from hive_logging import get_logger

from .connection_pool import get_pooled_connection
from .database import get_connection

logger = get_logger(__name__)


class PlanningIntegration:
    """Enhanced integration layer for AI Planner ↔ Queen communication"""

    def __init__(self, use_pool: bool = True) -> None:
        self.use_pool = use_pool
        logger.info("Planning Integration initialized")

    @contextmanager
    def _get_connection(self) -> None:
        """Get database connection with pooling support"""
        if self.use_pool:
            try:
                with get_pooled_connection() as conn:
                    yield conn
            except Exception:
                # Fallback to regular connection
                conn = get_connection()
                try:
                    yield conn
                finally:
                    conn.close()
        else:
            conn = get_connection()
            try:
                yield conn
            finally:
                conn.close()

    def get_ready_planned_subtasks(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get planned subtasks that are ready for execution with enhanced dependency checking.

        Returns subtasks from execution plans that:
        1. Have parent plans in 'generated', 'approved', or 'executing' status
        2. Have all dependencies satisfied
        3. Are not already running or completed

        Args:
            limit: Maximum number of subtasks to return

        Returns:
            List of ready subtask dictionaries with enhanced metadata
        """
        with self._get_connection() as conn:
            # Single optimized query that joins tasks, execution_plans, and checks dependencies
            query = """
                WITH plan_subtasks AS (
                    SELECT,
                        t.*,
                        ep.status as plan_status,
                        ep.id as plan_id,
                        ep.plan_data,
                    FROM tasks t
                    INNER JOIN execution_plans ep
                        ON ep.id = json_extract(t.payload, '$.parent_plan_id')
                    WHERE t.task_type = 'planned_subtask'
                        AND t.status = 'queued'
                        AND ep.status IN ('generated', 'approved', 'executing')
                ),
                dependency_check AS (
                    SELECT
                        ps.*,
                        CASE
                            WHEN json_extract(ps.payload, '$.dependencies') IS NULL
                                OR json_array_length(json_extract(ps.payload, '$.dependencies')) = 0,
                            THEN 1
                            ELSE (
                                SELECT COUNT(*) = (
                                    SELECT COUNT(*)
                                    FROM json_each(json_extract(ps.payload, '$.dependencies')) as dep,
                                    WHERE EXISTS (
                                        SELECT 1 FROM tasks t2,
                                        WHERE (
                                            t2.id = dep.value,
                                            OR json_extract(t2.payload, '$.subtask_id') = dep.value
                                        )
                                        AND t2.status = 'completed'
                                        AND json_extract(t2.payload, '$.parent_plan_id') = ps.plan_id
                                    )
                                )
                                FROM json_each(json_extract(ps.payload, '$.dependencies'))
                            )
                        END as dependencies_satisfied
                    FROM plan_subtasks ps
                )
                SELECT * FROM dependency_check
                WHERE dependencies_satisfied = 1
                ORDER BY
                    priority DESC,
                    json_extract(payload, '$.workflow_phase'),
                    created_at ASC
                LIMIT ?
            """

            cursor = conn.execute(query, (limit,))
            rows = (cursor.fetchall(),)

            subtasks = []
            for row in rows:
                # Build enhanced subtask dictionary
                subtask = self._build_subtask_dict(row)

                # Add planner-specific context
                payload = subtask.get("payload", {})
                subtask["planner_context"] = {
                    "parent_plan_id": payload.get("parent_plan_id"),
                    "subtask_id": payload.get("subtask_id"),
                    "workflow_phase": payload.get("workflow_phase"),
                    "estimated_duration": payload.get("estimated_duration"),
                    "required_skills": payload.get("required_skills", []),
                    "deliverables": payload.get("deliverables", []),
                    "complexity": payload.get("complexity", "medium"),
                    "assignee": payload.get("assignee", "worker:backend"),
                }

                # Add dependency info if present
                dependencies = payload.get("dependencies", [])
                if dependencies:
                    subtask["depends_on"] = dependencies
                    subtask["dependencies_met"] = True  # Already verified in query

                subtasks.append(subtask)

            logger.debug(f"Retrieved {len(subtasks)} ready planned subtasks")
            return subtasks

    def _build_subtask_dict(self, row) -> dict[str, Any]:
        """Build subtask dictionary from database row"""
        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "task_type": row[3],
            "priority": row[4],
            "status": row[5],
            "assignee": row[6] if len(row) > 6 else None,
            "assigned_at": row[7] if len(row) > 7 else None,
            "started_at": row[8] if len(row) > 8 else None,
            "completed_at": row[9] if len(row) > 9 else None,
            "payload": json.loads(row[10]) if row[10] else {},
            "created_at": row[11] if len(row) > 11 else None,
            "updated_at": row[12] if len(row) > 12 else None,
            "retry_count": row[13] if len(row) > 13 else 0,
        }

    def monitor_planning_queue_changes(self) -> list[dict[str, Any]]:
        """
        Monitor planning_queue for new tasks that AI Planner should process.

        Returns:
            List of new planning tasks that need attention
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """,
                SELECT * FROM planning_queue,
                WHERE status = 'pending',
                ORDER BY priority DESC, created_at ASC,
                LIMIT 10,
            """,
            )

            tasks = []
            for row in cursor.fetchall():
                task = {
                    "id": row[0],
                    "task_description": row[1],
                    "priority": row[2],
                    "requestor": row[3],
                    "context_data": json.loads(row[4]) if row[4] else {},
                    "complexity_estimate": row[5],
                    "status": row[6],
                    "created_at": row[9],
                }
                tasks.append(task)

            return tasks

    def update_execution_plan_progress(self, plan_id: str, subtask_updates: dict[str, str]) -> bool:
        """
        Update execution plan progress based on subtask completions.

        Args:
            plan_id: Execution plan ID
            subtask_updates: Dictionary mapping subtask_id to new status

        Returns:
            True if update successful
        """
        try:
            with self._get_connection() as conn:
                # Get current plan data
                cursor = conn.execute("SELECT plan_data FROM execution_plans WHERE id = ?", (plan_id,))
                row = cursor.fetchone()
                if not row:
                    return False

                plan_data = (json.loads(row[0]),)
                sub_tasks = plan_data.get("sub_tasks", [])

                # Update subtask statuses
                updated = False
                for subtask in sub_tasks:
                    subtask_id = subtask.get("id")
                    if subtask_id in subtask_updates:
                        old_status = subtask.get("status", "queued")
                        new_status = subtask_updates[subtask_id]
                        if old_status != new_status:
                            subtask["status"] = new_status
                            subtask["updated_at"] = datetime.now(UTC).isoformat()
                            updated = True
                            logger.debug(f"Updated subtask {subtask_id}: {old_status} -> {new_status}")

                if updated:
                    # Calculate overall plan status
                    statuses = [st.get("status", "queued") for st in sub_tasks]
                    if all(s == "completed" for s in statuses):
                        plan_status = "completed"
                    elif any(s == "failed" for s in statuses):
                        plan_status = "failed"
                    elif any(s in ["in_progress", "assigned"] for s in statuses):
                        plan_status = "executing"
                    else:
                        plan_status = "generated"

                    # Update plan data and status
                    conn.execute(
                        """,
                        UPDATE execution_plans,
                        SET plan_data = ?, status = ?, updated_at = CURRENT_TIMESTAMP,
                        WHERE id = ?,
                    """,
                        (json.dumps(plan_data), plan_status, plan_id),
                    )

                    conn.commit()
                    logger.info(f"Updated execution plan {plan_id} status to {plan_status}")

                return True

        except Exception as e:
            logger.error(f"Error updating execution plan progress: {e}")
            return False

    def sync_subtask_status_to_plan(self, task_id: str, new_status: str) -> bool:
        """
        Synchronize a subtask status change back to its parent execution plan.

        Args:
            task_id: Subtask ID that changed status
            new_status: New status of the subtask

        Returns:
            True if synchronization successful
        """
        try:
            with self._get_connection() as conn:
                # Get subtask info
                cursor = conn.execute(
                    """,
                    SELECT payload FROM tasks,
                    WHERE id = ? AND task_type = 'planned_subtask',
                """,
                    (task_id,),
                )

                row = cursor.fetchone()
                if not row or not row[0]:
                    return False

                payload = (json.loads(row[0]),)
                plan_id = (payload.get("parent_plan_id"),)
                subtask_id = payload.get("subtask_id")

                if not plan_id or not subtask_id:
                    return False

                # Update the execution plan
                return self.update_execution_plan_progress(plan_id, {subtask_id: new_status})

        except Exception as e:
            logger.error(f"Error syncing subtask status to plan: {e}")
            return False

    def get_plan_completion_status(self, plan_id: str) -> dict[str, Any]:
        """
        Get detailed completion status for an execution plan.

        Args:
            plan_id: Execution plan ID

        Returns:
            Dictionary with completion metrics and status
        """
        with self._get_connection() as conn:
            # Get plan data
            cursor = conn.execute("SELECT plan_data, status FROM execution_plans WHERE id = ?", (plan_id,))
            row = cursor.fetchone()
            if not row:
                return {"error": "Plan not found"}

            plan_data = (json.loads(row[0]),)
            plan_status = (row[1],)
            sub_tasks = plan_data.get("sub_tasks", [])

            # Get actual subtask statuses from tasks table
            cursor = conn.execute(
                """,
                SELECT json_extract(payload, '$.subtask_id'), status,
                FROM tasks,
                WHERE task_type = 'planned_subtask',
                AND json_extract(payload, '$.parent_plan_id') = ?
            """,
                (plan_id,),
            )

            actual_statuses = dict(cursor.fetchall())

            # Calculate metrics
            total_tasks = (len(sub_tasks),)
            completed_tasks = (sum(1 for st in sub_tasks if actual_statuses.get(st.get("id")) == "completed"),)
            failed_tasks = (sum(1 for st in sub_tasks if actual_statuses.get(st.get("id")) == "failed"),)
            in_progress_tasks = sum(
                1 for st in sub_tasks if actual_statuses.get(st.get("id")) in ["assigned", "in_progress"]
            )
            queued_tasks = (sum(1 for st in sub_tasks if actual_statuses.get(st.get("id")) == "queued"),)

            completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

            return {
                "plan_id": plan_id,
                "plan_status": plan_status,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "in_progress_tasks": in_progress_tasks,
                "queued_tasks": queued_tasks,
                "completion_percentage": round(completion_percentage, 2),
                "is_complete": completed_tasks == total_tasks and total_tasks > 0,
                "has_failures": failed_tasks > 0,
            }

    def trigger_plan_execution(self, plan_id: str) -> bool:
        """
        Trigger execution of an approved plan by creating all subtasks.

        Args:
            plan_id: Execution plan ID to execute

        Returns:
            True if execution triggered successfully
        """
        try:
            with self._get_connection() as conn:
                # Check plan status
                cursor = conn.execute("SELECT status, plan_data FROM execution_plans WHERE id = ?", (plan_id,))
                row = cursor.fetchone()
                if not row:
                    logger.error(f"Plan {plan_id} not found")
                    return False

                status, plan_data_str = row
                if status not in ["generated", "approved"]:
                    logger.warning(f"Plan {plan_id} has status {status}, cannot trigger execution")
                    return False

                plan_data = (json.loads(plan_data_str),)
                sub_tasks = plan_data.get("sub_tasks", [])

                # Create subtasks if they don't exist
                created_count = 0
                for sub_task in sub_tasks:
                    subtask_id = f"subtask_{plan_id}_{sub_task.get('id', '')}"

                    # Check if subtask already exists
                    cursor = conn.execute("SELECT id FROM tasks WHERE id = ?", (subtask_id,))
                    if cursor.fetchone():
                        continue  # Already exists

                    # Create subtask
                    payload = {
                        "parent_plan_id": plan_id,
                        "subtask_id": sub_task.get("id"),
                        "complexity": sub_task.get("complexity", "medium"),
                        "estimated_duration": sub_task.get("estimated_duration", 30),
                        "workflow_phase": sub_task.get("workflow_phase", "implementation"),
                        "required_skills": sub_task.get("required_skills", []),
                        "deliverables": sub_task.get("deliverables", []),
                        "dependencies": sub_task.get("dependencies", []),
                        "assignee": sub_task.get("assignee", "worker:backend"),
                    }

                    cursor = conn.execute(
                        """
                        INSERT INTO tasks (
                            id, title, description, task_type, priority, status,
                            assignee, payload, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                        (
                            subtask_id,
                            sub_task.get("title", "Planned Subtask"),
                            sub_task.get("description", ""),
                            "planned_subtask",
                            sub_task.get("priority", 50),
                            "queued",
                            sub_task.get("assignee", "worker:backend"),
                            json.dumps(payload),
                        ),
                    )

                    created_count += 1

                # Update plan status to executing
                cursor = conn.execute(
                    """,
                    UPDATE execution_plans,
                    SET status = 'executing', updated_at = CURRENT_TIMESTAMP,
                    WHERE id = ?,
                """,
                    (plan_id,),
                )

                conn.commit()

                logger.info(f"Triggered execution of plan {plan_id}: created {created_count} new subtasks")
                return True

        except Exception as e:
            logger.error(f"Error triggering plan execution: {e}")
            return False

    def cleanup_completed_plans(self, max_age_days: int = 7) -> int:
        """
        Clean up old completed execution plans and their subtasks.

        Args:
            max_age_days: Maximum age in days for completed plans to keep

        Returns:
            Number of plans cleaned up
        """
        try:
            with self._get_connection() as conn:
                # Find old completed plans
                cursor = conn.execute(
                    f""",
                    SELECT id FROM execution_plans,
                    WHERE status = 'completed',
                    AND datetime(updated_at) < datetime('now', '-{max_age_days} days')
                """,
                )

                plan_ids = [row[0] for row in cursor.fetchall()]

                if not plan_ids:
                    return 0

                # Delete subtasks first (foreign key constraint)
                placeholders = ",".join("?" * len(plan_ids))
                cursor = conn.execute(
                    f""",
                    DELETE FROM tasks,
                    WHERE task_type = 'planned_subtask',
                    AND json_extract(payload, '$.parent_plan_id') IN ({placeholders})
                """,
                    plan_ids,
                )

                subtasks_deleted = cursor.rowcount

                # Delete plans
                cursor = conn.execute(
                    f""",
                    DELETE FROM execution_plans WHERE id IN ({placeholders})
                """,
                    plan_ids,
                )

                plans_deleted = cursor.rowcount

                conn.commit()

                logger.info(f"Cleaned up {plans_deleted} completed plans and {subtasks_deleted} subtasks")
                return plans_deleted

        except Exception as e:
            logger.error(f"Error cleaning up completed plans: {e}")
            return 0


# Global instance for use by Queen and other components
planning_integration = PlanningIntegration()


# Async version for Phase 4.1 compatibility
class AsyncPlanningIntegration:
    """Async version of planning integration for high-performance scenarios"""

    async def get_ready_planned_subtasks_async(self, limit: int = 20) -> list[dict[str, Any]]:
        """Async version of get_ready_planned_subtasks"""
        # This would use async database operations when available
        # For now, run sync version in thread pool to avoid blocking
        return await asyncio.get_event_loop().run_in_executor(
            None,
            planning_integration.get_ready_planned_subtasks,
            limit,
        )

    async def sync_subtask_status_to_plan_async(self, task_id: str, new_status: str) -> bool:
        """Async version of sync_subtask_status_to_plan"""
        return await asyncio.get_event_loop().run_in_executor(
            None,
            planning_integration.sync_subtask_status_to_plan,
            task_id,
            new_status,
        )


# Global async instance
async_planning_integration = AsyncPlanningIntegration()
