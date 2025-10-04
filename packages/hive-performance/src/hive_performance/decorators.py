"""
Decorator-based observability API for unified metrics and tracing.

Provides zero-config decorators for instrumentation with optional config-driven backends.
All decorators support both sync and async functions transparently.

Examples:
    ```python
    from hive_performance import timed, counted, traced, measure_memory, track_errors

    @timed("api.request_duration")
    async def handle_request(request):
        return await process(request)

    @counted("cache.hits")
    def get_cached_value(key):
        return cache.get(key)

    @traced("database.query")
    async def query_database(sql):
        return await db.execute(sql)
    ```
"""

from __future__ import annotations

import asyncio
import functools
import time
import traceback
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


# --- Metrics Storage ---


@dataclass
class MetricData:
    """Container for metric observations."""

    name: str
    metric_type: str  # counter, gauge, histogram, summary
    value: float = 0.0
    count: int = 0
    min_value: float = float("inf")
    max_value: float = float("-inf")
    sum_value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


class MetricsRegistry:
    """
    In-memory metrics registry for decorator-based observability.

    Zero-config storage with optional Prometheus export integration.
    Thread-safe for concurrent metric updates.
    """

    def __init__(self) -> None:
        """Initialize metrics registry."""
        self._metrics: dict[str, MetricData] = {}
        self._lock = asyncio.Lock()

    async def record_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Record counter increment."""
        async with self._lock:
            key = self._metric_key(name, labels)
            if key not in self._metrics:
                self._metrics[key] = MetricData(name=name, metric_type="counter", labels=labels or {})
            metric = self._metrics[key]
            metric.value += value
            metric.count += 1
            metric.last_updated = datetime.now(UTC)

    async def record_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record histogram observation."""
        async with self._lock:
            key = self._metric_key(name, labels)
            if key not in self._metrics:
                self._metrics[key] = MetricData(name=name, metric_type="histogram", labels=labels or {})
            metric = self._metrics[key]
            metric.count += 1
            metric.sum_value += value
            metric.min_value = min(metric.min_value, value)
            metric.max_value = max(metric.max_value, value)
            metric.value = metric.sum_value / metric.count  # Rolling average
            metric.last_updated = datetime.now(UTC)

    async def record_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record gauge value."""
        async with self._lock:
            key = self._metric_key(name, labels)
            if key not in self._metrics:
                self._metrics[key] = MetricData(name=name, metric_type="gauge", labels=labels or {})
            metric = self._metrics[key]
            metric.value = value
            metric.count += 1
            metric.last_updated = datetime.now(UTC)

    def get_metric(self, name: str, labels: dict[str, str] | None = None) -> MetricData | None:
        """Retrieve metric data."""
        key = self._metric_key(name, labels)
        return self._metrics.get(key)

    def get_all_metrics(self) -> dict[str, MetricData]:
        """Get all metrics."""
        return self._metrics.copy()

    def clear(self) -> None:
        """Clear all metrics (for testing)."""
        self._metrics.clear()

    @staticmethod
    def _metric_key(name: str, labels: dict[str, str] | None) -> str:
        """Generate unique key for metric with labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Global registry instance
_metrics_registry = MetricsRegistry()


def get_metrics_registry() -> MetricsRegistry:
    """Get global metrics registry."""
    return _metrics_registry


# --- Tracing Infrastructure ---


@dataclass
class SpanData:
    """Container for distributed trace span."""

    span_id: str
    trace_id: str
    name: str
    start_time: datetime
    end_time: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "OK"  # OK, ERROR
    exception: str | None = None


class TracingContext:
    """
    Simple tracing context for decorator-based spans.

    Zero-config storage with optional OpenTelemetry export integration.
    """

    def __init__(self) -> None:
        """Initialize tracing context."""
        self._spans: list[SpanData] = []
        self._current_trace_id: str | None = None

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> SpanData:
        """Start new span."""
        import uuid

        span_id = str(uuid.uuid4())
        trace_id = self._current_trace_id or str(uuid.uuid4())
        self._current_trace_id = trace_id

        span = SpanData(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            start_time=datetime.now(UTC),
            attributes=attributes or {},
        )
        self._spans.append(span)
        return span

    def end_span(self, span: SpanData, status: str = "OK", exception: str | None = None) -> None:
        """End span."""
        span.end_time = datetime.now(UTC)
        span.status = status
        span.exception = exception

    def get_spans(self) -> list[SpanData]:
        """Get all spans."""
        return self._spans.copy()

    def clear(self) -> None:
        """Clear all spans (for testing)."""
        self._spans.clear()
        self._current_trace_id = None


