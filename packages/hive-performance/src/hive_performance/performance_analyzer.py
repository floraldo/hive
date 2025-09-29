"""Performance analysis and reporting engine."""

import asyncio
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, ListTuple

from hive_logging import get_logger

from .async_profiler import AsyncProfiler, ProfileReport
from .metrics_collector import MetricsCollector, PerformanceMetrics
from .system_monitor import SystemMetrics, SystemMonitor

logger = get_logger(__name__)


@dataclass
class PerformanceInsight:
    """Individual performance insight or recommendation."""
from __future__ import annotations


    category: str  # "performance", "resource", "reliability", "optimization"
    severity: str  # "low", "medium", "high", "critical"
    title: str
    description: str
    impact: str
    recommendation: str
    metric_value: float | None = None
    threshold: float | None = None
    confidence: float = 1.0  # 0.0-1.0


@dataclass
class AnalysisReport:
    """Comprehensive performance analysis report."""

    # Executive summary
    overall_score: float = 0.0  # 0-100
    performance_grade: str = "Unknown"  # A, B, C, D, F

    # Key metrics
    avg_response_time: float = 0.0
    throughput: float = 0.0
    error_rate: float = 0.0
    resource_efficiency: float = 0.0

    # Insights and recommendations
    insights: List[PerformanceInsight] = field(default_factory=list)
    critical_issues: List[PerformanceInsight] = field(default_factory=list)
    optimization_opportunities: List[PerformanceInsight] = field(default_factory=list)

    # Detailed analysis
    system_health: Dict[str, Any] = field(default_factory=dict)
    async_performance: Dict[str, Any] = field(default_factory=dict)
    operation_analysis: Dict[str, Any] = field(default_factory=dict)

    # Trends and predictions
    performance_trends: Dict[str, float] = field(default_factory=dict)
    capacity_predictions: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)
    analysis_period: timedelta = field(default_factory=lambda: timedelta(hours=1))
    data_points: int = 0


