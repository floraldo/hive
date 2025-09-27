"""
EcoSystemiser-specific events that inherit from Hive Event Bus.

Defines application-specific event types for simulation, analysis, and study workflows
while maintaining consistency with the broader Hive ecosystem event system.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path

from hive_bus import Event, create_workflow_event
from hive_bus.events import WorkflowEventType


class EcoSystemiserEventType:
    """Event types specific to EcoSystemiser workflows"""
    SIMULATION_STARTED = "ecosystemiser.simulation.started"
    SIMULATION_COMPLETED = "ecosystemiser.simulation.completed"
    SIMULATION_FAILED = "ecosystemiser.simulation.failed"

    STUDY_STARTED = "ecosystemiser.study.started"
    STUDY_COMPLETED = "ecosystemiser.study.completed"
    STUDY_FAILED = "ecosystemiser.study.failed"

    ANALYSIS_STARTED = "ecosystemiser.analysis.started"
    ANALYSIS_COMPLETED = "ecosystemiser.analysis.completed"
    ANALYSIS_FAILED = "ecosystemiser.analysis.failed"

    OPTIMIZATION_STARTED = "ecosystemiser.optimization.started"
    OPTIMIZATION_ITERATION = "ecosystemiser.optimization.iteration"
    OPTIMIZATION_COMPLETED = "ecosystemiser.optimization.completed"
    OPTIMIZATION_FAILED = "ecosystemiser.optimization.failed"


@dataclass
class SimulationEvent(Event):
    """Event for simulation lifecycle notifications"""

    simulation_id: str = ""
    system_config_path: Optional[str] = None
    results_path: Optional[str] = None
    solver_type: Optional[str] = None
    duration_seconds: Optional[float] = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EcoSystemiserEventType.SIMULATION_STARTED

        # Add simulation info to payload
        self.payload.update({
            "simulation_id": self.simulation_id,
            "system_config_path": self.system_config_path,
            "results_path": self.results_path,
            "solver_type": self.solver_type,
            "duration_seconds": self.duration_seconds,
        })


@dataclass
class StudyEvent(Event):
    """Event for multi-simulation study notifications"""

    study_id: str = ""
    study_type: Optional[str] = None  # parametric, fidelity, optimization, etc.
    results_path: Optional[str] = None
    total_simulations: Optional[int] = None
    completed_simulations: Optional[int] = None
    duration_seconds: Optional[float] = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EcoSystemiserEventType.STUDY_STARTED

        # Add study info to payload
        self.payload.update({
            "study_id": self.study_id,
            "study_type": self.study_type,
            "results_path": self.results_path,
            "total_simulations": self.total_simulations,
            "completed_simulations": self.completed_simulations,
            "duration_seconds": self.duration_seconds,
        })


@dataclass
class AnalysisEvent(Event):
    """Event for analysis workflow notifications"""

    analysis_id: str = ""
    source_results_path: Optional[str] = None
    analysis_results_path: Optional[str] = None
    strategies_executed: Optional[List[str]] = None
    duration_seconds: Optional[float] = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EcoSystemiserEventType.ANALYSIS_STARTED

        # Add analysis info to payload
        self.payload.update({
            "analysis_id": self.analysis_id,
            "source_results_path": self.source_results_path,
            "analysis_results_path": self.analysis_results_path,
            "strategies_executed": self.strategies_executed or [],
            "duration_seconds": self.duration_seconds,
        })


@dataclass
class OptimizationEvent(Event):
    """Event for optimization workflow notifications"""

    optimization_id: str = ""
    algorithm_type: Optional[str] = None  # genetic, monte_carlo, etc.
    generation: Optional[int] = None
    best_fitness: Optional[float] = None
    results_path: Optional[str] = None
    duration_seconds: Optional[float] = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EcoSystemiserEventType.OPTIMIZATION_STARTED

        # Add optimization info to payload
        self.payload.update({
            "optimization_id": self.optimization_id,
            "algorithm_type": self.algorithm_type,
            "generation": self.generation,
            "best_fitness": self.best_fitness,
            "results_path": self.results_path,
            "duration_seconds": self.duration_seconds,
        })


# Convenience factory functions for creating EcoSystemiser events

def create_simulation_event(
    event_type: str,
    simulation_id: str,
    source_agent: str,
    system_config_path: Optional[str] = None,
    results_path: Optional[str] = None,
    solver_type: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    correlation_id: Optional[str] = None,
    **extra_payload
) -> SimulationEvent:
    """Create a simulation lifecycle event"""
    return SimulationEvent(
        event_type=event_type,
        simulation_id=simulation_id,
        source_agent=source_agent,
        system_config_path=system_config_path,
        results_path=results_path,
        solver_type=solver_type,
        duration_seconds=duration_seconds,
        correlation_id=correlation_id,
        payload=extra_payload
    )


def create_study_event(
    event_type: str,
    study_id: str,
    source_agent: str,
    study_type: Optional[str] = None,
    results_path: Optional[str] = None,
    total_simulations: Optional[int] = None,
    completed_simulations: Optional[int] = None,
    duration_seconds: Optional[float] = None,
    correlation_id: Optional[str] = None,
    **extra_payload
) -> StudyEvent:
    """Create a study lifecycle event"""
    return StudyEvent(
        event_type=event_type,
        study_id=study_id,
        source_agent=source_agent,
        study_type=study_type,
        results_path=results_path,
        total_simulations=total_simulations,
        completed_simulations=completed_simulations,
        duration_seconds=duration_seconds,
        correlation_id=correlation_id,
        payload=extra_payload
    )


def create_analysis_event(
    event_type: str,
    analysis_id: str,
    source_agent: str,
    source_results_path: Optional[str] = None,
    analysis_results_path: Optional[str] = None,
    strategies_executed: Optional[List[str]] = None,
    duration_seconds: Optional[float] = None,
    correlation_id: Optional[str] = None,
    **extra_payload
) -> AnalysisEvent:
    """Create an analysis lifecycle event"""
    return AnalysisEvent(
        event_type=event_type,
        analysis_id=analysis_id,
        source_agent=source_agent,
        source_results_path=source_results_path,
        analysis_results_path=analysis_results_path,
        strategies_executed=strategies_executed,
        duration_seconds=duration_seconds,
        correlation_id=correlation_id,
        payload=extra_payload
    )


def create_optimization_event(
    event_type: str,
    optimization_id: str,
    source_agent: str,
    algorithm_type: Optional[str] = None,
    generation: Optional[int] = None,
    best_fitness: Optional[float] = None,
    results_path: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    correlation_id: Optional[str] = None,
    **extra_payload
) -> OptimizationEvent:
    """Create an optimization lifecycle event"""
    return OptimizationEvent(
        event_type=event_type,
        optimization_id=optimization_id,
        source_agent=source_agent,
        algorithm_type=algorithm_type,
        generation=generation,
        best_fitness=best_fitness,
        results_path=results_path,
        duration_seconds=duration_seconds,
        correlation_id=correlation_id,
        payload=extra_payload
    )