"""
Core interfaces for Hive AI components.

Defines the contracts that all AI implementations must follow,
enabling provider independence and testability.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, AsyncIterable
from dataclasses import dataclass
from enum import Enum


class ModelType(Enum):
    """AI model types supported by the platform."""
    COMPLETION = "completion"
    CHAT = "chat"
    EMBEDDING = "embedding"
    VISION = "vision"


@dataclass
class ModelResponse:
    """Standardized response from any AI model."""
    content: str
    model: str
    tokens_used: int
    cost: float
    latency_ms: int
    metadata: Dict[str, Any]


@dataclass
class TokenUsage:
    """Token usage tracking for cost and performance monitoring."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float


class ModelProviderInterface(ABC):
    """Abstract interface for AI model providers."""

    @abstractmethod
    async def generate_async(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> ModelResponse:
        """Generate completion from model."""
        pass

    @abstractmethod
    async def generate_stream_async(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> AsyncIterable[str]:
        """Generate streaming completion from model."""
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Return list of available models."""
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate provider connection."""
        pass


class VectorStoreInterface(ABC):
    """Abstract interface for vector database operations."""

    @abstractmethod
    async def store_async(
        self,
        vectors: List[List[float]],
        metadata: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Store vectors with metadata."""
        pass

    @abstractmethod
    async def search_async(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        pass

    @abstractmethod
    async def delete_async(self, ids: List[str]) -> bool:
        """Delete vectors by IDs."""
        pass


class PromptTemplateInterface(ABC):
    """Abstract interface for prompt template management."""

    @abstractmethod
    def render(self, **kwargs) -> str:
        """Render template with provided variables."""
        pass

    @abstractmethod
    def validate_variables(self, **kwargs) -> bool:
        """Validate required template variables."""
        pass

    @abstractmethod
    def get_required_variables(self) -> List[str]:
        """Get list of required template variables."""
        pass


class MetricsCollectorInterface(ABC):
    """Abstract interface for metrics collection."""

    @abstractmethod
    async def record_model_usage_async(
        self,
        model: str,
        tokens: TokenUsage,
        latency_ms: int,
        success: bool
    ) -> None:
        """Record model usage metrics."""
        pass

    @abstractmethod
    async def record_vector_operation_async(
        self,
        operation: str,
        count: int,
        latency_ms: int,
        success: bool
    ) -> None:
        """Record vector database operation metrics."""
        pass

    @abstractmethod
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get aggregated metrics summary."""
        pass