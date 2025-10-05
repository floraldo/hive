"""Adapter for ai-planner agent."""

from typing import Any

from hive_bus import UnifiedEventType
from hive_logging import get_logger

from ..base_agent import AgentCapability, StandardAgent

logger = get_logger(__name__)


class AIPlannerAdapter(StandardAgent):
    """Adapter for ai-planner agent."""

    def __init__(
        self,
        wrapped_agent: Any | None = None,
        agent_id: str = "ai-planner-adapter",
        event_bus: Any | None = None,
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type="ai-planner",
            capabilities=[AgentCapability.PLAN],
            event_bus=event_bus,
        )
        self._wrapped_agent = wrapped_agent

    async def execute(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute planning task."""
        correlation_id = task_data.get("correlation_id", "unknown")

        self.emit_event(
            event_type=UnifiedEventType.PLAN_REQUESTED,
            correlation_id=correlation_id,
            payload={"task_description": task_data.get("description")},
        )

        try:
            if self._wrapped_agent:
                result = await self._call_wrapped_agent(task_data)
            else:
                result = {"plan": "Placeholder plan", "phases": []}

            self.emit_event(
                event_type=UnifiedEventType.PLAN_GENERATED,
                correlation_id=correlation_id,
                payload={"plan_id": result.get("plan_id", "unknown")},
            )

            return result
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            self.emit_event(
                event_type=UnifiedEventType.AGENT_ERROR,
                correlation_id=correlation_id,
                payload={"error": str(e)},
            )
            raise

    async def _call_wrapped_agent(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Call wrapped ai-planner."""
        logger.info("Calling wrapped ai-planner agent")
        return {"plan": "Generated plan", "phases": []}

    async def health_check(self) -> dict[str, Any]:
        """Check ai-planner health."""
        return {
            "status": "healthy",
            "message": "AI Planner adapter operational",
            "wrapped_agent": self._wrapped_agent is not None,
        }
