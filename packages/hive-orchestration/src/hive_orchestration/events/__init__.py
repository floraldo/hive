"""
Orchestration Events

This module contains event definitions and event bus integration
for task, workflow, and agent lifecycle events.
"""

from hive_logging import get_logger

from .bus import get_async_event_bus, reset_event_bus
from .events import AgentEvent, TaskEvent, WorkflowEvent
from .qa_events import EscalationEvent, QATaskEvent, WorkerHeartbeat, WorkerRegistration

logger = get_logger(__name__)

__all__ = [
    "get_async_event_bus",
    "reset_event_bus",
    "TaskEvent",
    "WorkflowEvent",
    "AgentEvent",
    "QATaskEvent",
    "WorkerHeartbeat",
    "WorkerRegistration",
    "EscalationEvent",
]
