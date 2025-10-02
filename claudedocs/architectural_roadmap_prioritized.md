# Hive Platform - Prioritized Architectural Roadmap

**Date**: 2025-09-30
**Status**: APPROVED - Ready for Implementation
**Based On**: Expert architectural review and pkg agent analysis

---

## Executive Summary

This roadmap addresses the critical architectural findings from the pkg agent analysis, validated and refined by expert review. The focus is on eliminating architectural violations, increasing utilization of powerful infrastructure, and codifying best practices into enforceable rules.

**Architecture Health Trajectory**:
- Current: 87%
- After Priority 1: 95%
- After Priority 2: 97%
- After Priority 3: 99%

---

## Priority 1: Eliminate App-to-App Dependencies (CRITICAL)

**Timeline**: 1-2 weeks
**Impact**: HIGH - Fixes primary architectural violation
**Effort**: Medium
**Blocker**: None

### Problem Statement

**Critical Architectural Violation**:
```python
# ❌ CURRENT - Apps importing from another app
# This creates "distributed monolith" - worst of both worlds
from hive_orchestrator.core.db import create_task        # ai-planner
from hive_orchestrator.core.bus import get_async_event_bus  # ai-deployer
```

**Issues**:
1. **Tight Coupling**: ai-planner can't deploy without hive-orchestrator
2. **Breaking Changes**: Orchestrator refactoring breaks dependent apps
3. **Testing Nightmare**: Can't unit test ai-planner independently
4. **Modularity Loss**: Violates modular monolith principles

**The Rule**: If 3+ apps need the same logic, it's **platform infrastructure**, not app-specific.

### Solution: Create hive-orchestration Package

**Proper Architecture**:
```python
# ✅ FUTURE - Apps using shared package
from hive_orchestration.core import TaskOperations, WorkerRegistry
from hive_orchestration.models import Task, Worker, ExecutionPlan
from hive_orchestration.events import TaskCreatedEvent

# All apps depend on package, not each other
```

---

### Implementation Steps

#### Step 1.1: Create Package Structure (Day 1)

**Task**: Create new hive-orchestration package

**Directory Structure**:
```
packages/hive-orchestration/
├── src/hive_orchestration/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py          # Public API exports
│   │   ├── task_operations.py   # Task interface
│   │   └── worker_operations.py # Worker interface
│   ├── models/
│   │   ├── __init__.py
│   │   ├── task.py              # Task data model
│   │   ├── worker.py            # Worker data model
│   │   └── execution_plan.py    # ExecutionPlan model
│   └── events/
│       ├── __init__.py
│       ├── task_events.py       # Task lifecycle events
│       └── worker_events.py     # Worker events
├── tests/
│   ├── test_task_operations.py
│   ├── test_models.py
│   └── test_events.py
├── pyproject.toml
└── README.md
```

**pyproject.toml**:
```toml
[tool.poetry]
name = "hive-orchestration"
version = "1.0.0"
description = "Orchestration infrastructure for Hive platform"
authors = ["Hive Team"]
packages = [{include = "hive_orchestration", from = "src"}]

[tool.poetry.dependencies]
python = "^3.11"
pydantic = "^2.0.0"
hive-logging = {path = "../hive-logging", develop = true}
hive-db = {path = "../hive-db", develop = true}
hive-bus = {path = "../hive-bus", develop = true}
hive-models = {path = "../hive-models", develop = true}
hive-errors = {path = "../hive-errors", develop = true}

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.2"
pytest-asyncio = "^0.23.0"
```

**Commands**:
```bash
mkdir -p packages/hive-orchestration/src/hive_orchestration/{core,models,events}
mkdir -p packages/hive-orchestration/tests
cd packages/hive-orchestration
# Create pyproject.toml
poetry install
```

---

#### Step 1.2: Identify Shared Core Logic (Day 2)

**Task**: Analyze hive-orchestrator to identify shared interfaces

**Investigation**:
```bash
# Find what ai-planner and ai-deployer import
grep -r "from hive_orchestrator.core" apps/ai-planner/src/
grep -r "from hive_orchestrator.core" apps/ai-deployer/src/

# Expected findings:
# - Task operations (create_task, get_task, update_task_status)
# - Worker operations (register_worker, get_active_workers)
# - Event bus (get_async_event_bus)
# - Data models (Task, Worker, ExecutionPlan)
```

**What to Extract** (interfaces, not implementations):

