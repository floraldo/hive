# Hive-Orchestration Package Extraction Plan

**Version**: 1.0.0
**Date**: 2025-09-30
**Effort**: 20 working days (~4 weeks)
**Priority**: MEDIUM (Q1 2026)
**Status**: PLANNED

---

## Executive Summary

Extract shared orchestration infrastructure from `hive-orchestrator.core` into a new `hive-orchestration` package to fix architectural violations and improve modular monolith design.

**Problem**: 3 apps import from `hive-orchestrator.core` (architectural smell - apps shouldn't import from other apps)

**Solution**: Create `hive-orchestration` package with clear interfaces, data models, and client SDK

**Timeline**: 4 weeks, 10 phases, staged rollout

---

## Why Extract to Package?

### Current Architectural Issues

**The Smell**:
```python
# ❌ CURRENT - Apps importing from another app's core
from hive_orchestrator.core.db import create_task  # ai-planner
from hive_orchestrator.core.bus import get_async_event_bus  # ai-deployer
```

**Problems**:
1. **Tight Coupling**: ai-planner/ai-deployer depend on orchestrator's internal implementation
2. **Deployment Dependency**: Can't deploy ai-planner without deploying hive-orchestrator
3. **Breaking Changes**: Orchestrator refactoring breaks dependent apps
4. **Testing Complexity**: Can't unit test ai-planner without full orchestrator
5. **Unclear Contract**: No interface boundary, just direct implementation access
6. **Violates Principles**: Modular monolith means apps use packages, not each other

### The Solution: Extract to Package

**Proper Architecture**:
```python
# ✅ FUTURE - Apps importing from shared package
from hive_orchestration import OrchestrationClient
from hive_orchestration.models import Task, Worker
from hive_orchestration.events import TaskCreatedEvent
```

**Benefits**:
- ✅ **Clear Contracts**: Well-defined interfaces and protocols
- ✅ **Independent Deployment**: Package is versioned dependency, not app
- ✅ **Stable API**: Semantic versioning with deprecation policy
- ✅ **Easy Testing**: Mock package interfaces, not entire app
- ✅ **Proper Modular Monolith**: Apps → packages (not apps → apps)
- ✅ **Future-Proof**: Other apps can use orchestration without coupling

---

## Scope Analysis

### Current State

**Orchestrator Core Structure**:
```
apps/hive-orchestrator/src/hive_orchestrator/core/
├── __init__.py          # Public API documentation
├── bus/                 # Event bus (shared) ← EXTRACT
├── claude/              # Claude integration (private) ← KEEP
├── db/                  # Database operations (shared) ← EXTRACT
├── errors/              # Error handling (private) ← KEEP
└── monitoring/          # Monitoring (private) ← KEEP
```

**Statistics**:
- Total files: 40 Python files
- Total LOC: ~1,155 lines
- Shared logic (db + bus): ~1,000 LOC
- Private logic (claude, errors, monitoring): ~155 LOC

**Import Usage**:
- ai-planner: 7 imports from orchestrator.core
- ai-deployer: Unknown (needs investigation)
- Estimated total: ~10-15 import statements to migrate

### Extraction Targets

**What Gets Extracted** (becomes `hive-orchestration` package):

**1. Task Database Operations** (~800 LOC)
```python
# From orchestrator.core.db
- create_task, get_task, update_task_status
- get_tasks_by_status, get_queued_tasks
- create_run, get_run, update_run_status
- register_worker, get_active_workers, update_worker_heartbeat
- AsyncDatabaseOperations class
- Planning integration (create_planned_subtasks, etc.)
```

**2. Event Bus** (~200 LOC)
```python
# From orchestrator.core.bus
- get_async_event_bus
- OrchestrationEventBus
- Task lifecycle events (TaskCreatedEvent, etc.)
- Worker events
```

**What Stays in Orchestrator** (private implementation):

**3. Private Logic** (~155 LOC)
```python
# Stays in orchestrator.core
- core.claude: Claude AI integration (orchestrator-specific)
- core.monitoring: Internal monitoring logic
- core.errors.hive_errors: Internal error handling
```

---

## Package Design

### Package Structure

```
packages/hive-orchestration/
├── src/hive_orchestration/
│   ├── __init__.py                    # Public API exports
│   │
│   ├── interfaces/                    # Protocol definitions
│   │   ├── __init__.py
│   │   ├── task_protocol.py          # TaskOperations protocol
│   │   ├── worker_protocol.py        # WorkerOperations protocol
│   │   └── event_protocol.py         # EventBus protocol
│   │
│   ├── models/                        # Data models (Pydantic)
│   │   ├── __init__.py
│   │   ├── task.py                   # Task model
│   │   ├── worker.py                 # Worker model
│   │   ├── execution_plan.py         # ExecutionPlan model
│   │   └── enums.py                  # TaskStatus, WorkerStatus
│   │
│   ├── database/                      # Database operations
│   │   ├── __init__.py
│   │   ├── schema.py                 # Schema definitions
│   │   ├── operations.py             # CRUD operations
│   │   ├── connection.py             # Connection management
│   │   └── async_operations.py       # Async database ops
│   │
│   ├── events/                        # Event system
│   │   ├── __init__.py
│   │   ├── base.py                   # Base event classes
│   │   ├── task_events.py            # Task lifecycle events
│   │   └── worker_events.py          # Worker events
│   │
│   ├── client/                        # High-level SDK
│   │   ├── __init__.py
│   │   └── orchestration_client.py   # OrchestrationClient
│   │
│   └── exceptions.py                  # Package exceptions
│
├── tests/
│   ├── test_interfaces.py
│   ├── test_models.py
│   ├── test_database.py
│   ├── test_events.py
│   ├── test_client.py
│   └── integration/
│       ├── test_full_workflow.py
│       └── test_async_operations.py
│
├── pyproject.toml
├── README.md
└── CHANGELOG.md
```

### Public API Design

**Simple Client API** (most apps will use this):
```python
from hive_orchestration import OrchestrationClient

# Initialize
client = OrchestrationClient()

# Task management
task_id = await client.create_task(
    task_type="deployment",
    payload={"script": "deploy.sh", "env": "production"}
)

task = await client.get_task(task_id)
await client.update_task_status(task_id, "completed")

tasks = await client.get_tasks_by_status("pending")

# Worker management
await client.register_worker(
    worker_id="worker-1",
    capabilities=["python", "docker"]
)

workers = await client.get_active_workers()
await client.update_worker_heartbeat("worker-1")

# Event coordination
await client.subscribe_to_task_events(task_id, callback_function)
await client.publish_task_event(TaskCompletedEvent(task_id=task_id))
```

**Advanced API** (for custom implementations):
```python
from hive_orchestration.interfaces import TaskOperations
from hive_orchestration.models import Task, TaskStatus
from hive_orchestration.database import TaskDatabase

# Custom implementation
class MyTaskService(TaskOperations):
    def __init__(self, db_path: str):
        self.db = TaskDatabase(db_path)

    def create_task(self, task_type: str, payload: dict) -> str:
        task = Task(type=task_type, payload=payload, status=TaskStatus.PENDING)
        return self.db.save(task)
```

### Dependencies

**Required Packages**:
```toml
[tool.poetry.dependencies]
python = "^3.11"
pydantic = "^2.0.0"

# Hive platform packages
hive-logging = {path = "../hive-logging", develop = true}
hive-db = {path = "../hive-db", develop = true}
hive-bus = {path = "../hive-bus", develop = true}
hive-models = {path = "../hive-models", develop = true}
hive-errors = {path = "../hive-errors", develop = true}
hive-async = {path = "../hive-async", develop = true}
```

**Why These Dependencies**:
- `hive-logging`: Structured logging
- `hive-db`: SQLite connection pooling and utilities
- `hive-bus`: Event bus base classes
- `hive-models`: Shared data model utilities
- `hive-errors`: Error handling base classes
- `hive-async`: Async utilities and patterns

---

## Implementation Phases

### Phase 1: Package Scaffolding (Days 1-2)

**Objective**: Create package structure with interfaces and models

**Tasks**:

1. **Create Package Directory**
   ```bash
   mkdir -p packages/hive-orchestration/src/hive_orchestration
   mkdir -p packages/hive-orchestration/tests
   ```

2. **Create pyproject.toml**
   ```toml
   [tool.poetry]
   name = "hive-orchestration"
   version = "0.1.0"
   description = "Orchestration infrastructure for Hive platform"
   authors = ["Hive Team"]
   packages = [{include = "hive_orchestration", from = "src"}]
   ```

3. **Define Interfaces** (interfaces/task_protocol.py)
   ```python
   from typing import Protocol
   from hive_orchestration.models import Task

   class TaskOperations(Protocol):
       """Protocol for task operations"""

       def create_task(self, task_type: str, payload: dict) -> str:
           """Create a new task"""
           ...

       def get_task(self, task_id: str) -> Task | None:
           """Get task by ID"""
           ...

       def update_task_status(self, task_id: str, status: str) -> None:
           """Update task status"""
           ...
   ```

4. **Define Models** (models/task.py)
   ```python
   from pydantic import BaseModel
   from datetime import datetime
   from hive_orchestration.models.enums import TaskStatus

   class Task(BaseModel):
       id: str
       type: str
       status: TaskStatus
       payload: dict
       created_at: datetime
       updated_at: datetime
   ```

5. **Write Initial Tests**
   ```python
   # tests/test_models.py
   def test_task_model_creation():
       task = Task(
           id="task-1",
           type="deployment",
           status=TaskStatus.PENDING,
           payload={"script": "deploy.sh"}
       )
       assert task.type == "deployment"
   ```

**Deliverables**:
- Package structure created
- Interfaces defined (TaskOperations, WorkerOperations, EventProtocol)
- Models defined (Task, Worker, ExecutionPlan)
- Basic tests passing

**Validation**:
```bash
cd packages/hive-orchestration
poetry install
pytest tests/
```

---

### Phase 2: Extract Database Layer (Days 3-5)

**Objective**: Move task/worker database operations to package

**Tasks**:

1. **Extract Task Operations** (from orchestrator.core.db.database.py)
   ```python
   # packages/hive-orchestration/src/hive_orchestration/database/operations.py

   from hive_db import get_sqlite_connection
   from hive_logging import get_logger
   from hive_orchestration.models import Task, TaskStatus

   logger = get_logger(__name__)

   class TaskDatabase:
       def __init__(self, db_path: str):
           self.db_path = db_path
           self._ensure_schema()

       def create_task(self, task_type: str, payload: dict) -> str:
           """Create a new orchestration task"""
           task_id = str(uuid.uuid4())
           with get_sqlite_connection(self.db_path) as conn:
               conn.execute(
                   """
                   INSERT INTO tasks (id, type, status, payload, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   """,
                   (task_id, task_type, TaskStatus.PENDING.value,
                    json.dumps(payload), datetime.now(UTC))
               )
           logger.info(f"Created task {task_id}")
           return task_id

       def get_task(self, task_id: str) -> Task | None:
           """Get task by ID"""
           with get_sqlite_connection(self.db_path) as conn:
               row = conn.execute(
                   "SELECT * FROM tasks WHERE id = ?",
                   (task_id,)
               ).fetchone()
               if row:
                   return Task.from_db_row(row)
           return None
   ```

2. **Extract Async Operations** (async_operations.py)
   ```python
   # Async versions using hive-async utilities
   from hive_async import async_retry

   class AsyncTaskDatabase:
       async def create_task_async(self, task_type: str, payload: dict) -> str:
           return await async_retry(
               lambda: self._create_task_sync(task_type, payload),
               max_attempts=3
           )
   ```

3. **Create Schema Management** (schema.py)
   ```python
   ORCHESTRATION_SCHEMA = """
   CREATE TABLE IF NOT EXISTS tasks (
       id TEXT PRIMARY KEY,
       type TEXT NOT NULL,
       status TEXT NOT NULL,
       payload TEXT NOT NULL,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
   CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
   """
   ```

4. **Write Comprehensive Tests**
   ```python
   # tests/test_database.py

   def test_create_task(test_db):
       db = TaskDatabase(test_db)
       task_id = db.create_task("deployment", {"script": "deploy.sh"})

       task = db.get_task(task_id)
       assert task.type == "deployment"
       assert task.status == TaskStatus.PENDING

   @pytest.mark.asyncio
   async def test_create_task_async(test_db):
       db = AsyncTaskDatabase(test_db)
       task_id = await db.create_task_async("deployment", {"script": "deploy.sh"})
       assert task_id is not None
   ```

**Key Functions to Extract**:
- create_task, get_task, update_task_status, delete_task
- get_tasks_by_status, get_queued_tasks, get_completed_tasks
- create_run, get_run, update_run_status
- register_worker, get_worker, update_worker_heartbeat, get_active_workers
- Planning: create_planned_subtasks, get_execution_plan_status, get_next_planned_subtask

**Deliverables**:
- Database operations in package
- Schema management
- Async operations
- 80%+ test coverage

**Validation**:
```bash
pytest tests/test_database.py -v --cov=hive_orchestration.database
```

---

### Phase 3: Extract Event Bus (Days 6-7)

**Objective**: Move orchestration events to package

**Tasks**:

1. **Define Event Base Classes** (events/base.py)
   ```python
   from hive_bus import BaseEvent
   from hive_orchestration.models import Task

   class OrchestrationEvent(BaseEvent):
       """Base class for orchestration events"""

       def __init__(self, event_type: str, **kwargs):
           super().__init__(event_type, source="orchestration", **kwargs)
   ```

2. **Define Task Events** (events/task_events.py)
   ```python
   class TaskCreatedEvent(OrchestrationEvent):
       def __init__(self, task_id: str, task_type: str, payload: dict):
           super().__init__(
               event_type="task.created",
               task_id=task_id,
               task_type=task_type,
               payload=payload
           )

   class TaskStartedEvent(OrchestrationEvent):
       def __init__(self, task_id: str, worker_id: str):
           super().__init__(
               event_type="task.started",
               task_id=task_id,
               worker_id=worker_id
           )

   class TaskCompletedEvent(OrchestrationEvent):
       def __init__(self, task_id: str, result: dict):
           super().__init__(
               event_type="task.completed",
               task_id=task_id,
               result=result
           )
   ```

3. **Create Event Bus Wrapper** (events/orchestration_bus.py)
   ```python
   from hive_bus import BaseBus

   class OrchestrationEventBus(BaseBus):
       """Event bus for orchestration events"""

       async def publish_task_event(self, event: OrchestrationEvent):
           """Publish task-related event"""
           await self.publish(event)

       async def subscribe_to_task(self, task_id: str, callback):
           """Subscribe to all events for a specific task"""
           await self.subscribe(f"task.*", callback, filter={"task_id": task_id})
   ```

4. **Write Event Tests**
   ```python
   # tests/test_events.py

   @pytest.mark.asyncio
   async def test_task_created_event():
       bus = OrchestrationEventBus()
       events_received = []

       async def handler(event):
           events_received.append(event)

       await bus.subscribe("task.created", handler)

       event = TaskCreatedEvent(
           task_id="task-1",
           task_type="deployment",
           payload={"script": "deploy.sh"}
       )
       await bus.publish_task_event(event)

       await asyncio.sleep(0.1)  # Wait for event processing
       assert len(events_received) == 1
       assert events_received[0].task_id == "task-1"
   ```

**Deliverables**:
- Event classes defined
- Event bus wrapper
- Event tests

**Validation**:
```bash
pytest tests/test_events.py -v
```

---

### Phase 4: Create Client SDK (Days 8-9)

**Objective**: High-level client API combining database + events

**Tasks**:

1. **Create OrchestrationClient** (client/orchestration_client.py)
   ```python
   from hive_orchestration.database import TaskDatabase, AsyncTaskDatabase
   from hive_orchestration.events import OrchestrationEventBus, TaskCreatedEvent
   from hive_orchestration.models import Task

   class OrchestrationClient:
       """High-level client for orchestration operations"""

       def __init__(self, db_path: str = None, event_bus: OrchestrationEventBus = None):
           self.db_path = db_path or self._get_default_db_path()
           self.task_db = AsyncTaskDatabase(self.db_path)
           self.event_bus = event_bus or OrchestrationEventBus()

       async def create_task(self, task_type: str, payload: dict) -> str:
           """Create task and publish event"""
           task_id = await self.task_db.create_task_async(task_type, payload)

           # Publish event
           await self.event_bus.publish_task_event(
               TaskCreatedEvent(task_id=task_id, task_type=task_type, payload=payload)
           )

           return task_id

       async def get_task(self, task_id: str) -> Task | None:
           """Get task by ID"""
           return await self.task_db.get_task_async(task_id)

       async def update_task_status(self, task_id: str, status: str) -> None:
           """Update task status and publish event"""
           await self.task_db.update_task_status_async(task_id, status)

           # Publish appropriate event
           if status == "completed":
               await self.event_bus.publish_task_event(
                   TaskCompletedEvent(task_id=task_id, result={})
               )

       async def subscribe_to_task_events(self, task_id: str, callback):
           """Subscribe to all events for a task"""
           await self.event_bus.subscribe_to_task(task_id, callback)
   ```

2. **Add Convenience Methods**
   ```python
   async def get_pending_tasks(self) -> list[Task]:
       """Get all pending tasks"""
       return await self.task_db.get_tasks_by_status_async("pending")

   async def get_active_workers(self) -> list[Worker]:
       """Get all active workers"""
       return await self.worker_db.get_active_workers_async()
   ```

3. **Write Client Tests**
   ```python
   # tests/test_client.py

   @pytest.mark.asyncio
   async def test_client_create_task():
       client = OrchestrationClient(db_path=":memory:")

       task_id = await client.create_task(
           task_type="deployment",
           payload={"script": "deploy.sh"}
       )

       task = await client.get_task(task_id)
       assert task.type == "deployment"
       assert task.status == TaskStatus.PENDING

   @pytest.mark.asyncio
   async def test_client_task_lifecycle():
       client = OrchestrationClient(db_path=":memory:")

       # Track events
       events = []
       await client.subscribe_to_task_events("*", lambda e: events.append(e))

       # Create task
       task_id = await client.create_task("deployment", {})

       # Update status
       await client.update_task_status(task_id, "running")
       await client.update_task_status(task_id, "completed")

       # Check events
       await asyncio.sleep(0.1)
       assert len(events) == 3  # created, started, completed
   ```

**Deliverables**:
- OrchestrationClient SDK
- Convenience methods
- Comprehensive tests

**Validation**:
```bash
pytest tests/test_client.py -v
```

---

### Phase 5: Update hive-orchestrator (Days 10-12)

**Objective**: Make orchestrator use the new package

**Tasks**:

1. **Add Package Dependency** (orchestrator/pyproject.toml)
   ```toml
   [tool.poetry.dependencies]
   hive-orchestration = {path = "../../packages/hive-orchestration", develop = true}
   ```

2. **Update Imports**
   ```python
   # orchestrator/queen.py
   # BEFORE
   from hive_orchestrator.core.db import create_task, get_queued_tasks

   # AFTER
   from hive_orchestration import OrchestrationClient

   client = OrchestrationClient()
   task_id = await client.create_task(task_type, payload)
   tasks = await client.get_pending_tasks()
   ```

3. **Keep Private Core Modules**
   ```
   hive-orchestrator/core/
   ├── claude/          # KEEP - orchestrator-specific Claude integration
   ├── monitoring/      # KEEP - orchestrator-specific monitoring
   └── errors/          # KEEP - orchestrator-specific error handling
   ```

4. **Update Tests**
   ```python
   # tests/test_queen.py
   from hive_orchestration import OrchestrationClient

   @pytest.fixture
   def orchestration_client():
       return OrchestrationClient(db_path=":memory:")

   def test_queen_creates_task(orchestration_client):
       queen = Queen(client=orchestration_client)
       task_id = queen.create_task("deployment", {})
       assert task_id is not None
   ```

5. **Run Full Test Suite**
   ```bash
   cd apps/hive-orchestrator
   pytest tests/ -v
   ```

**Deliverables**:
- Orchestrator using package
- Private logic preserved
- All tests passing

**Validation**:
```bash
cd apps/hive-orchestrator
pytest tests/ --cov=hive_orchestrator
```

---

### Phase 6: Migrate ai-planner (Days 13-14)

**Objective**: Replace orchestrator.core imports with package

**Tasks**:

1. **Update Dependencies** (ai-planner/pyproject.toml)
   ```toml
   [tool.poetry.dependencies]
   # REMOVE
   # hive-orchestrator = {path = "../hive-orchestrator", develop = true}

   # ADD
   hive-orchestration = {path = "../../packages/hive-orchestration", develop = true}
   ```

2. **Replace Imports** (ai-planner/agent.py)
   ```python
   # BEFORE
   from hive_orchestrator.core.db import (
       create_task,
       get_connection,
       AsyncDatabaseOperations,
       get_async_db_operations,
   )
   from hive_orchestrator.core.bus import get_async_event_bus

   # AFTER
   from hive_orchestration import OrchestrationClient
   from hive_orchestration.models import Task, TaskStatus
   from hive_orchestration.events import TaskCreatedEvent

   # Use client
   client = OrchestrationClient()
   task_id = await client.create_task(task_type, payload)
   ```

3. **Update All 7 Import Locations**
   ```bash
   grep -r "from hive_orchestrator.core" apps/ai-planner/src/
   # Replace each instance with package import
   ```

4. **Update Tests**
   ```python
   # tests/test_agent.py
   from hive_orchestration import OrchestrationClient

   @pytest.fixture
   def mock_client():
       return OrchestrationClient(db_path=":memory:")

   def test_planner_creates_execution_plan(mock_client):
       planner = PlannerAgent(client=mock_client)
       plan = planner.create_execution_plan(task)
       assert plan is not None
   ```

5. **Validate Migration**
   ```bash
   cd apps/ai-planner
   poetry install
   pytest tests/ -v
   python -m ai_planner.agent --test
   ```

**Deliverables**:
- ai-planner using hive-orchestration package
- No orchestrator dependency
- All tests passing

**Validation**:
```bash
cd apps/ai-planner
pytest tests/ --cov=ai_planner
python -m ai_planner.agent --test
```

---

### Phase 7: Migrate ai-deployer (Day 15)

**Objective**: Replace orchestrator.core imports in ai-deployer

**Tasks**:

1. **Investigate Current Usage**
   ```bash
   grep -r "from hive_orchestrator.core" apps/ai-deployer/src/
   ```

2. **Update Dependencies** (ai-deployer/pyproject.toml)
   ```toml
   [tool.poetry.dependencies]
   # REMOVE orchestrator dependency
   # ADD hive-orchestration
   hive-orchestration = {path = "../../packages/hive-orchestration", develop = true}
   ```

3. **Replace Imports** (similar pattern to ai-planner)

4. **Update Tests**

5. **Validate**

**Deliverables**:
- ai-deployer using package
- All tests passing

---

### Phase 8: Update Golden Rules (Day 16)

**Objective**: Remove platform app exceptions

**Tasks**:

1. **Update Validator** (packages/hive-tests/src/hive_tests/ast_validator.py)
   ```python
   # REMOVE
   PLATFORM_APP_EXCEPTIONS = {
       "hive_orchestrator.core.db": ["ai_planner", "ai_deployer"],
       "hive_orchestrator.core.bus": ["ai_planner", "ai_deployer"],
   }

   # Platform exceptions no longer needed - apps use hive-orchestration package
   ```

2. **Run Full Validation**
   ```bash
   python scripts/validation/validate_golden_rules.py --level ERROR
   ```

3. **Update Documentation** (.claude/ARCHITECTURE_PATTERNS.md)
   ```markdown
   # REMOVE Platform App Exception section

   # ADD hive-orchestration Usage section
   ## Using hive-orchestration Package

   All apps needing orchestration should use hive-orchestration:

   ```python
   from hive_orchestration import OrchestrationClient
   client = OrchestrationClient()
   ```
   ```

4. **Update CLAUDE.md**
   ```markdown
   # REMOVE platform exception documentation
   # ADD hive-orchestration as standard package
   ```

**Deliverables**:
- Golden rules updated
- All validation passing
- Documentation updated

**Validation**:
```bash
python scripts/validation/validate_golden_rules.py --level ERROR
# SHOULD PASS: 13/13 rules
```

---

### Phase 9: Documentation & Release (Days 17-18)

**Objective**: Complete package documentation and release v1.0.0

**Tasks**:

1. **Package README** (packages/hive-orchestration/README.md)
   ```markdown
   # hive-orchestration

   Orchestration infrastructure for the Hive platform.

   ## Quick Start

   ```python
   from hive_orchestration import OrchestrationClient

   client = OrchestrationClient()
   task_id = await client.create_task("deployment", {"script": "deploy.sh"})
   ```

   ## Installation

   ```bash
   poetry add hive-orchestration
   ```

   ## API Reference

   [Full documentation here]
   ```

2. **API Reference Documentation**
   - Document all public classes and methods
   - Usage examples for each API
   - Best practices guide

3. **Migration Guide** (claudedocs/hive_orchestration_migration_guide.md)
   ```markdown
   # Migration from orchestrator.core to hive-orchestration

   ## Before
   ```python
   from hive_orchestrator.core.db import create_task
   task_id = create_task(task_type, payload)
   ```

   ## After
   ```python
   from hive_orchestration import OrchestrationClient
   client = OrchestrationClient()
   task_id = await client.create_task(task_type, payload)
   ```
   ```

4. **CHANGELOG** (packages/hive-orchestration/CHANGELOG.md)
   ```markdown
   # Changelog

   ## [1.0.0] - 2026-01-15

   ### Added
   - Initial release of hive-orchestration package
   - Task operations (create, get, update, delete)
   - Worker operations (register, heartbeat, get active)
   - Event system (TaskCreatedEvent, etc.)
   - OrchestrationClient SDK
   ```

5. **Update Architecture Docs**
   - Update package overview
   - Add hive-orchestration to package list
   - Update dependency diagrams

**Deliverables**:
- Complete documentation
- Migration guide
- v1.0.0 release ready

---

### Phase 10: Deprecation & Cleanup (Days 19-20)

**Objective**: Clean up old code and complete migration

**Tasks**:

1. **Add Deprecation Warnings** (orchestrator.core shims)
   ```python
   # orchestrator/core/db/__init__.py (temporary shim)
   import warnings
   from hive_orchestration import OrchestrationClient

   def create_task(*args, **kwargs):
       warnings.warn(
           "Importing from hive_orchestrator.core.db is deprecated. "
           "Use 'from hive_orchestration import OrchestrationClient' instead. "
           "This shim will be removed in v2.0.0.",
           DeprecationWarning,
           stacklevel=2
       )
       client = OrchestrationClient()
       return client.create_task(*args, **kwargs)
   ```

2. **Monitor Usage** (1 sprint - 2 weeks)
   - Watch for deprecation warnings in logs
   - Ensure no other apps importing old code
   - Check for internal orchestrator usage

3. **Remove Shims** (after 1 sprint)
   ```bash
   # Remove orchestrator.core.db and orchestrator.core.bus
   rm -rf apps/hive-orchestrator/src/hive_orchestrator/core/db
   rm -rf apps/hive-orchestrator/src/hive_orchestrator/core/bus

   # Keep private modules
   # apps/hive-orchestrator/src/hive_orchestrator/core/claude
   # apps/hive-orchestrator/src/hive_orchestrator/core/monitoring
   # apps/hive-orchestrator/src/hive_orchestrator/core/errors
   ```

4. **Final Validation**
   ```bash
   # Run all tests across platform
   cd /c/git/hive
   pytest apps/*/tests/ packages/*/tests/ -v

   # Run golden rules
   python scripts/validation/validate_golden_rules.py --level ERROR

   # Run integration tests
   python scripts/testing/run_integration_tests.py
   ```

5. **Update Architecture Health**
   ```
   Before extraction: 87%
   After extraction: 95%

   Improvements:
   - Zero app-to-app dependencies ✅
   - All apps use packages properly ✅
   - Clear interface contracts ✅
   - Proper modular monolith ✅
   ```

**Deliverables**:
- Old code removed
- All tests passing
- Architecture health at 95%

---

## Testing Strategy

### Unit Tests (Package Level)

**Coverage Target**: >90%

```python
# tests/test_database.py
def test_task_crud_operations()
def test_worker_operations()
def test_execution_plan_operations()

# tests/test_events.py
def test_task_event_publishing()
def test_event_subscription()
def test_event_filtering()

# tests/test_client.py
def test_client_task_lifecycle()
def test_client_worker_management()
def test_client_event_coordination()
```

### Integration Tests (Cross-Package)

```python
# tests/integration/test_full_workflow.py
async def test_complete_task_workflow():
    """Test full task lifecycle with events"""
    client = OrchestrationClient(db_path=":memory:")

    # Track events
    events = []
    await client.subscribe_to_task_events("*", lambda e: events.append(e))

    # Create and execute task
    task_id = await client.create_task("deployment", {"script": "deploy.sh"})
    await client.update_task_status(task_id, "running")
    await client.update_task_status(task_id, "completed")

    # Verify events
    assert len(events) == 3
    assert events[0].event_type == "task.created"
    assert events[1].event_type == "task.started"
    assert events[2].event_type == "task.completed"
```

### System Tests (End-to-End)

```python
# tests/e2e/test_orchestration_system.py
async def test_orchestrator_planner_deployer_integration():
    """Test full orchestration workflow"""

    # Start orchestrator
    orchestrator = Orchestrator()
    await orchestrator.start()

    # Planner creates task
    planner = PlannerAgent()
    plan = await planner.create_plan("Deploy to production")

    # Orchestrator executes
    task_id = await orchestrator.execute_plan(plan)

    # Deployer handles deployment
    deployer = DeployerAgent()
    result = await deployer.deploy(task_id)

    # Verify completion
    task = await orchestrator.get_task(task_id)
    assert task.status == TaskStatus.COMPLETED
```

---

## Migration Checklist

### For Each App Using Orchestrator.Core

- [ ] Add hive-orchestration dependency to pyproject.toml
- [ ] Remove hive-orchestrator dependency (if present)
- [ ] Replace all `from hive_orchestrator.core.db` imports
- [ ] Replace all `from hive_orchestrator.core.bus` imports
- [ ] Update direct database calls to use OrchestrationClient
- [ ] Update event bus usage to use package events
- [ ] Update tests to use package fixtures
- [ ] Run full test suite and verify passing
- [ ] Update documentation and examples
- [ ] Deploy and monitor for issues

### For hive-orchestrator

- [ ] Add hive-orchestration dependency
- [ ] Replace core.db usage with package
- [ ] Replace core.bus usage with package
- [ ] Keep private modules (claude, monitoring, errors)
- [ ] Update tests
- [ ] Run full test suite
- [ ] Deploy and validate

---

## Risk Mitigation

### Risk 1: Breaking Changes During Extraction

**Risk**: Moving code breaks existing functionality

**Mitigation**:
- Maintain backward compatibility shims during transition
- Comprehensive test coverage (>90%)
- Gradual migration (one app at a time)
- Feature flags for new vs old code paths
- Extensive integration testing

**Rollback Plan**:
- Keep old code in orchestrator.core during deprecation period
- Can revert package dependency and use shims
- 2-week monitoring period before final removal

### Risk 2: Hidden Dependencies

**Risk**: Unknown code depending on orchestrator.core

**Mitigation**:
- Thorough code search before extraction
- Deprecation warnings for 1 sprint (2 weeks)
- Monitor logs for deprecation usage
- Golden rules validator catches violations

**Detection**:
```bash
# Find all imports
grep -r "from hive_orchestrator.core" apps/ packages/

# Find any runtime usage
grep -r "hive_orchestrator\.core" apps/ packages/
```

### Risk 3: Performance Regression

**Risk**: New package slower than direct access

**Mitigation**:
- Benchmark before/after extraction
- Performance tests in package
- Monitor production metrics
- Optimize bottlenecks if found

**Benchmarks**:
```python
# Before extraction
def benchmark_task_creation_old():
    start = time.time()
    for i in range(1000):
        create_task("test", {})
    duration = time.time() - start
    print(f"Old: {duration:.2f}s for 1000 tasks")

# After extraction
def benchmark_task_creation_new():
    client = OrchestrationClient()
    start = time.time()
    for i in range(1000):
        await client.create_task("test", {})
    duration = time.time() - start
    print(f"New: {duration:.2f}s for 1000 tasks")
```

### Risk 4: Database Migration Issues

**Risk**: Schema changes required, data loss

**Mitigation**:
- Package uses same schema as orchestrator.core
- No data migration needed (schema compatible)
- Test with production database copy first
- Backup before deployment

### Risk 5: Event System Changes

**Risk**: Event publishing/subscription breaks

**Mitigation**:
- Event schemas remain identical
- Test event flow in integration tests
- Monitor event delivery in production
- Gradual rollout with monitoring

---

## Success Criteria

### Functional

- [ ] hive-orchestration package created and published
- [ ] All database operations work correctly
- [ ] All event operations work correctly
- [ ] OrchestrationClient SDK functional
- [ ] hive-orchestrator migrated successfully
- [ ] ai-planner migrated successfully
- [ ] ai-deployer migrated successfully
- [ ] All apps can create/manage tasks
- [ ] All apps can handle events properly
- [ ] No functionality lost in migration

### Quality

- [ ] Test coverage >90% for package
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] All E2E tests passing
- [ ] Golden rules validation 100% passing
- [ ] No deprecation warnings in production
- [ ] No performance regression (<5% slower acceptable)

