"""
Predictive Analysis Runner

Periodically analyzes monitoring data and generates predictive alerts.
Designed to run as a scheduled job (every 5-15 minutes).

Part of PROJECT VANGUARD Phase 2.1 - Predictive Failure Alerts
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

from hive_logging import get_logger

try:
    from hive_errors.alert_manager import AlertConfig, PredictiveAlertManager
    from hive_errors.predictive_alerts import MetricPoint, MetricType

    HIVE_ERRORS_AVAILABLE = True
except ImportError:
    HIVE_ERRORS_AVAILABLE = False
    PredictiveAlertManager = None
    AlertConfig = None
    MetricPoint = None
    MetricType = None

logger = get_logger(__name__)


class PredictiveAnalysisRunner:
    """
    Run predictive analysis on monitoring data.

    Integrates with MonitoringErrorReporter and HealthMonitor
    to analyze trends and generate proactive alerts.
    """

    def __init__(self, alert_manager: PredictiveAlertManager, error_reporter=None, health_monitor=None):
        """
        Initialize analysis runner.

        Args:
            alert_manager: Predictive alert manager instance
            error_reporter: MonitoringErrorReporter instance (optional)
            health_monitor: HealthMonitor instance (optional)
        """
        self.alert_manager = alert_manager
        self._error_reporter = error_reporter
        self._health_monitor = health_monitor
        self.run_stats = {
            "total_runs": 0,
            "total_alerts_generated": 0,
            "last_run_time": None,
            "last_run_duration_seconds": 0,
        }

    async def run_analysis_async(self) -> dict:
        """
        Run complete predictive analysis cycle.

        Returns:
            Analysis results and statistics
        """
        start_time = datetime.utcnow()
        logger.info("Starting predictive analysis run")

        try:
            # Collect metrics from monitoring systems
            metrics_by_service = await self._collect_metrics_async()

            # Analyze each service/metric combination
            alerts_generated = []
            for (service_name, metric_type), metrics in metrics_by_service.items():
                alert = await self.alert_manager.analyze_metrics_async(
                    service_name=service_name,
                    metric_type=metric_type,
                    metrics=metrics,
                )

                if alert:
                    alerts_generated.append(alert)

            # Update statistics
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.run_stats["total_runs"] += 1
            self.run_stats["total_alerts_generated"] += len(alerts_generated)
            self.run_stats["last_run_time"] = start_time.isoformat()
            self.run_stats["last_run_duration_seconds"] = duration

            logger.info(f"Analysis complete: {len(alerts_generated)} alerts generated in {duration:.2f}s")

            return {
                "success": True,
                "alerts_generated": len(alerts_generated),
                "alerts": [alert.to_dict() for alert in alerts_generated],
                "duration_seconds": duration,
                "timestamp": start_time.isoformat(),
            }

        except Exception as e:
            logger.error(f"Analysis run failed: {e}", exc_info=True)
            return {"success": False, "error": str(e), "timestamp": start_time.isoformat()}

    async def run_analysis_cycle(self) -> dict:
        """Alias for run_analysis_async for compatibility with service interface."""
        return await self.run_analysis_async()

    async def _collect_metrics_async(self) -> dict[tuple[str, MetricType], list[MetricPoint]]:
        """
        Collect metrics from monitoring systems.

        In production, this would integrate with:
        - MonitoringErrorReporter for error rate trends
        - HealthMonitor for resource utilization
        - CircuitBreaker for failure statistics

        Returns:
            Dictionary mapping (service, metric_type) to metric points
        """
        metrics = {}

        # TODO: Integrate with actual monitoring systems
        # For now, generate sample data for demonstration

        # Example: AI Model Service error rates
        ai_service_errors = await self._get_service_error_rates_async("ai_model_service")
        if ai_service_errors:
            metrics[("ai_model_service", MetricType.ERROR_RATE)] = ai_service_errors

        # Example: Database service CPU utilization
        db_cpu_metrics = await self._get_service_cpu_metrics_async("database_service")
        if db_cpu_metrics:
            metrics[("database_service", MetricType.CPU_UTILIZATION)] = db_cpu_metrics

        # Example: Web API latency
        api_latency = await self._get_service_latency_async("web_api")
        if api_latency:
            metrics[("web_api", MetricType.LATENCY_P95)] = api_latency

        return metrics

    async def _get_service_error_rates_async(self, service_name: str) -> list[MetricPoint] | None:
        """
        Get error rate metrics for a service.

        Args:
            service_name: Name of service to get metrics for

        Returns:
            List of error rate metric points
        """
        try:
            # Get global instance if available
            # In production, this would be injected via dependency injection
            error_reporter = getattr(self, "_error_reporter", None)
            if not error_reporter:
                logger.debug(f"No error reporter configured for {service_name}")
                return None

            # Get error rate history
            error_data = error_reporter.get_error_rate_history(service_name=service_name, hours=24)

            if not error_data:
                logger.debug(f"No error data available for {service_name}")
                return None

            # Convert to MetricPoint objects
            metric_points = [
                MetricPoint(timestamp=point["timestamp"], value=point["value"], metadata=point["metadata"])
                for point in error_data
            ]

            logger.info(f"Collected {len(metric_points)} error rate points for {service_name}")
            return metric_points

        except Exception as e:
            logger.warning(f"Failed to collect error rates for {service_name}: {e}")
            return None

    async def _get_service_cpu_metrics_async(self, service_name: str) -> list[MetricPoint] | None:
        """
        Get CPU utilization metrics for a service.

        Args:
            service_name: Name of service to get metrics for

        Returns:
            List of CPU metric points
        """
        try:
            # Get health monitor instance if available
            health_monitor = getattr(self, "_health_monitor", None)
            if not health_monitor:
                logger.debug(f"No health monitor configured for {service_name}")
                return None

            # Get CPU utilization history
            cpu_data = health_monitor.get_metric_history(provider=service_name, metric_name="cpu_percent", hours=24)

            if not cpu_data:
                logger.debug(f"No CPU data available for {service_name}")
                return None

            # Convert to MetricPoint objects
            metric_points = [
                MetricPoint(timestamp=point["timestamp"], value=point["value"], metadata=point["metadata"])
                for point in cpu_data
            ]

            logger.info(f"Collected {len(metric_points)} CPU metric points for {service_name}")
            return metric_points

        except Exception as e:
            logger.warning(f"Failed to collect CPU metrics for {service_name}: {e}")
            return None

    async def _get_service_latency_async(self, service_name: str) -> list[MetricPoint] | None:
        """
        Get latency metrics for a service.

        Args:
            service_name: Name of service to get metrics for

        Returns:
            List of latency metric points
        """
        try:
            # Get health monitor instance if available
            health_monitor = getattr(self, "_health_monitor", None)
            if not health_monitor:
                logger.debug(f"No health monitor configured for {service_name}")
                return None

            # Get response time history (latency proxy)
            latency_data = health_monitor.get_metric_history(
                provider=service_name,
                metric_name="response_time",
                hours=24,
            )

            if not latency_data:
                logger.debug(f"No latency data available for {service_name}")
                return None

            # Convert to MetricPoint objects
            metric_points = [
                MetricPoint(timestamp=point["timestamp"], value=point["value"], metadata=point["metadata"])
                for point in latency_data
            ]

            logger.info(f"Collected {len(metric_points)} latency metric points for {service_name}")
            return metric_points

        except Exception as e:
            logger.warning(f"Failed to collect latency metrics for {service_name}: {e}")
            return None

    def get_stats(self) -> dict:
        """Get runner statistics."""
        return {**self.run_stats, "alert_manager_stats": self.alert_manager.get_stats()}

    def get_metrics(self) -> dict:
        """Alias for get_stats for compatibility with service interface."""
        return self.get_stats()


async def main():
    """Main entry point for predictive analysis script."""
    if not HIVE_ERRORS_AVAILABLE:
        print("ERROR: hive-errors package not available")
        print("Install with: pip install -e packages/hive-errors")
        sys.exit(1)

    import argparse

    parser = argparse.ArgumentParser(description="Predictive Failure Analysis")
    parser.add_argument("--continuous", action="store_true", help="Run continuously with periodic analysis")
    parser.add_argument("--interval", type=int, default=5, help="Analysis interval in minutes (default: 5)")
    parser.add_argument("--config", type=Path, help="Path to alert configuration file (YAML/JSON)")
    parser.add_argument("--output", type=Path, help="Output file for analysis results (JSON)")

    args = parser.parse_args()

    # Initialize alert manager with configurations
    alert_manager = PredictiveAlertManager()

    # Load configurations from file if provided
    if args.config and args.config.exists():
        logger.info(f"Loading configuration from: {args.config}")
        # TODO: Load configuration from file
        # configs = load_alert_configs(args.config)
        # for config in configs:
        #     alert_manager.add_config(config)

    # Add default configurations for demo
    alert_manager.add_config(
        AlertConfig(
            service_name="ai_model_service",
            metric_type=MetricType.ERROR_RATE,
            threshold=5.0,  # 5% error rate
            confidence_threshold=0.80,
            degradation_window_minutes=30,
        ),
    )

    alert_manager.add_config(
        AlertConfig(
            service_name="database_service",
            metric_type=MetricType.CPU_UTILIZATION,
            threshold=85.0,  # 85% CPU
            confidence_threshold=0.85,
            degradation_window_minutes=15,
        ),
    )

    alert_manager.add_config(
        AlertConfig(
            service_name="web_api",
            metric_type=MetricType.LATENCY_P95,
            threshold=1000.0,  # 1 second
            confidence_threshold=0.75,
            degradation_window_minutes=30,
        ),
    )

    # Initialize orchestrator service (NEW: proper architecture)
    try:
        from hive_orchestrator.services.monitoring import PredictiveMonitoringService

        service = PredictiveMonitoringService(alert_manager=alert_manager)
        logger.info("Using orchestrator monitoring service (architecture-compliant)")
    except ImportError:
        # Fallback to standalone runner for backward compatibility
        logger.warning("Orchestrator service not available, using standalone runner")
        service = PredictiveAnalysisRunner(alert_manager)

    if args.continuous:
        # Continuous mode: run analysis periodically
        logger.info(f"Starting continuous analysis (interval: {args.interval} minutes)")

        try:
            while True:
                result = await service.run_analysis_cycle()

                if args.output:
                    import json

                    args.output.write_text(json.dumps(result, indent=2))
                    logger.info(f"Results written to: {args.output}")

                # Wait for next interval
                await asyncio.sleep(args.interval * 60)

        except KeyboardInterrupt:
            logger.info("Continuous analysis stopped by user")

            # Print final statistics
            stats = service.get_metrics()
            print("\n=== Final Statistics ===")
            print(f"Total Runs: {stats['total_runs']}")
            print(f"Total Alerts Generated: {stats['total_alerts_generated']}")
            print(f"Last Run: {stats['last_run_time']}")

    else:
        # Single run mode
        result = await service.run_analysis_cycle()

        if args.output:
            import json

            args.output.write_text(json.dumps(result, indent=2))
            print(f"Results written to: {args.output}")
        else:
            import json

            print(json.dumps(result, indent=2))

        # Exit with appropriate code
        sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
