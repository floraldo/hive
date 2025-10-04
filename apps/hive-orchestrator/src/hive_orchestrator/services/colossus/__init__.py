"""Colossus - Autonomous Development Pipeline Services.

Provides NL requirement → ExecutionPlan → Service code generation.

Architecture:
    ArchitectService: NL requirements → ExecutionPlan (JSON)
    CoderService: ExecutionPlan → Service code (via hive-toolkit)

Integration:
    - Used by ProjectOrchestrator in hive-ui
    - Coordinates with Guardian for validation
    - Leverages hive-bus for event communication
"""

from __future__ import annotations

from .architect_service import ArchitectService
from .coder_service import CoderService

__all__ = [
    "ArchitectService",
    "CoderService",
]
