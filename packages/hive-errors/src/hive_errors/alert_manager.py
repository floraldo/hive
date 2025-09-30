"""
Predictive alert management system.

Manages the lifecycle of predictive alerts, including creation,
routing, deduplication, and resolution.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from hive_logging import get_logger

from .predictive_alerts import AlertSeverity, DegradationAlert, MetricPoint, MetricType, TrendAnalyzer

logger = get_logger(__name__)


@dataclass
class AlertConfig:
    """Configuration for predictive alerts."""

    service_name: str
    metric_type: MetricType
    threshold: float
    confidence_threshold: float = 0.75
    degradation_window_minutes: int = 30
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRoutingRule:
    """Rules for routing alerts based on severity."""

    severity: AlertSeverity
    channels: list[str]  # e.g., ["github", "slack", "pagerduty"]
    escalation_time_minutes: int | None = None
    require_acknowledgment: bool = False


class PredictiveAlertManager:
    """
    Manage predictive alerts based on monitoring data.

    Integrates with MonitoringErrorReporter and HealthMonitor to
    analyze trends and generate proactive alerts.
    """

    def __init__(self, configs: list[AlertConfig] | None = None, routing_rules: list[AlertRoutingRule] | None = None):
        """
        Initialize predictive alert manager.

        Args:
            configs: Alert configurations per service/metric
            routing_rules: Alert routing rules by severity
        """
        self.configs: dict[tuple[str, MetricType], AlertConfig] = {}
        if configs:
            for config in configs:
                self.configs[(config.service_name, config.metric_type)] = config

        self.routing_rules: dict[AlertSeverity, AlertRoutingRule] = {}
        if routing_rules:
            for rule in routing_rules:
                self.routing_rules[rule.severity] = rule
        else:
            self._setup_default_routing_rules()

        self.trend_analyzer = TrendAnalyzer()
        self.active_alerts: dict[str, DegradationAlert] = {}
        self.alert_history: list[DegradationAlert] = []

        # Statistics
        self.stats = {
            "total_alerts_generated": 0,
            "alerts_by_severity": defaultdict(int),
            "alerts_by_service": defaultdict(int),
            "true_positives": 0,
            "false_positives": 0,
        }

    def _setup_default_routing_rules(self) -> None:
        """Setup default alert routing rules."""
        self.routing_rules = {
            AlertSeverity.CRITICAL: AlertRoutingRule(
                severity=AlertSeverity.CRITICAL,
                channels=["pagerduty", "slack_critical", "github"],
                escalation_time_minutes=5,
                require_acknowledgment=True,
            ),
            AlertSeverity.HIGH: AlertRoutingRule(
                severity=AlertSeverity.HIGH,
                channels=["slack_alerts", "github"],
                escalation_time_minutes=15,
                require_acknowledgment=False,
            ),
            AlertSeverity.MEDIUM: AlertRoutingRule(
                severity=AlertSeverity.MEDIUM,
                channels=["slack_monitoring"],
                escalation_time_minutes=None,
                require_acknowledgment=False,
            ),
            AlertSeverity.LOW: AlertRoutingRule(
                severity=AlertSeverity.LOW,
                channels=["github"],
                escalation_time_minutes=None,
                require_acknowledgment=False,
            ),
        }

    def add_config(self, config: AlertConfig) -> None:
        """Add or update alert configuration."""
        key = (config.service_name, config.metric_type)
        self.configs[key] = config
        logger.info(f"Added alert config: {config.service_name}/{config.metric_type.value}")

    def get_config(self, service_name: str, metric_type: MetricType) -> AlertConfig | None:
        """Get alert configuration for service/metric."""
        return self.configs.get((service_name, metric_type))

    async def analyze_metrics_async(
        self,
        service_name: str,
        metric_type: MetricType,
        metrics: list[MetricPoint],
    ) -> DegradationAlert | None:
        """
        Analyze metric trend and generate alert if degradation detected.

        Args:
            service_name: Name of service being monitored
            metric_type: Type of metric being analyzed
            metrics: Historical metric data points

        Returns:
            DegradationAlert if degradation detected, None otherwise
        """
        # Get configuration
        config = self.get_config(service_name, metric_type)
        if not config or not config.enabled:
            logger.debug(f"Alert disabled or not configured for {service_name}/{metric_type.value}")
            return None

        # Enrich metrics with metadata
        for metric in metrics:
            metric.metadata.update({"service": service_name, "metric_type": metric_type.value})

        # Detect degradation
        alert = self.trend_analyzer.detect_degradation(metrics, config.threshold)

        if alert and alert.confidence >= config.confidence_threshold:
            # Check for duplicate alerts
            if self._is_duplicate_alert(alert):
                logger.debug(f"Duplicate alert suppressed: {alert.alert_id}")
                return None

            # Store active alert
            self.active_alerts[alert.alert_id] = alert
            self.alert_history.append(alert)

            # Update statistics
            self.stats["total_alerts_generated"] += 1
            self.stats["alerts_by_severity"][alert.severity.value] += 1
            self.stats["alerts_by_service"][service_name] += 1

            logger.warning(
                f"Predictive alert generated: {alert.service_name}/{alert.metric_type.value} "
                f"[{alert.severity.value}] - {alert.confidence:.0%} confidence",
            )

            # Route alert
            await self._route_alert_async(alert)

            return alert

        return None

    def _is_duplicate_alert(self, alert: DegradationAlert) -> bool:
        """
        Check if alert is duplicate of existing active alert.

        Args:
            alert: Alert to check

        Returns:
            True if duplicate exists
        """
        for active_alert in self.active_alerts.values():
            if (
                active_alert.service_name == alert.service_name
                and active_alert.metric_type == alert.metric_type
                and active_alert.severity == alert.severity
            ):
                # Check if active alert is recent (within last 30 minutes)
                alert_age = datetime.utcnow() - active_alert.created_at
                if alert_age < timedelta(minutes=30):
                    return True

        return False

    async def _route_alert_async(self, alert: DegradationAlert) -> None:
        """
        Route alert to configured channels based on severity.

        Args:
            alert: Alert to route
        """
        routing_rule = self.routing_rules.get(alert.severity)
        if not routing_rule:
            logger.warning(f"No routing rule for severity: {alert.severity.value}")
            return

        logger.info(f"Routing alert {alert.alert_id} to channels: {routing_rule.channels}")

        # Route to each configured channel
        tasks = []
        for channel in routing_rule.channels:
            if channel == "github":
                tasks.append(self._send_to_github_async(alert))
            elif channel.startswith("slack"):
                tasks.append(self._send_to_slack_async(alert, channel))
            elif channel == "pagerduty":
                tasks.append(self._send_to_pagerduty_async(alert))
            else:
                logger.warning(f"Unknown routing channel: {channel}")

        # Execute all routing tasks in parallel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_github_async(self, alert: DegradationAlert) -> None:
        """
        Create GitHub issue for alert.

        Args:
            alert: Alert to create issue for
        """
        try:
            # This would integrate with GitHub API
            # For now, log the action
            logger.info(f"GitHub issue creation for alert: {alert.alert_id}")

            # Issue content
            issue_title = (
                f"🚨 Predictive Alert: {alert.service_name} {alert.metric_type.value} [{alert.severity.value.upper()}]"
            )

            issue_body = self._format_alert_for_github(alert)

            logger.info(f"GitHub Issue:\nTitle: {issue_title}\n\nBody:\n{issue_body}")

            # TODO: Actually create GitHub issue via API
            # gh_client.create_issue(title=issue_title, body=issue_body, labels=[...])

        except Exception as e:
            logger.error(f"Failed to send alert to GitHub: {e}")

    async def _send_to_slack_async(self, alert: DegradationAlert, channel: str) -> None:
        """
        Send alert to Slack channel.

        Args:
            alert: Alert to send
            channel: Slack channel identifier
        """
        try:
            logger.info(f"Slack notification to {channel} for alert: {alert.alert_id}")

            message = self._format_alert_for_slack(alert)

            logger.info(f"Slack Message ({channel}):\n{message}")

            # TODO: Actually send to Slack via webhook
            # slack_client.post_message(channel=channel, text=message)

        except Exception as e:
            logger.error(f"Failed to send alert to Slack: {e}")

    async def _send_to_pagerduty_async(self, alert: DegradationAlert) -> None:
        """
        Send alert to PagerDuty.

        Args:
            alert: Alert to send
        """
        try:
            logger.info(f"PagerDuty incident for alert: {alert.alert_id}")

            incident_payload = self._format_alert_for_pagerduty(alert)

            logger.info(f"PagerDuty Incident:\n{incident_payload}")

            # TODO: Actually create PagerDuty incident
            # pagerduty_client.trigger_incident(payload=incident_payload)

        except Exception as e:
            logger.error(f"Failed to send alert to PagerDuty: {e}")

    def _format_alert_for_github(self, alert: DegradationAlert) -> str:
        """Format alert as GitHub issue body."""
        time_to_breach_str = (
            f"{alert.time_to_breach.total_seconds() / 3600:.1f} hours" if alert.time_to_breach else "N/A"
        )

        lines = [
            "# Predictive Alert",
            "",
            f"**Service**: {alert.service_name}",
            f"**Metric**: {alert.metric_type.value}",
            f"**Severity**: {alert.severity.value.upper()}",
            f"**Confidence**: {alert.confidence:.0%}",
            "",
            "## Current Status",
            "",
            f"- **Current Value**: {alert.current_value:.2f}",
            f"- **Predicted Value**: {alert.predicted_value:.2f}",
            f"- **Threshold**: {alert.threshold:.2f}",
            f"- **Time to Breach**: {time_to_breach_str}",
            "",
            "## Recommended Actions",
            "",
        ]

        for action in alert.recommended_actions:
            lines.append(f"- {action}")

        lines.extend(
            [
                "",
                "## Details",
                "",
                f"- **Alert ID**: `{alert.alert_id}`",
                f"- **Created**: {alert.created_at.isoformat()}",
                "",
                "---",
                "",
                "*Generated by PROJECT VANGUARD Predictive Alert System*",
            ],
        )

        return "\n".join(lines)

    def _format_alert_for_slack(self, alert: DegradationAlert) -> str:
        """Format alert as Slack message."""
        severity_emoji = {
            AlertSeverity.CRITICAL: "🔴",
            AlertSeverity.HIGH: "🟠",
            AlertSeverity.MEDIUM: "🟡",
            AlertSeverity.LOW: "🟢",
        }

        emoji = severity_emoji.get(alert.severity, "⚠️")

        time_to_breach_str = (
            f"{alert.time_to_breach.total_seconds() / 3600:.1f} hours" if alert.time_to_breach else "N/A"
        )

        lines = [
            f"{emoji} *Predictive Alert: {alert.service_name}*",
            "",
            f"*Metric*: {alert.metric_type.value}",
            f"*Severity*: {alert.severity.value.upper()}",
            f"*Confidence*: {alert.confidence:.0%}",
            f"*Time to Breach*: {time_to_breach_str}",
            "",
            f"Current: {alert.current_value:.2f} | Threshold: {alert.threshold:.2f}",
            "",
            "*Recommended Actions*:",
        ]

        for action in alert.recommended_actions[:3]:  # Top 3 actions for Slack
            lines.append(f"• {action}")

        return "\n".join(lines)

    def _format_alert_for_pagerduty(self, alert: DegradationAlert) -> dict[str, Any]:
        """Format alert as PagerDuty incident payload."""
        return {
            "routing_key": "YOUR_INTEGRATION_KEY",  # Would be configured
            "event_action": "trigger",
            "payload": {
                "summary": f"Predictive Alert: {alert.service_name} {alert.metric_type.value}",
                "severity": alert.severity.value,
                "source": alert.service_name,
                "custom_details": {
                    "alert_id": alert.alert_id,
                    "metric_type": alert.metric_type.value,
                    "current_value": alert.current_value,
                    "threshold": alert.threshold,
                    "confidence": alert.confidence,
                    "recommended_actions": alert.recommended_actions,
                },
            },
        }

    async def resolve_alert_async(self, alert_id: str, resolution_note: str = "") -> bool:
        """
        Resolve an active alert.

        Args:
            alert_id: ID of alert to resolve
            resolution_note: Optional note about resolution

        Returns:
            True if alert was resolved
        """
        if alert_id not in self.active_alerts:
            logger.warning(f"Alert not found: {alert_id}")
            return False

        self.active_alerts.pop(alert_id)

        logger.info(f"Alert resolved: {alert_id} - {resolution_note}")

        # TODO: Update external systems (GitHub, PagerDuty, etc.)

        return True

    def get_active_alerts(
        self,
        service_name: str | None = None,
        severity: AlertSeverity | None = None,
    ) -> list[DegradationAlert]:
        """
        Get currently active alerts with optional filtering.

        Args:
            service_name: Filter by service name
            severity: Filter by severity

        Returns:
            List of active alerts matching filters
        """
        alerts = list(self.active_alerts.values())

        if service_name:
            alerts = [a for a in alerts if a.service_name == service_name]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts

    def get_stats(self) -> dict[str, Any]:
        """Get alert manager statistics."""
        return {
            **self.stats,
            "active_alerts_count": len(self.active_alerts),
            "alert_history_count": len(self.alert_history),
        }

    def clear_old_alerts(self, hours: int = 24) -> int:
        """
        Clear old active alerts that haven't been resolved.

        Args:
            hours: Age threshold for clearing alerts

        Returns:
            Number of alerts cleared
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        alerts_to_clear = [alert_id for alert_id, alert in self.active_alerts.items() if alert.created_at < cutoff]

        for alert_id in alerts_to_clear:
            self.active_alerts.pop(alert_id)
            logger.info(f"Cleared old alert: {alert_id}")

        return len(alerts_to_clear)
