"""
Database Schema for Hive Orchestration

Defines the database schema for tasks, workers, runs, and execution plans.
"""

from __future__ import annotations

from hive_logging import get_logger

from .operations import transaction

logger = get_logger(__name__)


def init_db() -> None:
    """
    Initialize the orchestration database with required tables.

    Creates tables for:
    - tasks: Task definitions and lifecycle
    - runs: Execution attempts of tasks
    - workers: Worker registration and heartbeat
    - planning_queue: AI planning requests
    - execution_plans: Generated execution plans
    - plan_execution: Plan execution monitoring
    """
    with transaction() as conn:
        # Tasks table - Task definitions (what needs to be done)
        conn.execute(
            """
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
            """,
        )

        # Runs table - Execution attempts
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                run_number INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                phase TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                result_data TEXT,
                error_message TEXT,
                output_log TEXT,
                transcript TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
                FOREIGN KEY (worker_id) REFERENCES workers (id),
                UNIQUE(task_id, run_number)
            )
            """,
        )

        # Workers table - Worker registration and heartbeat
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                capabilities TEXT,
                current_task_id TEXT,
                metadata TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (current_task_id) REFERENCES tasks (id)
            )
            """,
        )

        # Planning queue - incoming requests for intelligent planning
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planning_queue (
                id TEXT PRIMARY KEY,
                task_description TEXT NOT NULL,
                priority INTEGER DEFAULT 50,
                requestor TEXT,
                context_data TEXT,
                status TEXT DEFAULT 'pending',
                complexity_estimate TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assigned_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                assigned_agent TEXT
            )
            """,
        )

        # Generated execution plans
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_plans (
                id TEXT PRIMARY KEY,
                planning_task_id TEXT NOT NULL,
                plan_data TEXT NOT NULL,
                estimated_duration INTEGER,
                estimated_complexity TEXT DEFAULT 'medium',
                generated_workflow TEXT,
                subtask_count INTEGER DEFAULT 0,
                dependency_count INTEGER DEFAULT 0,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'draft',
                FOREIGN KEY (planning_task_id) REFERENCES planning_queue (id) ON DELETE CASCADE
            )
            """,
        )

        # Plan execution monitoring
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_execution (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                current_phase TEXT,
                progress_percent INTEGER DEFAULT 0,
                active_subtasks TEXT,
                completed_subtasks TEXT,
                failed_subtasks TEXT,
                blocked_subtasks TEXT,
                execution_notes TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                FOREIGN KEY (plan_id) REFERENCES execution_plans (id) ON DELETE CASCADE
            )
            """,
        )

        # Indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks (priority DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON runs (task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_worker_id ON runs (worker_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workers_status ON workers (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workers_role ON workers (role)")

        # AI Planning indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_planning_queue_status ON planning_queue (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_planning_queue_priority ON planning_queue (priority DESC)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_execution_plans_planning_task_id ON execution_plans (planning_task_id)",
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_plans_status ON execution_plans (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_execution_plan_id ON plan_execution (plan_id)")

        # Apply migrations for existing databases
        _apply_memory_nexus_migration(conn)

        logger.info("Orchestration database initialized successfully")


def _apply_memory_nexus_migration(conn) -> None:
    """
    Migration: Add Memory Nexus columns to existing tasks table.

    This migration adds columns for the Intelligent Task & Memory Nexus:
    - summary: AI-generated executive summary
    - generated_artifacts: JSON array of file paths created
    - related_document_ids: JSON array of RAG vector IDs
    - knowledge_fragments: JSON structured fragments (summaries, errors, decisions)
    """
    # Check if migration is needed
    cursor = conn.execute("PRAGMA table_info(tasks)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    memory_columns = {
        "summary": "TEXT",
        "generated_artifacts": "TEXT",
        "related_document_ids": "TEXT",
        "knowledge_fragments": "TEXT"
    }

    for column_name, column_type in memory_columns.items():
        if column_name not in existing_columns:
            try:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_type}")
                logger.info(f"Migration: Added column '{column_name}' to tasks table")
            except Exception as e:
                logger.warning(f"Migration: Failed to add column '{column_name}': {e}")


__all__ = ["init_db"]