**Task Operations Interface** (`core/task_operations.py`):
```python
from typing import Protocol
from hive_orchestration.models import Task, TaskStatus

class TaskOperations(Protocol):
    """Protocol for task orchestration operations"""

    def create_task(self, task_type: str, payload: dict) -> str:
        """Create a new task"""
        ...

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID"""
        ...

    def update_task_status(self, task_id: str, status: TaskStatus) -> None:
        """Update task status"""
        ...

    def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        """Get tasks by status"""
        ...
```

**Worker Operations Interface** (`core/worker_operations.py`):
```python
from typing import Protocol
from hive_orchestration.models import Worker

class WorkerOperations(Protocol):
    """Protocol for worker management operations"""

    def register_worker(self, worker_id: str, capabilities: list[str]) -> None:
        """Register a new worker"""
        ...

    def get_active_workers(self) -> list[Worker]:
        """Get all active workers"""
        ...

    def update_worker_heartbeat(self, worker_id: str) -> None:
        """Update worker heartbeat timestamp"""
        ...
```

**Data Models** (`models/task.py`):
```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(BaseModel):
    """Task data model"""
    id: str
    type: str
    status: TaskStatus
    payload: dict
    created_at: datetime
    updated_at: datetime
    worker_id: str | None = None
    result: dict | None = None

    @classmethod
    def from_db_row(cls, row):
        """Create Task from database row"""
        return cls(
            id=row["id"],
            type=row["type"],
            status=TaskStatus(row["status"]),
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            worker_id=row.get("worker_id"),
            result=json.loads(row["result"]) if row.get("result") else None
        )
```

**Events** (`events/task_events.py`):
```python
from hive_bus import BaseEvent
from hive_orchestration.models import Task

class TaskCreatedEvent(BaseEvent):
    """Event published when task is created"""

    def __init__(self, task: Task):
        super().__init__(
            event_type="task.created",
            source="orchestration",
            task_id=task.id,
            task_type=task.type,
            payload=task.payload
        )

class TaskCompletedEvent(BaseEvent):
    """Event published when task completes"""

    def __init__(self, task: Task):
        super().__init__(
            event_type="task.completed",
            source="orchestration",
            task_id=task.id,
            result=task.result
        )
```

**Public API** (`__init__.py`):
```python
"""
hive-orchestration - Orchestration infrastructure for Hive platform

This package provides the core interfaces, data models, and events for
task orchestration across the Hive platform.

Public API:
-----------
from hive_orchestration.core import TaskOperations, WorkerOperations
from hive_orchestration.models import Task, Worker, TaskStatus
from hive_orchestration.events import TaskCreatedEvent, TaskCompletedEvent
"""

from hive_orchestration.core.task_operations import TaskOperations
from hive_orchestration.core.worker_operations import WorkerOperations
from hive_orchestration.models.task import Task, TaskStatus
from hive_orchestration.models.worker import Worker
from hive_orchestration.events.task_events import (
    TaskCreatedEvent,
    TaskCompletedEvent,
)

__all__ = [
    # Core interfaces
    "TaskOperations",
    "WorkerOperations",
    # Models
    "Task",
    "TaskStatus",
    "Worker",
    # Events
    "TaskCreatedEvent",
    "TaskCompletedEvent",
]

__version__ = "1.0.0"
```

---

#### Step 1.3: Move Core Logic to Package (Day 3)

**Task**: Extract shared logic from orchestrator to package

**What Stays in hive-orchestrator** (implementation):
```python
# apps/hive-orchestrator/src/hive_orchestrator/services/task_service.py
from hive_orchestration.core import TaskOperations
from hive_orchestration.models import Task, TaskStatus
from hive_db import get_sqlite_connection

class HiveTaskService(TaskOperations):
    """Orchestrator's implementation of TaskOperations"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def create_task(self, task_type: str, payload: dict) -> str:
        """Implementation using orchestrator's database"""
        task_id = str(uuid.uuid4())
        with get_sqlite_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO tasks (id, type, status, payload) VALUES (?, ?, ?, ?)",
                (task_id, task_type, TaskStatus.PENDING.value, json.dumps(payload))
            )
        return task_id

    # ... other implementations
```

**Key Principle**: Package has interfaces and models, orchestrator has implementation.

---

#### Step 1.4: Update ai-planner Dependencies (Day 4)

**Task**: Refactor ai-planner to use package

