from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Configuration classes for Hive AI components.

Follows the inherit-extend pattern by building upon hive-config
with AI-specific configuration needs.
"""

from typing import Any

from pydantic import BaseModel, Field, validator

from hive_config import BaseConfig


class ModelConfig(BaseModel):
    """Configuration for individual AI models."""

    name: str = Field(..., description="Model identifier")
    provider: str = Field(..., description="Provider name (anthropic, openai, local)")
    model_type: str = Field(..., description="Model type (completion, chat, embedding)")
    api_key: str | None = Field(None, description="API key for provider")
    api_base: str | None = Field(None, description="Custom API base URL")
    max_tokens: int = Field(4096, description="Maximum tokens per request")
    temperature: float = Field(0.7, description="Sampling temperature")
    timeout_seconds: int = Field(30, description="Request timeout")
    rate_limit_rpm: int = Field(60, description="Requests per minute limit")
    cost_per_token: float = Field(0.0, description="Cost per token in USD")

    @validator("temperature")
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is within valid range (0.0-2.0)."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    @validator("provider")
    def validate_provider(cls, v: str) -> str:
        """Validate provider is in allowed list."""
        allowed = ["anthropic", "openai", "local", "azure", "huggingface"]
        if v not in allowed:
            raise ValueError(f"Provider must be one of: {allowed}")
        return v


class VectorConfig(BaseModel):
    """Configuration for vector database operations."""

    provider: str = Field(..., description="Vector DB provider")
    connection_string: str | None = Field(None, description="Database connection")
    collection_name: str = Field("default", description="Collection/index name")
    dimension: int = Field(1536, description="Vector dimension")
    distance_metric: str = Field("cosine", description="Distance metric")
    index_type: str = Field("hnsw", description="Index type")
    max_connections: int = Field(10, description="Max concurrent connections")
    timeout_seconds: int = Field(30, description="Operation timeout")

    @validator("distance_metric")
    def validate_distance_metric(cls, v: str) -> str:
        """Validate distance metric is in allowed list."""
        allowed = ["cosine", "euclidean", "dot_product"]
        if v not in allowed:
            raise ValueError(f"Distance metric must be one of: {allowed}")
        return v


class PromptConfig(BaseModel):
    """Configuration for prompt templates and optimization."""

    template_directory: str = Field("prompts/", description="Template directory")
    cache_enabled: bool = Field(True, description="Enable template caching")
    validation_enabled: bool = Field(True, description="Enable variable validation")
    optimization_enabled: bool = Field(False, description="Enable prompt optimization")
    max_template_size: int = Field(50000, description="Max template size in chars")
    variable_prefix: str = (Field("{{", description="Variable start delimiter"),)
    variable_suffix: str = Field("}}", description="Variable end delimiter")


class AIConfig(BaseConfig):
    """Main configuration for Hive AI components.

    Extends BaseConfig from hive-config with AI-specific settings.
    """

    # Model configurations
    models: dict[str, ModelConfig] = Field(default_factory=dict, description="Available model configurations")
    default_model: str = Field("claude-3-sonnet", description="Default model name")

    # Vector database configuration
    vector: VectorConfig = Field(
        default_factory=lambda: VectorConfig(provider="chroma"),
        description="Vector database configuration",
    )

    # Prompt configuration
    prompts: PromptConfig = Field(default_factory=PromptConfig, description="Prompt template configuration")

    # Cost and usage limits
    daily_cost_limit: float = Field(100.0, description="Daily cost limit in USD")
    monthly_cost_limit: float = Field(1000.0, description="Monthly cost limit in USD")
    token_rate_limit: int = Field(10000, description="Tokens per minute limit")

    # Circuit breaker settings
    circuit_breaker_enabled: bool = Field(True, description="Enable circuit breakers")
    failure_threshold: int = Field(5, description="Failures before opening circuit")
    recovery_timeout: int = Field(60, description="Recovery timeout in seconds")

    # Observability settings
    metrics_enabled: bool = Field(True, description="Enable metrics collection")
    tracing_enabled: bool = Field(False, description="Enable request tracing")
    log_requests: bool = Field(False, description="Log all requests")

    @validator("models")
    def validate_models(cls, v: dict[str, ModelConfig]) -> dict[str, ModelConfig]:
        """Validate models configuration and provide defaults if empty."""
        if not v:
            # Provide default model configurations
            return {
                "claude-3-sonnet": ModelConfig(
                    name="claude-3-sonnet-20240229",
                    provider="anthropic",
                    model_type="chat",
                    max_tokens=4096,
                    cost_per_token=0.000015,
                ),
                "gpt-4": ModelConfig(
                    name="gpt-4",
                    provider="openai",
                    model_type="chat",
                    max_tokens=4096,
                    cost_per_token=0.00003,
                ),
                "text-embedding-ada-002": ModelConfig(
                    name="text-embedding-ada-002",
                    provider="openai",
                    model_type="embedding",
                    max_tokens=8191,
                    cost_per_token=0.0000001,
                ),
            }
        return v

    @validator("default_model")
    def validate_default_model(cls, v: str, values: dict[str, Any]) -> str:
        """Validate default model exists in configured models."""
        models = values.get("models", {})
        if models and v not in models:
            raise ValueError(f'Default model "{v}" not found in configured models')
        return v

    def get_model_config(self, model_name: str | None = None) -> ModelConfig:
        """Get configuration for specific model or default.

        Args:
            model_name: Name of the model to retrieve. If None, uses default_model.

        Returns:
            ModelConfig instance for the specified model.

        Raises:
            ValueError: If the specified model is not configured.

        """
        name = model_name or self.default_model
        if name not in self.models:
            raise ValueError(f'Model "{name}" not configured')
        return self.models[name]

    def add_model(self, config: ModelConfig) -> None:
        """Add new model configuration.

        Args:
            config: ModelConfig instance to add to available models.

        """
        self.models[config.name] = config

    def remove_model(self, model_name: str) -> None:
        """Remove model configuration.

        Args:
            model_name: Name of the model to remove from configuration.

        Note:
            If removing the default model, automatically sets a new default
            from remaining models if any exist.

        """
        if model_name in self.models:
            del self.models[model_name]
            if self.default_model == model_name:
                # Set new default if available
                if self.models:
                    self.default_model = list(self.models.keys())[0]


class AgentConfig(BaseConfig):
    """Configuration for AI agents with sequential thinking capabilities.

    Extends BaseConfig from hive-config with agent-specific settings including
    the God Mode sequential thinking loop and web search integration.
    """

    # Sequential thinking configuration (God Mode)
    max_thoughts: int = Field(
        default=1,
        ge=1,
        le=50,
        description="Maximum sequential thinking steps per task (1-50)",
    )

    enable_retry_prevention: bool = Field(
        default=True,
        description="Prevent retrying identical failed solutions via hashing",
    )

    thought_timeout_seconds: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="Maximum time allowed for thinking loop (10-3600 seconds)",
    )

    # Web search configuration (Exa integration)
    enable_exa_search: bool = Field(
        default=False,
        description="Enable Exa web search tool for real-time knowledge retrieval",
    )

    exa_results_count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of search results to retrieve from Exa (1-20)",
    )

    # RAG and knowledge archival
    enable_knowledge_archival: bool = Field(
        default=True,
        description="Archive thinking sessions and web searches to RAG",
    )

    rag_retrieval_count: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of RAG documents to retrieve for context (1-50)",
    )

    # Agent behavior
    agent_name: str = Field(
        default="default",
        description="Agent identifier for logging and tracking",
    )

    agent_role: str = Field(
        default="general",
        description="Agent role (general, specialist, coordinator)",
    )

    enable_episodic_memory: bool = Field(
        default=True,
        description="Store thinking session logs for later analysis",
    )

    @validator("max_thoughts")
    def validate_max_thoughts(cls, v: int) -> int:
        """Validate max_thoughts is within reasonable range."""
        if v > 50:
            logger.warning(f"max_thoughts={v} is high, may impact performance")
        return v

    @validator("agent_role")
    def validate_agent_role(cls, v: str) -> str:
        """Validate agent role is in allowed list."""
        allowed = ["general", "specialist", "coordinator", "tester", "reviewer"]
        if v not in allowed:
            raise ValueError(f"Agent role must be one of: {allowed}")
        return v
