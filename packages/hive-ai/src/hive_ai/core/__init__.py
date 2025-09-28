"""
Core interfaces and configuration for Hive AI.

Following the inherit-extend pattern, this module provides the foundational
interfaces and configuration that all AI components build upon.
"""

from .config import AIConfig, ModelConfig, VectorConfig, PromptConfig
from .exceptions import (
    AIError,
    ModelError,
    VectorError,
    PromptError,
    CostLimitError,
    ModelUnavailableError,
)
from .interfaces import (
    ModelProviderInterface,
    VectorStoreInterface,
    PromptTemplateInterface,
    MetricsCollectorInterface,
)

__all__ = [
    # Configuration
    "AIConfig",
    "ModelConfig",
    "VectorConfig",
    "PromptConfig",

    # Exceptions
    "AIError",
    "ModelError",
    "VectorError",
    "PromptError",
    "CostLimitError",
    "ModelUnavailableError",

    # Interfaces
    "ModelProviderInterface",
    "VectorStoreInterface",
    "PromptTemplateInterface",
    "MetricsCollectorInterface",
]