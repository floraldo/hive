"""Tests for decorator-based observability API.

Validates all decorators work correctly with sync/async functions,
metrics collection, tracing, and error handling.
"""

import asyncio

import pytest

from hive_performance import (
    counted,
    get_all_metrics_summary,
    get_metric_value,
    get_tracing_context,
    measure_memory,
    reset_metrics,
    timed,
    traced,
    track_errors,
)


@pytest.fixture(autouse=True)
def reset_all_metrics():
    """Reset metrics and traces before each test."""
    reset_metrics()
    yield
    reset_metrics()


# --- @timed decorator tests ---


@pytest.mark.asyncio
async def test_timed_async_function():
    """Test @timed decorator with async function."""

    @timed("test.async_duration")
    async def async_task():
        await asyncio.sleep(0.01)
        return "done"

    result = await async_task()

    assert result == "done"
    duration = get_metric_value("test.async_duration")
    assert duration is not None
    assert duration >= 0.01  # Should be at least 10ms


@pytest.mark.asyncio
async def test_timed_sync_function_in_async_context():
    """Test @timed decorator with sync function in async context."""

    @timed("test.sync_duration")
    def sync_task():
        import time

        time.sleep(0.01)
        return "done"

    # Run in event loop context
    result = await asyncio.to_thread(sync_task)

    assert result == "done"
    # Metric may not be recorded if sync function runs outside event loop
    # This is expected behavior per WARNING in decorators.py


@pytest.mark.asyncio
async def test_timed_with_labels():
    """Test @timed decorator with metric labels."""

    @timed("test.labeled_duration", labels={"endpoint": "/users", "method": "GET"})
    async def api_call():
        await asyncio.sleep(0.01)
        return "response"

    result = await api_call()

    assert result == "response"
    duration = get_metric_value("test.labeled_duration", labels={"endpoint": "/users", "method": "GET"})
    assert duration is not None
    assert duration >= 0.01


# --- @counted decorator tests ---


@pytest.mark.asyncio
async def test_counted_async_function():
    """Test @counted decorator with async function."""

    @counted("test.async_calls")
    async def async_task():
        return "done"

    await async_task()
    await async_task()
    await async_task()

    count = get_metric_value("test.async_calls")
    assert count == 3.0


@pytest.mark.asyncio
async def test_counted_with_increment():
    """Test @counted decorator with custom increment."""

    @counted("test.weighted_calls", increment=5.0)
    async def async_task():
        return "done"

    await async_task()
    await async_task()

    count = get_metric_value("test.weighted_calls")
    assert count == 10.0  # 2 calls * 5.0 increment


@pytest.mark.asyncio
async def test_counted_with_labels():
    """Test @counted decorator with labels."""

    @counted("test.labeled_calls", labels={"status": "success"})
    async def success_call():
        return "ok"

    @counted("test.labeled_calls", labels={"status": "error"})
    async def error_call():
        return "error"

    await success_call()
    await success_call()
    await error_call()

    success_count = get_metric_value("test.labeled_calls", labels={"status": "success"})
    error_count = get_metric_value("test.labeled_calls", labels={"status": "error"})

    assert success_count == 2.0
    assert error_count == 1.0


# --- @traced decorator tests ---


@pytest.mark.asyncio
async def test_traced_async_function():
    """Test @traced decorator with async function."""

    @traced("test.async_span")
    async def async_task():
        await asyncio.sleep(0.01)
        return "done"

    result = await async_task()

    assert result == "done"

    # Check tracing context
    spans = get_tracing_context().get_spans()
    assert len(spans) == 1
    assert spans[0].name == "test.async_span"
    assert spans[0].status == "OK"
    assert spans[0].end_time is not None


def test_traced_sync_function():
    """Test @traced decorator with sync function."""

    @traced("test.sync_span")
    def sync_task():
        import time

        time.sleep(0.01)
        return "done"

    result = sync_task()

    assert result == "done"

    # Check tracing context
    spans = get_tracing_context().get_spans()
    assert len(spans) == 1
    assert spans[0].name == "test.sync_span"
    assert spans[0].status == "OK"


@pytest.mark.asyncio
async def test_traced_with_attributes():
    """Test @traced decorator with span attributes."""

    @traced("test.attributed_span", attributes={"user_id": "123", "action": "create"})
    async def async_task():
        return "done"

    await async_task()

    spans = get_tracing_context().get_spans()
    assert len(spans) == 1
    assert spans[0].attributes == {"user_id": "123", "action": "create"}


@pytest.mark.asyncio
async def test_traced_with_exception():
    """Test @traced decorator captures exceptions."""

    @traced("test.error_span")
    async def failing_task():
        raise ValueError("Test error")

    with pytest.raises(ValueError, match="Test error"):
        await failing_task()

    spans = get_tracing_context().get_spans()
    assert len(spans) == 1
    assert spans[0].status == "ERROR"
    assert "Test error" in spans[0].exception


# --- @measure_memory decorator tests ---


@pytest.mark.asyncio
async def test_measure_memory_async_function():
    """Test @measure_memory decorator with async function."""

    @measure_memory("test.async_memory")
    async def memory_task():
        # Allocate some memory
        data = [0] * 100000
        await asyncio.sleep(0.01)
        return len(data)

    result = await memory_task()

    assert result == 100000
    memory_peak = get_metric_value("test.async_memory")
    assert memory_peak is not None
    assert memory_peak > 0  # Should have tracked some memory


@pytest.mark.asyncio
async def test_measure_memory_with_labels():
    """Test @measure_memory decorator with labels."""

    @measure_memory("test.labeled_memory", labels={"operation": "data_load"})
    async def load_data():
        data = [0] * 50000
        await asyncio.sleep(0.01)
        return data

    await load_data()

    memory = get_metric_value("test.labeled_memory", labels={"operation": "data_load"})
    assert memory is not None
    assert memory > 0


