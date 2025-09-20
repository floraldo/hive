"""
Database adapter for AI Reviewer to interact with Hive Core DB
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from hive_core_db import HiveDatabase, Task, TaskStatus
from hive_logging import get_logger


logger = get_logger(__name__)


class DatabaseAdapter:
    """
    Adapter for database operations specific to AI Review functionality
    """

    def __init__(self, db: HiveDatabase):
        """Initialize with database connection"""
        self.db = db

    def get_pending_reviews(self, limit: int = 10) -> List[Task]:
        """
        Get tasks pending review

        Args:
            limit: Maximum number of tasks to retrieve

        Returns:
            List of tasks with status 'review_pending'
        """
        try:
            with self.db.get_session() as session:
                tasks = session.query(Task)\
                    .filter(Task.status == TaskStatus.REVIEW_PENDING)\
                    .order_by(Task.created_at)\
                    .limit(limit)\
                    .all()
                return tasks
        except Exception as e:
            logger.error(f"Error fetching pending reviews: {e}")
            return []

    def get_task_code_files(self, task_id: str) -> Dict[str, str]:
        """
        Retrieve code files associated with a task

        Args:
            task_id: Task identifier

        Returns:
            Dictionary mapping filename to content
        """
        try:
            with self.db.get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    return {}

                # Extract code from result_data
                result_data = task.result_data or {}

                # Look for code files in various possible locations
                code_files = {}

                # Direct files field
                if "files" in result_data:
                    code_files.update(result_data["files"])

                # Code field
                if "code" in result_data:
                    if isinstance(result_data["code"], dict):
                        code_files.update(result_data["code"])
                    else:
                        # Single file scenario
                        code_files["main.py"] = result_data["code"]

                # Generated files field
                if "generated_files" in result_data:
                    code_files.update(result_data["generated_files"])

                # Worker results
                if "worker_results" in result_data:
                    for worker, results in result_data["worker_results"].items():
                        if isinstance(results, dict) and "files" in results:
                            code_files.update(results["files"])

                return code_files

        except Exception as e:
            logger.error(f"Error fetching code files for task {task_id}: {e}")
            return {}

    def get_test_results(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve test results for a task

        Args:
            task_id: Task identifier

        Returns:
            Test results dictionary or None
        """
        try:
            with self.db.get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    return None

                result_data = task.result_data or {}

                # Look for test results in various locations
                if "test_results" in result_data:
                    return result_data["test_results"]

                if "tests" in result_data:
                    return result_data["tests"]

                # Check worker results
                if "worker_results" in result_data:
                    for worker, results in result_data["worker_results"].items():
                        if isinstance(results, dict) and "test_results" in results:
                            return results["test_results"]

                return None

        except Exception as e:
            logger.error(f"Error fetching test results for task {task_id}: {e}")
            return None

    def get_task_transcript(self, task_id: str) -> Optional[str]:
        """
        Retrieve conversation transcript for a task

        Args:
            task_id: Task identifier

        Returns:
            Transcript string or None
        """
        try:
            with self.db.get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    return None

                result_data = task.result_data or {}

                # Look for transcript
                if "transcript" in result_data:
                    return result_data["transcript"]

                if "conversation" in result_data:
                    return result_data["conversation"]

                # Check metadata
                metadata = task.metadata or {}
                if "transcript" in metadata:
                    return metadata["transcript"]

                return None

        except Exception as e:
            logger.error(f"Error fetching transcript for task {task_id}: {e}")
            return None

    def update_task_status(
        self,
        task_id: str,
        new_status: TaskStatus,
        review_data: Dict[str, Any]
    ) -> bool:
        """
        Update task status after review

        Args:
            task_id: Task identifier
            new_status: New status to set
            review_data: Review results to store

        Returns:
            True if successful
        """
        try:
            with self.db.get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    logger.error(f"Task {task_id} not found")
                    return False

                # Update status
                task.status = new_status
                task.updated_at = datetime.utcnow()

                # Store review results
                if not task.result_data:
                    task.result_data = {}

                task.result_data["review"] = review_data
                task.result_data["review_timestamp"] = datetime.utcnow().isoformat()
                task.result_data["reviewed_by"] = "ai-reviewer"

                # Store escalation details if present
                if "escalation_reason" in review_data:
                    task.result_data["escalation_reason"] = review_data["escalation_reason"]
                if "confusion_points" in review_data:
                    task.result_data["confusion_points"] = review_data["confusion_points"]

                # Add to metadata for tracking
                if not task.metadata:
                    task.metadata = {}

                task.metadata["last_review"] = {
                    "status": new_status.value,
                    "timestamp": datetime.utcnow().isoformat(),
                    "score": review_data.get("overall_score", 0)
                }

                session.commit()
                logger.info(f"Updated task {task_id} to status {new_status.value}")
                return True

        except Exception as e:
            logger.error(f"Error updating task {task_id} status: {e}")
            return False

    def store_review_report(
        self,
        task_id: str,
        report: Dict[str, Any]
    ) -> bool:
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

    def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
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

                result_data = task.result_data or {}
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

    def get_agent_statistics(self) -> Dict[str, Any]:
        """
        Get overall AI reviewer statistics

        Returns:
            Dictionary of statistics
        """
        try:
            with self.db.get_session() as session:
                # Count tasks by review status
                total_reviewed = session.query(Task)\
                    .filter(Task.result_data.contains({"reviewed_by": "ai-reviewer"}))\
                    .count()

                approved = session.query(Task)\
                    .filter(Task.status == TaskStatus.APPROVED)\
                    .filter(Task.result_data.contains({"reviewed_by": "ai-reviewer"}))\
                    .count()

                rejected = session.query(Task)\
                    .filter(Task.status == TaskStatus.REJECTED)\
                    .filter(Task.result_data.contains({"reviewed_by": "ai-reviewer"}))\
                    .count()

                rework = session.query(Task)\
                    .filter(Task.status == TaskStatus.REWORK_NEEDED)\
                    .filter(Task.result_data.contains({"reviewed_by": "ai-reviewer"}))\
                    .count()

                pending = session.query(Task)\
                    .filter(Task.status == TaskStatus.REVIEW_PENDING)\
                    .count()

                return {
                    "total_reviewed": total_reviewed,
                    "approved": approved,
                    "rejected": rejected,
                    "rework_needed": rework,
                    "pending_review": pending,
                    "approval_rate": (approved / total_reviewed * 100) if total_reviewed > 0 else 0
                }

        except Exception as e:
            logger.error(f"Error fetching agent statistics: {e}")
            return {}