### Documentation

- [ ] Package README complete with examples
- [ ] API reference documentation complete
- [ ] Migration guide published
- [ ] Architecture docs updated
- [ ] CHANGELOG up to date
- [ ] Code comments comprehensive

### Architecture

- [ ] Zero app-to-app dependencies
- [ ] All apps use packages properly
- [ ] Clear interface contracts
- [ ] Proper modular monolith design
- [ ] Golden rules no longer need exceptions
- [ ] Architecture health at 95%

---

## Post-Extraction Benefits

### Architectural Benefits

**Before**:
```
ai-planner → hive-orchestrator.core (app-to-app dependency)
ai-deployer → hive-orchestrator.core (app-to-app dependency)
```

**After**:
```
ai-planner → hive-orchestration (package dependency)
ai-deployer → hive-orchestration (package dependency)
hive-orchestrator → hive-orchestration (package dependency)
```

**Improvements**:
- ✅ **Proper Modular Monolith**: Apps use packages, not each other
- ✅ **Independent Deployment**: Can deploy ai-planner without orchestrator
- ✅ **Clear Contracts**: Well-defined interfaces and protocols
- ✅ **Stable API**: Semantic versioning with deprecation policy
- ✅ **Easier Testing**: Mock package interfaces, not entire app

### Development Benefits

