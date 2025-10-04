"""Base Recovery Playbook

PROJECT CHIMERA Phase 3: Self-Healing Feedback Loop
Abstract base class for all recovery playbooks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class PlaybookResult:
    """Result of playbook execution."""

    success: bool
    action: str
    alert_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    rollback_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "success": self.success,
            "action": self.action,
            "alert_id": self.alert_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "details": self.details,
            "error_message": self.error_message,
            "rollback_performed": self.rollback_performed,
        }


@dataclass
class PlaybookSignature:
    """Signature pattern for playbook matching."""

    service_pattern: str  # e.g., "hive-db", "*" for all
    metric_type: str  # e.g., "connection_pool", "error_rate"
    condition: str | None = None  # e.g., "ExhaustionPredicted", "HighUtilization"

    def matches(self, service_name: str, metric_type: str, condition: str | None = None) -> bool:
        """Check if signature matches given alert attributes."""
        # Match service (with wildcard support)
        service_match = self.service_pattern == "*" or self.service_pattern == service_name

        # Match metric type
        metric_match = self.metric_type == metric_type

        # Match condition if specified
        condition_match = self.condition is None or self.condition == condition

        return service_match and metric_match and condition_match


class RecoveryPlaybook(ABC):
    """Abstract base class for recovery playbooks.

    All recovery playbooks must inherit from this class and implement:
    - playbook_id: Unique identifier
    - target_signatures: List of alert patterns this playbook handles
    - execute_async: Recovery action implementation
    - rollback_async: Rollback logic (optional but recommended)
    """

    playbook_id: str = "base_playbook"
    target_signatures: list[PlaybookSignature] = []
    description: str = ""
    risk_level: str = "medium"  # low, medium, high

    def __init__(self):
        """Initialize playbook."""
        if not self.playbook_id or self.playbook_id == "base_playbook":
            raise ValueError(f"{self.__class__.__name__} must define playbook_id")

        if not self.target_signatures:
            raise ValueError(f"{self.__class__.__name__} must define target_signatures")

        logger.info(f"Initialized recovery playbook: {self.playbook_id}")

    def matches_alert(self, service_name: str, metric_type: str, condition: str | None = None) -> bool:
        """Check if this playbook can handle the given alert."""
        return any(sig.matches(service_name, metric_type, condition) for sig in self.target_signatures)

    @abstractmethod
    async def execute_async(self, alert_event: Any) -> PlaybookResult:
        """Execute recovery action.

        Args:
            alert_event: PredictiveAlertEvent instance

        Returns:
            PlaybookResult with execution outcome

        """

    async def rollback_async(self, execution_result: PlaybookResult) -> bool:
        """Rollback recovery action if needed.

        Override this method if playbook supports rollback.

        Args:
            execution_result: Result from execute_async

        Returns:
            True if rollback succeeded

        """
        logger.warning(f"Playbook {self.playbook_id} does not implement rollback")
        return False

    async def pre_execution_check_async(self, alert_event: Any) -> bool:
        """Pre-execution safety check.

        Override to add playbook-specific safety checks.

        Args:
            alert_event: PredictiveAlertEvent instance

        Returns:
            True if safe to proceed

        """
        return True

    def get_estimated_impact(self) -> dict[str, str]:
        """Get estimated impact of this playbook."""
        return {
            "risk_level": self.risk_level,
            "description": self.description,
            "reversible": hasattr(self, "rollback_async"),
        }


__all__ = ["PlaybookResult", "PlaybookSignature", "RecoveryPlaybook"]
