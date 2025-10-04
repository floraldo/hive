"""Orchestration Event Bus

Provides get_async_event_bus() for task, workflow, and agent coordination events.
This is a thin wrapper around hive-bus for orchestration-specific needs.
"""

from __future__ import annotations

from hive_bus import BaseBus
from hive_logging import get_logger

logger = get_logger(__name__)


# Global event bus instance
_event_bus_instance: BaseBus | None = None


def get_async_event_bus() -> BaseBus:
    """Get the async event bus instance for orchestration.

    Returns:
        BaseBus: Event bus for publishing/subscribing to orchestration events

    Example:
        ```python
        from hive_orchestration import get_async_event_bus, TaskEvent

        bus = get_async_event_bus()
        await bus.publish(TaskEvent(
            task_id="task-123",
            event_type="started",
            payload={"worker": "worker-1"}
        ))
        ```

    """
    global _event_bus_instance

    if _event_bus_instance is None:
        _event_bus_instance = BaseBus()
        logger.info("Orchestration event bus initialized")

    return _event_bus_instance


def reset_event_bus() -> None:
    """Reset the event bus instance (for testing)"""
    global _event_bus_instance
    _event_bus_instance = None


__all__ = ["get_async_event_bus", "reset_event_bus"]
