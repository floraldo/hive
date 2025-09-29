"""
Metrics collection and analysis for AI model operations.

Provides comprehensive tracking of usage, costs, performance
and trends with integration to the Hive observability stack.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict

from hive_cache import CacheManager
from hive_db import AsyncSession, get_async_session
from hive_logging import get_logger

from ..core.interfaces import MetricsCollectorInterface, TokenUsage

logger = get_logger(__name__)


@dataclass
class ModelUsageRecord:
    """Record of individual model usage."""

    timestamp: datetime
    model: str
    provider: str
    tokens: TokenUsage
    latency_ms: int
    success: bool
    cost: float


@dataclass
class ModelPerformanceStats:
    """Aggregated performance statistics for a model."""

    total_requests: int
    successful_requests: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float
    success_rate: float
    requests_per_hour: float


class ModelMetrics(MetricsCollectorInterface):
    """
    Comprehensive metrics collection for AI model operations.

    Tracks usage patterns, costs, performance, and provides
    analytics for optimization and cost management.
    """

    def __init__(self, cache_ttl: int = 300) -> None:
        self.cache = CacheManager("model_metrics")
        self.cache_ttl = cache_ttl
        self._recent_usage: deque = deque(maxlen=1000)  # Keep last 1000 operations
        self._hourly_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    async def record_model_usage_async(
        self,
        model: str,
        provider: str,
        tokens: TokenUsage,
        latency_ms: int,
        success: bool,
    ) -> None:
        """Record individual model usage event."""
        timestamp = datetime.utcnow()
        cost = tokens.estimated_cost

        record = ModelUsageRecord(
            timestamp=timestamp,
            model=model,
            provider=provider,
            tokens=tokens,
            latency_ms=latency_ms,
            success=success,
            cost=cost,
        )

        # Store in recent usage queue
        self._recent_usage.append(record)

        # Update hourly statistics
        hour_key = timestamp.strftime("%Y-%m-%d-%H")
        self._hourly_stats[hour_key]["requests"] += 1
        self._hourly_stats[hour_key]["tokens"] += tokens.total_tokens
        self._hourly_stats[hour_key]["cost"] += cost
        if success:
            self._hourly_stats[hour_key]["successful"] += 1

        # Persist to database if available
        try:
            async with get_async_session() as session:
                await self._persist_usage_record_async(session, record)
        except Exception as e:
            logger.warning(f"Failed to persist metrics to database: {e}")

        # Invalidate relevant caches
        self._invalidate_caches()

        logger.debug(
            f"Recorded usage: {model} ",
            f"({tokens.total_tokens} tokens, {latency_ms}ms, " f"${cost:.4f}, {'success' if success else 'failure'})",
        )

    async def record_vector_operation_async(self, operation: str, count: int, latency_ms: int, success: bool) -> None:
        """Record vector database operation metrics."""
        # Implementation for vector operations metrics
        timestamp = datetime.utcnow()
        hour_key = timestamp.strftime("%Y-%m-%d-%H")

        self._hourly_stats[hour_key][f"vector_{operation}"] += count
        if success:
            self._hourly_stats[hour_key][f"vector_{operation}_success"] += count

        logger.debug(f"Recorded vector operation: {operation} ({count} items, {latency_ms}ms)")

    async def get_daily_cost_async(self, date: datetime | None = None) -> float:
        """Get total cost for specific date (default: today)."""
        target_date = date or datetime.utcnow()
        cache_key = f"daily_cost_{target_date.strftime('%Y-%m-%d')}"

        cached_cost = self.cache.get(cache_key)
        if cached_cost is not None:
            return cached_cost

        # Calculate from recent usage first (fast path)
        total_cost = 0.0
        target_date_str = target_date.strftime("%Y-%m-%d")

        for record in self._recent_usage:
            if record.timestamp.strftime("%Y-%m-%d") == target_date_str:
                total_cost += record.cost

        # If we need more history, query database
        if len(self._recent_usage) < 1000:  # May not have full day
            try:
                async with get_async_session() as session:
                    db_cost = await self._get_daily_cost_from_db_async(session, target_date)
                    total_cost = max(total_cost, db_cost)  # Use higher value
            except Exception as e:
                logger.warning(f"Failed to get daily cost from database: {e}")

        # Cache for 5 minutes
        self.cache.set(cache_key, total_cost, ttl=self.cache_ttl)
        return total_cost

    async def get_monthly_cost_async(self, year: int, month: int) -> float:
        """Get total cost for specific month."""
        cache_key = f"monthly_cost_{year}_{month:02d}"

        cached_cost = self.cache.get(cache_key)
        if cached_cost is not None:
            return cached_cost

        # Calculate from recent usage
        total_cost = 0.0
        for record in self._recent_usage:
            if record.timestamp.year == year and record.timestamp.month == month:
                total_cost += record.cost

        # Query database for complete data
        try:
            async with get_async_session() as session:
                db_cost = await self._get_monthly_cost_from_db_async(session, year, month)
                total_cost = max(total_cost, db_cost)
        except Exception as e:
            logger.warning(f"Failed to get monthly cost from database: {e}")

        # Cache for 1 hour
        self.cache.set(cache_key, total_cost, ttl=3600)
        return total_cost

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get real-time metrics summary from in-memory data."""
        if not self._recent_usage:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "total_cost": 0.0,
                "avg_latency_ms": 0.0,
                "success_rate": 0.0,
            }

        total_requests = len(self._recent_usage)
        successful_requests = sum(1 for r in self._recent_usage if r.success)
        total_cost = sum(r.cost for r in self._recent_usage)
        total_latency = sum(r.latency_ms for r in self._recent_usage)

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "total_cost": total_cost,
            "avg_latency_ms": total_latency / total_requests if total_requests > 0 else 0.0,
            "success_rate": successful_requests / total_requests if total_requests > 0 else 0.0,
            "time_range": "recent_1000_operations",
        }

    async def get_model_performance_async(self, model: str) -> ModelPerformanceStats:
        """Get detailed performance stats for specific model."""
        cache_key = f"model_perf_{model}"
        cached_stats = self.cache.get(cache_key)

        if cached_stats is not None:
            return ModelPerformanceStats(**cached_stats)

        # Calculate from recent usage
        model_records = [r for r in self._recent_usage if r.model == model]

        if not model_records:
            return ModelPerformanceStats(0, 0, 0, 0.0, 0.0, 0.0, 0.0)

        total_requests = len(model_records)
        successful_requests = sum(1 for r in model_records if r.success)
        total_tokens = sum(r.tokens.total_tokens for r in model_records)
        total_cost = sum(r.cost for r in model_records)
        avg_latency = sum(r.latency_ms for r in model_records) / total_requests

        # Calculate requests per hour
        if model_records:
            time_span = (model_records[-1].timestamp - model_records[0].timestamp).total_seconds()
            requests_per_hour = (total_requests / (time_span / 3600)) if time_span > 0 else 0.0
        else:
            requests_per_hour = 0.0

        stats = ModelPerformanceStats(
            total_requests=total_requests,
            successful_requests=successful_requests,
            total_tokens=total_tokens,
            total_cost=total_cost,
            avg_latency_ms=avg_latency,
            success_rate=successful_requests / total_requests if total_requests > 0 else 0.0,
            requests_per_hour=requests_per_hour,
        )

        # Cache for 2 minutes
        self.cache.set(cache_key, asdict(stats), ttl=120)
        return stats

    async def get_usage_summary_async(self) -> Dict[str, Any]:
        """Get comprehensive usage summary."""
        now = datetime.utcnow()
        today_cost = await self.get_daily_cost_async()
        current_month_cost = await self.get_monthly_cost_async(now.year, now.month)

        # Model breakdown
        model_usage = defaultdict(int)
        provider_usage = defaultdict(int)

        for record in self._recent_usage:
            model_usage[record.model] += 1
            provider_usage[record.provider] += 1

        # Recent performance trends
        recent_24h = [r for r in self._recent_usage if r.timestamp > now - timedelta(hours=24)]

        return {
            "costs": {"today": today_cost, "current_month": current_month_cost},
            "usage_last_24h": {
                "total_requests": len(recent_24h),
                "successful_requests": sum(1 for r in recent_24h if r.success),
                "total_tokens": sum(r.tokens.total_tokens for r in recent_24h),
                "avg_latency_ms": (sum(r.latency_ms for r in recent_24h) / len(recent_24h) if recent_24h else 0.0),
            },
            "model_distribution": dict(model_usage),
            "provider_distribution": dict(provider_usage),
            "hourly_stats": dict(self._hourly_stats),
        }

    def _invalidate_caches(self) -> None:
        """Invalidate relevant caches after new data."""
        # Invalidate daily cost cache for today
        today = datetime.utcnow().strftime("%Y-%m-%d")
        self.cache.delete(f"daily_cost_{today}")

        # Invalidate monthly cost cache for current month
        now = datetime.utcnow()
        self.cache.delete(f"monthly_cost_{now.year}_{now.month:02d}")

    async def _persist_usage_record_async(self, session: AsyncSession, record: ModelUsageRecord) -> None:
        """Persist usage record to database."""
        # Implementation would depend on specific database schema
        # This is a placeholder for the actual database persistence
        pass

    async def _get_daily_cost_from_db_async(self, session: AsyncSession, date: datetime) -> float:
        """Get daily cost from database."""
        # Implementation would query the database for daily cost
        # This is a placeholder for the actual database query
        return 0.0

    async def _get_monthly_cost_from_db_async(self, session: AsyncSession, year: int, month: int) -> float:
        """Get monthly cost from database."""
        # Implementation would query the database for monthly cost
        # This is a placeholder for the actual database query
        return 0.0
