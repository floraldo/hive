from hive_logging import get_logger

logger = get_logger(__name__)

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

from .core.config import AIConfig, ModelConfig, PromptConfig, VectorConfig
from .core.exceptions import AIError, CostLimitError, ModelError, ModelUnavailableError, PromptError, VectorError
from .models.client import ModelClient, ModelResponse
from .models.metrics import ModelMetrics, TokenUsage
from .models.pool import ModelPool

# Model Management
from .models.registry import ModelRegistry
from .observability.cost import CostManager
from .observability.health import ModelHealthChecker

# Observability
from .observability.metrics import AIMetricsCollector
from .prompts.optimizer import PromptOptimizer
from .prompts.registry import PromptRegistry

# Prompt Engineering
from .prompts.template import PromptChain, PromptTemplate

# Resilience (extending hive-async patterns)
from .resilience.circuit_breaker import AICircuitBreaker
from .resilience.rate_limiter import RateLimiter
from .resilience.timeout import AITimeoutManager
from .vector.embedding import EmbeddingManager
from .vector.metrics import VectorMetrics
from .vector.search import SemanticSearch

# Vector Database
from .vector.store import VectorStore

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
