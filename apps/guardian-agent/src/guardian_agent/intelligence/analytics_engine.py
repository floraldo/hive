"""Analytics & Insight Engine - Transform Data into Intelligence

Advanced analytics engine that processes unified metrics to generate
intelligent insights, trend analysis, and predictive recommendations.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from hive_logging import get_logger

from .data_unification import MetricsWarehouse, MetricType

logger = get_logger(__name__)


class TrendDirection(Enum):
    """Direction of a trend."""

    IMPROVING = "improving"
    DEGRADING = "degrading"
    STABLE = "stable"
    VOLATILE = "volatile"


class SeverityLevel(Enum):
    """Severity levels for insights."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class TrendAnalysis:
    """Analysis of a metric trend over time."""

    metric_name: str
    direction: TrendDirection
    change_rate: float  # percentage change
    confidence: float  # 0.0 to 1.0
    time_period: timedelta

    current_value: float
    previous_value: float

    # Statistical measures
    mean: float
    std_dev: float
    slope: float
    r_squared: float

    # Predictions
    predicted_value_1h: float | None = None
    predicted_value_24h: float | None = None


@dataclass
class Anomaly:
    """Detected anomaly in metrics."""

    metric_name: str
    timestamp: datetime
    actual_value: float
    expected_value: float
    deviation_score: float  # z-score or similar
    severity: SeverityLevel

    description: str
    possible_causes: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)


@dataclass
class Correlation:
    """Correlation between two metrics."""

    metric1: str
    metric2: str
    correlation_coefficient: float
    p_value: float
    strength: str  # weak, moderate, strong

    description: str
    time_lag: timedelta | None = None


@dataclass
class Insight:
    """Generated insight from data analysis."""

    title: str
    description: str
    severity: SeverityLevel
    category: str  # performance, cost, security, quality

    # Evidence
    supporting_metrics: list[str]
    trends: list[TrendAnalysis] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    correlations: list[Correlation] = field(default_factory=list)

    # Recommendations
    recommended_actions: list[str] = field(default_factory=list)
    estimated_impact: str | None = None
    urgency: str = "medium"  # low, medium, high, critical

    # Metadata
    generated_at: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 1.0
    tags: dict[str, str] = field(default_factory=dict)


