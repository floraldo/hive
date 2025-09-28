"""Main simulation service orchestrator."""
from ecosystemiser.hive_logging_adapter import get_logger
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import yaml
from typing import List

from ecosystemiser.system_model.system import System
from ecosystemiser.utils.system_builder import SystemBuilder
from ecosystemiser.component_data.repository import ComponentRepository
from ecosystemiser.solver.factory import SolverFactory
from ecosystemiser.solver.base import SolverConfig
from ecosystemiser.profile_loader import get_profile_sync, ClimateRequest
from ecosystemiser.results_io import ResultsIO

logger = get_logger(__name__)

class StageConfig(BaseModel):
    """Configuration for a single stage in staged simulation."""
    stage_name: str
    system_config_path: str
    solver_type: str = "milp"
    outputs_to_pass: Optional[List[Dict[str, Any]]] = None
    inputs_from_stage: Optional[List[Dict[str, Any]]] = None

class SimulationConfig(BaseModel):
    """Complete configuration for a simulation run."""
    simulation_id: str
    system_config_path: Optional[str] = None  # Optional for staged simulations
    solver_type: str = "rule_based"
    solver_config: Optional[SolverConfig] = None
    climate_input: Optional[Dict[str, Any]] = None
    demand_input: Optional[Dict[str, Any]] = None
    output_config: Dict[str, Any] = Field(default_factory=dict)
    # Support for staged simulations
    stages: Optional[List[StageConfig]] = None

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

        Supports both single-run and staged simulations for multi-domain problems.

        Args:
            config: Simulation configuration

        Returns:
            SimulationResult with status and output paths
        """
        logger.info(f"Starting simulation: {config.simulation_id}")

        # Check if this is a staged simulation
        if config.stages:
            return self._run_staged_simulation(config)

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

    def _run_staged_simulation(self, config: SimulationConfig) -> SimulationResult:
        """Run a multi-stage simulation for domain decomposition.

        This enables solving complex multi-domain problems (e.g., thermal→electrical)
        by solving them in stages and passing intermediate results between stages.

        Args:
            config: Simulation configuration with stages

        Returns:
            SimulationResult with aggregated results
        """
        logger.info(f"Starting staged simulation with {len(config.stages)} stages")

        intermediate_profiles = {}  # Store outputs between stages
        stage_results = []
        aggregated_kpis = {}

        try:
            # Load base profiles once
            base_profiles = self._load_profiles(config)

            # Execute each stage sequentially
            for stage_idx, stage in enumerate(config.stages):
                logger.info(f"Executing stage {stage_idx + 1}/{len(config.stages)}: {stage.stage_name}")

                # Prepare profiles for this stage
                stage_profiles = base_profiles.copy()

                # Add inputs from previous stages
                if stage.inputs_from_stage:
                    for input_spec in stage.inputs_from_stage:
                        from_stage = input_spec.get('from_stage')
                        profile_name = input_spec.get('profile_name')

                        if profile_name in intermediate_profiles:
                            # Assign to the component or as a general profile
                            assign_to = input_spec.get('assign_to_component')
                            if assign_to:
                                stage_profiles[f"{assign_to}_additional_demand"] = intermediate_profiles[profile_name]
                            else:
                                stage_profiles[profile_name] = intermediate_profiles[profile_name]

                            logger.info(f"Passed profile '{profile_name}' from {from_stage} to {stage.stage_name}")

                # Build and solve this stage's system
                stage_config = SimulationConfig(
                    simulation_id=f"{config.simulation_id}_{stage.stage_name}",
                    system_config_path=stage.system_config_path,
                    solver_type=stage.solver_type,
                    solver_config=config.solver_config,  # Use global solver config
                    output_config=config.output_config
                )

                # Build system for this stage
                stage_system = self._build_system(stage_config, stage_profiles)

                # Run solver for this stage
                stage_solver_result = self._run_solver(stage_system, stage_config)

                # Extract outputs to pass to next stage
                if stage.outputs_to_pass:
                    for output_spec in stage.outputs_to_pass:
                        component_name = output_spec.get('component')
                        attribute = output_spec.get('attribute')
                        as_profile_name = output_spec.get('as_profile_name')

                        # Extract the specified output from the component
                        if component_name in stage_system.components:
                            comp = stage_system.components[component_name]

                            # Try to extract the attribute
                            if hasattr(comp, attribute):
                                profile_data = getattr(comp, attribute)
                            elif 'flows' in dir(comp) and attribute in comp.flows.get('sink', {}):
                                profile_data = comp.flows['sink'][attribute]['value']
                            elif 'flows' in dir(comp) and attribute in comp.flows.get('source', {}):
                                profile_data = comp.flows['source'][attribute]['value']
                            else:
                                logger.warning(f"Could not find attribute '{attribute}' in component '{component_name}'")
                                continue

                            intermediate_profiles[as_profile_name] = profile_data
                            logger.info(f"Extracted '{attribute}' from '{component_name}' as '{as_profile_name}'")

                # Calculate stage KPIs
                stage_kpis = self._calculate_basic_kpis(stage_system)
                for key, value in stage_kpis.items():
                    aggregated_kpis[f"{stage.stage_name}_{key}"] = value

                # Store stage results
                stage_results.append({
                    'stage_name': stage.stage_name,
                    'status': stage_solver_result.status,
                    'solve_time': stage_solver_result.solve_time
                })

                # Save stage results
                self._save_results(stage_system, stage_config, stage_solver_result)

            # Aggregate final results
            total_solve_time = sum(r['solve_time'] for r in stage_results if r.get('solve_time'))
            all_success = all(r['status'] == 'optimal' for r in stage_results)

            return SimulationResult(
                simulation_id=config.simulation_id,
                status='optimal' if all_success else 'feasible',
                results_path=Path(config.output_config.get('directory', 'outputs')),
                kpis=aggregated_kpis,
                solver_metrics={
                    'solve_time': total_solve_time,
                    'stages': stage_results,
                    'iterations': len(config.stages)
                }
            )

        except Exception as e:
            logger.error(f"Staged simulation failed: {e}")
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
                from ecosystemiser.profile_loader.demand.file_adapter import DemandFileAdapter
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