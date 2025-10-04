"""Recovery Audit Logger - PROJECT CHIMERA Phase 3"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class RecoveryAuditLogger:
    """Log all automated recovery actions for compliance and debugging."""

    def __init__(self):
        """Initialize audit logger."""
        self.audit_trail: list[dict[str, Any]] = []

    async def log_decision_async(self, alert_event: Any, decision: Any) -> None:
        """Log automation decision."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "decision",
            "alert_id": alert_event.alert_id,
            "service": alert_event.service_name,
            "metric_type": alert_event.metric_type,
            "should_automate": decision.should_automate,
            "confidence": decision.confidence_score,
            "playbook": decision.playbook_id,
            "escalation_reason": decision.escalation_reason,
            "safety_checks": decision.safety_checks,
        }

        self.audit_trail.append(entry)

        logger.info(
            "Recovery decision logged",
            extra=entry,
        )

    async def log_execution_async(self, playbook_id: str, result: Any) -> None:
        """Log playbook execution."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "execution",
            "playbook_id": playbook_id,
            "success": result.success,
            "action": result.action,
            "alert_id": result.alert_id,
            "error_message": result.error_message,
            "rollback_performed": result.rollback_performed,
        }

        self.audit_trail.append(entry)

        logger.info(
            "Playbook execution logged",
            extra=entry,
        )

    def get_audit_trail(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get recent audit trail entries."""
        if limit:
            return self.audit_trail[-limit:]
        return self.audit_trail


__all__ = ["RecoveryAuditLogger"]
