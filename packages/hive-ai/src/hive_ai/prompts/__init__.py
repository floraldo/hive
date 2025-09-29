from hive_logging import get_logger

logger = get_logger(__name__)

"""
Prompt Engineering Toolkit for Hive AI.

Provides comprehensive prompt template management, optimization,
and engineering capabilities with type safety and validation.
"""

from .optimizer import (
    OptimizationResult,
    OptimizationStrategy,
    PerformanceMetric,
    PromptOptimizer,
    PromptTestResult,
)
from .registry import PromptRegistry
from .template import PromptChain, PromptMetadata, PromptTemplate, PromptVariable

__all__ = [
    # Core template management
    "PromptTemplate",
    "PromptChain",
    "PromptVariable",
    "PromptMetadata",
    # Optimization and testing
    "PromptOptimizer",
    "OptimizationResult",
    "OptimizationStrategy",
    "PromptTestResult",
    "PerformanceMetric",
    # Registry management
    "PromptRegistry",
]
