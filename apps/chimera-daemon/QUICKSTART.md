# Chimera Daemon - Quick Start Guide

**Layer 2 - Parallel Execution** (Week 3-4 Complete)

Multi-line autonomous development factory with 5-10 concurrent workflows.

This guide gets you up and running with the Chimera Daemon parallel execution system in 5 minutes.

---

## Prerequisites

- Python 3.11+
- Hive platform (with packages installed)
- FastAPI, uvicorn, pydantic, aiosqlite

---

## Installation

### Option 1: Using pip (without Poetry)

```bash
cd apps/chimera-daemon

# Install dependencies
pip install fastapi uvicorn[standard] pydantic pydantic-settings aiosqlite httpx pytest pytest-asyncio

# Install local hive packages (from repository root)
cd ../..
pip install -e packages/hive-logging
pip install -e packages/hive-config
pip install -e packages/hive-orchestration
pip install -e packages/hive-db

# Back to chimera-daemon
cd apps/chimera-daemon
```

### Option 2: Using Poetry (if available)

```bash
cd apps/chimera-daemon
poetry install
```

---

## Quick Test

### 1. Verify Imports

```bash
python -c "import sys; sys.path.insert(0, 'src'); from chimera_daemon.task_queue import TaskQueue; print('OK')"
python -c "import sys; sys.path.insert(0, 'src'); from chimera_daemon.daemon import ChimeraDaemon; print('OK')"
python -c "import sys; sys.path.insert(0, 'src'); from chimera_daemon.api import create_app; print('OK')"
```

### 2. Run Tests

```bash
# Run all tests (unit + integration)
pytest tests/ -v

# Expected: 14/14 tests passing (1 skipped E2E test)
# - 7 unit tests (task_queue)
# - 5 integration tests (REST API)
# - 2 integration tests (daemon + metrics)
```

---

## Running the Daemon

### Method 1: CLI (Recommended for Development)

```bash
# Option A: Just the daemon (background processor)
PYTHONPATH=src python -m chimera_daemon.cli start

# Option B: Just the API (submit/status endpoints)
PYTHONPATH=src python -m chimera_daemon.cli api

# Option C: Both daemon + API (development mode)
PYTHONPATH=src python -m chimera_daemon.cli start-all
```

### Method 2: Programmatic

```python
import asyncio
import sys
sys.path.insert(0, 'src')

from chimera_daemon.daemon import ChimeraDaemon

async def main():
    daemon = ChimeraDaemon(poll_interval=1.0)
    await daemon.start()

asyncio.run(main())
```

---

## Usage Examples

### Submit Task via API

```bash
# Start daemon + API in Terminal 1
PYTHONPATH=src python -m chimera_daemon.cli start-all

# In Terminal 2: Submit task
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "User can view homepage",
    "target_url": "https://example.com",
    "priority": 5
  }'

# Response:
# {
#   "task_id": "chimera-abc123456789",
#   "status": "queued",
#   "created_at": "2025-10-04T..."
# }
```

### Check Task Status

```bash
# Get task status
curl http://localhost:8000/api/tasks/chimera-abc123456789

# Response (while running):
# {
#   "task_id": "chimera-abc123456789",
#   "status": "running",
#   "phase": "CODE_IMPLEMENTATION",
#   "progress": "2/7 phases complete",
#   ...
# }

# Response (when complete):
# {
#   "task_id": "chimera-abc123456789",
#   "status": "completed",
#   "phase": "COMPLETE",
#   "result": {
#     "test_path": "tests/e2e/test_user_can_view_homepage.py",
#     "code_pr_id": "local-chimera-abc123",
#     "review_decision": "approved",
#     "deployment_url": "file:///.../staging/...",
#     "validation_status": "passed"
#   },
#   "duration": 32.4
# }
```

### Health Check

