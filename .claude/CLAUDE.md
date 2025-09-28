# Fleet Command Protocol v4.0 - Automated Multi-Agent System

You are part of the Hive Fleet Command system. Each agent is a claude code instance running in a tmux pane with full automation support.

## Fleet Structure (Perfect 2x2 Grid)
- **Queen (Pane 0 - top-left)**: Fleet commander and mission orchestrator
- **Frontend Worker (Pane 1 - top-right)**: React/Next.js specialist  
- **Backend Worker (Pane 2 - bottom-left)**: Python/Flask/FastAPI specialist
- **Infra Worker (Pane 3 - bottom-right)**: Docker/Kubernetes/CI specialist

## For the Queen: Mission Execution Protocol

### 1. Receive Mission
The Fleet Admiral (human) will type a mission directly into your terminal.

### 2. Create Battle Plan
Analyze the mission and create a detailed plan with task IDs:
```
[T101] Backend: Create API endpoints
[T102] Frontend: Build UI components  
[T103] Infra: Setup deployment
```

### 3. Command Workers via Automation System
Execute automated commands to send tasks to workers. **Fleet Command v4.0 provides full automation with expect-based delivery.**

```bash
# ✅ AUTOMATED: Use fleet_send.sh for reliable delivery
./scripts/fleet_send.sh send backend "[T101] Backend Worker, implement user authentication API with JWT. Use TDD. Report: STATUS: success when done."

# ✅ BROADCAST: Send to all workers simultaneously
./scripts/fleet_send.sh broadcast "Fleet status report requested"

# ✅ FILE-BASED: Send large tasks via message bus
./scripts/hive-send --to frontend --topic task --file task_description.md

# Working examples with full automation:
./scripts/fleet_send.sh send frontend "[T102] Frontend Worker, create login form component. Write tests first. Report: STATUS: success when done."
./scripts/fleet_send.sh send infra "[T103] Infra Worker, containerize the application with Docker. Report: STATUS: success when done."
```

### 4. Autonomous Communication System
Workers communicate through automated message bus and direct pane interaction:
- **Message Bus**: Structured JSON messages via hive-send/hive-recv tools
- **Direct Delivery**: Automated expect-based message injection to panes
- **Status Monitoring**: Real-time dashboard via hive-status command
- **Two-Way Flow**: Queen ↔ Workers autonomous communication

**Message Bus Commands:**
```bash
# Send structured message
./scripts/hive-send --to backend --topic task --priority high --message "Implement authentication"

# Receive messages  
./scripts/hive-recv --for frontend --unread-only --mark-read

# Monitor overall status
./scripts/hive-status --detailed --watch
```

### 5. Handle Git Operations
Once all workers complete:
```bash
git add .
git commit -m "feat: implement [mission description]"
git push origin main
gh pr create --title "Mission: [description]" --body "Implemented by Fleet Command"
```

### 6. Report Completion
Type: "MISSION COMPLETE: [summary of achievements]"

## For Workers: Task Execution Protocol

### 1. Receive Commands
Commands from Queen will appear in your terminal with format: `[T###] Task description`

### 2. Acknowledge
Type: "Acknowledged [T###]. Starting implementation..."

### 3. Execute with TDD (when applicable)
- Write tests first (RED phase)
- Implement minimal code (GREEN phase)
- Refactor (REFACTOR phase)

### 4. Report Status
Always end with:
```
STATUS: success|failed|blocked
CHANGES: files modified or created
NEXT: recommended action
```

## Fleet Command v4.0 Features

### Full Automation Capabilities
- **Expect Integration**: Robust message delivery with retry logic and readiness detection
- **Message Bus**: Structured JSON-based communication system
- **Error Recovery**: Automatic fallback and error handling mechanisms
- **Large Message Support**: Chunked delivery for complex task descriptions

### Automation Tools Available
```bash
# Direct pane automation (immediate execution)
./scripts/fleet_send.sh send <agent> "<message>"
./scripts/fleet_send.sh broadcast "<message>"
./scripts/fleet_send.sh test

# Message bus system (persistent communication)
./scripts/hive-send --to <agent> --topic <topic> --message "<message>"
./scripts/hive-recv --for <agent> --unread-only --mark-read
./scripts/hive-status --detailed --watch

# System validation
./scripts/readiness_test.sh
./scripts/test_automation.sh
```

