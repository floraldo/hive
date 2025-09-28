"""
Hive-specific event types.

Extends the generic messaging toolkit with Hive orchestration events.
These contain the business logic for agent coordination.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from hive_bus import BaseEvent


class TaskStatus(Enum):
    """Hive task status enumeration"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(Enum):
    """Hive agent status enumeration"""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class TaskEvent(BaseEvent):
    """
    Hive-specific task event.

    Extends BaseEvent with Hive task orchestration properties.
    """
    task_id: str = ""
    worker_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 1

    def __post_init__(self):
        """Set event type for task events"""
        if not self.event_type:
            self.event_type = f"task.{self.status.value}"


@dataclass
class AgentEvent(BaseEvent):
    """
    Hive-specific agent event.

    Extends BaseEvent with Hive agent orchestration properties.
    """
    agent_id: str = ""
    agent_type: str = ""  # queen, worker, reviewer, etc.
    status: AgentStatus = AgentStatus.IDLE
    capabilities: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set event type for agent events"""
        if not self.event_type:
            self.event_type = f"agent.{self.status.value}"


@dataclass
class WorkflowEvent(BaseEvent):
    """
    Hive-specific workflow event.

    Extends BaseEvent with Hive workflow orchestration properties.
    """
    workflow_id: str = ""
    phase: str = ""  # planning, execution, review, completion
    progress: float = 0.0  # 0.0 to 1.0
    dependencies: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Set event type for workflow events"""
        if not self.event_type:
            self.event_type = f"workflow.{self.phase}"