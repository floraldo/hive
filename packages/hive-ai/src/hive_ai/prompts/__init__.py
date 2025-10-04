from hive_logging import get_logger

logger = get_logger(__name__)

"""
Prompt Engineering Toolkit for Hive AI.

Provides comprehensive prompt template management, optimization,
and engineering capabilities with type safety and validation.
"""

from .optimizer import OptimizationResult, OptimizationStrategy, PerformanceMetric, PromptOptimizer, PromptTestResult
from .registry import PromptRegistry
from .template import PromptChain, PromptMetadata, PromptTemplate, PromptVariable

__all__ = [
    "OptimizationResult",
    "OptimizationStrategy",
    "PerformanceMetric",
    "PromptChain",
    "PromptMetadata",
    # Optimization and testing
    "PromptOptimizer",
    # Registry management
    "PromptRegistry",
    # Core template management
    "PromptTemplate",
    "PromptTestResult",
    "PromptVariable",
]
