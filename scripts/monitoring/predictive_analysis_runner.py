"""
Predictive Analysis Runner

Periodically analyzes monitoring data and generates predictive alerts.
Designed to run as a scheduled job (every 5-15 minutes).

Part of PROJECT VANGUARD Phase 2.1 - Predictive Failure Alerts
"""

import asyncio
import sys
from datetime import datetime, timedelta
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

    def __init__(self, alert_manager: PredictiveAlertManager):
        """
        Initialize analysis runner.

        Args:
            alert_manager: Predictive alert manager instance
        """
        self.alert_manager = alert_manager
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
                    service_name=service_name, metric_type=metric_type, metrics=metrics
                )

                if alert:
                    alerts_generated.append(alert)

            # Update statistics
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.run_stats["total_runs"] += 1
            self.run_stats["total_alerts_generated"] += len(alerts_generated)
            self.run_stats["last_run_time"] = start_time.isoformat()
            self.run_stats["last_run_duration_seconds"] = duration

            logger.info(
                f"Analysis complete: {len(alerts_generated)} alerts generated "
                f"in {duration:.2f}s"
            )

            return {
                "success": True,
                "alerts_generated": len(alerts_generated),
                "alerts": [alert.to_dict() for alert in alerts_generated],
                "duration_seconds": duration,
                "timestamp": start_time.isoformat(),
            }

        except Exception as e:
            logger.error(f"Analysis run failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "timestamp": start_time.isoformat(),
            }

    async def _collect_metrics_async(
        self,
    ) -> dict[tuple[str, MetricType], list[MetricPoint]]:
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

    async def _get_service_error_rates_async(
        self, service_name: str
    ) -> list[MetricPoint] | None:
        """
        Get error rate metrics for a service.

        Args:
            service_name: Name of service to get metrics for

        Returns:
            List of error rate metric points
        """
        try:
            # TODO: Integrate with MonitoringErrorReporter
            # error_trends = await error_reporter.get_error_trends(
            #     service_name=service_name,
            #     hours=24
            # )

            # For now, return None (no data)
            logger.debug(f"Collecting error rates for {service_name}")
            return None

        except Exception as e:
            logger.warning(f"Failed to collect error rates for {service_name}: {e}")
            return None

    async def _get_service_cpu_metrics_async(
        self, service_name: str
    ) -> list[MetricPoint] | None:
        """
        Get CPU utilization metrics for a service.

        Args:
            service_name: Name of service to get metrics for

        Returns:
            List of CPU metric points
        """
        try:
            # TODO: Integrate with HealthMonitor
            # cpu_metrics = await health_monitor.get_metric_history(
            #     service_name=service_name,
            #     metric_name="cpu_percent",
            #     hours=24
            # )

            logger.debug(f"Collecting CPU metrics for {service_name}")
            return None

        except Exception as e:
            logger.warning(f"Failed to collect CPU metrics for {service_name}: {e}")
            return None

    async def _get_service_latency_async(
        self, service_name: str
    ) -> list[MetricPoint] | None:
        """
        Get latency metrics for a service.

        Args:
            service_name: Name of service to get metrics for

        Returns:
            List of latency metric points
        """
        try:
            # TODO: Integrate with performance monitoring
            # latency_metrics = await perf_monitor.get_latency_history(
            #     service_name=service_name,
            #     percentile=95,
            #     hours=24
            # )

            logger.debug(f"Collecting latency metrics for {service_name}")
            return None

        except Exception as e:
            logger.warning(f"Failed to collect latency metrics for {service_name}: {e}")
            return None

    def get_stats(self) -> dict:
        """Get runner statistics."""
        return {
            **self.run_stats,
            "alert_manager_stats": self.alert_manager.get_stats(),
        }


async def main():
    """Main entry point for predictive analysis script."""
    if not HIVE_ERRORS_AVAILABLE:
        print("ERROR: hive-errors package not available")
        print("Install with: pip install -e packages/hive-errors")
        sys.exit(1)

    import argparse

    parser = argparse.ArgumentParser(description="Predictive Failure Analysis")
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously with periodic analysis",
    )
    parser.add_argument(
        "--interval", type=int, default=5, help="Analysis interval in minutes (default: 5)"
    )
    parser.add_argument(
        "--config", type=Path, help="Path to alert configuration file (YAML/JSON)"
    )
    parser.add_argument(
        "--output", type=Path, help="Output file for analysis results (JSON)"
    )

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
        )
    )

    alert_manager.add_config(
        AlertConfig(
            service_name="database_service",
            metric_type=MetricType.CPU_UTILIZATION,
            threshold=85.0,  # 85% CPU
            confidence_threshold=0.85,
            degradation_window_minutes=15,
        )
    )

    alert_manager.add_config(
        AlertConfig(
            service_name="web_api",
            metric_type=MetricType.LATENCY_P95,
            threshold=1000.0,  # 1 second
            confidence_threshold=0.75,
            degradation_window_minutes=30,
        )
    )

    # Initialize runner
    runner = PredictiveAnalysisRunner(alert_manager)

    if args.continuous:
        # Continuous mode: run analysis periodically
        logger.info(f"Starting continuous analysis (interval: {args.interval} minutes)")

        try:
            while True:
                result = await runner.run_analysis_async()

                if args.output:
                    import json

                    args.output.write_text(json.dumps(result, indent=2))
                    logger.info(f"Results written to: {args.output}")

                # Wait for next interval
                await asyncio.sleep(args.interval * 60)

        except KeyboardInterrupt:
            logger.info("Continuous analysis stopped by user")

            # Print final statistics
            stats = runner.get_stats()
            print("\n=== Final Statistics ===")
            print(f"Total Runs: {stats['total_runs']}")
            print(f"Total Alerts Generated: {stats['total_alerts_generated']}")
            print(f"Last Run: {stats['last_run_time']}")

    else:
        # Single run mode
        result = await runner.run_analysis_async()

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