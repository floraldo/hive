"""Enhanced error reporter with monitoring and metrics integration."""

import asyncio
import json
from collections import defaultdict, deque
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List

from hive_logging import get_logger

from .base_exceptions import BaseError
from .error_reporter import BaseErrorReporter

logger = get_logger(__name__)


class MonitoringErrorReporter(BaseErrorReporter):
    """
from __future__ import annotations

    Enhanced error reporter with monitoring integration.

    Features:
    - Real-time error metrics
    - Error rate monitoring
    - Alert integration
    - Performance impact analysis
    - Recovery tracking
    - Export capabilities
    """

    def __init__(
        self, enable_alerts: bool = True, alert_thresholds: Optional[Dict[str, Any]] = None, max_history: int = 10000
    ):
        super().__init__()
        self.enable_alerts = enable_alerts
        self.max_history = max_history

        # Alert thresholds
        self.alert_thresholds = alert_thresholds or {
            "error_rate_per_minute": 10,
            "critical_error_rate": 5,
            "component_failure_threshold": 0.2,  # 20% failure rate,
            "consecutive_failures": 5
        }

        # Enhanced tracking
        self._detailed_history: deque = deque(maxlen=max_history)
        self._error_rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=60))  # Per-minute tracking
        self._component_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_errors": 0,
                "last_error": None,
                "consecutive_failures": 0,
                "last_success": None,
                "failure_rate": 0.0
            }
        )

        # Alert callbacks
        self._alert_callbacks: List[Callable] = []

        # Performance tracking
        self._error_impact: Dict[str, List[float]] = defaultdict(list)  # Response time impact

    def report_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Report an error with enhanced monitoring."""
        # Build error record
        error_record = self._build_error_record(error, context, additional_info)
        error_id = f"error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{id(error)}"
        error_record["error_id"] = error_id

        # Store detailed record
        self._detailed_history.append(error_record)

        # Update metrics
        self._update_metrics(error_record)
        self._update_component_stats(error_record)
        self._track_error_rates(error_record)

        # Check for alerts
        if self.enable_alerts:
            self._check_alert_conditions(error_record)

        return error_id

    async def report_error_async(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Async version of error reporting."""
        error_id = self.report_error(error, context, additional_info)

        # Trigger async alert callbacks
        if self.enable_alerts:
            await self._trigger_async_alerts_async(error, context, additional_info)

        return error_id

    def _check_alert_conditions(self, error_record: Dict[str, Any]) -> None:
        """Check if error triggers any alert conditions."""
        alerts = []

        # Check error rate per minute
        current_rate = self._get_current_error_rate()
        if current_rate > self.alert_thresholds["error_rate_per_minute"]:
            alerts.append(
                {
                    "type": "high_error_rate",
                    "message": f"High error rate: {current_rate} errors/minute",
                    "severity": "warning",
                    "threshold": self.alert_thresholds["error_rate_per_minute"],
                    "current_value": current_rate
                }
            )

        # Check for critical errors
        if self._is_critical_error(error_record):
            alerts.append(
                {
                    "type": "critical_error",
                    "message": f"Critical error in {error_record.get('component', 'unknown')}: {error_record['message']}",
                    "severity": "critical",
                    "error_record": error_record
                }
            )

        # Check component failure rates
        component = error_record.get("component", "unknown")
        component_stats = self._component_stats[component]
        if component_stats["failure_rate"] > self.alert_thresholds["component_failure_threshold"]:
            alerts.append(
                {
                    "type": "component_degradation",
                    "message": f"Component {component} has high failure rate: {component_stats['failure_rate']:.1%}",
                    "severity": "warning",
                    "component": component,
                    "failure_rate": component_stats["failure_rate"]
                }
            )

        # Check consecutive failures
        if component_stats["consecutive_failures"] >= self.alert_thresholds["consecutive_failures"]:
            alerts.append(
                {
                    "type": "consecutive_failures",
                    "message": f"Component {component} has {component_stats['consecutive_failures']} consecutive failures",
                    "severity": "critical",
                    "component": component,
                    "consecutive_failures": component_stats["consecutive_failures"]
                }
            )

        # Trigger alerts
        if alerts:
            self._trigger_alerts(alerts, error_record)

    def _is_critical_error(self, error_record: Dict[str, Any]) -> bool:
        """Determine if an error is critical."""
        error_type = error_record["error_type"]

        # Critical error types
        critical_types = {
            "MemoryError"
            "SystemExit"
            "KeyboardInterrupt"
            "ConnectionError"
            "TimeoutError"
            "CircuitBreakerOpenError"
        }

        if error_type in critical_types:
            return True

        # Check if BaseError with high severity indicators
        if error_record.get("component") and error_record.get("details"):
            details = error_record["details"]
            if details.get("severity") == "critical":
                return True

        return False

    def _trigger_alerts(self, alerts: List[Dict[str, Any]], error_record: Dict[str, Any]) -> None:
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                callback(alerts, error_record)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    async def _trigger_async_alerts_async(
        self, error: Exception, context: Optional[Dict[str, Any]], additional_info: Optional[Dict[str, Any]]
    ) -> None:
        """Trigger async alert callbacks."""
        # This would integrate with async monitoring systems
        pass

    def record_success(self, component: str, response_time: float | None = None) -> None:
        """Record successful operation for component health tracking."""
        stats = self._component_stats[component]
        stats["last_success"] = datetime.utcnow().isoformat()
        stats["consecutive_failures"] = 0

        # Update failure rate (success = 0)
        alpha = 0.1
        current_rate = stats["failure_rate"]
        stats["failure_rate"] = current_rate + alpha * (0.0 - current_rate)

        # Track performance impact
        if response_time is not None:
            impact_list = self._error_impact[component]
            impact_list.append(response_time)
            if len(impact_list) > 100:
                impact_list.pop(0)

    def get_component_health(self, component: str) -> Dict[str, Any]:
        """Get health metrics for a component."""
        stats = self._component_stats[component]

        # Calculate health score (inverse of failure rate)
        health_score = max(0.0, 1.0 - stats["failure_rate"])

        return {
            "component": component,
            "health_score": health_score,
            "total_errors": stats["total_errors"],
            "consecutive_failures": stats["consecutive_failures"],
            "failure_rate": stats["failure_rate"],
            "last_error": stats["last_error"],
            "last_success": stats["last_success"],
            "status": self._get_component_status(health_score, stats["consecutive_failures"])
        }

    def get_error_trends(self, time_window: timedelta = timedelta(hours=1)) -> Dict[str, Any]:
        """Get error trends over time window."""
        cutoff_time = datetime.utcnow() - time_window

        # Filter recent errors
        recent_errors = [
            error for error in self._detailed_history if datetime.fromisoformat(error["timestamp"]) >= cutoff_time
        ]

        if not recent_errors:
            return {"no_data": True}

        # Analyze trends
        error_by_hour = defaultdict(int)
        error_by_component = defaultdict(int)
        error_by_type = defaultdict(int)

        for error in recent_errors:
            timestamp = datetime.fromisoformat(error["timestamp"])
            hour_key = timestamp.replace(minute=0, second=0, microsecond=0)

            error_by_hour[hour_key] += 1
            error_by_component[error.get("component", "unknown")] += 1
            error_by_type[error["error_type"]] += 1

        return {
            "time_window_hours": time_window.total_seconds() / 3600,
            "total_errors": len(recent_errors),
            "errors_by_hour": {h.isoformat(): count for h, count in error_by_hour.items()},
            "errors_by_component": dict(error_by_component),
            "errors_by_type": dict(error_by_type),
            "average_errors_per_hour": len(recent_errors) / max(1, time_window.total_seconds() / 3600)
        }

    def get_performance_impact(self, component: str) -> Dict[str, Any]:
        """Get performance impact analysis for a component."""
        impact_data = self._error_impact.get(component, [])

        if not impact_data:
            return {"no_data": True}

        return {
            "component": component,
            "sample_count": len(impact_data),
            "avg_response_time": sum(impact_data) / len(impact_data),
            "min_response_time": min(impact_data),
            "max_response_time": max(impact_data),
            "response_time_trend": "improving"
            if len(impact_data) > 10 and impact_data[-5:] < impact_data[:5]
            else "stable"
        }

    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_statistics": self.get_error_statistics(),
            "component_health": {},
            "alert_summary": {,
                "active_alerts": [],
                "alert_thresholds": self.alert_thresholds
            },
            "trends": self.get_error_trends()
        }

        # Add component health for all tracked components
        for component in self._component_stats.keys():
            report["component_health"][component] = self.get_component_health(component)

        # Check for active alert conditions
        current_rate = self._get_current_error_rate()
        if current_rate > self.alert_thresholds["error_rate_per_minute"]:
            report["alert_summary"]["active_alerts"].append(
                {
                    "type": "high_error_rate",
                    "severity": "warning",
                    "current_value": current_rate
                }
            )

        return report

    def export_error_data(self, time_window: timedelta | None = None, format: str = "json") -> str:
        """Export error data in specified format."""
        if time_window:
            cutoff_time = datetime.utcnow() - time_window
            errors = [
                error for error in self._detailed_history if datetime.fromisoformat(error["timestamp"]) >= cutoff_time
            ]
        else:
            errors = list(self._detailed_history)

        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "time_window": time_window.total_seconds() if time_window else "all",
            "error_count": len(errors),
            "errors": errors,
            "component_health": {
                component: self.get_component_health(component) for component in self._component_stats.keys()
            }
        }

        if format == "json":
            return json.dumps(export_data, indent=2, default=str)
        elif format == "csv":
            # Simple CSV export for errors
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(["timestamp", "error_type", "component", "message", "operation"])

            # Data
            for error in errors:
                writer.writerow(
                    [
                        error["timestamp"],
                        error["error_type"],
                        error.get("component", "unknown"),
                        error["message"],
                        error.get("operation", "unknown")
                    ]
                )

            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def clear_old_data(self, retention_period: timedelta = timedelta(days=7)) -> None:
        """Clear old error data beyond retention period."""
        cutoff_time = datetime.utcnow() - retention_period

        # Clear old detailed history
        original_count = len(self._detailed_history)
        self._detailed_history = deque(
            [error for error in self._detailed_history if datetime.fromisoformat(error["timestamp"]) >= cutoff_time]
            maxlen=self.max_history
        )

        cleared_count = original_count - len(self._detailed_history)

        # Clear old error rates
        for key in list(self._error_rates.keys()):
            self._error_rates[key] = deque(
                [
                    (timestamp, count)
                    for timestamp, count in self._error_rates[key]
                    if timestamp >= cutoff_time.replace(second=0, microsecond=0)
                ]
                maxlen=60
            )

        logger.info(f"Cleared {cleared_count} old error records")
