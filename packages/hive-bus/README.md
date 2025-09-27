# Hive Event Bus

Event-driven communication bus for Hive autonomous agents. Makes the implicit database-driven choreography pattern explicit and debuggable.

## Features

- **Database-backed persistence** for reliable event delivery
- **Topic-based subscriptions** with pattern matching
- **Full event history** for debugging and replay
- **Correlation tracking** for workflow tracing
- **Async-ready architecture** for future performance
- **Structured event types** for type safety

## Quick Start

### Publishing Events

```python
from hive_bus import get_event_bus, create_task_event, TaskEventType

# Get the global event bus
bus = get_event_bus()

# Create and publish a task event
event = create_task_event(
    event_type=TaskEventType.CREATED,
    task_id="task_123",
    source_agent="queen",
    task_status="queued",
    assignee="backend-worker"
)

event_id = bus.publish(event)
print(f"Published event {event_id}")
```

### Subscribing to Events

```python
from hive_bus import get_event_bus

def handle_task_events(event):
    print(f"Received task event: {event.event_type}")
    print(f"Task ID: {event.payload['task_id']}")

# Subscribe to all task events
bus = get_event_bus()
subscription_id = bus.subscribe("task.*", handle_task_events, "my-agent")
```

### Querying Event History

```python
from hive_bus import get_event_bus

bus = get_event_bus()

# Get all events for a specific correlation ID
workflow_events = bus.get_event_history("workflow_123")

# Get recent task events
task_events = bus.get_events(event_type="task.created", limit=10)
```

## Event Types

### Task Events
- `task.created` - New task created
- `task.queued` - Task added to execution queue
- `task.assigned` - Task assigned to worker
- `task.started` - Task execution started
- `task.completed` - Task completed successfully
- `task.failed` - Task execution failed
- `task.review_requested` - Task sent for review
- `task.review_completed` - Review completed
- `task.escalated` - Task escalated to human

### Agent Events
- `agent.started` - Agent came online
- `agent.stopped` - Agent stopped
- `agent.heartbeat` - Agent health check
- `agent.error` - Agent error occurred
- `agent.capacity_changed` - Agent capacity updated

### Workflow Events
- `workflow.plan_generated` - Execution plan created
- `workflow.phase_started` - Workflow phase began
- `workflow.phase_completed` - Workflow phase finished
- `workflow.dependencies_resolved` - Dependencies satisfied
- `workflow.blocked` - Workflow blocked on dependency

## Architecture

### Database Storage
Events are stored in SQLite with the following schema:

```sql
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source_agent TEXT NOT NULL,
    correlation_id TEXT,
    payload TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Pattern Matching
Subscription patterns support:
- Exact match: `task.created`
- Wildcard: `*` (all events)
- Prefix match: `task.*` (all task events)

### Correlation Tracking
Use correlation IDs to track related events across workflows:

```python
# All events in a workflow share the same correlation ID
correlation_id = "workflow_123"

# Publish related events
bus.publish(plan_event, correlation_id=correlation_id)
bus.publish(execution_event, correlation_id=correlation_id)
bus.publish(completion_event, correlation_id=correlation_id)

# Query the complete workflow trace
workflow_trace = bus.get_event_history(correlation_id)
```

## Migration from Direct Database Updates

### Before (Direct Status Updates)
```python
# Old pattern - direct database updates
def assign_task(task_id, worker):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET status = ?, assignee = ? WHERE id = ?",
            ("assigned", worker, task_id)
        )
        conn.commit()
```

### After (Event-Driven)
```python
# New pattern - event-driven communication
def assign_task(task_id, worker):
    # Update database
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET status = ?, assignee = ? WHERE id = ?",
            ("assigned", worker, task_id)
        )
        conn.commit()

    # Publish event for other agents
    bus = get_event_bus()
    event = create_task_event(
        event_type=TaskEventType.ASSIGNED,
        task_id=task_id,
        source_agent="queen",
        assignee=worker
    )
    bus.publish(event)
```

## Integration with Existing Agents

### QueenLite Integration
```python
from hive_bus import get_event_bus, create_task_event, TaskEventType

class QueenLite:
    def __init__(self):
        self.bus = get_event_bus()

    def assign_task(self, task_id, worker):
        # Existing logic...

        # Publish event
        event = create_task_event(
            event_type=TaskEventType.ASSIGNED,
            task_id=task_id,
            source_agent="queen",
            assignee=worker
        )
        self.bus.publish(event)
```

### AI Planner Integration
```python
from hive_bus import get_event_bus, create_workflow_event, WorkflowEventType

class AIPlanner:
    def __init__(self):
        self.bus = get_event_bus()

    def generate_plan(self, task_id):
        # Existing planning logic...

        # Publish plan completion event
        event = create_workflow_event(
            event_type=WorkflowEventType.PLAN_GENERATED,
            workflow_id=f"plan_{task_id}",
            task_id=task_id,
            source_agent="ai-planner"
        )
        self.bus.publish(event)
```

## Configuration

The event bus uses the centralized Hive configuration system:

```python
# In hive_db_utils.config
DEFAULTS = {
    # Event bus settings
    "event_bus_enabled": True,
    "event_history_days": 30,
    "event_batch_size": 100,
    "event_cleanup_interval": 86400,  # 24 hours
}
```

## Future Enhancements

### Phase 4.1: Async Support
```python
# Future async event publishing
async def publish_async(event):
    await bus.publish_async(event)

# Future async subscribers
@async_event_handler("task.*")
async def handle_task_events(event):
    await process_task_event(event)
```

### Phase 4.2: External Bus Integration
```python
# Future Redis/RabbitMQ backend
bus = EventBus(backend="redis://localhost:6379")
```

### Phase 4.3: Event Replay
```python
# Future event replay capability
await bus.replay_events(
    from_timestamp=yesterday,
    correlation_id="workflow_123"
)
```

## Contributing

The event bus is designed to be:
1. **Backwards compatible** with existing direct database patterns
2. **Incrementally adoptable** - can be added to agents one at a time
3. **Performance conscious** - minimal overhead over direct database updates
4. **Debugging friendly** - full event history and correlation tracking

When adding new event types, follow the existing patterns and add them to the appropriate enum in `events.py`.