### Communication Protocols
**Immediate Execution**: Messages are automatically injected into agent REPLs
**Persistent Bus**: Messages stored in JSON format for asynchronous processing
**Status Monitoring**: Real-time dashboard shows message counts and agent activity

### Safety Guardrails
- No infinite loops in monitoring
- Clear task IDs prevent confusion
- Workers validate commands before executing
- Human can intervene in any pane at any time
- All commands are visible and auditable

## Example Mission Flow

**Fleet Admiral types in Queen's terminal:**
```
Create a health check API endpoint at /api/health that returns {"status": "ok", "timestamp": "<current_time>"}
```

**Queen's response:**
```
Mission received. Creating battle plan...

[T101] Backend: Implement /api/health endpoint with TDD
[T102] Frontend: Create health status display component
[T103] Infra: Add health check to Docker configuration

Delegating to workers...
```

**Queen executes:**
```bash
tmux send-keys -t hive-swarm:0.1 "[T101] Backend Worker, create /api/health endpoint that returns status and timestamp. Use TDD. Report STATUS when complete."
```

**Queen monitors:**
```bash
# After 30 seconds
tmux capture-pane -pt hive-swarm:0.1 -S -20
# Sees: "STATUS: success"
```

**Queen completes mission:**
```bash
git add .
git commit -m "feat: add health check endpoint"
git push origin main
gh pr create --title "Add health check API" --body "Implements /api/health endpoint with timestamp"
```

**Queen reports:**
```
MISSION COMPLETE: Health check API implemented, tested, and deployed.
- Backend: /api/health endpoint created with tests
- Frontend: Status display component ready
- Infra: Docker health checks configured
- PR #42 created and ready for review
```

## Fleet Command Benefits

### Total Transparency
- All communication visible in tmux panes
- Human can monitor all agent activity in real-time
- Every command and response is human-readable

### Human-in-the-Loop
- Fleet Admiral can intervene at any time
- Click into any pane to provide guidance
- Override or assist any agent directly

### Collaborative Intelligence
- Natural language enables complex, nuanced instructions
- Agents can ask for clarification when needed
- Emergent problem-solving through agent collaboration

### Simplified Architecture
- No Python orchestration code needed
- All intelligence resides in claude code agents
- Natural language is the universal communication bus
- Standard tmux commands provide reliable automation

## Windows Terminal Note
If running in Windows (non-WSL), emojis may not display correctly. The system will still function normally - the emojis are just visual indicators.

# ═══════════════════════════════════════════════════
# HIVE MODULAR MONOLITH ARCHITECTURE
# ═══════════════════════════════════════════════════

## Architecture Overview

Hive uses a **Modular Monolith** architecture with Poetry workspace dependencies, following the **"inherit → extend"** pattern to ensure clean separation between generic infrastructure and app-specific business logic.

### Core Principles

1. **Poetry Workspace Dependencies**: All imports handled via path references in pyproject.toml
2. **Dependency Direction**: Apps → Packages ✅ | Packages → Apps ❌
3. **Core Service Layer**: Each app has `core/` modules that extend generic packages
4. **Golden Rules Enforcement**: 10+ architectural rules prevent pattern violations
5. **No Path Manipulation**: Never use `sys.path` - Poetry handles all imports

## Project Structure

```
C:\git\hive\
├── apps/                           # Application services
│   ├── ai-planner/                 # AI planning service
│   │   ├── src/ai_planner/
│   │   │   ├── core/               # ⭐ Core extensions
│   │   │   │   ├── __init__.py
│   │   │   │   └── error.py        # Extends hive-error-handling
│   │   │   ├── agent.py            # Main business logic
│   │   │   └── ...
│   │   └── pyproject.toml          # Poetry deps with path refs
│   ├── ai-reviewer/                # Code review service
│   │   ├── src/ai_reviewer/
│   │   │   ├── core/               # ⭐ Core extensions
│   │   │   │   ├── __init__.py
│   │   │   │   └── error.py        # Extends hive-error-handling
│   │   │   └── ...
│   │   └── pyproject.toml
│   ├── ecosystemiser/              # Energy system modeling
│   │   ├── src/EcoSystemiser/
│   │   │   ├── core/               # ⭐ Reference implementation
│   │   │   │   ├── __init__.py
│   │   │   │   └── errors.py       # Pattern example
│   │   │   └── ...
│   │   └── pyproject.toml
│   └── hive-orchestrator/          # System orchestration
│       ├── src/hive_orchestrator/
│       │   ├── core/               # ⭐ Core extensions
│       │   │   └── db/             # Extended database layer
│       │   └── ...
│       └── pyproject.toml
└── packages/                       # Generic infrastructure
    ├── hive-config/                # Configuration management
    ├── hive-db-utils/              # Database utilities
    ├── hive-error-handling/        # Error handling framework
    ├── hive-logging/               # Logging infrastructure
    ├── hive-messaging/             # Event bus and messaging
    └── hive-testing-utils/         # Testing framework
```

