# Hive Orchestration Package Migration Guide

**Status**: Package Created - Ready for Migration
**Target**: ai-planner, ai-deployer apps
**Timeline**: Q1 2026 (now accelerated to immediate)
**Priority**: Critical - Eliminates platform app exception

## Overview

The hive-orchestration package extracts shared orchestration functionality from `hive-orchestrator.core` into a proper infrastructure package. This eliminates the platform app exception where ai-planner and ai-deployer imported from another app's core.

## Migration Path

### Before (Platform App Exception)

```python
# ai-planner/agent.py
from hive_orchestrator.core.db import (
    create_task,
    get_tasks_by_status,
    update_task_status,
    create_task_async,
    get_tasks_by_status_async,
    update_task_status_async,
)
from hive_orchestrator.core.bus import get_async_event_bus
```

### After (Clean Architecture)

```python
# ai-planner/agent.py
from hive_orchestration import (
    get_client,
    create_task,
    get_tasks_by_status,
    update_task_status,
)
# Or use the client SDK (recommended)
from hive_orchestration import get_client

client = get_client()
task_id = client.create_task("My Task", "analysis")
```

## Step-by-Step Migration

### For ai-planner

**Current imports in `apps/ai-planner/src/ai_planner/agent.py`**:
```python
from hive_orchestrator.core.db import (
    create_task,
    create_task_async,
    get_async_connection,
    get_connection,
    get_tasks_by_status_async,
    update_task_status_async,
)
```

**New imports**:
```python
from hive_orchestration import (
    create_task,
    get_tasks_by_status,
    update_task_status,
)
# Note: Async versions will be implemented in Phase 2
```

**Migration steps**:
1. Add hive-orchestration to pyproject.toml dependencies
2. Replace `from hive_orchestrator.core.db import` with `from hive_orchestration import`
3. Update function calls (signatures remain the same)
4. Test with existing workflows
5. Remove hive_orchestrator dependency

### For ai-deployer

**Current imports in `apps/ai-deployer/src/ai_deployer/agent.py`**:
```python
from hive_orchestrator.core.db import (
    get_async_connection,
    get_tasks_by_status_async,
    update_task_status_async,
)
```

**New imports**:
```python
from hive_orchestration import (
    get_tasks_by_status,
    update_task_status,
)
# Note: Async versions will be implemented in Phase 2
```

**Migration steps**:
1. Add hive-orchestration to pyproject.toml dependencies
2. Replace orchestrator.core imports
3. Update database adapter if needed
4. Test deployment workflows
5. Remove hive_orchestrator dependency

## API Compatibility

### Function Signatures (100% Compatible)

All function signatures in hive-orchestration match the original orchestrator.core functions:

| Function | Signature | Status |
|----------|-----------|--------|
| `create_task` | `(title, task_type, description="", payload=None, **kwargs) -> str` | ✅ Compatible |
| `get_task` | `(task_id: str) -> dict \| None` | ✅ Compatible |
| `update_task_status` | `(task_id: str, status: str, metadata=None) -> bool` | ✅ Compatible |
| `get_tasks_by_status` | `(status: str) -> list[dict]` | ✅ Compatible |
| `get_queued_tasks` | `(limit=10, task_type=None) -> list[dict]` | ✅ Compatible |
| `register_worker` | `(worker_id, role, capabilities=None) -> bool` | ✅ Compatible |
| `update_worker_heartbeat` | `(worker_id, status=None) -> bool` | ✅ Compatible |
| `get_active_workers` | `(role=None) -> list[dict]` | ✅ Compatible |

### Models (Enhanced with Pydantic)

New Pydantic models provide type safety and validation:

```python
from hive_orchestration import Task, TaskStatus, Worker, WorkerStatus

# Create typed task
task = Task(
    title="My Task",
    task_type="analysis",
    priority=5,
)

# Use enum for status
task.status = TaskStatus.IN_PROGRESS

# Type-safe operations
if task.is_ready():
    task.start_execution()
```

