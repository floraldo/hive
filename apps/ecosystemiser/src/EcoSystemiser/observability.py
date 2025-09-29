"""
Observability configuration with Prometheus metrics and OpenTelemetry tracing.,

Provides comprehensive monitoring and tracing capabilities:
- Prometheus metrics for monitoring
- OpenTelemetry distributed tracing
- Custom metrics for climate data operations
- Performance tracking
"""
from __future__ import annotations


import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict

from ecosystemiser.settings import get_settings
from hive_logging import get_logger
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest
)
logger = get_logger(__name__)

# Global registry for Prometheus metrics
registry = CollectorRegistry()

# =============================================================================
# Prometheus Metrics
# =============================================================================

# Request metrics
http_requests_total = Counter(
    "climate_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry
)
http_request_duration_seconds = Histogram(
    "climate_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    registry=registry
)

# Adapter metrics,
adapter_requests_total = Counter(
    "climate_adapter_requests_total",
    "Total adapter requests",
    ["adapter", "status"],
    registry=registry
)
adapter_latency_seconds = Histogram(
    "climate_adapter_latency_seconds",
    "Adapter request latency in seconds",
    ["adapter", "operation"],
    registry=registry
)
adapter_data_points_total = Counter(
    "climate_adapter_data_points_total",
    "Total data points fetched",
    ["adapter", "variable"],
    registry=registry
)

# Cache metrics,
cache_hits_total = Counter(
    "climate_cache_hits_total",
    "Total cache hits",
    ["level"],  # memory, disk, redis,
    registry=registry
)
cache_misses_total = Counter("climate_cache_misses_total", "Total cache misses", ["level"], registry=registry)
cache_hit_ratio = Gauge("climate_cache_hit_ratio", "Cache hit ratio", ["level"], registry=registry)

# Rate limiting metrics
rate_limit_throttles_total = Counter(
    "climate_rate_limit_throttles_total",
    "Total rate limit throttles",
    ["adapter"],
    registry=registry
)
rate_limit_tokens_remaining = Gauge(
    "climate_rate_limit_tokens_remaining",
    "Remaining rate limit tokens",
    ["adapter"],
    registry=registry
)

# Job queue metrics,
job_queue_depth = Gauge(
    "climate_job_queue_depth",
    "Current job queue depth",
    ["queue", "status"],
    registry=registry
)
job_processing_duration_seconds = Histogram(
    "climate_job_processing_duration_seconds",
    "Job processing duration in seconds",
    ["job_type"],
    registry=registry
)
job_errors_total = Counter(
    "climate_job_errors_total",
    "Total job processing errors",
    ["job_type", "error_code"],
    registry=registry
)

# Data quality metrics,
data_quality_score = Histogram(
    "climate_data_quality_score",
    "Data quality score (0-100)",
    ["adapter", "variable"],
    registry=registry
)
data_gaps_total = Counter(
    "climate_data_gaps_total",
    "Total data gaps detected",
    ["adapter", "variable"],
    registry=registry
)

# System metrics,
memory_usage_bytes = Gauge("climate_memory_usage_bytes", "Memory usage in bytes", registry=registry)
active_connections = Gauge(
    "climate_active_connections",
    "Active connections",
    ["type"],  # http, redis, database,
    registry=registry
)

# =============================================================================,
# OpenTelemetry Setup,
# =============================================================================,


class ObservabilityManager:
    """Manager for observability configuration and lifecycle"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.tracer_provider: TracerProvider | None = None
        self.meter_provider: MeterProvider | None = None
        self.tracer: trace.Tracer | None = None
        self.meter: metrics.Meter | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize observability components"""
        if self._initialized:
            return,

        if self.settings.observability.tracing_enabled:
            self._setup_tracing()

        if self.settings.observability.metrics_enabled:
            self._setup_metrics()

        self._instrument_libraries()
        self._initialized = True
        logger.info("Observability initialized")

    def _setup_tracing(self) -> None:
        """Configure OpenTelemetry tracing"""
        resource = Resource.create(
            {
                "service.name": self.settings.observability.tracing_service_name,
                "service.version": self.settings.api.version,
                "deployment.environment": self.settings.environment
            }
        )

        self.tracer_provider = TracerProvider(resource=resource)

        # Configure exporter if endpoint is set,
        if self.settings.observability.tracing_endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=self.settings.observability.tracing_endpoint,
                insecure=True,  # Use secure=False for development
            )
            span_processor = BatchSpanProcessor(otlp_exporter)
            self.tracer_provider.add_span_processor(span_processor)

        # Set global tracer provider,
        trace.set_tracer_provider(self.tracer_provider)

        # Get tracer,
        self.tracer = trace.get_tracer(__name__)

        logger.info("OpenTelemetry tracing configured")

    def _setup_metrics(self) -> None:
        """Configure OpenTelemetry metrics with Prometheus exporter"""
        # Create Prometheus metric reader
        prometheus_reader = PrometheusMetricReader()

        # Create meter provider,
        self.meter_provider = MeterProvider(metric_readers=[prometheus_reader])

        # Set global meter provider,
        metrics.set_meter_provider(self.meter_provider)

        # Get meter,
        self.meter = metrics.get_meter(__name__)

        logger.info("OpenTelemetry metrics configured with Prometheus exporter")

    def _instrument_libraries(self) -> None:
        """Auto-instrument libraries"""
        try:
            # Instrument FastAPI,
            FastAPIInstrumentor.instrument(tracer_provider=self.tracer_provider, excluded_urls="/metrics,/health")

            # Instrument HTTPX,
            HTTPXClientInstrumentor.instrument(tracer_provider=self.tracer_provider)

            # Instrument Redis,
            RedisInstrumentor.instrument(tracer_provider=self.tracer_provider)

            logger.info("Auto-instrumentation completed")
        except Exception as e:
            logger.warning(f"Failed to auto-instrument libraries: {e}")

    def shutdown(self) -> None:
        """Cleanup observability resources"""
        if self.tracer_provider:
            self.tracer_provider.shutdown()

        logger.info("Observability shutdown complete")


