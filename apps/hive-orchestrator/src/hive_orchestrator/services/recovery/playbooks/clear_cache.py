"""Clear Cache Playbook - PROJECT CHIMERA Phase 3"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hive_cache import get_cache_client
from hive_logging import get_logger

from .base import PlaybookResult, PlaybookSignature, RecoveryPlaybook

logger = get_logger(__name__)


class ClearCachePlaybook(RecoveryPlaybook):
    """Clear cache for service experiencing cache-related issues.

    Risk Level: LOW
    - Clears cache which will be rebuilt from source
    - May cause temporary performance degradation but no data loss
    - Fully reversible (cache repopulates automatically)
    """

    playbook_id = "clear_cache"
    description = "Clear cache for service experiencing cache corruption or stale data"
    risk_level = "low"

    target_signatures = [
        PlaybookSignature("hive-cache", "error_rate", "CacheCorruption"),
        PlaybookSignature("*", "cache_hit_rate", "AnomalouslyLow"),
        PlaybookSignature("*", "cache_errors", None),
    ]

    async def execute_async(self, alert_event: Any) -> PlaybookResult:
        """Execute cache clear recovery."""
        result = PlaybookResult(
            success=False,
            action="cache_cleared",
            alert_id=alert_event.alert_id,
            started_at=datetime.utcnow(),
        )

        try:
            service_name = alert_event.service_name

            logger.warning(f"AUTOMATED RECOVERY: Clearing cache for {service_name}")

            # Get cache client
            cache_client = await get_cache_client()

            # Clear cache (in production, might clear specific keys by service)
            # For MVP, we'll use pattern matching
            pattern = f"{service_name}:*"
            keys_cleared = await cache_client.delete_pattern_async(pattern)

            result.success = True
            result.details = {
                "service_name": service_name,
                "keys_cleared": keys_cleared,
                "pattern": pattern,
            }

            logger.info(f"Cache cleared for {service_name}: {keys_cleared} keys removed")

        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Failed to clear cache: {e}", exc_info=True)

        return result

    async def rollback_async(self, execution_result: PlaybookResult) -> bool:
        """Rollback not needed for cache clear.

        Cache will repopulate automatically from source data.
        """
        logger.info("Cache clear doesn't require rollback (auto-repopulates)")
        return True


__all__ = ["ClearCachePlaybook"]
