"""
Hive AI - Advanced AI/ML Infrastructure for the Hive Platform

This package provides production-ready AI/ML capabilities including:
- Multi-provider model management (Anthropic, OpenAI, local models)
- Vector database integration with multiple backends
- Advanced prompt engineering and optimization toolkit
- AI-specific observability and cost management
- Autonomous agent framework with resilience patterns

Built on the Hive platform's unassailable architecture for maximum
reliability, performance, and maintainability.
"""

from .core.config import AIConfig, ModelConfig, VectorConfig, PromptConfig
from .core.exceptions import (
    AIError,
    ModelError,
    VectorError,
    PromptError,
    CostLimitError,
    ModelUnavailableError,
)

# Model Management
from .models.registry import ModelRegistry
from .models.client import ModelClient, ModelResponse
from .models.pool import ModelPool
from .models.metrics import ModelMetrics, TokenUsage

# Vector Database
from .vector.store import VectorStore
from .vector.embedding import EmbeddingManager
from .vector.search import SemanticSearch
from .vector.metrics import VectorMetrics

# Prompt Engineering
from .prompts.template import PromptTemplate, PromptChain
from .prompts.optimizer import PromptOptimizer
from .prompts.registry import PromptRegistry

# Observability
from .observability.metrics import AIMetricsCollector
from .observability.health import ModelHealthChecker
from .observability.cost import CostManager

# Resilience (extending hive-async patterns)
from .resilience.circuit_breaker import AICircuitBreaker
from .resilience.rate_limiter import RateLimiter
from .resilience.timeout import AITimeoutManager

__version__ = "1.0.0"

__all__ = [
    # Core configuration and exceptions
    "AIConfig",
    "ModelConfig",
    "VectorConfig",
    "PromptConfig",
    "AIError",
    "ModelError",
    "VectorError",
    "PromptError",
    "CostLimitError",
    "ModelUnavailableError",

    # Model management
    "ModelRegistry",
    "ModelClient",
    "ModelResponse",
    "ModelPool",
    "ModelMetrics",
    "TokenUsage",

    # Vector database
    "VectorStore",
    "EmbeddingManager",
    "SemanticSearch",
    "VectorMetrics",

    # Prompt engineering
    "PromptTemplate",
    "PromptChain",
    "PromptOptimizer",
    "PromptRegistry",

    # Observability
    "AIMetricsCollector",
    "ModelHealthChecker",
    "CostManager",

    # Resilience
    "AICircuitBreaker",
    "RateLimiter",
    "AITimeoutManager",
]