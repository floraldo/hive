"""Restart Service Playbook - PROJECT CHIMERA Phase 3"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hive_deployment import get_deployment_client
from hive_logging import get_logger

from .base import PlaybookResult, PlaybookSignature, RecoveryPlaybook

logger = get_logger(__name__)


class RestartServicePlaybook(RecoveryPlaybook):
    """Gracefully restart service experiencing persistent issues.

    Risk Level: MEDIUM
    - Rolling restart minimizes downtime
    - Health checks ensure service recovers properly
    - May cause temporary service degradation
    """

    playbook_id = "restart_service"
    description = "Gracefully restart service with rolling strategy"
    risk_level = "medium"

    target_signatures = [
        PlaybookSignature("*", "memory_utilization", "MemoryLeakDetected"),
        PlaybookSignature("*", "error_rate", "ConsecutiveFailures"),
        PlaybookSignature("*", "circuit_breaker_failures", None),
    ]

    async def execute_async(self, alert_event: Any) -> PlaybookResult:
        """Execute service restart recovery."""
        result = PlaybookResult(
            success=False,
            action="service_restarted",
            alert_id=alert_event.alert_id,
            started_at=datetime.utcnow(),
        )

        try:
            service_name = alert_event.service_name

            logger.warning(f"AUTOMATED RECOVERY: Restarting service {service_name}")

            # Get deployment client
            deployment_client = await get_deployment_client()

            # Execute rolling restart
            restart_result = await deployment_client.rolling_restart_async(
                service=service_name,
                strategy="gradual",
                health_check_interval=30,
                max_unavailable=1,
            )

            result.success = restart_result.success
            result.details = {
                "service_name": service_name,
                "strategy": "rolling",
                "instances_restarted": restart_result.instances_restarted,
                "duration_seconds": restart_result.duration_seconds,
            }

            if result.success:
                logger.info(f"Service {service_name} restarted successfully")
            else:
                result.error_message = restart_result.error_message
                logger.error(f"Service restart failed: {restart_result.error_message}")

        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Failed to restart service: {e}", exc_info=True)

        return result

    async def rollback_async(self, execution_result: PlaybookResult) -> bool:
        """Rollback service restart.

        In practice, rollback would revert to previous version/config.
        For this MVP, we log the failure and alert operators.
        """
        logger.error(
            f"Service restart failed for {execution_result.details.get('service_name')}. "
            "Manual intervention required.",
        )
        return False


__all__ = ["RestartServicePlaybook"]
