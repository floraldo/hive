"""Multi-simulation orchestration service for parametric studies and optimization workflows."""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
import json
import yaml
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import itertools

from .simulation_service import SimulationService, SimulationConfig, SimulationResult
from ..system_model.components.shared.archetypes import FidelityLevel

logger = logging.getLogger(__name__)


class ParameterSweepSpec(BaseModel):
    """Specification for a parameter sweep."""
    component_name: str
    parameter_path: str  # dot notation e.g., "technical.capacity_nominal"
    values: List[Union[float, int, str]]


class FidelitySweepSpec(BaseModel):
    """Specification for fidelity level sweep."""
    component_names: List[str] = Field(
        default_factory=list,
        description="Components to sweep, empty means all"
    )
    fidelity_levels: List[str] = Field(
        default_factory=lambda: ["SIMPLE", "STANDARD"],
        description="Fidelity levels to test"
    )


class StudyConfig(BaseModel):
    """Configuration for a multi-simulation study."""
    study_id: str
    study_type: str = "parametric"  # parametric, fidelity, optimization, monte_carlo
    base_config: SimulationConfig

    # For parametric studies
    parameter_sweeps: Optional[List[ParameterSweepSpec]] = None

    # For fidelity studies
    fidelity_sweep: Optional[FidelitySweepSpec] = None

    # For optimization studies
    optimization_objective: Optional[str] = None  # e.g., "minimize_cost", "maximize_renewable"
    optimization_constraints: Optional[List[Dict[str, Any]]] = None

    # Execution settings
    parallel_execution: bool = True
    max_workers: int = 4
    save_all_results: bool = False
    output_directory: Path = Field(default_factory=lambda: Path("studies"))


class StudyResult(BaseModel):
    """Result of a multi-simulation study."""
    study_id: str
    study_type: str
    num_simulations: int
    successful_simulations: int
    failed_simulations: int
    best_result: Optional[Dict[str, Any]] = None
    all_results: Optional[List[Dict[str, Any]]] = None
    summary_statistics: Optional[Dict[str, Any]] = None
    execution_time: float


