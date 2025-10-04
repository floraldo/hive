"""
Tests for composite decorator patterns.

Validates that composite decorators correctly combine multiple observability
patterns and generate expected metrics.
"""

import asyncio

import pytest

from hive_performance import (
    get_all_metrics_summary,
    get_metric_value,
    get_tracing_context,
    reset_metrics,
    track_adapter_request,
    track_cache_operation,
    track_request,
)


@pytest.fixture(autouse=True)
def reset_all_metrics():
    """Reset metrics and traces before each test."""
    reset_metrics()
    yield
    reset_metrics()


# --- @track_request decorator tests ---


@pytest.mark.asyncio
async def test_track_request_success():
    """Test @track_request decorator with successful request."""

    @track_request("api.users.get", labels={"endpoint": "/users"})
    async def get_users():
        await asyncio.sleep(0.01)
        return {"users": []}

    result = await get_users()

    assert result == {"users": []}

    # Should generate 3 metrics (duration, calls, no errors on success)
    duration = get_metric_value("api.users.get.duration", labels={"endpoint": "/users"})
    calls = get_metric_value("api.users.get.calls", labels={"endpoint": "/users"})

    assert duration is not None
    assert duration >= 0.01
    assert calls == 1.0

    # Should create trace span
    spans = get_tracing_context().get_spans()
    assert len(spans) == 1
    assert spans[0].name == "api.users.get"
    assert spans[0].status == "OK"


@pytest.mark.asyncio
async def test_track_request_failure():
    """Test @track_request decorator with failing request."""

    @track_request("api.users.create", labels={"endpoint": "/users"})
    async def create_user():
        raise ValueError("Invalid user data")

    with pytest.raises(ValueError, match="Invalid user data"):
        await create_user()

    # Should track error
    errors = get_metric_value("api.users.create.errors", labels={"endpoint": "/users", "error_type": "ValueError"})
    assert errors == 1.0

    # Should still track call
    calls = get_metric_value("api.users.create.calls", labels={"endpoint": "/users"})
    assert calls == 1.0

    # Span should be marked as error
    spans = get_tracing_context().get_spans()
    assert len(spans) == 1
    assert spans[0].status == "ERROR"
    assert "Invalid user data" in spans[0].exception


@pytest.mark.asyncio
async def test_track_request_without_error_tracking():
    """Test @track_request decorator with error tracking disabled."""

    @track_request("api.search", record_errors=False)
    async def search():
        raise RuntimeError("Search failed")

    with pytest.raises(RuntimeError, match="Search failed"):
        await search()

    # Should NOT track error (error tracking disabled)
    errors = get_metric_value("api.search.errors")
    assert errors is None


# --- @track_cache_operation decorator tests ---


@pytest.mark.asyncio
async def test_track_cache_operation_hit():
    """Test @track_cache_operation decorator with cache hit."""

    @track_cache_operation("redis", "get")
    async def get_from_cache(key: str):
        await asyncio.sleep(0.01)
        return "cached_value"  # Non-None = hit

    result = await get_from_cache("test_key")

    assert result == "cached_value"

    # Should track hit
    hits = get_metric_value("cache.redis.hits", labels={"level": "redis"})
    assert hits == 1.0

    # Should NOT track miss
    misses = get_metric_value("cache.redis.misses", labels={"level": "redis"})
    assert misses is None

    # Should track operation metrics
    calls = get_metric_value("cache.redis.get.calls", labels={"level": "redis", "operation": "get"})
    duration = get_metric_value("cache.redis.get.duration", labels={"level": "redis", "operation": "get"})

    assert calls == 1.0
    assert duration is not None
    assert duration >= 0.01


@pytest.mark.asyncio
async def test_track_cache_operation_miss():
    """Test @track_cache_operation decorator with cache miss."""

    @track_cache_operation("memory", "get")
    async def get_from_cache(key: str):
        await asyncio.sleep(0.01)
        return None  # None = miss

    result = await get_from_cache("missing_key")

    assert result is None

    # Should track miss
    misses = get_metric_value("cache.memory.misses", labels={"level": "memory"})
    assert misses == 1.0

    # Should NOT track hit
    hits = get_metric_value("cache.memory.hits", labels={"level": "memory"})
    assert hits is None

    # Should still track operation
    calls = get_metric_value("cache.memory.get.calls", labels={"level": "memory", "operation": "get"})
    assert calls == 1.0


@pytest.mark.asyncio
async def test_track_cache_operation_multiple_operations():
    """Test @track_cache_operation with multiple cache operations."""

    @track_cache_operation("redis", "get")
    async def cache_get(key: str):
        # Simulate: first two hits, then miss
        if key in ["key1", "key2"]:
            return f"value_{key}"
        return None

    # Execute operations
    await cache_get("key1")  # Hit
    await cache_get("key2")  # Hit
    await cache_get("key3")  # Miss

    # Verify hit/miss counts
    hits = get_metric_value("cache.redis.hits", labels={"level": "redis"})
    misses = get_metric_value("cache.redis.misses", labels={"level": "redis"})

    assert hits == 2.0
    assert misses == 1.0

    # Verify total calls
    calls = get_metric_value("cache.redis.get.calls", labels={"level": "redis", "operation": "get"})
    assert calls == 3.0


# --- @track_adapter_request decorator tests ---


