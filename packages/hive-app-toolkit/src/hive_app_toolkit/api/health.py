"""
Health check endpoints and canonical base health monitoring.

CANONICAL BASE: BaseHealthMonitor
All health monitoring implementations across the platform should inherit
from BaseHealthMonitor to ensure consistent patterns and reduce code duplication.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from hive_logging import get_logger

from ..config.app_config import HiveAppConfig

logger = get_logger(__name__)


class HealthStatusLevel(Enum):
    """Standard health status levels across all components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    healthy: bool
    timestamp: datetime
    response_time_ms: float
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    status_level: HealthStatusLevel = HealthStatusLevel.UNKNOWN

    def __post_init__(self):
        """Determine status level from healthy flag if not set."""
        if self.status_level == HealthStatusLevel.UNKNOWN:
            if self.healthy:
                self.status_level = HealthStatusLevel.HEALTHY
            else:
                self.status_level = HealthStatusLevel.UNHEALTHY


class BaseHealthMonitor(ABC):
    """
    Canonical base class for all health monitoring implementations.

    Provides common functionality:
    - Health check execution with timing
    - Health history tracking
    - Alert threshold monitoring
    - Periodic monitoring loops
    - Consecutive failure tracking

    Component-specific implementations only need to override:
    - _perform_component_health_check_async()
    """

    def __init__(
        self,
        check_interval: int = 300,
        max_history_size: int = 100,
        alert_thresholds: dict[str, Any] | None = None,
    ):
        """
        Initialize base health monitor.

        Args:
            check_interval: Seconds between health checks
            max_history_size: Maximum health check results to store
            alert_thresholds: Custom alert thresholds
        """
        self.check_interval = check_interval
        self._max_history_size = max_history_size
        self._health_history: list[HealthCheckResult] = []
        self._monitoring_active = False
        self._monitoring_task: asyncio.Task | None = None
        self._consecutive_failures = 0

        # Default alert thresholds (can be overridden)
        self._alert_thresholds = alert_thresholds or {
            "response_time_ms": 1000,
            "error_rate_percent": 10,
            "consecutive_failures": 3,
        }

    @abstractmethod
    async def _perform_component_health_check_async(self) -> HealthCheckResult:
        """
        Perform component-specific health check.

        Override this method with component-specific logic (e.g., Redis ping,
        database connection test, AI model availability check).

        Returns:
            HealthCheckResult with component-specific details
        """
        pass

    async def perform_health_check_async(self) -> HealthCheckResult:
        """
        Perform health check with timing and error handling.

        This wraps the component-specific check with common functionality.
        """
        start_time = time.time()

        try:
            result = await self._perform_component_health_check_async()
            response_time_ms = (time.time() - start_time) * 1000

            # Update response time if not set by component
            if result.response_time_ms == 0:
                result.response_time_ms = response_time_ms

            # Add to history
            self._add_to_history(result)

            # Check alerts
            await self._check_alerts_async(result)

            return result

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Health check failed: {e}")

            result = HealthCheckResult(
                healthy=False,
                timestamp=datetime.utcnow(),
                response_time_ms=response_time_ms,
                errors=[str(e)],
                status_level=HealthStatusLevel.UNHEALTHY,
            )

            self._add_to_history(result)
            return result

    def _add_to_history(self, result: HealthCheckResult) -> None:
        """Add health check result to history."""
        self._health_history.append(result)

        # Maintain max history size
        if len(self._health_history) > self._max_history_size:
            self._health_history.pop(0)

    async def _check_alerts_async(self, result: HealthCheckResult) -> None:
        """Check if alerts should be generated."""
        alerts = []

        # Check response time
        if result.response_time_ms > self._alert_thresholds["response_time_ms"]:
            alerts.append(f"High response time: {result.response_time_ms:.2f}ms")

        # Check for failures
        if not result.healthy:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._alert_thresholds["consecutive_failures"]:
                alerts.append(f"Consecutive failures: {self._consecutive_failures}")
        else:
            self._consecutive_failures = 0

        # Check error rate over recent history
        if len(self._health_history) >= 10:
            recent_checks = self._health_history[-10:]
            failed_checks = sum(1 for check in recent_checks if not check.healthy)
            error_rate = (failed_checks / len(recent_checks)) * 100

            if error_rate > self._alert_thresholds["error_rate_percent"]:
                alerts.append(f"High error rate: {error_rate:.1f}%")

        # Log alerts
        for alert in alerts:
            logger.warning(f"Health alert: {alert}")

    async def start_monitoring_async(self) -> None:
        """Start continuous health monitoring."""
        if self._monitoring_active:
            logger.warning("Health monitoring already active")
            return

        self._monitoring_active = True
        logger.info("Starting health monitoring")

        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop_async())

    async def stop_monitoring_async(self) -> None:
        """Stop continuous health monitoring."""
        self._monitoring_active = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped health monitoring")

    async def _monitoring_loop_async(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                await self.perform_health_check_async()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(self.check_interval)

    def get_health_history(self, limit: int | None = None) -> list[HealthCheckResult]:
        """
        Get health check history.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of health check results
        """
        if limit is None:
            return self._health_history.copy()
        else:
            return self._health_history[-limit:]

    def get_health_summary(self) -> dict[str, Any]:
        """
        Get summary of health status.

        Returns:
            Health summary dictionary
        """
        if not self._health_history:
            return {"status": "unknown", "message": "No health checks performed yet"}

        recent_checks = self._health_history[-10:] if len(self._health_history) >= 10 else self._health_history
        healthy_count = sum(1 for check in recent_checks if check.healthy)
        health_rate = (healthy_count / len(recent_checks)) * 100

        latest_check = self._health_history[-1]
        avg_response_time = sum(check.response_time_ms for check in recent_checks) / len(recent_checks)

        status = "healthy"
        if health_rate < 50:
            status = "critical"
        elif health_rate < 80:
            status = "degraded"

        return {
            "status": status,
            "health_rate_percent": round(health_rate, 1),
            "average_response_time_ms": round(avg_response_time, 2),
            "last_check": latest_check.timestamp.isoformat(),
            "consecutive_failures": self._consecutive_failures,
            "total_checks": len(self._health_history),
            "monitoring_active": self._monitoring_active,
        }


class HealthStatus(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str | None = None
    components: dict[str, str] | None = None
    metrics: dict[str, Any] | None = None


class ComponentCheck:
    """Individual component health check."""

    def __init__(self, name: str, check_func: Callable[[], bool]) -> None:
        """Initialize component check."""
        self.name = name
        self.check_func = check_func

    async def check(self) -> tuple[str, str]:
        """Run the health check."""
        try:
            is_healthy = self.check_func()
            return self.name, "healthy" if is_healthy else "unhealthy"
        except Exception:
            return self.name, "unhealthy"


class HealthManager:
    """Manages health checks for the application."""

    def __init__(self) -> None:
        """Initialize health manager."""
        self.components: list[ComponentCheck] = []
        self.custom_metrics: dict[str, Callable[[], Any]] = {}

    def add_component(self, name: str, check_func: Callable[[], bool]) -> None:
        """Add a component health check."""
        self.components.append(ComponentCheck(name, check_func))

    def add_metric(self, name: str, metric_func: Callable[[], Any]) -> None:
        """Add a custom metric to health endpoint."""
        self.custom_metrics[name] = metric_func

    async def get_health_status(self, include_details: bool = True) -> HealthStatus:
        """Get overall health status."""
        # Check all components
        component_statuses = {}
        if include_details:
            for component in self.components:
                name, status = await component.check()
                component_statuses[name] = status

        # Determine overall status
        unhealthy_components = [name for name, status in component_statuses.items() if status == "unhealthy"]

        overall_status = "unhealthy" if unhealthy_components else "healthy"

        # Collect custom metrics
        metrics = {}
        if include_details:
            for name, metric_func in self.custom_metrics.items():
                try:
                    metrics[name] = metric_func()
                except Exception:
                    metrics[name] = "error"

        return HealthStatus(
            status=overall_status,
            timestamp=datetime.now().isoformat(),
            components=component_statuses if include_details else None,
            metrics=metrics if include_details else None,
        )


# Global health manager instance
_health_manager = HealthManager()


def get_health_manager() -> HealthManager:
    """Get the global health manager."""
    return _health_manager


def add_health_endpoints(app: FastAPI, config: HiveAppConfig) -> None:
    """
    Add health check endpoints to the application.

    Adds three endpoints:
    - /health: Detailed health check with component status
    - /health/live: Simple liveness probe for Kubernetes
    - /health/ready: Readiness probe for Kubernetes
    """

    @app.get("/health", response_model=HealthStatus)
    async def health_check():
        """
        Comprehensive health check endpoint.

        Returns detailed status including:
        - Overall application health
        - Individual component status
        - Custom metrics
        - Timestamp
        """
        try:
            status = await _health_manager.get_health_status(include_details=True)

            if status.status == "unhealthy":
                raise HTTPException(status_code=503, detail="Service unhealthy")

            return status

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

    @app.get("/health/live")
    async def liveness_probe():
        """
        Kubernetes liveness probe endpoint.

        Simple endpoint that returns 200 OK if the application is running.
        Kubernetes will restart the pod if this fails.
        """
        return {"status": "alive", "timestamp": datetime.now().isoformat()}

    @app.get("/health/ready")
    async def readiness_probe():
        """
        Kubernetes readiness probe endpoint.

        Returns 200 OK if the application is ready to serve traffic.
        Kubernetes will route traffic only when this succeeds.
        """
        try:
            status = await _health_manager.get_health_status(include_details=False)

            if status.status == "unhealthy":
                raise HTTPException(status_code=503, detail="Service not ready")

            return {"status": "ready", "timestamp": datetime.now().isoformat()}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Readiness check failed: {str(e)}")

    # Add default component checks
    if config.database.enabled:

        def check_database() -> bool:
            # Implement database connectivity check
            return True  # Placeholder

        _health_manager.add_component("database", check_database)

    if config.cache.enabled:

        def check_cache() -> bool:
            # Implement cache connectivity check
            return True  # Placeholder

        _health_manager.add_component("cache", check_cache)

    # Add default metrics
    def get_startup_time() -> str:
        """Get application startup time."""
        return datetime.now().isoformat()  # Simplified

    _health_manager.add_metric("startup_time", get_startup_time)
