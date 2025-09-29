from hive_logging import get_logger

logger = get_logger(__name__)

"""
Core interfaces and configuration for Hive AI.

Following the inherit-extend pattern, this module provides the foundational
interfaces and configuration that all AI components build upon.
"""

from .config import AIConfig, ModelConfig, PromptConfig, VectorConfig
from .exceptions import AIError, CostLimitError, ModelError, ModelUnavailableError, PromptError, VectorError
from .interfaces import MetricsCollectorInterface, ModelProviderInterface, PromptTemplateInterface, VectorStoreInterface

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
