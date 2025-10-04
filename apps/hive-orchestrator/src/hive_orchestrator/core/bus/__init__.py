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

from .event_bus import get_event_bus
from .events import TaskEventType, WorkflowEventType, create_task_event, create_workflow_event
from .hive_bus import HiveEventBus, get_hive_event_bus
from .hive_events import AgentEvent, AgentStatus, TaskEvent, TaskStatus, WorkflowEvent

# Backward compatibility alias
get_async_event_bus = get_event_bus

__all__ = [
    "AgentEvent",
    "AgentStatus",
    # Infrastructure base classes (re-exported)
    "BaseBus",
    "BaseEvent",
    "BaseSubscriber",
    # Event bus instances
    "HiveEventBus",
    # Hive-specific events
    "TaskEvent",
    "TaskEventType",
    "TaskStatus",
    "WorkflowEvent",
    "WorkflowEventType",
    # Event creation helpers
    "create_task_event",
    "create_workflow_event",
    "get_async_event_bus",  # Backward compatibility alias
    "get_event_bus",
    "get_hive_event_bus",
]
