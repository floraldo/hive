# hive-orchestration

**Purpose**: Task orchestration and workflow management infrastructure for Hive platform

## Overview

The hive-orchestration package provides core orchestration capabilities for managing distributed task execution, worker coordination, and workflow tracking across the Hive platform.

## Core Features

- **Task Management**: Create, track, and manage task lifecycle
- **Worker Coordination**: Register and coordinate worker processes
- **Execution Planning**: Support for multi-step execution plans with dependencies
- **Event Bus Integration**: Task and workflow event publishing
- **Async Support**: Full async/await patterns for scalable orchestration

## Architecture

This package follows the inherit→extend pattern:
- **Inherits from**: hive-db, hive-bus, hive-async, hive-models
- **Extended by**: Apps that need orchestration (ai-planner, ai-deployer, hive-orchestrator)

## Public API (v1.0.0)

### Task Operations

```python
from hive_orchestration import (
    create_task,
    get_task,
    update_task_status,
    get_tasks_by_status,
    get_queued_tasks,
)

# Create a task
task_id = await create_task(
    task_type="deployment",
    payload={"script": "deploy.sh", "env": "production"},
    priority=5,
)

# Get task by ID
task = await get_task(task_id)

# Update task status
await update_task_status(task_id, "running")

# Get tasks by status
pending_tasks = await get_tasks_by_status("pending")
```

### Worker Operations

```python
from hive_orchestration import (
    register_worker,
    update_worker_heartbeat,
    get_active_workers,
)

# Register a worker
worker_id = await register_worker(
    worker_type="executor",
    capabilities=["python", "bash"],
)

# Update worker heartbeat
await update_worker_heartbeat(worker_id)

# Get active workers
workers = await get_active_workers()
```

### Execution Plans

```python
from hive_orchestration import (
    create_planned_subtasks_from_plan,
    get_execution_plan_status,
    check_subtask_dependencies,
    get_next_planned_subtask,
)

# Create subtasks from execution plan
await create_planned_subtasks_from_plan(parent_task_id, execution_plan)

# Check plan status
status = await get_execution_plan_status(parent_task_id)

# Check if subtask dependencies are satisfied
ready = await check_subtask_dependencies(subtask_id)

# Get next ready subtask
next_task = await get_next_planned_subtask(parent_task_id)
```

### Event Bus Integration

```python
from hive_orchestration import (
    get_async_event_bus,
    TaskEvent,
    WorkflowEvent,
)

# Get event bus
bus = get_async_event_bus()

# Publish task event
await bus.publish(TaskEvent(
    task_id=task_id,
    event_type="started",
    payload={"worker": worker_id},
))

# Publish workflow event
await bus.publish(WorkflowEvent(
    workflow_id=workflow_id,
    event_type="completed",
    payload={"duration": 120},
))
```

## Installation

```bash
# Development mode (from monorepo root)
poetry install

# Or add as dependency in another package
[tool.poetry.dependencies.hive-orchestration]
path = "../hive-orchestration"
develop = true
```

## Usage Example

### Using the Client SDK (Recommended)

```python
from hive_orchestration import get_client

# Get client instance
client = get_client()

# Register worker
client.register_worker("worker-1", role="executor", capabilities=["python", "bash"])

# Create task
task_id = client.create_task(
    title="Run analysis",
    task_type="analysis",
    payload={"script": "analyze.py"},
    priority=5,
)

# Get pending tasks
pending_tasks = client.get_pending_tasks(task_type="analysis")

# Process task
client.update_task_status(task_id, "running")

# Send worker heartbeat
client.heartbeat("worker-1", status="active")

# Complete task
client.update_task_status(task_id, "completed")
```

### Using Direct Operations (Advanced)

```python
from hive_orchestration import (
    create_task,
    register_worker,
    get_queued_tasks,
    update_task_status,
)

# Register worker
register_worker("worker-1", "executor", ["python"])

# Create task
task_id = create_task("python_script", payload={"script": "analyze.py"})

# Get queued tasks
tasks = get_queued_tasks()

# Process task
update_task_status(task_id, "running")
update_task_status(task_id, "completed")
```

## Migration from hive-orchestrator.core

This package replaces the platform app exception where ai-planner and ai-deployer imported from `hive_orchestrator.core.db` and `hive_orchestrator.core.bus`.

**Before**:
```python
from hive_orchestrator.core.db import create_task, get_tasks_by_status
from hive_orchestrator.core.bus import get_async_event_bus
```

**After**:
```python
from hive_orchestration import create_task, get_tasks_by_status, get_async_event_bus
```

## API Stability

This package follows semantic versioning (v1.0.0):
- **Major version**: Breaking changes (require code updates)
- **Minor version**: New features (backward compatible)
- **Patch version**: Bug fixes (backward compatible)

Breaking changes require:
1. One release cycle deprecation notice
2. Deprecation warnings in logs
3. Migration guide in documentation
4. Minimum 3-month notice period

## Dependencies

- **hive-logging**: Structured logging
- **hive-db**: Database abstractions
- **hive-bus**: Event bus infrastructure
- **hive-models**: Shared data models
- **hive-async**: Async utilities

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=hive_orchestration --cov-report=html

# Run specific test
pytest tests/test_task_operations.py
```

## Development

```bash
# Install dev dependencies
poetry install --with dev

# Run type checking
mypy src/hive_orchestration

# Format code
ruff check --fix src/
```

## Architecture Pattern

This package demonstrates the **platform infrastructure pattern**:
- Extracted from `hive-orchestrator.core` to eliminate platform app exception
- Provides stable public API for cross-app orchestration needs
- Maintains backward compatibility through clear deprecation policy
- Designed for extension via app-specific `core/` directories

For more information, see `.claude/ARCHITECTURE_PATTERNS.md`.