```bash
curl http://localhost:8000/health

# Response:
# {
#   "status": "healthy",
#   "uptime": 3600,
#   "tasks_queued": 5,
#   "tasks_running": 2,
#   "tasks_completed": 147,
#   "tasks_failed": 3
# }
```

---

## Validation

### Automated Validation Script

```bash
# Terminal 1: Start daemon
PYTHONPATH=src python -m chimera_daemon.cli start-all

# Terminal 2: Run validation
PYTHONPATH=src python scripts/validate_autonomous_execution.py
```

**Expected Output**:
```
[1/5] Checking daemon status...
   ✅ Daemon is running

[2/5] Submitting task via API...
   ✅ Task submitted: chimera-abc123

[3/5] Monitoring autonomous execution...
   Phase: E2E_TEST_GENERATION (1/7)
   Phase: CODE_IMPLEMENTATION (2/7)
   ...
   Phase: COMPLETE (7/7)

[4/5] Workflow execution finished (32.4s)

[5/5] Final Result:
   ✅ AUTONOMOUS EXECUTION SUCCESSFUL!

✅ Layer 2 (Autonomous Execution) VALIDATED
```

---

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'chimera_daemon'`

**Solution**: Add src to Python path:
```bash
export PYTHONPATH=src:$PYTHONPATH
# Or on Windows:
set PYTHONPATH=src;%PYTHONPATH%
```

### Database Errors

**Problem**: `sqlite3.OperationalError: no such table: tasks`

**Solution**: Database not initialized. Ensure daemon starts properly:
```python
from chimera_daemon.task_queue import TaskQueue
queue = TaskQueue("tasks.db")
await queue.initialize()  # Creates tables
```

### Port Already in Use

**Problem**: `OSError: [Errno 98] Address already in use`

**Solution**: Change API port:
```bash
PYTHONPATH=src python -c "
from chimera_daemon.api import create_app
import uvicorn
app = create_app()
uvicorn.run(app, host='0.0.0.0', port=8001)  # Use different port
"
```

### Missing Hive Packages

**Problem**: `ModuleNotFoundError: No module named 'hive_logging'`

**Solution**: Install hive packages:
```bash
cd ../..  # Go to repo root
pip install -e packages/hive-logging
pip install -e packages/hive-config
pip install -e packages/hive-orchestration
pip install -e packages/hive-db
```

---

## What's Next

### Week 1-2 (Current): Foundation ✅
- ✅ Background daemon
- ✅ Task queue with SQLite
- ✅ REST API
- ✅ Unit tests

### Week 3-4: Parallel Execution
- ExecutorPool (5-10 concurrent workers)
- Task prioritization
- Resource management

### Week 5-6: Monitoring
- Advanced health metrics
- Error recovery
- Comprehensive logging

### Week 7-8: Production Deployment
- Systemd service
- Docker container
- Production guide

---

## Key Files

- `src/chimera_daemon/daemon.py` - ChimeraDaemon (background service)
- `src/chimera_daemon/task_queue.py` - TaskQueue (SQLite queue)
- `src/chimera_daemon/api.py` - REST API (FastAPI)
- `src/chimera_daemon/cli.py` - CLI commands
- `tests/unit/test_task_queue.py` - Unit tests
- `scripts/validate_autonomous_execution.py` - E2E validation

---

## Summary

**Before (Layer 1)**:
```python
# Human-triggered, terminal-bound
workflow = await executor.execute_workflow(task)  # BLOCKS
```

**After (Layer 2)**:
```bash
# Autonomous, background execution
curl -X POST http://localhost:8000/api/tasks -d '{...}'  # Submit once
# Close terminal - daemon keeps running
# Check result later: curl http://localhost:8000/api/tasks/{id}
```

**Status**: Layer 2 foundation complete, ready for production enhancements (Week 3-8)

---

**For Questions**: See `README.md` or `claudedocs/PROJECT_COLOSSUS_LAYER_2_WEEK_1_2_COMPLETE.md`