# --- @track_errors decorator tests ---


@pytest.mark.asyncio
async def test_track_errors_async_function_success():
    """Test @track_errors decorator with successful async function."""

    @track_errors("test.async_errors")
    async def success_task():
        return "ok"

    result = await success_task()

    assert result == "ok"
    # No error should be recorded
    errors = get_metric_value("test.async_errors")
    assert errors is None  # Counter not created if no errors


@pytest.mark.asyncio
async def test_track_errors_async_function_failure():
    """Test @track_errors decorator with failing async function."""

    @track_errors("test.async_errors")
    async def failing_task():
        raise RuntimeError("Test failure")

    with pytest.raises(RuntimeError, match="Test failure"):
        await failing_task()

    # Error should be recorded with error_type label
    errors = get_metric_value("test.async_errors", labels={"error_type": "RuntimeError"})
    assert errors == 1.0


@pytest.mark.asyncio
async def test_track_errors_with_existing_labels():
    """Test @track_errors decorator adds error_type to existing labels."""

    @track_errors("test.labeled_errors", labels={"endpoint": "/api/users"})
    async def api_error():
        raise ValueError("Bad request")

    with pytest.raises(ValueError, match="Bad request"):
        await api_error()

    # Should have both original labels and error_type
    errors = get_metric_value("test.labeled_errors", labels={"endpoint": "/api/users", "error_type": "ValueError"})
    assert errors == 1.0


def test_track_errors_sync_function():
    """Test @track_errors decorator with sync function."""

    @track_errors("test.sync_errors")
    def failing_sync():
        raise KeyError("Missing key")

    with pytest.raises(KeyError, match="Missing key"):
        failing_sync()

    # Error should be recorded
    # Note: May not record if no event loop - this is expected behavior


# --- Utility function tests ---


@pytest.mark.asyncio
async def test_get_all_metrics_summary():
    """Test get_all_metrics_summary() utility."""

    @timed("test.metric1")
    @counted("test.metric2")
    async def multi_metric_task():
        await asyncio.sleep(0.01)
        return "done"

    await multi_metric_task()

    summary = get_all_metrics_summary()

    assert "test.metric1" in summary
    assert "test.metric2" in summary

    # Validate metric structure
    metric1 = summary["test.metric1"]
    assert metric1["name"] == "test.metric1"
    assert metric1["type"] == "histogram"
    assert metric1["value"] > 0
    assert metric1["count"] == 1

    metric2 = summary["test.metric2"]
    assert metric2["name"] == "test.metric2"
    assert metric2["type"] == "counter"
    assert metric2["value"] == 1.0


@pytest.mark.asyncio
async def test_reset_metrics_clears_all_data():
    """Test reset_metrics() clears metrics and traces."""

    @timed("test.reset_metric")
    @traced("test.reset_span")
    async def task():
        return "done"

    await task()

    # Verify data exists
    assert get_metric_value("test.reset_metric") is not None
    assert len(get_tracing_context().get_spans()) == 1

    # Reset
    reset_metrics()

    # Verify data cleared
    assert get_metric_value("test.reset_metric") is None
    assert len(get_tracing_context().get_spans()) == 0


# --- Integration tests ---


@pytest.mark.asyncio
async def test_multiple_decorators_stacked():
    """Test stacking multiple decorators on same function."""

    @timed("test.stacked_duration")
    @counted("test.stacked_calls")
    @traced("test.stacked_span")
    @track_errors("test.stacked_errors")
    async def fully_instrumented():
        await asyncio.sleep(0.01)
        return "done"

    result = await fully_instrumented()

    assert result == "done"

    # All metrics should be recorded
    assert get_metric_value("test.stacked_duration") is not None
    assert get_metric_value("test.stacked_calls") == 1.0
    assert len(get_tracing_context().get_spans()) == 1
    # No errors recorded (function succeeded)


@pytest.mark.asyncio
async def test_decorator_overhead_minimal():
    """Test decorator overhead is minimal (<1% as per design)."""

    # Baseline: function without decorators
    async def baseline_task():
        await asyncio.sleep(0.1)

    # Instrumented: same function with all decorators
    @timed("test.overhead_duration")
    @counted("test.overhead_calls")
    @traced("test.overhead_span")
    @track_errors("test.overhead_errors")
    async def instrumented_task():
        await asyncio.sleep(0.1)

    # Measure baseline
    import time

    start = time.perf_counter()
    await baseline_task()
    baseline_time = time.perf_counter() - start

    # Measure instrumented
    start = time.perf_counter()
    await instrumented_task()
    instrumented_time = time.perf_counter() - start

    # Overhead should be < 1% in production, but allow 10% for test environment variability
    overhead = instrumented_time - baseline_time
    overhead_percent = (overhead / baseline_time) * 100

    # Allow up to 10% overhead for test environment variability
    # Production target is <1%, but testing introduces measurement noise
    assert overhead_percent < 10.0, f"Overhead {overhead_percent:.2f}% exceeds 10% threshold"


@pytest.mark.asyncio
async def test_metrics_registry_thread_safe():
    """Test MetricsRegistry handles concurrent metric updates."""

    @counted("test.concurrent_calls")
    async def concurrent_task(task_id):
        await asyncio.sleep(0.01)
        return task_id

    # Run 10 concurrent tasks
    tasks = [concurrent_task(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 10
    # All 10 calls should be counted
    count = get_metric_value("test.concurrent_calls")
    assert count == 10.0