**Update pyproject.toml**:
```toml
[tool.poetry.dependencies]
# REMOVE
# hive-orchestrator = {path = "../hive-orchestrator", develop = true}

# ADD
hive-orchestration = {path = "../../packages/hive-orchestration", develop = true}
```

**Update Imports** (ai-planner/agent.py):
```python
# BEFORE
from hive_orchestrator.core.db import (
    create_task,
    get_connection,
    AsyncDatabaseOperations,
)

# AFTER
from hive_orchestration.core import TaskOperations
from hive_orchestration.models import Task, TaskStatus

# Use dependency injection
class PlannerAgent:
    def __init__(self, task_ops: TaskOperations):
        self.task_ops = task_ops

    async def create_execution_plan(self, task_description: str):
        # Use interface, not direct implementation
        task_id = self.task_ops.create_task(
            task_type="execution_plan",
            payload={"description": task_description}
        )
        return task_id
```

**Update Tests**:
```python
# tests/test_planner_agent.py
from hive_orchestration.core import TaskOperations
from unittest.mock import Mock

def test_planner_creates_task():
    # Mock the interface
    mock_task_ops = Mock(spec=TaskOperations)
    mock_task_ops.create_task.return_value = "task-123"

    planner = PlannerAgent(task_ops=mock_task_ops)
    result = planner.create_execution_plan("Deploy to prod")

    mock_task_ops.create_task.assert_called_once()
    assert result == "task-123"
```

**Commands**:
```bash
cd apps/ai-planner
poetry lock
poetry install
pytest tests/ -v
```

---

#### Step 1.5: Update ai-deployer Dependencies (Day 5)

**Task**: Refactor ai-deployer to use package (same pattern as ai-planner)

**Repeat Step 1.4** for ai-deployer app.

---

#### Step 1.6: Update Golden Rules Validator (Day 6)

**Task**: Remove platform app exceptions (no longer needed)

**Edit**: `packages/hive-tests/src/hive_tests/ast_validator.py`

```python
# REMOVE (lines 484-497)
# Platform app exceptions - no longer needed
# PLATFORM_APP_EXCEPTIONS = {
#     "hive_orchestrator.core.db": ["ai_planner", "ai_deployer"],
#     "hive_orchestrator.core.bus": ["ai_planner", "ai_deployer"],
# }

# Update _is_invalid_app_import method
def _is_invalid_app_import(self, module_name: str) -> bool:
    """Check if this is an invalid app-to-app import"""
    if not module_name:
        return False

    # Skip if importing from packages
    if module_name.startswith("hive_"):
        return False  # All hive-* packages are allowed

    # Skip if importing from current app
    if self.context.app_name:
        app_name_normalized = self.context.app_name.replace("-", "_")
        if module_name.startswith(app_name_normalized):
            return False

    # Allow imports from apps' core modules (inherit→extend pattern)
    if ".core." in module_name or module_name.endswith(".core"):
        return False

    # Check if this looks like an app import
    app_indicators = ["ai_", "hive_orchestrator", "ecosystemiser"]
    return any(module_name.startswith(indicator) for indicator in app_indicators)
```

**Validation**:
```bash
python scripts/validation/validate_golden_rules.py --level ERROR
# SHOULD PASS: 13/13 rules with no exceptions
```

---

#### Step 1.7: Update Documentation (Day 7)

**Task**: Update architecture documentation

**Update**: `.claude/ARCHITECTURE_PATTERNS.md`

Remove platform exception section, add:

```markdown
## Using hive-orchestration Package

All apps needing task orchestration should use the hive-orchestration package:

### Installation

```toml
[tool.poetry.dependencies]
hive-orchestration = {path = "../../packages/hive-orchestration", develop = true}
```

### Usage

```python
from hive_orchestration.core import TaskOperations
from hive_orchestration.models import Task, TaskStatus

# Use dependency injection
class MyApp:
    def __init__(self, task_ops: TaskOperations):
        self.task_ops = task_ops

    def process(self):
        task_id = self.task_ops.create_task("my_task", {"data": "value"})
```

### Benefits

- ✅ Clear interface contracts (protocols)
- ✅ Independent deployment (package dependency)
- ✅ Easy testing (mock TaskOperations interface)
- ✅ Proper modular monolith (apps → packages)
```

**Update**: `.claude/CLAUDE.md`

Update import pattern section to reflect no exceptions:

```markdown
### Import Pattern Rules (CRITICAL)

**✅ ALWAYS ALLOWED**:
```python
# 1. Package imports
from hive_logging import get_logger
from hive_orchestration import TaskOperations  # NEW - Orchestration package

