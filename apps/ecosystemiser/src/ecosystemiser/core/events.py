"""EcoSystemiser-specific event types.,

Extends the generic messaging toolkit with EcoSystemiser-specific events:
- Simulation lifecycle events
- Analysis workflow events
- Optimization progress events
- Component state change events
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

try:
    from hive_bus import BaseEvent
except ImportError:
    # Fallback implementation if hive_messaging is not available
    class BaseEvent:
        """Base event class for fallback implementation."""

        def __init__(self, event_type: str, source: str = "unknown", **kwargs) -> None:
            self.event_type = event_type
            self.source = source
            self.timestamp = datetime.now(UTC)
            self.event_id = str(uuid.uuid4())
            for key, value in kwargs.items():
                setattr(self, key, value)


from hive_logging import get_logger

logger = get_logger(__name__)


class EcoSystemiserEvent(BaseEvent):
    """Base event class for all EcoSystemiser events.,

    Extends BaseEvent with simulation context and EcoSystemiser-specific,
    metadata fields.,
    """

    def __init__(
        self,
        event_type: str,
        source: str = "ecosystemiser",
        payload: dict[str, Any] | None = None,
        simulation_id: str | None = None,
        analysis_id: str | None = None,
        optimization_id: str | None = None,
        timestep: int | None = None,
        **kwargs,
    ):
        """Initialize an EcoSystemiser event.

        Args:
            event_type: Type of event,
            source: Source component,
            payload: Event payload data,
            simulation_id: Associated simulation ID,
            analysis_id: Associated analysis ID,
            optimization_id: Associated optimization ID,
            timestep: Simulation timestep if applicable,

        """
        super().__init__(event_type=event_type, source=source, payload=payload or {}, **kwargs)

        # EcoSystemiser-specific fields
        self.simulation_id = simulation_id
        self.analysis_id = analysis_id
        self.optimization_id = optimization_id
        self.timestep = timestep

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EcoSystemiserEvent:
        """Create event from dictionary"""
        return cls(
            event_type=data.get("event_type", "unknown"),
            source=data.get("source", "ecosystemiser"),
            payload=data.get("payload", {}),
            simulation_id=data.get("simulation_id"),
            analysis_id=data.get("analysis_id"),
            optimization_id=data.get("optimization_id"),
            timestep=data.get("timestep"),
            event_id=data.get("event_id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", datetime.now(UTC)),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


# ===============================================================================
# SIMULATION EVENTS
# ===============================================================================


class SimulationEvent(EcoSystemiserEvent):
    """Events related to simulation lifecycle and execution"""

    def __init__(self, event_type: str, **kwargs) -> None:
        super().__init__(event_type=f"simulation.{event_type}", source=kwargs.get("source", "simulation"), **kwargs)

    @classmethod
    def started(cls, simulation_id: str, config: dict[str, Any], **kwargs) -> SimulationEvent:
        """Create simulation started event"""
        return cls(
            event_type="started",
            simulation_id=simulation_id,
            payload={"simulation_id": simulation_id, "config": config, "status": "started"},
            **kwargs,
        )

    @classmethod
    def completed(
        cls,
        simulation_id: str,
        results: dict[str, Any],
        duration_seconds: float,
        **kwargs,
    ) -> SimulationEvent:
        """Create simulation completed event"""
        return cls(
            event_type="completed",
            simulation_id=simulation_id,
            payload={
                "simulation_id": simulation_id,
                "results": results,
                "duration_seconds": duration_seconds,
                "status": "completed",
            },
            **kwargs,
        )

    @classmethod
    def failed(
        cls,
        simulation_id: str,
        error_message: str,
        error_details: dict[str, Any] | None = None,
        **kwargs,
    ) -> SimulationEvent:
        """Create simulation failed event"""
        return cls(
            event_type="failed",
            simulation_id=simulation_id,
            payload={
                "simulation_id": simulation_id,
                "error_message": error_message,
                "error_details": error_details or {},
                "status": "failed",
            },
            **kwargs,
        )

    @classmethod
    def progress(
        cls,
        simulation_id: str,
        timestep: int,
        total_timesteps: int,
        status_message: str,
        **kwargs,
    ) -> SimulationEvent:
        """Create simulation progress event"""
        return cls(
            event_type="progress",
            simulation_id=simulation_id,
            timestep=timestep,
            payload={
                "simulation_id": simulation_id,
                "timestep": timestep,
                "total_timesteps": total_timesteps,
                "progress_percent": ((timestep / total_timesteps) * 100 if total_timesteps > 0 else 0),
                "status_message": status_message,
            },
            **kwargs,
        )


# ===============================================================================
# ANALYSIS EVENTS
# ===============================================================================


class AnalysisEvent(EcoSystemiserEvent):
    """Events related to analysis workflows and results"""

    def __init__(self, event_type: str, **kwargs) -> None:
        super().__init__(event_type=f"analysis.{event_type}", source=kwargs.get("source", "analysis"), **kwargs)

    @classmethod
    def started(cls, analysis_id: str, analysis_type: str, parameters: dict[str, Any], **kwargs) -> AnalysisEvent:
        """Create analysis started event"""
        return cls(
            event_type="started",
            analysis_id=analysis_id,
            payload={
                "analysis_id": analysis_id,
                "analysis_type": analysis_type,
                "parameters": parameters,
                "status": "started",
            },
            **kwargs,
        )

    @classmethod
    def completed(
        cls,
        analysis_id: str,
        results: dict[str, Any],
        insights: list[str] | None = None,
        **kwargs,
    ) -> AnalysisEvent:
        """Create analysis completed event"""
        return cls(
            event_type="completed",
            analysis_id=analysis_id,
            payload={"analysis_id": analysis_id, "results": results, "insights": insights or [], "status": "completed"},
            **kwargs,
        )

    @classmethod
    def failed(
        cls,
        analysis_id: str,
        error_message: str,
        error_details: dict[str, Any] | None = None,
        **kwargs,
    ) -> AnalysisEvent:
        """Create analysis failed event"""
        return cls(
            event_type="failed",
            analysis_id=analysis_id,
            payload={
                "analysis_id": analysis_id,
                "error_message": error_message,
                "error_details": error_details or {},
                "status": "failed",
            },
            **kwargs,
        )


# ===============================================================================
# STUDY EVENTS
# ===============================================================================


class StudyEvent(EcoSystemiserEvent):
    """Events related to multi-simulation study lifecycle and execution"""

    def __init__(self, event_type: str, **kwargs) -> None:
        super().__init__(event_type=f"study.{event_type}", source=kwargs.get("source", "study"), **kwargs)

    @classmethod
    def started(cls, study_id: str, config: dict[str, Any], source_agent: str = "StudyService", **kwargs) -> StudyEvent:
        """Create study started event"""
        return cls(
            event_type="started",
            study_id=study_id,
            source=source_agent,
            payload={"study_id": study_id, "config": config, "status": "started"},
            **kwargs,
        )

    @classmethod
    def completed(
        cls,
        study_id: str,
        results: dict[str, Any],
        duration_seconds: float,
        source_agent: str = "StudyService",
        **kwargs,
    ) -> StudyEvent:
        """Create study completed event"""
        return cls(
            event_type="completed",
            study_id=study_id,
            source=source_agent,
            payload={
                "study_id": study_id,
                "results": results,
                "duration_seconds": duration_seconds,
                "status": "completed",
            },
            **kwargs,
        )

    @classmethod
    def failed(
        cls,
        study_id: str,
        error_message: str,
        error_details: dict[str, Any] | None = None,
        source_agent: str = "StudyService",
        **kwargs,
    ) -> StudyEvent:
        """Create study failed event"""
        return cls(
            event_type="failed",
            study_id=study_id,
            source=source_agent,
            payload={
                "study_id": study_id,
                "error_message": error_message,
                "error_details": error_details or {},
                "status": "failed",
            },
            **kwargs,
        )

    @classmethod
    def metric_calculated(
        cls,
        analysis_id: str,
        metric_name: str,
        metric_value: float,
        metric_unit: str | None = None,
        **kwargs,
    ) -> AnalysisEvent:
        """Create metric calculated event"""
        return cls(
            event_type="metric_calculated",
            analysis_id=analysis_id,
            payload={
                "analysis_id": analysis_id,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "metric_unit": metric_unit,
            },
            **kwargs,
        )


# ===============================================================================
# OPTIMIZATION EVENTS
# ===============================================================================


class OptimizationEvent(EcoSystemiserEvent):
    """Events related to optimization processes"""

    def __init__(self, event_type: str, **kwargs) -> None:
        super().__init__(event_type=f"optimization.{event_type}", source=kwargs.get("source", "optimization"), **kwargs)

    @classmethod
    def started(cls, optimization_id: str, solver_type: str, objectives: list[str], **kwargs) -> OptimizationEvent:
        """Create optimization started event"""
        return cls(
            event_type="started",
            optimization_id=optimization_id,
            payload={
                "optimization_id": optimization_id,
                "solver_type": solver_type,
                "objectives": objectives,
                "status": "started",
            },
            **kwargs,
        )

    @classmethod
    def iteration(
        cls,
        optimization_id: str,
        iteration: int,
        objective_value: float,
        convergence_metric: float | None = None,
        **kwargs,
    ) -> OptimizationEvent:
        """Create optimization iteration event"""
        return cls(
            event_type="iteration",
            optimization_id=optimization_id,
            payload={
                "optimization_id": optimization_id,
                "iteration": iteration,
                "objective_value": objective_value,
                "convergence_metric": convergence_metric,
            },
            **kwargs,
        )

    @classmethod
    def converged(
        cls,
        optimization_id: str,
        final_objective: float,
        iterations: int,
        solution: dict[str, Any],
        **kwargs,
    ) -> OptimizationEvent:
        """Create optimization converged event"""
        return cls(
            event_type="converged",
            optimization_id=optimization_id,
            payload={
                "optimization_id": optimization_id,
                "final_objective": final_objective,
                "iterations": iterations,
                "solution": solution,
                "status": "converged",
            },
            **kwargs,
        )

    @classmethod
    def infeasible(
        cls,
        optimization_id: str,
        constraints_violated: list[str],
        solver_message: str | None = None,
        **kwargs,
    ) -> OptimizationEvent:
        """Create optimization infeasible event"""
        return cls(
            event_type="infeasible",
            optimization_id=optimization_id,
            payload={
                "optimization_id": optimization_id,
                "constraints_violated": constraints_violated,
                "solver_message": solver_message,
                "status": "infeasible",
            },
            **kwargs,
        )


# ===============================================================================
# COMPONENT EVENTS
# ===============================================================================


class ComponentEvent(EcoSystemiserEvent):
    """Events related to component lifecycle and state changes"""

    def __init__(self, event_type: str, **kwargs) -> None:
        super().__init__(event_type=f"component.{event_type}", source=kwargs.get("source", "component"), **kwargs)

    @classmethod
    def created(cls, component_name: str, component_type: str, parameters: dict[str, Any], **kwargs) -> ComponentEvent:
        """Create component created event"""
        return cls(
            event_type="created",
            payload={
                "component_name": component_name,
                "component_type": component_type,
                "parameters": parameters,
                "status": "created",
            },
            **kwargs,
        )

    @classmethod
    def configured(cls, component_name: str, configuration: dict[str, Any], **kwargs) -> ComponentEvent:
        """Create component configured event"""
        return cls(
            event_type="configured",
            payload={"component_name": component_name, "configuration": configuration, "status": "configured"},
            **kwargs,
        )

    @classmethod
    def state_changed(
        cls,
        component_name: str,
        old_state: str,
        new_state: str,
        timestep: int | None = None,
        **kwargs,
    ) -> ComponentEvent:
        """Create component state changed event"""
        return cls(
            event_type="state_changed",
            timestep=timestep,
            payload={
                "component_name": component_name,
                "old_state": old_state,
                "new_state": new_state,
                "timestep": timestep,
            },
            **kwargs,
        )


# ===============================================================================
# PROFILE LOADING EVENTS
# ===============================================================================


class ProfileEvent(EcoSystemiserEvent):
    """Events related to profile loading and processing"""

    def __init__(self, event_type: str, **kwargs) -> None:
        super().__init__(event_type=f"profile.{event_type}", source=kwargs.get("source", "profile_loader"), **kwargs)

    @classmethod
    def load_started(cls, profile_type: str, source: str, parameters: dict[str, Any], **kwargs) -> ProfileEvent:
        """Create profile load started event"""
        return cls(
            event_type="load_started",
            payload={"profile_type": profile_type, "source": source, "parameters": parameters, "status": "loading"},
            **kwargs,
        )

    @classmethod
    def load_completed(
        cls,
        profile_type: str,
        source: str,
        data_points: int,
        duration_seconds: float,
        **kwargs,
    ) -> ProfileEvent:
        """Create profile load completed event"""
        return cls(
            event_type="load_completed",
            payload={
                "profile_type": profile_type,
                "source": source,
                "data_points": data_points,
                "duration_seconds": duration_seconds,
                "status": "completed",
            },
            **kwargs,
        )

    @classmethod
    def validation_warning(
        cls,
        profile_type: str,
        warning_type: str,
        warning_message: str,
        affected_data_points: int | None = None,
        **kwargs,
    ) -> ProfileEvent:
        """Create profile validation warning event"""
        return cls(
            event_type="validation_warning",
            payload={
                "profile_type": profile_type,
                "warning_type": warning_type,
                "warning_message": warning_message,
                "affected_data_points": affected_data_points,
            },
            **kwargs,
        )


# Export main event classes
__all__ = [
    # Analysis events
    "AnalysisEvent",
    # Component events
    "ComponentEvent",
    # Base event
    "EcoSystemiserEvent",
    # Optimization events
    "OptimizationEvent",
    # Profile events
    "ProfileEvent",
    # Simulation events
    "SimulationEvent",
]
