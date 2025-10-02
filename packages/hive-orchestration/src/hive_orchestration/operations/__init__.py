"""
Orchestration Operations

This module contains the core operation implementations for task, worker,
and execution plan management.
"""

from hive_logging import get_logger

logger = get_logger(__name__)

# Task operations
# Execution plan operations
from .plans import (
    check_subtask_dependencies,
    check_subtask_dependencies_batch,
    create_planned_subtasks_from_plan,
    get_execution_plan_status,
    get_execution_plan_status_cached,
    get_next_planned_subtask,
    mark_plan_execution_started,
)
from .tasks import (
    create_task,
    delete_task,
    get_queued_tasks,
    get_task,
    get_tasks_by_status,
    update_task_status,
)

# Worker operations
from .workers import (
    get_active_workers,
    get_worker,
    register_worker,
    unregister_worker,
    update_worker_heartbeat,
)

__all__ = [
    # Task operations
    "create_task",
    "get_task",
    "update_task_status",
    "get_tasks_by_status",
    "get_queued_tasks",
    "delete_task",
    # Worker operations
    "register_worker",
    "update_worker_heartbeat",
    "get_active_workers",
    "get_worker",
    "unregister_worker",
    # Execution plan operations
    "create_planned_subtasks_from_plan",
    "get_execution_plan_status",
    "check_subtask_dependencies",
    "get_next_planned_subtask",
    "mark_plan_execution_started",
    "check_subtask_dependencies_batch",
    "get_execution_plan_status_cached",
]
