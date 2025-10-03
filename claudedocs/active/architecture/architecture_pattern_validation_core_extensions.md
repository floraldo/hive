# Hive Architecture Pattern Validation: `core/` Extension Pattern

**Date**: 2025-09-30
**Context**: Feedback on package-app architecture analysis
**Focus**: Validating the `packages → app.core → app` extension pattern

---

## Executive Summary

**Pattern Assessment**: ✅ **VALID but needs refinement**

The `core/` extension pattern is architecturally sound for most use cases, but the current app-to-app imports through `core/` need clarification and potentially restructuring.

**Key Findings**:
1. ✅ **`packages → app.core` extension**: Valid inherit→extend pattern
2. ⚠️ **`app.core → other_app.core` imports**: Architecturally questionable
3. 💡 **Shared `core/` logic**: Should be extracted to packages
4. 📋 **Documentation gap**: Pattern not clearly documented for AI agents

---

## I. The `core/` Extension Pattern Explained

### Pattern Definition

```
Architectural Layers:
┌─────────────────────────────────────┐
│  App Business Logic Layer           │  ← Uses extended functionality
│  (services/, handlers/, etc.)       │
└──────────────┬──────────────────────┘
               │ imports from
┌──────────────▼──────────────────────┐
│  App Core Extension Layer (core/)   │  ← Extends packages with app-specific logic
│  - Extends hive-bus                 │
│  - Extends hive-db                  │
│  - Extends hive-errors              │
│  - App-specific event types         │
│  - App-specific database schema     │
└──────────────┬──────────────────────┘
               │ inherits from
┌──────────────▼──────────────────────┐
│  Package Infrastructure Layer       │  ← Generic, reusable infrastructure
│  (packages/hive-*)                  │
└─────────────────────────────────────┘
```

### How It Works

**Example: EcoSystemiser Database Extension**

```python
# packages/hive-db/src/hive_db/sqlite.py (GENERIC)
def get_sqlite_connection(db_path: str):
    """Generic SQLite connection manager"""
    conn = sqlite3.connect(db_path)
    return conn

# apps/ecosystemiser/src/ecosystemiser/core/db.py (EXTENDS)
from hive_db import get_sqlite_connection  # Inherit

def get_ecosystemiser_connection():
    """Extends with EcoSystemiser-specific path and config"""
    db_path = get_ecosystemiser_db_path()  # App-specific logic
    with get_sqlite_connection(str(db_path)) as conn:  # Uses inherited
        conn.execute("PRAGMA foreign_keys = ON")  # App-specific config
        yield conn
```

**What This Achieves**:
- ✅ Reuses package infrastructure (DRY)
- ✅ Adds app-specific behavior (customization)
- ✅ Maintains separation (packages stay generic)
- ✅ Clear inheritance chain (inherit → extend → use)

---

## II. Pattern Validation: Is This Good Architecture?

### ✅ EXCELLENT: Package → App.Core Extension

**Pattern**: `hive-db` → `ecosystemiser/core/db.py`

**Example from ecosystemiser/core/bus.py**:
```python
from hive_bus import BaseBus, BaseEvent  # Inherit from package

class EcoSystemiserEventBus(BaseBus):  # Extend with app logic
    """Extends BaseBus with EcoSystemiser simulation features:
    - Persistent storage in EcoSystemiser database
    - Simulation-specific event routing
    - Analysis correlation tracking
    """

    def __init__(self):
        super().__init__()  # Use parent implementation
        self.db_path = get_ecosystemiser_db_path()  # Add app-specific
        self._ensure_event_tables()  # Add app-specific
```

**Why This Works**:
1. **Clear inheritance**: Uses `super().__init__()` to inherit base functionality
2. **Clear extension**: Adds simulation-specific features (simulation_id, analysis_id, optimization_id)
3. **Domain-focused**: Extension is specific to EcoSystemiser domain
4. **Reusability**: Base `hive-bus` remains generic, usable by other apps

**Assessment**: ✅ **GOLD STANDARD** - This is exactly how the pattern should work

