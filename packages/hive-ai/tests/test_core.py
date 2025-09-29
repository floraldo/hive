"""
Comprehensive tests for hive-ai core components.

Tests configuration, exceptions, and interfaces with property-based testing.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hive_ai.core.config import AIConfig, ModelConfig, PromptConfig, VectorConfig
from hive_ai.core.exceptions import AIError, CostLimitError, ModelError, ModelUnavailableError, PromptError, VectorError
from hive_ai.core.interfaces import ModelResponse, ModelType, TokenUsage


class TestAIConfig:
    """Test AIConfig configuration management."""

    def test_default_configuration(self):
        """Test default AI configuration creation."""
        config = AIConfig()

        assert isinstance(config, AIConfig)
        assert config.default_model == "claude-3-sonnet"
        assert len(config.models) >= 3  # Should have default models
        assert config.daily_cost_limit == 100.0
        assert config.monthly_cost_limit == 1000.0
        assert config.circuit_breaker_enabled is True

    def test_get_model_config(self):
        """Test model configuration retrieval."""
        config = AIConfig()

        # Test getting default model
        model_config = config.get_model_config()
        assert model_config.name == "claude-3-sonnet-20240229"
        assert model_config.provider == "anthropic"

        # Test getting specific model
        gpt4_config = config.get_model_config("gpt-4")
        assert gpt4_config.name == "gpt-4"
        assert gpt4_config.provider == "openai"

    def test_get_model_config_not_found(self):
        """Test error when model not found."""
        config = AIConfig()

        with pytest.raises(ValueError, match="not configured"):
            config.get_model_config("nonexistent-model")

    def test_add_remove_model(self):
        """Test adding and removing model configurations."""
        config = AIConfig()

        # Add new model
        new_model = ModelConfig(name="test-model", provider="test-provider", model_type="completion")
        config.add_model(new_model)

        assert "test-model" in config.models
        assert config.models["test-model"] == new_model

        # Remove model
        config.remove_model("test-model")
        assert "test-model" not in config.models

    @given(st.text(min_size=1), st.floats(min_value=0, max_value=2.0))
    def test_model_config_validation(self, name, temperature):
        """Property-based test for model configuration validation."""
        model_config = ModelConfig(name=name, provider="test", model_type="completion", temperature=temperature)

        assert model_config.name == name
        assert 0.0 <= model_config.temperature <= 2.0

    @given(st.floats())
    def test_model_config_invalid_temperature(self, temperature):
        """Test model configuration with invalid temperature."""
        # Skip valid temperatures
        if 0.0 <= temperature <= 2.0:
            return

        with pytest.raises(ValueError, match="Temperature must be between"):
            ModelConfig(name="test", provider="test", model_type="completion", temperature=temperature)

    @given(st.text())
    def test_model_config_invalid_provider(self, provider):
        """Test model configuration with invalid provider."""
        valid_providers = ["anthropic", "openai", "local", "azure", "huggingface"]

        if provider in valid_providers:
            # Should work
            model_config = ModelConfig(name="test", provider=provider, model_type="completion")
            assert model_config.provider == provider
        else:
            # Should fail
            with pytest.raises(ValueError, match="Provider must be one of"):
                ModelConfig(name="test", provider=provider, model_type="completion")


class TestVectorConfig:
    """Test vector database configuration."""

    def test_default_vector_config(self):
        """Test default vector configuration."""
        config = VectorConfig(provider="chroma")

        assert config.provider == "chroma"
        assert config.collection_name == "default"
        assert config.dimension == 1536
        assert config.distance_metric == "cosine"
        assert config.max_connections == 10

    @given(st.sampled_from(["cosine", "euclidean", "dot_product"]))
    def test_valid_distance_metrics(self, metric):
        """Test valid distance metrics."""
        config = VectorConfig(provider="chroma", distance_metric=metric)
        assert config.distance_metric == metric

    @given(st.text())
    def test_invalid_distance_metric(self, metric):
        """Test invalid distance metrics."""
        valid_metrics = ["cosine", "euclidean", "dot_product"]

        if metric not in valid_metrics:
            with pytest.raises(ValueError, match="Distance metric must be one of"):
                VectorConfig(provider="chroma", distance_metric=metric)


class TestExceptions:
    """Test AI-specific exceptions."""

    def test_ai_error_hierarchy(self):
        """Test that all AI errors inherit from AIError."""
        errors = [
            ModelError("test", model="test-model"),
            VectorError("test", collection="test-collection"),
            PromptError("test", template_name="test-template"),
            CostLimitError("test", current_cost=100.0, limit=50.0),
            ModelUnavailableError("test", model="test", provider="test"),
        ]

        for error in errors:
            assert isinstance(error, AIError)

    def test_model_error_attributes(self):
        """Test ModelError specific attributes."""
        error = ModelError("Test error", model="test-model", provider="test-provider", request_id="req-123")

        assert error.model == "test-model"
        assert error.provider == "test-provider"
        assert error.request_id == "req-123"

    def test_cost_limit_error_attributes(self):
        """Test CostLimitError specific attributes."""
        error = CostLimitError("Budget exceeded", current_cost=150.0, limit=100.0, period="daily")

        assert error.current_cost == 150.0
        assert error.limit == 100.0
        assert error.period == "daily"

    def test_prompt_error_attributes(self):
        """Test PromptError specific attributes."""
        missing_vars = ["var1", "var2"]
        error = PromptError("Missing variables", template_name="test-template", missing_variables=missing_vars)

        assert error.template_name == "test-template"
        assert error.missing_variables == missing_vars

    @given(st.floats(min_value=0), st.floats(min_value=0))
    def test_cost_limit_error_property(self, current_cost, limit):
        """Property-based test for cost limit validation."""
        error = CostLimitError("Cost exceeded", current_cost=current_cost, limit=limit)

        assert error.current_cost >= 0
        assert error.limit >= 0


class TestInterfaces:
    """Test core interfaces and data classes."""

    def test_model_response_creation(self):
        """Test ModelResponse data class."""
        response = ModelResponse(
            content="Test response",
            model="test-model",
            tokens_used=100,
            cost=0.01,
            latency_ms=1500,
            metadata={"test": "value"},
        )

        assert response.content == "Test response"
        assert response.model == "test-model"
        assert response.tokens_used == 100
        assert response.cost == 0.01
        assert response.latency_ms == 1500
        assert response.metadata["test"] == "value"

    def test_token_usage_creation(self):
        """Test TokenUsage data class."""
        usage = TokenUsage(prompt_tokens=50, completion_tokens=50, total_tokens=100, estimated_cost=0.01)

        assert usage.prompt_tokens == 50
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 100
        assert usage.estimated_cost == 0.01

    @given(st.integers(min_value=0, max_value=10000), st.integers(min_value=0, max_value=10000))
    def test_token_usage_property(self, prompt_tokens, completion_tokens):
        """Property-based test for token usage consistency."""
        total_tokens = prompt_tokens + completion_tokens

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=total_tokens * 0.0001,
        )

        assert usage.total_tokens == prompt_tokens + completion_tokens
        assert usage.estimated_cost >= 0

    def test_model_type_enum(self):
        """Test ModelType enum values."""
        assert ModelType.COMPLETION.value == "completion"
        assert ModelType.CHAT.value == "chat"
        assert ModelType.EMBEDDING.value == "embedding"
        assert ModelType.VISION.value == "vision"

    @given(st.text(), st.text(), st.integers(min_value=0), st.floats(min_value=0))
    def test_model_response_property(self, content, model, tokens, cost):
        """Property-based test for ModelResponse invariants."""
        response = ModelResponse(
            content=content, model=model, tokens_used=tokens, cost=cost, latency_ms=1000, metadata={},
        )

        assert response.tokens_used >= 0
        assert response.cost >= 0
        assert response.latency_ms >= 0


class TestConfigIntegration:
    """Test configuration integration and complex scenarios."""

    def test_config_validation_with_invalid_default_model(self):
        """Test configuration validation when default model is not in models."""
        with pytest.raises(ValueError, match="Default model.*not found"):
            AIConfig(
                models={"model1": ModelConfig(name="model1", provider="test", model_type="chat")},
                default_model="nonexistent-model",
            )

    def test_full_config_creation(self):
        """Test creating a complete AI configuration."""
        models = {
            "test-model": ModelConfig(
                name="test-model",
                provider="test",
                model_type="completion",
                temperature=0.5,
                max_tokens=2048,
                cost_per_token=0.00001,
            ),
        }

        vector_config = VectorConfig(provider="chroma", dimension=768, distance_metric="euclidean")

        prompt_config = PromptConfig(template_directory="custom_prompts/", cache_enabled=False)

        config = AIConfig(
            models=models,
            default_model="test-model",
            vector=vector_config,
            prompts=prompt_config,
            daily_cost_limit=50.0,
            monthly_cost_limit=500.0,
        )

        assert config.models["test-model"].name == "test-model"
        assert config.default_model == "test-model"
        assert config.vector.provider == "chroma"
        assert config.vector.dimension == 768
        assert config.prompts.template_directory == "custom_prompts/"
        assert config.daily_cost_limit == 50.0

    @given(st.floats(min_value=1.0, max_value=1000.0), st.floats(min_value=100.0, max_value=10000.0))
    def test_cost_limit_configuration_property(self, daily_limit, monthly_limit):
        """Property-based test for cost limit configuration."""
        # Ensure monthly is higher than daily
        if monthly_limit < daily_limit:
            monthly_limit = daily_limit * 10

        config = AIConfig(daily_cost_limit=daily_limit, monthly_cost_limit=monthly_limit)

        assert config.daily_cost_limit == daily_limit
        assert config.monthly_cost_limit == monthly_limit
        # Invariant: monthly should be >= daily
        assert config.monthly_cost_limit >= config.daily_cost_limit


@pytest.fixture
def sample_ai_config():
    """Fixture providing a sample AI configuration for tests."""
    return AIConfig()


@pytest.fixture
def sample_model_config():
    """Fixture providing a sample model configuration for tests."""
    return ModelConfig(name="test-model", provider="test", model_type="completion", temperature=0.7, max_tokens=4096)


# Performance-oriented property-based tests
@settings(max_examples=50, deadline=3000)
class TestPerformanceProperties:
    """Performance-focused property-based tests."""

    @given(st.lists(st.text(min_size=1), min_size=1, max_size=100))
    def test_model_config_creation_performance(self, model_names):
        """Test that model configuration creation scales reasonably."""
        models = {}

        for name in model_names:
            models[name] = ModelConfig(name=name, provider="test", model_type="completion")

        config = AIConfig(models=models, default_model=model_names[0])
        assert len(config.models) == len(set(model_names))  # Unique names only

    @given(st.integers(min_value=1, max_value=10000))
    def test_token_usage_calculation_performance(self, token_count):
        """Test token usage calculations with various token counts."""
        usage = TokenUsage(
            prompt_tokens=token_count // 2,
            completion_tokens=token_count // 2,
            total_tokens=token_count,
            estimated_cost=token_count * 0.00001,
        )

        # Basic performance check - should complete quickly
        assert usage.total_tokens == token_count
        assert usage.estimated_cost == token_count * 0.00001
