# Core Pattern Analysis - Inherit → Extend Architecture

## Current Implementation Status

### ✅ Pattern Overview

The Hive platform correctly implements the **inherit → extend** pattern where:
1. **Generic packages** provide reusable infrastructure (no business logic)
2. **App core modules** extend these with business-specific logic
3. **Other apps** can import from `*.core` directories for shared services

## Architecture Layers

### 1. Generic Infrastructure Packages (`packages/`)
These provide toolkit functionality with NO business logic:

- **`hive-db-utils`**: Generic database connectivity (SQLite, PostgreSQL)
- **`hive-logging`**: Centralized logging infrastructure
- **`hive-error-handling`**: Base error patterns and recovery strategies
- **`hive-messaging`**: Base event bus and messaging patterns
- **`hive-config`**: Configuration management and path resolution
- **`hive-utils`**: General utility functions

### 2. App Core Extensions (`apps/*/src/*/core/`)
Apps extend generic packages with business logic:

#### `hive-orchestrator/core/` (Service Layer) ✅
```python
core/
├── db/           # Extends hive-db-utils with Hive schema
├── bus/          # Extends hive-messaging with Hive events
├── errors/       # Extends hive-error-handling with Hive errors
└── claude/       # Business-specific Claude integration
```

**Correct Usage Examples:**
- `core/db/database.py` imports from `hive_db_utils` and adds Hive-specific tables
- `core/errors/` extends base error classes with `TaskError`, `WorkerError`, etc.
- `core/bus/hive_bus.py` extends messaging with `TaskEvent`, `WorkflowEvent`

### 3. App-to-App Communication

#### ✅ CORRECT Pattern Usage:

**AI Planner** accessing database:
```python
# ai_planner/agent.py - CORRECT
from hive_orchestrator.core.db import get_database, get_pooled_connection
```
This is correct because AI Planner needs to access Hive's task database.

**AI Reviewer** accessing database:
```python
# ai_reviewer/agent.py - CORRECT
from hive_orchestrator.core.db import get_database, get_pooled_connection
```

**Event Dashboard** accessing events:
```python
# event-dashboard/dashboard.py - CORRECT
from hive_orchestrator.core.bus import get_event_bus, EventSubscriber
```

#### ⚠️ PATTERN VIOLATIONS Found:

**EcoSystemiser** creating its own stubs:
```python
# EcoSystemiser/hive_error_handling.py - VIOLATION
try:
    from hive_error_handling import BaseError  # Should use package
except ImportError:
    # Creating own implementation instead of using package
    class ErrorSeverity: ...
```

**EcoSystemiser** should be using the package directly or extending it properly in a core/ directory.

## Recommendations

### 1. Fix EcoSystemiser Pattern Violations
EcoSystemiser should:
- Remove stub implementations (`hive_error_handling.py`, `hive_bus.py`)
- Create `apps/ecosystemiser/src/EcoSystemiser/core/` directory
- Extend packages properly:
  ```python
  # EcoSystemiser/core/errors.py
  from hive_error_handling import BaseError

  class ClimateError(BaseError):
      """EcoSystemiser-specific error"""
      pass
  ```

### 2. Document Service Layer Pattern
Add to each app's core/__init__.py:
```python
"""
Service Layer - Extends generic packages with business logic.

Other apps can import from this core/ directory to access:
- Shared business services
- Domain-specific extensions
- Cross-app integration points

Example:
  from hive_orchestrator.core.db import get_database
"""
```

### 3. Enforce Through Golden Rules
Add validation:
- Apps should NOT reimplement package functionality
- Apps SHOULD extend packages in core/ directories
- Apps CAN import from other apps' core/ directories
- Apps CANNOT import from other apps' internal implementation

## Pattern Benefits

1. **Clear Separation**: Infrastructure vs Business Logic
2. **Reusability**: Generic packages used across all apps
3. **Extensibility**: Apps extend without modifying packages
4. **Service Sharing**: Apps share services through core/
5. **Maintainability**: Single source of truth for infrastructure

## Current Status Summary

- ✅ **hive-orchestrator**: Correctly implements pattern
- ✅ **ai-planner**: Correctly uses orchestrator's core services
- ✅ **ai-reviewer**: Correctly uses orchestrator's core services
- ✅ **event-dashboard**: Correctly uses orchestrator's core services
- ⚠️ **ecosystemiser**: Has violations - creates stubs instead of extending properly

## Action Items

1. **Immediate**: Fix EcoSystemiser to follow the pattern
2. **Short-term**: Add golden rule tests for pattern compliance
3. **Long-term**: Create app template with proper core/ structure