"""
Prompt Engineering Toolkit for Hive AI.

Provides comprehensive prompt template management, optimization,
and engineering capabilities with type safety and validation.
"""

from .template import (
    PromptTemplate,
    PromptChain,
    PromptVariable,
    PromptMetadata
)
from .optimizer import (
    PromptOptimizer,
    OptimizationResult,
    OptimizationStrategy,
    PromptTestResult,
    PerformanceMetric
)
from .registry import PromptRegistry

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