## Client SDK (Recommended Approach)

The client SDK provides a simplified, high-level interface:

```python
from hive_orchestration import get_client

client = get_client()

# Task operations
task_id = client.create_task(
    title="Deploy app",
    task_type="deployment",
    payload={"env": "prod"},
)

# Get pending work
pending = client.get_pending_tasks(task_type="deployment")

# Worker operations
client.register_worker("worker-1", role="deployer", capabilities=["docker", "k8s"])
client.heartbeat("worker-1", status="active")

# Execution plans
client.start_plan_execution("plan-123")
next_task = client.get_next_subtask("plan-123")
```

## Implementation Phases

### Phase 1: Package Foundation (COMPLETE)
- ✅ Package structure created
- ✅ Interfaces extracted (18 operations)
- ✅ Models created (Task, Worker, Run, ExecutionPlan, SubTask)
- ✅ Client SDK implemented
- ✅ Documentation completed

### Phase 2: Implementation Wiring (NEXT)
- Connect operations to hive-orchestrator database implementations
- Add async support for operations
- Implement event bus integration
- Add connection pooling

### Phase 3: App Migrations (READY)
- Migrate ai-planner to use package
- Migrate ai-deployer to use package
- Update tests
- Verify functionality

### Phase 4: Cleanup (FINAL)
- Remove platform app exception from golden rules
- Update architecture documentation
- Remove orchestrator.core public API documentation
- Archive migration guide

## Testing Strategy

### Unit Tests
```python
# Test models
from hive_orchestration import Task, TaskStatus

def test_task_lifecycle():
    task = Task(title="Test", task_type="test")
    assert task.status == TaskStatus.QUEUED

    task.start_execution()
    assert task.status == TaskStatus.IN_PROGRESS
```

### Integration Tests
```python
# Test operations
from hive_orchestration import get_client

def test_task_creation():
    client = get_client()
    task_id = client.create_task("Test Task", "test")

    task = client.get_task(task_id)
    assert task is not None
    assert task["title"] == "Test Task"
```

## Rollback Plan

If migration issues occur:

1. **Revert imports**: Change back to `hive_orchestrator.core.db` imports
2. **Keep package**: hive-orchestration can coexist with orchestrator.core
3. **Debug**: Package is designed for gradual migration
4. **No data loss**: All operations use same underlying database

## Benefits After Migration

### Architectural Health
- ✅ **Eliminates platform app exception**: Clean three-layer architecture
- ✅ **Proper dependency flow**: packages → app.core → app logic
- ✅ **Reusable infrastructure**: Other apps can use orchestration
- ✅ **Clear boundaries**: Packages don't import from apps

### Code Quality
- ✅ **Type safety**: Pydantic models with validation
- ✅ **Better testing**: Package can be tested independently
- ✅ **Clear API**: Documented public interface with versioning
- ✅ **Simplified usage**: Client SDK reduces boilerplate

### Maintainability
- ✅ **Semantic versioning**: v1.0.0 with deprecation policy
- ✅ **Backward compatibility**: 3-month deprecation notices
- ✅ **Migration guides**: Clear upgrade paths
- ✅ **Independent evolution**: Package and apps evolve separately

## Support and Questions

- **Package README**: `packages/hive-orchestration/README.md`
- **Architecture docs**: `.claude/ARCHITECTURE_PATTERNS.md`
- **Migration support**: This document
- **API reference**: Package docstrings and README

## Timeline

**Immediate Next Steps**:
1. Wire operations to orchestrator database (Phase 2)
2. Migrate ai-planner (Phase 3.1)
3. Migrate ai-deployer (Phase 3.2)
4. Remove platform exception (Phase 4)

**Expected Duration**: 2-3 days for full migration

---

*Generated: 2025-10-02*
*Package Version: 1.0.0*
*Status: Ready for Implementation*
