"""Main simulation service orchestrator."""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import yaml

from ..system_model.system import System
from ..utils.system_builder import SystemBuilder
from ..component_data.repository import ComponentRepository
from ..solver.factory import SolverFactory
from ..solver.base import SolverConfig
from ..profile_loader import get_profile_sync, ClimateRequest
from .results_io import ResultsIO

logger = logging.getLogger(__name__)

class SimulationConfig(BaseModel):
    """Complete configuration for a simulation run."""
    simulation_id: str
    system_config_path: str
    solver_type: str = "rule_based"
    solver_config: Optional[SolverConfig] = None
    climate_input: Optional[Dict[str, Any]] = None
    demand_input: Optional[Dict[str, Any]] = None
    output_config: Dict[str, Any] = Field(default_factory=dict)

class SimulationResult(BaseModel):
    """Result of a simulation run."""
    simulation_id: str
    status: str
    results_path: Optional[Path] = None
    kpis: Optional[Dict[str, float]] = None
    solver_metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class SimulationService:
    """Main service for orchestrating system simulations."""

    def __init__(self, component_repo: Optional[ComponentRepository] = None):
        """Initialize simulation service.

        Args:
            component_repo: Optional component repository, creates default if None
        """
        self.component_repo = component_repo or ComponentRepository()
        self.results_io = ResultsIO()

    def run_simulation(self, config: SimulationConfig) -> SimulationResult:
        """Run a complete simulation from configuration.

        Args:
            config: Simulation configuration

        Returns:
            SimulationResult with status and output paths
        """
        logger.info(f"Starting simulation: {config.simulation_id}")

        try:
            # Load profiles
            profiles = self._load_profiles(config)

            # Build system
            system = self._build_system(config, profiles)

            # Create and run solver
            solver_result = self._run_solver(system, config)

            # Save results
            results_path = self._save_results(system, config, solver_result)

            # Calculate KPIs (basic for now)
            kpis = self._calculate_basic_kpis(system)

            return SimulationResult(
                simulation_id=config.simulation_id,
                status=solver_result.status,
                results_path=results_path,
                kpis=kpis,
                solver_metrics={
                    'solve_time': solver_result.solve_time,
                    'iterations': solver_result.iterations,
                    'objective_value': solver_result.objective_value
                }
            )

        except Exception as e:
            logger.error(f"Simulation failed: {e}")
            return SimulationResult(
                simulation_id=config.simulation_id,
                status="error",
                error=str(e)
            )

    def _load_profiles(self, config: SimulationConfig) -> Dict[str, Any]:
        """Load climate and demand profiles.

        Args:
            config: Simulation configuration

        Returns:
            Dictionary of profile data
        """
        profiles = {}

        # Load climate profiles if configured
        if config.climate_input:
            try:
                climate_request = ClimateRequest(**config.climate_input)
                climate_response = get_profile_sync(climate_request)
                profiles.update(climate_response.data)
                logger.info("Loaded climate profiles")
            except Exception as e:
                logger.warning(f"Could not load climate profiles: {e}")

        # Load demand profiles if configured
        if config.demand_input:
            try:
                from ..profile_loader.demand.file_adapter import DemandFileAdapter
                adapter = DemandFileAdapter()
                demand_profiles = adapter.fetch(config.demand_input)
                profiles.update(demand_profiles)
                logger.info(f"Loaded {len(demand_profiles)} demand profiles")
            except Exception as e:
                logger.warning(f"Could not load demand profiles: {e}")

        return profiles

    def _build_system(self, config: SimulationConfig, profiles: Dict[str, Any]) -> System:
        """Build system from configuration.

        Args:
            config: Simulation configuration
            profiles: Loaded profiles

        Returns:
            Configured System object
        """
        # Create system builder
        builder = SystemBuilder(
            Path(config.system_config_path),
            self.component_repo
        )

        # Build system
        system = builder.build()

        # Assign profiles to components
        builder.assign_profiles(system, profiles)

        logger.info(f"Built system with {len(system.components)} components")
        return system

    def _run_solver(self, system: System, config: SimulationConfig):
        """Run the configured solver on the system.

        Args:
            system: System to solve
            config: Simulation configuration

        Returns:
            SolverResult
        """
        # Get solver from factory
        solver = SolverFactory.get_solver(
            config.solver_type,
            system,
            config.solver_config
        )

        # Run solver
        logger.info(f"Running {config.solver_type} solver")
        result = solver.solve()

        logger.info(f"Solver completed with status: {result.status}")
        return result

    def _save_results(self, system: System, config: SimulationConfig,
                     solver_result) -> Path:
        """Save simulation results.

        Args:
            system: Solved system
            config: Simulation configuration
            solver_result: Result from solver

        Returns:
            Path to saved results
        """
        # Configure output
        output_config = config.output_config
        output_dir = Path(output_config.get('directory', 'outputs'))
        output_format = output_config.get('format', 'json')

        # Save results
        results_path = self.results_io.save_results(
            system,
            config.simulation_id,
            output_dir,
            output_format,
            metadata={
                'solver_type': config.solver_type,
                'solver_status': solver_result.status,
                'solve_time': solver_result.solve_time
            }
        )

        logger.info(f"Results saved to: {results_path}")
        return results_path

    def _calculate_basic_kpis(self, system: System) -> Dict[str, float]:
        """Calculate basic KPIs from solved system.

        Args:
            system: Solved system

        Returns:
            Dictionary of KPIs
        """
        import numpy as np

        kpis = {}

        # Calculate total energy from grid
        for comp in system.components.values():
            if comp.type == "transmission" and comp.medium == "electricity":
                if 'P_draw' in comp.flows.get('source', {}):
                    flow = comp.flows['source']['P_draw']['value']
                    if isinstance(flow, np.ndarray):
                        kpis['total_grid_import_kwh'] = float(np.sum(flow))

                if 'P_feed' in comp.flows.get('sink', {}):
                    flow = comp.flows['sink']['P_feed']['value']
                    if isinstance(flow, np.ndarray):
                        kpis['total_grid_export_kwh'] = float(np.sum(flow))

        # Calculate renewable generation
        total_renewable = 0
        for comp in system.components.values():
            if comp.type == "generation" and hasattr(comp, 'profile'):
                total_renewable += np.sum(comp.profile)
        kpis['total_renewable_kwh'] = float(total_renewable)

        # Calculate self-consumption rate
        if 'total_grid_export_kwh' in kpis and total_renewable > 0:
            self_consumed = total_renewable - kpis['total_grid_export_kwh']
            kpis['self_consumption_rate'] = float(self_consumed / total_renewable)

        return kpis

    def run_from_yaml(self, yaml_path: str) -> SimulationResult:
        """Run simulation from YAML configuration file.

        Args:
            yaml_path: Path to YAML configuration file

        Returns:
            SimulationResult
        """
        with open(yaml_path, 'r') as f:
            config_dict = yaml.safe_load(f)

        config = SimulationConfig(**config_dict)
        return self.run_simulation(config)