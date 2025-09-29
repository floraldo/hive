"""
Predictive failure alerts and trend analysis.

Analyzes trends from monitoring systems to predict potential failures
before thresholds are breached, enabling proactive maintenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from hive_logging import get_logger

logger = get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    CRITICAL = "critical"  # Breach predicted within 1 hour (>90% confidence)
    HIGH = "high"  # Breach predicted within 4 hours (>80% confidence)
    MEDIUM = "medium"  # Concerning trend but no immediate threat
    LOW = "low"  # Informational, monitor for pattern changes


class MetricType(Enum):
    """Types of metrics being monitored."""

    ERROR_RATE = "error_rate"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    CPU_UTILIZATION = "cpu_utilization"
    MEMORY_UTILIZATION = "memory_utilization"
    CONNECTION_POOL = "connection_pool"
    REQUEST_RATE = "request_rate"
    CIRCUIT_BREAKER_FAILURES = "circuit_breaker_failures"


@dataclass
class MetricPoint:
    """Single metric measurement point."""

    timestamp: datetime
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DegradationAlert:
    """Alert for detected metric degradation."""

    alert_id: str
    service_name: str
    metric_type: MetricType
    current_value: float
    predicted_value: float
    threshold: float
    time_to_breach: timedelta | None
    confidence: float  # 0.0-1.0
    severity: AlertSeverity
    recommended_actions: list[str]
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "service_name": self.service_name,
            "metric_type": self.metric_type.value,
            "current_value": self.current_value,
            "predicted_value": self.predicted_value,
            "threshold": self.threshold,
            "time_to_breach_seconds": (self.time_to_breach.total_seconds() if self.time_to_breach else None),
            "confidence": self.confidence,
            "severity": self.severity.value,
            "recommended_actions": self.recommended_actions,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class TrendAnalyzer:
    """
    Analyze metric trends for predictive insights.

    Uses exponential moving average, linear regression, and pattern
    detection to identify potential failures before they occur.
    """

    def __init__(self, window_size: int = 50, ema_alpha: float = 0.2, degradation_threshold: int = 3):
        """
        Initialize trend analyzer.

        Args:
            window_size: Number of data points to analyze
            ema_alpha: EMA smoothing factor (0.0-1.0, higher = more responsive)
            degradation_threshold: Consecutive increases to trigger alert
        """
        self.window_size = window_size
        self.ema_alpha = ema_alpha
        self.degradation_threshold = degradation_threshold

    def calculate_ema(self, data: list[float], alpha: float | None = None) -> list[float]:
        """
        Calculate exponential moving average.

        Args:
            data: List of metric values
            alpha: Smoothing factor (uses default if None)

        Returns:
            List of EMA values
        """
        if not data:
            return []

        alpha = alpha or self.ema_alpha
        ema = [data[0]]

        for value in data[1:]:
            ema.append(alpha * value + (1 - alpha) * ema[-1])

        return ema

    def detect_degradation(self, metrics: list[MetricPoint], threshold: float) -> Optional[DegradationAlert]:
        """
        Detect if metrics show degradation pattern.

        Returns alert if consecutive increases detected that could
        lead to threshold breach.

        Args:
            metrics: Historical metric data points
            threshold: Threshold value that triggers concern

        Returns:
            DegradationAlert if pattern detected, None otherwise
        """
        if len(metrics) < self.degradation_threshold + 1:
            logger.debug(f"Insufficient data points: {len(metrics)} < {self.degradation_threshold + 1}")
            return None

        # Use recent window for analysis
        recent_metrics = metrics[-self.window_size :]
        values = [m.value for m in recent_metrics]

        # Calculate EMA to smooth noise
        ema = self.calculate_ema(values)

        # Check for consecutive increases
        increases = 0
        for i in range(len(ema) - 1):
            if ema[i + 1] > ema[i]:
                increases += 1
                if increases >= self.degradation_threshold:
                    logger.info(f"Degradation detected: {increases} consecutive increases")
                    return self._create_degradation_alert(recent_metrics, ema, threshold)
            else:
                increases = 0  # Reset on decrease

        return None

    def _create_degradation_alert(
        self, metrics: list[MetricPoint], ema: list[float], threshold: float
    ) -> DegradationAlert:
        """Create degradation alert from analysis results."""
        current_value = metrics[-1].value
        ema_current = ema[-1]

        # Predict time to breach using linear regression
        time_to_breach = self.predict_time_to_breach(metrics, threshold)

        # Calculate confidence based on trend consistency
        confidence = self._calculate_confidence(ema)

        # Determine severity based on time to breach and confidence
        severity = self._determine_severity(time_to_breach, confidence)

        # Generate recommended actions
        recommended_actions = self._generate_recommendations(metrics, threshold, severity)

        alert_id = self._generate_alert_id(metrics[0].metadata.get("service", "unknown"))

        return DegradationAlert(
            alert_id=alert_id,
            service_name=metrics[0].metadata.get("service", "unknown"),
            metric_type=MetricType(metrics[0].metadata.get("metric_type", "error_rate")),
            current_value=current_value,
            predicted_value=ema_current,
            threshold=threshold,
            time_to_breach=time_to_breach,
            confidence=confidence,
            severity=severity,
            recommended_actions=recommended_actions,
            created_at=datetime.utcnow(),
            metadata={"ema_value": ema_current, "trend_length": len(ema)},
        )

    def predict_time_to_breach(self, metrics: list[MetricPoint], threshold: float) -> timedelta | None:
        """
        Use linear regression to predict when threshold will be breached.

        Args:
            metrics: Historical metric data points
            threshold: Threshold value to predict breach time

        Returns:
            Time until breach, or None if not trending toward threshold
        """
        if len(metrics) < 5:
            return None

        # Convert to arrays for regression
        base_time = metrics[0].timestamp
        timestamps = [(m.timestamp - base_time).total_seconds() for m in metrics]
        values = [m.value for m in metrics]

        # Calculate linear regression
        slope, intercept = self._linear_regression(timestamps, values)

        current_value = values[-1]
        current_time = timestamps[-1]

        # Check if trending toward threshold
        if slope <= 0 and threshold > current_value:
            return None  # Improving or stable
        if slope >= 0 and threshold < current_value:
            return None  # Already breached

        # Avoid division by zero
        if abs(slope) < 1e-10:
            return None

        # Calculate time to breach
        seconds_to_breach = (threshold - intercept) / slope - current_time

        if seconds_to_breach <= 0:
            return timedelta(0)  # Already at threshold

        return timedelta(seconds=seconds_to_breach)

    def _linear_regression(self, x: list[float], y: list[float]) -> tuple[float, float]:
        """
        Calculate simple linear regression.

        Args:
            x: Independent variable (time)
            y: Dependent variable (metric value)

        Returns:
            (slope, intercept) of regression line
        """
        n = len(x)
        if n == 0:
            return 0.0, 0.0

        x_mean = sum(x) / n
        y_mean = sum(y) / n

        # Calculate slope
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0, y_mean

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        return slope, intercept

    def _calculate_confidence(self, ema: list[float]) -> float:
        """
        Calculate confidence score based on trend consistency.

        Higher confidence when trend is consistent and strong.

        Args:
            ema: Exponential moving average values

        Returns:
            Confidence score (0.0-1.0)
        """
        if len(ema) < 3:
            return 0.5

        # Calculate trend strength (rate of change)
        changes = [ema[i + 1] - ema[i] for i in range(len(ema) - 1)]

        # Consistency: how many changes are in same direction
        positive_changes = sum(1 for c in changes if c > 0)
        consistency = positive_changes / len(changes)

        # Magnitude: average size of changes
        avg_change = sum(abs(c) for c in changes) / len(changes)
        magnitude_score = min(avg_change / (ema[-1] * 0.1), 1.0)  # Cap at 1.0

        # Combine consistency and magnitude
        confidence = (consistency * 0.7) + (magnitude_score * 0.3)

        return min(max(confidence, 0.0), 1.0)  # Clamp to [0, 1]

    def _determine_severity(self, time_to_breach: timedelta | None, confidence: float) -> AlertSeverity:
        """
        Determine alert severity based on time to breach and confidence.

        Args:
            time_to_breach: Predicted time until threshold breach
            confidence: Confidence in prediction (0.0-1.0)

        Returns:
            Alert severity level
        """
        if time_to_breach is None:
            return AlertSeverity.LOW

        hours_to_breach = time_to_breach.total_seconds() / 3600

        # Critical: <1 hour with high confidence
        if hours_to_breach < 1 and confidence > 0.9:
            return AlertSeverity.CRITICAL

        # High: <4 hours with good confidence
        if hours_to_breach < 4 and confidence > 0.8:
            return AlertSeverity.HIGH

        # Medium: <24 hours with decent confidence
        if hours_to_breach < 24 and confidence > 0.6:
            return AlertSeverity.MEDIUM

        # Low: longer timeframe or lower confidence
        return AlertSeverity.LOW

    def _generate_recommendations(
        self, metrics: list[MetricPoint], threshold: float, severity: AlertSeverity
    ) -> list[str]:
        """
        Generate recommended actions based on metric type and severity.

        Args:
            metrics: Historical metric data
            threshold: Threshold value
            severity: Alert severity

        Returns:
            List of recommended actions
        """
        metric_type = metrics[0].metadata.get("metric_type", "unknown")
        recommendations = []

        if metric_type == "error_rate":
            recommendations.extend(
                [
                    "Review recent error logs for root cause",
                    "Check if circuit breakers are functioning",
                    "Consider enabling fallback mechanisms",
                ]
            )
            if severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
                recommendations.append("Enable request throttling immediately")

        elif metric_type in ["latency_p95", "latency_p99"]:
            recommendations.extend(
                ["Review slow query logs", "Check connection pool utilization", "Consider enabling response caching"]
            )
            if severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
                recommendations.append("Activate load shedding for non-critical requests")

        elif metric_type in ["cpu_utilization", "memory_utilization"]:
            recommendations.extend(
                [
                    "Scale out additional worker instances",
                    "Review recent resource-intensive operations",
                    "Check for memory leaks or CPU-bound tasks",
                ]
            )
            if severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
                recommendations.append("Implement emergency auto-scaling")

        elif metric_type == "connection_pool":
            recommendations.extend(
                ["Increase connection pool size", "Review connection timeout settings", "Check for connection leaks"]
            )

        return recommendations

    def _generate_alert_id(self, service_name: str) -> str:
        """Generate unique alert identifier."""
        import hashlib

        timestamp = datetime.utcnow().isoformat()
        content = f"{service_name}:{timestamp}"
        hash_value = hashlib.md5(content.encode("utf-8")).hexdigest()[:12]
        return f"alert-{hash_value}"

    def detect_anomaly(self, metrics: list[MetricPoint], std_dev_threshold: float = 2.0) -> bool:
        """
        Detect statistical anomalies using standard deviation.

        Args:
            metrics: Historical metric data points
            std_dev_threshold: Number of standard deviations for anomaly

        Returns:
            True if current value is anomalous
        """
        if len(metrics) < 10:
            return False

        values = [m.value for m in metrics[:-1]]  # Exclude current value
        current_value = metrics[-1].value

        # Calculate mean and standard deviation
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance**0.5

        # Check if current value is beyond threshold
        z_score = abs(current_value - mean) / std_dev if std_dev > 0 else 0
        is_anomaly = z_score > std_dev_threshold

        if is_anomaly:
            logger.warning(
                f"Anomaly detected: value={current_value:.2f}, "
                f"mean={mean:.2f}, std_dev={std_dev:.2f}, z_score={z_score:.2f}"
            )

        return is_anomaly
