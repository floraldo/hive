"""
Pipeline Monitoring Implementation
Contains the business logic for pipeline monitoring.
Separated from core interfaces to maintain clean architecture.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineMetrics:
    """Metrics for pipeline execution"""

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_duration_ms: float = 0.0
    stage_durations: dict[str, float] = field(default_factory=dict)
    error_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_execution_time: datetime | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100

    @property
    def average_duration_ms(self) -> float:
        """Calculate average duration"""
        if self.total_executions == 0:
            return 0.0
        return self.total_duration_ms / self.total_executions

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": self.success_rate,
            "average_duration_ms": self.average_duration_ms,
            "total_duration_ms": self.total_duration_ms,
            "stage_durations": self.stage_durations,
            "error_counts": dict(self.error_counts),
            "last_execution_time": self.last_execution_time.isoformat() if self.last_execution_time else None,
        }


@dataclass
class StageMetrics:
    """Metrics for individual pipeline stages"""

    stage_name: str
    execution_count: int = 0
    total_duration_ms: float = 0.0
    error_count: int = 0
    last_error: str | None = None
    last_execution: datetime | None = None

    @property
    def average_duration_ms(self) -> float:
        """Calculate average stage duration"""
        if self.execution_count == 0:
            return 0.0
        return self.total_duration_ms / self.execution_count

    @property
    def error_rate(self) -> float:
        """Calculate error rate for this stage"""
        if self.execution_count == 0:
            return 0.0
        return (self.error_count / self.execution_count) * 100


class PipelineMonitor:
    """Implementation of pipeline monitoring with metrics collection"""

    def __init__(self, pipeline_name: str, retention_hours: int = 24) -> None:
        self.pipeline_name = pipeline_name
        self.retention_hours = retention_hours
        self.metrics = PipelineMetrics()
        self.stage_metrics: dict[str, StageMetrics] = {}
        self.execution_history: deque = deque(maxlen=1000)
        self.lock = Lock()
        self._active_executions: dict[str, float] = {}

    def start_execution(self, execution_id: str) -> None:
        """Start tracking a pipeline execution"""
        with self.lock:
            self._active_executions[execution_id] = time.time()
            logger.debug(f"Started tracking execution {execution_id} for pipeline {self.pipeline_name}")

    def end_execution(self, execution_id: str, success: bool, error: str | None = None) -> None:
        """End tracking a pipeline execution"""
        with self.lock:
            if execution_id not in self._active_executions:
                logger.warning(f"Execution {execution_id} not found in active executions")
                return

            start_time = self._active_executions.pop(execution_id)
            duration_ms = (time.time() - start_time) * 1000

            # Update metrics
            self.metrics.total_executions += 1
            self.metrics.total_duration_ms += duration_ms
            self.metrics.last_execution_time = datetime.now()

            if success:
                self.metrics.successful_executions += 1
            else:
                self.metrics.failed_executions += 1
                if error:
                    self.metrics.error_counts[error] += 1

            # Add to history
            self.execution_history.append(
                {
                    "execution_id": execution_id,
                    "timestamp": datetime.now(),
                    "duration_ms": duration_ms,
                    "success": success,
                    "error": error,
                },
            )

            logger.info(f"Completed execution {execution_id}: success={success}, duration={duration_ms:.2f}ms")

    def record_stage_execution(
        self, stage_name: str, duration_ms: float, success: bool, error: str | None = None,
    ) -> None:
        """Record execution of a pipeline stage"""
        with self.lock:
            if stage_name not in self.stage_metrics:
                self.stage_metrics[stage_name] = StageMetrics(stage_name=stage_name)

            stage = self.stage_metrics[stage_name]
            stage.execution_count += 1
            stage.total_duration_ms += duration_ms
            stage.last_execution = datetime.now()

            if not success:
                stage.error_count += 1
                stage.last_error = error

            # Update pipeline metrics
            self.metrics.stage_durations[stage_name] = stage.average_duration_ms

            logger.debug(f"Stage {stage_name} executed: duration={duration_ms:.2f}ms, success={success}")

    def get_metrics(self) -> dict[str, Any]:
        """Get current pipeline metrics"""
        with self.lock:
            metrics = self.metrics.to_dict()
            metrics["pipeline_name"] = self.pipeline_name
            metrics["active_executions"] = len(self._active_executions)
            metrics["stages"] = {
                name: {
                    "execution_count": stage.execution_count,
                    "average_duration_ms": stage.average_duration_ms,
                    "error_rate": stage.error_rate,
                    "last_error": stage.last_error,
                    "last_execution": stage.last_execution.isoformat() if stage.last_execution else None,
                }
                for name, stage in self.stage_metrics.items()
            }
            return metrics

    def get_recent_executions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent execution history"""
        with self.lock:
            recent = list(self.execution_history)[-limit:]
            return recent

    def clear_old_history(self) -> None:
        """Clear execution history older than retention period"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)

            # Filter history to keep only recent executions
            new_history = deque(maxlen=1000)
            for execution in self.execution_history:
                if execution["timestamp"] > cutoff_time:
                    new_history.append(execution)

            self.execution_history = new_history
            logger.info(
                f"Cleared old history for pipeline {self.pipeline_name}, kept {len(self.execution_history)} records",
            )

    def get_health_status(self) -> dict[str, Any]:
        """Get pipeline health status"""
        with self.lock:
            # Determine health based on recent performance
            recent_failures = sum(1 for exec in list(self.execution_history)[-10:] if not exec.get("success", False))

            if recent_failures >= 5:
                health = "unhealthy"
            elif recent_failures >= 2:
                health = "degraded"
            else:
                health = "healthy"

            return {
                "pipeline": self.pipeline_name,
                "health": health,
                "success_rate": self.metrics.success_rate,
                "recent_failures": recent_failures,
                "active_executions": len(self._active_executions),
                "last_execution": (
                    self.metrics.last_execution_time.isoformat() if self.metrics.last_execution_time else None
                ),
            }


class BaseMonitoringService(ABC):
    """Abstract base class defining the monitoring service interface.

    Establishes the service layer contract for all monitoring implementations
    following Golden Rule 10 - Service Layer Architecture standards.
    """

    @abstractmethod
    def get_or_create_monitor(self, pipeline_name: str) -> PipelineMonitor:
        """Get existing monitor or create new one for pipeline."""
        pass

    @abstractmethod
    def remove_monitor(self, pipeline_name: str) -> bool:
        """Remove monitor for specified pipeline."""
        pass

    @abstractmethod
    def get_monitor_status(self, pipeline_name: str) -> dict[str, Any] | None:
        """Get current status of pipeline monitor."""
        pass

    @abstractmethod
    def get_all_monitors_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all active monitors."""
        pass


