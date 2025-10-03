# Phase 3 Quick-Start Guide - App Migrations

**Status**: Ready to Begin
**Prerequisites**: Phase 1 ✅ | Phase 2 ✅
**Estimated Time**: 2-4 hours

---

## Overview

Migrate ai-planner and ai-deployer from `hive_orchestrator.core` imports to `hive_orchestration` package.

---

## Pre-Migration Checklist

### Verify Package Ready ✅
```bash
# Check package structure
ls packages/hive-orchestration/src/hive_orchestration/

# Verify operations implemented
python -c "from hive_orchestration.operations.tasks import create_task; print('OK')"

# Check database module
python -c "from hive_orchestration.database import init_db; print('OK')"
```

### Identify Import Locations

**ai-planner imports**:
```bash
cd apps/ai-planner
grep -r "from hive_orchestrator" src/
```

Expected locations:
- `src/ai_planner/agent.py` (lines 25-32)
- `src/ai_planner/async_agent.py` (if exists)

**ai-deployer imports**:
```bash
cd apps/ai-deployer
grep -r "from hive_orchestrator" src/
```

Expected locations:
- `src/ai_deployer/agent.py` (lines 20-24)
- `src/ai_deployer/database_adapter.py`

---

## Migration Steps - ai-planner

### Step 1: Update Dependencies (5 min)

**File**: `apps/ai-planner/pyproject.toml`

Add dependency:
```toml
[tool.poetry.dependencies.hive-orchestration]
path = "../../packages/hive-orchestration"
develop = true
```

### Step 2: Update Imports (10 min)

**File**: `apps/ai-planner/src/ai_planner/agent.py`

**Before**:
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

**After**:
```python
from hive_orchestration import (
    create_task,
    get_tasks_by_status,
    update_task_status,
)
# Note: Async versions not yet implemented - use sync for now
```

### Step 3: Update Function Calls (5 min)

**Change async calls to sync** (temporary):
```python
# Before
tasks = await get_tasks_by_status_async("pending")

# After
tasks = get_tasks_by_status("pending")
```

### Step 4: Test (15 min)

```bash
cd apps/ai-planner

# Run tests
python -m pytest tests/ -v

# Manual test if needed
python -m ai_planner.agent --help
```

### Step 5: Remove Old Dependency (2 min)

**File**: `apps/ai-planner/pyproject.toml`

Remove or comment out:
```toml
# [tool.poetry.dependencies.hive-orchestrator]
# path = "../../apps/hive-orchestrator"
# develop = true
```

---

## Migration Steps - ai-deployer

### Step 1: Update Dependencies (5 min)

**File**: `apps/ai-deployer/pyproject.toml`

Add:
```toml
[tool.poetry.dependencies.hive-orchestration]
path = "../../packages/hive-orchestration"
develop = true
```

### Step 2: Update Imports (10 min)

**File**: `apps/ai-deployer/src/ai_deployer/agent.py`

**Before**:
```python
from hive_orchestrator.core.db import (
    get_async_connection,
    get_tasks_by_status_async,
    update_task_status_async,
)
```

**After**:
```python
from hive_orchestration import (
    get_tasks_by_status,
    update_task_status,
)
```

**File**: `apps/ai-deployer/src/ai_deployer/database_adapter.py`

Update any database operations to use package functions.

### Step 3: Update Function Calls (5 min)

Same pattern as ai-planner - convert async to sync temporarily.

### Step 4: Test (15 min)

```bash
cd apps/ai-deployer

# Run tests
python -m pytest tests/ -v

# Test deployment workflow
python -m ai_deployer.agent --help
```

### Step 5: Remove Old Dependency (2 min)

Remove hive-orchestrator from pyproject.toml.

---

## Validation Checklist

### Per-App Validation

**For each migrated app**:
- [ ] Package imports without errors
- [ ] All tests pass
- [ ] App starts without errors
- [ ] Core workflows functional
- [ ] No import errors in logs

### System-Wide Validation

- [ ] ai-planner can create tasks
- [ ] ai-deployer can query tasks
- [ ] hive-orchestrator still functional
- [ ] Database operations work
- [ ] No duplicate database access

---

## Common Issues & Solutions

### Issue 1: Async Operations Not Available

