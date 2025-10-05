"""Adapter for guardian-agent."""

from typing import Any

from hive_bus import UnifiedEventType
from hive_logging import get_logger

from ..base_agent import AgentCapability, StandardAgent

logger = get_logger(__name__)


class GuardianAdapter(StandardAgent):
    """Adapter for guardian-agent."""

    def __init__(
        self,
        wrapped_agent: Any | None = None,
        agent_id: str = "guardian-adapter",
        event_bus: Any | None = None,
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type="guardian",
            capabilities=[AgentCapability.MONITOR],
            event_bus=event_bus,
        )
        self._wrapped_agent = wrapped_agent

    async def execute(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute monitoring/guardian task."""
        correlation_id = task_data.get("correlation_id", "unknown")

        self.emit_event(
            event_type=UnifiedEventType.TASK_STARTED,
            correlation_id=correlation_id,
            payload={"task_type": "monitor", "target": task_data.get("target")},
        )

        try:
            if self._wrapped_agent:
                result = await self._call_wrapped_agent(task_data)
            else:
                result = {"status": "monitoring", "alerts": []}

            self.emit_event(
                event_type=UnifiedEventType.TASK_COMPLETED,
                correlation_id=correlation_id,
                payload={"alerts_count": len(result.get("alerts", []))},
            )

            return result
        except Exception as e:
            logger.error(f"Guardian task failed: {e}")
            self.emit_event(
                event_type=UnifiedEventType.TASK_FAILED,
                correlation_id=correlation_id,
                payload={"error": str(e)},
            )
            raise

    async def _call_wrapped_agent(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Call wrapped guardian agent."""
        logger.info("Calling wrapped guardian agent")
        return {"status": "monitoring", "alerts": []}

    async def health_check(self) -> dict[str, Any]:
        """Check guardian health."""
        return {
            "status": "healthy",
            "message": "Guardian adapter operational",
            "wrapped_agent": self._wrapped_agent is not None,
        }
