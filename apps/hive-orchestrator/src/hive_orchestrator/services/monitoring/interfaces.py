"""Monitoring Service Interfaces

Defines contracts for monitoring service integration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IMonitoringService(ABC):
    """Interface for monitoring service implementations"""

    @abstractmethod
    async def run_analysis_cycle(self) -> dict[str, Any]:
        """Run single predictive analysis cycle.

        Returns:
            Analysis results with alerts and statistics

        """

    @abstractmethod
    async def start_continuous_monitoring(self, interval_minutes: int) -> None:
        """Start continuous monitoring with periodic analysis.

        Args:
            interval_minutes: Interval between analysis cycles

        """

    @abstractmethod
    def get_metrics(self) -> dict[str, Any]:
        """Get monitoring service health metrics.

        Returns:
            Service metrics and statistics

        """

    @abstractmethod
    def get_component_health(self, component: str) -> dict[str, Any]:
        """Get health status for specific component.

        Args:
            component: Component name

        Returns:
            Health metrics for component

        """
