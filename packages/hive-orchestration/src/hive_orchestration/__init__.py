"""
Hive Orchestration Package - Platform Infrastructure (v1.0.0)

This package provides task orchestration and workflow management infrastructure
for the Hive platform. It replaces the platform app exception where ai-planner
and ai-deployer imported from hive_orchestrator.core.

========================================================================
PUBLIC API (v1.0.0)
========================================================================

Task Operations:
----------------
- create_task(task_type, payload, **kwargs) -> str
  Create a new orchestration task

- get_task(task_id) -> dict | None
  Retrieve task by ID

- update_task_status(task_id, status) -> None
  Update task execution status

- get_tasks_by_status(status) -> list[dict]
  Get all tasks with given status

- get_queued_tasks() -> list[dict]
  Get all queued tasks ready for execution

Worker Operations:
------------------
- register_worker(worker_type, capabilities) -> str
  Register a new worker

- update_worker_heartbeat(worker_id) -> None
  Update worker heartbeat timestamp

- get_active_workers() -> list[dict]
  Get all active workers

Execution Plans:
----------------
- create_planned_subtasks_from_plan(parent_task_id, plan) -> None
  Create subtasks from execution plan

- get_execution_plan_status(parent_task_id) -> dict
  Get execution plan status

- check_subtask_dependencies(subtask_id) -> bool
  Check if subtask dependencies are satisfied

- get_next_planned_subtask(parent_task_id) -> dict | None
  Get next ready subtask

Event Bus:
----------
- get_async_event_bus() -> AsyncEventBus
  Get async event bus instance

- TaskEvent: Task lifecycle events
- WorkflowEvent: Workflow lifecycle events
- AgentEvent: Agent lifecycle events

Usage Example:
--------------
```python
from hive_orchestration import (
    create_task,
    get_queued_tasks,
    update_task_status,
    get_async_event_bus,
    TaskEvent,
)

# Create and process task
task_id = await create_task("deployment", {"env": "prod"})
tasks = await get_queued_tasks()
await update_task_status(task_id, "running")

# Publish event
bus = get_async_event_bus()
await bus.publish(TaskEvent(task_id=task_id, event_type="started"))
```

========================================================================
MIGRATION FROM hive_orchestrator.core
========================================================================

Before:
-------
from hive_orchestrator.core.db import create_task, get_tasks_by_status
from hive_orchestrator.core.bus import get_async_event_bus

After:
------
from hive_orchestration import create_task, get_tasks_by_status, get_async_event_bus

========================================================================
DEPRECATION POLICY
========================================================================

This package follows semantic versioning (v1.0.0):
- Major version: Breaking changes (require code updates)
- Minor version: New features (backward compatible)
- Patch version: Bug fixes (backward compatible)

Breaking changes require:
1. One release cycle deprecation notice
2. Deprecation warnings in logs
3. Migration guide in documentation
4. Minimum 3-month notice period

========================================================================
"""
# ruff: noqa: E402
# Module-level docstring must precede imports for package documentation

# Import operations
# Import client SDK
from .client import OrchestrationClient, get_client

# Import event bus and events
from .events import AgentEvent, TaskEvent, WorkflowEvent, get_async_event_bus

# Import models
from .models import ExecutionPlan, PlanStatus, Run, RunStatus, SubTask, Task, TaskStatus, Worker, WorkerStatus
from .operations import (
    check_subtask_dependencies,
    check_subtask_dependencies_batch,
    create_planned_subtasks_from_plan,
    create_task,
    delete_task,
    get_active_workers,
    get_execution_plan_status,
    get_execution_plan_status_cached,
    get_next_planned_subtask,
    get_queued_tasks,
    get_task,
    get_tasks_by_status,
    get_worker,
    mark_plan_execution_started,
    register_worker,
    unregister_worker,
    update_task_status,
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
    # Models
    "Task",
    "TaskStatus",
    "Worker",
    "WorkerStatus",
    "Run",
    "RunStatus",
    "ExecutionPlan",
    "SubTask",
    "PlanStatus",
    # Client SDK
    "OrchestrationClient",
    "get_client",
    # Event bus
    "get_async_event_bus",
    "TaskEvent",
    "WorkflowEvent",
    "AgentEvent",
]

__version__ = "1.0.0"
