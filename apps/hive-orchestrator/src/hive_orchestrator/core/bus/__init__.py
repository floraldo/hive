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

from hive_bus import BaseBus, BaseEvent

from .event_bus import (
    create_task_event,
    create_workflow_event,
    get_async_event_bus,
    get_event_bus,
    publish_event_async,
)
from .events import TaskEventType, WorkflowEventType
from .hive_bus import HiveEventBus, get_hive_event_bus
from .hive_events import AgentEvent, AgentStatus, TaskEvent, TaskStatus, WorkflowEvent

__all__ = [
    "TaskEvent",
    "AgentEvent",
    "WorkflowEvent",
    "TaskStatus",
    "AgentStatus",
    "TaskEventType",
    "WorkflowEventType",
    "HiveEventBus",
    "get_hive_event_bus",
    "get_event_bus",
    "create_task_event",
    "create_workflow_event",
    "get_async_event_bus",
    "publish_event_async",
]
