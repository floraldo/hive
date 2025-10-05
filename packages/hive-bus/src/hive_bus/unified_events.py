"""Unified event types for cross-agent coordination.

These event types provide a common language for all agents in the Hive platform.
During migration, both legacy and unified events can coexist.

Architecture:
    - UnifiedEventType: Standard event types across all agents
    - UnifiedEvent: Standard event payload structure
    - Correlation IDs: Track work across multiple agents and services

Usage:
    from hive_bus import UnifiedEventType, UnifiedEvent

    # Create unified event
    event = UnifiedEvent(
        event_type=UnifiedEventType.TASK_CREATED,
        correlation_id="workflow-123",
        payload={
            "task_id": "task-456",
            "task_type": "review",
            "input_data": {...}
        },
        source_agent="orchestrator"
    )

    # Emit event
    bus.emit(event)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class UnifiedEventType(str, Enum):
    """Standard event types for cross-agent coordination.

    These event types map to common patterns across all agents:
    - Task lifecycle events (created, started, completed, failed)
    - Review events (requested, completed, approved, rejected)
    - Workflow events (phase transitions, checkpoints)
    - Deployment events (triggered, in_progress, deployed, validated)
    - Planning events (requested, generated, approved)
    """

    # Task lifecycle events
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"

    # Review events (ai-reviewer)
    REVIEW_REQUESTED = "review.requested"
    REVIEW_IN_PROGRESS = "review.in_progress"
    REVIEW_COMPLETED = "review.completed"
    REVIEW_APPROVED = "review.approved"
    REVIEW_REJECTED = "review.rejected"
    AUTO_FIX_APPLIED = "review.auto_fix_applied"

    # Workflow events (orchestrator)
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_PHASE_COMPLETED = "workflow.phase_completed"
    WORKFLOW_CHECKPOINT = "workflow.checkpoint"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"

    # Deployment events (ai-deployer)
    DEPLOYMENT_REQUESTED = "deployment.requested"
    DEPLOYMENT_IN_PROGRESS = "deployment.in_progress"
    DEPLOYMENT_COMPLETED = "deployment.completed"
    DEPLOYMENT_VALIDATED = "deployment.validated"
    DEPLOYMENT_FAILED = "deployment.failed"
    DEPLOYMENT_ROLLED_BACK = "deployment.rolled_back"

    # Planning events (ai-planner)
    PLAN_REQUESTED = "plan.requested"
    PLAN_GENERATED = "plan.generated"
    PLAN_APPROVED = "plan.approved"
    PLAN_EXECUTION_STARTED = "plan.execution_started"
    PLAN_EXECUTION_COMPLETED = "plan.execution_completed"

    # System events
    AGENT_REGISTERED = "agent.registered"
    AGENT_HEARTBEAT = "agent.heartbeat"
    AGENT_ERROR = "agent.error"
    SYSTEM_ERROR = "system.error"


@dataclass
class UnifiedEvent:
    """Standard event structure for cross-agent communication.

    All agents should emit events in this format to enable:
    - Correlation tracking across agents
    - Event replay and debugging
    - Workflow orchestration
    - Metrics and monitoring

    Attributes:
        event_type: Type of event (from UnifiedEventType enum)
        correlation_id: ID to track related events across agents
        payload: Event-specific data
        source_agent: Which agent emitted this event
        timestamp: When the event occurred (auto-set)
        metadata: Additional context (tags, environment, etc.)
    """

    event_type: UnifiedEventType
    correlation_id: str
    payload: dict[str, Any]
    source_agent: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "source_agent": self.source_agent,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedEvent":
        """Create event from dictionary."""
        return cls(
            event_type=UnifiedEventType(data["event_type"]),
            correlation_id=data["correlation_id"],
            payload=data["payload"],
            source_agent=data["source_agent"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


# Helper functions for common event patterns

def create_task_event(
    event_type: UnifiedEventType,
    task_id: str,
    correlation_id: str,
    source_agent: str,
    additional_data: dict[str, Any] | None = None,
) -> UnifiedEvent:
    """Create a task lifecycle event.

    Args:
        event_type: Type of task event (should be TASK_*)
        task_id: ID of the task
        correlation_id: Correlation ID for tracking
        source_agent: Agent emitting the event
        additional_data: Additional event-specific data

    Returns:
        UnifiedEvent with task data
    """
    payload = {"task_id": task_id}
    if additional_data:
        payload.update(additional_data)

    return UnifiedEvent(
        event_type=event_type,
        correlation_id=correlation_id,
        payload=payload,
        source_agent=source_agent,
    )


def create_workflow_event(
    event_type: UnifiedEventType,
    workflow_id: str,
    correlation_id: str,
    phase: str,
    source_agent: str = "orchestrator",
    additional_data: dict[str, Any] | None = None,
) -> UnifiedEvent:
    """Create a workflow event.

    Args:
        event_type: Type of workflow event (should be WORKFLOW_*)
        workflow_id: ID of the workflow
        correlation_id: Correlation ID for tracking
        phase: Current workflow phase
        source_agent: Agent emitting the event (default: orchestrator)
        additional_data: Additional event-specific data

    Returns:
        UnifiedEvent with workflow data
    """
    payload = {
        "workflow_id": workflow_id,
        "phase": phase,
    }
    if additional_data:
        payload.update(additional_data)

    return UnifiedEvent(
        event_type=event_type,
        correlation_id=correlation_id,
        payload=payload,
        source_agent=source_agent,
    )


def create_deployment_event(
    event_type: UnifiedEventType,
    deployment_id: str,
    correlation_id: str,
    service_name: str,
    environment: str,
    source_agent: str = "ai-deployer",
    additional_data: dict[str, Any] | None = None,
) -> UnifiedEvent:
    """Create a deployment event.

    Args:
        event_type: Type of deployment event (should be DEPLOYMENT_*)
        deployment_id: ID of the deployment
        correlation_id: Correlation ID for tracking
        service_name: Name of service being deployed
        environment: Target environment (dev, staging, prod)
        source_agent: Agent emitting the event (default: ai-deployer)
        additional_data: Additional event-specific data

    Returns:
        UnifiedEvent with deployment data
    """
    payload = {
        "deployment_id": deployment_id,
        "service_name": service_name,
        "environment": environment,
    }
    if additional_data:
        payload.update(additional_data)

    return UnifiedEvent(
        event_type=event_type,
        correlation_id=correlation_id,
        payload=payload,
        source_agent=source_agent,
    )
