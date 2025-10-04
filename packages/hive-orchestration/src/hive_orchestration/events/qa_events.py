"""QA Worker Event Types

Event definitions for autonomous QA worker fleet coordination.
"""

from __future__ import annotations

from dataclasses import dataclass

from hive_bus import BaseEvent


@dataclass
class QATaskEvent(BaseEvent):
    """QA task lifecycle event for worker coordination.

    Attributes:
        task_id: Task identifier
        qa_type: Type of QA check ('ruff' | 'golden_rules' | 'test' | 'security')
        event_type: Event type ('auto_fixed' | 'escalation_needed' | 'completed' | 'failed')
        payload: Additional event data including:
            - worker_id: Worker that processed task
            - violations_fixed: Number of violations auto-fixed
            - violations_remaining: Number of violations that need escalation
            - execution_time_ms: Time taken to process task
            - files_processed: Number of files checked/fixed

    """

    task_id: str = ""
    qa_type: str = "ruff"

    def __post_init__(self) -> None:
        """Ensure task_id and qa_type are in payload."""
        if not self.payload:
            self.payload = {}
        self.payload["task_id"] = self.task_id
        self.payload["qa_type"] = self.qa_type


@dataclass
class WorkerHeartbeat(BaseEvent):
    """Worker health monitoring heartbeat.

    Attributes:
        worker_id: Worker identifier
        event_type: Always 'heartbeat'
        payload: Worker health data including:
            - status: 'idle' | 'working' | 'error' | 'offline'
            - tasks_completed: Total tasks processed
            - violations_fixed: Total violations auto-fixed
            - escalations: Total escalations to HITL
            - uptime_seconds: Worker uptime in seconds

    """

    worker_id: str = ""

    def __post_init__(self) -> None:
        """Ensure worker_id is in payload and event_type is heartbeat."""
        if not self.payload:
            self.payload = {}
        self.payload["worker_id"] = self.worker_id
        # Override event_type to always be heartbeat
        self.event_type = "heartbeat"


@dataclass
class WorkerRegistration(BaseEvent):
    """Worker registration event when worker comes online.

    Attributes:
        worker_id: Worker identifier
        worker_type: Type of worker ('qa' | 'golden_rules' | 'test' | 'security')
        event_type: Always 'registered'
        payload: Worker metadata including:
            - capabilities: List of auto-fixable violation types
            - version: Worker software version
            - workspace: Worker workspace path

    """

    worker_id: str = ""
    worker_type: str = "qa"

    def __post_init__(self) -> None:
        """Ensure worker_id and worker_type are in payload."""
        if not self.payload:
            self.payload = {}
        self.payload["worker_id"] = self.worker_id
        self.payload["worker_type"] = self.worker_type
        # Override event_type to always be registered
        self.event_type = "registered"


@dataclass
class EscalationEvent(BaseEvent):
    """Escalation event when worker cannot auto-fix an issue.

    Attributes:
        task_id: Task that needs escalation
        worker_id: Worker that escalated
        event_type: Always 'escalation_needed'
        payload: Escalation context including:
            - reason: Why escalation is needed
            - violations_remaining: Number of violations that couldn't be fixed
            - attempts: Number of fix attempts made
            - files: Affected file paths
            - details: Additional context for HITL review

    """

    task_id: str = ""
    worker_id: str = ""

    def __post_init__(self) -> None:
        """Ensure task_id and worker_id are in payload."""
        if not self.payload:
            self.payload = {}
        self.payload["task_id"] = self.task_id
        self.payload["worker_id"] = self.worker_id
        # Override event_type to always be escalation_needed
        self.event_type = "escalation_needed"


__all__ = [
    "EscalationEvent",
    "QATaskEvent",
    "WorkerHeartbeat",
    "WorkerRegistration",
]