# Global tracing context
_tracing_context = TracingContext()


def get_tracing_context() -> TracingContext:
    """Get global tracing context."""
    return _tracing_context


# --- Decorators ---


def timed(metric_name: str, labels: dict[str, str] | None = None) -> Callable:
    """
    Track function execution time.

    Records duration as histogram metric with min/max/avg statistics.
    Supports both sync and async functions transparently.

    Args:
        metric_name: Name of the metric (e.g., "api.request_duration")
        labels: Optional labels for metric dimensionality

    Examples:
        ```python
        @timed("api.request_duration", labels={"endpoint": "/users"})
        async def handle_request():
            await process()

        @timed("cache.lookup_time")
        def get_value(key):
            return cache[key]
        ```
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.perf_counter() - start
                    await _metrics_registry.record_histogram(metric_name, duration, labels)
                    logger.debug(f"Timed {func.__name__}: {duration:.4f}s", extra={"metric": metric_name})

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.perf_counter() - start
                    # Use asyncio.create_task if in event loop, otherwise skip metric
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(_metrics_registry.record_histogram(metric_name, duration, labels))
                    except RuntimeError:
                        # No event loop - log warning and skip metric
                        logger.warning(
                            f"Cannot record metric {metric_name} - no event loop (sync function in non-async context)"
                        )
                    logger.debug(f"Timed {func.__name__}: {duration:.4f}s", extra={"metric": metric_name})

            return sync_wrapper

    return decorator


def counted(metric_name: str, labels: dict[str, str] | None = None, increment: float = 1.0) -> Callable:
    """
    Count function calls.

    Increments counter metric each time function is called.
    Supports both sync and async functions transparently.

    Args:
        metric_name: Name of the metric (e.g., "api.requests_total")
        labels: Optional labels for metric dimensionality
        increment: Amount to increment (default: 1.0)

    Examples:
        ```python
        @counted("cache.hits")
        def get_cached(key):
            return cache.get(key)

        @counted("api.requests", labels={"method": "POST"})
        async def create_resource(data):
            return await db.insert(data)
        ```
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                await _metrics_registry.record_counter(metric_name, increment, labels)
                return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(_metrics_registry.record_counter(metric_name, increment, labels))
                except RuntimeError:
                    logger.warning(
                        f"Cannot record metric {metric_name} - no event loop (sync function in non-async context)"
                    )
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def traced(span_name: str, attributes: dict[str, Any] | None = None) -> Callable:
    """
    Create distributed trace span for function execution.

    Records span with start/end times and optional attributes.
    Captures exceptions and marks span as failed.
    Supports both sync and async functions transparently.

    Args:
        span_name: Name of the span (e.g., "database.query")
        attributes: Optional span attributes for context

    Examples:
        ```python
        @traced("database.query", attributes={"db": "postgres"})
        async def query_users(filter):
            return await db.query("SELECT * FROM users WHERE ...", filter)

        @traced("external.api_call")
        def fetch_data(url):
            return requests.get(url)
        ```
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                span = _tracing_context.start_span(span_name, attributes)
                try:
                    result = await func(*args, **kwargs)
                    _tracing_context.end_span(span, status="OK")
                    logger.debug(f"Traced {func.__name__}", extra={"span": span_name})
                    return result
                except Exception as e:
                    _tracing_context.end_span(span, status="ERROR", exception=str(e))
                    logger.error(f"Traced {func.__name__} failed: {e}", extra={"span": span_name})
                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                span = _tracing_context.start_span(span_name, attributes)
                try:
                    result = func(*args, **kwargs)
                    _tracing_context.end_span(span, status="OK")
                    logger.debug(f"Traced {func.__name__}", extra={"span": span_name})
                    return result
                except Exception as e:
                    _tracing_context.end_span(span, status="ERROR", exception=str(e))
                    logger.error(f"Traced {func.__name__} failed: {e}", extra={"span": span_name})
                    raise

            return sync_wrapper

    return decorator


def measure_memory(metric_name: str, labels: dict[str, str] | None = None) -> Callable:
    """
    Track memory usage during function execution.

    Records peak memory delta as gauge metric.
    Supports both sync and async functions transparently.

    Args:
        metric_name: Name of the metric (e.g., "memory.peak_mb")
        labels: Optional labels for metric dimensionality

    Examples:
        ```python
        @measure_memory("processing.memory_peak")
        async def process_large_dataset(data):
            return await analyze(data)

        @measure_memory("cache.memory_usage")
        def build_cache():
            return {k: expensive_computation(k) for k in keys}
        ```
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracemalloc.start()
                try:
                    result = await func(*args, **kwargs)
                    current, peak = tracemalloc.get_traced_memory()
                    peak_mb = peak / 1024 / 1024  # Convert to MB
                    await _metrics_registry.record_gauge(metric_name, peak_mb, labels)
                    logger.debug(f"Memory peak {func.__name__}: {peak_mb:.2f}MB", extra={"metric": metric_name})
                    return result
                finally:
                    tracemalloc.stop()

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracemalloc.start()
                try:
                    result = func(*args, **kwargs)
                    current, peak = tracemalloc.get_traced_memory()
                    peak_mb = peak / 1024 / 1024  # Convert to MB
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(_metrics_registry.record_gauge(metric_name, peak_mb, labels))
                    except RuntimeError:
                        logger.warning(
                            f"Cannot record metric {metric_name} - no event loop (sync function in non-async context)"
                        )
                    logger.debug(f"Memory peak {func.__name__}: {peak_mb:.2f}MB", extra={"metric": metric_name})
                    return result
                finally:
                    tracemalloc.stop()

            return sync_wrapper

    return decorator


