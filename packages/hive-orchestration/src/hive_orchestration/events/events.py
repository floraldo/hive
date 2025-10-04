"""Orchestration Event Types

Defines task, workflow, and agent event types for orchestration coordination.
"""

from __future__ import annotations

from dataclasses import dataclass

from hive_bus import BaseEvent
from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class TaskEvent(BaseEvent):
    """Task lifecycle event for orchestration coordination.

    Attributes:
        task_id: Task identifier
        event_type: Event type (e.g., "started", "completed", "failed")
        payload: Additional event data

    """

    task_id: str = ""

    def __post_init__(self) -> None:
        """Ensure task_id is in payload"""
        if not self.payload:
            self.payload = {}
        self.payload["task_id"] = self.task_id


@dataclass
class WorkflowEvent(BaseEvent):
    """Workflow lifecycle event for multi-step orchestration.

    Attributes:
        workflow_id: Workflow identifier
        event_type: Event type (e.g., "phase_started", "completed")
        payload: Additional event data

    """

    workflow_id: str = ""

    def __post_init__(self) -> None:
        """Ensure workflow_id is in payload"""
        if not self.payload:
            self.payload = {}
        self.payload["workflow_id"] = self.workflow_id


@dataclass
class AgentEvent(BaseEvent):
    """Agent lifecycle event for worker coordination.

    Attributes:
        agent_id: Agent/worker identifier
        event_type: Event type (e.g., "registered", "heartbeat", "offline")
        payload: Additional event data

    """

    agent_id: str = ""

    def __post_init__(self) -> None:
        """Ensure agent_id is in payload"""
        if not self.payload:
            self.payload = {}
        self.payload["agent_id"] = self.agent_id


__all__ = ["AgentEvent", "TaskEvent", "WorkflowEvent"]
