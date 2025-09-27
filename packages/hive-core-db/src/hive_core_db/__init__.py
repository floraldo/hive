"""
Hive Core DB - Internal state management database for the Hive orchestration system.

This package manages Hive's private, internal database for task orchestration,
worker management, and execution tracking. It is NOT for general application use.
"""

from .database import (
    init_db,
    get_connection,
    create_task,
    get_task,
    get_queued_tasks,
    get_tasks_by_status,
    update_task_status,
    create_run,
    update_run_status,
    log_run_result,
    get_run,
    get_task_runs,
    register_worker,
    update_worker_heartbeat,
    get_active_workers,
    close_connection
)

# Import enhanced functions for AI Planner integration
from .database_enhanced import (
    get_queued_tasks_with_planning,
    check_subtask_dependencies,
    get_execution_plan_status,
    mark_plan_execution_started,
    get_next_planned_subtask,
    create_planned_subtasks_from_plan
)

__all__ = [
    # Database management
    'init_db',
    'get_connection',
    'close_connection',

    # Task management
    'create_task',
    'get_task',
    'get_queued_tasks',
    'get_tasks_by_status',
    'update_task_status',

    # Enhanced task management for AI Planner integration
    'get_queued_tasks_with_planning',
    'check_subtask_dependencies',
    'get_execution_plan_status',
    'mark_plan_execution_started',
    'get_next_planned_subtask',
    'create_planned_subtasks_from_plan',

    # Run tracking (task executions)
    'create_run',
    'update_run_status',
    'log_run_result',
    'get_run',
    'get_task_runs',

    # Worker management
    'register_worker',
    'update_worker_heartbeat',
    'get_active_workers'
]