- ✅ **Faster Development**: Clear API reduces cognitive load
- ✅ **Better Documentation**: Package docs vs scattered app code
- ✅ **Reusability**: Other apps can use orchestration easily
- ✅ **Maintainability**: Single source of truth for orchestration
- ✅ **Code Quality**: Enforced interfaces and testing

### Operational Benefits

- ✅ **Independent Scaling**: Package can be optimized separately
- ✅ **Monitoring**: Clear boundaries for instrumentation
- ✅ **Version Management**: Semantic versioning for changes
- ✅ **Deployment Flexibility**: Apps can upgrade independently
- ✅ **Debugging**: Clear package boundaries

---

## Timeline & Resource Planning

### Timeline Summary

**Total Duration**: 20 working days (~4 weeks)

**Week 1** (Days 1-5): Foundation
- Days 1-2: Package scaffolding
- Days 3-5: Database extraction

**Week 2** (Days 6-10): Core Implementation
- Days 6-7: Event bus extraction
- Days 8-9: Client SDK creation
- Days 10-12: Orchestrator migration

**Week 3** (Days 11-15): App Migrations
- Days 13-14: ai-planner migration
- Day 15: ai-deployer migration

**Week 4** (Days 16-20): Finalization
- Day 16: Golden rules update
- Days 17-18: Documentation and release
- Days 19-20: Deprecation and cleanup

