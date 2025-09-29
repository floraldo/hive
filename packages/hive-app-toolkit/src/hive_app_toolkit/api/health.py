"""Health check endpoints for Kubernetes integration."""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..config.app_config import HiveAppConfig


class HealthStatus(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: Optional[str] = None
    components: Optional[Dict[str, str]] = None
    metrics: Optional[Dict[str, Any]] = None


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
        self.components: List[ComponentCheck] = []
        self.custom_metrics: Dict[str, Callable[[], Any]] = {}

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
