"""Tests for hive_ai.core.config module."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from hive_ai.core.config import AIConfig, ModelConfig, PromptConfig, VectorConfig


@pytest.mark.core
class TestModelConfig:
    """Test cases for ModelConfig."""

    @pytest.mark.core
    def test_model_config_creation_with_defaults(self):
        """Test creating ModelConfig with minimal required fields."""
        config = ModelConfig(name="test-model", provider="anthropic", model_type="completion")
        assert config.name == "test-model"
        assert config.provider == "anthropic"
        assert config.model_type == "completion"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.timeout_seconds == 30

    @pytest.mark.core
    def test_model_config_with_all_fields(self):
        """Test creating ModelConfig with all fields specified."""
        config = ModelConfig(name="custom-model", provider="openai", model_type="chat", api_key="sk-test123", api_base="https://custom.api.com", max_tokens=8192, temperature=0.5, timeout_seconds=60, rate_limit_rpm=100, cost_per_token=0.001)
        assert config.api_key == "sk-test123"
        assert config.api_base == "https://custom.api.com"
        assert config.max_tokens == 8192
        assert config.temperature == 0.5
        assert config.cost_per_token == 0.001

    @pytest.mark.core
    def test_temperature_validation_valid_range(self):
        """Test temperature validation accepts valid values."""
        for temp in [0.0, 0.5, 1.0, 1.5, 2.0]:
            config = ModelConfig(name="test", provider="anthropic", model_type="completion", temperature=temp)
            assert config.temperature == temp

    @pytest.mark.core
    def test_temperature_validation_invalid_low(self):
        """Test temperature validation rejects values below 0.0."""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(name="test", provider="anthropic", model_type="completion", temperature=-0.1)
        assert "Temperature must be between 0.0 and 2.0" in str(exc_info.value)

    @pytest.mark.core
    def test_temperature_validation_invalid_high(self):
        """Test temperature validation rejects values above 2.0."""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(name="test", provider="anthropic", model_type="completion", temperature=2.1)
        assert "Temperature must be between 0.0 and 2.0" in str(exc_info.value)

    @pytest.mark.core
    def test_provider_validation_valid_providers(self):
        """Test provider validation accepts all valid providers."""
        valid_providers = ["anthropic", "openai", "local", "azure", "huggingface"]
        for provider in valid_providers:
            config = ModelConfig(name="test", provider=provider, model_type="completion")
            assert config.provider == provider

    @pytest.mark.core
    def test_provider_validation_invalid_provider(self):
        """Test provider validation rejects invalid providers."""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(name="test", provider="invalid_provider", model_type="completion")
        assert "Provider must be one of" in str(exc_info.value)

@pytest.mark.core
class TestVectorConfig:
    """Test cases for VectorConfig."""

    @pytest.mark.core
    def test_vector_config_creation_with_defaults(self):
        """Test creating VectorConfig with minimal required fields."""
        config = VectorConfig(provider="chroma")
        assert config.provider == "chroma"
        assert config.collection_name == "default"
        assert config.dimension == 1536
        assert config.distance_metric == "cosine"
        assert config.index_type == "hnsw"
        assert config.max_connections == 10

    @pytest.mark.core
    def test_vector_config_with_all_fields(self):
        """Test creating VectorConfig with all fields specified."""
        config = VectorConfig(provider="pinecone", connection_string="https://pinecone.io/index", collection_name="embeddings", dimension=384, distance_metric="euclidean", index_type="flat", max_connections=20, timeout_seconds=60)
        assert config.provider == "pinecone"
        assert config.connection_string == "https://pinecone.io/index"
        assert config.collection_name == "embeddings"
        assert config.dimension == 384
        assert config.distance_metric == "euclidean"

    @pytest.mark.core
    def test_distance_metric_validation_valid_metrics(self):
        """Test distance metric validation accepts valid metrics."""
        valid_metrics = ["cosine", "euclidean", "dot_product"]
        for metric in valid_metrics:
            config = VectorConfig(provider="chroma", distance_metric=metric)
            assert config.distance_metric == metric

    @pytest.mark.core
    def test_distance_metric_validation_invalid_metric(self):
        """Test distance metric validation rejects invalid metrics."""
        with pytest.raises(ValidationError) as exc_info:
            VectorConfig(provider="chroma", distance_metric="invalid_metric")
        assert "Distance metric must be one of" in str(exc_info.value)

@pytest.mark.core
class TestPromptConfig:
    """Test cases for PromptConfig."""

    @pytest.mark.core
    def test_prompt_config_creation_with_defaults(self):
        """Test creating PromptConfig with default values."""
        config = PromptConfig()
        assert config.template_directory == "prompts/"
        assert config.cache_enabled is True
        assert config.validation_enabled is True
        assert config.optimization_enabled is False
        assert config.max_template_size == 50000
        assert config.variable_suffix == "}}"

    @pytest.mark.core
    def test_prompt_config_with_custom_values(self):
        """Test creating PromptConfig with custom values."""
        config = PromptConfig(template_directory="custom/prompts/", cache_enabled=False, validation_enabled=False, optimization_enabled=True, max_template_size=100000)
        assert config.template_directory == "custom/prompts/"
        assert config.cache_enabled is False
        assert config.optimization_enabled is True
        assert config.max_template_size == 100000

@pytest.mark.core
class TestAIConfig:
    """Test cases for AIConfig."""

    @pytest.mark.core
    def test_ai_config_creation_with_defaults(self):
        """Test creating AIConfig with default values."""
        config = AIConfig()
        assert config.models == {}
        assert config.default_model == "claude-3-sonnet"
        assert config.vector.provider == "chroma"

    @pytest.mark.core
    def test_ai_config_with_custom_models(self):
        """Test creating AIConfig with custom model configurations."""
        model1 = ModelConfig(name="model1", provider="anthropic", model_type="completion")
        model2 = ModelConfig(name="model2", provider="openai", model_type="chat")
        config = AIConfig(models={"model1": model1, "model2": model2}, default_model="model1")
        assert len(config.models) == 2
        assert "model1" in config.models
        assert "model2" in config.models
        assert config.default_model == "model1"

    @pytest.mark.core
    def test_ai_config_with_custom_vector(self):
        """Test creating AIConfig with custom vector configuration."""
        vector_config = VectorConfig(provider="pinecone", dimension=384, collection_name="test_collection")
        config = AIConfig(vector=vector_config)
        assert config.vector.provider == "pinecone"
        assert config.vector.dimension == 384
        assert config.vector.collection_name == "test_collection"
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