---

### ⚠️ QUESTIONABLE: App.Core → Other_App.Core Imports

**Pattern**: `ai-planner` → `hive_orchestrator.core.db`

**Current Implementation**:
```python
# apps/ai-planner/src/ai_planner/agent.py
from hive_orchestrator.core.db import (
    create_task,
    get_connection,
    AsyncDatabaseOperations,
    get_async_db_operations
)
```

**What's Being Imported**: Orchestrator's **extended** database layer (not base package)

**Why This Is Problematic**:
1. **Tight Coupling**: ai-planner now depends on orchestrator's specific extensions
2. **Violates Modularity**: Apps should be independently deployable
3. **Breaks Separation**: Orchestrator's `core/` is its private extension layer
4. **Unclear Contract**: What if orchestrator changes its `core/` implementation?

**Assessment**: ⚠️ **ARCHITECTURAL SMELL** - This violates modular monolith principles

---

## III. The Core Question: When Are App-to-App Imports Acceptable?

### Current Situation

**What ai-planner/ai-deployer Need**:
- Access to orchestrator's task database (task creation, status updates)
- Access to orchestrator's event bus (coordination events)
- Access to orchestrator's worker registry

**What They're Importing**:
- `hive_orchestrator.core.db` - Orchestrator's extended database layer
- `hive_orchestrator.core.bus` - Orchestrator's extended event bus

**The Dilemma**:
- These are **extensions**, not **interfaces**
- They contain orchestrator-specific implementation details
- But they also represent **shared orchestration state** needed by multiple apps

---

## IV. Architectural Solutions

### Solution 1: Extract Shared Core to Package (RECOMMENDED)

**Rationale**: If multiple apps need orchestrator's `core/` functionality, it's not app-specific—it's **platform infrastructure**.

**Implementation**: Create `hive-orchestration` package

```
packages/hive-orchestration/
├── src/hive_orchestration/
│   ├── interfaces/
│   │   ├── task_protocol.py      # Task interface
│   │   ├── worker_protocol.py    # Worker interface
│   │   └── orchestrator_client.py # Client SDK
│   ├── models/
│   │   ├── task.py               # Task data model
│   │   ├── worker.py             # Worker data model
│   │   └── execution_plan.py    # Execution plan model
│   ├── database/
│   │   ├── schema.py             # Orchestration schema
│   │   ├── task_operations.py   # Task CRUD operations
│   │   └── worker_operations.py # Worker CRUD operations
│   └── events/
│       └── orchestration_events.py # Orchestration event types
```

**Then Apps Use It**:
```python
# hive-orchestrator/core/db.py (IMPLEMENTS interface)
from hive_orchestration.interfaces import TaskOperations
from hive_orchestration.database import OrchestrationSchema

class OrchestratorDatabase(TaskOperations):
    """Orchestrator's implementation of task operations"""
    pass

# ai-planner/agent.py (USES interface)
from hive_orchestration import OrchestratorClient

client = OrchestratorClient()
await client.create_task(task_data)
```

**Benefits**:
- ✅ Apps import from **package**, not other apps
- ✅ Clear interface contracts (protocols/interfaces)
- ✅ Orchestrator remains implementation owner
- ✅ Apps use well-defined SDK
- ✅ Maintains modular monolith principles

**Effort**: 3-4 days (extract, test, migrate)

**Assessment**: ✅ **BEST SOLUTION** - Proper architecture

---

### Solution 2: Define Shared Core Convention (ACCEPTABLE)

**Rationale**: If extraction is too costly, document when app.core → other_app.core is acceptable

**Rules for Acceptable App-to-App Core Imports**:

1. **Only Import from Designated "Platform Apps"**
   - hive-orchestrator is a **platform coordination app**
   - Its `core/` contains **shared orchestration state**
   - Other apps may import its `core/` **only if documented as public API**

