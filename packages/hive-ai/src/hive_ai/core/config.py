"""
Configuration classes for Hive AI components.

Follows the inherit-extend pattern by building upon hive-config
with AI-specific configuration needs.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from hive_config import BaseConfig


class ModelConfig(BaseModel):
    """Configuration for individual AI models."""

    name: str = Field(..., description="Model identifier")
    provider: str = Field(..., description="Provider name (anthropic, openai, local)")
    model_type: str = Field(..., description="Model type (completion, chat, embedding)")
    api_key: Optional[str] = Field(None, description="API key for provider")
    api_base: Optional[str] = Field(None, description="Custom API base URL")
    max_tokens: int = Field(4096, description="Maximum tokens per request")
    temperature: float = Field(0.7, description="Sampling temperature")
    timeout_seconds: int = Field(30, description="Request timeout")
    rate_limit_rpm: int = Field(60, description="Requests per minute limit")
    cost_per_token: float = Field(0.0, description="Cost per token in USD")

    @validator('temperature')
    def validate_temperature(cls, v):
        if not 0.0 <= v <= 2.0:
            raise ValueError('Temperature must be between 0.0 and 2.0')
        return v

    @validator('provider')
    def validate_provider(cls, v):
        allowed = ['anthropic', 'openai', 'local', 'azure', 'huggingface']
        if v not in allowed:
            raise ValueError(f'Provider must be one of: {allowed}')
        return v


class VectorConfig(BaseModel):
    """Configuration for vector database operations."""

    provider: str = Field(..., description="Vector DB provider")
    connection_string: Optional[str] = Field(None, description="Database connection")
    collection_name: str = Field("default", description="Collection/index name")
    dimension: int = Field(1536, description="Vector dimension")
    distance_metric: str = Field("cosine", description="Distance metric")
    index_type: str = Field("hnsw", description="Index type")
    max_connections: int = Field(10, description="Max concurrent connections")
    timeout_seconds: int = Field(30, description="Operation timeout")

    @validator('distance_metric')
    def validate_distance_metric(cls, v):
        allowed = ['cosine', 'euclidean', 'dot_product']
        if v not in allowed:
            raise ValueError(f'Distance metric must be one of: {allowed}')
        return v


class PromptConfig(BaseModel):
    """Configuration for prompt templates and optimization."""

    template_directory: str = Field("prompts/", description="Template directory")
    cache_enabled: bool = Field(True, description="Enable template caching")
    validation_enabled: bool = Field(True, description="Enable variable validation")
    optimization_enabled: bool = Field(False, description="Enable prompt optimization")
    max_template_size: int = Field(50000, description="Max template size in chars")
    variable_prefix: str = Field("{{", description="Variable start delimiter")
    variable_suffix: str = Field("}}", description="Variable end delimiter")


class AIConfig(BaseConfig):
    """
    Main configuration for Hive AI components.

    Extends BaseConfig from hive-config with AI-specific settings.
    """

    # Model configurations
    models: Dict[str, ModelConfig] = Field(
        default_factory=dict,
        description="Available model configurations"
    )
    default_model: str = Field("claude-3-sonnet", description="Default model name")

    # Vector database configuration
    vector: VectorConfig = Field(
        default_factory=lambda: VectorConfig(provider="chroma"),
        description="Vector database configuration"
    )

    # Prompt configuration
    prompts: PromptConfig = Field(
        default_factory=PromptConfig,
        description="Prompt template configuration"
    )

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

    @validator('models')
    def validate_models(cls, v):
        if not v:
            # Provide default model configurations
            return {
                "claude-3-sonnet": ModelConfig(
                    name="claude-3-sonnet-20240229",
                    provider="anthropic",
                    model_type="chat",
                    max_tokens=4096,
                    cost_per_token=0.000015
                ),
                "gpt-4": ModelConfig(
                    name="gpt-4",
                    provider="openai",
                    model_type="chat",
                    max_tokens=4096,
                    cost_per_token=0.00003
                ),
                "text-embedding-ada-002": ModelConfig(
                    name="text-embedding-ada-002",
                    provider="openai",
                    model_type="embedding",
                    max_tokens=8191,
                    cost_per_token=0.0000001
                )
            }
        return v

    @validator('default_model')
    def validate_default_model(cls, v, values):
        models = values.get('models', {})
        if models and v not in models:
            raise ValueError(f'Default model "{v}" not found in configured models')
        return v

    def get_model_config(self, model_name: Optional[str] = None) -> ModelConfig:
        """Get configuration for specific model or default."""
        name = model_name or self.default_model
        if name not in self.models:
            raise ValueError(f'Model "{name}" not configured')
        return self.models[name]

    def add_model(self, config: ModelConfig) -> None:
        """Add new model configuration."""
        self.models[config.name] = config

    def remove_model(self, model_name: str) -> None:
        """Remove model configuration."""
        if model_name in self.models:
            del self.models[model_name]
            if self.default_model == model_name:
                # Set new default if available
                if self.models:
                    self.default_model = list(self.models.keys())[0]