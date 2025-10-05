"""Climate-specific observability metrics for EcoSystemiser.

Provides domain-specific Prometheus metrics for climate data operations:
- Data quality scoring
- Data gap detection
- Adapter data point tracking
- Job queue monitoring

For general observability (timing, tracing, error tracking), use hive-performance decorators:
- @timed() for duration tracking
- @counted() for event counting
- @traced() for distributed tracing
- @track_errors() for error tracking
- @track_adapter_request() for external API calls
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from ecosystemiser.settings import get_settings
from hive_logging import get_logger

logger = get_logger(__name__)

# Global registry for Prometheus metrics
registry = CollectorRegistry()

# =============================================================================
# Domain-Specific Climate Metrics
# =============================================================================

# Data quality metrics
data_quality_score = Histogram(
    "climate_data_quality_score",
    "Data quality score (0-100)",
    ["adapter", "variable"],
    registry=registry,
)
data_gaps_total = Counter(
    "climate_data_gaps_total",
    "Total data gaps detected",
    ["adapter", "variable"],
    registry=registry,
)

# Adapter metrics
adapter_data_points_total = Counter(
    "climate_adapter_data_points_total",
    "Total data points fetched",
    ["adapter", "variable"],
    registry=registry,
)

# Job queue metrics
job_queue_depth = Gauge(
    "climate_job_queue_depth",
    "Current job queue depth",
    ["queue", "status"],
    registry=registry,
)
job_errors_total = Counter(
    "climate_job_errors_total",
    "Total job processing errors",
    ["job_type", "error_code"],
    registry=registry,
)

# System metrics (kept for backwards compatibility)
memory_usage_bytes = Gauge(
    "climate_memory_usage_bytes",
    "Memory usage in bytes",
    registry=registry,
)


# =============================================================================
# Domain Metrics Collector
# =============================================================================


class ClimateMetricsCollector:
    """Collector for climate-specific business metrics.

    These are domain-specific metrics that belong in the application layer,
    not generic observability patterns (which should use hive-performance).
    """

    @staticmethod
    def record_data_quality(adapter: str, variable: str, score: float) -> None:
        """Record data quality score (0-100)."""
        data_quality_score.labels(adapter=adapter, variable=variable).observe(score)

    @staticmethod
    def record_data_gap(adapter: str, variable: str, count: int = 1) -> None:
        """Record data gap detection."""
        data_gaps_total.labels(adapter=adapter, variable=variable).inc(count)

    @staticmethod
    def record_data_points(adapter: str, variable: str, count: int) -> None:
        """Record number of data points fetched."""
        adapter_data_points_total.labels(adapter=adapter, variable=variable).inc(count)

    @staticmethod
    def update_queue_depth(queue: str, status: str, depth: int) -> None:
        """Update job queue depth gauge."""
        job_queue_depth.labels(queue=queue, status=status).set(depth)

    @staticmethod
    def record_job_error(job_type: str, error_code: str) -> None:
        """Record job processing error."""
        job_errors_total.labels(job_type=job_type, error_code=error_code).inc()


# =============================================================================
# Metrics Endpoint
# =============================================================================


def get_metrics() -> bytes:
    """Generate Prometheus metrics for scraping.

    Returns:
        Metrics in Prometheus text format
    """
    # Update system metrics
    try:
        import psutil

        process = psutil.Process()
        memory_usage_bytes.set(process.memory_info().rss)
    except ImportError:
        pass

    return generate_latest(registry)


# =============================================================================
# Lifecycle Management
# =============================================================================


def init_observability() -> None:
    """Initialize observability (called at startup).

    Note: For general observability (timing, tracing, errors), use hive-performance
    decorators on your functions instead of custom implementations.

    Examples:
        from hive_performance import timed, track_adapter_request

        @timed(metric_name="climate.fetch_data.duration")
        @track_adapter_request(adapter="knmi")
        async def fetch_weather_data():
            ...
    """
    settings = get_settings()
    logger.info(
        f"EcoSystemiser observability initialized (env: {settings.environment})",
    )
    logger.info("For timing/tracing, use hive-performance decorators")


def shutdown_observability() -> None:
    """Shutdown observability (called at shutdown)."""
    logger.info("EcoSystemiser observability shutdown complete")


# Export main components
__all__ = [
    "ClimateMetricsCollector",
    "get_metrics",
    "init_observability",
    "shutdown_observability",
    # Domain metrics (for direct access if needed)
    "data_quality_score",
    "data_gaps_total",
    "adapter_data_points_total",
    "job_queue_depth",
    "job_errors_total",
]
