"""Tests for hive_ai.core.interfaces module."""

from __future__ import annotations

import pytest

from hive_ai.core.interfaces import (
    MetricsCollectorInterface,
    ModelProviderInterface,
    ModelResponse,
    ModelType,
    PromptTemplateInterface,
    TokenUsage,
    VectorStoreInterface,
)


class TestModelType:
    """Test cases for ModelType enum."""

    def test_model_type_values(self):
        """Test that ModelType enum has expected values."""
        assert ModelType.COMPLETION.value == "completion"
        assert ModelType.CHAT.value == "chat"
        assert ModelType.EMBEDDING.value == "embedding"
        assert ModelType.VISION.value == "vision"

    def test_model_type_comparison(self):
        """Test ModelType enum comparison."""
        assert ModelType.COMPLETION == ModelType.COMPLETION
        assert ModelType.CHAT != ModelType.COMPLETION

    def test_model_type_membership(self):
        """Test ModelType enum membership checks."""
        model_types = [ModelType.COMPLETION, ModelType.CHAT, ModelType.EMBEDDING, ModelType.VISION]
        assert len(model_types) == 4
        assert ModelType.COMPLETION in model_types


class TestModelResponse:
    """Test cases for ModelResponse dataclass."""

    def test_model_response_creation(self):
        """Test creating ModelResponse with all fields."""
        response = ModelResponse(
            content="Generated text response",
            model="claude-3-sonnet",
            tokens_used=150,
            cost=0.015,
            latency_ms=1250,
            metadata={"provider": "anthropic", "stop_reason": "end_turn"},
        )
        assert response.content == "Generated text response"
        assert response.model == "claude-3-sonnet"
        assert response.tokens_used == 150
        assert response.cost == 0.015
        assert response.latency_ms == 1250
        assert response.metadata["provider"] == "anthropic"

    def test_model_response_empty_metadata(self):
        """Test ModelResponse with empty metadata."""
        response = ModelResponse(
            content="Test",
            model="test-model",
            tokens_used=10,
            cost=0.001,
            latency_ms=100,
            metadata={},
        )
        assert response.metadata == {}

    def test_model_response_field_access(self):
        """Test accessing ModelResponse fields."""
        response = ModelResponse(
            content="Response",
            model="gpt-4",
            tokens_used=200,
            cost=0.02,
            latency_ms=2000,
            metadata={"key": "value"},
        )
        # Should be able to access all fields
        assert hasattr(response, "content")
        assert hasattr(response, "model")
        assert hasattr(response, "tokens_used")
        assert hasattr(response, "cost")
        assert hasattr(response, "latency_ms")
        assert hasattr(response, "metadata")