### Resource Requirements

**Developer Time**: 1 senior developer full-time for 4 weeks

**Skills Required**:
- Python expert (async/await patterns)
- Database experience (SQLite, schema design)
- Event-driven architecture
- Testing expertise (unit, integration, E2E)
- Documentation writing

**Supporting Resources**:
- Code reviewer (1-2 hours per phase)
- QA testing (2-3 days total)
- DevOps support (deployment assistance)

### Milestones

**M1** (End of Week 1): Package with database layer working
- Package structure complete
- Database operations extracted
- Unit tests passing

**M2** (End of Week 2): Orchestrator migrated
- Event system in package
- Client SDK complete
- Orchestrator using package

**M3** (End of Week 3): All apps migrated
- ai-planner using package
- ai-deployer using package
- All tests passing

**M4** (End of Week 4): Production ready
- Documentation complete
- v1.0.0 released
- Old code deprecated

---

## Appendix A: Code Examples

### Example 1: Task Creation Comparison

**Before (orchestrator.core)**:
```python
from hive_orchestrator.core.db import create_task

task_id = create_task(
    task_type="deployment",
    payload={"script": "deploy.sh", "env": "production"}
)
```

**After (hive-orchestration)**:
```python
from hive_orchestration import OrchestrationClient

client = OrchestrationClient()
task_id = await client.create_task(
    task_type="deployment",
    payload={"script": "deploy.sh", "env": "production"}
)
```