2. **Document Public Core API**
   ```python
   # hive-orchestrator/core/__init__.py
   """
   Hive Orchestrator Core - PUBLIC API

   This core module serves as platform infrastructure for orchestration.
   Other apps MAY import from this core module as it represents shared
   orchestration state and coordination primitives.

   PUBLIC API:
   - core.db: Task and worker database operations
   - core.bus: Orchestration event types
   - core.interfaces: Coordination protocols

   PRIVATE (DO NOT IMPORT):
   - core.claude: Claude-specific implementation details
   - core.monitoring: Internal monitoring logic
   """
   ```

3. **Versioning and Stability**
   - Public `core/` API must be versioned
   - Breaking changes require migration path
   - Documented deprecation policy

4. **Alternative: Most Apps Don't Import from Other Apps**
   - Rule: Apps cannot import from other app `core/` by default
   - Exception: Explicitly documented platform apps (e.g., hive-orchestrator)
   - Golden rule validator should allow exceptions for documented cases

**Benefits**:
- ✅ Pragmatic (acknowledges shared state reality)
- ✅ Faster than extraction
- ✅ Maintains some modularity (documented contracts)
- ⚠️ Still creates coupling (orchestrator changes affect apps)

**Effort**: 1-2 days (documentation + golden rule updates)

**Assessment**: ⚠️ **ACCEPTABLE** but not ideal - Temporary solution

---

### Solution 3: Event-Driven Coordination (DECOUPLED)

**Rationale**: Apps coordinate via events, not direct database access

**Implementation**:
```python
# ai-planner publishes event instead of direct DB access
from hive_bus import get_event_bus

bus = get_event_bus()
await bus.publish(TaskCreatedEvent(
    task_id="task-123",
    task_type="deployment",
    payload={"script": "deploy.sh"}
))

# hive-orchestrator subscribes and handles
@bus.subscribe("task.created")
async def handle_task_created(event: TaskCreatedEvent):
    # Orchestrator writes to its own database
    await orchestrator_db.create_task(event.task_id, event.payload)
```