# 2. Same app core extensions
from myapp.core.bus import get_event_bus
```

**❌ NEVER ALLOWED**:
```python
# Cross-app imports (NO EXCEPTIONS)
from hive_orchestrator.core.db import create_task  # ❌ FORBIDDEN
from other_app.services import something  # ❌ FORBIDDEN
```
```

---

### Success Criteria - Priority 1

- [ ] hive-orchestration package created and functional
- [ ] Interfaces defined (TaskOperations, WorkerOperations)
- [ ] Models defined (Task, Worker, ExecutionPlan)
- [ ] Events defined (TaskCreatedEvent, etc.)
- [ ] ai-planner using package (not orchestrator app)
- [ ] ai-deployer using package (not orchestrator app)
- [ ] hive-orchestrator implements package interfaces
- [ ] All tests passing across platform
- [ ] Golden rules validator updated (no exceptions)
- [ ] Golden rules validation passing (13/13)
- [ ] Documentation updated
- [ ] Architecture health: 95%

---

## Priority 2: Drive Adoption of Underutilized Packages (HIGH VALUE)

**Timeline**: 1-2 weeks
**Impact**: HIGH - Leverage existing powerful infrastructure
**Effort**: Low-Medium
**Blocker**: None

### Problem Statement

**Underutilized Infrastructure**:
- `hive-performance`: 0% adoption (0/9 apps)
- `hive-cache`: 11% adoption (1/9 apps) - should be 80%+
- `hive-algorithms`: 0% adoption (0/9 apps)
- `hive-service-discovery`: 0% adoption (0/9 apps)

**Impact**: Existing powerful tools not delivering value, reinventing wheels.

---

### Step 2.1: Integrate hive-performance (Week 1)

**Task**: Add performance monitoring to critical apps

**Target Apps**: ecosystemiser, guardian-agent, hive-orchestrator

#### ecosystemiser Integration

**Add to critical operations** (`ecosystemiser/services/solver.py`):

```python
from hive_performance import MetricsCollector, operation_tracker

metrics = MetricsCollector(app_name="ecosystemiser")

class EnergyOptimizer:
    def optimize_system(self, config: dict):
        """Optimize energy system configuration"""
        with operation_tracker("optimization", metrics):
            # Expensive optimization logic
            result = self._run_genetic_algorithm(config)
            return result

    @metrics.track_performance("genetic_algorithm")
    def _run_genetic_algorithm(self, config: dict):
        """Run GA optimization"""
        # Track performance of expensive algorithm
        for generation in range(config["max_generations"]):
            population = self._evolve_population(population)
        return best_solution

    def get_climate_data(self, location: str, date: str):
        """Fetch climate data from external API"""
        with operation_tracker("api_call.nasa_power", metrics):
            # Track external API performance
            data = self._fetch_nasa_power(location, date)
            return data
```

**Add metrics endpoint** (`ecosystemiser/api/routes.py`):

```python
from fastapi import APIRouter
from hive_performance import get_metrics_summary

router = APIRouter()

@router.get("/metrics")
async def get_performance_metrics():
    """Get performance metrics for monitoring"""
    return get_metrics_summary(app_name="ecosystemiser")
```

#### guardian-agent Integration

**Track code review operations** (`guardian_agent/services/reviewer.py`):

```python
from hive_performance import MetricsCollector

metrics = MetricsCollector(app_name="guardian_agent")

class CodeReviewer:
    @metrics.track_performance("code_review.full")
    async def review_code(self, file_path: str):
        """Review code file"""
        # Track review time
        analysis = await self._analyze_code(file_path)
        return analysis

    @metrics.track_performance("ai_call.claude")
    async def _call_claude_api(self, prompt: str):
        """Track Claude API call performance"""
        response = await self.claude_client.generate(prompt)
        return response
```

#### hive-orchestrator Integration

**Track task execution** (`hive_orchestrator/services/task_executor.py`):

```python
from hive_performance import MetricsCollector

metrics = MetricsCollector(app_name="hive_orchestrator")

class TaskExecutor:
    @metrics.track_performance("task.execution")
    async def execute_task(self, task_id: str):
        """Execute orchestration task"""
        task = await self.get_task(task_id)
        result = await self._run_task(task)
        return result

    @metrics.track_performance("task.lifecycle")
    async def task_lifecycle_time(self, task_id: str):
        """Track complete task lifecycle"""
        # Measure from creation to completion
        pass
```