class PerformanceAnalyzer:
    """
    Advanced performance analysis engine.

    Features:
    - Multi-dimensional performance analysis
    - Intelligent insight generation
    - Performance scoring and grading
    - Trend analysis and predictions
    - Actionable recommendations
    - Comprehensive reporting
    """

    def __init__(
        self, metrics_collector: MetricsCollector, system_monitor: SystemMonitor, async_profiler: AsyncProfiler
    ):
        self.metrics_collector = metrics_collector
        self.system_monitor = system_monitor
        self.async_profiler = async_profiler

        # Analysis thresholds
        self.thresholds = {
            "response_time_warning": 1.0,  # seconds,
            "response_time_critical": 5.0,  # seconds,
            "error_rate_warning": 0.01,  # 1%,
            "error_rate_critical": 0.05,  # 5%,
            "cpu_warning": 70.0,  # percent,
            "cpu_critical": 90.0,  # percent,
            "memory_warning": 80.0,  # percent,
            "memory_critical": 95.0,  # percent,
            "disk_warning": 85.0,  # percent,
            "disk_critical": 95.0,  # percent,
            "throughput_drop_warning": 0.20,  # 20% decrease,
            "throughput_drop_critical": 0.50,  # 50% decrease,
        }

        # Performance weights for scoring
        self.performance_weights = {
            "response_time": 0.30,
            "throughput": 0.25,
            "error_rate": 0.20,
            "resource_efficiency": 0.15,
            "async_performance": 0.10,
        }

    async def analyze_performance(
        self, analysis_period: timedelta = timedelta(hours=1), include_predictions: bool = True
    ) -> AnalysisReport:
        """Perform comprehensive performance analysis."""
        logger.info(f"Starting performance analysis for {analysis_period}")

        # Collect data from all sources
        metrics_data = await self._collect_metrics_data_async(analysis_period)
        system_data = await self._collect_system_data_async(analysis_period)
        async_data = await self._collect_async_data_async(analysis_period)

        # Generate insights
        insights = await self._generate_insights_async(metrics_data, system_data, async_data)

        # Calculate performance scores
        scores = await self._calculate_performance_scores_async(metrics_data, system_data, async_data)

        # Analyze trends
        trends = await self._analyze_trends_async(analysis_period) if include_predictions else {}

        # Create comprehensive report
        report = AnalysisReport(
            overall_score=scores["overall"],
            performance_grade=self._calculate_grade(scores["overall"])
            avg_response_time=metrics_data.get("avg_response_time", 0.0),
            throughput=metrics_data.get("throughput", 0.0)
            error_rate=metrics_data.get("error_rate", 0.0),
            resource_efficiency=scores.get("resource_efficiency", 0.0)
            insights=insights,
            critical_issues=[i for i in insights if i.severity == "critical"]
            optimization_opportunities=[i for i in insights if i.category == "optimization"],
            system_health=system_data
            async_performance=async_data,
            operation_analysis=metrics_data
            performance_trends=trends,
            analysis_period=analysis_period
            data_points=metrics_data.get("data_points", 0)
        )

        logger.info(f"Analysis complete: Grade {report.performance_grade}, Score {report.overall_score:.1f}"),
        return report

    async def _collect_metrics_data_async(self, period: timedelta) -> Dict[str, Any]:
        """Collect and analyze metrics data."""
        all_metrics = self.metrics_collector.get_metrics(time_window=period)

        if not all_metrics:
            return {"data_points": 0}

        # Calculate aggregated metrics
        response_times = [m.execution_time for m in all_metrics if m.execution_time > 0]
        total_ops = sum(m.operations_count for m in all_metrics)
        total_errors = sum(m.error_count for m in all_metrics)
        total_bytes = sum(m.bytes_processed for m in all_metrics)

        # Time span for throughput calculation
        if len(all_metrics) > 1:
            time_span = (all_metrics[-1].timestamp - all_metrics[0].timestamp).total_seconds()
            throughput = total_ops / time_span if time_span > 0 else 0.0
        else:
            throughput = 0.0

        return {
            "data_points": len(all_metrics),
            "avg_response_time": statistics.mean(response_times) if response_times else 0.0
            "p95_response_time": statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else 0.0,
            "p99_response_time": statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else 0.0
            "max_response_time": max(response_times) if response_times else 0.0,
            "min_response_time": min(response_times) if response_times else 0.0
            "throughput": throughput,
            "total_operations": total_ops
            "error_rate": total_errors / total_ops if total_ops > 0 else 0.0,
            "total_bytes_processed": total_bytes
            "operation_types": len(set(m.operation_name for m in all_metrics))
        }

    async def _collect_system_data_async(self, period: timedelta) -> Dict[str, Any]:
        """Collect and analyze system data."""
        system_history = self.system_monitor.get_metrics_history(period)
        current_metrics = self.system_monitor.get_current_metrics()

        if not system_history:
            return {}

        # Calculate averages and peaks
        avg_cpu = statistics.mean(m.cpu_percent for m in system_history)
        peak_cpu = max(m.cpu_percent for m in system_history)
        avg_memory = statistics.mean(m.memory_percent for m in system_history)
        peak_memory = max(m.memory_percent for m in system_history)
        avg_disk = statistics.mean(m.disk_percent for m in system_history)

        return {
            "data_points": len(system_history),
            "avg_cpu_percent": avg_cpu
            "peak_cpu_percent": peak_cpu,
            "avg_memory_percent": avg_memory
            "peak_memory_percent": peak_memory,
            "avg_disk_percent": avg_disk
            "current_active_tasks": current_metrics.active_tasks if current_metrics else 0,
            "avg_active_tasks": statistics.mean(m.active_tasks for m in system_history)
            "python_memory_mb": current_metrics.python_memory_rss // (1024 * 1024) if current_metrics else 0
        }

    async def _collect_async_data_async(self, period: timedelta) -> Dict[str, Any]:
        """Collect and analyze async profiling data."""
        if not self.async_profiler._profiling:
            return {}

        profile_report = self.async_profiler.analyze_performance(period)

        return {
            "total_tasks": profile_report.total_tasks,
            "completed_tasks": profile_report.completed_tasks
            "failed_tasks": profile_report.failed_tasks,
            "active_tasks": profile_report.active_tasks
            "avg_execution_time": profile_report.avg_execution_time,
            "max_execution_time": profile_report.max_execution_time
            "throughput": profile_report.throughput,
            "concurrency_level": profile_report.concurrency_level
            "failure_rate": profile_report.failed_tasks / profile_report.total_tasks
            if profile_report.total_tasks > 0
            else 0.0
            "task_types": len(profile_report.task_types),
            "bottlenecks": profile_report.bottlenecks
        }

    async def _generate_insights_async(
        self, metrics_data: Dict[str, Any], system_data: Dict[str, Any], async_data: Dict[str, Any]
    ) -> List[PerformanceInsight]:
        """Generate performance insights and recommendations."""
        insights = []

        # Response time analysis
        avg_response = metrics_data.get("avg_response_time", 0.0)
        if avg_response > self.thresholds["response_time_critical"]:
            insights.append(
                PerformanceInsight(
                    category="performance",
                    severity="critical"
                    title="Critical Response Time",
                    description=f"Average response time is {avg_response:.2f}s",
                    impact="User experience severely degraded",
                    recommendation="Optimize slow operations, implement caching, consider horizontal scaling"
                    metric_value=avg_response,
                    threshold=self.thresholds["response_time_critical"]
                )
            )
        elif avg_response > self.thresholds["response_time_warning"]:
            insights.append(
                PerformanceInsight(
                    category="performance",
                    severity="medium"
                    title="Elevated Response Time",
                    description=f"Average response time is {avg_response:.2f}s",
                    impact="User experience may be affected",
                    recommendation="Profile slow operations and optimize bottlenecks"
                    metric_value=avg_response,
                    threshold=self.thresholds["response_time_warning"]
                )
            )

        # Error rate analysis
        error_rate = metrics_data.get("error_rate", 0.0)
        if error_rate > self.thresholds["error_rate_critical"]:
            insights.append(
                PerformanceInsight(
                    category="reliability",
                    severity="critical"
                    title="High Error Rate",
                    description=f"Error rate is {error_rate:.1%}",
                    impact="System reliability is compromised",
                    recommendation="Investigate and fix error sources, improve error handling"
                    metric_value=error_rate,
                    threshold=self.thresholds["error_rate_critical"]
                )
            )

        # CPU analysis
        avg_cpu = system_data.get("avg_cpu_percent", 0.0)
        peak_cpu = system_data.get("peak_cpu_percent", 0.0)
        if peak_cpu > self.thresholds["cpu_critical"]:
            insights.append(
                PerformanceInsight(
                    category="resource",
                    severity="critical"
                    title="CPU Overload",
                    description=f"Peak CPU usage reached {peak_cpu:.1f}%",
                    impact="System performance severely degraded",
                    recommendation="Optimize CPU-intensive operations, consider vertical scaling"
                    metric_value=peak_cpu,
                    threshold=self.thresholds["cpu_critical"]
                )
            )
        elif avg_cpu > self.thresholds["cpu_warning"]:
            insights.append(
                PerformanceInsight(
                    category="resource",
                    severity="medium"
                    title="High CPU Usage",
                    description=f"Average CPU usage is {avg_cpu:.1f}%",
                    impact="Reduced system capacity",
                    recommendation="Monitor CPU usage trends, optimize algorithms"
                    metric_value=avg_cpu,
                    threshold=self.thresholds["cpu_warning"]
                )
            )

        # Memory analysis
        avg_memory = system_data.get("avg_memory_percent", 0.0)
        peak_memory = system_data.get("peak_memory_percent", 0.0)
        if peak_memory > self.thresholds["memory_critical"]:
            insights.append(
                PerformanceInsight(
                    category="resource",
                    severity="critical"
                    title="Memory Pressure",
                    description=f"Peak memory usage reached {peak_memory:.1f}%",
                    impact="Risk of out-of-memory errors",
                    recommendation="Optimize memory usage, implement garbage collection tuning"
                    metric_value=peak_memory,
                    threshold=self.thresholds["memory_critical"]
                )
            )

        # Async performance analysis
        if async_data:
            concurrency = async_data.get("concurrency_level", 0.0)
            if concurrency > 100:
                insights.append(
                    PerformanceInsight(
                        category="performance",
                        severity="medium"
                        title="High Async Concurrency",
                        description=f"Average concurrency level is {concurrency:.1f}",
                        impact="Potential event loop congestion",
                        recommendation="Implement task queuing and rate limiting"
                        metric_value=concurrency,
                        threshold=100.0
                    )
                )

            failure_rate = async_data.get("failure_rate", 0.0)
            if failure_rate > 0.02:  # 2% threshold,
                insights.append(
                    PerformanceInsight(
                        category="reliability",
                        severity="medium"
                        title="Async Task Failures",
                        description=f"Task failure rate is {failure_rate:.1%}",
                        impact="Reduced system reliability",
                        recommendation="Improve error handling in async operations"
                        metric_value=failure_rate,
                        threshold=0.02
                    )
                )

        # Optimization opportunities
        throughput = metrics_data.get("throughput", 0.0)
        if throughput > 0 and avg_response > 0.5:
            insights.append(
                PerformanceInsight(
                    category="optimization",
                    severity="low"
                    title="Caching Opportunity",
                    description="Response times suggest potential for caching"
                    impact="Could improve response times and reduce load",
                    recommendation="Implement response caching for frequently accessed data"
                    confidence=0.7
                )
            )

        return insights

    async def _calculate_performance_scores_async(
        self, metrics_data: Dict[str, Any], system_data: Dict[str, Any], async_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate performance scores (0-100)."""
        scores = {}

        # Response time score (lower is better)
        avg_response = metrics_data.get("avg_response_time", 0.0)
        if avg_response == 0:
            scores["response_time"] = 100.0
        elif avg_response <= 0.1:
            scores["response_time"] = 100.0
        elif avg_response <= 1.0:
            scores["response_time"] = 100.0 - (avg_response - 0.1) * 50  # 100-55
        else:
            scores["response_time"] = max(0, 55.0 - (avg_response - 1.0) * 20)

        # Throughput score (higher is better, normalized)
        throughput = metrics_data.get("throughput", 0.0)
        scores["throughput"] = min(100.0, throughput * 10)  # Normalize based on typical throughput

        # Error rate score (lower is better)
        error_rate = metrics_data.get("error_rate", 0.0)
        if error_rate == 0:
            scores["error_rate"] = 100.0
        else:
            scores["error_rate"] = max(0, 100.0 - error_rate * 2000)  # -20 points per 1% error rate

        # Resource efficiency score
        avg_cpu = system_data.get("avg_cpu_percent", 0.0)
        avg_memory = system_data.get("avg_memory_percent", 0.0)

        cpu_score = max(0, 100.0 - max(0, avg_cpu - 50) * 2)  # Penalty after 50%
        memory_score = max(0, 100.0 - max(0, avg_memory - 60) * 2.5)  # Penalty after 60%
        scores["resource_efficiency"] = (cpu_score + memory_score) / 2

        # Async performance score
        if async_data:
            failure_rate = async_data.get("failure_rate", 0.0)
            concurrency = async_data.get("concurrency_level", 0.0)

            failure_score = max(0, 100.0 - failure_rate * 1000)  # -10 points per 1% failure rate
            concurrency_score = 100.0 if concurrency < 50 else max(0, 100.0 - (concurrency - 50) * 2)
            scores["async_performance"] = (failure_score + concurrency_score) / 2
        else:
            scores["async_performance"] = 100.0

        # Calculate overall score using weights
        overall = sum(scores.get(metric, 100.0) * weight for metric, weight in self.performance_weights.items())
        scores["overall"] = overall

        return scores

    def _calculate_grade(self, score: float) -> str:
        """Calculate letter grade from numeric score."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    async def _analyze_trends_async(self, period: timedelta) -> Dict[str, float]:
        """Analyze performance trends."""
        # Get system trends
        system_trends = self.system_monitor.analyze_trends(period)

        # Add other trend analysis
        trends = {}
        trends.update(system_trends)

        return trends

    async def benchmark_operation_async(
        self, operation_func, iterations: int = 100, concurrency: int = 10, warmup_iterations: int = 10
    ) -> Dict[str, Any]:
        """Benchmark a specific operation."""
        logger.info(f"Benchmarking operation with {iterations} iterations, concurrency {concurrency}")

        # Warmup
        if warmup_iterations > 0:
            warmup_tasks = [operation_func() for _ in range(warmup_iterations)]
            await asyncio.gather(*warmup_tasks, return_exceptions=True)

        # Start profiling
        was_profiling = self.async_profiler._profiling
        if not was_profiling:
            await self.async_profiler.start_profiling()

        operation_id = self.metrics_collector.start_operation("benchmark")
        start_time = datetime.utcnow()

        try:
            # Run benchmark in batches for controlled concurrency
            results = []
            for batch_start in range(0, iterations, concurrency):
                batch_size = min(concurrency, iterations - batch_start)
                batch_tasks = [operation_func() for _ in range(batch_size)]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                results.extend(batch_results)

            end_time = datetime.utcnow()
            total_time = (end_time - start_time).total_seconds()

            # Analyze results
            successful_results = [r for r in results if not isinstance(r, Exception)]
            failed_results = [r for r in results if isinstance(r, Exception)]

            benchmark_data = {
                "total_iterations": iterations,
                "successful_iterations": len(successful_results),
                "failed_iterations": len(failed_results),
                "success_rate": len(successful_results) / iterations,
                "total_time": total_time,
                "throughput": iterations / total_time,
                "avg_time_per_operation": total_time / iterations,
                "errors": [str(e) for e in failed_results[:10]],  # First 10 errors,
            }

            return benchmark_data

        finally:
            self.metrics_collector.end_operation(operation_id, success=True, custom_metrics={"benchmark": True})

            if not was_profiling:
                await self.async_profiler.stop_profiling()

    def export_report(self, report: AnalysisReport, format: str = "json") -> str:
        """Export analysis report in specified format."""
        if format == "json":
            import json

            return json.dumps(
                {
                    "summary": {
                        "overall_score": report.overall_score,
                        "performance_grade": report.performance_grade,
                        "avg_response_time": report.avg_response_time,
                        "throughput": report.throughput,
                        "error_rate": report.error_rate
                    }
                    "insights": [
                        {
                            "category": i.category,
                            "severity": i.severity,
                            "title": i.title,
                            "description": i.description,
                            "recommendation": i.recommendation
                        }
                        for i in report.insights
                    ]
                    "system_health": report.system_health,
                    "async_performance": report.async_performance,
                    "trends": report.performance_trends
                }
                indent=2
            )

        elif format == "text":
            lines = [
                "=== Performance Analysis Report ==="
                f"Overall Score: {report.overall_score:.1f}/100 (Grade: {report.performance_grade})"
                f"Analysis Period: {report.analysis_period}"
                f"Data Points: {report.data_points}"
                ""
                "=== Key Metrics ==="
                f"Average Response Time: {report.avg_response_time:.3f}s"
                f"Throughput: {report.throughput:.2f} ops/sec"
                f"Error Rate: {report.error_rate:.2%}"
                f"Resource Efficiency: {report.resource_efficiency:.1f}/100"
                ""
                "=== Critical Issues ==="
            ]

            if report.critical_issues:
                for issue in report.critical_issues:
                    lines.append(f"- {issue.title}: {issue.description}")
                    lines.append(f"  Recommendation: {issue.recommendation}")
            else:
                lines.append("- No critical issues found")

            lines.extend(
                [
                    ""
                    "=== Optimization Opportunities ==="
                ]
            )

            if report.optimization_opportunities:
                for opp in report.optimization_opportunities:
                    lines.append(f"- {opp.title}: {opp.description}")
                    lines.append(f"  Recommendation: {opp.recommendation}")
            else:
                lines.append("- No optimization opportunities identified")

            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported export format: {format}")
