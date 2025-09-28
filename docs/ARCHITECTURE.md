# Hive Platform Architecture

## Overview

Hive is a multi-agent orchestration system that follows a clean architecture pattern with clear separation of concerns between infrastructure packages and business applications.

## Core Principles

### 1. Inherit → Extend Pattern
- **Packages** provide generic, reusable infrastructure (inherit layer)
- **Apps** contain business logic and extend packages with domain-specific functionality
- Business logic ALWAYS lives in apps, never in packages

### 2. Service Layer Pattern
Apps can expose service interfaces through a `core/` subdirectory:
- `app/src/app_name/core/` = Service API layer (other apps can import)
- `app/src/app_name/` = Internal implementation (forbidden to import)

### 3. Communication Patterns
Apps communicate through well-defined channels:
- **Database Queues**: Task queues for asynchronous work
- **Event Bus**: Pub/sub for real-time notifications
- **REST APIs**: HTTP endpoints for synchronous operations
- **Service Layers**: Direct imports from `app.core` modules

## Directory Structure

```
hive/
├── packages/               # Generic infrastructure (inherit layer)
│   ├── hive-utils/        # File operations, paths, utilities
│   ├── hive-logging/      # Logging infrastructure
│   ├── hive-db-utils/     # Database connections, transactions
│   ├── hive-messaging/    # Event bus, pub/sub infrastructure
│   ├── hive-config/       # Configuration management
│   ├── hive-deployment/   # Deployment utilities
│   ├── hive-testing-utils/# Testing infrastructure
│   └── hive-error-handling/# Error handling base classes
│
├── apps/                   # Business applications (extend layer)
│   ├── hive-orchestrator/  # Core orchestration platform
│   │   ├── src/
│   │   │   └── hive_orchestrator/
│   │   │       ├── core/   # Service API layer (exposed)
│   │   │       │   ├── db/ # Database service extensions
│   │   │       │   ├── bus/# Event bus service extensions
│   │   │       │   └── errors/# Error handling extensions
│   │   │       ├── queen.py   # Orchestrator implementation
│   │   │       └── worker.py  # Worker implementation
│   │   └── hive-app.toml  # App contract declaration
│   │
│   ├── ai-planner/        # AI planning agent
│   │   ├── src/
│   │   │   └── ai_planner/
│   │   │       └── agent.py  # Planning business logic
│   │   └── hive-app.toml
│   │
│   ├── ai-reviewer/       # AI review agent
│   │   ├── src/
│   │   │   └── ai_reviewer/
│   │   │       └── agent.py  # Review business logic
│   │   └── hive-app.toml
│   │
│   └── ecosystemiser/     # Ecosystem optimization
│       ├── src/
│       │   └── EcoSystemiser/
│       │       ├── api.py     # REST API endpoints
│       │       └── cli.py     # CLI interface
│       └── hive-app.toml
```

## Dependency Rules

### Allowed Dependencies

✅ **App → Infrastructure Package**
```python
# apps/ai-planner/agent.py
from hive_logging import get_logger  # OK: Using infrastructure
from hive_utils.paths import PROJECT_ROOT  # OK: Using utilities
```

✅ **App → App's Service Layer (core/)**
```python
# apps/ai-reviewer/agent.py
from hive_orchestrator.core.db import get_database  # OK: Using service layer
from hive_orchestrator.core.bus import get_event_bus  # OK: Using service layer
```

✅ **Package → Package (infrastructure only)**
```python
# packages/hive-db-utils/database.py
from hive_logging import get_logger  # OK: Infrastructure using infrastructure
from hive_error_handling import BaseError  # OK: Infrastructure dependency
```

### Forbidden Dependencies

❌ **Package → App**
```python
# packages/hive-utils/helper.py
from ai_planner import PlannerService  # FORBIDDEN: Package depends on app
```

❌ **App → App's Internal Implementation**
```python
# apps/ai-reviewer/agent.py
from ai_planner.agent import PlannerAgent  # FORBIDDEN: Direct app import
from ecosystemiser.cli import run_command  # FORBIDDEN: Not from core/
```

❌ **Business Logic in Packages**
```python
# packages/hive-utils/business.py
class TaskWorkflow:  # FORBIDDEN: Business logic in package
    def process_ai_task(self):
        pass
```

## Communication Patterns

### 1. Database Queues (Asynchronous)
Apps communicate through task queues in the database:

```python
# Producer (ai-planner)
task = {
    "type": "review_request",
    "status": "pending",
    "payload": {...}
}
db.insert_task(task)

# Consumer (ai-reviewer)
pending_tasks = db.get_tasks_by_status("pending")
for task in pending_tasks:
    process_review(task)
```

### 2. Event Bus (Real-time)
Apps publish and subscribe to events:

