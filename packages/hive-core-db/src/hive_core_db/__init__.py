"""
Hive Core DB - Internal state management database for the Hive orchestration system.

This package manages Hive's private, internal database for task orchestration,
worker management, and execution tracking. It is NOT for general application use.
"""

from .database import (
    init_db,
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

__all__ = [
    # Database management
    'init_db',
    'close_connection',

    # Task management
    'create_task',
    'get_task',
    'get_queued_tasks',
    'get_tasks_by_status',
    'update_task_status',

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