class TestTokenUsage:
    """Test cases for TokenUsage dataclass."""

    def test_token_usage_creation(self):
        """Test creating TokenUsage with all fields."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost=0.015,
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.estimated_cost == 0.015

    def test_token_usage_total_calculation(self):
        """Test that total tokens can be validated."""
        usage = TokenUsage(
            prompt_tokens=75,
            completion_tokens=25,
            total_tokens=100,
            estimated_cost=0.01,
        )
        # Verify total is sum of parts
        assert usage.total_tokens == usage.prompt_tokens + usage.completion_tokens

    def test_token_usage_zero_values(self):
        """Test TokenUsage with zero values."""
        usage = TokenUsage(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost=0.0,
        )
        assert usage.prompt_tokens == 0
        assert usage.estimated_cost == 0.0


class TestModelProviderInterface:
    """Test cases for ModelProviderInterface abstract class."""

    def test_interface_is_abstract(self):
        """Test that ModelProviderInterface cannot be instantiated."""
        with pytest.raises(TypeError):
            ModelProviderInterface()

    def test_interface_requires_generate_async(self):
        """Test that implementing class must provide generate_async."""

        class IncompleteProvider(ModelProviderInterface):
            def get_available_models(self):
                return []

            def validate_connection(self):
                return True

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_interface_complete_implementation(self):
        """Test that complete implementation can be instantiated."""

        class CompleteProvider(ModelProviderInterface):
            async def generate_async(self, prompt, model, **kwargs):
                return ModelResponse(
                    content="response",
                    model=model,
                    tokens_used=10,
                    cost=0.001,
                    latency_ms=100,
                    metadata={},
                )

            async def generate_stream_async(self, prompt, model, **kwargs):
                yield "chunk"

            def get_available_models(self):
                return ["model1"]

            def validate_connection(self):
                return True

        provider = CompleteProvider()
        assert provider is not None
        assert provider.validate_connection() is True


class TestVectorStoreInterface:
    """Test cases for VectorStoreInterface abstract class."""

    def test_interface_is_abstract(self):
        """Test that VectorStoreInterface cannot be instantiated."""
        with pytest.raises(TypeError):
            VectorStoreInterface()

    def test_interface_complete_implementation(self):
        """Test complete VectorStoreInterface implementation."""

        class CompleteVectorStore(VectorStoreInterface):
            async def store_async(self, vectors, metadata, ids=None):
                return ids or ["id1", "id2"]

            async def search_async(self, query_vector, top_k=10, filter_metadata=None):
                return []

            async def delete_async(self, ids):
                return True

        store = CompleteVectorStore()
        assert store is not None


class TestPromptTemplateInterface:
    """Test cases for PromptTemplateInterface abstract class."""

    def test_interface_is_abstract(self):
        """Test that PromptTemplateInterface cannot be instantiated."""
        with pytest.raises(TypeError):
            PromptTemplateInterface()

    def test_interface_complete_implementation(self):
        """Test complete PromptTemplateInterface implementation."""

        class CompleteTemplate(PromptTemplateInterface):
            def render(self, **kwargs):
                return "rendered template"

            def validate_variables(self, **kwargs):
                return True

            def get_required_variables(self):
                return ["var1", "var2"]

        template = CompleteTemplate()
        assert template is not None
        assert template.render() == "rendered template"
        assert len(template.get_required_variables()) == 2


class TestMetricsCollectorInterface:
    """Test cases for MetricsCollectorInterface abstract class."""

    def test_interface_is_abstract(self):
        """Test that MetricsCollectorInterface cannot be instantiated."""
        with pytest.raises(TypeError):
            MetricsCollectorInterface()

    def test_interface_complete_implementation(self):
        """Test complete MetricsCollectorInterface implementation."""

        class CompleteMetricsCollector(MetricsCollectorInterface):
            async def record_model_usage_async(self, model, tokens, latency_ms, success):
                pass

            async def record_vector_operation_async(self, operation, count, latency_ms, success):
                pass

            def get_metrics_summary(self):
                return {"total_requests": 0}

        collector = CompleteMetricsCollector()
        assert collector is not None
        summary = collector.get_metrics_summary()
        assert "total_requests" in summary


class TestInterfaceContract:
    """Test interface contracts and polymorphism."""

    def test_multiple_provider_implementations(self):
        """Test that multiple providers can implement the same interface."""

        class Provider1(ModelProviderInterface):
            async def generate_async(self, prompt, model, **kwargs):
                return ModelResponse("p1", model, 10, 0.001, 100, {})

            async def generate_stream_async(self, prompt, model, **kwargs):
                yield "p1"

            def get_available_models(self):
                return ["provider1-model"]

            def validate_connection(self):
                return True

        class Provider2(ModelProviderInterface):
            async def generate_async(self, prompt, model, **kwargs):
                return ModelResponse("p2", model, 10, 0.001, 100, {})

            async def generate_stream_async(self, prompt, model, **kwargs):
                yield "p2"

            def get_available_models(self):
                return ["provider2-model"]

            def validate_connection(self):
                return False

        p1 = Provider1(),
        p2 = Provider2()

        # Both implement the interface
        assert isinstance(p1, ModelProviderInterface)
        assert isinstance(p2, ModelProviderInterface)

        # But have different implementations
        assert p1.get_available_models() != p2.get_available_models()
        assert p1.validate_connection() != p2.validate_connection()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