**Commands**:
```bash
cd apps/ecosystemiser
# Add hive-performance to pyproject.toml dependencies
poetry add ../packages/hive-performance --editable
pytest tests/ -v
```

---

### Step 2.2: Integrate hive-cache (Week 1)

**Task**: Cache expensive operations (especially external APIs)

**Target**: ecosystemiser climate API calls (HIGH IMPACT - 10-100x speedup)

#### Cache Climate API Calls

**Update** (`ecosystemiser/profile_loader/climate/adapters/nasa_power.py`):

```python
from hive_cache import PerformanceCache, cached
from hive_logging import get_logger

logger = get_logger(__name__)

# Initialize cache
cache = PerformanceCache(
    namespace="climate_api",
    default_ttl=86400  # 24 hours
)

class NASAPowerAdapter:
    @cached(cache, ttl=86400, key_prefix="nasa_power")
    async def fetch_climate_data(
        self,
        location: tuple[float, float],  # (lat, lon)
        start_date: str,
        end_date: str,
        parameters: list[str]
    ) -> dict:
        """
        Fetch climate data from NASA POWER API with caching.

        Cache key includes location, dates, and parameters for uniqueness.
        """
        logger.info(f"Fetching NASA POWER data for {location} (will cache)")

        # Expensive API call (only happens on cache miss)
        url = self._build_api_url(location, start_date, end_date, parameters)
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

        logger.info(f"Fetched NASA POWER data, caching for 24h")
        return data

    def _build_cache_key(self, location, start_date, end_date, parameters):
        """Build unique cache key"""
        return f"{location[0]:.2f},{location[1]:.2f}:{start_date}:{end_date}:{','.join(parameters)}"
```

**Similarly for other adapters**:
- `meteostat.py`: Cache historical weather data
- `era5.py`: Cache ERA5 reanalysis data
- `pvgis.py`: Cache solar radiation data

**Expected Impact**:
```
Before caching:
- NASA API call: 2-5 seconds
- Repeated calls: 2-5 seconds each

After caching:
- First call: 2-5 seconds (cache miss)
- Subsequent calls: 0.01-0.05 seconds (100x speedup)
- Cache hit rate: Expected 70-90% in production
```

#### Cache AI Responses (guardian-agent)

**Update** (`guardian_agent/services/code_analyzer.py`):

```python
from hive_cache import PerformanceCache, cached
import hashlib

cache = PerformanceCache(namespace="ai_analysis", default_ttl=3600)

class CodeAnalyzer:
    @cached(cache, ttl=3600, key_prefix="code_analysis")
    async def analyze_code_quality(self, file_content: str) -> dict:
        """
        Analyze code with AI, caching results.

        Cache key is hash of file content (same code = same analysis)
        """
        # Expensive AI API call
        analysis = await self.ai_client.analyze(file_content)
        return analysis

    def _build_cache_key(self, file_content: str):
        """Hash file content for cache key"""
        return hashlib.sha256(file_content.encode()).hexdigest()
```

**Commands**:
```bash
cd apps/ecosystemiser
# Add hive-cache dependency
poetry add ../packages/hive-cache --editable

# Test caching behavior
pytest tests/test_climate_adapters.py -v -s  # -s shows cache logs
```

---

### Step 2.3: Create Package Adoption Guide (Week 2)

**Task**: Document how to use underutilized packages

**Create**: `claudedocs/package_adoption_guide.md`

```markdown
# Hive Platform - Package Adoption Guide

Quick guide for integrating powerful Hive packages into your app.

## hive-performance - Performance Monitoring

### When to Use
- Track expensive operations (APIs, algorithms, DB queries)
- Identify bottlenecks
- Monitor production performance

### Quick Start

```python
from hive_performance import MetricsCollector, operation_tracker

metrics = MetricsCollector(app_name="my_app")

# Method 1: Decorator
@metrics.track_performance("my_operation")
def expensive_function():
    # Your code
    pass

# Method 2: Context manager
with operation_tracker("api_call", metrics):
    result = call_external_api()
```

## hive-cache - High-Performance Caching

### When to Use
- External API calls (NASA, weather services, AI APIs)
- Expensive computations
- Database query results

### Quick Start

```python
from hive_cache import PerformanceCache, cached

cache = PerformanceCache(namespace="my_app", default_ttl=3600)

