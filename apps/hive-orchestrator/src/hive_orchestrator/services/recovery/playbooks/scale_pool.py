"""Scale Connection Pool Playbook - PROJECT CHIMERA Phase 3"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from hive_logging import get_logger

from .base import PlaybookResult, PlaybookSignature, RecoveryPlaybook

# Import PoolTuningOrchestrator
sys.path.insert(0, str(Path(__file__).parents[6] / "scripts/performance"))
try:
    from pool_tuning_orchestrator import PoolTuningOrchestrator
except ImportError:
    PoolTuningOrchestrator = None

logger = get_logger(__name__)


class ScalePoolPlaybook(RecoveryPlaybook):
    """Scale connection pool to prevent exhaustion.

    Risk Level: LOW
    - Temporarily increases pool size
    - Monitored for 15 minutes with automatic rollback on errors
    - Reversible (can restore original pool size)
    """

    playbook_id = "scale_pool"
    description = "Temporarily scale connection pool to prevent exhaustion"
    risk_level = "low"

    target_signatures = [
        PlaybookSignature("hive-db", "connection_pool", "ExhaustionPredicted"),
        PlaybookSignature("*", "connection_pool", "HighUtilization"),
    ]

    def __init__(self):
        """Initialize with pool tuning orchestrator."""
        super().__init__()
        self.pool_orchestrator = PoolTuningOrchestrator() if PoolTuningOrchestrator else None
        self._original_configs: dict[str, Any] = {}

    async def execute_async(self, alert_event: Any) -> PlaybookResult:
        """Execute pool scaling recovery."""
        result = PlaybookResult(
            success=False,
            action="pool_scaled",
            alert_id=alert_event.alert_id,
            started_at=datetime.utcnow(),
        )

        try:
            service_name = alert_event.service_name

            logger.warning(f"AUTOMATED RECOVERY: Scaling connection pool for {service_name}")

            if not self.pool_orchestrator:
                raise ImportError("PoolTuningOrchestrator not available")

            # Store original config for rollback
            original_config = await self._get_current_pool_config(service_name)
            self._original_configs[alert_event.alert_id] = original_config

            # Scale pool by 50%
            scale_result = await self.pool_orchestrator.scale_pool_async(
                service=service_name,
                scale_factor=1.5,
                duration_minutes=60,
                monitor=True,
            )

            result.success = scale_result.success
            result.details = {
                "service_name": service_name,
                "scale_factor": 1.5,
                "original_max_size": original_config.get("max_size"),
                "new_max_size": scale_result.new_max_size,
                "duration_minutes": 60,
            }

            if result.success:
                logger.info(f"Connection pool scaled for {service_name}")
            else:
                result.error_message = scale_result.error_message
                logger.error(f"Pool scaling failed: {scale_result.error_message}")

        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Failed to scale pool: {e}", exc_info=True)

        return result

    async def rollback_async(self, execution_result: PlaybookResult) -> bool:
        """Rollback pool scaling to original configuration."""
        try:
            alert_id = execution_result.alert_id
            service_name = execution_result.details.get("service_name")

            if alert_id not in self._original_configs:
                logger.warning(f"No original config found for rollback: {alert_id}")
                return False

            original_config = self._original_configs[alert_id]

            logger.warning(f"Rolling back connection pool for {service_name}")

            # Restore original pool configuration
            if self.pool_orchestrator:
                rollback_result = await self.pool_orchestrator.restore_config_async(
                    service=service_name,
                    config=original_config,
                )

                if rollback_result.success:
                    logger.info(f"Pool configuration restored for {service_name}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Rollback failed: {e}", exc_info=True)
            return False

    async def _get_current_pool_config(self, service_name: str) -> dict[str, Any]:
        """Get current pool configuration (placeholder for MVP)."""
        # In production, this would query actual pool configuration
        return {
            "service": service_name,
            "max_size": 20,  # Placeholder
            "min_size": 5,
        }


__all__ = ["ScalePoolPlaybook"]