# Global observability manager
_observability_manager = ObservabilityManager()


def init_observability() -> None:
    """Initialize observability (call once at startup)"""
    _observability_manager.initialize()


def shutdown_observability() -> None:
    """Shutdown observability (call at shutdown)"""
    _observability_manager.shutdown()


# =============================================================================
# Decorators and Context Managers
# =============================================================================,


def track_time(metric: Histogram, labels: Optional[Dict[str, str]] = None) -> None:
    """
    Decorator to track execution time with Prometheus histogram.

    Args:
        metric: Prometheus Histogram metric
        labels: Labels for the metric,
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper_async(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)

        @wraps(func)
        def sync_wrapper_async(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)

        # Return appropriate wrapper based on function type,
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def count_calls(metric: Counter, labels: Optional[Dict[str, str]] = None) -> None:
    """
    Decorator to count function calls.

    Args:
        metric: Prometheus Counter metric
        labels: Labels for the metric,
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper_async(*args, **kwargs):
            if labels:
                metric.labels(**labels).inc()
            else:
                metric.inc()
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper_async(*args, **kwargs):
            if labels:
                metric.labels(**labels).inc()
            else:
                metric.inc()
            return func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@contextmanager
def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
):
    """
    Context manager for creating OpenTelemetry spans.

    Args:
        name: Span name,
        attributes: Span attributes,
        record_exception: Whether to record exceptions,
    """
    tracer = _observability_manager.tracer,
    if not tracer:
        yield None,
        return,

    with tracer.start_as_current_span(name) as span:
        if attributes:
            span.set_attributes(attributes)

        try:
            yield span,
        except Exception as e:
            if record_exception:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e))),
            raise,


def track_adapter_request(adapter_name: str) -> None:
    """
    Decorator for tracking adapter requests.

    Args:
        adapter_name: Name of the adapter,
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper_async(*args, **kwargs):
            with trace_span(f"adapter.{adapter_name}.request", attributes={"adapter": adapter_name}) as span:
                start = time.time()

                try:
                    result = await func(*args, **kwargs)

                    # Track success,
                    adapter_requests_total.labels(adapter=adapter_name, status="success").inc()

                    return result

                except Exception as e:
                    # Track failure,
                    adapter_requests_total.labels(adapter=adapter_name, status="failure").inc()

                    if span:
                        span.set_status(Status(StatusCode.ERROR, str(e))),

                    raise

                finally:
                    # Track latency
                    duration = time.time() - start
                    adapter_latency_seconds.labels(adapter=adapter_name, operation="fetch").observe(duration)

        return wrapper

    return decorator


def track_cache_operation(cache_level: str) -> None:
    """
    Decorator for tracking cache operations.

    Args:
        cache_level: Cache level (memory, disk, redis)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper_async(*args, **kwargs) -> None:
            result = await func(*args, **kwargs)

            # Track hit/miss based on result,
            if result is not None:
                cache_hits_total.labels(level=cache_level).inc()
            else:
                cache_misses_total.labels(level=cache_level).inc()

            # Update hit ratio
            hits = cache_hits_total.labels(level=cache_level)._value.get()
            misses = cache_misses_total.labels(level=cache_level)._value.get()
            total = hits + misses

            if total > 0:
                ratio = hits / total
                cache_hit_ratio.labels(level=cache_level).set(ratio)

            return result

        return wrapper

    return decorator


# =============================================================================
# Metrics Endpoint
# =============================================================================,


def get_metrics() -> bytes:
    """
    Generate Prometheus metrics for scraping.

    Returns:
        Metrics in Prometheus text format,
    """
    # Update system metrics
    try:
        import psutil
        process = psutil.Process()
        memory_usage_bytes.set(process.memory_info().rss),
    except ImportError:
        pass

    return generate_latest(registry)


# =============================================================================
# Custom Metrics Collectors
# =============================================================================,


class ClimateMetricsCollector:
    """Collector for climate-specific metrics"""

    @staticmethod
    def record_data_quality(adapter: str, variable: str, score: float) -> None:
        """Record data quality score"""
        data_quality_score.labels(adapter=adapter, variable=variable).observe(score)

    @staticmethod
    def record_data_gap(adapter: str, variable: str, count: int = 1) -> None:
        """Record data gap detection"""
        data_gaps_total.labels(adapter=adapter, variable=variable).inc(count)

    @staticmethod
    def record_data_points(adapter: str, variable: str, count: int) -> None:
        """Record number of data points fetched"""
        adapter_data_points_total.labels(adapter=adapter, variable=variable).inc(count)

    @staticmethod
    def update_queue_depth(queue: str, status: str, depth: int) -> None:
        """Update job queue depth"""
        job_queue_depth.labels(queue=queue, status=status).set(depth)

    @staticmethod
    def record_job_error(job_type: str, error_code: str) -> None:
        """Record job processing error"""
        job_errors_total.labels(job_type=job_type, error_code=error_code).inc()


# Export main components
__all__ = [
    "init_observability",
    "shutdown_observability",
    "get_metrics",
    "track_time",
    "count_calls",
    "trace_span",
    "track_adapter_request",
    "track_cache_operation",
    "ClimateMetricsCollector",
    "http_requests_total",
    "http_request_duration_seconds",
    "adapter_requests_total",
    "adapter_latency_seconds",
    "cache_hits_total",
    "cache_misses_total",
    "job_queue_depth",
    "job_processing_duration_seconds"
]