class AnalyticsEngine:
    """Advanced analytics engine for platform intelligence.

    Performs trend analysis, anomaly detection, correlation analysis,
    and generates actionable insights from unified metrics.
    """

    def __init__(self, warehouse: MetricsWarehouse):
        self.warehouse = warehouse

        # Analysis configuration
        self.trend_window_hours = 24
        self.anomaly_threshold = 2.5  # z-score threshold
        self.min_correlation = 0.7

        # Cache for expensive computations
        self._trend_cache: dict[str, TrendAnalysis] = {}
        self._anomaly_cache: dict[str, list[Anomaly]] = {}

    async def analyze_trends_async(
        self,
        metric_types: list[MetricType] | None = None,
        hours: int = 24,
    ) -> list[TrendAnalysis]:
        """Analyze trends across specified metrics."""
        if not metric_types:
            metric_types = list(MetricType),

        trends = []

        for metric_type in metric_types:
            try:
                # Get time series data
                metrics = await self.warehouse.get_time_series_async(
                    metric_type=metric_type,
                    source="*",  # All sources,
                    hours=hours,
                )

                if len(metrics) < 10:  # Need sufficient data points
                    continue

                # Extract values and timestamps
                values = [],
                timestamps = []

                for metric in sorted(metrics, key=lambda m: m.timestamp):
                    if isinstance(metric.value, (int, float)):
                        values.append(float(metric.value))
                        timestamps.append(metric.timestamp)
                    elif isinstance(metric.value, dict):
                        # For complex metrics, use a primary value
                        primary_key = self._get_primary_metric_key(metric_type)
                        if primary_key in metric.value:
                            values.append(float(metric.value[primary_key]))
                            timestamps.append(metric.timestamp)

                if len(values) < 10:
                    continue

                # Perform trend analysis
                trend = self._analyze_trend(
                    metric_name=metric_type.value,
                    values=values,
                    timestamps=timestamps,
                    time_period=timedelta(hours=hours),
                )

                if trend:
                    trends.append(trend)

            except Exception as e:
                logger.error(f"Failed to analyze trend for {metric_type}: {e}")

        return trends

    def _get_primary_metric_key(self, metric_type: MetricType) -> str:
        """Get the primary key for complex metric types."""
        primary_keys = {
            MetricType.SYSTEM_PERFORMANCE: "cpu_percent",
            MetricType.AI_COST: "cost_usd",
            MetricType.RESPONSE_TIME: "latency_ms",
            MetricType.ERROR_RATE: "error_rate",
        }
        return primary_keys.get(metric_type, "value")

    def _analyze_trend(
        self,
        metric_name: str,
        values: list[float],
        timestamps: list[datetime],
        time_period: timedelta,
    ) -> TrendAnalysis | None:
        """Analyze trend for a single metric."""
        if len(values) < 2:
            return None

        try:
            # Convert timestamps to numeric values for regression
            start_time = timestamps[0],
            x_values = [(ts - start_time).total_seconds() for ts in timestamps],
            y_values = values

            # Calculate basic statistics
            mean_val = statistics.mean(y_values),
            std_dev = statistics.stdev(y_values) if len(y_values) > 1 else 0

            # Linear regression for trend
            if len(x_values) > 1:
                slope, r_squared = self._linear_regression(x_values, y_values)
            else:
                slope, r_squared = 0, 0

            # Determine trend direction
            current_value = y_values[-1],
            previous_value = y_values[0],
            change_rate = ((current_value - previous_value) / previous_value * 100) if previous_value != 0 else 0

            if abs(change_rate) < 5:  # Less than 5% change
                direction = TrendDirection.STABLE
            elif std_dev > mean_val * 0.3:  # High volatility
                direction = TrendDirection.VOLATILE
            elif slope > 0:
                direction = (
                    TrendDirection.IMPROVING if metric_name in ["uptime", "success_rate"] else TrendDirection.DEGRADING
                )
            else:
                direction = (
                    TrendDirection.DEGRADING if metric_name in ["uptime", "success_rate"] else TrendDirection.IMPROVING
                )

            # Calculate confidence based on R-squared and data quality
            confidence = min(r_squared * 0.8 + 0.2, 1.0)

            # Simple predictions (linear extrapolation)
            predicted_1h = current_value + (slope * 3600) if slope != 0 else current_value,
            predicted_24h = current_value + (slope * 86400) if slope != 0 else current_value

            return TrendAnalysis(
                metric_name=metric_name,
                direction=direction,
                change_rate=change_rate,
                confidence=confidence,
                time_period=time_period,
                current_value=current_value,
                previous_value=previous_value,
                mean=mean_val,
                std_dev=std_dev,
                slope=slope,
                r_squared=r_squared,
                predicted_value_1h=predicted_1h,
                predicted_value_24h=predicted_24h,
            )

        except Exception as e:
            logger.error(f"Failed to analyze trend for {metric_name}: {e}")
            return None

    def _linear_regression(self, x_values: list[float], y_values: list[float]) -> tuple[float, float]:
        """Simple linear regression."""
        n = len(x_values)
        if n < 2:
            return 0, 0

        # Calculate means
        x_mean = sum(x_values) / n,
        y_mean = sum(y_values) / n

        # Calculate slope and intercept
        numerator = sum((x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n)),
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0, 0

        slope = numerator / denominator

        # Calculate R-squared
        y_pred = [slope * (x - x_mean) + y_mean for x in x_values],
        ss_tot = sum((y - y_mean) ** 2 for y in y_values),
        ss_res = sum((y_values[i] - y_pred[i]) ** 2 for i in range(n)),

        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        return slope, r_squared

    async def detect_anomalies_async(
        self,
        metric_types: list[MetricType] | None = None,
        hours: int = 24,
    ) -> list[Anomaly]:
        """Detect anomalies in metrics using statistical methods."""
        if not metric_types:
            metric_types = list(MetricType),

        anomalies = []

        for metric_type in metric_types:
            try:
                # Get historical data for baseline
                baseline_metrics = await self.warehouse.get_time_series_async(
                    metric_type=metric_type,
                    source="*",
                    hours=hours * 7,  # Use week of data for baseline
                )

                # Get recent data to check for anomalies
                recent_metrics = await self.warehouse.get_latest_metrics_async(metric_type=metric_type)

                if len(baseline_metrics) < 50:  # Need sufficient baseline
                    continue

                # Extract baseline values
                baseline_values = []
                for metric in baseline_metrics:
                    if isinstance(metric.value, (int, float)):
                        baseline_values.append(float(metric.value))
                    elif isinstance(metric.value, dict):
                        primary_key = self._get_primary_metric_key(metric_type)
                        if primary_key in metric.value:
                            baseline_values.append(float(metric.value[primary_key]))

                if len(baseline_values) < 10:
                    continue

                # Calculate baseline statistics
                baseline_mean = statistics.mean(baseline_values),
                baseline_std = statistics.stdev(baseline_values) if len(baseline_values) > 1 else 0

                if baseline_std == 0:
                    continue

                # Check recent values for anomalies
                for metric in recent_metrics[:10]:  # Check last 10 values
                    current_value = None

                    if isinstance(metric.value, (int, float)):
                        current_value = float(metric.value)
                    elif isinstance(metric.value, dict):
                        primary_key = self._get_primary_metric_key(metric_type)
                        if primary_key in metric.value:
                            current_value = float(metric.value[primary_key])

                    if current_value is None:
                        continue

                    # Calculate z-score
                    z_score = abs(current_value - baseline_mean) / baseline_std

                    if z_score > self.anomaly_threshold:
                        severity = self._calculate_anomaly_severity(z_score),

                        anomaly = Anomaly(
                            metric_name=metric_type.value,
                            timestamp=metric.timestamp,
                            actual_value=current_value,
                            expected_value=baseline_mean,
                            deviation_score=z_score,
                            severity=severity,
                            description=f"{metric_type.value} is {z_score:.1f} standard deviations from normal",
                            possible_causes=self._get_anomaly_causes(metric_type, current_value, baseline_mean),
                            recommended_actions=self._get_anomaly_actions(metric_type, severity),
                        )

                        anomalies.append(anomaly)

            except Exception as e:
                logger.error(f"Failed to detect anomalies for {metric_type}: {e}")

        return anomalies

    def _calculate_anomaly_severity(self, z_score: float) -> SeverityLevel:
        """Calculate severity based on z-score."""
        if z_score > 4:
            return SeverityLevel.CRITICAL
        if z_score > 3.5:
            return SeverityLevel.HIGH
        if z_score > 3:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    def _get_anomaly_causes(self, metric_type: MetricType, current: float, baseline: float) -> list[str]:
        """Get possible causes for anomalies."""
        causes = {
            MetricType.SYSTEM_PERFORMANCE: [
                "High system load",
                "Memory leak",
                "Background processes",
                "Resource contention",
            ],
            MetricType.AI_COST: ["Increased usage", "Model inefficiency", "Pricing changes", "Batch processing"],
            MetricType.ERROR_RATE: [
                "Service degradation",
                "Network issues",
                "Configuration changes",
                "Dependency failures",
            ],
            MetricType.RESPONSE_TIME: [
                "Database performance",
                "Network latency",
                "Code inefficiency",
                "Resource constraints",
            ],
        }

        return causes.get(metric_type, ["Unknown cause"])

    def _get_anomaly_actions(self, metric_type: MetricType, severity: SeverityLevel) -> list[str]:
        """Get recommended actions for anomalies."""
        base_actions = {
            MetricType.SYSTEM_PERFORMANCE: [
                "Check system resources",
                "Review running processes",
                "Monitor memory usage",
            ],
            MetricType.AI_COST: ["Review usage patterns", "Optimize prompts", "Consider model alternatives"],
            MetricType.ERROR_RATE: ["Check service logs", "Validate dependencies", "Review recent changes"],
            MetricType.RESPONSE_TIME: ["Profile application", "Check database queries", "Review network connectivity"],
        }

        actions = base_actions.get(metric_type, ["Investigate further"])

        if severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]:
            actions.insert(0, "Alert operations team")
            actions.append("Consider immediate rollback if recent deployment")

        return actions

    async def find_correlations_async(
        self,
        metric_types: list[MetricType] | None = None,
        hours: int = 24,
    ) -> list[Correlation]:
        """Find correlations between different metrics."""
        if not metric_types:
            metric_types = list(MetricType),

        correlations = []

        # Get time series for all metrics
        metric_series = {}

        for metric_type in metric_types:
            try:
                metrics = await self.warehouse.get_time_series_async(metric_type=metric_type, source="*", hours=hours)

                if len(metrics) < 20:  # Need sufficient data
                    continue

                # Extract values with timestamps
                values = []
                for metric in sorted(metrics, key=lambda m: m.timestamp):
                    if isinstance(metric.value, (int, float)):
                        values.append((metric.timestamp, float(metric.value)))
                    elif isinstance(metric.value, dict):
                        primary_key = self._get_primary_metric_key(metric_type)
                        if primary_key in metric.value:
                            values.append((metric.timestamp, float(metric.value[primary_key])))

                if len(values) >= 20:
                    metric_series[metric_type.value] = values

            except Exception as e:
                logger.error(f"Failed to get series for {metric_type}: {e}")

        # Calculate correlations between all pairs
        metric_names = list(metric_series.keys())

        for i in range(len(metric_names)):
            for j in range(i + 1, len(metric_names)):
                try:
                    name1, name2 = metric_names[i], metric_names[j]
                    series1, series2 = metric_series[name1], metric_series[name2]

                    correlation = self._calculate_correlation(series1, series2)

                    if correlation and abs(correlation.correlation_coefficient) >= self.min_correlation:
                        correlations.append(correlation)

                except Exception as e:
                    logger.error(f"Failed to calculate correlation between {name1} and {name2}: {e}")

        return correlations

    def _calculate_correlation(
        self,
        series1: list[tuple[datetime, float]],
        series2: list[tuple[datetime, float]],
    ) -> Correlation | None:
        """Calculate correlation between two time series."""
        try:
            # Align time series (find common time points)
            dict1 = dict(series1),
            dict2 = dict(series2),

            common_times = set(dict1.keys()) & set(dict2.keys())

            if len(common_times) < 10:
                return None

            values1 = [dict1[ts] for ts in sorted(common_times)],
            values2 = [dict2[ts] for ts in sorted(common_times)]

            # Calculate Pearson correlation
            if len(values1) < 2:
                return None

            mean1 = sum(values1) / len(values1),
            mean2 = sum(values2) / len(values2),

            numerator = sum((v1 - mean1) * (v2 - mean2) for v1, v2 in zip(values1, values2, strict=False))

            sum_sq1 = sum((v1 - mean1) ** 2 for v1 in values1),
            sum_sq2 = sum((v2 - mean2) ** 2 for v2 in values2),

            denominator = (sum_sq1 * sum_sq2) ** 0.5

            if denominator == 0:
                return None

            correlation_coef = numerator / denominator

            # Simple p-value estimation (not statistically rigorous)
            n = len(values1),
            t_stat = correlation_coef * ((n - 2) / (1 - correlation_coef**2)) ** 0.5,
            p_value = min(0.05, abs(t_stat) / 10)  # Rough approximation

            # Determine strength
            abs_corr = abs(correlation_coef)
            if abs_corr >= 0.8:
                strength = "strong"
            elif abs_corr >= 0.6:
                strength = "moderate"
            else:
                strength = "weak"

            # Generate description
            direction = "positive" if correlation_coef > 0 else "negative",
            description = f"{strength.title()} {direction} correlation detected"

            return Correlation(
                metric1=series1[0][0] if series1 else "unknown",  # This needs to be fixed,
                metric2=series2[0][0] if series2 else "unknown",  # This needs to be fixed,
                correlation_coefficient=correlation_coef,
                p_value=p_value,
                strength=strength,
                description=description,
            )

        except Exception as e:
            logger.error(f"Failed to calculate correlation: {e}")
            return None


