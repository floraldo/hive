from hive_logging import get_logger

logger = get_logger(__name__)

"""
Hive Event Bus - Orchestration Communication System.

Extends generic messaging toolkit with Hive-specific agent coordination:
- Task orchestration events
- Agent lifecycle management
- Workflow correlation tracking
- Database-backed persistence
"""

# Import from infrastructure package (Inherit-Extend pattern)
from hive_bus import BaseBus, BaseEvent, BaseSubscriber

from .event_bus import create_task_event, create_workflow_event, get_async_event_bus, get_event_bus, publish_event_async
from .events import TaskEventType, WorkflowEventType
from .hive_bus import HiveEventBus, get_hive_event_bus
from .hive_events import AgentEvent, AgentStatus, TaskEvent, TaskStatus, WorkflowEvent

__all__ = [
    # Infrastructure base classes (re-exported)
    "BaseBus",
    "BaseEvent",
    "BaseSubscriber",
    # Hive-specific events
    "TaskEvent",
    "AgentEvent",
    "WorkflowEvent",
    "TaskStatus",
    "AgentStatus",
    "TaskEventType",
    "WorkflowEventType",
    # Event bus instances
    "HiveEventBus",
    "get_hive_event_bus",
    "get_event_bus",
    # Event creation helpers
    "create_task_event",
    "create_workflow_event",
    # Async operations
    "get_async_event_bus",
    "publish_event_async",
]