## "Inherit → Extend" Pattern

### ✅ CORRECT Pattern Implementation

**1. Apps extend packages in their core/ modules:**

```python
# apps/ai-planner/src/ai_planner/core/error.py
from hive_error_handling import BaseError, BaseErrorReporter

class PlannerError(BaseError):
    """Extends BaseError with AI Planner-specific context"""
    def __init__(self, message: str, component: str = "ai-planner",
                 task_id: Optional[str] = None, plan_id: Optional[str] = None, **kwargs):
        super().__init__(message=message, component=component, **kwargs)
        self.task_id = task_id
        self.plan_id = plan_id
```

**2. Business logic imports from core/ extensions:**

```python
# apps/ai-planner/src/ai_planner/agent.py
from ai_planner.core.error import PlannerError, TaskProcessingError
from hive_logging import get_logger

logger = get_logger(__name__)
```

**3. Poetry workspace dependencies:**

```toml
# apps/ai-planner/pyproject.toml
[tool.poetry.dependencies]
python = "^3.11"

# Hive workspace dependencies
hive-config = {path = "../../packages/hive-config", develop = true}
hive-db-utils = {path = "../../packages/hive-db-utils", develop = true}
hive-logging = {path = "../../packages/hive-logging", develop = true}
hive-error-handling = {path = "../../packages/hive-error-handling", develop = true}
hive-messaging = {path = "../../packages/hive-messaging", develop = true}
```

### ❌ ANTI-PATTERNS (Forbidden)

```python
# ❌ NEVER: Direct import of generic classes in business logic
from hive_error_handling import BaseError  # Use core.error.PlannerError instead

# ❌ NEVER: Path manipulation
import sys
sys.path.insert(0, "../../packages")  # Poetry handles this

# ❌ NEVER: Direct logging import
import logging  # Use hive_logging.get_logger() instead

# ❌ NEVER: Package imports app
# packages/hive-logging/src/hive_logging/logger.py
from ai_planner.agent import AIPlanner  # Violates dependency direction
```

## Core Service Layer Pattern

Each app MUST implement a `core/` directory with extensions:

### Required Core Modules

```python
# apps/{app}/src/{app}/core/__init__.py
"""
{App} Core Components.

Contains the core infrastructure that extends generic Hive packages:
- Error handling (extends hive-error-handling)
- Event bus (extends hive-messaging)
- Database layer (extends hive-db-utils)
- {App}-specific service interfaces

This follows the "inherit → extend" pattern:
- Generic packages provide reusable infrastructure
- Core components add {App}-specific business logic
"""

# Core modules are imported as needed by specific components
# No re-exports at this level to maintain clear module boundaries
```

```python
# apps/{app}/src/{app}/core/error.py
"""
{App}-specific error handling implementation.

Extends the generic error handling toolkit with {App} capabilities.
"""

from hive_error_handling import BaseError, BaseErrorReporter
from hive_logging import get_logger

logger = get_logger(__name__)

class {App}Error(BaseError):
    """Base error class for all {App}-specific errors."""
    def __init__(self, message: str, component: str = "{app}", **kwargs):
        super().__init__(message=message, component=component, **kwargs)
        # Add app-specific attributes
```

## Golden Rules Enforcement

The following rules are automatically tested and MUST be followed:

### 1. **App Contract**: Apps must have proper pyproject.toml structure
### 2. **Colocated Tests**: Tests in tests/ directories, not alongside source
### 3. **No Path Hacks**: Never use `sys.path.insert()` or `sys.path.append()`
### 4. **No Direct App Imports**: Packages cannot import from apps
### 5. **Logging Standards**: Use `hive_logging.get_logger()`, never direct `logging`
### 6. **Error Handling**: Use core error classes, extend `hive_error_handling`

