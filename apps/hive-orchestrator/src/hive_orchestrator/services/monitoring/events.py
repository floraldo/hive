"""Monitoring Service Events

Event types emitted by the predictive monitoring service for cross-app coordination.
Follows hive-bus BaseEvent pattern for compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from hive_bus import BaseEvent


@dataclass
class PredictiveAlertEvent(BaseEvent):
    """Event emitted when predictive monitoring generates an alert.

    Other apps can subscribe to these events to:
    - Take automated remediation actions
    - Update dashboards and UIs
    - Trigger escalation workflows
    - Log to external systems
    """

    def __init__(
        self,
        alert_id: str,
        service_name: str,
        metric_type: str,
        severity: str,
        prediction: dict[str, Any],
        recommended_actions: list[str] | None = None,
        **kwargs,
    ):
        """Initialize predictive alert event.

        Args:
            alert_id: Unique alert identifier
            service_name: Name of service being monitored
            metric_type: Type of metric (error_rate, latency, etc.)
            severity: Alert severity (low, medium, high, critical)
            prediction: Prediction details (failure_probability, estimated_time, etc.)
            recommended_actions: Suggested remediation steps
            **kwargs: Additional BaseEvent parameters

        """
        payload = {
            "alert_id": alert_id,
            "service_name": service_name,
            "metric_type": metric_type,
            "severity": severity,
            "prediction": prediction,
            "recommended_actions": recommended_actions or [],
        }

        super().__init__(
            event_type="monitoring.predictive_alert",
            source="hive-orchestrator.monitoring-service",
            payload=payload,
            **kwargs,
        )

    @property
    def alert_id(self) -> str:
        """Get alert ID"""
        return self.payload["alert_id"]

    @property
    def service_name(self) -> str:
        """Get service name"""
        return self.payload["service_name"]

    @property
    def metric_type(self) -> str:
        """Get metric type"""
        return self.payload["metric_type"]

    @property
    def severity(self) -> str:
        """Get severity level"""
        return self.payload["severity"]

    @property
    def prediction(self) -> dict[str, Any]:
        """Get prediction details"""
        return self.payload["prediction"]

    @property
    def recommended_actions(self) -> list[str]:
        """Get recommended actions"""
        return self.payload["recommended_actions"]


@dataclass
class MonitoringCycleCompleteEvent(BaseEvent):
    """Event emitted when a monitoring analysis cycle completes.

    Used for coordination with other systems that need to know
    when monitoring has completed its periodic check.
    """

    def __init__(
        self,
        cycle_id: str,
        alerts_generated: int,
        services_analyzed: int,
        duration_seconds: float,
        timestamp: datetime | None = None,
        **kwargs,
    ):
        """Initialize cycle complete event.

        Args:
            cycle_id: Unique cycle identifier
            alerts_generated: Number of alerts generated this cycle
            services_analyzed: Number of services analyzed
            duration_seconds: Cycle execution duration
            timestamp: Cycle completion time
            **kwargs: Additional BaseEvent parameters

        """
        payload = {
            "cycle_id": cycle_id,
            "alerts_generated": alerts_generated,
            "services_analyzed": services_analyzed,
            "duration_seconds": duration_seconds,
        }

        super().__init__(
            event_type="monitoring.cycle_complete",
            source="hive-orchestrator.monitoring-service",
            payload=payload,
            timestamp=timestamp,
            **kwargs,
        )

    @property
    def cycle_id(self) -> str:
        """Get cycle ID"""
        return self.payload["cycle_id"]

    @property
    def alerts_generated(self) -> int:
        """Get alerts generated count"""
        return self.payload["alerts_generated"]

    @property
    def services_analyzed(self) -> int:
        """Get services analyzed count"""
        return self.payload["services_analyzed"]

    @property
    def duration_seconds(self) -> float:
        """Get cycle duration"""
        return self.payload["duration_seconds"]


@dataclass
class MonitoringHealthChangeEvent(BaseEvent):
    """Event emitted when monitoring service health status changes.

    Used for monitoring the monitor - ensures the monitoring service
    itself is healthy and operational.
    """

    def __init__(
        self,
        previous_status: str,
        current_status: str,
        reason: str,
        **kwargs,
    ):
        """Initialize health change event.

        Args:
            previous_status: Previous health status (healthy, degraded, unhealthy)
            current_status: Current health status
            reason: Reason for status change
            **kwargs: Additional BaseEvent parameters

        """
        payload = {
            "previous_status": previous_status,
            "current_status": current_status,
            "reason": reason,
        }

        super().__init__(
            event_type="monitoring.health_change",
            source="hive-orchestrator.monitoring-service",
            payload=payload,
            **kwargs,
        )

    @property
    def previous_status(self) -> str:
        """Get previous status"""
        return self.payload["previous_status"]

    @property
    def current_status(self) -> str:
        """Get current status"""
        return self.payload["current_status"]

    @property
    def reason(self) -> str:
        """Get reason for change"""
        return self.payload["reason"]