class InsightGenerator:
    """Generates high-level insights from analytics results.

    Combines trends, anomalies, and correlations into
    actionable strategic recommendations.
    """

    def __init__(self, analytics: AnalyticsEngine):
        self.analytics = analytics

    async def generate_insights_async(self, hours: int = 24) -> list[Insight]:
        """Generate comprehensive insights from recent data."""
        insights = []

        # Get analytics results
        trends = await self.analytics.analyze_trends_async(hours=hours),
        anomalies = await self.analytics.detect_anomalies_async(hours=hours),
        correlations = await self.analytics.find_correlations_async(hours=hours)

        # Generate performance insights
        performance_insights = self._generate_performance_insights(trends, anomalies)
        insights.extend(performance_insights)

        # Generate cost insights
        cost_insights = self._generate_cost_insights(trends, anomalies)
        insights.extend(cost_insights)

        # Generate security insights
        security_insights = self._generate_security_insights(anomalies)
        insights.extend(security_insights)

        # Generate quality insights
        quality_insights = self._generate_quality_insights(trends)
        insights.extend(quality_insights)

        # Generate correlation-based insights
        correlation_insights = self._generate_correlation_insights(correlations)
        insights.extend(correlation_insights)

        # Sort by severity and confidence
        insights.sort(
            key=lambda i: (
                {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}[i.severity.value],
                i.confidence,
            ),
            reverse=True,
        )

        return insights

    def _generate_performance_insights(self, trends: list[TrendAnalysis], anomalies: list[Anomaly]) -> list[Insight]:
        """Generate performance-related insights."""
        insights = []

        # Check for performance degradation trends
        perf_trends = [
            t for t in trends if "performance" in t.metric_name.lower() or "response" in t.metric_name.lower()
        ]

        for trend in perf_trends:
            if trend.direction == TrendDirection.DEGRADING and trend.confidence > 0.7:
                insight = Insight(
                    title=f"Performance Degradation Detected: {trend.metric_name}",
                    description=f"Performance has degraded by {trend.change_rate:.1f}% over the last {trend.time_period}",
                    severity=SeverityLevel.HIGH if abs(trend.change_rate) > 20 else SeverityLevel.MEDIUM,
                    category="performance",
                    supporting_metrics=[trend.metric_name],
                    trends=[trend],
                    recommended_actions=[
                        "Profile application performance",
                        "Check resource utilization",
                        "Review recent code changes",
                        "Consider scaling resources",
                    ],
                    confidence=trend.confidence,
                    urgency="high" if abs(trend.change_rate) > 30 else "medium",
                )
                insights.append(insight)

        # Check for performance anomalies
        perf_anomalies = [a for a in anomalies if "performance" in a.metric_name.lower()]

        if len(perf_anomalies) > 3:  # Multiple performance anomalies
            insight = Insight(
                title="Multiple Performance Anomalies Detected",
                description=f"Detected {len(perf_anomalies)} performance anomalies in the last period",
                severity=SeverityLevel.HIGH,
                category="performance",
                supporting_metrics=[a.metric_name for a in perf_anomalies],
                anomalies=perf_anomalies,
                recommended_actions=[
                    "Investigate system-wide performance issues",
                    "Check for resource bottlenecks",
                    "Review infrastructure health",
                    "Consider emergency scaling",
                ],
                confidence=0.9,
                urgency="high",
            )
            insights.append(insight)

        return insights

    def _generate_cost_insights(self, trends: list[TrendAnalysis], anomalies: list[Anomaly]) -> list[Insight]:
        """Generate cost-related insights."""
        insights = []

        # Check for cost trends
        cost_trends = [t for t in trends if "cost" in t.metric_name.lower()]

        for trend in cost_trends:
            if trend.direction == TrendDirection.DEGRADING and trend.confidence > 0.6:
                # For costs, degrading means increasing
                if trend.change_rate > 25:  # More than 25% increase
                    insight = Insight(
                        title=f"Significant Cost Increase: {trend.metric_name}",
                        description=f"Costs have increased by {trend.change_rate:.1f}% over {trend.time_period}",
                        severity=SeverityLevel.HIGH,
                        category="cost",
                        supporting_metrics=[trend.metric_name],
                        trends=[trend],
                        recommended_actions=[
                            "Review usage patterns",
                            "Optimize AI model selection",
                            "Implement cost controls",
                            "Analyze cost drivers",
                        ],
                        estimated_impact=f"Potential monthly savings: ${trend.current_value * 0.3:.2f}",
                        confidence=trend.confidence,
                        urgency="high",
                    )
                    insights.append(insight)

        return insights

    def _generate_security_insights(self, anomalies: list[Anomaly]) -> list[Insight]:
        """Generate security-related insights."""
        insights = []

        # Check for security-related anomalies
        security_anomalies = [
            a for a in anomalies if "error" in a.metric_name.lower() or "security" in a.metric_name.lower()
        ]

        if security_anomalies:
            insight = Insight(
                title="Security Anomalies Detected",
                description=f"Detected {len(security_anomalies)} security-related anomalies",
                severity=SeverityLevel.HIGH,
                category="security",
                supporting_metrics=[a.metric_name for a in security_anomalies],
                anomalies=security_anomalies,
                recommended_actions=[
                    "Review security logs",
                    "Check for unauthorized access",
                    "Validate system integrity",
                    "Update security monitoring",
                ],
                confidence=0.8,
                urgency="high",
            )
            insights.append(insight)

        return insights

    def _generate_quality_insights(self, trends: list[TrendAnalysis]) -> list[Insight]:
        """Generate code quality insights."""
        insights = []

        # Check for code quality trends
        quality_trends = [
            t for t in trends if "quality" in t.metric_name.lower() or "violation" in t.metric_name.lower()
        ]

        for trend in quality_trends:
            if trend.direction == TrendDirection.DEGRADING:
                insight = Insight(
                    title=f"Code Quality Degradation: {trend.metric_name}",
                    description=f"Code quality metrics show {trend.change_rate:.1f}% degradation",
                    severity=SeverityLevel.MEDIUM,
                    category="quality",
                    supporting_metrics=[trend.metric_name],
                    trends=[trend],
                    recommended_actions=[
                        "Review recent code changes",
                        "Increase code review coverage",
                        "Run architectural validation",
                        "Update development guidelines",
                    ],
                    confidence=trend.confidence,
                )
                insights.append(insight)

        return insights

    def _generate_correlation_insights(self, correlations: list[Correlation]) -> list[Insight]:
        """Generate insights from correlations."""
        insights = []

        # Look for strong correlations that might indicate causation
        strong_correlations = [c for c in correlations if c.strength == "strong"]

        for correlation in strong_correlations:
            if "cost" in correlation.metric1.lower() and "usage" in correlation.metric2.lower():
                insight = Insight(
                    title="Cost-Usage Correlation Identified",
                    description=f"Strong correlation ({correlation.correlation_coefficient:.2f}) between cost and usage metrics",
                    severity=SeverityLevel.INFO,
                    category="cost",
                    supporting_metrics=[correlation.metric1, correlation.metric2],
                    correlations=[correlation],
                    recommended_actions=[
                        "Implement usage-based cost controls",
                        "Set up predictive cost alerts",
                        "Optimize high-usage operations",
                    ],
                    confidence=0.7,
                )
                insights.append(insight)

        return insights