### Example 2: Event Subscription Comparison

**Before**:
```python
from hive_orchestrator.core.bus import get_async_event_bus

bus = get_async_event_bus()
await bus.subscribe("task.*", handler)
```

**After**:
```python
from hive_orchestration import OrchestrationClient

client = OrchestrationClient()
await client.subscribe_to_task_events("*", handler)
```

### Example 3: Full Workflow

```python
from hive_orchestration import OrchestrationClient
from hive_orchestration.models import TaskStatus

# Initialize client
client = OrchestrationClient()

# Create task
task_id = await client.create_task(
    task_type="deployment",
    payload={
        "script": "deploy.sh",
        "env": "production",
        "services": ["api", "worker"]
    }
)

# Subscribe to task events
async def handle_task_event(event):
    print(f"Task event: {event.event_type} for {event.task_id}")

await client.subscribe_to_task_events(task_id, handle_task_event)

# Update task status
await client.update_task_status(task_id, TaskStatus.RUNNING)

# Simulate work
await asyncio.sleep(5)

# Complete task
await client.update_task_status(
    task_id,
    TaskStatus.COMPLETED,
    result={"deployed_services": ["api", "worker"]}
)

# Get final task state
task = await client.get_task(task_id)
print(f"Task {task.id} completed at {task.updated_at}")
```

