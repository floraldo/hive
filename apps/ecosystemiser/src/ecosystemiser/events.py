"""
EcoSystemiser Event System

Extends the generic hive-bus with EcoSystemiser-specific events and patterns.
Follows the inherit→extend pattern for event-driven architecture.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hive_bus import BaseEvent
from hive_logging import get_logger

logger = get_logger(__name__)


class EcoSystemiserEvent(BaseEvent):
    """Base class for all EcoSystemiser events"""

    def __init__(
        self,
        event_type: str,
        component: str,
        data: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(event_type=event_type, source="ecosystemiser", data=data or {}, correlation_id=correlation_id)
        self.component = component


class ClimateDataFetchedEvent(EcoSystemiserEvent):
    """Event fired when climate data is successfully fetched"""

    def __init__(
        self,
        location: tuple[float, float],
        variables: list[str],
        source: str,
        correlation_id: str | None = None,
    ):
        super().__init__(
            event_type="climate_data_fetched",
            component="climate_service",
            data={
                "location": location,
                "variables": variables,
                "source": source,
                "timestamp": datetime.utcnow().isoformat(),
            },
            correlation_id=correlation_id,
        )


class SolverExecutionStartedEvent(EcoSystemiserEvent):
    """Event fired when solver execution begins"""

    def __init__(self, solver_type: str, system_id: str, config: dict[str, Any], correlation_id: str | None = None):
        super().__init__(
            event_type="solver_execution_started",
            component="solver",
            data={
                "solver_type": solver_type,
                "system_id": system_id,
                "config": config,
                "timestamp": datetime.utcnow().isoformat(),
            },
            correlation_id=correlation_id,
        )


class SolverExecutionCompletedEvent(EcoSystemiserEvent):
    """Event fired when solver execution completes"""

    def __init__(
        self,
        solver_type: str,
        system_id: str,
        status: str,
        execution_time: float,
        correlation_id: str | None = None,
    ):
        super().__init__(
            event_type="solver_execution_completed",
            component="solver",
            data={
                "solver_type": solver_type,
                "system_id": system_id,
                "status": status,
                "execution_time": execution_time,
                "timestamp": datetime.utcnow().isoformat(),
            },
            correlation_id=correlation_id,
        )


class ComponentValidationEvent(EcoSystemiserEvent):
    """Event fired when component validation occurs"""

    def __init__(
        self,
        component_id: str,
        component_type: str,
        validation_status: str,
        issues: list[str] | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(
            event_type="component_validation",
            component="validation",
            data={
                "component_id": component_id,
                "component_type": component_type,
                "validation_status": validation_status,
                "issues": issues or [],
                "timestamp": datetime.utcnow().isoformat(),
            },
            correlation_id=correlation_id,
        )


# Event type constants for easy reference
class EventTypes:
    CLIMATE_DATA_FETCHED = "climate_data_fetched"
    SOLVER_EXECUTION_STARTED = "solver_execution_started"
    SOLVER_EXECUTION_COMPLETED = "solver_execution_completed"
    COMPONENT_VALIDATION = "component_validation"