**Test Location**: `apps/hive-orchestrator/tests/test_golden_rules.py`

## Development Workflow

### 1. Creating New Apps

```bash
# 1. Create app structure
mkdir -p apps/my-app/src/my_app/core
mkdir -p apps/my-app/tests

# 2. Create pyproject.toml with workspace deps
cd apps/my-app
# Add Poetry dependencies using path references

# 3. Implement core/ extensions
# Create core/__init__.py and core/error.py following pattern

# 4. Implement business logic importing from core/
# Import from my_app.core.error, not hive_error_handling directly

# 5. Run golden rules tests
cd ../..
python -m pytest apps/hive-orchestrator/tests/test_golden_rules.py -v
```

### 2. Adding New Packages

```bash
# 1. Create package in packages/
mkdir -p packages/hive-new-feature/src/hive_new_feature

# 2. Design generic, reusable interfaces
# NO app-specific logic in packages

# 3. Add to workspace dependencies in apps that need it
# Update app pyproject.toml files with path reference

# 4. Extend in app core/ modules as needed
```

### 3. Code Quality Checks

```bash
# Run golden rules (architectural compliance)
python -m pytest apps/hive-orchestrator/tests/test_golden_rules.py -v

# Run app-specific tests
python -m pytest apps/ai-planner/tests/ -v
python -m pytest apps/ai-reviewer/tests/ -v

# Check import violations
grep -r "from hive_error_handling import" apps/*/src/*/
# Should only find imports in core/ modules
```

## Import Strategy

### ✅ Correct Import Patterns

```python
# In app business logic (e.g., agent.py)
from ai_planner.core.error import PlannerError, TaskProcessingError
from hive_logging import get_logger
from hive_config import get_config

# In app core/ modules (e.g., core/error.py)
from hive_error_handling import BaseError, BaseErrorReporter
from hive_logging import get_logger

# In packages (generic infrastructure)
from typing import Dict, Any, Optional
# NO imports from apps/ directory
```

### ❌ Forbidden Import Patterns

```python
# ❌ Business logic importing generic classes directly
from hive_error_handling import BaseError  # Use core.error.AppError

# ❌ Any sys.path manipulation
import sys
sys.path.insert(0, "...")

# ❌ Direct logging imports
import logging  # Use hive_logging.get_logger()

# ❌ Packages importing from apps
from ai_planner.agent import AIPlanner  # Violates dependency direction
```

## Key Architecture Benefits

1. **Clean Separation**: Generic infrastructure vs app-specific logic
2. **Reusability**: Packages can be used across multiple apps
3. **Maintainability**: Clear dependency direction prevents circular imports
4. **Testability**: Each layer can be tested independently
5. **Extensibility**: New apps follow established patterns
6. **Compliance**: Golden rules enforce architectural consistency

## Memory Notes for Agent

When working on Hive codebase:

1. **ALWAYS** check if core/ modules exist before creating error classes
2. **NEVER** import `hive_error_handling.BaseError` directly in business logic
3. **ALWAYS** use `hive_logging.get_logger()` instead of `logging`
4. **NEVER** use `sys.path` manipulation - Poetry handles imports
5. **ALWAYS** run golden rules tests after architectural changes
6. **FOLLOW** the ecosystemiser core/errors.py pattern for new apps
7. **MAINTAIN** dependency direction: Apps → Packages only
8. **USE** Poetry workspace path dependencies for all internal imports

This architecture ensures clean, maintainable, and scalable code that follows established patterns and prevents common architectural anti-patterns.

# ═══════════════════════════════════════════════════
# POETRY DEPENDENCY MANAGEMENT WORKFLOW
# ═══════════════════════════════════════════════════

## How Poetry Works with Hive Workspace

### **No Poetry Unlock Required for Package Updates**

Poetry workspace dependencies with `develop = true` automatically use the latest local code:

```toml
# In any app's pyproject.toml
[tool.poetry.dependencies]
hive-logging = {path = "../../packages/hive-logging", develop = true}
```

**Key Benefits:**
- **Editable Installs**: Changes to package source code are immediately available
- **No Lock File Updates**: poetry.lock doesn't need updating for local package changes
- **Live Development**: Edit packages/hive-logging/src and all apps see changes instantly
- **Zero Friction**: No `poetry update` or `poetry install` needed for local changes

