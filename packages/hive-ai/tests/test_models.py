"""
Comprehensive tests for hive-ai model management components.

Tests ModelRegistry, ModelClient, ModelPool, and ModelMetrics with property-based testing.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hive_ai.core.config import AIConfig, ModelConfig
from hive_ai.core.exceptions import CostLimitError, ModelUnavailableError
from hive_ai.core.interfaces import ModelResponse, TokenUsage
from hive_ai.models.client import ModelClient
from hive_ai.models.metrics import ModelMetrics
from hive_ai.models.pool import ModelPool, PoolStats
from hive_ai.models.registry import ModelRegistry


class TestModelRegistry:
    """Test ModelRegistry functionality."""

    @pytest.fixture
    def sample_config(self):
        """Sample AI configuration for testing."""
        return AIConfig()

    @pytest.fixture
    def registry(self, sample_config):
        """ModelRegistry instance for testing."""
        return ModelRegistry(sample_config)

    def test_registry_initialization(self, registry):
        """Test registry initialization."""
        assert isinstance(registry, ModelRegistry)
        assert len(registry.list_available_models()) >= 3  # Default models

    def test_get_model_config(self, registry):
        """Test getting model configuration."""
        model_config = registry.get_model_config("claude-3-sonnet")
        assert model_config.name == "claude-3-sonnet-20240229"
        assert model_config.provider == "anthropic"

    def test_get_model_config_not_found(self, registry):
        """Test error when model not found."""
        with pytest.raises(ModelUnavailableError):
            registry.get_model_config("nonexistent-model")

    def test_list_models_by_type(self, registry):
        """Test filtering models by type."""
        embedding_models = registry.get_models_by_type("embedding")
        assert len(embedding_models) >= 1
        assert "text-embedding-ada-002" in embedding_models

        chat_models = registry.get_models_by_type("chat")
        assert len(chat_models) >= 2

    def test_get_cheapest_model(self, registry):
        """Test finding cheapest model by type."""
        cheapest_embedding = registry.get_cheapest_model("embedding")
        assert cheapest_embedding is not None

        # Test with nonexistent type
        cheapest_nonexistent = registry.get_cheapest_model("nonexistent")
        assert cheapest_nonexistent is None

    @patch("hive_ai.models.registry.CacheManager")
    def test_health_check_caching(self, mock_cache, registry):
        """Test provider health check caching."""
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = True
        mock_cache.return_value = mock_cache_instance

        # First call should hit cache
        health = registry.is_provider_healthy("anthropic")
        assert health is True
        mock_cache_instance.get.assert_called()

    def test_registry_stats(self, registry):
        """Test registry statistics."""
        stats = registry.get_registry_stats()

        assert "total_models" in stats
        assert "healthy_models" in stats
        assert "total_providers" in stats
        assert "health_percentage" in stats

        assert stats["total_models"] >= 3
        assert 0 <= stats["health_percentage"] <= 100

    @given(st.text(min_size=1), st.sampled_from(["chat", "completion", "embedding"]))
    def test_model_filtering_property(self, model_name, model_type):
        """Property-based test for model filtering."""
        config = AIConfig()
        config.models[model_name] = ModelConfig(name=model_name, provider="test", model_type=model_type)

        registry = ModelRegistry(config),
        models_of_type = registry.get_models_by_type(model_type)

        assert model_name in models_of_type


class TestModelClient:
    """Test ModelClient functionality."""

    @pytest.fixture
    def mock_registry(self):
        """Mock ModelRegistry for testing."""
        registry = Mock()
        registry.get_model_config.return_value = ModelConfig(
            name="test-model",
            provider="test",
            model_type="completion",
            temperature=0.7,
            max_tokens=4096,
            cost_per_token=0.00001,
        )
        registry.validate_model_available.return_value = True

        mock_provider = Mock()
        mock_provider.generate_async = AsyncMock(
            return_value=ModelResponse(
                content="Test response",
                model="test-model",
                tokens_used=50,
                cost=0.0005,
                latency_ms=1000,
                metadata={},
            ),
        )
        registry.get_provider_for_model.return_value = mock_provider

        return registry

    @pytest.fixture
    def mock_metrics(self):
        """Mock ModelMetrics for testing."""
        metrics = Mock()
        metrics.get_daily_cost_async = AsyncMock(return_value=10.0)
        metrics.get_monthly_cost_async = AsyncMock(return_value=100.0)
        metrics.record_model_usage_async = AsyncMock()
        return metrics

    @pytest.fixture
    def client(self, mock_registry, mock_metrics):
        """ModelClient instance for testing."""
        config = AIConfig(),
        client = ModelClient(config)
        client.registry = mock_registry
        client.metrics = mock_metrics
        return client

    @pytest.mark.asyncio
    async def test_generate_async_success_async(self, client):
        """Test successful model generation."""
        response = await client.generate_async("Test prompt")

        assert response.content == "Test response"
        assert response.model == "test-model"
        assert response.tokens_used == 50
        assert response.cost == 0.0005

    @pytest.mark.asyncio
    async def test_generate_async_cost_limit_exceeded_async(self, client, mock_metrics):
        """Test cost limit enforcement."""
        # Set daily cost to exceed limit
        mock_metrics.get_daily_cost_async.return_value = 99.0
        client.config.daily_cost_limit = 100.0

        # Large prompt that would exceed limit
        large_prompt = "x" * 10000  # Would cost more than $1

        with pytest.raises(CostLimitError):
            await client.generate_async(large_prompt)

    @pytest.mark.asyncio
    async def test_generate_async_model_unavailable_async(self, client, mock_registry):
        """Test handling of unavailable model."""
        mock_registry.validate_model_available.return_value = False
        mock_registry.list_healthy_models.return_value = ["alternative-model"]

        with pytest.raises(ModelUnavailableError) as exc_info:
            await client.generate_async("Test prompt", model="unavailable-model")

        assert "unavailable-model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_stream_async(self, client, mock_registry):
        """Test streaming generation."""
        mock_provider = mock_registry.get_provider_for_model.return_value

        async def mock_stream_async():
            for chunk in ["Hello", " world", "!"]:
                yield chunk

        mock_provider.generate_stream_async = mock_stream_async

        chunks = []
        async for chunk in client.generate_stream_async("Test prompt"):
            chunks.append(chunk)

        assert chunks == ["Hello", " world", "!"]

    @pytest.mark.asyncio
    async def test_health_check_async(self, client, mock_registry):
        """Test client health check."""
        mock_registry.refresh_health_status.return_value = {"test": True}
        mock_registry.get_registry_stats.return_value = {"health_percentage": 100}

        health = await client.health_check_async()

        assert health["healthy"] is True
        assert "provider_health" in health
        assert "registry_stats" in health

    @given(st.text(min_size=1, max_size=1000), st.floats(min_value=0.1, max_value=1.0))
    @pytest.mark.asyncio
    async def test_cost_estimation_property_async(self, prompt, temperature):
        """Property-based test for cost estimation."""
        config = AIConfig(),
        client = ModelClient(config),

        estimated_cost = client._estimate_cost("test-model", prompt)

        # Cost should be proportional to prompt length
        assert estimated_cost >= 0
        # Longer prompts should cost more
        if len(prompt) > 100:
            short_cost = client._estimate_cost("test-model", "short")
            assert estimated_cost > short_cost


class TestModelMetrics:
    """Test ModelMetrics functionality."""

    @pytest.fixture
    def metrics(self):
        """ModelMetrics instance for testing."""
        return ModelMetrics()

    @pytest.mark.asyncio
    async def test_record_model_usage_async(self, metrics):
        """Test recording model usage."""
        tokens = TokenUsage(prompt_tokens=25, completion_tokens=25, total_tokens=50, estimated_cost=0.0005)

        await metrics.record_model_usage_async(
            model="test-model",
            provider="test-provider",
            tokens=tokens,
            latency_ms=1000,
            success=True,
        )

        summary = metrics.get_metrics_summary()
        assert summary["total_requests"] == 1
        assert summary["successful_requests"] == 1
        assert summary["total_cost"] == 0.0005

    @pytest.mark.asyncio
    async def test_get_daily_cost_async(self, metrics):
        """Test daily cost calculation."""
        # Record some usage
        tokens = TokenUsage(10, 10, 20, 0.002)

        await metrics.record_model_usage_async(
            model="test",
            provider="test",
            tokens=tokens,
            latency_ms=500,
            success=True,
        )

        daily_cost = await metrics.get_daily_cost_async()
        assert daily_cost == 0.002

    @pytest.mark.asyncio
    async def test_get_model_performance_async(self, metrics):
        """Test model performance statistics."""
        # Record multiple operations
        for i in range(5):
            tokens = TokenUsage(10, 10, 20, 0.001)
            await metrics.record_model_usage_async(
                model="test-model",
                provider="test",
                tokens=tokens,
                latency_ms=1000 + i * 100,
                success=i < 4,  # One failure
            )

        stats = await metrics.get_model_performance_async("test-model")

        assert stats.total_requests == 5
        assert stats.successful_requests == 4
        assert stats.success_rate == 0.8
        assert stats.avg_latency_ms == 1200  # Average of 1000, 1100, 1200, 1300, 1400

    @given(st.lists(st.floats(min_value=0, max_value=10), min_size=1, max_size=100))
    @pytest.mark.asyncio
    async def test_metrics_aggregation_property_async(self, costs):
        """Property-based test for metrics aggregation."""
        metrics = ModelMetrics(),

        total_expected_cost = 0
        for cost in costs:
            tokens = TokenUsage(10, 10, 20, cost)
            await metrics.record_model_usage_async(
                model="test",
                provider="test",
                tokens=tokens,
                latency_ms=1000,
                success=True,
            )
            total_expected_cost += cost

        summary = metrics.get_metrics_summary()

        assert summary["total_requests"] == len(costs)
        assert abs(summary["total_cost"] - total_expected_cost) < 0.001  # Floating point precision


class TestModelPool:
    """Test ModelPool functionality."""

    @pytest.fixture
    def pool_config(self):
        """Sample configuration for testing."""
        return AIConfig()

    @pytest.fixture
    def model_pool(self, pool_config):
        """ModelPool instance for testing."""
        return ModelPool(pool_config)

    def test_pool_initialization(self, model_pool):
        """Test pool initialization."""
        assert isinstance(model_pool, ModelPool)
        # Should have pools for configured providers
        assert len(model_pool._pools) >= 1

    @pytest.mark.asyncio
    async def test_get_pool_stats_async(self, model_pool):
        """Test getting pool statistics."""
        stats = await model_pool.get_pool_stats_async("anthropic")

        assert isinstance(stats, PoolStats)
        assert stats.total_connections >= 0
        assert stats.active_connections >= 0
        assert stats.idle_connections >= 0

    @pytest.mark.asyncio
    async def test_scale_pool_async(self, model_pool):
        """Test dynamic pool scaling."""
        success = await model_pool.scale_pool_async("anthropic", 10)
        # Should succeed or fail gracefully
        assert isinstance(success, bool)

    @pytest.mark.asyncio
    async def test_warm_pools_async(self, model_pool):
        """Test pool warming."""
        results = await model_pool.warm_pools_async()

        assert isinstance(results, dict)
        # Should have results for each provider
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_health_check_async(self, model_pool):
        """Test pool health check."""
        health = await model_pool.health_check_async()

        assert "overall_healthy" in health
        assert "providers" in health
        assert "total_pools" in health
        assert isinstance(health["overall_healthy"], bool)

    @pytest.mark.asyncio
    async def test_optimize_pools_async(self, model_pool):
        """Test pool optimization."""
        results = await model_pool.optimize_pools_async()

        assert isinstance(results, dict)
        # Should have optimization results for providers
        for provider_result in results.values():
            assert "action" in provider_result

    @given(st.integers(min_value=1, max_value=50))
    @pytest.mark.asyncio
    async def test_pool_scaling_property_async(self, target_size):
        """Property-based test for pool scaling."""
        config = AIConfig(),
        pool = ModelPool(config)

        # Scaling should succeed for reasonable sizes
        success = await pool.scale_pool_async("anthropic", target_size)

        # Should either succeed or fail gracefully
        assert isinstance(success, bool)


class TestModelIntegration:
    """Integration tests for model components working together."""

    @pytest.fixture
    def full_config(self):
        """Complete AI configuration for integration testing."""
        return AIConfig()

    @pytest.mark.asyncio
    async def test_registry_client_integration_async(self, full_config):
        """Test ModelRegistry and ModelClient integration."""
        registry = ModelRegistry(full_config),
        client = ModelClient(full_config)

        # Should be able to list models
        models = registry.list_available_models()
        assert len(models) >= 3

        # Should be able to get model info
        model_info = await client.list_models_async()
        assert len(model_info) >= 3

    @pytest.mark.asyncio
    async def test_metrics_persistence_simulation_async(self):
        """Test metrics behavior under sustained load (simulation)."""
        metrics = ModelMetrics()

        # Simulate 100 operations
        for i in range(100):
            tokens = TokenUsage(
                prompt_tokens=20 + i % 10,
                completion_tokens=30 + i % 15,
                total_tokens=50 + i % 25,
                estimated_cost=(50 + i % 25) * 0.00001,
            )

            await metrics.record_model_usage_async(
                model=f"model-{i % 3}",  # 3 different models
                provider=f"provider-{i % 2}",  # 2 different providers
                tokens=tokens,
                latency_ms=1000 + i * 10,
                success=(i % 10) != 0,  # 90% success rate
            )

        # Check aggregated statistics
        summary = metrics.get_metrics_summary()

        assert summary["total_requests"] == 100
        assert summary["successful_requests"] == 90
        assert summary["success_rate"] == 0.9
        assert summary["total_cost"] > 0

        # Check usage summary
        usage_summary = await metrics.get_usage_summary_async()

        assert "costs" in usage_summary
        assert "usage_last_24h" in usage_summary
        assert "model_distribution" in usage_summary
        assert "provider_distribution" in usage_summary

    @settings(max_examples=20, deadline=5000)
    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=20),  # model name,
                st.integers(min_value=10, max_value=1000),  # tokens,
                st.floats(min_value=0.0001, max_value=0.1),  # cost
            ),
            min_size=1,
            max_size=50,
        ),
    )
    @pytest.mark.asyncio
    async def test_metrics_consistency_property_async(self, operations):
        """Property-based test for metrics consistency across operations."""
        metrics = ModelMetrics(),

        total_expected_cost = 0,
        total_expected_tokens = 0

        for model, tokens, cost in operations:
            token_usage = TokenUsage(
                prompt_tokens=tokens // 2,
                completion_tokens=tokens // 2,
                total_tokens=tokens,
                estimated_cost=cost,
            )

            await metrics.record_model_usage_async(
                model=model,
                provider="test",
                tokens=token_usage,
                latency_ms=1000,
                success=True,
            )

            total_expected_cost += cost
            total_expected_tokens += tokens

        summary = metrics.get_metrics_summary()

        # Verify consistency
        assert summary["total_requests"] == len(operations)
        assert abs(summary["total_cost"] - total_expected_cost) < 0.001
        assert summary["successful_requests"] == len(operations)
        assert summary["success_rate"] == 1.0
