from hive_logging import get_logger

logger = get_logger(__name__)

"""
Hive Orchestrator Core Components - PLATFORM INFRASTRUCTURE

This core module serves as PLATFORM INFRASTRUCTURE for task orchestration
across the Hive platform. Other apps MAY import from designated PUBLIC APIs
documented below.

========================================================================
PUBLIC API (v1.0.0) - Other Apps May Import
========================================================================

Database Operations (hive_orchestrator.core.db):
------------------------------------------------
Task Management:
- create_task(task_type, payload, **kwargs) -> str
  Create a new orchestration task

- get_task(task_id) -> dict | None
  Retrieve task by ID

- update_task_status(task_id, status) -> None
  Update task execution status

- get_tasks_by_status(status) -> list[dict]
  Get all tasks with given status

Connection Management:
- get_connection() -> Connection
  Get database connection (sync)

- get_pooled_connection() -> Connection
  Get pooled database connection (sync)

- AsyncDatabaseOperations class
  Async database operations interface

- get_async_db_operations() -> AsyncDatabaseOperations
  Get async database operations instance

Event Bus (hive_orchestrator.core.bus):
----------------------------------------
- get_async_event_bus() -> AsyncEventBus
  Get the orchestrator's async event bus for coordination

Apps Allowed to Import This API:
---------------------------------
- ai-planner: Task planning and execution coordination
- ai-deployer: Deployment task orchestration

Usage Example:
--------------
```python
from hive_orchestrator.core.db import create_task, get_tasks_by_status
from hive_orchestrator.core.bus import get_async_event_bus

# Create orchestration task
task_id = await create_task(
    task_type="deployment",
    payload={"script": "deploy.sh", "env": "production"}
)

# Get pending tasks
pending = await get_tasks_by_status("pending")

# Coordinate via events
bus = get_async_event_bus()
await bus.publish(TaskCreatedEvent(task_id=task_id))
```

========================================================================
PRIVATE APIs - DO NOT IMPORT
========================================================================

The following are internal implementation details and MUST NOT be
imported by other apps:

- core.claude: Claude AI integration (implementation detail)
- core.monitoring: Internal monitoring logic (implementation detail)
- core.errors.hive_errors: Internal error handling (implementation detail)

========================================================================
DEPRECATION POLICY
========================================================================

Public APIs follow semantic versioning (v1.0.0):
- Major version: Breaking changes (require code updates)
- Minor version: New features (backward compatible)
- Patch version: Bug fixes (backward compatible)

Breaking changes require:
1. One release cycle deprecation notice
2. Deprecation warnings in logs
3. Migration guide in documentation
4. Minimum 3-month notice period

========================================================================
FUTURE ROADMAP
========================================================================

This public API will be extracted to a dedicated 'hive-orchestration'
package in Q1 2026. Apps currently using this API should plan for
migration:

Timeline:
- Q4 2025: hive-orchestration package development
- Q1 2026: Package release with migration guide
- Q2 2026: Migrate ai-planner and ai-deployer
- Q3 2026: Deprecate direct core imports
- Q4 2026: Remove platform exception (package only)

New apps should anticipate this migration and design accordingly.

========================================================================
ARCHITECTURE PATTERN
========================================================================

This follows the "inherit → extend" pattern:
- Generic packages (hive-db, hive-bus) provide reusable infrastructure
- Core components add orchestration-specific business logic
- Apps use orchestrator's extended functionality via documented API

For more information: .claude/ARCHITECTURE_PATTERNS.md

========================================================================
"""

# Core modules are imported as needed by specific components
# No re-exports at this level to maintain clear module boundaries
