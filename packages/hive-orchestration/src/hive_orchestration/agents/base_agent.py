"""Standard agent interface for unified orchestration.

All agents in the Hive platform should implement this interface (either directly
or through an adapter). This allows the orchestrator to:
- Route tasks to appropriate agents
- Monitor agent health
- Track agent capabilities
- Emit standardized events

Architecture:
    - StandardAgent: Abstract base class defining the agent contract
    - AgentCapability: Enum of standard agent capabilities
    - Health check support for monitoring
    - Event emission for observability

Usage:
    from hive_orchestration.agents import StandardAgent, AgentCapability

    class MyAgent(StandardAgent):
        def __init__(self):
            super().__init__(
                agent_id="my-agent-1",
                agent_type="my-agent",
                capabilities=[AgentCapability.CUSTOM]
            )

        async def execute(self, task_data: dict) -> dict:
            # Implement task execution
            return {"result": "success"}

        async def health_check(self) -> dict:
            # Implement health check
            return {"status": "healthy"}
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from hive_bus import UnifiedEvent, UnifiedEventType
from hive_logging import get_logger

logger = get_logger(__name__)


class AgentCapability(str, Enum):
    """Standard agent capabilities.

    These map to common task types in the platform:
    - REVIEW: Code review and quality analysis (ai-reviewer)
    - PLAN: Planning and task breakdown (ai-planner)
    - CODE: Code generation and modification (hive-coder)
    - DEPLOY: Deployment and infrastructure (ai-deployer)
    - TEST: Test generation and execution (qa-agent)
    - MONITOR: Monitoring and alerting (guardian-agent)
    - ORCHESTRATE: Workflow orchestration (hive-orchestrator)
    - CUSTOM: Custom agent capabilities
    """

    REVIEW = "review"
    PLAN = "plan"
    CODE = "code"
    DEPLOY = "deploy"
    TEST = "test"
    MONITOR = "monitor"
    ORCHESTRATE = "orchestrate"
    CUSTOM = "custom"


class StandardAgent(ABC):
    """Standard agent interface for the Hive platform.

    All agents should either:
    1. Inherit from this class directly (new agents)
    2. Be wrapped in an adapter that implements this interface (legacy agents)

    This interface enables:
    - Standardized task execution
    - Health monitoring
    - Event emission for observability
    - Capability-based routing
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        capabilities: list[AgentCapability],
        event_bus: Any | None = None,
    ):
        """Initialize standard agent.

        Args:
            agent_id: Unique identifier for this agent instance
            agent_type: Type of agent (e.g., "ai-reviewer", "ai-planner")
            capabilities: List of capabilities this agent provides
            event_bus: Optional event bus for emitting events
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.capabilities = capabilities
        self._event_bus = event_bus

    @abstractmethod
    async def execute(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a task.

        Args:
            task_data: Task input data (structure varies by agent type)

        Returns:
            Task result data

        Raises:
            Exception: If task execution fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check agent health status.

        Returns:
            Health status dictionary with at least:
            - status: "healthy" | "unhealthy" | "degraded"
            - message: Optional health message
            - details: Optional additional health details
        """
        pass

    def emit_event(
        self,
        event_type: UnifiedEventType,
        correlation_id: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Emit a unified event.

        Args:
            event_type: Type of event to emit
            correlation_id: Correlation ID for tracking related events
            payload: Event payload data
            metadata: Optional event metadata
        """
        if self._event_bus is None:
            logger.warning(
                f"Agent {self.agent_id} has no event bus configured, skipping event emission"
            )
            return

        event = UnifiedEvent(
            event_type=event_type,
            correlation_id=correlation_id,
            payload=payload,
            source_agent=self.agent_type,
            metadata=metadata or {},
        )

        try:
            self._event_bus.emit(event)
            logger.debug(
                f"Agent {self.agent_id} emitted event: {event_type.value} "
                f"(correlation_id={correlation_id})"
            )
        except Exception as e:
            logger.error(f"Failed to emit event from agent {self.agent_id}: {e}")

    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent has a specific capability.

        Args:
            capability: Capability to check for

        Returns:
            True if agent has the capability
        """
        return capability in self.capabilities

    def get_info(self) -> dict[str, Any]:
        """Get agent information.

        Returns:
            Dictionary with agent metadata:
            - agent_id: Unique agent identifier
            - agent_type: Agent type
            - capabilities: List of capabilities
        """
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "capabilities": [cap.value for cap in self.capabilities],
        }

    def __repr__(self) -> str:
        """String representation of agent."""
        caps = ", ".join(cap.value for cap in self.capabilities)
        return f"<{self.__class__.__name__} id={self.agent_id} type={self.agent_type} capabilities=[{caps}]>"