@cached(cache, ttl=3600, key_prefix="api_data")
async def fetch_external_data(param1, param2):
    # Expensive operation (only runs on cache miss)
    data = await external_api.get(param1, param2)
    return data
```

### Expected Impact
- 10-100x speedup for cached operations
- 70-90% cache hit rate typical
- Dramatic reduction in API costs

## hive-service-discovery - Service Registry

### When to Use
- Dynamic service discovery (not hardcoded URLs)
- Health checking
- Load balancing across instances

### Quick Start

```python
from hive_service_discovery import ServiceRegistry

registry = ServiceRegistry()

# Register service
await registry.register(
    service_name="my_service",
    url="http://localhost:8000",
    health_endpoint="/health"
)

# Discover service
service_url = await registry.discover("other_service")
```

## Integration Checklist

Per app integration:

- [ ] Add package dependency to pyproject.toml
- [ ] Import and initialize in app
- [ ] Instrument critical operations
- [ ] Run tests to verify
- [ ] Monitor metrics/cache hits in production
- [ ] Document usage in app README
```

---

### Success Criteria - Priority 2

- [ ] hive-performance integrated in 3+ apps
  - [ ] ecosystemiser (optimization, API calls)
  - [ ] guardian-agent (code review, AI calls)
  - [ ] hive-orchestrator (task execution)
- [ ] hive-cache integrated in 2+ apps
  - [ ] ecosystemiser (climate APIs - 10-100x speedup)
  - [ ] guardian-agent (AI analysis caching)
- [ ] Package adoption guide created
- [ ] Performance metrics visible in production
- [ ] Cache hit rates >70%
- [ ] Documentation updated
- [ ] Architecture health: 97%

---

## Priority 3: Codify "Public API" Pattern (BEST PRACTICE)

**Timeline**: 3-5 days
**Impact**: MEDIUM - Prevents future violations
**Effort**: Low
**Blocker**: None

### Problem Statement

**Convention vs Enforcement**:
- Current: "Import from core" is a convention (can be bypassed)
- Risk: Developers (or AI) might accidentally import internal modules
- Need: Make this an enforceable Golden Rule

---

### Step 3.1: Create New Golden Rule (Day 1-2)

**Task**: Add "Public API Enforcement" golden rule

**Edit**: `packages/hive-tests/src/hive_tests/ast_validator.py`

Add new rule in `GoldenRuleVisitor` class:

```python
def _validate_public_api_imports(self, node: ast.ImportFrom) -> None:
    """
    Golden Rule 25: Public API Enforcement

    When importing from packages, must import from public API (core/ or __init__.py),
    not internal implementation modules.

    Examples:
    ✅ GOOD: from hive_db.core import get_connection
    ✅ GOOD: from hive_db import get_connection
    ❌ BAD:  from hive_db.internal.pool import ConnectionPool
    ❌ BAD:  from hive_db.utils.helpers import format_query
    """
    if not node.module or not node.module.startswith("hive_"):
        return  # Only validate hive-* package imports

    # Allow imports from public API
    public_api_patterns = [
        ".core.",           # from hive_pkg.core.module
        ".__init__",        # from hive_pkg (uses __init__.py)
    ]

    # Check if this is a public API import
    is_public = any(pattern in node.module for pattern in public_api_patterns)

    # Allow top-level package imports (they use __init__.py)
    parts = node.module.split(".")
    if len(parts) == 1:  # e.g., "hive_logging"
        is_public = True

    if not is_public:
        # Check if importing from internal/private modules
        internal_indicators = [
            ".internal.",
            ".utils.",
            ".helpers.",
            "._private",
            ".impl.",
            ".implementation.",
        ]

        if any(indicator in node.module for indicator in internal_indicators):
            self.add_violation(
                "rule-25",
                "Public API Enforcement",
                node.lineno,
                f"Import from internal module: {node.module}. "
                f"Use public API instead (core/ or package root). "
                f"Example: 'from hive_pkg.core import func' or 'from hive_pkg import func'",
                severity="warning"  # Warning for now, error after grace period
            )
```

**Update** visitor methods to call new validation:

```python
def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
    """Validate from imports"""
    self._validate_dependency_direction_from(node)
    self._validate_no_unsafe_imports_from(node)
    self._validate_no_deprecated_config_imports(node)
    self._validate_public_api_imports(node)  # NEW
    self.generic_visit(node)
```

---

### Step 3.2: Update Package __init__.py Files (Day 3)

**Task**: Ensure all packages expose public API clearly

**Pattern for all packages** (`packages/hive-*/src/hive_*/__init__.py`):

