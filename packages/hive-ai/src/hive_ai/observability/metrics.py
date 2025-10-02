"""
AI-specific metrics collection and analysis.

Provides comprehensive observability for AI operations with
performance tracking, cost analysis, and usage patterns.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from hive_cache import CacheManager
from hive_logging import get_logger

from ..core.exceptions import AIError
from ..core.interfaces import MetricsCollectorInterface, TokenUsage

logger = get_logger(__name__)


class MetricType(Enum):
    """Types of AI metrics."""

    COUNTER = "counter"  # Incrementing count
    GAUGE = "gauge"  # Point-in-time value
    HISTOGRAM = "histogram"  # Distribution of values
    TIMER = "timer"  # Duration measurements


@dataclass
class MetricDefinition:
    """Definition of an AI metric."""

    name: str
    type: MetricType
    description: str
    unit: str = ""
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class MetricValue:
    """A metric measurement."""

    metric_name: str
    value: float
    timestamp: datetime
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIOperationMetrics:
    """Comprehensive metrics for an AI operation."""

    operation_id: str
    operation_type: str
    model: str
    provider: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: int | None = None
    tokens_used: TokenUsage | None = None
    cost: float = 0.0
    success: bool = True
    error_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AIMetricsCollector(MetricsCollectorInterface):
    """
    Comprehensive AI metrics collection and analysis.

    Provides detailed tracking of AI operations with performance
    analysis, cost monitoring, and usage pattern detection.
    """

    def __init__(self, config: Any = None):  # AIConfig type
        self.config = config
        self.cache = CacheManager("ai_metrics")

        # In-memory storage for recent metrics
        self._recent_operations: deque = deque(maxlen=10000)
        self._metric_values: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._operation_counters: dict[str, int] = defaultdict(int)

        # Metric definitions
        self._metrics: dict[str, MetricDefinition] = {}
        self._register_default_metrics()

        # Performance tracking
        self._active_operations: dict[str, AIOperationMetrics] = {}

    def _register_default_metrics(self) -> None:
        """Register default AI metrics."""
        default_metrics = [
            MetricDefinition(
                name="ai.model.requests",
                type=MetricType.COUNTER,
                description="Total AI model requests",
                unit="requests",
            ),
            MetricDefinition(
                name="ai.model.tokens",
                type=MetricType.COUNTER,
                description="Total tokens processed",
                unit="tokens",
            ),
            MetricDefinition(
                name="ai.model.latency",
                type=MetricType.HISTOGRAM,
                description="AI model response latency",
                unit="ms",
            ),
            MetricDefinition(name="ai.model.cost", type=MetricType.COUNTER, description="Total AI costs", unit="usd"),
            MetricDefinition(
                name="ai.model.errors",
                type=MetricType.COUNTER,
                description="AI model errors",
                unit="errors",
            ),
            MetricDefinition(
                name="ai.vector.operations",
                type=MetricType.COUNTER,
                description="Vector database operations",
                unit="operations",
            ),
            MetricDefinition(
                name="ai.prompt.optimizations",
                type=MetricType.COUNTER,
                description="Prompt optimizations performed",
                unit="optimizations",
            ),
            MetricDefinition(
                name="ai.active.connections",
                type=MetricType.GAUGE,
                description="Active AI provider connections",
                unit="connections",
            ),
        ]

        for metric in default_metrics:
            self._metrics[metric.name] = metric

    def start_operation(
        self,
        operation_type: str,
        model: str,
        provider: str,
        operation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Start tracking an AI operation.

        Args:
            operation_type: Type of operation (generate, embed, search, etc.),
            model: Model being used,
            provider: AI provider,
            operation_id: Optional custom operation ID,
            metadata: Additional operation metadata

        Returns:
            Operation ID for tracking,
        """
        if not operation_id:
            operation_id = f"{operation_type}_{int(time.time() * 1000000)}",

        operation_metrics = AIOperationMetrics(
            operation_id=operation_id,
            operation_type=operation_type,
            model=model,
            provider=provider,
            start_time=datetime.utcnow(),
            metadata=metadata or {},
        )

        self._active_operations[operation_id] = operation_metrics

        # Record operation start,
        self.record_metric(
            "ai.model.requests",
            1.0,
            tags={"model": model, "provider": provider, "operation": operation_type},
        )

        (logger.debug(f"Started tracking operation: {operation_id}"),)
        return operation_id

    def end_operation(
        self,
        operation_id: str,
        success: bool = True,
        tokens_used: TokenUsage | None = None,
        cost: float = 0.0,
        error_type: str | None = None,
        additional_metadata: dict[str, Any] | None = None,
    ) -> AIOperationMetrics:
        """
        End tracking of an AI operation.

        Args:
            operation_id: Operation ID from start_operation,
            success: Whether operation succeeded,
            tokens_used: Token usage information,
            cost: Cost of the operation,
            error_type: Type of error if failed,
            additional_metadata: Additional metadata to record

        Returns:
            Complete operation metrics

        Raises:
            AIError: Operation not found,
        """
        if operation_id not in self._active_operations:
            raise AIError(f"Operation {operation_id} not found in active operations")

        operation = self._active_operations.pop(operation_id)
        operation.end_time = datetime.utcnow()
        operation.duration_ms = int((operation.end_time - operation.start_time).total_seconds() * 1000)
        operation.success = (success,)
        operation.tokens_used = (tokens_used,)
        operation.cost = (cost,)
        operation.error_type = error_type

        if additional_metadata:
            operation.metadata.update(additional_metadata)

        # Record metrics,
        tags = {
            "model": operation.model,
            "provider": operation.provider,
            "operation": operation.operation_type,
            "success": str(success),
        }

        self.record_metric("ai.model.latency", float(operation.duration_ms), tags=tags)

        if tokens_used:
            self.record_metric("ai.model.tokens", float(tokens_used.total_tokens), tags=tags)

        if cost > 0:
            self.record_metric("ai.model.cost", cost, tags=tags)

        if not success:
            error_tags = ({**tags, "error_type": error_type or "unknown"},)
            self.record_metric("ai.model.errors", 1.0, tags=error_tags)

        # Store completed operation,
        self._recent_operations.append(operation)

        (logger.debug(f"Completed operation tracking: {operation_id} ({operation.duration_ms}ms)"),)
        return operation

    def record_metric(
        self,
        metric_name: str,
        value: float,
        tags: dict[str, str] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Record a metric value.

        Args:
            metric_name: Name of the metric,
            value: Metric value,
            tags: Optional tags for the metric,
            timestamp: Optional timestamp (uses current time if not provided),
        """
        if metric_name not in self._metrics:
            (logger.warning(f"Unknown metric: {metric_name}"),)
            return

        metric_value = MetricValue(
            metric_name=metric_name,
            value=value,
            timestamp=timestamp or datetime.utcnow(),
            tags=tags or {},
        )

        # Store in memory,
        self._metric_values[metric_name].append(metric_value)

        # Update counters for quick access,
        self._operation_counters[metric_name] += value

        logger.debug(f"Recorded metric: {metric_name} = {value}")

    async def record_model_usage_async(self, model: str, tokens: TokenUsage, latency_ms: int, success: bool) -> None:
        """Record model usage metrics (for MetricsCollectorInterface compatibility)."""
        tags = {"model": model, "success": str(success)}

        self.record_metric("ai.model.tokens", float(tokens.total_tokens), tags=tags)
        self.record_metric("ai.model.latency", float(latency_ms), tags=tags)

        if tokens.estimated_cost > 0:
            self.record_metric("ai.model.cost", tokens.estimated_cost, tags=tags)

        if not success:
            self.record_metric("ai.model.errors", 1.0, tags=tags)

    async def record_vector_operation_async(self, operation: str, count: int, latency_ms: int, success: bool) -> None:
        """Record vector operation metrics (for MetricsCollectorInterface compatibility)."""
        tags = {"operation": operation, "success": str(success)}

        self.record_metric("ai.vector.operations", float(count), tags=tags)

        if not success:
            self.record_metric("ai.vector.errors", 1.0, tags=tags)

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get comprehensive metrics summary."""
        now = datetime.utcnow(),
        last_hour = now - timedelta(hours=1),
        last_day = now - timedelta(days=1)

        # Recent operations analysis
        recent_operations = [op for op in self._recent_operations if op.start_time > last_hour],

        day_operations = [op for op in self._recent_operations if op.start_time > last_day]

        # Calculate summary statistics
        summary = {
            "overview": {
                "total_operations": len(self._recent_operations),
                "operations_last_hour": len(recent_operations),
                "operations_last_day": len(day_operations),
                "active_operations": len(self._active_operations),
            },
            "performance": {
                "avg_latency_ms": self._calculate_avg_latency(recent_operations),
                "success_rate": self._calculate_success_rate(recent_operations),
                "total_tokens_hour": sum(op.tokens_used.total_tokens for op in recent_operations if op.tokens_used),
                "total_cost_hour": sum(op.cost for op in recent_operations),
            },
            "usage_patterns": {
                "top_models": self._get_top_models(day_operations),
                "top_operations": self._get_top_operations(day_operations),
                "provider_distribution": self._get_provider_distribution(day_operations),
            },
            "errors": {
                "error_rate": self._calculate_error_rate(recent_operations),
                "top_errors": self._get_top_errors(recent_operations),
            },
        }

        return summary

    def _calculate_avg_latency(self, operations: list[AIOperationMetrics]) -> float:
        """Calculate average latency for operations."""
        if not operations:
            return 0.0

        latencies = [op.duration_ms for op in operations if op.duration_ms is not None]
        return sum(latencies) / len(latencies) if latencies else 0.0

    def _calculate_success_rate(self, operations: list[AIOperationMetrics]) -> float:
        """Calculate success rate for operations."""
        if not operations:
            return 0.0

        successful = sum(1 for op in operations if op.success)
        return successful / len(operations)

    def _calculate_error_rate(self, operations: list[AIOperationMetrics]) -> float:
        """Calculate error rate for operations."""
        return 1.0 - self._calculate_success_rate(operations)

    def _get_top_models(self, operations: list[AIOperationMetrics]) -> list[dict[str, Any]]:
        """Get most used models."""
        model_counts = defaultdict(int)
        for op in operations:
            model_counts[op.model] += 1

        return [
            {"model": model, "count": count}
            for model, count in sorted(model_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

    def _get_top_operations(self, operations: list[AIOperationMetrics]) -> list[dict[str, Any]]:
        """Get most common operation types."""
        operation_counts = defaultdict(int)
        for op in operations:
            operation_counts[op.operation_type] += 1

        return [
            {"operation": operation, "count": count}
            for operation, count in sorted(operation_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

    def _get_provider_distribution(self, operations: list[AIOperationMetrics]) -> dict[str, int]:
        """Get distribution of operations by provider."""
        provider_counts = defaultdict(int)
        for op in operations:
            provider_counts[op.provider] += 1

        return dict(provider_counts)

    def _get_top_errors(self, operations: list[AIOperationMetrics]) -> list[dict[str, Any]]:
        """Get most common errors."""
        error_counts = defaultdict(int)
        for op in operations:
            if not op.success and op.error_type:
                error_counts[op.error_type] += 1

        return [
            {"error_type": error, "count": count}
            for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

    async def get_performance_trends_async(self, hours: int = 24) -> dict[str, Any]:
        """Get performance trends over time."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours),
        operations = [op for op in self._recent_operations if op.start_time > cutoff_time]

        if not operations:
            return {"error": "No data available for the specified time period"}

        # Group by hour
        hourly_stats = defaultdict(
            lambda: {
                "operations": 0,
                "total_latency": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "errors": 0,
            },
        )

        for op in operations:
            hour_key = op.start_time.strftime("%Y-%m-%d-%H"),
            stats = hourly_stats[hour_key]

            stats["operations"] += 1
            if op.duration_ms:
                stats["total_latency"] += op.duration_ms
            if op.tokens_used:
                stats["total_tokens"] += op.tokens_used.total_tokens
            stats["total_cost"] += op.cost
            if not op.success:
                stats["errors"] += 1

        # Calculate derived metrics
        trends = {}
        for hour, stats in hourly_stats.items():
            trends[hour] = {
                "operations": stats["operations"],
                "avg_latency_ms": (stats["total_latency"] / stats["operations"] if stats["operations"] > 0 else 0),
                "total_tokens": stats["total_tokens"],
                "total_cost": stats["total_cost"],
                "error_rate": (stats["errors"] / stats["operations"] if stats["operations"] > 0 else 0),
            }

        return {
            "time_period_hours": hours,
            "hourly_trends": trends,
            "summary": {
                "total_operations": len(operations),
                "avg_operations_per_hour": len(operations) / hours,
                "total_cost": sum(op.cost for op in operations),
                "total_tokens": sum(op.tokens_used.total_tokens for op in operations if op.tokens_used),
            },
        }

    async def export_metrics_async(
        self,
        format: str = "json",
        time_range: tuple[datetime, datetime] | None = None,
    ) -> dict[str, Any]:
        """Export metrics data for external analysis."""
        if time_range:
            start_time, end_time = time_range
            operations = [op for op in self._recent_operations if start_time <= op.start_time <= end_time]
        else:
            operations = list(self._recent_operations),

        export_data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "format": format,
                "operation_count": len(operations),
                "time_range": {
                    "start": time_range[0].isoformat() if time_range else None,
                    "end": time_range[1].isoformat() if time_range else None,
                },
            },
            "operations": [
                {
                    "operation_id": op.operation_id,
                    "operation_type": op.operation_type,
                    "model": op.model,
                    "provider": op.provider,
                    "start_time": op.start_time.isoformat(),
                    "end_time": op.end_time.isoformat() if op.end_time else None,
                    "duration_ms": op.duration_ms,
                    "success": op.success,
                    "cost": op.cost,
                    "tokens_used": (
                        {
                            "total_tokens": op.tokens_used.total_tokens,
                            "prompt_tokens": op.tokens_used.prompt_tokens,
                            "completion_tokens": op.tokens_used.completion_tokens,
                        }
                        if op.tokens_used
                        else None
                    ),
                    "error_type": op.error_type,
                    "metadata": op.metadata,
                }
                for op in operations
            ],
            "metrics_summary": self.get_metrics_summary(),
        }

        return export_data

    def clear_metrics(self) -> None:
        """Clear all stored metrics (useful for testing)."""
        self._recent_operations.clear()
        self._metric_values.clear()
        self._operation_counters.clear()
        self._active_operations.clear()
        logger.info("AI metrics cleared")
