"""Agent interfaces and adapters for unified orchestration.

This module provides:
- StandardAgent: Base interface all agents should implement
- AgentCapability: Standard agent capabilities (REVIEW, PLAN, CODE, etc.)
- Agent adapters: Wrap existing agents in the StandardAgent interface

During migration:
- Existing agents keep working unchanged
- Adapters translate between old and new interfaces
- New agents can implement StandardAgent directly
"""

from .base_agent import AgentCapability, StandardAgent
from .registry import AgentRegistry, auto_register_adapters, get_global_registry

__all__ = [
    "StandardAgent",
    "AgentCapability",
    "AgentRegistry",
    "get_global_registry",
    "auto_register_adapters",
]
