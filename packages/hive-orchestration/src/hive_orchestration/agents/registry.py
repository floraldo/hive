"""Agent registry for unified orchestration.

The registry provides:
- Central registry of all available agents
- Capability-based agent lookup
- Agent lifecycle management (registration, health checks)
- Auto-registration of adapters for legacy agents

During migration:
- Existing agents are automatically wrapped in adapters
- New agents can register directly
- Orchestrator uses registry for agent routing

Usage:
    from hive_orchestration.agents import AgentRegistry, AgentCapability
    from hive_orchestration.agents.adapters import AIReviewerAdapter

    # Create registry
    registry = AgentRegistry()

    # Register agent (adapter or direct implementation)
    reviewer = AIReviewerAdapter()
    registry.register(reviewer)

    # Get agent by name
    agent = registry.get("ai-reviewer")

    # Get agents by capability
    reviewers = registry.get_by_capability(AgentCapability.REVIEW)

    # Health check all agents
    health = await registry.health_check_all()
"""

from typing import Any

from hive_logging import get_logger

from .base_agent import AgentCapability, StandardAgent

logger = get_logger(__name__)


class AgentRegistry:
    """Registry for managing agents in the Hive platform.

    Maintains a central registry of all available agents and provides:
    - Agent registration and deregistration
    - Lookup by agent ID, type, or capability
    - Health monitoring
    - Agent metadata
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        # Map agent_id -> agent instance
        self._agents: dict[str, StandardAgent] = {}

        # Map agent_type -> list of agent instances
        self._by_type: dict[str, list[StandardAgent]] = {}

        # Map capability -> list of agent instances
        self._by_capability: dict[AgentCapability, list[StandardAgent]] = {}

        logger.info("Initialized AgentRegistry")

    def register(self, agent: StandardAgent) -> None:
        """Register an agent.

        Args:
            agent: StandardAgent instance to register

        Raises:
            ValueError: If agent_id already registered
        """
        if agent.agent_id in self._agents:
            raise ValueError(f"Agent {agent.agent_id} already registered")

        # Register by ID
        self._agents[agent.agent_id] = agent

        # Register by type
        if agent.agent_type not in self._by_type:
            self._by_type[agent.agent_type] = []
        self._by_type[agent.agent_type].append(agent)

        # Register by capabilities
        for capability in agent.capabilities:
            if capability not in self._by_capability:
                self._by_capability[capability] = []
            self._by_capability[capability].append(agent)

        logger.info(
            f"Registered agent: {agent.agent_id} (type={agent.agent_type}, "
            f"capabilities={[c.value for c in agent.capabilities]})"
        )

    def unregister(self, agent_id: str) -> None:
        """Unregister an agent.

        Args:
            agent_id: ID of agent to unregister

        Raises:
            KeyError: If agent_id not found
        """
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not registered")

        agent = self._agents[agent_id]

        # Remove from all indices
        del self._agents[agent_id]
        self._by_type[agent.agent_type].remove(agent)

        for capability in agent.capabilities:
            self._by_capability[capability].remove(agent)
            # Clean up empty lists
            if not self._by_capability[capability]:
                del self._by_capability[capability]

        logger.info(f"Unregistered agent: {agent_id}")

    def get(self, agent_id: str) -> StandardAgent | None:
        """Get agent by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            StandardAgent instance or None if not found
        """
        return self._agents.get(agent_id)

    def get_by_type(self, agent_type: str) -> list[StandardAgent]:
        """Get all agents of a specific type.

        Args:
            agent_type: Type of agent (e.g., "ai-reviewer", "ai-planner")

        Returns:
            List of agents with that type
        """
        return self._by_type.get(agent_type, []).copy()

    def get_by_capability(self, capability: AgentCapability) -> list[StandardAgent]:
        """Get all agents with a specific capability.

        Args:
            capability: Required capability

        Returns:
            List of agents with that capability
        """
        return self._by_capability.get(capability, []).copy()

    def list_agent_ids(self) -> list[str]:
        """List all registered agent IDs.

        Returns:
            List of agent IDs
        """
        return list(self._agents.keys())

    def list_agent_types(self) -> list[str]:
        """List all registered agent types.

        Returns:
            List of unique agent types
        """
        return list(self._by_type.keys())

    def list_capabilities(self) -> list[AgentCapability]:
        """List all available capabilities.

        Returns:
            List of capabilities provided by registered agents
        """
        return list(self._by_capability.keys())

    async def health_check_all(self) -> dict[str, dict[str, Any]]:
        """Health check all registered agents.

        Returns:
            Dictionary mapping agent_id -> health status
        """
        health_results = {}

        for agent_id, agent in self._agents.items():
            try:
                health = await agent.health_check()
                health_results[agent_id] = health
            except Exception as e:
                logger.error(f"Health check failed for agent {agent_id}: {e}")
                health_results[agent_id] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        return health_results

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dictionary with registry metrics
        """
        return {
            "total_agents": len(self._agents),
            "agent_types": len(self._by_type),
            "capabilities": len(self._by_capability),
            "agents_by_type": {
                agent_type: len(agents) for agent_type, agents in self._by_type.items()
            },
            "agents_by_capability": {
                capability.value: len(agents)
                for capability, agents in self._by_capability.items()
            },
        }

    def __repr__(self) -> str:
        """String representation of registry."""
        stats = self.get_stats()
        return (
            f"<AgentRegistry agents={stats['total_agents']} "
            f"types={stats['agent_types']} capabilities={stats['capabilities']}>"
        )


# Global registry instance (optional - can create dedicated instances)
_global_registry = AgentRegistry()


def get_global_registry() -> AgentRegistry:
    """Get the global agent registry.

    This is a convenience function for simple use cases.
    For complex scenarios, create dedicated registry instances.

    Returns:
        Global AgentRegistry instance
    """
    return _global_registry


def auto_register_adapters(
    registry: AgentRegistry | None = None,
    event_bus: Any | None = None,
) -> None:
    """Auto-register all standard agent adapters.

    This creates adapter instances for all standard agents and registers them.
    Used during migration to enable orchestrator to use unified interface.

    Args:
        registry: Optional registry to use (defaults to global registry)
        event_bus: Optional event bus to provide to adapters
    """
    from .adapters import AIDeployerAdapter, AIPlannerAdapter, AIReviewerAdapter, GuardianAdapter, HiveCoderAdapter

    if registry is None:
        registry = get_global_registry()

    # Create and register all adapters
    adapters = [
        AIReviewerAdapter(event_bus=event_bus),
        AIPlannerAdapter(event_bus=event_bus),
        AIDeployerAdapter(event_bus=event_bus),
        HiveCoderAdapter(event_bus=event_bus),
        GuardianAdapter(event_bus=event_bus),
    ]

    for adapter in adapters:
        registry.register(adapter)

    logger.info(f"Auto-registered {len(adapters)} agent adapters")