**Problem**: App uses `create_task_async` but package only has sync.

**Solution**:
```python
# Option 1: Use sync version
task_id = create_task(...)

# Option 2: Add async wrapper (temporary)
async def create_task_async(*args, **kwargs):
    import asyncio
    return await asyncio.to_thread(create_task, *args, **kwargs)
```

### Issue 2: Module Not Found

**Problem**: `ModuleNotFoundError: No module named 'hive_orchestration'`

**Solution**:
```bash
# Install package in development mode
cd packages/hive-orchestration
pip install -e .

# Or use poetry
poetry install
```

### Issue 3: Database Path Mismatch

**Problem**: App can't find orchestration database.

**Solution**:
```python
# Both use same default: hive/db/hive-internal.db
# Verify path in both:
from hive_orchestration.database.operations import _get_default_db_path
print(_get_default_db_path())
```

### Issue 4: Import Circular Dependencies

**Problem**: Circular import between package and app.

**Solution**:
- Ensure package doesn't import from apps
- Check core/ extensions are one-way

---

## Rollback Plan

If migration fails:

### Quick Rollback (5 min):
```bash
cd apps/ai-planner
git checkout pyproject.toml src/

cd apps/ai-deployer
git checkout pyproject.toml src/
```

### Coexistence Mode:
Both packages can coexist:
```python
# Old code continues to work
from hive_orchestrator.core.db import create_task

# New code uses package
from hive_orchestration import create_task as create_task_new
```

---

## Testing Strategy

### Unit Tests
```bash
# Test package in isolation
cd packages/hive-orchestration
python -m pytest tests/ -v
```

### Integration Tests
```bash
# Test app with package
cd apps/ai-planner
python -m pytest tests/ -v

cd apps/ai-deployer
python -m pytest tests/ -v
```

### End-to-End Test
```python
# Test full workflow
from hive_orchestration import get_client

client = get_client()

# Create task
task_id = client.create_task("Test Migration", "test")

# Query task
task = client.get_task(task_id)
assert task is not None

# Update task
success = client.update_task_status(task_id, "completed")
assert success is True
```

---

## Success Criteria

### Per-App Success:
- ✅ No import errors
- ✅ All existing tests pass
- ✅ App functionality unchanged
- ✅ Database operations work
- ✅ Logs show package usage

### Overall Success:
- ✅ Both apps migrated
- ✅ Platform app exception removable
- ✅ Architecture health 99%
- ✅ No regressions

---

## Time Estimates

**ai-planner Migration**: 35-40 minutes
- Dependencies: 5 min
- Imports: 10 min
- Function calls: 5 min
- Testing: 15 min
- Cleanup: 2 min

**ai-deployer Migration**: 35-40 minutes
- Same breakdown

**Total Phase 3**: 70-80 minutes (1-1.5 hours)

**With buffer for issues**: 2-3 hours

---

## Phase 4 Preview

After successful migration:

1. **Remove Platform Exception** (15 min):
   - Update golden rules validator
   - Remove DEPRECATED_PLATFORM_EXCEPTIONS
   - Run full validation

2. **Update Documentation** (30 min):
   - Mark platform exception as removed
   - Update architecture diagrams
   - Archive migration guide

3. **Final Validation** (15 min):
   - Run golden rules: `python scripts/validation/validate_golden_rules.py`
   - Verify architecture health: 99%
   - All apps using package

**Total Phase 4**: 1 hour

---

## Quick Commands Reference

```bash
# Find all orchestrator imports
grep -r "from hive_orchestrator" apps/

# Check package installed
python -c "import hive_orchestration; print(hive_orchestration.__version__)"

# Test basic operation
python -c "from hive_orchestration import get_client; print(get_client())"

# Run app tests
cd apps/ai-planner && python -m pytest tests/ -v
cd apps/ai-deployer && python -m pytest tests/ -v

# Validate golden rules
python scripts/validation/validate_golden_rules.py --level ERROR
```

---

**Ready to Start**: Phase 3 app migrations
**Estimated Time**: 2-3 hours
**Next File**: `apps/ai-planner/pyproject.toml`

---

*Quick-Start Guide - Phase 3*
*Created: 2025-10-02*
*Agent: pkg*