**Benefits**:
- ✅ Complete decoupling (apps don't import from each other)
- ✅ Event-driven architecture (scalable)
- ✅ Clear boundaries (each app owns its data)
- ⚠️ More complex (async, eventual consistency)
- ⚠️ Debugging harder (distributed tracing needed)

**Effort**: 2-3 weeks (significant refactoring)

**Assessment**: ✅ **IDEAL** for microservices, ⚠️ **OVERKILL** for modular monolith

---

## V. Recommendation: Phased Approach

### Phase 1: Documentation (Immediate - 1-2 days)

**Action**: Document the current pattern and rules

**Create**: `.claude/ARCHITECTURE_PATTERNS.md`
```markdown
# Hive Architecture Patterns

## Core Extension Pattern

### Rule 1: Package → App.Core (ALWAYS ALLOWED)
Apps extend packages in their `core/` directory.

Example:
```python
from hive_db import get_sqlite_connection  # ✅ GOOD
from hive_bus import BaseBus  # ✅ GOOD

class MyAppEventBus(BaseBus):  # ✅ GOOD - extends package
    pass
```

### Rule 2: App.Core → Other_App.Core (EXCEPTION ONLY)
By default, apps CANNOT import from other apps' core/.

Exception: Platform coordination apps may expose PUBLIC core/ API.

Currently Allowed:
- `hive_orchestrator.core.db` - Shared orchestration database
- `hive_orchestrator.core.bus` - Orchestration events

Apps that may import: ai-planner, ai-deployer

### Rule 3: Business Logic Never Crosses Apps
App business logic (outside core/) NEVER imports from other apps.

Example:
```python
# ai-planner/services/planning.py
from hive_orchestrator.core.db import create_task  # ✅ ALLOWED (core API)
from hive_orchestrator.services.deployment import deploy  # ❌ FORBIDDEN (business logic)
```
```

**Update Golden Rules Validator**:
```python
# packages/hive-tests/src/hive_tests/ast_validator.py

ALLOWED_APP_CORE_IMPORTS = {
    "ai_planner": ["hive_orchestrator.core.db", "hive_orchestrator.core.bus"],
    "ai_deployer": ["hive_orchestrator.core.db", "hive_orchestrator.core.bus"],
}

def validate_app_imports(app_name, import_statement):
    if import_from_other_app(import_statement):
        if import_statement in ALLOWED_APP_CORE_IMPORTS.get(app_name, []):
            return True  # Allowed exception
        else:
            raise ArchitecturalViolation(
                f"App {app_name} cannot import from other apps",
                severity="ERROR"
            )
```

**Effort**: 1-2 days
**Priority**: HIGH (clarifies current state)

---

### Phase 2: Extract hive-orchestration Package (Q1 2026 - 3-4 days)

**Action**: Proper architectural solution

**Steps**:
1. Create `packages/hive-orchestration/`
2. Extract task/worker interfaces and models
3. Extract database schema and operations
4. Extract orchestration events
5. Have hive-orchestrator implement interfaces
6. Update ai-planner/ai-deployer to use package
7. Remove from `ALLOWED_APP_CORE_IMPORTS`

**Effort**: 3-4 days
**Priority**: MEDIUM (proper long-term solution)

---

### Phase 3: Evaluate Other Apps (Q2 2026)

**Action**: Review other app `core/` directories for extraction opportunities

**Questions**:
1. Does guardian-agent's `core/` contain shared logic?
2. Does ecosystemiser's `core/` contain reusable patterns?
3. Should we create `hive-climate` package from ecosystemiser's climate core?

**Effort**: 1 week (investigation + extraction)
**Priority**: LOW (optimization, not urgent)

---

## VI. Guidance for AI Coding Agent

### What to Tell the Agent

```markdown
# Hive Import Rules for AI Agents

## ✅ ALWAYS ALLOWED

### 1. Package Imports
```python
from hive_logging import get_logger
from hive_config import create_config_from_sources
from hive_db import get_sqlite_connection
from hive_bus import BaseBus, BaseEvent
from hive_errors import BaseError
```

### 2. App.Core Extensions
```python
# Within an app, extend packages in core/
from hive_bus import BaseBus

class MyAppEventBus(BaseBus):  # ✅ Extends package
    """Add app-specific event handling"""
    pass
```

### 3. Internal App Imports
```python
# Within same app
from ecosystemiser.core.bus import get_ecosystemiser_event_bus
from ecosystemiser.services.solver import run_optimization
```

## ⚠️ EXCEPTION - DOCUMENTED PLATFORM APPS

### Orchestrator Core API (Public)
```python
# ai-planner, ai-deployer MAY import orchestrator core API
from hive_orchestrator.core.db import (
    create_task,
    get_connection,
    AsyncDatabaseOperations
)
from hive_orchestrator.core.bus import get_async_event_bus
```

**Why Allowed**: hive-orchestrator provides shared orchestration infrastructure.
**Future**: Will be extracted to hive-orchestration package.

## ❌ NEVER ALLOWED

### 1. App Business Logic Cross-Imports
```python
# ❌ FORBIDDEN
from ecosystemiser.services.solver import run_optimization
from ai_planner.services.planning import create_plan
```

### 2. Importing Non-Platform App Core
```python
# ❌ FORBIDDEN (unless documented)
from guardian_agent.core.cost_control import calculate_cost
from ecosystemiser.core.db import get_ecosystemiser_connection
```

### 3. Bypassing Core Extension
```python
# ❌ BAD - Direct package import in business logic when core extension exists
from hive_db import get_sqlite_connection  # Use app.core.db instead

# ✅ GOOD - Use app's extended core
from ecosystemiser.core.db import get_ecosystemiser_connection
```

## Decision Tree for Imports

```
Need to import something?
│
├─ Is it a hive-* package?
│  └─ ✅ YES → Import directly from package
│
├─ Is it from same app?
│  ├─ Within same app's core/?
│  │  └─ ✅ YES → Import from app.core
│  └─ Within same app's services/?
│     └─ ✅ YES → Import from app.services
│
└─ Is it from another app?
   ├─ Is it hive_orchestrator.core.* ?
   │  └─ ✅ YES (exception) → Import if needed for orchestration
   └─ Is it other app's business logic?
      └─ ❌ NO → Use hive-bus events or extract to package
```
```

---

## VII. Pattern Assessment Summary

### What Works Well

1. **✅ Package → App.Core Extension**
   - **Pattern**: Apps extend packages in `core/` directories
   - **Example**: ecosystemiser/core/bus.py extends hive-bus
   - **Assessment**: EXCELLENT - This is gold standard inherit→extend

2. **✅ Clear Documentation in Core**
   - **Pattern**: Each app's `core/__init__.py` documents inheritance
   - **Example**: "extends hive-db with EcoSystemiser-specific functionality"
   - **Assessment**: GOOD - Makes intent clear

3. **✅ Separation of Concerns**
   - **Pattern**: Generic (packages) vs specific (app.core)
   - **Example**: hive-db (generic) vs ecosystemiser/core/db.py (domain-specific)
   - **Assessment**: EXCELLENT - Maintains clean boundaries

### What Needs Refinement

1. **⚠️ App.Core → Other_App.Core Imports**
   - **Current**: ai-planner → hive_orchestrator.core.db
   - **Issue**: Creates coupling between apps
   - **Solution**: Extract to hive-orchestration package OR document as exception

2. **⚠️ Unclear Public vs Private Core APIs**
   - **Current**: Not clear what's "public API" in orchestrator's core
   - **Issue**: Unclear contract stability
   - **Solution**: Document public vs private in core/__init__.py

3. **⚠️ No Versioning for Core APIs**
   - **Current**: No version guarantees for core/ APIs
   - **Issue**: Breaking changes can cascade
   - **Solution**: Version orchestrator's public core API

---

## VIII. Final Recommendations

### For Your Coding Agent

**Immediate Updates to Agent Instructions**:

```markdown
## Import Pattern Rules

1. **Package Imports**: Always allowed
   ```python
   from hive_logging import get_logger  # ✅ GOOD
   ```

2. **App Core Extensions**: Always allowed within same app
   ```python
   from ecosystemiser.core.db import get_ecosystemiser_connection  # ✅ GOOD
   ```

3. **Orchestrator Core API**: Allowed for coordination apps (ai-planner, ai-deployer)
   ```python
   from hive_orchestrator.core.db import create_task  # ✅ ALLOWED (documented exception)
   ```

4. **Other App Imports**: Not allowed
   ```python
   from ecosystemiser.services.solver import optimize  # ❌ FORBIDDEN
   ```

5. **When In Doubt**: Use packages or hive-bus events
   ```python
   # Instead of importing from other app
   from hive_bus import get_event_bus
   await bus.publish(OptimizationRequestEvent(...))  # ✅ GOOD
   ```
```

### Architecture Health Assessment

**Current State**: 85% → **87%** (pattern is mostly sound)

**Adjustments from Previous Analysis**:
- ✅ Core extension pattern is valid (not a violation)
- ⚠️ Orchestrator core imports need documentation (not immediate violation)
- 💡 Still recommend hive-orchestration extraction (long-term solution)

**Revised Critical Actions**:
1. ~~Extract hive-orchestration package~~ → **Document orchestrator core API first**
2. Add golden rule exceptions for documented platform apps
3. Then extract hive-orchestration (Q1 2026)

---

## IX. Conclusion

### Is the Pattern OK?

**Yes, with clarifications**:

1. **✅ Package → App.Core**: Excellent pattern, keep using it
2. **⚠️ App.Core → Other_App.Core**: Acceptable IF:
   - Other app is designated "platform app" (like hive-orchestrator)
   - Core API is documented as public
   - Exception is documented in golden rules
   - Long-term plan to extract to package

3. **❌ App → Other_App (non-core)**: Never acceptable

### Does It Make Sense?

**Yes**, the `core/` extension pattern makes excellent architectural sense:

- **Reusability**: Packages stay generic and reusable
- **Customization**: Apps add domain-specific logic
- **Separation**: Clear boundaries between generic and specific
- **Maintainability**: Changes to packages don't break app logic
- **Testability**: Can mock package layer, test app extensions

**The only issue** is the app-to-app core imports, which should be:
1. Explicitly documented (short-term)
2. Extracted to packages (long-term)

### How to Continue

**For Your Agent**:
1. ✅ Use package imports freely
2. ✅ Use app.core extensions freely (within same app)
3. ⚠️ Use hive_orchestrator.core.* only for orchestration (ai-planner, ai-deployer)
4. ❌ Never import other app business logic
5. 💡 When shared logic needed: extract to package or use events

**For Your Platform**:
1. **Immediate** (1-2 days): Document pattern and exceptions
2. **Short-term** (Q1 2026): Extract hive-orchestration package
3. **Long-term** (Q2 2026): Review all apps for extraction opportunities

---

## Appendix: Pattern Examples

### A. Good Core Extension (ecosystemiser/core/bus.py)

```python
from hive_bus import BaseBus, BaseEvent  # ✅ Inherits from package

class EcoSystemiserEventBus(BaseBus):    # ✅ Extends with app logic
    """Extends BaseBus with simulation features"""

    def __init__(self):
        super().__init__()  # ✅ Uses parent
        self.db_path = get_ecosystemiser_db_path()  # ✅ Adds app-specific
        self._ensure_event_tables()  # ✅ Adds app-specific

    def publish_simulation_event(self, sim_id, event_type, payload):
        """✅ App-specific extension method"""
        event = SimulationEvent(
            simulation_id=sim_id,  # ✅ App-specific field
            event_type=event_type,
            payload=payload
        )
        super().publish(event)  # ✅ Uses parent method
```

**Why This Is Excellent**:
- Inherits from package (hive-bus)
- Adds domain-specific features (simulation tracking)
- Uses parent functionality (super().publish)
- Clear extension points (new methods)

---

### B. Acceptable Platform Core Import (ai-planner/agent.py)

```python
# ⚠️ ACCEPTABLE - documented exception for orchestration
from hive_orchestrator.core.db import create_task, get_connection

class PlannerAgent:
    async def execute_plan(self, plan):
        # Uses orchestrator's shared task database
        for step in plan.steps:
            task_id = await create_task(
                task_type=step.type,
                payload=step.payload
            )
```

**Why This Is Acceptable** (for now):
- Orchestrator provides platform coordination
- Task database is shared orchestration state
- Documented as allowed exception
- Will be extracted to hive-orchestration package

**Better Future State**:
```python
# ✅ IDEAL - after extraction
from hive_orchestration import OrchestrationClient

class PlannerAgent:
    def __init__(self, orchestration_client: OrchestrationClient = None):
        self.client = orchestration_client or OrchestrationClient()

    async def execute_plan(self, plan):
        for step in plan.steps:
            task_id = await self.client.create_task(
                task_type=step.type,
                payload=step.payload
            )
```

---

### C. Bad Cross-App Import (Hypothetical)

```python
# ❌ FORBIDDEN - importing business logic from another app
from ecosystemiser.services.solver import run_optimization

class DeploymentAgent:
    def deploy_with_optimization(self):
        result = run_optimization()  # ❌ BAD - tight coupling
        self.deploy(result)
```

**Why This Is Bad**:
- Couples deployment to ecosystemiser internals
- No clear interface contract
- Changes to ecosystemiser break deployer
- Makes apps non-independent

**Better Alternative**:
```python
# ✅ GOOD - use events for coordination
from hive_bus import get_event_bus

class DeploymentAgent:
    async def request_optimization(self):
        bus = get_event_bus()

        # Publish request event
        event_id = await bus.publish(OptimizationRequestedEvent(
            requester="deployment-agent",
            parameters={"target": "energy-efficiency"}
        ))

        # Subscribe to response
        @bus.subscribe(f"optimization.completed.{event_id}")
        async def handle_result(event):
            self.deploy(event.result)
```

---

**Document Complete**: Ready for agent consumption and architectural refinement.
