"""Integrated monitoring service orchestrating all performance components.

# golden-rule-ignore: package-app-discipline - This is infrastructure orchestration, not business logic
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from hive_logging import get_logger

from .async_profiler import AsyncProfiler
from .metrics_collector import MetricsCollector
from .performance_analyzer import AnalysisReport, PerformanceAnalyzer
from .system_monitor import SystemMonitor

logger = get_logger(__name__)


class MonitoringService:
    """
    Comprehensive monitoring service for Hive platform.

    Features:
    - Integrated performance monitoring
    - Automated analysis and reporting
    - Real-time alerting
    - Performance optimization recommendations
    - Configurable monitoring intervals
    - Export capabilities
    """

    def __init__(
        self,
        collection_interval: float = 1.0,
        analysis_interval: float = 300.0,  # 5 minutes,
        enable_profiling: bool = True,
        enable_alerts: bool = True,
        max_history_hours: int = 24,
    ):
        self.collection_interval = collection_interval
        self.analysis_interval = analysis_interval
        self.enable_profiling = enable_profiling
        self.enable_alerts = enable_alerts
        self.max_history_hours = max_history_hours

        # Initialize components
        max_history_points = int(max_history_hours * 3600 / collection_interval)

        self.metrics_collector = MetricsCollector(
            collection_interval=collection_interval,
            max_history=max_history_points,
        )

        self.system_monitor = SystemMonitor(
            collection_interval=collection_interval,
            max_history=max_history_points,
            enable_alerts=enable_alerts,
        )

        self.async_profiler = AsyncProfiler(
            max_task_history=max_history_points // 10,  # Less frequent task storage,
            enable_stack_traces=False,  # Disabled for performance,
            sample_rate=0.1,  # 10% sampling for performance
        )

        self.performance_analyzer = PerformanceAnalyzer(
            self.metrics_collector,
            self.system_monitor,
            self.async_profiler,
        )

        # Service state
        self._monitoring = (False,)
        self._analysis_task: asyncio.Task | None = (None,)
        self._alert_callbacks: list[Callable] = []

        # Analysis history
        self._analysis_history: list[AnalysisReport] = []

    async def start_monitoring_async(self) -> None:
        """Start comprehensive monitoring."""
        if self._monitoring:
            logger.warning("Monitoring already started")
            return

        logger.info("Starting comprehensive monitoring service")
        self._monitoring = True

        try:
            # Start all monitoring components
            await self.metrics_collector.start_collection()
            await self.system_monitor.start_monitoring_async()

            if self.enable_profiling:
                await self.async_profiler.start_profiling()

            # Start analysis task
            self._analysis_task = asyncio.create_task(self._analysis_loop_async())

            logger.info("Monitoring service started successfully")

        except Exception as e:
            logger.error(f"Failed to start monitoring service: {e}")
            await self.stop_monitoring_async()
            raise

    async def stop_monitoring_async(self) -> None:
        """Stop all monitoring."""
        if not self._monitoring:
            return

        logger.info("Stopping monitoring service")
        self._monitoring = False

        # Stop analysis task
        if self._analysis_task:
            (self._analysis_task.cancel(),)
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass

        # Stop all components
        await self.metrics_collector.stop_collection()
        await self.system_monitor.stop_monitoring_async()

        if self.enable_profiling:
            await self.async_profiler.stop_profiling()

        logger.info("Monitoring service stopped")

    async def _analysis_loop_async(self) -> None:
        """Periodic analysis and reporting loop."""
        while self._monitoring:
            try:
                await asyncio.sleep(self.analysis_interval)

                if not self._monitoring:
                    break

                # Perform analysis
                analysis_period = timedelta(seconds=self.analysis_interval * 2)  # Analyze last 2 intervals
                report = await self.performance_analyzer.analyze_performance(analysis_period)

                # Store analysis
                self._analysis_history.append(report)

                # Keep only recent analyses (last 24 hours)
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                self._analysis_history = [r for r in self._analysis_history if r.analysis_timestamp >= cutoff_time]

                # Check for alerts
                if self.enable_alerts:
                    await self._check_analysis_alerts_async(report)

                logger.debug(f"Analysis complete: Grade {report.performance_grade}, Score {report.overall_score:.1f}")

            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def _check_analysis_alerts_async(self, report: AnalysisReport) -> None:
        """Check analysis results for alert conditions."""
        alert_conditions = []

        # Critical performance score
        if report.overall_score < 60:
            alert_conditions.append(f"Critical performance score: {report.overall_score:.1f}/100")

        # Critical issues
        if report.critical_issues:
            for issue in report.critical_issues:
                alert_conditions.append(f"Critical issue: {issue.title}")

        # High error rate
        if report.error_rate > 0.05:  # 5%
            alert_conditions.append(f"High error rate: {report.error_rate:.1%}")

        # Slow response times
        if report.avg_response_time > 5.0:
            alert_conditions.append(f"Slow response times: {report.avg_response_time:.2f}s")

        if alert_conditions:
            await self._trigger_alerts_async(alert_conditions, report)

    async def _trigger_alerts_async(self, conditions: list[str], report: AnalysisReport) -> None:
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    (await callback(conditions, report),)
                else:
                    callback(conditions, report)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    def add_alert_callback(self, callback: Callable) -> None:
        """Add alert callback function."""
        self._alert_callbacks.append(callback)
        logger.info(f"Added alert callback: {callback.__name__}")

    def get_current_status(self) -> dict[str, Any]:
        """Get current monitoring status."""
        current_metrics = self.system_monitor.get_current_metrics()
        latest_analysis = self._analysis_history[-1] if self._analysis_history else None

        return {
            "monitoring_active": self._monitoring,
            "profiling_enabled": self.enable_profiling,
            "alerts_enabled": self.enable_alerts,
            "collection_interval": self.collection_interval,
            "analysis_interval": self.analysis_interval,
            "current_system_metrics": (
                {
                    "cpu_percent": current_metrics.cpu_percent if current_metrics else 0.0,
                    "memory_percent": current_metrics.memory_percent if current_metrics else 0.0,
                    "active_tasks": current_metrics.active_tasks if current_metrics else 0,
                }
                if current_metrics
                else {}
            ),
            "latest_analysis": (
                {
                    "overall_score": latest_analysis.overall_score,
                    "performance_grade": latest_analysis.performance_grade,
                    "avg_response_time": latest_analysis.avg_response_time,
                    "error_rate": latest_analysis.error_rate,
                    "critical_issues_count": len(latest_analysis.critical_issues),
                }
                if latest_analysis
                else {}
            ),
            "analysis_history_count": len(self._analysis_history),
        }

    async def get_health_check_async(self) -> dict[str, Any]:
        """Get comprehensive health check."""
        status = self.get_current_status()
        current_metrics = self.system_monitor.get_current_metrics()

        # Determine health status
        health_status = "healthy"
        health_issues = []

        if not self._monitoring:
            health_status = "unhealthy"
            health_issues.append("Monitoring not active")

        if current_metrics:
            if current_metrics.cpu_percent > 90:
                health_status = "degraded"
                health_issues.append(f"High CPU usage: {current_metrics.cpu_percent:.1f}%")

            if current_metrics.memory_percent > 95:
                health_status = "unhealthy"
                health_issues.append(f"Critical memory usage: {current_metrics.memory_percent:.1f}%")

        latest_analysis = self._analysis_history[-1] if self._analysis_history else None
        if latest_analysis:
            if latest_analysis.overall_score < 60:
                health_status = "degraded"
                health_issues.append(f"Poor performance score: {latest_analysis.overall_score:.1f}")

            if latest_analysis.critical_issues:
                health_status = "degraded"
                health_issues.append(f"{len(latest_analysis.critical_issues)} critical issues")

        return {
            "status": health_status,
            "timestamp": datetime.utcnow().isoformat(),
            "monitoring_active": self._monitoring,
            "issues": health_issues,
            "metrics": status,
        }

    async def generate_report_async(
        self,
        time_window: timedelta | None = None,
        include_recommendations: bool = True,
    ) -> AnalysisReport:
        """Generate comprehensive performance report."""
        if time_window is None:
            time_window = timedelta(hours=1)

        return await self.performance_analyzer.analyze_performance(
            analysis_period=time_window,
            include_predictions=include_recommendations,
        )

    async def benchmark_system_async(
        self,
        operation_func: Callable,
        iterations: int = 100,
        concurrency: int = 10,
    ) -> dict[str, Any]:
        """Run system benchmark."""
        logger.info(f"Starting system benchmark: {iterations} iterations, concurrency {concurrency}")

        # Ensure monitoring is active
        was_monitoring = self._monitoring
        if not was_monitoring:
            await self.start_monitoring_async()
            await asyncio.sleep(2)  # Let monitoring stabilize

        try:
            # Run benchmark
            benchmark_results = await self.performance_analyzer.benchmark_operation(
                operation_func,
                iterations=iterations,
                concurrency=concurrency,
            )

            # Get system metrics during benchmark
            system_metrics = self.system_monitor.get_current_metrics()

            return {
                "benchmark_results": benchmark_results,
                "system_metrics_during_benchmark": (
                    {
                        "cpu_percent": system_metrics.cpu_percent if system_metrics else 0.0,
                        "memory_percent": system_metrics.memory_percent if system_metrics else 0.0,
                        "active_tasks": system_metrics.active_tasks if system_metrics else 0,
                    }
                    if system_metrics
                    else {}
                ),
                "timestamp": datetime.utcnow().isoformat(),
            }

        finally:
            if not was_monitoring:
                await self.stop_monitoring_async()

    def get_analysis_history(
        self,
        time_window: timedelta | None = None,
        limit: int | None = None,
    ) -> list[AnalysisReport]:
        """Get historical analysis reports."""
        reports = self._analysis_history.copy()

        if time_window:
            cutoff_time = datetime.utcnow() - time_window
            reports = [r for r in reports if r.analysis_timestamp >= cutoff_time]

        if limit:
            reports = reports[-limit:]

        return reports

    def get_performance_trends(self, days: int = 7) -> dict[str, Any]:
        """Get performance trends over specified days."""
        time_window = timedelta(days=days)
        historical_reports = self.get_analysis_history(time_window)

        if len(historical_reports) < 2:
            return {"insufficient_data": True}

        # Calculate trends
        scores = [r.overall_score for r in historical_reports]
        response_times = [r.avg_response_time for r in historical_reports]
        error_rates = [r.error_rate for r in historical_reports]
        throughputs = [r.throughput for r in historical_reports]

        def calculate_trend(values: list[float]) -> float:
            if len(values) < 2:
                return 0.0
            return (values[-1] - values[0]) / len(values)

        return {
            "period_days": days,
            "data_points": len(historical_reports),
            "score_trend": calculate_trend(scores),
            "response_time_trend": calculate_trend(response_times),
            "error_rate_trend": calculate_trend(error_rates),
            "throughput_trend": calculate_trend(throughputs),
            "current_score": scores[-1] if scores else 0.0,
            "best_score": max(scores) if scores else 0.0,
            "worst_score": min(scores) if scores else 0.0,
        }

    async def optimize_performance_async(self) -> dict[str, Any]:
        """Run automated performance optimization analysis."""
        logger.info("Running performance optimization analysis")

        # Generate current report
        current_report = await self.generate_report_async()

        # Analyze optimization opportunities
        optimization_recommendations = []

        for insight in current_report.insights:
            if insight.category == "optimization":
                optimization_recommendations.append(
                    {
                        "title": insight.title,
                        "description": insight.description,
                        "recommendation": insight.recommendation,
                        "expected_impact": insight.impact,
                        "confidence": insight.confidence,
                    },
                )

        # System-level recommendations
        system_metrics = self.system_monitor.get_current_metrics()
        if system_metrics:
            if system_metrics.memory_percent > 80:
                optimization_recommendations.append(
                    {
                        "title": "Memory Optimization",
                        "description": f"Memory usage at {system_metrics.memory_percent:.1f}%",
                        "recommendation": "Consider implementing memory-efficient algorithms or increasing memory limits",
                        "expected_impact": "Reduced memory pressure and improved stability",
                        "confidence": 0.9,
                    },
                )

            if system_metrics.cpu_percent > 70:
                optimization_recommendations.append(
                    {
                        "title": "CPU Optimization",
                        "description": f"CPU usage at {system_metrics.cpu_percent:.1f}%",
                        "recommendation": "Profile CPU-intensive operations and consider async alternatives",
                        "expected_impact": "Improved responsiveness and throughput",
                        "confidence": 0.8,
                    },
                )

        # Async-specific recommendations
        if self.enable_profiling:
            async_report = self.async_profiler.analyze_performance()
            if async_report.concurrency_level > 100:
                optimization_recommendations.append(
                    {
                        "title": "Async Concurrency Control",
                        "description": f"High concurrency level: {async_report.concurrency_level:.1f}",
                        "recommendation": "Implement semaphores or task queuing to control concurrency",
                        "expected_impact": "Reduced event loop congestion",
                        "confidence": 0.85,
                    },
                )

        return {
            "overall_score": current_report.overall_score,
            "performance_grade": current_report.performance_grade,
            "optimization_opportunities": len(optimization_recommendations),
            "recommendations": optimization_recommendations,
            "critical_issues": len(current_report.critical_issues),
            "analysis_timestamp": datetime.utcnow().isoformat(),
        }

    def export_monitoring_data(self, time_window: timedelta | None = None, format: str = "json") -> str:
        """Export comprehensive monitoring data."""
        if time_window is None:
            time_window = timedelta(hours=1)

        # Collect data from all components
        metrics_data = self.metrics_collector.get_metrics(time_window=time_window)
        system_data = self.system_monitor.get_metrics_history(time_window)
        analysis_data = self.get_analysis_history(time_window)

        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "time_window_hours": time_window.total_seconds() / 3600,
            "metrics_count": len(metrics_data),
            "system_metrics_count": len(system_data),
            "analysis_reports_count": len(analysis_data),
            "current_status": self.get_current_status(),
        }

        if format == "json":
            import json

            return (json.dumps(export_data, indent=2),)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def cleanup_old_data_async(self, retention_hours: int = 24) -> None:
        """Clean up old monitoring data."""
        cutoff_time = datetime.utcnow() - timedelta(hours=retention_hours)

        # Clean analysis history
        original_count = len(self._analysis_history)
        self._analysis_history = [r for r in self._analysis_history if r.analysis_timestamp >= cutoff_time]
        cleaned_count = original_count - len(self._analysis_history)

        # Clean component data
        self.metrics_collector.clear_metrics()
        self.system_monitor.clear_history()
        self.async_profiler.clear_history()

        logger.info(f"Cleaned up {cleaned_count} old analysis reports")
