"""
Monitoring Service Protocols

Type protocols for dependencies used by monitoring service.
Enables type checking without circular dependencies.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class HealthMonitorProtocol(Protocol):
    """
    Protocol for health monitoring implementations.

    This protocol defines the interface for health monitors that
    can be used by the predictive monitoring service to gather
    system health metrics.
    """

    def get_cpu_metrics(self, service_name: str | None = None) -> list[dict[str, Any]]:
        """
        Get CPU utilization metrics.

        Args:
            service_name: Optional service name filter

        Returns:
            List of CPU metric points
        """
        ...

    def get_memory_metrics(self, service_name: str | None = None) -> list[dict[str, Any]]:
        """
        Get memory utilization metrics.

        Args:
            service_name: Optional service name filter

        Returns:
            List of memory metric points
        """
        ...

    def get_latency_metrics(self, service_name: str | None = None) -> list[dict[str, Any]]:
        """
        Get latency metrics.

        Args:
            service_name: Optional service name filter

        Returns:
            List of latency metric points
        """
        ...

    def get_component_health(self, component: str) -> dict[str, Any]:
        """
        Get health status for specific component.

        Args:
            component: Component name

        Returns:
            Health metrics for component
        """
        ...


@runtime_checkable
class EventBusProtocol(Protocol):
    """
    Protocol for event bus implementations.

    Defines the interface for event publishing that monitoring
    service needs to emit events to other system components.
    """

    def publish(self, event: Any) -> str:
        """
        Publish event synchronously.

        Args:
            event: Event to publish

        Returns:
            Event ID
        """
        ...

    async def publish_async(self, event: Any) -> str:
        """
        Publish event asynchronously.

        Args:
            event: Event to publish

        Returns:
            Event ID
        """
        ...

    def subscribe(self, event_pattern: str, callback: Any, subscriber_name: str = "anonymous") -> str:
        """
        Subscribe to events matching pattern.

        Args:
            event_pattern: Event type pattern to match
            callback: Callback function to invoke
            subscriber_name: Name for subscriber tracking

        Returns:
            Subscription ID
        """
        ...