```python
"""
hive-mypackage

This package provides [brief description].

PUBLIC API:
-----------
The following imports are the stable, public API of this package:

    from hive_mypackage import public_function
    from hive_mypackage.core import CoreClass

INTERNAL MODULES:
-----------------
Modules not explicitly exported here are considered internal implementation
details and may change without notice. Do not import directly from:
- hive_mypackage.internal.*
- hive_mypackage.utils.*
- hive_mypackage._private*

Use the public API exports defined in this file or the core/ module.
"""

# Public API exports
from hive_mypackage.core.main import MainClass
from hive_mypackage.core.operations import operation_function

__all__ = [
    "MainClass",
    "operation_function",
]

__version__ = "1.0.0"
```

**Update all 16 packages** to follow this pattern.

---

### Step 3.3: Add Public API Documentation (Day 4)

**Task**: Document public API pattern in architecture guide

**Update**: `.claude/ARCHITECTURE_PATTERNS.md`

Add section:

```markdown
## Golden Rule 25: Public API Enforcement

### Principle

When importing from packages, **always import from the public API**, not internal implementation modules.

### Public API Locations

1. **Package root** (`from hive_pkg import func`)
   - Imports from `__init__.py`
   - Most convenient for commonly-used functions

2. **Core module** (`from hive_pkg.core import Class`)
   - Imports from `core/` directory
   - Stable interface designed for external use

### Examples

✅ **GOOD**:
```python
# Import from package root
from hive_logging import get_logger
from hive_db import get_sqlite_connection

# Import from core module
from hive_orchestration.core import TaskOperations
from hive_cache.core import CacheManager
```

❌ **BAD**:
```python
# DON'T import from internal modules
from hive_db.internal.pool import ConnectionPool  # ❌ Internal implementation
from hive_cache.utils.helpers import format_key   # ❌ Internal utility
from hive_logging._private.formatter import CustomFormatter  # ❌ Private module
```

### Why This Matters

**Stability**: Public API is stable and versioned. Internal modules can change.

**Clarity**: Clear what's supported vs implementation detail.

**Refactoring**: Packages can refactor internals without breaking consumers.

### Validation

The golden rules validator enforces this automatically:

```bash
python scripts/validation/validate_golden_rules.py
# Will flag: "Import from internal module: hive_db.internal.pool"
```

### Migration Guide

If you're importing from an internal module:

1. Check package `__init__.py` or `core/` for public API
2. If function not exported, it may be intentionally private
3. If needed publicly, submit issue to package maintainer
4. Package maintainer can promote to public API with documentation
```

---

### Step 3.4: Test Golden Rule (Day 5)

**Task**: Verify new rule works correctly

**Create test cases** (`packages/hive-tests/tests/test_public_api_rule.py`):

```python
import pytest
from hive_tests.ast_validator import GoldenRulesValidator

def test_public_api_rule_allows_core_imports():
    """Test that imports from core/ are allowed"""
    code = """
from hive_db.core import get_connection
from hive_cache.core import CacheManager
"""
    # Should pass validation
    validator = GoldenRulesValidator()
    result = validator.validate_code_string(code, file_path="test.py")
    assert "Public API Enforcement" not in result.violations

def test_public_api_rule_allows_package_root():
    """Test that imports from package root are allowed"""
    code = """
from hive_logging import get_logger
from hive_db import get_sqlite_connection
"""
    # Should pass validation
    validator = GoldenRulesValidator()
    result = validator.validate_code_string(code, file_path="test.py")
    assert "Public API Enforcement" not in result.violations

def test_public_api_rule_flags_internal_imports():
    """Test that imports from internal modules are flagged"""
    code = """
from hive_db.internal.pool import ConnectionPool
from hive_cache.utils.helpers import format_key
"""
    # Should fail validation
    validator = GoldenRulesValidator()
    result = validator.validate_code_string(code, file_path="test.py")
    assert "Public API Enforcement" in result.violations
    assert len(result.violations["Public API Enforcement"]) == 2

def test_public_api_rule_suggests_alternative():
    """Test that violation message suggests correct usage"""
    code = """
from hive_db.internal.pool import ConnectionPool
"""
    validator = GoldenRulesValidator()
    result = validator.validate_code_string(code, file_path="test.py")

    violation_msg = result.violations["Public API Enforcement"][0]
    assert "from hive_db.core import" in violation_msg or "from hive_db import" in violation_msg
```

