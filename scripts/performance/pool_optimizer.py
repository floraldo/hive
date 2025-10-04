"""Connection Pool Optimizer

Analyzes connection pool utilization metrics and provides data-driven
tuning recommendations for optimal pool sizing.
"""

import asyncio
import json
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class PoolMetrics:
    """Metrics captured from a connection pool at a point in time."""

    timestamp: datetime
    pool_name: str

    # Pool sizing
    pool_size: int
    in_use: int
    min_size: int
    max_size: int

    # Usage patterns
    utilization_pct: float  # in_use / max_size
    available_pct: float  # pool_size / max_size

    # Performance
    acquisition_time_ms: float | None = None
    slow_acquisitions: int = 0

    # Lifecycle
    connections_created: int = 0
    connections_reused: int = 0
    connections_closed: int = 0
    errors: int = 0


@dataclass
class OptimizationRecommendation:
    """A single pool optimization recommendation."""

    pool_name: str
    severity: str  # "critical", "warning", "info"
    category: str  # "sizing", "performance", "efficiency"
    issue: str
    recommendation: str
    current_value: Any
    recommended_value: Any
    expected_improvement: str


class PoolOptimizer:
    """Analyzes connection pool metrics and recommends optimal configurations.

    Collects metrics over time and applies heuristics to identify:
    - Undersized pools (high utilization, slow acquisitions)
    - Oversized pools (low utilization, waste)
    - Inefficient configurations (churn, errors)
    """

    def __init__(self, collection_interval: float = 5.0):
        """Initialize pool optimizer.

        Args:
            collection_interval: Seconds between metric collections

        """
        self.collection_interval = collection_interval
        self.metrics_history: list[PoolMetrics] = []
        self._collecting = False

    async def collect_metrics_async(self, get_pool_stats_func, duration: timedelta = timedelta(minutes=5)) -> None:
        """Collect pool metrics over a period of time.

        Args:
            get_pool_stats_func: Async function that returns pool statistics dict
            duration: How long to collect metrics

        """
        logger.info(f"Starting metric collection for {duration}")

        self._collecting = True
        end_time = datetime.now() + duration

        try:
            while datetime.now() < end_time and self._collecting:
                try:
                    # Get current pool stats
                    stats = await get_pool_stats_func()

                    # Convert to PoolMetrics objects
                    for pool_name, pool_stats in stats.items():
                        metrics = self._stats_to_metrics(pool_name, pool_stats)
                        self.metrics_history.append(metrics)

                    await asyncio.sleep(self.collection_interval)

                except Exception as e:
                    logger.error(f"Error collecting pool metrics: {e}")
                    await asyncio.sleep(self.collection_interval)

        finally:
            self._collecting = False
            logger.info(f"Metric collection complete: {len(self.metrics_history)} data points")

    def _stats_to_metrics(self, pool_name: str, stats: dict[str, Any]) -> PoolMetrics:
        """Convert raw pool stats to PoolMetrics."""
        in_use = stats.get("in_use", 0)
        pool_size = stats.get("pool_size", 0)
        max_size = stats.get("max_size", 20)

        return PoolMetrics(
            timestamp=datetime.now(),
            pool_name=pool_name,
            pool_size=pool_size,
            in_use=in_use,
            min_size=stats.get("min_size", 5),
            max_size=max_size,
            utilization_pct=in_use / max_size if max_size > 0 else 0.0,
            available_pct=pool_size / max_size if max_size > 0 else 0.0,
            acquisition_time_ms=stats.get("acquisition_time_ms"),
            slow_acquisitions=stats.get("slow_acquisitions", 0),
            connections_created=stats.get("connections_created", 0),
            connections_reused=stats.get("connections_reused", 0),
            connections_closed=stats.get("connections_closed", 0),
            errors=stats.get("errors", 0),
        )

    def analyze_pools(self) -> dict[str, list[OptimizationRecommendation]]:
        """Analyze collected metrics and generate recommendations.

        Returns:
            Dict mapping pool names to lists of recommendations

        """
        if not self.metrics_history:
            logger.warning("No metrics collected, cannot analyze")
            return {}

        # Group metrics by pool
        pools: dict[str, list[PoolMetrics]] = {}
        for metric in self.metrics_history:
            if metric.pool_name not in pools:
                pools[metric.pool_name] = []
            pools[metric.pool_name].append(metric)

        # Analyze each pool
        recommendations = {}
        for pool_name, metrics in pools.items():
            recommendations[pool_name] = self._analyze_single_pool(pool_name, metrics)

        return recommendations

    def _analyze_single_pool(self, pool_name: str, metrics: list[PoolMetrics]) -> list[OptimizationRecommendation]:
        """Analyze metrics for a single pool."""
        recommendations = []

        # Calculate statistics
        utilizations = [m.utilization_pct for m in metrics]
        avg_utilization = statistics.mean(utilizations)
        peak_utilization = max(utilizations)

        in_use_counts = [m.in_use for m in metrics]
        avg_in_use = statistics.mean(in_use_counts)
        peak_in_use = max(in_use_counts)

        # Pool sizing analysis
        current_max = metrics[0].max_size
        current_min = metrics[0].min_size

        # Undersized pool detection
        if peak_utilization > 0.9:  # >90% utilization at peak
            recommendations.append(
                OptimizationRecommendation(
                    pool_name=pool_name,
                    severity="critical" if peak_utilization > 0.95 else "warning",
                    category="sizing",
                    issue=f"Pool frequently near capacity ({peak_utilization * 100:.1f}% peak utilization)",
                    recommendation="Increase max_size to handle peak load with headroom",
                    current_value=current_max,
                    recommended_value=int(peak_in_use * 1.5),  # 50% headroom
                    expected_improvement="Reduced acquisition times, better response under load",
                ),
            )

        # Oversized pool detection
        if avg_utilization < 0.2 and current_max > 5:  # <20% avg utilization
            recommendations.append(
                OptimizationRecommendation(
                    pool_name=pool_name,
                    severity="info",
                    category="efficiency",
                    issue=f"Pool underutilized ({avg_utilization * 100:.1f}% average utilization)",
                    recommendation="Reduce max_size to conserve resources",
                    current_value=current_max,
                    recommended_value=max(int(peak_in_use * 1.3), current_min),  # 30% headroom
                    expected_improvement="Reduced memory footprint, lower maintenance overhead",
                ),
            )

        # Min size optimization
        if avg_in_use > current_min * 1.5:  # Avg usage well above min
            recommendations.append(
                OptimizationRecommendation(
                    pool_name=pool_name,
                    severity="warning",
                    category="sizing",
                    issue=f"Minimum pool size too low ({current_min} vs {avg_in_use:.1f} avg usage)",
                    recommendation="Increase min_size to maintain warm connections",
                    current_value=current_min,
                    recommended_value=int(avg_in_use * 0.8),  # Just below average
                    expected_improvement="Faster connection acquisition, reduced creation overhead",
                ),
            )

        elif avg_in_use < current_min * 0.5 and current_min > 2:  # Min too high
            recommendations.append(
                OptimizationRecommendation(
                    pool_name=pool_name,
                    severity="info",
                    category="efficiency",
                    issue=f"Minimum pool size too high ({current_min} vs {avg_in_use:.1f} avg usage)",
                    recommendation="Reduce min_size to avoid idle connections",
                    current_value=current_min,
                    recommended_value=max(int(avg_in_use * 1.2), 2),  # 20% above avg, min 2
                    expected_improvement="Reduced idle connection overhead",
                ),
            )

        # Acquisition time analysis
        acquisition_times = [m.acquisition_time_ms for m in metrics if m.acquisition_time_ms is not None]
        if acquisition_times:
            avg_acquisition_ms = statistics.mean(acquisition_times)
            p95_acquisition_ms = (
                statistics.quantiles(acquisition_times, n=20)[18]
                if len(acquisition_times) >= 20
                else avg_acquisition_ms
            )

            if p95_acquisition_ms > 100:  # >100ms p95
                recommendations.append(
                    OptimizationRecommendation(
                        pool_name=pool_name,
                        severity="warning" if p95_acquisition_ms > 200 else "info",
                        category="performance",
                        issue=f"Slow connection acquisitions (p95: {p95_acquisition_ms:.1f}ms)",
                        recommendation="Increase pool size or optimize connection creation",
                        current_value=f"{avg_acquisition_ms:.1f}ms avg",
                        recommended_value="<50ms p95",
                        expected_improvement="Faster request response times",
                    ),
                )

        # Churn analysis
        if metrics[-1].connections_created > 0:
            reuse_rate = metrics[-1].connections_reused / (
                metrics[-1].connections_created + metrics[-1].connections_reused
            )

            if reuse_rate < 0.8:  # <80% reuse rate
                recommendations.append(
                    OptimizationRecommendation(
                        pool_name=pool_name,
                        severity="warning",
                        category="efficiency",
                        issue=f"High connection churn ({reuse_rate * 100:.1f}% reuse rate)",
                        recommendation="Increase min_size and/or max_idle_time",
                        current_value=f"{reuse_rate * 100:.1f}% reuse",
                        recommended_value=">90% reuse",
                        expected_improvement="Reduced overhead from connection creation",
                    ),
                )

        # Error analysis
        if metrics[-1].errors > 0:
            error_rate = metrics[-1].errors / (metrics[-1].connections_created + metrics[-1].connections_reused)

            if error_rate > 0.01:  # >1% error rate
                recommendations.append(
                    OptimizationRecommendation(
                        pool_name=pool_name,
                        severity="critical" if error_rate > 0.05 else "warning",
                        category="performance",
                        issue=f"High error rate ({error_rate * 100:.1f}%)",
                        recommendation="Investigate connection errors, may need timeout adjustments",
                        current_value=f"{metrics[-1].errors} errors",
                        recommended_value="<0.5% error rate",
                        expected_improvement="Increased reliability",
                    ),
                )

        return recommendations

    def export_report(self, recommendations: dict[str, list[OptimizationRecommendation]], format: str = "text") -> str:
        """Export optimization report."""
        if format == "json":
            return json.dumps(
                {
                    "analysis_time": datetime.now().isoformat(),
                    "metrics_collected": len(self.metrics_history),
                    "pools_analyzed": len(recommendations),
                    "recommendations": {pool: [asdict(rec) for rec in recs] for pool, recs in recommendations.items()},
                },
                indent=2,
            )

        if format == "text":
            lines = [
                "=== Connection Pool Optimization Report ===",
                f"Analysis Time: {datetime.now().isoformat()}",
                f"Metrics Collected: {len(self.metrics_history)} data points",
                f"Pools Analyzed: {len(recommendations)}",
                "",
            ]

            for pool_name, recs in recommendations.items():
                lines.append(f"\n## Pool: {pool_name}")

                if not recs:
                    lines.append("✅ No optimization recommendations - pool is well-configured")
                    continue

                # Group by severity
                critical = [r for r in recs if r.severity == "critical"]
                warnings = [r for r in recs if r.severity == "warning"]
                info = [r for r in recs if r.severity == "info"]

                if critical:
                    lines.append("\n❌ CRITICAL Issues:")
                    for rec in critical:
                        lines.append(f"  • {rec.issue}")
                        lines.append(f"    → {rec.recommendation}")
                        lines.append(f"    Current: {rec.current_value} | Recommended: {rec.recommended_value}")

                if warnings:
                    lines.append("\n⚠️ Warnings:")
                    for rec in warnings:
                        lines.append(f"  • {rec.issue}")
                        lines.append(f"    → {rec.recommendation}")
                        lines.append(f"    Current: {rec.current_value} | Recommended: {rec.recommended_value}")

                if info:
                    lines.append("\nℹ️ Optimization Opportunities:")
                    for rec in info:
                        lines.append(f"  • {rec.issue}")
                        lines.append(f"    → {rec.recommendation}")
                        lines.append(f"    Current: {rec.current_value} | Recommended: {rec.recommended_value}")

            return "\n".join(lines)

        raise ValueError(f"Unsupported format: {format}")

    def save_metrics(self, filepath: Path) -> None:
        """Save collected metrics to file."""
        data = [asdict(m) for m in self.metrics_history]

        # Convert datetime to string
        for record in data:
            record["timestamp"] = record["timestamp"].isoformat()

        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Metrics saved to {filepath}")


