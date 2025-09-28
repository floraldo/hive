"""
Hive Core DB - Internal state management database for the Hive orchestration system.

This package manages Hive's private, internal database for task orchestration,
worker management, and execution tracking. It is NOT for general application use.

Extends the generic hive_db package with Hive Orchestrator-specific functionality.
"""

from hive_db import get_sqlite_connection, sqlite_transaction, create_table_if_not_exists

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

# Import optimized enhanced functions (Phase 4.1)
from .database_enhanced_optimized import (
    get_queued_tasks_with_planning_optimized,
    check_subtask_dependencies_batch,
    get_execution_plan_status_cached,
    create_planned_subtasks_optimized
)

# Import planning integration layer
try:
    from .planning_integration import (
        planning_integration,
        async_planning_integration
    )
    PLANNING_INTEGRATION_AVAILABLE = True
except ImportError:
    PLANNING_INTEGRATION_AVAILABLE = False

# Import shared database service for multi-database support
from .shared_connection_service import (
    get_database_connection,
    get_shared_database_service,
    close_all_database_pools,
    get_database_stats,
    database_health_check
)

# Import connection pool functions
from .connection_pool import (
    get_pooled_connection,
    close_pool
)

# Import async support if available
try:
    from .async_connection_pool import (
        get_async_connection,
        create_task_async,
        get_tasks_by_status_async,
        update_task_status_async,
        get_task_async,
        get_queued_tasks_async
    )
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False

# Export all functions
__all__ = [
    # Core database functions
    'init_db',
    'get_connection',
    'create_task',
    'get_task',
    'get_queued_tasks',
    'get_tasks_by_status',
    'update_task_status',
    'create_run',
    'update_run_status',
    'log_run_result',
    'get_run',
    'get_task_runs',
    'register_worker',
    'update_worker_heartbeat',
    'get_active_workers',
    'close_connection',

    # Enhanced AI Planner integration
    'get_queued_tasks_with_planning',
    'check_subtask_dependencies',
    'get_execution_plan_status',
    'mark_plan_execution_started',
    'get_next_planned_subtask',
    'create_planned_subtasks_from_plan',

    # Optimized functions
    'get_queued_tasks_with_planning_optimized',
    'check_subtask_dependencies_batch',
    'get_execution_plan_status_cached',
    'create_planned_subtasks_optimized',

    # Planning integration (if available)
    'planning_integration',
    'async_planning_integration',
    'PLANNING_INTEGRATION_AVAILABLE',

    # Shared services
    'get_database_connection',
    'get_shared_database_service',
    'close_all_database_pools',
    'get_database_stats',
    'database_health_check',

    # Connection pooling
    'get_pooled_connection',
    'close_pool',

    # Async support (if available)
    'ASYNC_AVAILABLE'
]

# Add async exports if available
if ASYNC_AVAILABLE:
    __all__.extend([
        'get_async_connection',
        'create_task_async',
        'get_tasks_by_status_async',
        'update_task_status_async',
        'get_task_async',
        'get_queued_tasks_async'
    ])