---

## Appendix B: Testing Examples

### Unit Test Example

```python
# tests/test_task_database.py

import pytest
from hive_orchestration.database import TaskDatabase
from hive_orchestration.models import Task, TaskStatus

@pytest.fixture
def task_db():
    """Create in-memory database for testing"""
    db = TaskDatabase(db_path=":memory:")
    yield db
    db.close()

def test_create_task(task_db):
    """Test task creation"""
    task_id = task_db.create_task(
        task_type="deployment",
        payload={"script": "deploy.sh"}
    )

    assert task_id is not None
    assert len(task_id) == 36  # UUID length

def test_get_task(task_db):
    """Test task retrieval"""
    task_id = task_db.create_task("deployment", {})

    task = task_db.get_task(task_id)

    assert task is not None
    assert task.id == task_id
    assert task.type == "deployment"
    assert task.status == TaskStatus.PENDING

def test_update_task_status(task_db):
    """Test task status update"""
    task_id = task_db.create_task("deployment", {})

    task_db.update_task_status(task_id, TaskStatus.RUNNING)

    task = task_db.get_task(task_id)
    assert task.status == TaskStatus.RUNNING

def test_get_tasks_by_status(task_db):
    """Test querying tasks by status"""
    # Create tasks with different statuses
    task1 = task_db.create_task("deployment", {})
    task2 = task_db.create_task("build", {})
    task_db.update_task_status(task2, TaskStatus.RUNNING)

    # Get pending tasks
    pending = task_db.get_tasks_by_status(TaskStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].id == task1

    # Get running tasks
    running = task_db.get_tasks_by_status(TaskStatus.RUNNING)
    assert len(running) == 1
    assert running[0].id == task2
```

