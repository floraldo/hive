"""Recovery Playbook Registry

PROJECT CHIMERA Phase 3: Self-Healing Feedback Loop
Central registry for all recovery playbooks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hive_logging import get_logger

from .exceptions import PlaybookNotFoundError

if TYPE_CHECKING:
    from .playbooks.base import RecoveryPlaybook

logger = get_logger(__name__)


class RecoveryPlaybookRegistry:
    """Registry for recovery playbooks.

    Manages available playbooks and routes alerts to appropriate handlers.
    """

    def __init__(self):
        """Initialize empty registry."""
        self.playbooks: dict[str, RecoveryPlaybook] = {}
        logger.info("RecoveryPlaybookRegistry initialized")

    def register(self, playbook: RecoveryPlaybook) -> None:
        """Register a recovery playbook.

        Args:
            playbook: RecoveryPlaybook instance to register

        """
        if playbook.playbook_id in self.playbooks:
            logger.warning(f"Playbook {playbook.playbook_id} already registered, replacing")

        self.playbooks[playbook.playbook_id] = playbook
        logger.info(
            f"Registered playbook: {playbook.playbook_id} "
            f"(handles {len(playbook.target_signatures)} signature patterns)",
        )

    def unregister(self, playbook_id: str) -> None:
        """Unregister a playbook.

        Args:
            playbook_id: ID of playbook to remove

        """
        if playbook_id in self.playbooks:
            del self.playbooks[playbook_id]
            logger.info(f"Unregistered playbook: {playbook_id}")
        else:
            logger.warning(f"Attempted to unregister unknown playbook: {playbook_id}")

    def find_playbook(
        self,
        service_name: str,
        metric_type: str,
        condition: str | None = None,
    ) -> RecoveryPlaybook | None:
        """Find appropriate playbook for given alert attributes.

        Args:
            service_name: Service name from alert
            metric_type: Metric type from alert
            condition: Optional condition/error type

        Returns:
            Matching RecoveryPlaybook or None if not found

        """
        for playbook in self.playbooks.values():
            if playbook.matches_alert(service_name, metric_type, condition):
                logger.info(
                    f"Found matching playbook: {playbook.playbook_id} "
                    f"for {service_name}/{metric_type}",
                )
                return playbook

        logger.debug(f"No playbook found for {service_name}/{metric_type}")
        return None

    def get_playbook(self, playbook_id: str) -> RecoveryPlaybook:
        """Get playbook by ID.

        Args:
            playbook_id: Playbook identifier

        Returns:
            RecoveryPlaybook instance

        Raises:
            PlaybookNotFoundError: If playbook doesn't exist

        """
        if playbook_id not in self.playbooks:
            raise PlaybookNotFoundError(f"Playbook not found: {playbook_id}")

        return self.playbooks[playbook_id]

    def list_playbooks(self) -> list[dict[str, str]]:
        """List all registered playbooks.

        Returns:
            List of playbook summaries

        """
        return [
            {
                "playbook_id": pb.playbook_id,
                "description": pb.description,
                "risk_level": pb.risk_level,
                "signature_count": len(pb.target_signatures),
            }
            for pb in self.playbooks.values()
        ]

    def get_stats(self) -> dict[str, int]:
        """Get registry statistics."""
        return {
            "total_playbooks": len(self.playbooks),
            "total_signatures": sum(len(pb.target_signatures) for pb in self.playbooks.values()),
        }


__all__ = ["RecoveryPlaybookRegistry"]