async def example_usage():
    """Example of how to use the PoolOptimizer."""

    # This would be replaced with actual pool stats function
    async def get_pool_stats():
        """Mock function returning pool statistics."""
        return {
            "database_pool": {
                "pool_size": 15,
                "in_use": 12,
                "min_size": 5,
                "max_size": 20,
                "connections_created": 100,
                "connections_reused": 500,
                "connections_closed": 10,
                "errors": 2,
                "acquisition_time_ms": 45.0,
                "slow_acquisitions": 3,
            },
            "cache_pool": {
                "pool_size": 3,
                "in_use": 1,
                "min_size": 2,
                "max_size": 10,
                "connections_created": 50,
                "connections_reused": 200,
                "connections_closed": 5,
                "errors": 0,
                "acquisition_time_ms": 15.0,
                "slow_acquisitions": 0,
            },
        }

    # Create optimizer
    optimizer = PoolOptimizer(collection_interval=5.0)

    # Collect metrics for 5 minutes
    await optimizer.collect_metrics_async(get_pool_stats_func=get_pool_stats, duration=timedelta(minutes=5))

    # Analyze and get recommendations
    recommendations = optimizer.analyze_pools()

    # Export report
    print(optimizer.export_report(recommendations, format="text"))

    # Save metrics for later analysis
    optimizer.save_metrics(Path("pool_metrics.json"))


if __name__ == "__main__":
    asyncio.run(example_usage())
