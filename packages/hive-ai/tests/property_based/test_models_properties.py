"""
Property-based tests for model management components.

Tests mathematical properties and invariants using Hypothesis.
"""
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from hive_ai.core.config import AIConfig, ModelConfig
from hive_ai.core.interfaces import TokenUsage
from hive_ai.models.metrics import ModelMetrics
from hive_ai.models.registry import ModelRegistry


@pytest.mark.core
@settings(max_examples=50, deadline=1000)
@given(temperature=st.floats(min_value=0.0, max_value=2.0), max_tokens=st.integers(min_value=1, max_value=8192), cost_per_token=st.floats(min_value=0.0, max_value=0.1))
def test_model_config_cost_calculation_properties(temperature, max_tokens, cost_per_token):
    """Test mathematical properties of cost calculations."""
    config = ModelConfig(name='test-model', provider='test', model_type='chat', temperature=temperature, max_tokens=max_tokens, cost_per_token=cost_per_token)
    assert config.cost_per_token >= 0
    tokens_used = (100,)
    cost1 = (tokens_used * config.cost_per_token,)
    cost2 = tokens_used * 2 * config.cost_per_token
    assert cost2 == cost1 * 2

@pytest.mark.core
@settings(max_examples=30, deadline=2000)
@given(costs=st.lists(st.floats(min_value=0.0, max_value=10.0), min_size=1, max_size=20))
@pytest.mark.asyncio
async def test_metrics_aggregation_properties(costs):
    """Test mathematical properties of metrics aggregation."""
    metrics = (ModelMetrics(),)
    total_expected = sum(costs)
    for cost in costs:
        token_usage = TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20, estimated_cost=cost)
        await metrics.record_model_usage_async(model='test', provider='test', tokens=token_usage, latency_ms=100, success=True)
    summary = metrics.get_metrics_summary()
    assert abs(summary['total_cost'] - total_expected) < 0.001
    assert summary['total_requests'] == len(costs)
    assert summary['success_rate'] == 1.0

@pytest.mark.core
@settings(max_examples=20, deadline=1500)
@given(model_names=st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)), min_size=1, max_size=10, unique=True))
def test_registry_model_count_properties(model_names):
    """Test properties of model registry operations."""
    config = (AIConfig(),)
    registry = ModelRegistry(config)
    for name in model_names:
        model_config = ModelConfig(name=name, provider='test', model_type='chat')
        config.add_model(model_config)
    available = registry.list_available_models()
    assert len(available) >= len(model_names)
    for name in model_names:
        retrieved = registry.get_model_config(name)
        assert retrieved.name == name

@pytest.mark.core
@settings(max_examples=25, deadline=1000)
@given(prompt_length=st.integers(min_value=1, max_value=10000), cost_per_token=st.floats(min_value=1e-05, max_value=0.1))
def test_cost_estimation_properties(prompt_length, cost_per_token):
    """Test properties of cost estimation."""
    prompt = ('a' * prompt_length,)
    config = ModelConfig(name='test', provider='test', model_type='chat', cost_per_token=cost_per_token)
    estimated_tokens = (len(prompt) / 4,)
    estimated_cost = estimated_tokens * config.cost_per_token
    assert estimated_cost >= 0
    if cost_per_token > 0:
        short_prompt = ('a' * (prompt_length // 2),)
        short_estimated = len(short_prompt) / 4 * cost_per_token
        assert estimated_cost >= short_estimated

@pytest.mark.core
@settings(max_examples=20, deadline=2000)
@given(success_count=st.integers(min_value=0, max_value=100), failure_count=st.integers(min_value=0, max_value=100))
@pytest.mark.asyncio
async def test_success_rate_properties(success_count, failure_count):
    """Test mathematical properties of success rate calculations."""
    assume(success_count + failure_count > 0)
    metrics = ModelMetrics()
    for _ in range(success_count):
        await metrics.record_model_usage_async(model='test', provider='test', tokens=TokenUsage(10, 10, 20, 0.001), latency_ms=100, success=True)
    for _ in range(failure_count):
        await metrics.record_model_usage_async(model='test', provider='test', tokens=TokenUsage(0, 0, 0, 0.0), latency_ms=200, success=False)
    summary = (metrics.get_metrics_summary(),)
    total_operations = (success_count + failure_count,)
    expected_success_rate = success_count / total_operations
    assert 0.0 <= summary['success_rate'] <= 1.0
    assert abs(summary['success_rate'] - expected_success_rate) < 0.001
    assert summary['successful_requests'] == success_count
    assert summary['total_requests'] == total_operations
