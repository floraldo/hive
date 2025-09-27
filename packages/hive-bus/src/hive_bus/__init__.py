"""
Hive Event Bus - Event-driven communication for autonomous agents

This package provides a formal event bus for inter-agent communication,
making the implicit database-driven choreography pattern explicit and debuggable.

Architecture:
- Event-driven communication (publish/subscribe)
- Database-backed persistence for reliability
- Async-ready design for future performance
- Full event history for debugging and replay
"""

from .event_bus import EventBus, get_event_bus

# Async functions - conditionally imported
try:
    from .event_bus import (
        get_async_event_bus,
        publish_event_async,
        get_events_async,
        get_event_history_async
    )
    ASYNC_FUNCTIONS_AVAILABLE = True
except ImportError:
    ASYNC_FUNCTIONS_AVAILABLE = False
from .events import (
    Event,
    TaskEvent,
    AgentEvent,
    WorkflowEvent,
    EventType,
    TaskEventType,
    AgentEventType,
    WorkflowEventType,
    create_task_event,
    create_agent_event,
    create_workflow_event
)
from .subscribers import EventSubscriber, AsyncEventSubscriber
from .exceptions import EventBusError, EventPublishError, EventSubscribeError

__version__ = "4.0.0"

__all__ = [
    # Core event bus
    "EventBus",
    "get_event_bus",

    # Event types
    "Event",
    "TaskEvent",
    "AgentEvent",
    "WorkflowEvent",
    "EventType",
    "TaskEventType",
    "AgentEventType",
    "WorkflowEventType",

    # Event factory functions
    "create_task_event",
    "create_agent_event",
    "create_workflow_event",

    # Subscribers
    "EventSubscriber",
    "AsyncEventSubscriber",

    # Exceptions
    "EventBusError",
    "EventPublishError",
    "EventSubscribeError",
]

# Add async functions to __all__ if available
if ASYNC_FUNCTIONS_AVAILABLE:
    __all__.extend([
        "get_async_event_bus",
        "publish_event_async",
        "get_events_async",
        "get_event_history_async",
    ])