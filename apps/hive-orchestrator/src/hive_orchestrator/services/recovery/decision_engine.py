"""Automation Decision Engine

PROJECT CHIMERA Phase 3: Self-Healing Feedback Loop
Determines if/when to automate recovery based on safety rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from hive_logging import get_logger

from .exceptions import (
    AmbiguousRootCauseError,
    InsufficientConfidenceError,
    ManualModeError,
    RecentFailureError,
    SafetyCheckFailedError,
)

logger = get_logger(__name__)


@dataclass
class AutomationDecision:
    """Decision on whether to automate recovery."""

    should_automate: bool
    confidence_score: float
    playbook_id: str | None
    escalation_reason: str | None
    safety_checks: dict[str, bool]
    historical_context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "should_automate": self.should_automate,
            "confidence_score": self.confidence_score,
            "playbook_id": self.playbook_id,
            "escalation_reason": self.escalation_reason,
            "safety_checks": self.safety_checks,
            "has_historical_context": self.historical_context is not None,
        }


class AutomationDecisionEngine:
    """Decide whether to automate recovery for a predictive alert.

    Safety Rules (ALL must pass):
    1. Confidence score > 95%
    2. Single unambiguous root cause from historical context
    3. Pre-defined safe playbook exists
    4. No failed automated recovery for same issue in last 24 hours
    5. Service is not in manual-only mode
    """

    def __init__(
        self,
        playbook_registry,
        failure_history: dict[str, list[datetime]] | None = None,
        manual_mode_services: set[str] | None = None,
        confidence_threshold: float = 0.95,
    ):
        """Initialize decision engine.

        Args:
            playbook_registry: RecoveryPlaybookRegistry instance
            failure_history: Dict mapping issue_key -> list of failure timestamps
            manual_mode_services: Set of services in manual-only mode
            confidence_threshold: Minimum confidence to automate (default 95%)

        """
        self.playbook_registry = playbook_registry
        self.failure_history = failure_history or {}
        self.manual_mode_services = manual_mode_services or set()
        self.confidence_threshold = confidence_threshold

        logger.info(
            f"AutomationDecisionEngine initialized "
            f"(confidence_threshold={confidence_threshold}, "
            f"manual_mode_services={len(self.manual_mode_services)})",
        )

    async def evaluate_async(self, alert_event: Any) -> AutomationDecision:
        """Evaluate whether to automate recovery for alert.

        Args:
            alert_event: PredictiveAlertEvent instance

        Returns:
            AutomationDecision with recommendation

        """
        logger.info(f"Evaluating automation decision for alert {alert_event.alert_id}")

        # Extract alert attributes
        service_name = alert_event.service_name
        metric_type = alert_event.metric_type
        confidence = alert_event.payload.get("confidence", 0.0)

        # Initialize safety check results
        safety_checks = {
            "confidence_sufficient": False,
            "root_cause_clear": False,
            "playbook_exists": False,
            "no_recent_failure": False,
            "not_manual_mode": False,
        }

        escalation_reason = None
        playbook_id = None

        try:
            # SAFETY RULE 1: Confidence score > threshold
            safety_checks["confidence_sufficient"] = confidence > self.confidence_threshold
            if not safety_checks["confidence_sufficient"]:
                raise InsufficientConfidenceError(
                    f"Confidence {confidence:.2%} below threshold {self.confidence_threshold:.2%}",
                )

            # SAFETY RULE 2: Single unambiguous root cause
            historical_context = alert_event.payload.get("historical_context")
            if historical_context:
                # Check if context points to single clear cause
                similar_incidents = historical_context.get("similar_incidents", [])
                if len(similar_incidents) > 0:
                    # Heuristic: If top incident has high similarity and common root cause exists
                    common_cause = historical_context.get("most_common_root_cause")
                    safety_checks["root_cause_clear"] = common_cause is not None
                else:
                    safety_checks["root_cause_clear"] = False
            else:
                safety_checks["root_cause_clear"] = False

            if not safety_checks["root_cause_clear"]:
                raise AmbiguousRootCauseError("No clear root cause from historical context")

            # SAFETY RULE 3: Pre-defined safe playbook exists
            playbook = self.playbook_registry.find_playbook(service_name, metric_type)
            if playbook:
                safety_checks["playbook_exists"] = True
                playbook_id = playbook.playbook_id
            else:
                raise SafetyCheckFailedError(f"No playbook found for {service_name}/{metric_type}")

            # SAFETY RULE 4: No recent failures for same issue
            issue_key = f"{service_name}:{metric_type}"
            safety_checks["no_recent_failure"] = not self._has_recent_failure(issue_key)
            if not safety_checks["no_recent_failure"]:
                raise RecentFailureError(f"Recent automated recovery failure for {issue_key}")

            # SAFETY RULE 5: Service not in manual-only mode
            safety_checks["not_manual_mode"] = service_name not in self.manual_mode_services
            if not safety_checks["not_manual_mode"]:
                raise ManualModeError(f"Service {service_name} is in manual-only mode")

            # ALL SAFETY CHECKS PASSED - Authorize automation
            logger.info(
                f"Automation APPROVED for alert {alert_event.alert_id} "
                f"(playbook={playbook_id}, confidence={confidence:.2%})",
            )

            return AutomationDecision(
                should_automate=True,
                confidence_score=confidence,
                playbook_id=playbook_id,
                escalation_reason=None,
                safety_checks=safety_checks,
                historical_context=historical_context,
            )

        except SafetyCheckFailedError as e:
            # Safety check failed - escalate to human
            escalation_reason = str(e)
            logger.warning(
                f"Automation DENIED for alert {alert_event.alert_id}: {escalation_reason}",
            )

            return AutomationDecision(
                should_automate=False,
                confidence_score=confidence,
                playbook_id=playbook_id,
                escalation_reason=escalation_reason,
                safety_checks=safety_checks,
                historical_context=historical_context.get("historical_context") if historical_context else None,
            )

    def _has_recent_failure(self, issue_key: str, window_hours: int = 24) -> bool:
        """Check if automated recovery recently failed for this issue.

        Args:
            issue_key: Unique key for issue (service:metric)
            window_hours: Time window to check (default 24 hours)

        Returns:
            True if recent failure exists

        """
        if issue_key not in self.failure_history:
            return False

        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        recent_failures = [ts for ts in self.failure_history[issue_key] if ts > cutoff]

        return len(recent_failures) > 0

    def record_failure(self, issue_key: str) -> None:
        """Record a recovery failure for future safety checks."""
        if issue_key not in self.failure_history:
            self.failure_history[issue_key] = []

        self.failure_history[issue_key].append(datetime.utcnow())
        logger.warning(f"Recorded recovery failure for {issue_key}")

    def add_manual_mode_service(self, service_name: str) -> None:
        """Add service to manual-only mode."""
        self.manual_mode_services.add(service_name)
        logger.info(f"Added {service_name} to manual-only mode")

    def remove_manual_mode_service(self, service_name: str) -> None:
        """Remove service from manual-only mode."""
        self.manual_mode_services.discard(service_name)
        logger.info(f"Removed {service_name} from manual-only mode")

    def get_stats(self) -> dict[str, Any]:
        """Get decision engine statistics."""
        return {
            "confidence_threshold": self.confidence_threshold,
            "manual_mode_services": list(self.manual_mode_services),
            "failure_history_entries": len(self.failure_history),
            "total_failures": sum(len(failures) for failures in self.failure_history.values()),
        }


__all__ = ["AutomationDecision", "AutomationDecisionEngine"]
