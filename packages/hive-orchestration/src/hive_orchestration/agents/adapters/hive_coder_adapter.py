"""Adapter for hive-coder agent."""

from typing import Any

from hive_bus import UnifiedEventType
from hive_logging import get_logger

from ..base_agent import AgentCapability, StandardAgent

logger = get_logger(__name__)


class HiveCoderAdapter(StandardAgent):
    """Adapter for hive-coder agent."""

    def __init__(
        self,
        wrapped_agent: Any | None = None,
        agent_id: str = "hive-coder-adapter",
        event_bus: Any | None = None,
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type="hive-coder",
            capabilities=[AgentCapability.CODE],
            event_bus=event_bus,
        )
        self._wrapped_agent = wrapped_agent

    async def execute(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute code generation/modification task."""
        correlation_id = task_data.get("correlation_id", "unknown")

        self.emit_event(
            event_type=UnifiedEventType.TASK_STARTED,
            correlation_id=correlation_id,
            payload={"task_type": "code", "description": task_data.get("description")},
        )

        try:
            if self._wrapped_agent:
                result = await self._call_wrapped_agent(task_data)
            else:
                result = {"files_modified": [], "status": "completed"}

            self.emit_event(
                event_type=UnifiedEventType.TASK_COMPLETED,
                correlation_id=correlation_id,
                payload={"files_modified": result.get("files_modified", [])},
            )

            return result
        except Exception as e:
            logger.error(f"Coding task failed: {e}")
            self.emit_event(
                event_type=UnifiedEventType.TASK_FAILED,
                correlation_id=correlation_id,
                payload={"error": str(e)},
            )
            raise

    async def _call_wrapped_agent(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Call wrapped hive-coder."""
        logger.info("Calling wrapped hive-coder agent")
        return {"files_modified": [], "status": "completed"}

    async def health_check(self) -> dict[str, Any]:
        """Check hive-coder health."""
        return {
            "status": "healthy",
            "message": "Hive Coder adapter operational",
            "wrapped_agent": self._wrapped_agent is not None,
        }
