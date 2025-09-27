"""Multi-simulation orchestration service for parametric studies and optimization workflows."""
from EcoSystemiser.hive_logging_adapter import get_logger
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

logger = get_logger(__name__)

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
    mixed_fidelity_configs: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Pre-defined mixed fidelity configurations as {component: fidelity_level}"
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

        This method now supports true mixed-fidelity studies where different
        components can have different fidelity levels within the same simulation.

        Args:
            config: Study configuration

        Returns:
            List of simulation configurations with mixed-fidelity settings
        """
        configs = []

        if not config.fidelity_sweep:
            return [config.base_config]

        # Check if we have pre-defined mixed fidelity configurations
        if config.fidelity_sweep.mixed_fidelity_configs:
            # Use pre-defined mixed fidelity configurations
            for mix_idx, mixed_config in enumerate(config.fidelity_sweep.mixed_fidelity_configs):
                sim_config = config.base_config.model_copy(deep=True)
                sim_config.simulation_id = f"{config.study_id}_mixed_fidelity_{mix_idx}"

                # Store the mixed fidelity configuration
                sim_config.output_config["mixed_fidelity_config"] = mixed_config
                sim_config.output_config["config_index"] = mix_idx

                # Create component-specific fidelity overrides
                component_fidelity_overrides = {}
                for component_name, fidelity_level in mixed_config.items():
                    component_fidelity_overrides[component_name] = {
                        "fidelity_level": fidelity_level
                    }

                sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                configs.append(sim_config)

        else:
            # Generate mixed fidelity configurations automatically
            target_components = config.fidelity_sweep.component_names
            fidelity_levels = config.fidelity_sweep.fidelity_levels

            if not target_components:
                logger.warning("No components specified for fidelity sweep, using uniform fidelity")
                # Fall back to uniform fidelity for each level
                for fidelity_idx, fidelity in enumerate(fidelity_levels):
                    sim_config = config.base_config.model_copy(deep=True)
                    sim_config.simulation_id = f"{config.study_id}_uniform_fidelity_{fidelity}"

                    sim_config.output_config["uniform_fidelity_level"] = fidelity
                    sim_config.output_config["fidelity_index"] = fidelity_idx
                    configs.append(sim_config)
            else:
                # Generate all combinations of fidelity levels for specified components
                if len(target_components) == 1:
                    # Single component sweep - test each fidelity level
                    component = target_components[0]
                    for fidelity_idx, fidelity in enumerate(fidelity_levels):
                        sim_config = config.base_config.model_copy(deep=True)
                        sim_config.simulation_id = f"{config.study_id}_{component}_fidelity_{fidelity}"

                        mixed_config = {component: fidelity}
                        sim_config.output_config["mixed_fidelity_config"] = mixed_config
                        sim_config.output_config["fidelity_index"] = fidelity_idx

                        component_fidelity_overrides = {
                            component: {"fidelity_level": fidelity}
                        }
                        sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                        configs.append(sim_config)

                elif len(target_components) <= 4:  # Reasonable limit for full combinatorics
                    # Multiple components - generate key combinations
                    # 1. All at lowest fidelity
                    lowest_fidelity = fidelity_levels[0]
                    sim_config = config.base_config.model_copy(deep=True)
                    sim_config.simulation_id = f"{config.study_id}_all_{lowest_fidelity}"

                    mixed_config = {comp: lowest_fidelity for comp in target_components}
                    sim_config.output_config["mixed_fidelity_config"] = mixed_config
                    component_fidelity_overrides = {
                        comp: {"fidelity_level": lowest_fidelity} for comp in target_components
                    }
                    sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                    configs.append(sim_config)

                    # 2. All at highest fidelity
                    if len(fidelity_levels) > 1:
                        highest_fidelity = fidelity_levels[-1]
                        sim_config = config.base_config.model_copy(deep=True)
                        sim_config.simulation_id = f"{config.study_id}_all_{highest_fidelity}"

                        mixed_config = {comp: highest_fidelity for comp in target_components}
                        sim_config.output_config["mixed_fidelity_config"] = mixed_config
                        component_fidelity_overrides = {
                            comp: {"fidelity_level": highest_fidelity} for comp in target_components
                        }
                        sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                        configs.append(sim_config)

                    # 3. Mixed configurations - one component at high fidelity, others at low
                    if len(fidelity_levels) > 1 and len(target_components) > 1:
                        for focus_component in target_components:
                            sim_config = config.base_config.model_copy(deep=True)
                            sim_config.simulation_id = f"{config.study_id}_{focus_component}_high_others_low"

                            mixed_config = {}
                            for comp in target_components:
                                mixed_config[comp] = highest_fidelity if comp == focus_component else lowest_fidelity

                            sim_config.output_config["mixed_fidelity_config"] = mixed_config
                            component_fidelity_overrides = {
                                comp: {"fidelity_level": fidelity} for comp, fidelity in mixed_config.items()
                            }
                            sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                            configs.append(sim_config)

                else:
                    # Too many components for full exploration - use sampling
                    logger.info(f"Too many components ({len(target_components)}) for full fidelity exploration, using sampling")

                    # Sample representative configurations
                    import random
                    random.seed(42)  # Reproducible sampling

                    for sample_idx in range(min(10, len(fidelity_levels) * 3)):  # Max 10 samples
                        sim_config = config.base_config.model_copy(deep=True)
                        sim_config.simulation_id = f"{config.study_id}_sample_{sample_idx}"

                        # Randomly assign fidelity levels
                        mixed_config = {}
                        for comp in target_components:
                            mixed_config[comp] = random.choice(fidelity_levels)

                        sim_config.output_config["mixed_fidelity_config"] = mixed_config
                        sim_config.output_config["sample_index"] = sample_idx
                        component_fidelity_overrides = {
                            comp: {"fidelity_level": fidelity} for comp, fidelity in mixed_config.items()
                        }
                        sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                        configs.append(sim_config)

        logger.info(f"Generated {len(configs)} mixed-fidelity configurations")
        for i, cfg in enumerate(configs):
            mixed_config = cfg.output_config.get("mixed_fidelity_config", {})
            logger.debug(f"Config {i}: {mixed_config}")

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
                # For mixed-fidelity studies, find the configuration with the best trade-off
                # between accuracy and computational cost
                if successful:
                    # Score each result based on accuracy and efficiency
                    scored_results = []
                    for result in successful:
                        # Get solve time and objective value
                        solve_time = result.solver_metrics.get("solve_time", float('inf')) if result.solver_metrics else float('inf')
                        objective_value = result.solver_metrics.get("objective_value", float('inf')) if result.solver_metrics else float('inf')

                        # Calculate efficiency score (lower is better)
                        efficiency_score = solve_time / max(objective_value, 1e-6)  # Avoid division by zero

                        scored_results.append((result, efficiency_score))

                    # Sort by efficiency score (best trade-off)
                    scored_results.sort(key=lambda x: x[1])
                    best_result = scored_results[0][0]  # Best efficiency
                else:
                    best_result = None

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
                               components: Optional[List[str]] = None,
                               mixed_fidelity_configs: Optional[List[Dict[str, str]]] = None) -> StudyResult:
        """Convenience method to run a fidelity comparison study.

        Args:
            base_config_path: Path to base system configuration
            components: Optional list of components to vary fidelity
            mixed_fidelity_configs: Optional pre-defined mixed fidelity configurations

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

        # Create study config with mixed-fidelity support
        study_config = StudyConfig(
            study_id=f"fidelity_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            study_type="fidelity",
            base_config=base_sim_config,
            fidelity_sweep=FidelitySweepSpec(
                component_names=components or [],
                fidelity_levels=["SIMPLE", "STANDARD", "DETAILED"],
                mixed_fidelity_configs=mixed_fidelity_configs
            ),
            parallel_execution=True,
            save_all_results=True
        )

        return self.run_study(study_config)

    def run_mixed_fidelity_study(self, base_config_path: Path,
                                 mixed_configs: List[Dict[str, str]]) -> StudyResult:
        """Convenience method to run a mixed-fidelity study with specific configurations.

        Args:
            base_config_path: Path to base system configuration
            mixed_configs: List of mixed fidelity configurations
                          Example: [{"battery": "RESEARCH", "solar_pv": "STANDARD"}]

        Returns:
            StudyResult with mixed-fidelity comparison
        """
        return self.run_fidelity_comparison(
            base_config_path=base_config_path,
            mixed_fidelity_configs=mixed_configs
        )

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