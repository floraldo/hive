from hive_logging import get_logger

logger = get_logger(__name__)

"""
Core interfaces for Hive AI components.

Defines the contracts that all AI implementations must follow,
enabling provider independence and testability.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterable, Dict, List, Optional


class ModelType(Enum):
    """AI model types supported by the platform.

    Categorizes models by their primary function to enable
    appropriate routing and configuration.
    """

    COMPLETION = "completion"
    CHAT = "chat"
    EMBEDDING = "embedding"
    VISION = "vision"


@dataclass
class ModelResponse:
    """Standardized response from any AI model.

    Provides consistent interface for model outputs regardless
    of the underlying provider implementation.
    """

    content: str
    model: str
    tokens_used: int
    cost: float
    latency_ms: int
    metadata: Dict[str, Any]


@dataclass
class TokenUsage:
    """Token usage tracking for cost and performance monitoring.

    Enables precise cost calculation and usage analytics
    across different model providers.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float


class ModelProviderInterface(ABC):
    """Abstract interface for AI model providers.

    Defines the contract that all model providers (Anthropic, OpenAI, etc.)
    must implement for seamless integration.
    """

    @abstractmethod
    async def generate_async(self, prompt: str, model: str, **kwargs) -> ModelResponse:
        """Generate completion from model.

        Args:
            prompt: Input text to generate completion for.
            model: Model identifier to use for generation.
            **kwargs: Provider-specific parameters.

        Returns:
            ModelResponse containing generated content and metadata.
        """
        pass

    @abstractmethod
    async def generate_stream_async(self, prompt: str, model: str, **kwargs) -> AsyncIterable[str]:
        """Generate streaming completion from model.

        Args:
            prompt: Input text to generate completion for.
            model: Model identifier to use for generation.
            **kwargs: Provider-specific parameters.

        Yields:
            str: Incremental completion chunks as they become available.
        """
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Return list of available models.

        Returns:
            List of model identifiers available from this provider.
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate provider connection.

        Returns:
            True if connection is healthy, False otherwise.
        """
        pass


class VectorStoreInterface(ABC):
    """Abstract interface for vector database operations.

    Provides unified interface for vector storage and similarity search
    across different vector database providers.
    """

    @abstractmethod
    async def store_async(
        self,
        vectors: List[List[float]],
        metadata: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Store vectors with metadata.

        Args:
            vectors: List of vector embeddings to store.,
            metadata: Corresponding metadata for each vector.,
            ids: Optional custom IDs for vectors. Generated if not provided.

        Returns:
            List of vector IDs that were assigned.
        """
        pass

    @abstractmethod
    async def search_async(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors.

        Args:
            query_vector: Vector to find similarities for.,
            top_k: Maximum number of results to return.,
            filter_metadata: Optional metadata filters to apply.

        Returns:
            List of search results with vectors, metadata, and similarity scores.
        """
        pass

    @abstractmethod
    async def delete_async(self, ids: List[str]) -> bool:
        """Delete vectors by IDs.

        Args:
            ids: List of vector IDs to delete.

        Returns:
            True if deletion was successful, False otherwise.
        """
        pass


class PromptTemplateInterface(ABC):
    """Abstract interface for prompt template management.

    Enables type-safe prompt rendering with variable validation
    and template reuse across different AI operations.
    """

    @abstractmethod
    def render(self, **kwargs) -> str:
        """Render template with provided variables.

        Args:
            **kwargs: Template variables to substitute.

        Returns:
            Rendered template string with variables substituted.
        """
        pass

    @abstractmethod
    def validate_variables(self, **kwargs) -> bool:
        """Validate required template variables.

        Args:
            **kwargs: Variables to validate against template requirements.

        Returns:
            True if all required variables are provided with correct types.
        """
        pass

    @abstractmethod
    def get_required_variables(self) -> List[str]:
        """Get list of required template variables.

        Returns:
            List of variable names that must be provided for rendering.
        """
        pass


class MetricsCollectorInterface(ABC):
    """Abstract interface for metrics collection.

    Enables comprehensive monitoring and observability across
    all AI operations with provider-agnostic metrics.
    """

    @abstractmethod
    async def record_model_usage_async(self, model: str, tokens: TokenUsage, latency_ms: int, success: bool) -> None:
        """Record model usage metrics.

        Args:
            model: Model identifier that was used.
            tokens: Token usage details for the operation.
            latency_ms: Operation latency in milliseconds.
            success: Whether the operation completed successfully.
        """
        pass

    @abstractmethod
    async def record_vector_operation_async(self, operation: str, count: int, latency_ms: int, success: bool) -> None:
        """Record vector database operation metrics.

        Args:
            operation: Type of vector operation (store, search, delete).
            count: Number of vectors processed.
            latency_ms: Operation latency in milliseconds.
            success: Whether the operation completed successfully.
        """
        pass

    @abstractmethod
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get aggregated metrics summary.

        Returns:
            Dictionary containing aggregated metrics and performance statistics.
        """
        pass
