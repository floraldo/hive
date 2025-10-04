"""Automated Recovery Service

PROJECT CHIMERA Phase 3: Self-Healing Feedback Loop
Main service for automated recovery coordination.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hive_logging import get_logger

from .audit import RecoveryAuditLogger
from .decision_engine import AutomationDecisionEngine
from .exceptions import PlaybookExecutionError
from .playbook_registry import RecoveryPlaybookRegistry

logger = get_logger(__name__)


class AutomatedRecoveryService:
    """Automated recovery service for predictive alerts.

    Subscribes to PredictiveAlertEvent, evaluates safety, executes playbooks.
    """

    def __init__(
        self,
        bus,
        decision_engine: AutomationDecisionEngine | None = None,
        playbook_registry: RecoveryPlaybookRegistry | None = None,
        audit_logger: RecoveryAuditLogger | None = None,
    ):
        """Initialize recovery service.

        Args:
            bus: Event bus for subscribing to alerts
            decision_engine: AutomationDecisionEngine instance
            playbook_registry: RecoveryPlaybookRegistry instance
            audit_logger: RecoveryAuditLogger instance

        """
        self.bus = bus
        self.playbook_registry = playbook_registry or RecoveryPlaybookRegistry()
        self.decision_engine = decision_engine or AutomationDecisionEngine(self.playbook_registry)
        self.audit_logger = audit_logger or RecoveryAuditLogger()

        # Service statistics
        self.stats = {
            "total_alerts_received": 0,
            "automation_approved": 0,
            "automation_denied": 0,
            "executions_successful": 0,
            "executions_failed": 0,
            "started_at": None,
        }

        logger.info("AutomatedRecoveryService initialized")

    async def start_async(self) -> None:
        """Start the recovery service and subscribe to events."""
        self.stats["started_at"] = datetime.utcnow().isoformat()

        # Subscribe to predictive alert events
        await self.bus.subscribe("monitoring.predictive_alert", self._handle_alert_async)

        logger.info("AutomatedRecoveryService started - subscribed to monitoring.predictive_alert")

    async def _handle_alert_async(self, event: Any) -> None:
        """Handle incoming predictive alert event.

        Args:
            event: PredictiveAlertEvent instance

        """
        self.stats["total_alerts_received"] += 1

        logger.info(
            f"Received predictive alert: {event.alert_id} "
            f"({event.service_name}/{event.metric_type}, severity={event.severity})",
        )

        try:
            # Step 1: Evaluate with decision engine
            decision = await self.decision_engine.evaluate_async(event)

            # Log decision
            await self.audit_logger.log_decision_async(event, decision)

            if decision.should_automate:
                # Step 2: Execute recovery playbook
                self.stats["automation_approved"] += 1
                await self._execute_playbook_async(decision.playbook_id, event)
            else:
                # Step 3: Escalate to human intervention
                self.stats["automation_denied"] += 1
                await self._escalate_alert_async(event, decision.escalation_reason)

        except Exception as e:
            logger.error(f"Error handling alert {event.alert_id}: {e}", exc_info=True)

    async def _execute_playbook_async(self, playbook_id: str, alert_event: Any) -> None:
        """Execute recovery playbook.

        Args:
            playbook_id: ID of playbook to execute
            alert_event: PredictiveAlertEvent instance

        """
        try:
            # Get playbook from registry
            playbook = self.playbook_registry.get_playbook(playbook_id)

            logger.warning(
                f"AUTOMATED RECOVERY: Executing playbook {playbook_id} "
                f"for alert {alert_event.alert_id}",
            )

            # Execute playbook
            result = await playbook.execute_async(alert_event)
            result.completed_at = datetime.utcnow()

            # Log execution
            await self.audit_logger.log_execution_async(playbook_id, result)

            if result.success:
                self.stats["executions_successful"] += 1
                logger.info(
                    f"Playbook {playbook_id} executed successfully for alert {alert_event.alert_id}",
                )
            else:
                self.stats["executions_failed"] += 1
                logger.error(
                    f"Playbook {playbook_id} execution failed for alert {alert_event.alert_id}: "
                    f"{result.error_message}",
                )

                # Record failure for future safety checks
                issue_key = f"{alert_event.service_name}:{alert_event.metric_type}"
                self.decision_engine.record_failure(issue_key)

                # Attempt rollback if available
                if not result.rollback_performed:
                    logger.warning(f"Attempting rollback for failed playbook {playbook_id}")
                    rollback_success = await playbook.rollback_async(result)
                    if rollback_success:
                        logger.info(f"Rollback successful for playbook {playbook_id}")
                    else:
                        logger.error(f"Rollback failed for playbook {playbook_id}")

        except PlaybookExecutionError as e:
            self.stats["executions_failed"] += 1
            logger.error(f"Playbook execution error: {e}", exc_info=True)

    async def _escalate_alert_async(self, alert_event: Any, reason: str | None) -> None:
        """Escalate alert to human intervention.

        Args:
            alert_event: PredictiveAlertEvent instance
            reason: Reason for escalation

        """
        logger.warning(
            f"Alert {alert_event.alert_id} escalated to human intervention: {reason}",
        )

        # In production, this would:
        # - Create a high-priority ticket in issue tracker
        # - Send notification to on-call engineer
        # - Update dashboard/UI with escalation status

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            **self.stats,
            "decision_engine_stats": self.decision_engine.get_stats(),
            "playbook_registry_stats": self.playbook_registry.get_stats(),
            "audit_trail_entries": len(self.audit_logger.audit_trail),
        }


__all__ = ["AutomatedRecoveryService"]
