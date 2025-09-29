"""
Predictive Monitoring Service Implementation

Provides predictive failure analysis integrated with hive-orchestrator.
Follows orchestrator service patterns for consistency.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from hive_errors.alert_manager import PredictiveAlertManager
from hive_errors.monitoring_error_reporter import MonitoringErrorReporter
from hive_errors.predictive_alerts import MetricPoint, MetricType
from hive_logging import get_logger

from .exceptions import MonitoringConfigurationError
from .interfaces import IMonitoringService

logger = get_logger(__name__)


class PredictiveMonitoringService(IMonitoringService):
    """
    Predictive monitoring service integrated with hive-orchestrator.

    Follows dependency injection pattern and orchestrator conventions.
    Emits events via hive-bus for cross-app coordination.
    """

    def __init__(
        self,
        alert_manager: PredictiveAlertManager,
        error_reporter: MonitoringErrorReporter | None = None,
        health_monitor: Any | None = None,
        bus: Any | None = None,
    ):
        """
        Initialize monitoring service.

        Args:
            alert_manager: Predictive alert manager instance (required)
            error_reporter: MonitoringErrorReporter instance (optional)
            health_monitor: HealthMonitor instance (optional)
            bus: Event bus for cross-app events (optional)
        """
        if not alert_manager:
            raise MonitoringConfigurationError("alert_manager is required")

        self.alert_manager = alert_manager
        self._error_reporter = error_reporter
        self._health_monitor = health_monitor
        self._bus = bus

        # Service statistics
        self.run_stats = {
            "total_runs": 0,
            "total_alerts_generated": 0,
            "last_run_time": None,
            "last_run_duration_seconds": 0,
        }

        logger.info("PredictiveMonitoringService initialized")

    async def run_analysis_cycle(self) -> dict[str, Any]:
        """
        Run single predictive analysis cycle.

        Returns:
            Analysis results with alerts and statistics
        """
        start_time = datetime.utcnow()
        logger.info("Starting predictive analysis cycle")

        try:
            # Collect metrics from monitoring systems
            metrics_by_service = await self._collect_metrics_async()

            # Analyze each service/metric combination
            alerts_generated = []
            for (service_name, metric_type), metrics in metrics_by_service.items():
                try:
                    alert = await self.alert_manager.analyze_metrics_async(
                        service_name=service_name, metric_type=metric_type, metrics=metrics,
                    )

                    if alert:
                        alerts_generated.append(alert)

                        # Emit event if bus available
                        if self._bus:
                            await self._emit_alert_event_async(alert)

                except Exception as e:
                    logger.warning(f"Analysis failed for {service_name}/{metric_type}: {e}")
                    # Continue with other metrics

            # Update statistics
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.run_stats["total_runs"] += 1
            self.run_stats["total_alerts_generated"] += len(alerts_generated)
            self.run_stats["last_run_time"] = start_time.isoformat()
            self.run_stats["last_run_duration_seconds"] = duration

            logger.info(f"Analysis cycle complete: {len(alerts_generated)} alerts in {duration:.2f}s")

            return {
                "success": True,
                "alerts_generated": len(alerts_generated),
                "alerts": [alert.to_dict() for alert in alerts_generated],
                "duration_seconds": duration,
                "timestamp": start_time.isoformat(),
            }

        except Exception as e:
            logger.error(f"Analysis cycle failed: {e}", exc_info=True)
            return {"success": False, "error": str(e), "timestamp": start_time.isoformat()}

    async def start_continuous_monitoring(self, interval_minutes: int) -> None:
        """
        Start continuous monitoring with periodic analysis.

        Args:
            interval_minutes: Interval between analysis cycles

        Raises:
            KeyboardInterrupt: When monitoring is stopped by user
        """
        logger.info(f"Starting continuous monitoring (interval: {interval_minutes} minutes)")

        try:
            while True:
                await self.run_analysis_cycle()

                # Wait for next interval
                await asyncio.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            logger.info("Continuous monitoring stopped by user")

            # Print final statistics
            stats = self.get_metrics()
            logger.info(f"Final statistics: {stats}")

    async def _collect_metrics_async(self) -> dict[tuple[str, MetricType], list[MetricPoint]]:
        """
        Collect metrics from monitoring systems.

        Returns:
            Dictionary mapping (service, metric_type) to metric points
        """
        metrics = {}

        # Collect error rates if reporter available
        if self._error_reporter:
            # Get list of services from error reporter component stats
            for component in self._error_reporter._component_stats.keys():
                try:
                    error_data = self._error_reporter.get_error_rate_history(service_name=component, hours=24)

                    if error_data and len(error_data) > 0:
                        metric_points = [
                            MetricPoint(timestamp=point["timestamp"], value=point["value"], metadata=point["metadata"])
                            for point in error_data
                        ]
                        metrics[(component, MetricType.ERROR_RATE)] = metric_points
                        logger.debug(f"Collected {len(metric_points)} error rate points for {component}")

                except Exception as e:
                    logger.warning(f"Failed to collect error rates for {component}: {e}")

        # Collect health metrics if monitor available
        if self._health_monitor:
            try:
                # Get CPU/memory/latency metrics from health monitor
                # Implementation depends on HealthMonitor API
                pass
            except Exception as e:
                logger.warning(f"Failed to collect health metrics: {e}")

        return metrics

    async def _emit_alert_event_async(self, alert: Any) -> None:
        """
        Emit alert event via event bus.

        Args:
            alert: Predictive alert to emit
        """
        if not self._bus:
            return

        try:
            from hive_bus import BaseEvent

            class PredictiveAlertEvent(BaseEvent):
                """Event emitted when predictive alert generated"""

                def __init__(self, alert_data: dict):
                    super().__init__(event_type="monitoring.predictive_alert")
                    self.alert_data = alert_data

            # Publish event
            event = PredictiveAlertEvent(alert.to_dict())
            await self._bus.publish_async(event)

            logger.debug(f"Emitted alert event: {alert.alert_id}")

        except Exception as e:
            logger.warning(f"Failed to emit alert event: {e}")

    def get_metrics(self) -> dict[str, Any]:
        """
        Get monitoring service health metrics.

        Returns:
            Service metrics and statistics
        """
        return {**self.run_stats, "alert_manager_stats": self.alert_manager.get_stats() if self.alert_manager else {}}

    def get_component_health(self, component: str) -> dict[str, Any]:
        """
        Get health status for specific component.

        Args:
            component: Component name

        Returns:
            Health metrics for component
        """
        if not self._error_reporter:
            return {"error": "error_reporter not configured"}

        return self._error_reporter.get_component_health(component)
