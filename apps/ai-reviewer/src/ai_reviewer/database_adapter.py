"""
Database adapter for AI Reviewer to interact with Hive Core DB
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import hive_db as hive_core_db
from hive_logging import get_logger

logger = get_logger(__name__)


class DatabaseAdapter:
    """
    Adapter for database operations specific to AI Review functionality
    """

    def __init__(self) -> None:
        """Initialize with database connection"""
        # Initialize the database
        hive_core_db.init_db()

    def _parse_task_payload(self, task: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Safely parse task payload from string or dict format.

        Args:
            task: Task dictionary containing payload

        Returns:
            Parsed payload dictionary or None if parsing fails
        """
        if not task.get("payload"):
            return None

        payload = task["payload"]
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse payload for task: {payload[:100]}...")
                return None
        elif isinstance(payload, dict):
            return payload
        else:
            logger.warning(f"Unexpected payload type: {type(payload)}")
            return None

    def get_pending_reviews(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get tasks pending review

        Args:
            limit: Maximum number of tasks to retrieve

        Returns:
            List of tasks with status 'review_pending'
        """
        try:
            tasks = hive_core_db.get_tasks_by_status("review_pending")
            # Sort by created_at and limit
            sorted_tasks = sorted(tasks, key=lambda t: t.get("created_at", ""))
            return sorted_tasks[:limit]
        except Exception as e:
            logger.error(f"Error fetching pending reviews: {e}")
            return []

    def get_task_code_files(self, task_id: str) -> dict[str, str]:
        """
        Retrieve code files associated with a task

        Args:
            task_id: Task identifier

        Returns:
            Dictionary mapping filename to content
        """
        try:
            task = hive_core_db.get_task(task_id)
            if not task:
                return {}

            # Extract code from payload or other fields
            code_files = {}

            # Check payload for code files
            payload = self._parse_task_payload(task)
            if payload:
                # Look for code files in various possible locations
                if "files" in payload:
                    code_files.update(payload["files"])

                if "code" in payload:
                    if isinstance(payload["code"], dict):
                        code_files.update(payload["code"])
                    else:
                        # Single file scenario
                        code_files["main.py"] = payload["code"]

                if "generated_files" in payload:
                    code_files.update(payload["generated_files"])

            return code_files

        except Exception as e:
            logger.error(f"Error fetching code files for task {task_id}: {e}")
            return {}

    def get_test_results(self, task_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve test results for a task

        Args:
            task_id: Task identifier

        Returns:
            Test results dictionary or None
        """
        try:
            task = hive_core_db.get_task(task_id)
            if not task:
                return None

            # Check if test results are in the payload
            payload = self._parse_task_payload(task)
            if payload:
                # Look for test results in various locations
                if "test_results" in payload:
                    return payload["test_results"]

                if "tests" in payload:
                    return payload["tests"]

                # Check worker results
                if "worker_results" in payload:
                    for _worker, results in payload["worker_results"].items():
                        if isinstance(results, dict) and "test_results" in results:
                            return results["test_results"]

            return None

        except Exception as e:
            logger.error(f"Error fetching test results for task {task_id}: {e}")
            return None

    def get_task_transcript(self, task_id: str) -> str | None:
        """
        Retrieve conversation transcript for a task

        Args:
            task_id: Task identifier

        Returns:
            Transcript string or None
        """
        try:
            # Get runs for this task to find transcript
            runs = hive_core_db.get_task_runs(task_id)
            if runs:
                # Get the most recent run
                for run in runs:
                    if run.get("transcript"):
                        return run["transcript"]

            # Fall back to checking task payload
            task = hive_core_db.get_task(task_id)
            if not task:
                return None

            payload = self._parse_task_payload(task)
            if payload:
                # Look for transcript in payload
                if "transcript" in payload:
                    return payload["transcript"]
                if "conversation" in payload:
                    return payload["conversation"]

            return None

        except Exception as e:
            logger.error(f"Error fetching transcript for task {task_id}: {e}")
            return None

    def update_task_status(self, task_id: str, new_status: str, review_data: dict[str, Any]) -> bool:
        """
        Update task status after review

        Args:
            task_id: Task identifier
            new_status: New status to set (string)
            review_data: Review results to store

        Returns:
            True if successful
        """
        try:
            # Get current task
            task = hive_core_db.get_task(task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return False

            # Update task status with metadata
            metadata = {
                "review": review_data,
                "review_timestamp": datetime.now().isoformat(),
                "reviewed_by": "ai-reviewer",
            }

            # Store escalation details if present
            if "escalation_reason" in review_data:
                metadata["escalation_reason"] = review_data["escalation_reason"]
            if "confusion_points" in review_data:
                metadata["confusion_points"] = review_data["confusion_points"]

            # Add tracking info
            metadata["last_review"] = {
                "status": new_status,
                "timestamp": datetime.now().isoformat(),
                "score": review_data.get("overall_score", 0),
            }

            success = hive_core_db.update_task_status(task_id, new_status, metadata)
            if success:
                logger.info(f"Updated task {task_id} to status {new_status}")
            else:
                logger.error(f"Failed to update task {task_id} status")

            return success

        except Exception as e:
            logger.error(f"Error updating task {task_id} status: {e}")
            return False

    def store_review_report(self, task_id: str, report: dict[str, Any]) -> bool:
        """
        Store detailed review report

        Args:
            task_id: Task identifier
            report: Full review report

        Returns:
            True if successful
        """
        try:
            with self.db.get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    return False

                # Store full report
                if not task.result_data:
                    task.result_data = {}

                task.result_data["detailed_review"] = report
                session.commit()
                return True

        except Exception as e:
            logger.error(f"Error storing review report for task {task_id}: {e}")
            return False

    def get_task_history(self, task_id: str) -> list[dict[str, Any]]:
        """
        Get review history for a task

        Args:
            task_id: Task identifier

        Returns:
            List of historical reviews
        """
        try:
            with self.db.get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    return []

                result_data = (task.result_data or {},)
                history = result_data.get("review_history", [])

                # Add current review if exists
                if "review" in result_data:
                    current = result_data["review"].copy()
                    current["timestamp"] = result_data.get("review_timestamp")
                    history.append(current)

                return history

        except Exception as e:
            logger.error(f"Error fetching history for task {task_id}: {e}")
            return []

    def get_agent_statistics(self) -> dict[str, Any]:
        """
        Get overall AI reviewer statistics

        Returns:
            Dictionary of statistics
        """
        try:
            with self.db.get_session() as session:
                # Count tasks by review status
                total_reviewed = (
                    session.query(Task).filter(Task.result_data.contains({"reviewed_by": "ai-reviewer"})).count()
                )

                approved = (
                    session.query(Task)
                    .filter(Task.status == TaskStatus.APPROVED)
                    .filter(Task.result_data.contains({"reviewed_by": "ai-reviewer"}))
                    .count()
                )

                rejected = (
                    session.query(Task)
                    .filter(Task.status == TaskStatus.REJECTED)
                    .filter(Task.result_data.contains({"reviewed_by": "ai-reviewer"}))
                    .count()
                )

                rework = (
                    session.query(Task)
                    .filter(Task.status == TaskStatus.REWORK_NEEDED)
                    .filter(Task.result_data.contains({"reviewed_by": "ai-reviewer"}))
                    .count()
                )

                pending = session.query(Task).filter(Task.status == TaskStatus.REVIEW_PENDING).count()

                return {
                    "total_reviewed": total_reviewed,
                    "approved": approved,
                    "rejected": rejected,
                    "rework_needed": rework,
                    "pending_review": pending,
                    "approval_rate": ((approved / total_reviewed * 100) if total_reviewed > 0 else 0),
                }

        except Exception as e:
            logger.error(f"Error fetching agent statistics: {e}")
            return {}
