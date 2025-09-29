"""
Metrics collection and analysis for vector database operations.

Provides comprehensive tracking of vector operations, search performance
and usage patterns with integration to AI observability.
"""
from __future__ import annotations


from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

from hive_cache import CacheManager
from hive_logging import get_logger

from ..core.interfaces import MetricsCollectorInterface

logger = get_logger(__name__)


@dataclass
class VectorOperationRecord:
    """Record of individual vector database operation."""

    timestamp: datetime
    operation: str  # store, search, delete, etc.
    count: int  # number of vectors processed
    latency_ms: int
    success: bool
    collection: str | None = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class VectorPerformanceStats:
    """Aggregated performance statistics for vector operations."""

    total_operations: int
    successful_operations: int
    total_vectors_processed: int
    avg_latency_ms: float
    success_rate: float
    operations_per_minute: float
    top_operations: Dict[str, int]


class VectorMetrics(MetricsCollectorInterface):
    """
    Comprehensive metrics collection for vector database operations.

    Tracks operation patterns, performance, and provides analytics
    for optimization and monitoring.
    """

    def __init__(self, cache_ttl: int = 300) -> None:
        self.cache = CacheManager("vector_metrics")
        self.cache_ttl = cache_ttl
        self._recent_operations: deque = deque(maxlen=1000)  # Keep last 1000 operations
        self._operation_counters: Dict[str, int] = defaultdict(int)
        self._hourly_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    async def record_vector_operation_async(
        self,
        operation: str,
        count: int,
        latency_ms: int,
        success: bool,
        collection: str | None = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record vector database operation metrics."""
        timestamp = datetime.utcnow()

        record = VectorOperationRecord(
            timestamp=timestamp,
            operation=operation,
            count=count,
            latency_ms=latency_ms,
            success=success,
            collection=collection,
            metadata=metadata or {}
        )

        # Store in recent operations queue,
        self._recent_operations.append(record)

        # Update operation counters,
        self._operation_counters[operation] += 1,
        if success:
            self._operation_counters[f"{operation}_success"] += 1

        # Update hourly statistics,
        hour_key = timestamp.strftime("%Y-%m-%d-%H")
        self._hourly_stats[hour_key][operation] += count,
        self._hourly_stats[hour_key]["total_operations"] += 1,
        if success:
            self._hourly_stats[hour_key][f"{operation}_success"] += count

        # Invalidate relevant caches,
        self._invalidate_caches(operation)

        logger.debug(
            f"Recorded vector operation: {operation} ",
            f"({count} vectors, {latency_ms}ms, ",
            f"{'success' if success else 'failure'})"
        )

    async def record_model_usage_async(
        self, model: str, tokens: Any, latency_ms: int, success: bool  # TokenUsage type
    ) -> None:
        """Record model usage (for MetricsCollectorInterface compatibility)."""
        # Convert model usage to vector operation for unified tracking,
        await self.record_vector_operation_async(
            operation="embedding_generation",
            count=tokens.total_tokens if hasattr(tokens, "total_tokens") else 1,
            latency_ms=latency_ms,
            success=success,
            metadata={"model": model}
        )

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get real-time metrics summary from in-memory data."""
        if not self._recent_operations:
            return {"total_operations": 0, "successful_operations": 0, "avg_latency_ms": 0.0, "success_rate": 0.0}

        total_ops = len(self._recent_operations)
        successful_ops = sum(1 for r in self._recent_operations if r.success)
        total_latency = sum(r.latency_ms for r in self._recent_operations)
        total_vectors = sum(r.count for r in self._recent_operations)

        return {
            "total_operations": total_ops,
            "successful_operations": successful_ops,
            "total_vectors_processed": total_vectors,
            "avg_latency_ms": total_latency / total_ops if total_ops > 0 else 0.0,
            "success_rate": successful_ops / total_ops if total_ops > 0 else 0.0,
            "time_range": "recent_1000_operations"
        }

    async def get_operation_performance_async(self, operation: str) -> VectorPerformanceStats:
        """Get detailed performance stats for specific operation type."""
        cache_key = f"operation_perf_{operation}"
        cached_stats = self.cache.get(cache_key)

        if cached_stats is not None:
            return VectorPerformanceStats(**cached_stats)

        # Calculate from recent operations
        operation_records = [r for r in self._recent_operations if r.operation == operation]

        if not operation_records:
            return VectorPerformanceStats(0, 0, 0, 0.0, 0.0, 0.0, {})

        total_operations = len(operation_records)
        successful_operations = sum(1 for r in operation_records if r.success)
        total_vectors = sum(r.count for r in operation_records)
        avg_latency = sum(r.latency_ms for r in operation_records) / total_operations

        # Calculate operations per minute
        if operation_records:
            time_span = (operation_records[-1].timestamp - operation_records[0].timestamp).total_seconds()
            ops_per_minute = (total_operations / (time_span / 60)) if time_span > 0 else 0.0
        else:
            ops_per_minute = 0.0

        # Get top operations for context
        top_operations = dict(sorted(self._operation_counters.items(), key=lambda x: x[1], reverse=True)[:5])

        stats = VectorPerformanceStats(
            total_operations=total_operations,
            successful_operations=successful_operations,
            total_vectors_processed=total_vectors,
            avg_latency_ms=avg_latency,
            success_rate=successful_operations / total_operations if total_operations > 0 else 0.0,
            operations_per_minute=ops_per_minute,
            top_operations=top_operations
        )

        # Cache for 2 minutes,
        self.cache.set(cache_key, asdict(stats), ttl=120)
        return stats

    async def get_performance_trends_async(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over specified time period."""
        cache_key = f"trends_{hours}h",
        cached_trends = self.cache.get(cache_key)

        if cached_trends is not None:
            return cached_trends

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_records = [r for r in self._recent_operations if r.timestamp > cutoff_time]

        if not recent_records:
            return {"error": "No data available for the specified time period"}

        # Group by operation type,
        operation_trends = defaultdict(list)
        hourly_trends = defaultdict(lambda: defaultdict(int))

        for record in recent_records:
            operation_trends[record.operation].append(
                {
                    "timestamp": record.timestamp.isoformat(),
                    "latency_ms": record.latency_ms,
                    "count": record.count,
                    "success": record.success
                }
            )

            # Hourly aggregation
            hour_key = record.timestamp.strftime("%Y-%m-%d-%H")
            hourly_trends[hour_key]["total_ops"] += 1
            hourly_trends[hour_key]["total_vectors"] += record.count
            if record.success:
                hourly_trends[hour_key]["successful_ops"] += 1

        # Calculate trend statistics
        trends = {
            "time_period_hours": hours,
            "total_records": len(recent_records)
            "operation_breakdown": dict(operation_trends),
            "hourly_summary": dict(hourly_trends)
            "performance_summary": {
                "avg_latency_ms": sum(r.latency_ms for r in recent_records) / len(recent_records)
                "success_rate": sum(1 for r in recent_records if r.success) / len(recent_records),
                "total_vectors": sum(r.count for r in recent_records)
            }
        }

        # Cache for 5 minutes
        self.cache.set(cache_key, trends, ttl=300)
        return trends

    async def get_collection_metrics_async(self, collection: str) -> Dict[str, Any]:
        """Get metrics specific to a collection."""
        collection_records = [r for r in self._recent_operations if r.collection == collection]

        if not collection_records:
            return {
                "collection": collection,
                "operations": 0,
                "vectors_processed": 0,
                "error": "No operations found for this collection"
            }

        # Calculate collection-specific metrics
        operation_counts = defaultdict(int)
        total_vectors = 0
        total_latency = 0
        successful_ops = 0

        for record in collection_records:
            operation_counts[record.operation] += 1
            total_vectors += record.count
            total_latency += record.latency_ms
            if record.success:
                successful_ops += 1

        return {
            "collection": collection,
            "total_operations": len(collection_records)
            "successful_operations": successful_ops,
            "total_vectors_processed": total_vectors,
            "avg_latency_ms": total_latency / len(collection_records),
            "success_rate": successful_ops / len(collection_records)
            "operation_breakdown": dict(operation_counts),
            "time_range": "recent_operations"
        }

    async def get_top_slow_operations_async(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slowest operations for performance analysis."""
        # Sort by latency in descending order
        slow_operations = sorted(self._recent_operations, key=lambda r: r.latency_ms, reverse=True)[:limit]

        return [
            {
                "timestamp": record.timestamp.isoformat(),
                "operation": record.operation,
                "latency_ms": record.latency_ms,
                "count": record.count,
                "success": record.success,
                "collection": record.collection,
                "metadata": record.metadata
            }
            for record in slow_operations
        ]

    async def get_error_analysis_async(self) -> Dict[str, Any]:
        """Analyze failed operations for troubleshooting."""
        failed_operations = [r for r in self._recent_operations if not r.success]

        if not failed_operations:
            return {"total_failures": 0, "failure_rate": 0.0, "error_patterns": {}}

        # Analyze error patterns
        error_by_operation = defaultdict(int)
        error_by_collection = defaultdict(int)
        recent_failures = []

        for record in failed_operations:
            error_by_operation[record.operation] += 1
            if record.collection:
                error_by_collection[record.collection] += 1

            recent_failures.append(
                {
                    "timestamp": record.timestamp.isoformat(),
                    "operation": record.operation,
                    "collection": record.collection,
                    "latency_ms": record.latency_ms,
                    "metadata": record.metadata
                }
            )

        total_operations = len(self._recent_operations)
        failure_rate = len(failed_operations) / total_operations if total_operations > 0 else 0.0

        return {
            "total_failures": len(failed_operations),
            "failure_rate": failure_rate,
            "errors_by_operation": dict(error_by_operation),
            "errors_by_collection": dict(error_by_collection)
            "recent_failures": recent_failures[-10:],  # Last 10 failures,
            "recommendations": self._generate_error_recommendations(error_by_operation)
        }

    def _generate_error_recommendations(self, error_by_operation: Dict[str, int]) -> List[str]:
        """Generate recommendations based on error patterns."""
        recommendations = []

        if error_by_operation.get("search", 0) > 5:
            recommendations.append("High search failures - check vector dimensions and query format")

        if error_by_operation.get("store", 0) > 3:
            recommendations.append("Store operation failures - verify connection and vector format")

        if error_by_operation.get("delete", 0) > 2:
            recommendations.append("Delete failures - check document ID format and existence")

        if sum(error_by_operation.values()) > 10:
            recommendations.append("High overall failure rate - consider circuit breaker implementation")

        return recommendations

    def _invalidate_caches(self, operation: str) -> None:
        """Invalidate relevant caches after new operation data."""
        # Invalidate operation-specific caches
        self.cache.delete(f"operation_perf_{operation}")

        # Invalidate trend caches
        for hours in [1, 6, 24]:
            self.cache.delete(f"trends_{hours}h")

    async def reset_metrics_async(self) -> bool:
        """Reset all metrics (useful for testing)."""
        try:
            self._recent_operations.clear()
            self._operation_counters.clear()
            self._hourly_stats.clear()
            self.cache.clear()

            logger.info("Vector metrics reset")
            return True

        except Exception as e:
            logger.error(f"Failed to reset metrics: {e}")
            return False
