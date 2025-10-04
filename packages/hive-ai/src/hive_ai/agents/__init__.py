"""AI agents with sequential thinking capabilities.

This module provides the BaseAgent class with God Mode features including:
- Multi-step sequential thinking loop (1-30 thoughts)
- Retry prevention via solution hashing
- Web search integration via Exa
- RAG-powered context retrieval
"""

from hive_ai.agents.agent import BaseAgent

__all__ = ["BaseAgent"]
