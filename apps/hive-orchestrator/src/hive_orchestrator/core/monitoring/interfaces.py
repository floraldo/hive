# ruff: noqa: E402
from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Monitoring Service Interfaces
Defines the abstract interfaces for monitoring services.
No business logic, only interface definitions.
"""

from abc import ABC, abstractmethod
from typing import Any


class PipelineMonitorInterface(ABC):
    """Abstract interface for pipeline monitoring"""

    @abstractmethod
    def start_execution(self, execution_id: str) -> None:
        """Start tracking a pipeline execution"""
        pass

    @abstractmethod
    def end_execution(self, execution_id: str, success: bool, error: str | None = None) -> None:
        """End tracking a pipeline execution"""
        pass

    @abstractmethod
    def record_stage_execution(
        self,
        stage_name: str,
        duration_ms: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Record execution of a pipeline stage"""
        pass

    @abstractmethod
    def get_metrics(self) -> dict[str, Any]:
        """Get current pipeline metrics"""
        pass

    @abstractmethod
    def get_health_status(self) -> dict[str, Any]:
        """Get pipeline health status"""
        pass


class MetricsCollectorInterface(ABC):
    """Abstract interface for metrics collection"""

    @abstractmethod
    def record_metric(self, metric_name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Record a metric value"""
        pass

    @abstractmethod
    def increment_counter(self, counter_name: str, value: int = 1, tags: dict[str, str] | None = None) -> None:
        """Increment a counter metric"""
        pass

    @abstractmethod
    def record_histogram(self, histogram_name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Record a histogram value"""
        pass

    @abstractmethod
    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary"""
        pass


class HealthCheckInterface(ABC):
    """Abstract interface for health checking"""

    @abstractmethod
    async def check_health_async(self) -> dict[str, Any]:
        """Perform health check"""
        pass

    @abstractmethod
    def get_readiness(self) -> bool:
        """Check if service is ready"""
        pass

    @abstractmethod
    def get_liveness(self) -> bool:
        """Check if service is alive"""
        pass