@pytest.mark.asyncio
async def test_track_adapter_request_success():
    """Test @track_adapter_request decorator with successful API call."""

    @track_adapter_request("weather_api")
    async def fetch_weather(location: str):
        await asyncio.sleep(0.01)
        return {"temp": 72, "location": location}

    result = await fetch_weather("New York")

    assert result == {"temp": 72, "location": "New York"}

    # Should track success
    calls_success = get_metric_value("adapter.weather_api.calls", labels={"adapter": "weather_api", "status": "success"})
    assert calls_success == 1.0

    # Should NOT track failure
    calls_failure = get_metric_value("adapter.weather_api.calls", labels={"adapter": "weather_api", "status": "failure"})
    assert calls_failure is None

    # Should track duration
    duration = get_metric_value("adapter.weather_api.duration", labels={"adapter": "weather_api"})
    assert duration is not None
    assert duration >= 0.01

    # Should create trace span
    spans = get_tracing_context().get_spans()
    assert len(spans) == 1
    assert spans[0].name == "adapter.weather_api.request"
    assert spans[0].status == "OK"


@pytest.mark.asyncio
async def test_track_adapter_request_failure():
    """Test @track_adapter_request decorator with failing API call."""

    @track_adapter_request("database")
    async def query_database(sql: str):
        raise ConnectionError("Database unreachable")

    with pytest.raises(ConnectionError, match="Database unreachable"):
        await query_database("SELECT * FROM users")

    # Should track failure
    calls_failure = get_metric_value("adapter.database.calls", labels={"adapter": "database", "status": "failure"})
    assert calls_failure == 1.0

    # Should track error with type
    errors = get_metric_value("adapter.database.errors", labels={"adapter": "database", "error_type": "ConnectionError"})
    assert errors == 1.0

    # Span should be marked as error
    spans = get_tracing_context().get_spans()
    assert len(spans) == 1
    assert spans[0].status == "ERROR"
    assert "Database unreachable" in spans[0].exception


@pytest.mark.asyncio
async def test_track_adapter_request_mixed_results():
    """Test @track_adapter_request with both success and failure calls."""

    @track_adapter_request("external_api")
    async def call_api(should_fail: bool):
        await asyncio.sleep(0.01)
        if should_fail:
            raise TimeoutError("API timeout")
        return "success"

    # Execute mixed calls
    result1 = await call_api(False)  # Success
    assert result1 == "success"

    with pytest.raises(TimeoutError):
        await call_api(True)  # Failure

    result2 = await call_api(False)  # Success
    assert result2 == "success"

    # Verify counts
    calls_success = get_metric_value("adapter.external_api.calls", labels={"adapter": "external_api", "status": "success"})
    calls_failure = get_metric_value("adapter.external_api.calls", labels={"adapter": "external_api", "status": "failure"})

    assert calls_success == 2.0
    assert calls_failure == 1.0

    # Verify error tracking
    errors = get_metric_value("adapter.external_api.errors", labels={"adapter": "external_api", "error_type": "TimeoutError"})
    assert errors == 1.0


# --- Integration tests ---


@pytest.mark.asyncio
async def test_composite_decorators_comprehensive_metrics():
    """Test that composite decorators generate comprehensive metrics."""

    @track_request("api.comprehensive", labels={"endpoint": "/test"})
    async def api_endpoint():
        await asyncio.sleep(0.01)
        return "ok"

    @track_cache_operation("redis", "set")
    async def cache_set(value):
        await asyncio.sleep(0.01)
        return value

    @track_adapter_request("service")
    async def service_call():
        await asyncio.sleep(0.01)
        return "response"

    # Execute all operations
    await api_endpoint()
    await cache_set("data")
    await service_call()

    # Get all metrics summary
    summary = get_all_metrics_summary()

    # Should have metrics from all decorators
    assert "api.comprehensive.duration" in [m["name"] for m in summary.values()]
    assert "api.comprehensive.calls" in [m["name"] for m in summary.values()]
    assert "cache.redis.set.calls" in [m["name"] for m in summary.values()]
    assert "adapter.service.duration" in [m["name"] for m in summary.values()]

    # Verify metric types
    duration_metrics = [m for m in summary.values() if "duration" in m["name"]]
    for metric in duration_metrics:
        assert metric["type"] == "histogram"

    call_metrics = [m for m in summary.values() if "calls" in m["name"]]
    for metric in call_metrics:
        assert metric["type"] == "counter"


@pytest.mark.asyncio
async def test_composite_decorator_performance_overhead():
    """Test that composite decorators have minimal overhead."""
    import time

    # Baseline function
    async def baseline():
        await asyncio.sleep(0.1)

    # Instrumented function with track_request (heaviest composite)
    @track_request("api.overhead_test")
    async def instrumented():
        await asyncio.sleep(0.1)

    # Measure baseline
    start = time.perf_counter()
    await baseline()
    baseline_time = time.perf_counter() - start

    # Measure instrumented
    start = time.perf_counter()
    await instrumented()
    instrumented_time = time.perf_counter() - start

    # Overhead should be < 10% (allowing for test environment variability)
    overhead = instrumented_time - baseline_time
    overhead_percent = (overhead / baseline_time) * 100

    assert overhead_percent < 10.0, f"Overhead {overhead_percent:.2f}% exceeds 10% threshold"


@pytest.mark.asyncio
async def test_composite_decorators_thread_safe():
    """Test that composite decorators handle concurrent operations safely."""

    @track_request("api.concurrent")
    async def concurrent_endpoint(task_id: int):
        await asyncio.sleep(0.01)
        return task_id

    # Run 20 concurrent requests
    tasks = [concurrent_endpoint(i) for i in range(20)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 20

    # All calls should be counted
    calls = get_metric_value("api.concurrent.calls")
    assert calls == 20.0

    # Should have 20 spans
    spans = get_tracing_context().get_spans()
    assert len(spans) == 20
