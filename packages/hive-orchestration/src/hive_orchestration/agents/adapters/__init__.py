"""Agent adapters for legacy agent integration.

These adapters wrap existing agents to implement the StandardAgent interface.
This allows:
- Legacy agents to work without modification
- Gradual migration to unified interface
- Backwards compatibility during transition

Available adapters:
- AIReviewerAdapter: Wraps ai-reviewer agent
- GuardianAdapter: Wraps guardian-agent
- HiveCoderAdapter: Wraps hive-coder agent
- AIDeployerAdapter: Wraps ai-deployer agent
- AIPlannerAdapter: Wraps ai-planner agent

Usage:
    from hive_orchestration.agents.adapters import AIReviewerAdapter

    # Wrap existing agent
    adapter = AIReviewerAdapter(original_agent_instance)

    # Use through StandardAgent interface
    result = await adapter.execute(task_data)
    health = await adapter.health_check()
"""

from .ai_deployer_adapter import AIDeployerAdapter
from .ai_planner_adapter import AIPlannerAdapter
from .ai_reviewer_adapter import AIReviewerAdapter
from .guardian_adapter import GuardianAdapter
from .hive_coder_adapter import HiveCoderAdapter

__all__ = [
    "AIReviewerAdapter",
    "GuardianAdapter",
    "HiveCoderAdapter",
    "AIDeployerAdapter",
    "AIPlannerAdapter",
]