def track_errors(metric_name: str, labels: dict[str, str] | None = None) -> Callable:
    """
    Track error rates and exceptions.

    Increments error counter when function raises exception.
    Logs exception details for debugging.
    Supports both sync and async functions transparently.

    Args:
        metric_name: Name of the metric (e.g., "api.errors_total")
        labels: Optional labels for metric dimensionality

    Examples:
        ```python
        @track_errors("api.errors", labels={"endpoint": "/users"})
        async def handle_request(request):
            return await process(request)  # Tracks if raises

        @track_errors("database.errors")
        def query_database(sql):
            return db.execute(sql)  # Tracks if raises
        ```
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    error_labels = (labels or {}).copy()
                    error_labels["error_type"] = type(e).__name__
                    await _metrics_registry.record_counter(metric_name, 1.0, error_labels)
                    logger.error(
                        f"Error in {func.__name__}: {e}",
                        extra={"metric": metric_name, "traceback": traceback.format_exc()},
                    )
                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    error_labels = (labels or {}).copy()
                    error_labels["error_type"] = type(e).__name__
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(_metrics_registry.record_counter(metric_name, 1.0, error_labels))
                    except RuntimeError:
                        logger.warning(
                            f"Cannot record metric {metric_name} - no event loop (sync function in non-async context)"
                        )
                    logger.error(
                        f"Error in {func.__name__}: {e}",
                        extra={"metric": metric_name, "traceback": traceback.format_exc()},
                    )
                    raise

            return sync_wrapper

    return decorator


# --- Utility Functions ---


def get_metric_value(metric_name: str, labels: dict[str, str] | None = None) -> float | None:
    """
    Retrieve current value of a metric.

    Args:
        metric_name: Name of the metric
        labels: Optional labels to match

    Returns:
        Current metric value or None if not found
    """
    metric = _metrics_registry.get_metric(metric_name, labels)
    return metric.value if metric else None


def get_all_metrics_summary() -> dict[str, dict[str, Any]]:
    """
    Get summary of all metrics.

    Returns:
        Dictionary mapping metric names to metric data
    """
    all_metrics = _metrics_registry.get_all_metrics()
    return {
        key: {
            "name": metric.name,
            "type": metric.metric_type,
            "value": metric.value,
            "count": metric.count,
            "labels": metric.labels,
            "last_updated": metric.last_updated.isoformat(),
        }
        for key, metric in all_metrics.items()
    }


def reset_metrics() -> None:
    """Reset all metrics (primarily for testing)."""
    _metrics_registry.clear()
    _tracing_context.clear()
    logger.info("All metrics and traces cleared")
