"""Escalation Manager - HITL Workflow Coordination.

Manages escalations requiring human-in-the-loop review, tracks escalation
lifecycle, and provides utilities for escalation management.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from hive_logging import get_logger
from pydantic import BaseModel, Field

logger = get_logger(__name__)


class EscalationStatus(str, Enum):
    """Escalation lifecycle states."""

    PENDING = "pending"  # Awaiting HITL review
    IN_REVIEW = "in_review"  # Human actively reviewing
    RESOLVED = "resolved"  # Human resolved the issue
    CANNOT_FIX = "cannot_fix"  # Issue cannot be fixed (technical limitation)
    WONT_FIX = "wont_fix"  # Intentional decision not to fix
    CANCELLED = "cancelled"  # Escalation no longer needed


class Escalation(BaseModel):
    """Escalation record for HITL workflow.

    Tracks escalation metadata, status, and resolution.
    """

    escalation_id: str = Field(..., description="Unique escalation ID")
    task_id: str = Field(..., description="Original task ID")
    worker_id: str = Field(..., description="Worker that escalated")
    reason: str = Field(..., description="Why escalated")
    status: EscalationStatus = Field(default=EscalationStatus.PENDING, description="Current status")
    violations: list[dict[str, Any]] = Field(default_factory=list, description="Violations requiring review")
    rag_context: list[dict[str, Any]] = Field(default_factory=list, description="RAG patterns for guidance")
    created_at: datetime = Field(default_factory=datetime.now, description="Escalation creation time")
    assigned_to: str | None = Field(default=None, description="Human reviewer assigned")
    reviewed_at: datetime | None = Field(default=None, description="Review start time")
    resolved_at: datetime | None = Field(default=None, description="Resolution time")
    resolution_notes: str | None = Field(default=None, description="Human resolution notes")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class EscalationManager:
    """Manage escalation lifecycle and HITL workflow.

    Responsibilities:
    - Create escalations from worker failures
    - Track escalation status
    - Assign escalations to human reviewers
    - Record resolutions
    - Publish escalation events to event bus

    Example:
        manager = EscalationManager(db)
        escalation = await manager.create_escalation(
            task_id="task-123",
            worker_id="qa-cc-456",
            reason="Critical security violation",
            violations=[...]
        )
    """

    def __init__(self, db: Any | None = None):
        """Initialize escalation manager.

        Args:
            db: Database connection for persistence
        """
        self.db = db
        self.logger = logger
        self.event_bus = None  # Optional - will be initialized if needed

        # In-memory escalation store (for MVP)
        # In production, this would be in database
        self.escalations: dict[str, Escalation] = {}

    async def create_escalation(
        self,
        task_id: str,
        worker_id: str,
        reason: str,
        violations: list[dict[str, Any]],
        rag_context: list[dict[str, Any]] | None = None,
    ) -> Escalation:
        """Create new escalation for HITL review.

        Args:
            task_id: Task ID that failed
            worker_id: Worker that escalated
            reason: Escalation reason
            violations: Violations requiring review
            rag_context: Optional RAG patterns for guidance

        Returns:
            Created escalation record
        """
        import uuid

        escalation_id = f"esc-{uuid.uuid4().hex[:8]}"

        escalation = Escalation(
            escalation_id=escalation_id,
            task_id=task_id,
            worker_id=worker_id,
            reason=reason,
            violations=violations,
            rag_context=rag_context or [],
            status=EscalationStatus.PENDING,
        )

        # Store escalation
        self.escalations[escalation_id] = escalation

        # Publish escalation event
        await self._publish_escalation_event(escalation)

        self.logger.info(
            f"Escalation created: {escalation_id} "
            f"(task: {task_id}, reason: {reason})"
        )

        return escalation

    async def assign_escalation(
        self,
        escalation_id: str,
        reviewer: str,
    ) -> bool:
        """Assign escalation to human reviewer.

        Args:
            escalation_id: Escalation ID
            reviewer: Reviewer identifier (email, user ID, etc.)

        Returns:
            True if assigned successfully
        """
        escalation = self.escalations.get(escalation_id)

        if not escalation:
            self.logger.error(f"Escalation not found: {escalation_id}")
            return False

        escalation.assigned_to = reviewer
        escalation.status = EscalationStatus.IN_REVIEW
        escalation.reviewed_at = datetime.now()

        self.logger.info(f"Escalation {escalation_id} assigned to {reviewer}")

        return True

    async def resolve_escalation(
        self,
        escalation_id: str,
        resolution_status: EscalationStatus,
        notes: str,
    ) -> bool:
        """Record escalation resolution.

        Args:
            escalation_id: Escalation ID
            resolution_status: Final status (RESOLVED, CANNOT_FIX, WONT_FIX)
            notes: Human resolution notes

        Returns:
            True if resolved successfully
        """
        escalation = self.escalations.get(escalation_id)

        if not escalation:
            self.logger.error(f"Escalation not found: {escalation_id}")
            return False

        escalation.status = resolution_status
        escalation.resolution_notes = notes
        escalation.resolved_at = datetime.now()

        self.logger.info(
            f"Escalation {escalation_id} resolved: {resolution_status.value} "
            f"({notes[:50]}...)" if len(notes) > 50 else f"({notes})"
        )

        # TODO: Update RAG index with human fix patterns for learning

        return True

    def get_pending_escalations(self) -> list[Escalation]:
        """Get all pending escalations awaiting review.

        Returns:
            List of pending escalations
        """
        return [
            esc
            for esc in self.escalations.values()
            if esc.status == EscalationStatus.PENDING
        ]

    def get_escalation(self, escalation_id: str) -> Escalation | None:
        """Get escalation by ID.

        Args:
            escalation_id: Escalation ID

        Returns:
            Escalation or None if not found
        """
        return self.escalations.get(escalation_id)

    def get_escalation_stats(self) -> dict[str, Any]:
        """Get escalation statistics.

        Returns:
            Stats dictionary
        """
        total = len(self.escalations)
        pending = sum(1 for e in self.escalations.values() if e.status == EscalationStatus.PENDING)
        in_review = sum(1 for e in self.escalations.values() if e.status == EscalationStatus.IN_REVIEW)
        resolved = sum(1 for e in self.escalations.values() if e.status == EscalationStatus.RESOLVED)
        cannot_fix = sum(1 for e in self.escalations.values() if e.status == EscalationStatus.CANNOT_FIX)
        wont_fix = sum(1 for e in self.escalations.values() if e.status == EscalationStatus.WONT_FIX)

        # Calculate resolution time for resolved escalations
        resolved_escalations = [e for e in self.escalations.values() if e.status == EscalationStatus.RESOLVED]
        avg_resolution_time = 0.0

        if resolved_escalations:
            resolution_times = [
                (e.resolved_at - e.created_at).total_seconds()
                for e in resolved_escalations
                if e.resolved_at
            ]
            if resolution_times:
                avg_resolution_time = sum(resolution_times) / len(resolution_times)

        return {
            "total_escalations": total,
            "pending": pending,
            "in_review": in_review,
            "resolved": resolved,
            "cannot_fix": cannot_fix,
            "wont_fix": wont_fix,
            "avg_resolution_time_seconds": avg_resolution_time,
        }

    async def _publish_escalation_event(self, escalation: Escalation) -> None:
        """Publish escalation event to event bus.

        Args:
            escalation: Escalation record
        """
        try:
            event = EscalationEvent(
                task_id=escalation.task_id,
                worker_id=escalation.worker_id,
                payload={
                    "escalation_id": escalation.escalation_id,
                    "reason": escalation.reason,
                    "violations_count": len(escalation.violations),
                    "status": escalation.status.value,
                    "created_at": escalation.created_at.isoformat(),
                },
            )

            await self.event_bus.publish("qa.escalation.created", event)

            self.logger.info(f"Escalation event published: {escalation.escalation_id}")

        except Exception as e:
            self.logger.error(f"Failed to publish escalation event: {e}", exc_info=True)


__all__ = ["Escalation", "EscalationManager", "EscalationStatus"]
