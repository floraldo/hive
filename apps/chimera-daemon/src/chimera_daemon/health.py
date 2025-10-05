"""Health monitoring system with threshold-based alerts.

Provides production-grade health monitoring with:
- Threshold-based alert detection
- Health status tracking (healthy/warning/critical)
- Actionable recommendations for operators
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from hive_logging import get_logger

from .metrics import PoolMetrics

logger = get_logger(__name__)


class HealthStatus(Enum):
    """System health status levels."""

    HEALTHY = "healthy"  # All metrics within acceptable ranges
    WARNING = "warning"  # Some metrics approaching thresholds
    CRITICAL = "critical"  # Metrics exceeding critical thresholds


@dataclass
class Alert:
    """Health alert with actionable recommendations."""

    severity: str  # "warning" | "critical"
    metric: str  # Metric that triggered alert
    current_value: float
    threshold: float
    message: str
    recommendation: str


@dataclass
class HealthReport:
    """Comprehensive health assessment report."""

    status: HealthStatus
    alerts: list[Alert]
    metrics_summary: dict[str, Any]
    recommendations: list[str]


class HealthThresholds:
    """Configurable health thresholds for monitoring.

    Thresholds are organized by severity:
    - WARNING: Early indicators, should investigate
    - CRITICAL: Immediate action required
    """

    def __init__(
        self,
        pool_utilization_warning: float = 80.0,
        pool_utilization_critical: float = 95.0,
        success_rate_warning: float = 90.0,
        success_rate_critical: float = 75.0,
        p95_latency_warning_ms: float = 60000.0,  # 60s
        p95_latency_critical_ms: float = 120000.0,  # 2min
        queue_depth_warning: int = 10,
        queue_depth_critical: int = 25,
        failure_rate_warning: float = 10.0,
        failure_rate_critical: float = 25.0,
    ):
        """Initialize health thresholds.

        Args:
            pool_utilization_warning: Pool utilization % warning threshold
            pool_utilization_critical: Pool utilization % critical threshold
            success_rate_warning: Success rate % warning threshold (below)
            success_rate_critical: Success rate % critical threshold (below)
            p95_latency_warning_ms: P95 latency warning threshold in ms
            p95_latency_critical_ms: P95 latency critical threshold in ms
            queue_depth_warning: Queue depth warning threshold
            queue_depth_critical: Queue depth critical threshold
            failure_rate_warning: Failure rate % warning threshold
            failure_rate_critical: Failure rate % critical threshold

        Raises:
            ValueError: If warning thresholds are not less than critical thresholds
        """
        # Validate threshold ordering
        if pool_utilization_warning >= pool_utilization_critical:
            raise ValueError(
                f"pool_utilization_warning ({pool_utilization_warning}) must be < "
                f"pool_utilization_critical ({pool_utilization_critical})"
            )

        if success_rate_warning <= success_rate_critical:
            raise ValueError(
                f"success_rate_warning ({success_rate_warning}) must be > "
                f"success_rate_critical ({success_rate_critical})"
            )

        if p95_latency_warning_ms >= p95_latency_critical_ms:
            raise ValueError(
                f"p95_latency_warning_ms ({p95_latency_warning_ms}) must be < "
                f"p95_latency_critical_ms ({p95_latency_critical_ms})"
            )

        if queue_depth_warning >= queue_depth_critical:
            raise ValueError(
                f"queue_depth_warning ({queue_depth_warning}) must be < "
                f"queue_depth_critical ({queue_depth_critical})"
            )

        if failure_rate_warning >= failure_rate_critical:
            raise ValueError(
                f"failure_rate_warning ({failure_rate_warning}) must be < "
                f"failure_rate_critical ({failure_rate_critical})"
            )

        # Validate ranges
        if not (0 <= pool_utilization_warning <= 100):
            raise ValueError(f"pool_utilization_warning must be 0-100, got {pool_utilization_warning}")

        if not (0 <= pool_utilization_critical <= 100):
            raise ValueError(f"pool_utilization_critical must be 0-100, got {pool_utilization_critical}")

        if queue_depth_warning < 0:
            raise ValueError(f"queue_depth_warning must be >= 0, got {queue_depth_warning}")

        if queue_depth_critical < 0:
            raise ValueError(f"queue_depth_critical must be >= 0, got {queue_depth_critical}")

        self.pool_utilization_warning = pool_utilization_warning
        self.pool_utilization_critical = pool_utilization_critical
        self.success_rate_warning = success_rate_warning
        self.success_rate_critical = success_rate_critical
        self.p95_latency_warning_ms = p95_latency_warning_ms
        self.p95_latency_critical_ms = p95_latency_critical_ms
        self.queue_depth_warning = queue_depth_warning
        self.queue_depth_critical = queue_depth_critical
        self.failure_rate_warning = failure_rate_warning
        self.failure_rate_critical = failure_rate_critical


class HealthMonitor:
    """Monitor ExecutorPool health with threshold-based alerting.

    Continuously assesses pool health and generates actionable alerts
    when metrics exceed configured thresholds.

    Example:
        monitor = HealthMonitor()
        report = await monitor.assess_health(pool_metrics)
        if report.status == HealthStatus.CRITICAL:
            for alert in report.alerts:
                logger.critical(alert.message)
    """

    def __init__(self, thresholds: HealthThresholds | None = None):
        """Initialize health monitor.

        Args:
            thresholds: Custom health thresholds (uses defaults if None)
        """
        self.thresholds = thresholds or HealthThresholds()
        self.logger = logger

    def assess_health(self, metrics: PoolMetrics) -> HealthReport:
        """Assess pool health based on current metrics.

        Args:
            metrics: Current pool metrics

        Returns:
            Health report with status, alerts, and recommendations
        """
        alerts: list[Alert] = []

        # Check pool utilization
        self._check_pool_utilization(metrics, alerts)

        # Check success rate
        self._check_success_rate(metrics, alerts)

        # Check latency (P95)
        self._check_latency(metrics, alerts)

        # Check queue depth
        self._check_queue_depth(metrics, alerts)

        # Check failure patterns by phase
        self._check_failure_patterns(metrics, alerts)

        # Determine overall health status
        status = self._determine_status(alerts)

        # Generate recommendations
        recommendations = self._generate_recommendations(alerts, metrics)

        # Create metrics summary
        metrics_summary = {
            "pool_utilization_pct": metrics.pool_utilization_pct,
            "success_rate": metrics.success_rate,
            "p95_latency_ms": metrics.p95_workflow_duration_ms,
            "queue_depth": metrics.queue_depth,
            "queue_trend": metrics.queue_depth_trend,
            "latency_trend": metrics.latency_trend,
        }

        return HealthReport(
            status=status,
            alerts=alerts,
            metrics_summary=metrics_summary,
            recommendations=recommendations,
        )

    def _check_pool_utilization(self, metrics: PoolMetrics, alerts: list[Alert]) -> None:
        """Check pool utilization against thresholds."""
        util = metrics.pool_utilization_pct

        if util >= self.thresholds.pool_utilization_critical:
            alerts.append(
                Alert(
                    severity="critical",
                    metric="pool_utilization",
                    current_value=util,
                    threshold=self.thresholds.pool_utilization_critical,
                    message=f"Pool utilization critical: {util:.1f}% (threshold: {self.thresholds.pool_utilization_critical}%)",
                    recommendation="Increase max_concurrent or investigate stuck workflows",
                )
            )
        elif util >= self.thresholds.pool_utilization_warning:
            alerts.append(
                Alert(
                    severity="warning",
                    metric="pool_utilization",
                    current_value=util,
                    threshold=self.thresholds.pool_utilization_warning,
                    message=f"Pool utilization high: {util:.1f}% (threshold: {self.thresholds.pool_utilization_warning}%)",
                    recommendation="Monitor closely - consider scaling up if sustained",
                )
            )

    def _check_success_rate(self, metrics: PoolMetrics, alerts: list[Alert]) -> None:
        """Check success rate against thresholds."""
        success_rate = metrics.success_rate

        if success_rate <= self.thresholds.success_rate_critical:
            alerts.append(
                Alert(
                    severity="critical",
                    metric="success_rate",
                    current_value=success_rate,
                    threshold=self.thresholds.success_rate_critical,
                    message=f"Success rate critical: {success_rate:.1f}% (threshold: {self.thresholds.success_rate_critical}%)",
                    recommendation="Investigate recent failures - check logs for error patterns",
                )
            )
        elif success_rate <= self.thresholds.success_rate_warning:
            alerts.append(
                Alert(
                    severity="warning",
                    metric="success_rate",
                    current_value=success_rate,
                    threshold=self.thresholds.success_rate_warning,
                    message=f"Success rate low: {success_rate:.1f}% (threshold: {self.thresholds.success_rate_warning}%)",
                    recommendation="Review failure patterns - may indicate quality issues",
                )
            )

    def _check_latency(self, metrics: PoolMetrics, alerts: list[Alert]) -> None:
        """Check P95 latency against thresholds."""
        p95 = metrics.p95_workflow_duration_ms

        if p95 >= self.thresholds.p95_latency_critical_ms:
            alerts.append(
                Alert(
                    severity="critical",
                    metric="p95_latency",
                    current_value=p95,
                    threshold=self.thresholds.p95_latency_critical_ms,
                    message=f"P95 latency critical: {p95:.0f}ms (threshold: {self.thresholds.p95_latency_critical_ms}ms)",
                    recommendation="Investigate slow workflows - check for resource contention",
                )
            )
        elif p95 >= self.thresholds.p95_latency_warning_ms:
            alerts.append(
                Alert(
                    severity="warning",
                    metric="p95_latency",
                    current_value=p95,
                    threshold=self.thresholds.p95_latency_warning_ms,
                    message=f"P95 latency high: {p95:.0f}ms (threshold: {self.thresholds.p95_latency_warning_ms}ms)",
                    recommendation="Monitor latency trend - optimize slow operations if sustained",
                )
            )

    def _check_queue_depth(self, metrics: PoolMetrics, alerts: list[Alert]) -> None:
        """Check queue depth against thresholds."""
        depth = metrics.queue_depth

        if depth >= self.thresholds.queue_depth_critical:
            alerts.append(
                Alert(
                    severity="critical",
                    metric="queue_depth",
                    current_value=float(depth),
                    threshold=float(self.thresholds.queue_depth_critical),
                    message=f"Queue depth critical: {depth} (threshold: {self.thresholds.queue_depth_critical})",
                    recommendation="Scale up immediately or pause task submission",
                )
            )
        elif depth >= self.thresholds.queue_depth_warning:
            # Check trend - only alert if increasing
            if metrics.queue_depth_trend == "increasing":
                alerts.append(
                    Alert(
                        severity="warning",
                        metric="queue_depth",
                        current_value=float(depth),
                        threshold=float(self.thresholds.queue_depth_warning),
                        message=f"Queue depth increasing: {depth} (threshold: {self.thresholds.queue_depth_warning})",
                        recommendation="Monitor queue trend - may need capacity increase",
                    )
                )

    def _check_failure_patterns(self, metrics: PoolMetrics, alerts: list[Alert]) -> None:
        """Check failure patterns by phase."""
        for phase, failure_rate in metrics.failure_rate_by_phase.items():
            if failure_rate >= self.thresholds.failure_rate_critical:
                alerts.append(
                    Alert(
                        severity="critical",
                        metric=f"failure_rate_{phase}",
                        current_value=failure_rate,
                        threshold=self.thresholds.failure_rate_critical,
                        message=f"High failure rate in {phase}: {failure_rate:.1f}%",
                        recommendation=f"Investigate {phase} phase - check agent configuration",
                    )
                )
            elif failure_rate >= self.thresholds.failure_rate_warning:
                alerts.append(
                    Alert(
                        severity="warning",
                        metric=f"failure_rate_{phase}",
                        current_value=failure_rate,
                        threshold=self.thresholds.failure_rate_warning,
                        message=f"Elevated failure rate in {phase}: {failure_rate:.1f}%",
                        recommendation=f"Review {phase} phase execution logs",
                    )
                )

    def _determine_status(self, alerts: list[Alert]) -> HealthStatus:
        """Determine overall health status from alerts."""
        if not alerts:
            return HealthStatus.HEALTHY

        # Critical if any critical alerts
        if any(a.severity == "critical" for a in alerts):
            return HealthStatus.CRITICAL

        # Warning if any warning alerts
        if any(a.severity == "warning" for a in alerts):
            return HealthStatus.WARNING

        return HealthStatus.HEALTHY

    def _generate_recommendations(self, alerts: list[Alert], metrics: PoolMetrics) -> list[str]:
        """Generate prioritized recommendations based on alerts and metrics."""
        recommendations = []

        # Add alert-specific recommendations
        for alert in sorted(alerts, key=lambda a: 0 if a.severity == "critical" else 1):
            recommendations.append(f"[{alert.severity.upper()}] {alert.recommendation}")

        # Add general optimization recommendations based on trends
        if metrics.latency_trend == "degrading" and not any("latency" in a.metric for a in alerts):
            recommendations.append("[INFO] Latency trending upward - consider profiling workflows")

        if metrics.throughput_trend == "decreasing" and not any("utilization" in a.metric for a in alerts):
            recommendations.append("[INFO] Throughput decreasing - check for bottlenecks")

        return recommendations


__all__ = ["HealthMonitor", "HealthThresholds", "HealthReport", "HealthStatus", "Alert"]