```python
# Publisher
from hive_orchestrator.core.bus import get_event_bus
bus = get_event_bus()
bus.publish("task.completed", {"task_id": "123"})

# Subscriber
@bus.subscribe("task.completed")
def on_task_completed(event):
    print(f"Task {event['task_id']} completed")
```

### 3. REST APIs (Synchronous)
Apps expose HTTP endpoints for external communication:

```python
# Server (ecosystemiser)
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/climate/data")
async def get_climate_data(location: str):
    return {"temperature": 25.5}

# Client (another app or external)
response = requests.get("http://ecosystemiser/api/climate/data")
```

### 4. Service Layers (Direct Import)
Apps can import from other apps' core service layers:

```python
# Service provider (hive-orchestrator)
# hive_orchestrator/core/db/__init__.py
class DatabaseService:
    def get_connection(self):
        return self.connection_pool.get()

# Service consumer (ai-reviewer)
from hive_orchestrator.core.db import DatabaseService
db = DatabaseService()
conn = db.get_connection()
```

## Background Processes

Apps can run as background daemons defined in `hive-app.toml`:

```toml
[daemons.default]
description = "Main agent loop"
command = "python src/agent.py"
restart_on_failure = true
restart_delay_seconds = 30
```

### Daemon Patterns

1. **Polling Agents**: Continuously check for work
```python
while True:
    tasks = db.get_pending_tasks()
    for task in tasks:
        process(task)
    time.sleep(POLL_INTERVAL)
```

2. **Event-Driven Agents**: React to events
```python
@bus.subscribe("task.created")
async def handle_task(event):
    await process_task(event["task_id"])

bus.run_forever()
```

3. **API Servers**: Serve HTTP requests
```python
uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Service Layer Rules

### What Goes in core/

✅ **Service Interfaces**
```python
# hive_orchestrator/core/db/service.py
class DatabaseService:
    def get_connection(self) -> Connection:
        """Get database connection from pool"""
        pass
```

✅ **Event Definitions**
```python
# hive_orchestrator/core/bus/events.py
class TaskEvent:
    task_id: str
    status: str
    timestamp: datetime
```

✅ **Shared Types and Models**
```python
# hive_orchestrator/core/models.py
class TaskStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
```

### What Stays in App Implementation

❌ **Business Logic**
```python
# Should be in ai_planner/agent.py, NOT in core/
def create_ai_plan(requirements):
    # Complex planning algorithm
    return plan
```

❌ **Workflow Orchestration**
```python
# Should be in queen.py, NOT in core/
def orchestrate_workflow(task):
    # Business workflow logic
    pass
```

❌ **Domain-Specific Processing**
```python
# Should be in ai_reviewer/reviewer.py, NOT in core/
def analyze_code_quality(code):
    # Review logic
    return score
```

## Testing Strategy

### Unit Tests
- Test packages in isolation
- Mock service layer dependencies
- Focus on business logic correctness

### Integration Tests
- Test app-to-app communication
- Verify service layer contracts
- Test database queue processing
- Validate event bus messaging

### Golden Rule Tests
- Enforce architectural patterns
- Run locally: `golden-test --app <app-name>`
- Run globally: `golden-test`
- CI/CD integration for automatic validation

## Best Practices

1. **Keep Service Layers Thin**: Only expose necessary interfaces
2. **Document Service Contracts**: Clear API documentation in core/
3. **Version Service APIs**: Handle backward compatibility
4. **Use Type Hints**: Enforce contracts with typing
5. **Log Service Calls**: Track inter-app communication
6. **Handle Failures Gracefully**: Service calls can fail
7. **Avoid Circular Dependencies**: Plan service dependencies carefully

## Migration Guide

### Moving from Direct Imports to Service Layers

Before (Forbidden):
```python
# ai-reviewer importing directly from ai-planner
from ai_planner.agent import PlannerAgent
planner = PlannerAgent()
plan = planner.create_plan(task)
```

After (Correct):
```python
# Option 1: Use database queue
db.insert_task({"type": "plan_request", "payload": task})

# Option 2: Use event bus
bus.publish("plan.requested", {"task": task})

# Option 3: Use REST API
response = requests.post("http://ai-planner/api/plan", json=task)

# Option 4: Use service layer (if exposed)
from ai_planner.core.service import PlannerService
service = PlannerService()
plan = service.create_plan(task)
```

## Platform Evolution

The Hive architecture is designed to evolve:

1. **Phase 1**: Current state with service layers
2. **Phase 2**: Add gRPC for high-performance communication
3. **Phase 3**: Containerize apps for independent deployment
4. **Phase 4**: Add service mesh for advanced routing
5. **Phase 5**: Full microservices with Kubernetes orchestration

Each phase maintains backward compatibility while adding capabilities.