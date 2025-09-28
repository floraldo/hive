"""
Hive-specific error reporter implementation.

Extends the generic error handling toolkit with Hive orchestration error reporting:
- Database-backed error persistence
- Agent error correlation
- Workflow error tracking
- Hive-specific recovery suggestions
"""

from hive_logging import get_logger
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional

from hive_errors import BaseErrorReporter
from hive_config import get_config

from .hive_exceptions import HiveError

logger = get_logger(__name__)


class HiveErrorReporter(BaseErrorReporter):
    """
    Hive-specific error reporter implementation.

    Extends BaseErrorReporter with Hive orchestration features:
    - Integration with Hive database
    - Agent-specific error tracking
    - Workflow error correlation
    - Task failure analysis
    """

    def __init__(
        self,
        log_to_file: bool = True,
        log_to_db: bool = True,
        error_log_path: Optional[Path] = None,
        error_db_path: Optional[Path] = None
    ):
        """Initialize Hive error reporter"""
        super().__init__(log_to_file, log_to_db, error_log_path, error_db_path)

        # Hive-specific configuration
        self.config = get_config()
        self._setup_hive_error_tables()

    def _setup_hive_error_tables(self):
        """Setup Hive-specific error tables"""
        if not self.log_to_db:
            return

        try:
            conn = sqlite3.connect(str(self.error_db_path))
            cursor = conn.cursor()

            # Extend base error table with Hive-specific fields
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hive_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    component TEXT NOT NULL,
                    operation TEXT,
                    message TEXT NOT NULL,
                    details TEXT,
                    context TEXT,
                    recovery_suggestions TEXT,
                    agent_id TEXT,
                    worker_id TEXT,
                    task_id TEXT,
                    workflow_id TEXT,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolution_time TEXT,
                    resolution_notes TEXT
                )
            """)

            # Hive-specific indexes for orchestration queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_hive_errors_agent
                ON hive_errors(agent_id, timestamp DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_hive_errors_task
                ON hive_errors(task_id, timestamp DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_hive_errors_workflow
                ON hive_errors(workflow_id, timestamp DESC)
            """)

            conn.commit()
            conn.close()

        except Exception as e:
            logger.warning(f"Failed to setup Hive error tables: {e}")

    def report_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Report an error with Hive orchestration context.

        Args:
            error: The exception to report
            context: Error context (may include agent_id, task_id, workflow_id)
            additional_info: Additional information about the error

        Returns:
            Error ID for tracking
        """
        # Build error record with Hive extensions
        error_record = self._build_hive_error_record(error, context, additional_info)

        # Update base metrics
        self._update_metrics(error_record)

        # Log to file (base implementation)
        if self.log_to_file:
            self._log_to_file(error_record)

        # Log to Hive database
        if self.log_to_db:
            self._log_to_hive_database(error_record)

        # Add to history
        self.error_history.append(error_record)
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-1000:]

        return error_record["error_id"]

    def _build_hive_error_record(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]],
        additional_info: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build error record with Hive-specific fields"""
        # Start with base error record
        record = self._build_error_record(error, context, additional_info)

        # Extract Hive-specific context
        if context:
            record["agent_id"] = context.get("agent_id")
            record["worker_id"] = context.get("worker_id")
            record["task_id"] = context.get("task_id")
            record["workflow_id"] = context.get("workflow_id")

        # Add Hive-specific error analysis
        if isinstance(error, HiveError):
            record["hive_error_details"] = {
                "component": error.component,
                "operation": error.operation,
                "recovery_suggestions": error.recovery_suggestions
            }

        return record

    def _log_to_hive_database(self, error_record: Dict[str, Any]):
        """Log error to Hive database with orchestration fields"""
        try:
            conn = sqlite3.connect(str(self.error_db_path))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO hive_errors (
                    timestamp, error_type, component, operation,
                    message, details, context, recovery_suggestions,
                    agent_id, worker_id, task_id, workflow_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                error_record["timestamp"],
                error_record["error_type"],
                error_record.get("component", "unknown"),
                error_record.get("operation"),
                error_record["message"],
                str(error_record.get("details", {})),
                str(error_record.get("context", {})),
                str(error_record.get("recovery_suggestions", [])),
                error_record.get("agent_id"),
                error_record.get("worker_id"),
                error_record.get("task_id"),
                error_record.get("workflow_id")
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.warning(f"Failed to write error to Hive database: {e}")

    def get_agent_errors(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get errors for a specific agent"""
        return self._get_hive_errors(agent_id=agent_id, limit=limit)

    def get_task_errors(self, task_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get errors for a specific task"""
        return self._get_hive_errors(task_id=task_id, limit=limit)

    def get_workflow_errors(self, workflow_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get errors for a specific workflow"""
        return self._get_hive_errors(workflow_id=workflow_id, limit=limit)

    def _get_hive_errors(
        self,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Query Hive errors with orchestration filters"""
        if not self.log_to_db:
            return []

        try:
            conn = sqlite3.connect(str(self.error_db_path))
            cursor = conn.cursor()

            query_parts = ["SELECT * FROM hive_errors WHERE 1=1"]
            params = []

            if agent_id:
                query_parts.append("AND agent_id = ?")
                params.append(agent_id)

            if task_id:
                query_parts.append("AND task_id = ?")
                params.append(task_id)

            if workflow_id:
                query_parts.append("AND workflow_id = ?")
                params.append(workflow_id)

            query_parts.append("ORDER BY timestamp DESC LIMIT ?")
            params.append(limit)

            query = " ".join(query_parts)
            cursor.execute(query, params)
            rows = cursor.fetchall()

            conn.close()

            # Convert rows to dicts
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.warning(f"Failed to query Hive errors: {e}")
            return []


# Global Hive error reporter instance
_hive_error_reporter: Optional[HiveErrorReporter] = None


def get_hive_error_reporter() -> HiveErrorReporter:
    """Get or create the global Hive error reporter"""
    global _hive_error_reporter
    if _hive_error_reporter is None:
        _hive_error_reporter = HiveErrorReporter()
    return _hive_error_reporter


def report_hive_error(
    error: Exception,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    **kwargs
) -> str:
    """
    Convenience function to report a Hive error with orchestration context.

    Args:
        error: The exception to report
        agent_id: Agent where error occurred
        task_id: Task where error occurred
        workflow_id: Workflow where error occurred
        **kwargs: Additional context

    Returns:
        Error ID for tracking
    """
    context = {
        "agent_id": agent_id,
        "task_id": task_id,
        "workflow_id": workflow_id,
        **kwargs
    }

    reporter = get_hive_error_reporter()
    return reporter.report_error(error, context)