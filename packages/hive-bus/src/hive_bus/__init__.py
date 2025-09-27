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
from .events import (
    Event,
    TaskEvent,
    AgentEvent,
    WorkflowEvent,
    EventType,
    TaskEventType,
    AgentEventType,
    WorkflowEventType
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

    # Subscribers
    "EventSubscriber",
    "AsyncEventSubscriber",

    # Exceptions
    "EventBusError",
    "EventPublishError",
    "EventSubscribeError",
]