### Integration Test Example

```python
# tests/integration/test_client_workflow.py

import pytest
import asyncio
from hive_orchestration import OrchestrationClient
from hive_orchestration.models import TaskStatus

@pytest.mark.asyncio
async def test_complete_task_workflow():
    """Test complete task lifecycle with client"""
    client = OrchestrationClient(db_path=":memory:")

    # Track events
    events = []

    async def event_handler(event):
        events.append(event)

    await client.subscribe_to_task_events("*", event_handler)

    # Create task
    task_id = await client.create_task(
        task_type="deployment",
        payload={"script": "deploy.sh"}
    )

    # Update through lifecycle
    await client.update_task_status(task_id, TaskStatus.RUNNING)
    await asyncio.sleep(0.1)  # Wait for event processing

    await client.update_task_status(task_id, TaskStatus.COMPLETED)
    await asyncio.sleep(0.1)

    # Verify task state
    task = await client.get_task(task_id)
    assert task.status == TaskStatus.COMPLETED

    # Verify events
    assert len(events) == 3
    assert events[0].event_type == "task.created"
    assert events[1].event_type == "task.started"
    assert events[2].event_type == "task.completed"
```

---

## Appendix C: Troubleshooting Guide

### Issue 1: Import Errors After Migration

**Symptom**: `ModuleNotFoundError: No module named 'hive_orchestration'`

**Solution**:
```bash
# Reinstall package
cd packages/hive-orchestration
poetry install

# Update app dependencies
cd apps/ai-planner
poetry update hive-orchestration
```

### Issue 2: Database Connection Errors

**Symptom**: `DatabaseError: unable to open database file`

**Solution**:
```python
# Check database path
from hive_orchestration import OrchestrationClient

client = OrchestrationClient()
print(f"Database path: {client.db_path}")

# Ensure directory exists
import os
os.makedirs(os.path.dirname(client.db_path), exist_ok=True)
```

### Issue 3: Events Not Being Received

**Symptom**: Event handler not called

**Solution**:
```python
# Ensure async event loop is running
import asyncio

async def main():
    client = OrchestrationClient()

    # Subscribe before publishing
    await client.subscribe_to_task_events("*", handler)

    # Give event loop time to process
    task_id = await client.create_task("test", {})
    await asyncio.sleep(0.1)  # Wait for event processing

asyncio.run(main())
```

---

**Document Status**: Implementation plan complete
**Next Action**: Begin Phase 1 (Package Scaffolding) in Q1 2026
**Owner**: Platform architecture team
**Review Date**: 2026-01-01
