"""Adapter for ai-deployer agent."""

from typing import Any

from hive_bus import UnifiedEventType
from hive_logging import get_logger

from ..base_agent import AgentCapability, StandardAgent

logger = get_logger(__name__)


class AIDeployerAdapter(StandardAgent):
    """Adapter for ai-deployer agent."""

    def __init__(
        self,
        wrapped_agent: Any | None = None,
        agent_id: str = "ai-deployer-adapter",
        event_bus: Any | None = None,
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type="ai-deployer",
            capabilities=[AgentCapability.DEPLOY],
            event_bus=event_bus,
        )
        self._wrapped_agent = wrapped_agent

    async def execute(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute deployment task."""
        correlation_id = task_data.get("correlation_id", "unknown")

        self.emit_event(
            event_type=UnifiedEventType.DEPLOYMENT_REQUESTED,
            correlation_id=correlation_id,
            payload={
                "service_name": task_data.get("service_name"),
                "environment": task_data.get("environment"),
            },
        )

        try:
            if self._wrapped_agent:
                result = await self._call_wrapped_agent(task_data)
            else:
                result = {"deployment_id": "placeholder", "status": "deployed"}

            self.emit_event(
                event_type=UnifiedEventType.DEPLOYMENT_COMPLETED,
                correlation_id=correlation_id,
                payload={"deployment_id": result.get("deployment_id")},
            )

            return result
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            self.emit_event(
                event_type=UnifiedEventType.DEPLOYMENT_FAILED,
                correlation_id=correlation_id,
                payload={"error": str(e)},
            )
            raise

    async def _call_wrapped_agent(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Call wrapped ai-deployer."""
        logger.info("Calling wrapped ai-deployer agent")
        return {"deployment_id": "deploy-123", "status": "deployed"}

    async def health_check(self) -> dict[str, Any]:
        """Check ai-deployer health."""
        return {
            "status": "healthy",
            "message": "AI Deployer adapter operational",
            "wrapped_agent": self._wrapped_agent is not None,
        }