**Run tests**:
```bash
cd packages/hive-tests
pytest tests/test_public_api_rule.py -v
```

**Run full validation**:
```bash
python scripts/validation/validate_golden_rules.py --level WARNING
# Should pass with new rule active
```

---

### Success Criteria - Priority 3

- [ ] Golden Rule 25 implemented
- [ ] Rule flags internal module imports
- [ ] Rule allows core/ and __init__.py imports
- [ ] All 16 packages have clear __init__.py with public API
- [ ] Documentation updated with rule explanation
- [ ] Test cases written and passing
- [ ] Full golden rules validation passing
- [ ] Architecture health: 99%

---

## Timeline Summary

### Week 1-2: Priority 1 (Critical)
- Create hive-orchestration package
- Migrate ai-planner and ai-deployer
- Update golden rules (remove exceptions)
- Architecture health: 87% → 95%

### Week 3-4: Priority 2 (High Value)
- Integrate hive-performance (3 apps)
- Integrate hive-cache (2 apps - ecosystemiser priority)
- Create adoption guide
- Architecture health: 95% → 97%

### Week 5: Priority 3 (Best Practice)
- Implement Golden Rule 25
- Update all package __init__.py files
- Full validation and testing
- Architecture health: 97% → 99%

**Total Timeline**: 5 weeks
**Final Architecture Health**: 99%

---

## Metrics & Success Tracking

### Priority 1 Success Metrics

**Before**:
- App-to-app dependencies: 2 (ai-planner, ai-deployer → orchestrator)
- Golden rule exceptions: 2 (platform app exceptions)
- Architecture health: 87%

**After**:
- App-to-app dependencies: 0 ✅
- Golden rule exceptions: 0 ✅
- Architecture health: 95% ✅
- hive-orchestration package adoption: 3 apps ✅

### Priority 2 Success Metrics

**Before**:
- hive-performance adoption: 0/9 apps (0%)
- hive-cache adoption: 1/9 apps (11%)
- Climate API response time: 2-5 seconds
- Cache hit rate: N/A

**After**:
- hive-performance adoption: 3/9 apps (33%) ✅
- hive-cache adoption: 3/9 apps (33%) ✅
- Climate API response time: 0.05 seconds (cached) ✅
- Cache hit rate: 70-90% ✅

### Priority 3 Success Metrics

**Before**:
- Public API enforcement: Convention (soft)
- Internal imports: Possible (no validation)
- Package API clarity: Variable

**After**:
- Public API enforcement: Golden Rule (hard) ✅
- Internal imports: Blocked by validator ✅
- Package API clarity: 100% (all packages documented) ✅

---

## Risk Mitigation

### Risk 1: Breaking Changes in Extraction

**Mitigation**:
- Comprehensive test coverage
- Gradual migration (one app at a time)
- Backward compatibility shims during transition
- Extensive integration testing

### Risk 2: Performance Regression

**Mitigation**:
- Benchmark before/after
- Performance tests in CI
- Monitor production metrics
- Optimize if needed

### Risk 3: Cache Invalidation Issues

**Mitigation**:
- Conservative TTLs (24h for climate data)
- Cache key includes all parameters
- Manual cache clear capability
- Monitor cache hit/miss rates

---

## Appendix: Quick Reference

### Commands Cheat Sheet

```bash
# Golden Rules Validation
python scripts/validation/validate_golden_rules.py --level ERROR

# Run Package Tests
cd packages/hive-orchestration && pytest tests/ -v

# Run App Tests
cd apps/ai-planner && pytest tests/ -v

# Check Package Dependencies
poetry show --tree

# Update Dependencies
poetry lock && poetry install

# Performance Monitoring
# Access at http://localhost:8000/metrics after integration

# Cache Statistics
# Available via hive-cache admin API after integration
```

### Architecture Health Checklist

- [ ] Zero app-to-app dependencies
- [ ] All apps use packages for shared logic
- [ ] Clear public APIs in all packages
- [ ] Golden rules enforcement (no exceptions)
- [ ] Performance monitoring integrated
- [ ] Caching integrated for expensive operations
- [ ] Documentation complete and up-to-date
- [ ] All tests passing (100%)

---

**Document Status**: APPROVED - Ready for Implementation
**Next Action**: Begin Priority 1, Step 1.1 (Create hive-orchestration package)
**Owner**: AI Coding Agent
**Review Date**: Weekly progress reviews
**Target Completion**: 5 weeks from start