class MonitoringService(BaseMonitoringService):
    """Service for managing multiple pipeline monitors"""

    def __init__(self) -> None:
        self.monitors: dict[str, PipelineMonitor] = {}
        self.lock = Lock()

    def get_or_create_monitor(self, pipeline_name: str) -> PipelineMonitor:
        """Get existing monitor or create new one"""
        with self.lock:
            if pipeline_name not in self.monitors:
                self.monitors[pipeline_name] = PipelineMonitor(pipeline_name)
                logger.info(f"Created new monitor for pipeline: {pipeline_name}")
            return self.monitors[pipeline_name]

    def get_all_metrics(self) -> dict[str, Any]:
        """Get metrics for all pipelines"""
        with self.lock:
            return {name: monitor.get_metrics() for name, monitor in self.monitors.items()}

    def get_health_summary(self) -> dict[str, Any]:
        """Get health summary for all pipelines"""
        with self.lock:
            summary = {"healthy": 0, "degraded": 0, "unhealthy": 0, "pipelines": {}}

            for name, monitor in self.monitors.items():
                health = monitor.get_health_status()
                summary["pipelines"][name] = health
                summary[health["health"]] += 1

            return summary

    def remove_monitor(self, pipeline_name: str) -> bool:
        """Remove monitor for specified pipeline."""
        with self.lock:
            if pipeline_name in self.monitors:
                del self.monitors[pipeline_name]
                logger.info(f"Removed monitor for pipeline: {pipeline_name}")
                return True
            return False

    def get_monitor_status(self, pipeline_name: str) -> dict[str, Any] | None:
        """Get current status of pipeline monitor."""
        with self.lock:
            if pipeline_name in self.monitors:
                return self.monitors[pipeline_name].get_health_status()
            return None

    def get_all_monitors_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all active monitors."""
        with self.lock:
            return {name: monitor.get_health_status() for name, monitor in self.monitors.items()}