### **When to Update Poetry.lock**

poetry.lock only needs updating when:
- **External dependencies change** (new PyPI packages, version bumps)
- **New workspace apps added** (new path dependencies)
- **Poetry configuration changes** (build system, scripts)

```bash
# Only needed for external dependency changes
poetry lock --no-update
poetry install
```

### **Dependency Management Commands**

```bash
# ✅ Add new external dependency
cd apps/my-app
poetry add requests

# ✅ Add new workspace dependency
cd apps/my-app
poetry add --editable ../../packages/hive-new-package

# ✅ Update external dependencies
poetry update requests

# ❌ NOT NEEDED: Update workspace packages
# Changes are automatically available!
```

### **Development Workflow**

**1. Normal Development (No Poetry Commands Needed):**
```bash
# Edit any package
vim packages/hive-logging/src/hive_logging/logger.py

# Use immediately in any app
python apps/ai-planner/src/ai_planner/agent.py
# ↑ Automatically uses latest hive-logging code
```

**2. Adding New Dependencies:**
```bash
# External package
cd apps/my-app
poetry add pandas

# Workspace package
cd apps/my-app
poetry add --editable ../../packages/hive-utils
```

**3. Creating New Apps:**
```bash
# 1. Create app structure
mkdir -p apps/new-app/src/new_app/core

# 2. Create pyproject.toml with workspace deps
cd apps/new-app
poetry init
poetry add --editable ../../packages/hive-config
poetry add --editable ../../packages/hive-logging
poetry add --editable ../../packages/hive-error-handling

# 3. Implement core/ extensions following patterns
```

## Poetry Architecture Benefits

### **1. Instant Development Feedback**
- Edit package → Test immediately in apps
- No intermediate build/install steps
- True live development experience

### **2. Consistent Dependency Resolution**
- All apps use same package versions
- poetry.lock ensures reproducible builds
- Workspace ensures local consistency

### **3. Clean Separation of Concerns**
- **Local packages**: Use `develop = true` for instant updates
- **External packages**: Managed through poetry.lock for stability
- **Clear distinction**: Workspace vs external dependencies

### **4. Team Collaboration**
- poetry.lock tracks external dependencies precisely
- Workspace dependencies always use latest local code
- No "works on my machine" issues with local packages

## Common Patterns

### **Package Development Cycle**
```bash
# 1. Edit package (no commands needed)
vim packages/hive-logging/src/hive_logging/logger.py

# 2. Test in multiple apps (automatic)
python apps/ai-planner/tests/test_logging.py  # Uses latest immediately
python apps/ai-reviewer/tests/test_logging.py # Uses latest immediately

# 3. Run tests across workspace
python -m pytest packages/hive-logging/tests/
python -m pytest apps/*/tests/
```

### **Adding New Package Features**
```bash
# 1. Implement in generic package
vim packages/hive-error-handling/src/hive_error_handling/new_feature.py

# 2. Extend in app core modules (automatic import)
vim apps/ai-planner/src/ai_planner/core/error.py
# Add: from hive_error_handling import NewFeature

# 3. Use in business logic (follows pattern)
vim apps/ai-planner/src/ai_planner/agent.py
# Add: from ai_planner.core.error import AppSpecificError
```

### **Dependency Troubleshooting**

**Problem**: ImportError for workspace package
```bash
# ✅ Solution: Check Poetry workspace installation
poetry install

# ✅ Verify editable install
poetry show --tree | grep hive-

# ✅ Check path references in pyproject.toml
grep -r "path.*hive-" apps/*/pyproject.toml
```

**Problem**: Old code still running
```bash
# ✅ Verify develop=true in pyproject.toml
grep -A5 "\[tool\.poetry\.dependencies\]" apps/my-app/pyproject.toml

# ✅ Reinstall if needed
cd apps/my-app && poetry install
```

## Summary

**Poetry + Workspace = Zero-Friction Development**

- ✅ **Edit packages**: Changes immediately available everywhere
- ✅ **No unlock needed**: poetry.lock stays stable for local changes
- ✅ **True editable installs**: Development feels seamless
- ✅ **External deps managed**: poetry.lock controls PyPI packages
- ✅ **Team consistency**: Everyone gets same environment

**Remember**: The power of `develop = true` means you edit once, run everywhere instantly!