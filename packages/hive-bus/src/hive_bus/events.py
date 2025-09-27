"""
Event definitions for the Hive Event Bus

Defines the formal event types that can be published and consumed
by autonomous agents in the Hive system.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import uuid


class EventType(str, Enum):
    """Base event type categories"""
    TASK = "task"
    AGENT = "agent"
    WORKFLOW = "workflow"
    SYSTEM = "system"


class TaskEventType(str, Enum):
    """Task-related event types"""
    CREATED = "task.created"
    QUEUED = "task.queued"
    ASSIGNED = "task.assigned"
    STARTED = "task.started"
    COMPLETED = "task.completed"
    FAILED = "task.failed"
    REVIEW_REQUESTED = "task.review_requested"
    REVIEW_COMPLETED = "task.review_completed"
    ESCALATED = "task.escalated"


class AgentEventType(str, Enum):
    """Agent-related event types"""
    STARTED = "agent.started"
    STOPPED = "agent.stopped"
    HEARTBEAT = "agent.heartbeat"
    ERROR = "agent.error"
    CAPACITY_CHANGED = "agent.capacity_changed"


class WorkflowEventType(str, Enum):
    """Workflow-related event types"""
    PLAN_GENERATED = "workflow.plan_generated"
    PHASE_STARTED = "workflow.phase_started"
    PHASE_COMPLETED = "workflow.phase_completed"
    DEPENDENCIES_RESOLVED = "workflow.dependencies_resolved"
    BLOCKED = "workflow.blocked"


@dataclass
class Event:
    """Base event class for all Hive events"""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = field(default="")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_agent: str = field(default="unknown")
    correlation_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for storage"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "source_agent": self.source_agent,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary"""
        timestamp = datetime.fromisoformat(data["timestamp"])
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            timestamp=timestamp,
            source_agent=data["source_agent"],
            correlation_id=data.get("correlation_id"),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskEvent(Event):
    """Task-specific event with task context"""

    task_id: str = ""
    task_status: Optional[str] = None
    assignee: Optional[str] = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = TaskEventType.CREATED

        # Add task info to payload
        self.payload.update({
            "task_id": self.task_id,
            "task_status": self.task_status,
            "assignee": self.assignee,
        })


@dataclass
class AgentEvent(Event):
    """Agent-specific event with agent context"""

    agent_name: str = ""
    agent_type: Optional[str] = None
    agent_status: Optional[str] = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = AgentEventType.HEARTBEAT

        # Add agent info to payload
        self.payload.update({
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "agent_status": self.agent_status,
        })


@dataclass
class WorkflowEvent(Event):
    """Workflow-specific event with workflow context"""

    workflow_id: str = ""
    task_id: str = ""
    phase: Optional[str] = None
    dependencies: Optional[list] = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = WorkflowEventType.PLAN_GENERATED

        # Add workflow info to payload
        self.payload.update({
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "phase": self.phase,
            "dependencies": self.dependencies or [],
        })


def create_task_event(
    event_type: Union[TaskEventType, str],
    task_id: str,
    source_agent: str,
    task_status: Optional[str] = None,
    assignee: Optional[str] = None,
    correlation_id: Optional[str] = None,
    **payload_data
) -> TaskEvent:
    """Factory function to create task events"""
    return TaskEvent(
        event_type=str(event_type),
        task_id=task_id,
        source_agent=source_agent,
        task_status=task_status,
        assignee=assignee,
        correlation_id=correlation_id,
        payload=payload_data,
    )


def create_agent_event(
    event_type: Union[AgentEventType, str],
    agent_name: str,
    agent_type: Optional[str] = None,
    agent_status: Optional[str] = None,
    correlation_id: Optional[str] = None,
    **payload_data
) -> AgentEvent:
    """Factory function to create agent events"""
    return AgentEvent(
        event_type=str(event_type),
        agent_name=agent_name,
        source_agent=agent_name,
        agent_type=agent_type,
        agent_status=agent_status,
        correlation_id=correlation_id,
        payload=payload_data,
    )


def create_workflow_event(
    event_type: Union[WorkflowEventType, str],
    workflow_id: str,
    task_id: str,
    source_agent: str,
    phase: Optional[str] = None,
    dependencies: Optional[list] = None,
    correlation_id: Optional[str] = None,
    **payload_data
) -> WorkflowEvent:
    """Factory function to create workflow events"""
    return WorkflowEvent(
        event_type=str(event_type),
        workflow_id=workflow_id,
        task_id=task_id,
        source_agent=source_agent,
        phase=phase,
        dependencies=dependencies,
        correlation_id=correlation_id,
        payload=payload_data,
    )