class StudyService:
    """Service for orchestrating multi-simulation studies."""

    def __init__(self, simulation_service: Optional[SimulationService] = None):
        """Initialize study service.

        Args:
            simulation_service: Optional simulation service, creates default if None
        """
        self.simulation_service = simulation_service or SimulationService()

    def run_study(self, config: StudyConfig) -> StudyResult:
        """Run a complete study based on configuration.

        Args:
            config: Study configuration

        Returns:
            StudyResult with aggregated results
        """
        logger.info(f"Starting {config.study_type} study: {config.study_id}")

        start_time = datetime.now()

        # Generate simulation configurations based on study type
        if config.study_type == "parametric":
            simulation_configs = self._generate_parametric_configs(config)
        elif config.study_type == "fidelity":
            simulation_configs = self._generate_fidelity_configs(config)
        elif config.study_type == "optimization":
            return self._run_optimization_study(config)
        elif config.study_type == "monte_carlo":
            simulation_configs = self._generate_monte_carlo_configs(config)
        else:
            raise ValueError(f"Unknown study type: {config.study_type}")

        # Run simulations
        results = self._run_simulations(simulation_configs, config)

        # Process results
        study_result = self._process_results(results, config)

        # Add execution time
        study_result.execution_time = (datetime.now() - start_time).total_seconds()

        logger.info(f"Study completed: {study_result.successful_simulations}/{study_result.num_simulations} successful")

        return study_result

    def _generate_parametric_configs(self, config: StudyConfig) -> List[SimulationConfig]:
        """Generate simulation configurations for parametric sweep.

        Args:
            config: Study configuration

        Returns:
            List of simulation configurations
        """
        configs = []

        # Generate all combinations of parameter values
        if not config.parameter_sweeps:
            return [config.base_config]

        # Extract parameter values for each sweep
        param_values = []
        param_specs = []
        for sweep in config.parameter_sweeps:
            param_values.append(sweep.values)
            param_specs.append(sweep)

        # Generate all combinations
        for combo_idx, combo in enumerate(itertools.product(*param_values)):
            # Create a copy of base config
            sim_config = config.base_config.model_copy(deep=True)
            sim_config.simulation_id = f"{config.study_id}_param_{combo_idx}"

            # Create metadata for this combination
            param_settings = {}
            for spec, value in zip(param_specs, combo):
                param_settings[f"{spec.component_name}.{spec.parameter_path}"] = value

            # Store parameter settings in output config for tracking
            sim_config.output_config["parameter_settings"] = param_settings
            sim_config.output_config["combo_index"] = combo_idx

            configs.append(sim_config)

        logger.info(f"Generated {len(configs)} parametric configurations")
        return configs

    def _generate_fidelity_configs(self, config: StudyConfig) -> List[SimulationConfig]:
        """Generate simulation configurations for fidelity sweep.

        Args:
            config: Study configuration

        Returns:
            List of simulation configurations
        """
        configs = []

        if not config.fidelity_sweep:
            return [config.base_config]

        # For each fidelity level, create a configuration
        for fidelity_idx, fidelity in enumerate(config.fidelity_sweep.fidelity_levels):
            # Create a copy of base config
            sim_config = config.base_config.model_copy(deep=True)
            sim_config.simulation_id = f"{config.study_id}_fidelity_{fidelity}"

            # Store fidelity settings
            sim_config.output_config["fidelity_level"] = fidelity
            sim_config.output_config["fidelity_index"] = fidelity_idx

            # If specific components specified, store them
            if config.fidelity_sweep.component_names:
                sim_config.output_config["fidelity_components"] = config.fidelity_sweep.component_names

            configs.append(sim_config)

        logger.info(f"Generated {len(configs)} fidelity configurations")
        return configs

    def _generate_monte_carlo_configs(self, config: StudyConfig) -> List[SimulationConfig]:
        """Generate simulation configurations for Monte Carlo analysis.

        Args:
            config: Study configuration

        Returns:
            List of simulation configurations
        """
        # This would generate configs with stochastic variations
        # For now, return base config
        logger.warning("Monte Carlo studies not yet fully implemented")
        return [config.base_config]

    def _run_optimization_study(self, config: StudyConfig) -> StudyResult:
        """Run an optimization study using iterative simulation.

        Args:
            config: Study configuration

        Returns:
            StudyResult with optimization results
        """
        # This would implement optimization algorithms
        # For now, return empty result
        logger.warning("Optimization studies not yet fully implemented")

        return StudyResult(
            study_id=config.study_id,
            study_type="optimization",
            num_simulations=0,
            successful_simulations=0,
            failed_simulations=0,
            execution_time=0.0
        )

    def _run_simulations(self, configs: List[SimulationConfig],
                        study_config: StudyConfig) -> List[SimulationResult]:
        """Run multiple simulations, potentially in parallel.

        Args:
            configs: List of simulation configurations
            study_config: Study configuration

        Returns:
            List of simulation results
        """
        results = []

        if study_config.parallel_execution and len(configs) > 1:
            # Run simulations in parallel
            logger.info(f"Running {len(configs)} simulations in parallel with {study_config.max_workers} workers")

            with ProcessPoolExecutor(max_workers=study_config.max_workers) as executor:
                # Submit all simulations
                future_to_config = {
                    executor.submit(self._run_single_simulation, cfg): cfg
                    for cfg in configs
                }

                # Collect results as they complete
                for future in as_completed(future_to_config):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Simulation failed: {e}")
                        # Create a failed result
                        cfg = future_to_config[future]
                        results.append(SimulationResult(
                            simulation_id=cfg.simulation_id,
                            status="error",
                            error=str(e)
                        ))
        else:
            # Run simulations sequentially
            logger.info(f"Running {len(configs)} simulations sequentially")

            for cfg in configs:
                try:
                    result = self._run_single_simulation(cfg)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Simulation {cfg.simulation_id} failed: {e}")
                    results.append(SimulationResult(
                        simulation_id=cfg.simulation_id,
                        status="error",
                        error=str(e)
                    ))

        return results

    def _run_single_simulation(self, config: SimulationConfig) -> SimulationResult:
        """Run a single simulation.

        Args:
            config: Simulation configuration

        Returns:
            SimulationResult
        """
        # This is called potentially in a separate process
        # Create a new simulation service instance to avoid sharing state
        sim_service = SimulationService()
        return sim_service.run_simulation(config)

    def _process_results(self, results: List[SimulationResult],
                        config: StudyConfig) -> StudyResult:
        """Process and aggregate simulation results.

        Args:
            results: List of simulation results
            config: Study configuration

        Returns:
            Aggregated study result
        """
        successful = [r for r in results if r.status in ["optimal", "feasible"]]
        failed = [r for r in results if r.status == "error"]

        # Find best result based on study type
        best_result = None
        if successful:
            if config.study_type == "parametric":
                # Find result with best objective value
                results_with_metrics = [r for r in successful if r.solver_metrics is not None]
                if results_with_metrics:
                    best_result = min(results_with_metrics,
                                    key=lambda r: r.solver_metrics.get("objective_value", float('inf')))
                else:
                    best_result = successful[0]  # Fallback to first result
            elif config.study_type == "fidelity":
                # Compare fidelity levels
                best_result = successful[-1]  # Highest fidelity tested

        # Calculate summary statistics
        summary_stats = self._calculate_summary_statistics(successful, config)

        # Prepare all results if requested
        all_results = None
        if config.save_all_results:
            all_results = [r.model_dump() for r in results]

        return StudyResult(
            study_id=config.study_id,
            study_type=config.study_type,
            num_simulations=len(results),
            successful_simulations=len(successful),
            failed_simulations=len(failed),
            best_result=best_result.model_dump() if best_result else None,
            all_results=all_results,
            summary_statistics=summary_stats,
            execution_time=0.0  # Will be set by caller
        )

    def _calculate_summary_statistics(self, results: List[SimulationResult],
                                     config: StudyConfig) -> Dict[str, Any]:
        """Calculate summary statistics from successful results.

        Args:
            results: List of successful simulation results
            config: Study configuration

        Returns:
            Dictionary of summary statistics
        """
        if not results:
            return {}

        stats = {}

        # Collect all KPIs
        kpi_values = {}
        for result in results:
            if result.kpis:
                for key, value in result.kpis.items():
                    if key not in kpi_values:
                        kpi_values[key] = []
                    kpi_values[key].append(value)

        # Calculate statistics for each KPI
        for kpi, values in kpi_values.items():
            if values:
                stats[f"{kpi}_mean"] = float(np.mean(values))
                stats[f"{kpi}_std"] = float(np.std(values))
                stats[f"{kpi}_min"] = float(np.min(values))
                stats[f"{kpi}_max"] = float(np.max(values))

        # Add solve time statistics
        solve_times = [r.solver_metrics.get("solve_time", 0) for r in results
                      if r.solver_metrics]
        if solve_times:
            stats["solve_time_mean"] = float(np.mean(solve_times))
            stats["solve_time_total"] = float(np.sum(solve_times))

        return stats

    def run_fidelity_comparison(self, base_config_path: Path,
                               components: Optional[List[str]] = None) -> StudyResult:
        """Convenience method to run a fidelity comparison study.

        Args:
            base_config_path: Path to base system configuration
            components: Optional list of components to vary fidelity

        Returns:
            StudyResult with fidelity comparison
        """
        # Load base configuration
        with open(base_config_path, 'r') as f:
            system_config = yaml.safe_load(f)

        # Create base simulation config
        base_sim_config = SimulationConfig(
            simulation_id="fidelity_base",
            system_config_path=str(base_config_path),
            solver_type="milp",
            output_config={"directory": "fidelity_study"}
        )

        # Create study config
        study_config = StudyConfig(
            study_id=f"fidelity_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            study_type="fidelity",
            base_config=base_sim_config,
            fidelity_sweep=FidelitySweepSpec(
                component_names=components or [],
                fidelity_levels=["SIMPLE", "STANDARD", "DETAILED"]
            ),
            parallel_execution=True,
            save_all_results=True
        )

        return self.run_study(study_config)

    def run_parameter_sensitivity(self, base_config_path: Path,
                                 parameter_specs: List[Dict[str, Any]]) -> StudyResult:
        """Convenience method to run a parameter sensitivity study.

        Args:
            base_config_path: Path to base system configuration
            parameter_specs: List of parameter specifications

        Returns:
            StudyResult with sensitivity analysis
        """
        # Create base simulation config
        base_sim_config = SimulationConfig(
            simulation_id="sensitivity_base",
            system_config_path=str(base_config_path),
            solver_type="milp",
            output_config={"directory": "sensitivity_study"}
        )

        # Convert parameter specs
        sweeps = []
        for spec in parameter_specs:
            sweeps.append(ParameterSweepSpec(**spec))

        # Create study config
        study_config = StudyConfig(
            study_id=f"sensitivity_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            study_type="parametric",
            base_config=base_sim_config,
            parameter_sweeps=sweeps,
            parallel_execution=True,
            save_all_results=True
        )

        return self.run_study(study_config)