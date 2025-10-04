"""Multi-simulation orchestration service for parametric studies and optimization workflows."""

import itertools
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from pydantic import BaseModel, Field

# EcoSystemiser Event Bus integration
from ecosystemiser.core.bus import get_ecosystemiser_event_bus
from ecosystemiser.core.events import StudyEvent
from ecosystemiser.discovery.algorithms.genetic_algorithm import (
    GeneticAlgorithm,
    GeneticAlgorithmConfig,
    NSGAIIOptimizer,
)
from ecosystemiser.discovery.algorithms.monte_carlo import MonteCarloConfig, MonteCarloEngine, UncertaintyAnalyzer
from ecosystemiser.discovery.encoders.constraint_handler import ConstraintHandler, TechnicalConstraintValidator
from ecosystemiser.discovery.encoders.parameter_encoder import SystemConfigEncoder
from ecosystemiser.services.database_metadata_service import DatabaseMetadataService
from ecosystemiser.services.job_facade import JobFacade

# Import only types from simulation_service to avoid direct coupling
from ecosystemiser.services.simulation_service import SimulationConfig, SimulationResult
from hive_logging import get_logger

logger = get_logger(__name__)


class ParameterSweepSpec(BaseModel):
    """Specification for a parameter sweep."""

    component_name: str
    parameter_path: str  # dot notation e.g., "technical.capacity_nominal"
    values: list[float | int | str]


class FidelitySweepSpec(BaseModel):
    """Specification for fidelity level sweep."""

    component_names: list[str] = Field(default_factory=list, description="Components to sweep, empty means all")
    fidelity_levels: list[str] = Field(
        default_factory=lambda: ["SIMPLE", "STANDARD"],
        description="Fidelity levels to test",
    )
    mixed_fidelity_configs: list[dict[str, str]] | None = Field(
        default=None,
        description="Pre-defined mixed fidelity configurations as {component: fidelity_level}",
    )


class StudyConfig(BaseModel):
    """Configuration for a multi-simulation study."""

    study_id: str
    study_type: str = "parametric"  # parametric, fidelity, optimization, monte_carlo, genetic_algorithm
    base_config: SimulationConfig

    # For parametric studies
    parameter_sweeps: list[ParameterSweepSpec] | None = None

    # For fidelity studies
    fidelity_sweep: FidelitySweepSpec | None = None

    # For optimization studies
    optimization_objective: str | None = None  # e.g., "minimize_cost", "maximize_renewable"
    optimization_constraints: list[dict[str, Any]] | None = None
    optimization_variables: list[dict[str, Any]] | None = None  # Parameter definitions for optimization

    # For genetic algorithm studies
    ga_config: dict[str, Any] | None = None  # GA-specific parameters
    multi_objective: bool = False  # Use NSGA-II for multi-objective optimization

    # For Monte Carlo studies
    mc_config: dict[str, Any] | None = None  # MC-specific parameters
    uncertainty_variables: dict[str, dict[str, Any]] | None = None

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
    best_result: dict[str, Any] | None = None
    all_results: list[dict[str, Any]] | None = None
    summary_statistics: dict[str, Any] | None = None
    execution_time: float


class StudyService:
    """Service for orchestrating multi-simulation studies."""

    def __init__(self, job_facade: JobFacade | None = None) -> None:
        """Initialize study service.

        Args:
            job_facade: Optional job facade, creates default if None:

        """
        self.job_facade = job_facade or JobFacade()
        self.event_bus = get_ecosystemiser_event_bus()
        self.database_service = DatabaseMetadataService()

    def run_study(self, config: StudyConfig) -> StudyResult:
        """Run a complete study based on configuration.

        Args:
            config: Study configuration

        Returns:
            StudyResult with aggregated results,

        """
        logger.info(f"Starting {config.study_type} study: {config.study_id}")
        start_time = datetime.now()

        # Publish study started event
        event_bus = get_ecosystemiser_event_bus(),
        study_started_event = StudyEvent.started(
            study_id=config.study_id,
            config={
                "study_type": config.study_type,
                "results_path": str(config.output_dir) if config.output_dir else None,
            },
            source_agent="StudyService",
        )
        try:
            event_bus.publish(study_started_event)
        except Exception as e:
            logger.debug(f"Could not publish study started event: {e}")

        try:
            # Generate simulation configurations based on study type

            if config.study_type == "parametric":
                simulation_configs = self._generate_parametric_configs(config)
            elif config.study_type == "fidelity":
                simulation_configs = self._generate_fidelity_configs(config)
            elif config.study_type == "optimization":
                return self._run_optimization_study(config)
            elif config.study_type == "genetic_algorithm":
                return self._run_genetic_algorithm_study(config)
            elif config.study_type == "monte_carlo":
                return self._run_monte_carlo_study(config)
            else:
                raise ValueError(f"Unknown study type: {config.study_type}")

            # Run simulations
            results = self._run_simulations(simulation_configs, config)

            # Process results
            study_result = self._process_results(results, config)

            # Add execution time

            study_result.execution_time = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"Study completed: {study_result.successful_simulations}/{study_result.num_simulations} successful",
            )

            # Publish study completed event
            study_completed_event = StudyEvent.completed(
                study_id=config.study_id,
                results={
                    "study_type": config.study_type,
                    "results_path": (str(config.output_dir) if config.output_dir else None),
                    "total_simulations": study_result.num_simulations,
                    "completed_simulations": study_result.successful_simulations,
                },
                duration_seconds=study_result.execution_time,
                source_agent="StudyService",
            )
            try:
                event_bus.publish(study_completed_event)
            except Exception as e:
                logger.debug(f"Could not publish study completed event: {e}")

            return study_result

        except Exception as e:
            # Publish study failed event
            execution_time = (datetime.now() - start_time).total_seconds(),
            study_failed_event = StudyEvent.failed(
                study_id=config.study_id,
                error_message=str(e),
                error_details={
                    "study_type": config.study_type,
                    "results_path": (str(config.output_dir) if config.output_dir else None),
                    "duration_seconds": execution_time,
                },
                source_agent="StudyService",
            )
            try:
                event_bus.publish(study_failed_event)
            except Exception as e_pub:
                logger.debug(f"Could not publish study failed event: {e_pub}")

            logger.error(f"Study failed: {config.study_id} - {e!s}")
            raise

    def run_genetic_algorithm_study(
        self,
        study_id: str,
        ga_config: GeneticAlgorithmConfig,
        fitness_function: Callable,
        log_to_database: bool = True,
    ) -> dict[str, Any]:
        """Run a genetic algorithm optimization study with database logging.

        Args:
            study_id: Unique identifier for the study
            ga_config: Genetic algorithm configuration
            fitness_function: Fitness evaluation function
            log_to_database: Whether to log to database (default True)

        Returns:
            Dictionary with results including best solution, convergence history

        """
        logger.info(f"Starting GA study: {study_id}")

        # Initialize database study record if logging enabled
        if log_to_database:
            try:
                self.database_service.create_study(
                    study_id=study_id,
                    study_type="genetic_algorithm",
                    study_name=study_id,
                    optimization_objective=",".join(ga_config.objectives),
                    population_size=ga_config.population_size,
                    max_generations=ga_config.max_generations,
                    config=ga_config.__dict__,
                )
                logger.info(f"Created database study record: {study_id}")
            except Exception as e:
                logger.warning(f"Could not create study record: {e}")
                log_to_database = False

        # Run GA optimization
        ga = GeneticAlgorithm(ga_config),
        population = ga.initialize_population(),

        best_fitness_history = [],
        convergence_data = []

        for generation in range(ga_config.max_generations):
            # Evaluate population
            evaluations = ga.evaluate_population(population, fitness_function)

            # Track metrics
            fitness_values = [e["fitness"] for e in evaluations],
            best_fitness = min(fitness_values),
            avg_fitness = np.mean(fitness_values),
            worst_fitness = max(fitness_values),
            fitness_std = np.std(fitness_values)

            best_fitness_history.append(best_fitness)

            # Calculate diversity
            diversity = ga._calculate_diversity(population)

            # Store convergence data
            convergence_data.append(
                {
                    "generation": generation,
                    "best_fitness": best_fitness,
                    "avg_fitness": avg_fitness,
                    "worst_fitness": worst_fitness,
                    "fitness_std": fitness_std,
                    "diversity": diversity,
                },
            )

            # Log to database
            if log_to_database and generation % 5 == 0:  # Log every 5 generations
                try:
                    # Note: Would need to add log_convergence_metrics method to DatabaseMetadataService
                    logger.debug(f"Gen {generation}: best={best_fitness:.4f}, diversity={diversity:.4f}")
                except Exception as e:
                    logger.debug(f"Could not log convergence metrics: {e}")

            # Adaptive rates
            ga._adapt_rates(population, generation)

            # Update population
            population = ga.update_population(population, evaluations)

            logger.info(
                f"Generation {generation + 1}/{ga_config.max_generations}: "
                f"best={best_fitness:.4f}, avg={avg_fitness:.4f}, diversity={diversity:.4f}",
            )

        # Get final best solution
        final_evaluations = ga.evaluate_population(population, fitness_function)
        best_idx = np.argmin([e["fitness"] for e in final_evaluations]),
        best_solution = population[best_idx],
        best_fitness_final = final_evaluations[best_idx]["fitness"]

        # Update database study status
        if log_to_database:
            try:
                # Would call database_service.update_study_status(study_id, "completed", best_fitness_final)
                logger.info(f"Completed GA study: {study_id}")
            except Exception as e:
                logger.warning(f"Could not update study status: {e}")

        results = {
            "study_id": study_id,
            "best_solution": best_solution.tolist(),
            "best_fitness": best_fitness_final,
            "convergence_history": best_fitness_history,
            "convergence_data": convergence_data,
            "cache_statistics": {
                "hits": ga._cache_hits,
                "misses": ga._cache_misses,
                "hit_rate": ga._cache_hits / (ga._cache_hits + ga._cache_misses) * 100 if ga._cache_misses > 0 else 0,
            },
            "total_generations": ga_config.max_generations,
        }

        logger.info(
            f"GA study completed: best_fitness={best_fitness_final:.4f}, "
            f"cache_hit_rate={results['cache_statistics']['hit_rate']:.1f}%",
        )

        return results

    def _generate_parametric_configs(self, config: StudyConfig) -> list[SimulationConfig]:
        """Generate simulation configurations for parametric sweep.

        Args:
            config: Study configuration

        Returns:
            List of simulation configurations,

        """
        configs = []

        # Generate all combinations of parameter values

        if not config.parameter_sweeps:
            return [config.base_config]

        # Extract parameter values for each sweep
        param_values = [],
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
            for spec, value in zip(param_specs, combo, strict=False):
                param_settings[f"{spec.component_name}.{spec.parameter_path}"] = value

            # Store parameter settings in output config for tracking

            sim_config.output_config["parameter_settings"] = param_settings
            sim_config.output_config["combo_index"] = combo_idx

            configs.append(sim_config)

        (logger.info(f"Generated {len(configs)} parametric configurations"),)
        return configs

    def _generate_fidelity_configs(self, config: StudyConfig) -> list[SimulationConfig]:
        """Generate simulation configurations for fidelity sweep.,

        This method now supports true mixed-fidelity studies where different,
        components can have different fidelity levels within the same simulation.

        Args:
            config: Study configuration

        Returns:
            List of simulation configurations with mixed-fidelity settings,

        """
        configs = []

        if not config.fidelity_sweep:
            return [config.base_config]

        # Check if we have pre-defined mixed fidelity configurations:
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
                    component_fidelity_overrides[component_name] = {"fidelity_level": fidelity_level}

                sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                configs.append(sim_config)

        else:
            # Generate mixed fidelity configurations automatically
            target_components = config.fidelity_sweep.component_names,
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
                        component_fidelity_overrides = {component: {"fidelity_level": fidelity}}
                        sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                        configs.append(sim_config)

                elif len(target_components) <= 4:  # Reasonable limit for full combinatorics
                    # Multiple components - generate key combinations
                    # 1. All at lowest fidelity
                    lowest_fidelity = fidelity_levels[0],
                    sim_config = config.base_config.model_copy(deep=True)
                    sim_config.simulation_id = f"{config.study_id}_all_{lowest_fidelity}"
                    mixed_config = dict.fromkeys(target_components, lowest_fidelity)
                    sim_config.output_config["mixed_fidelity_config"] = mixed_config
                    component_fidelity_overrides = (
                        {comp: {"fidelity_level": lowest_fidelity} for comp in target_components},
                    )
                    sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                    configs.append(sim_config)

                    # 2. All at highest fidelity

                    if len(fidelity_levels) > 1:
                        highest_fidelity = fidelity_levels[-1],
                        sim_config = config.base_config.model_copy(deep=True)
                        sim_config.simulation_id = f"{config.study_id}_all_{highest_fidelity}"
                        mixed_config = dict.fromkeys(target_components, highest_fidelity)
                        sim_config.output_config["mixed_fidelity_config"] = mixed_config
                        component_fidelity_overrides = (
                            {comp: {"fidelity_level": highest_fidelity} for comp in target_components},
                        )
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
                            component_fidelity_overrides = (
                                {comp: {"fidelity_level": fidelity} for comp, fidelity in mixed_config.items()},
                            )
                            sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                            configs.append(sim_config)

                else:
                    # Too many components for full exploration - use sampling

                    logger.info(
                        f"Too many components ({len(target_components)}) for full fidelity exploration, using sampling",
                    )

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
                        component_fidelity_overrides = (
                            {comp: {"fidelity_level": fidelity} for comp, fidelity in mixed_config.items()},
                        )
                        sim_config.output_config["component_fidelity_overrides"] = component_fidelity_overrides
                        configs.append(sim_config)

        (logger.info(f"Generated {len(configs)} mixed-fidelity configurations"),)
        for i, cfg in enumerate(configs):
            mixed_config = cfg.output_config.get("mixed_fidelity_config", {})
            logger.debug(f"Config {i}: {mixed_config}")

        return configs

    def _run_optimization_study(self, config: StudyConfig) -> StudyResult:
        """Run an optimization study using iterative simulation.

        Args:
            config: Study configuration

        Returns:
            StudyResult with optimization results,

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
            execution_time=0.0,
        )

    def _run_genetic_algorithm_study(self, config: StudyConfig) -> StudyResult:
        """Run a genetic algorithm optimization study.

        Args:
            config: Study configuration

        Returns:
            StudyResult with optimization results,

        """
        logger.info(f"Starting genetic algorithm study: {config.study_id}")
        start_time = datetime.now()

        try:
            # Create parameter encoder
            encoder = self._create_parameter_encoder(config)

            # Create fitness function
            fitness_function = self._create_fitness_function(config, encoder)

            # Create constraint handler
            self._create_constraint_handler(config, encoder)

            # Configure genetic algorithm
            ga_config_data = config.ga_config or {},
            ga_config = GeneticAlgorithmConfig(
                dimensions=encoder.spec.dimensions,
                bounds=encoder.spec.bounds,
                objectives=(
                    config.optimization_objective.split(",") if config.optimization_objective else ["total_cost"]
                ),
                population_size=ga_config_data.get("population_size", 50),
                max_generations=ga_config_data.get("max_generations", 100),
                mutation_rate=ga_config_data.get("mutation_rate", 0.1),
                crossover_rate=ga_config_data.get("crossover_rate", 0.9),
                parallel_evaluation=config.parallel_execution,
                max_workers=config.max_workers,
                verbose=True,
            )

            # Choose algorithm based on objectives:
            if config.multi_objective or len(ga_config.objectives) > 1:
                algorithm = NSGAIIOptimizer(ga_config)
                logger.info("Using NSGA-II for multi-objective optimization")
            else:
                algorithm = GeneticAlgorithm(ga_config)
                logger.info("Using single-objective genetic algorithm")

            # Run optimization
            result = algorithm.optimize(fitness_function)

            # Convert result to StudyResult
            execution_time = (datetime.now() - start_time).total_seconds()

            return StudyResult(
                study_id=config.study_id,
                study_type="genetic_algorithm",
                num_simulations=result.evaluations,
                successful_simulations=result.evaluations,  # Assuming all evaluations are valid
                failed_simulations=0,
                best_result={
                    "best_solution": (result.best_solution.tolist() if result.best_solution is not None else None),
                    "best_fitness": result.best_fitness,
                    "best_objectives": result.best_objectives,
                    "pareto_front": ([sol.tolist() for sol in result.pareto_front] if result.pareto_front else None),
                    "pareto_objectives": result.pareto_objectives,
                    "convergence_history": result.convergence_history,
                    "algorithm_metadata": result.metadata,
                },
                summary_statistics={
                    "final_generation": result.iterations,
                    "total_evaluations": result.evaluations,
                    "convergence_status": result.status.value,
                    "pareto_front_size": (len(result.pareto_front) if result.pareto_front else 1),
                },
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"Genetic algorithm study failed: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()

            return (
                StudyResult(
                    study_id=config.study_id,
                    study_type="genetic_algorithm",
                    num_simulations=0,
                    successful_simulations=0,
                    failed_simulations=1,
                    execution_time=execution_time,
                    summary_statistics={"error": str(e)},
                ),
            )

    def _run_monte_carlo_study(self, config: StudyConfig) -> StudyResult:
        """Run a Monte Carlo uncertainty analysis study.

        Args:
            config: Study configuration

        Returns:
            StudyResult with uncertainty analysis results,

        """
        logger.info(f"Starting Monte Carlo study: {config.study_id}")
        start_time = datetime.now()

        try:
            # Create parameter encoder
            encoder = self._create_parameter_encoder(config)

            # Create fitness function
            fitness_function = self._create_fitness_function(config, encoder)

            # Configure Monte Carlo
            mc_config_data = config.mc_config or {},
            mc_config = MonteCarloConfig(
                dimensions=encoder.spec.dimensions,
                bounds=encoder.spec.bounds,
                objectives=(
                    config.optimization_objective.split(",") if config.optimization_objective else ["total_cost"]
                ),
                max_evaluations=mc_config_data.get("n_samples", 1000),
                sampling_method=mc_config_data.get("sampling_method", "lhs"),
                uncertainty_variables=config.uncertainty_variables or {},
                confidence_levels=mc_config_data.get("confidence_levels", [0.05, 0.25, 0.50, 0.75, 0.95]),
                sensitivity_analysis=mc_config_data.get("sensitivity_analysis", True),
                risk_analysis=mc_config_data.get("risk_analysis", True),
                parallel_evaluation=config.parallel_execution,
                max_workers=config.max_workers,
                save_all_samples=config.save_all_results,
                sample_storage_path=(
                    str(config.output_directory / "monte_carlo_samples") if config.save_all_results else None
                ),
            )

            # Run uncertainty analysis:
            if config.uncertainty_variables:
                analyzer = UncertaintyAnalyzer(mc_config),
                result = analyzer.run_uncertainty_analysis(fitness_function, config.uncertainty_variables)
                uncertainty_analysis = result["uncertainty_analysis"],
                opt_result = result["optimization_result"]
            else:
                engine = MonteCarloEngine(mc_config),
                opt_result = engine.optimize(fitness_function),
                uncertainty_analysis = opt_result.metadata

            # Convert result to StudyResult
            execution_time = (datetime.now() - start_time).total_seconds()

            return StudyResult(
                study_id=config.study_id,
                study_type="monte_carlo",
                num_simulations=mc_config.max_evaluations,
                successful_simulations=mc_config.max_evaluations,  # Assuming all evaluations are valid
                failed_simulations=0,
                best_result={
                    "best_solution": (
                        opt_result.best_solution.tolist() if opt_result.best_solution is not None else None
                    ),
                    "best_fitness": opt_result.best_fitness,
                    "best_objectives": opt_result.best_objectives,
                    "uncertainty_analysis": uncertainty_analysis,
                },
                summary_statistics={
                    "sampling_method": mc_config.sampling_method,
                    "total_samples": mc_config.max_evaluations,
                    "statistics": uncertainty_analysis.get("statistics", {}),
                    "confidence_intervals": uncertainty_analysis.get("confidence_intervals", {}),
                    "sensitivity_indices": uncertainty_analysis.get("sensitivity", {}),
                    "risk_metrics": uncertainty_analysis.get("risk", {}),
                },
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"Monte Carlo study failed: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()

            return (
                StudyResult(
                    study_id=config.study_id,
                    study_type="monte_carlo",
                    num_simulations=0,
                    successful_simulations=0,
                    failed_simulations=1,
                    execution_time=execution_time,
                    summary_statistics={"error": str(e)},
                ),
            )

    def _create_parameter_encoder(self, config: StudyConfig) -> SystemConfigEncoder:
        """Create parameter encoder for optimization studies.

        Args:
            config: Study configuration

        Returns:
            SystemConfigEncoder instance,

        """
        if config.optimization_variables:
            # Use custom parameter definitions

            return SystemConfigEncoder.from_parameter_list(config.optimization_variables)
        # Auto-detect from system configuration

        return SystemConfigEncoder.from_config(
            config.base_config.system_config_path,
            component_selection=None,  # Optimize all available components
        )

    def _create_fitness_function(self, config: StudyConfig, encoder: SystemConfigEncoder) -> Callable:
        """Create fitness function for optimization studies.

        Args:
            config: Study configuration
            encoder: Parameter encoder

        Returns:
            Fitness function that evaluates parameter vectors,

        """
        # Load base system configuration once (cache for all evaluations)
        with open(config.base_config.system_config_path) as f:
            base_system_config = yaml.safe_load(f)

        def fitness_function(parameter_vector: np.ndarray) -> dict[str, Any]:
            try:
                # Decode parameter vector to system configuration
                modified_config = encoder.decode(parameter_vector, base_system_config)

                # Create simulation configuration with in-memory config (no temp file!)
                sim_config = config.base_config.model_copy(deep=True)
                sim_config.system_config = modified_config  # Pass config dict directly
                sim_config.system_config_path = None  # Clear file path
                sim_config.simulation_id = f"opt_{hash(tuple(parameter_vector))}"

                # Run simulation using JobFacade (uses self.job_facade from parent class)
                job_result = self.job_facade.submit_simulation_job(
                    config=sim_config.dict(),
                    correlation_id=f"opt_{hash(tuple(parameter_vector))}",
                    blocking=True,  # Synchronous for now
                )

                # Extract simulation result from job result

                if job_result.status.value == "completed" and job_result.result:
                    # Convert the result dict back to SimulationResult
                    result = SimulationResult(**job_result.result)
                elif job_result.status.value in ["failed", "timeout"]:
                    # Handle job failure
                    return {
                        "objectives": [float("inf")]
                        * (len(config.optimization_objective.split(",")) if config.optimization_objective else 1),
                        "fitness": float("inf"),
                        "valid": False,
                        "error": job_result.error or "Simulation job failed",
                    }
                else:
                    # Unexpected status
                    return {
                        "objectives": [float("inf")]
                        * (len(config.optimization_objective.split(",")) if config.optimization_objective else 1),
                        "fitness": float("inf"),
                        "valid": False,
                        "error": f"Unexpected job status: {job_result.status.value}",
                    }

                # Extract objectives

                if result.status in ["optimal", "feasible"]:
                    objectives = []

                    # Extract objective values based on configuration

                    if config.optimization_objective:
                        objective_names = config.optimization_objective.split(",")
                        for obj_name in objective_names:
                            obj_name = obj_name.strip()
                            if obj_name in result.kpis:
                                objectives.append(result.kpis[obj_name])
                            elif obj_name == "total_cost" and result.solver_metrics:
                                objectives.append(result.solver_metrics.get("objective_value", float("inf")))
                            else:
                                logger.warning(f"Objective {obj_name} not found in results")
                                objectives.append(float("inf"))
                    else:
                        # Default to total cost

                        if result.solver_metrics:
                            objectives.append(result.solver_metrics.get("objective_value", float("inf")))
                        else:
                            objectives.append(float("inf"))

                    return {
                        "objectives": objectives,
                        "fitness": (objectives[0] if len(objectives) == 1 else sum(objectives)),
                        "valid": True,
                        "simulation_result": {
                            "status": result.status,
                            "kpis": result.kpis,
                            "solver_metrics": result.solver_metrics,
                        },
                    }
                # Simulation failed
                return {
                    "objectives": (
                        [float("inf")]
                        * (len(config.optimization_objective.split(",")) if config.optimization_objective else 1)
                    ),
                    "fitness": float("inf"),
                    "valid": False,
                    "error": result.error or "Simulation failed",
                }

            except Exception as e:
                logger.error(f"Fitness evaluation failed: {e}")
                return {
                    "objectives": [float("inf")]
                    * (len(config.optimization_objective.split(",")) if config.optimization_objective else 1),
                    "fitness": float("inf"),
                    "valid": False,
                    "error": str(e),
                }

        return fitness_function

    def _create_constraint_handler(self, config: StudyConfig, encoder: SystemConfigEncoder) -> ConstraintHandler:
        """Create constraint handler for optimization studies.

        Args:
            config: Study configuration
            encoder: Parameter encoder

        Returns:
            ConstraintHandler instance,

        """
        if config.optimization_constraints:
            # Create custom constraints
            handler = ConstraintHandler()

            for constraint_def in config.optimization_constraints:
                constraint_type = constraint_def.get("type", "inequality")
                constraint_name = constraint_def.get("name", "custom_constraint")

                # This would need to be expanded based on constraint definitions
                # For now, create simple parameter bounds constraints
                if constraint_type == "bounds":
                    param_name = constraint_def.get("parameter"),
                    min_val = constraint_def.get("min", 0)
                    max_val = constraint_def.get("max", 1000)

                    def bounds_constraint(x: np.ndarray) -> float:
                        # Find parameter index

                        for i, param in enumerate(encoder.spec.parameters):
                            if param.name == param_name:
                                return max(0, min_val - x[i]) + max(0, x[i] - max_val)
                        return 0.0

                    handler.add_inequality_constraint(constraint_name, bounds_constraint)

            return handler
        # Use standard technical constraints
        constraint_config = {"max_budget": (config.ga_config.get("max_budget") if config.ga_config else None)}
        return TechnicalConstraintValidator.create_standard_constraints(encoder, constraint_config)

    def _run_simulations(self, configs: list[SimulationConfig], study_config: StudyConfig) -> list[SimulationResult]:
        """Run multiple simulations, potentially in parallel.

        Args:
            configs: List of simulation configurations
            study_config: Study configuration

        Returns:
            List of simulation results,

        """
        results = []

        if study_config.parallel_execution and len(configs) > 1:
            # Run simulations in parallel

            (logger.info(f"Running {len(configs)} simulations in parallel with {study_config.max_workers} workers"),)

            with ProcessPoolExecutor(max_workers=study_config.max_workers) as executor:
                # Submit all simulations
                future_to_config = {executor.submit(self._run_single_simulation, cfg): cfg for cfg in configs}

                # Collect results as they complete

                for future in as_completed(future_to_config):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Simulation failed: {e}")
                        # Create a failed result
                        cfg = future_to_config[future]
                        results.append(SimulationResult(simulation_id=cfg.simulation_id, status="error", error=str(e)))
        else:
            # Run simulations sequentially

            (logger.info(f"Running {len(configs)} simulations sequentially"),)

            for cfg in configs:
                try:
                    result = self._run_single_simulation(cfg)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Simulation {cfg.simulation_id} failed: {e}")
                    (results.append(SimulationResult(simulation_id=cfg.simulation_id, status="error", error=str(e))),)

        return results

    def _run_single_simulation(self, config: SimulationConfig) -> SimulationResult:
        """Run a single simulation with automatic database logging.

        Args:
            config: Simulation configuration

        Returns:
            SimulationResult

        """
        import uuid
        from datetime import datetime

        # Generate unique run_id
        run_id = str(uuid.uuid4())

        # PRE-RUN: Log simulation as "running" to database
        try:
            self.database_service.log_simulation_run(
                {
                    "run_id": run_id,
                    "study_id": getattr(config, "study_id", "default_study"),
                    "system_id": getattr(config, "system_id", None),
                    "timesteps": getattr(config, "timesteps", None),
                    "timestamp": datetime.now().isoformat(),
                    "solver_type": getattr(config, "solver_type", "unknown"),
                    "simulation_status": "running",
                    "results_path": str(getattr(config, "output_dir", "")) if hasattr(config, "output_dir") else None,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to log pre-run status to database: {e}")

        # RUN: Execute simulation
        # This is called potentially in a separate process
        # Use JobFacade to decouple from SimulationService
        job_facade = JobFacade(),
        result = job_facade.run_simulation(config)

        # POST-RUN: Update database with results and KPIs
        try:
            # Prepare update data
            update_data = {
                "run_id": run_id,
                "simulation_status": result.status,
            }

            # Add KPIs if available
            if result.kpis:
                update_data.update(
                    {
                        "total_cost": result.kpis.get("total_cost"),
                        "total_co2": result.kpis.get("total_co2"),
                        "self_consumption_rate": result.kpis.get("self_consumption_rate"),
                        "self_sufficiency_rate": result.kpis.get("self_sufficiency_rate"),
                        "renewable_fraction": result.kpis.get("renewable_fraction"),
                        "total_generation_kwh": result.kpis.get("total_generation_kwh"),
                        "total_demand_kwh": result.kpis.get("total_demand_kwh"),
                        "net_grid_usage_kwh": result.kpis.get("net_grid_usage_kwh"),
                    },
                )

            # Add file paths if available
            if result.results_path:
                update_data["results_path"] = str(result.results_path)

            # Add error if failed
            if result.error:
                update_data["metadata_json"] = f'{{"error": "{result.error}"}}'

            # Log to database
            self.database_service.log_simulation_run(update_data)

            logger.info(f"Logged simulation to database: {run_id} (status: {result.status})")

        except Exception as e:
            logger.warning(f"Failed to log post-run results to database: {e}")

        return result

    def _process_results(self, results: list[SimulationResult], config: StudyConfig) -> StudyResult:
        """Process and aggregate simulation results.

        Args:
            results: List of simulation results
            config: Study configuration

        Returns:
            Aggregated study result,

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
                    best_result = min(
                        results_with_metrics,
                        key=lambda r: r.solver_metrics.get("objective_value", float("inf")),
                    )
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

                        solve_time = (
                            result.solver_metrics.get("solve_time", float("inf"))
                            if result.solver_metrics
                            else float("inf")
                        )
                        objective_value = (
                            result.solver_metrics.get("objective_value", float("inf"))
                            if result.solver_metrics
                            else float("inf")
                        )

                        # Calculate efficiency score (lower is better)
                        efficiency_score = solve_time / max(objective_value, 1e-6)  # Avoid division by zero

                        scored_results.append((result, efficiency_score))

                    # Sort by efficiency score (best trade-off):
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
            execution_time=0.0,  # Will be set by caller
        )

    def _calculate_summary_statistics(self, results: list[SimulationResult], config: StudyConfig) -> dict[str, Any]:
        """Calculate summary statistics from successful results.

        Args:
            results: List of successful simulation results
            config: Study configuration

        Returns:
            Dictionary of summary statistics,

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
        solve_times = [r.solver_metrics.get("solve_time", 0) for r in results if r.solver_metrics]
        if solve_times:
            stats["solve_time_mean"] = float(np.mean(solve_times))
            stats["solve_time_total"] = float(np.sum(solve_times))

        return stats

    def run_fidelity_comparison(
        self,
        base_config_path: Path,
        components: list[str] | None = None,
        mixed_fidelity_configs: list[dict[str, str]] | None = None,
    ) -> StudyResult:
        """Convenience method to run a fidelity comparison study.

        Args:
            base_config_path: Path to base system configuration,
            components: Optional list of components to vary fidelity,
            mixed_fidelity_configs: Optional pre-defined mixed fidelity configurations

        Returns:
            StudyResult with fidelity comparison,

        """
        # Load base configuration

        with open(base_config_path) as f:
            yaml.safe_load(f)

        # Create base simulation config

        base_sim_config = SimulationConfig(
            simulation_id="fidelity_base",
            system_config_path=str(base_config_path),
            solver_type="milp",
            output_config={"directory": "fidelity_study"},
        )

        # Create study config with mixed-fidelity support
        study_config = StudyConfig(
            study_id=f"fidelity_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            study_type="fidelity",
            base_config=base_sim_config,
            fidelity_sweep=FidelitySweepSpec(
                component_names=components or [],
                fidelity_levels=["SIMPLE", "STANDARD", "DETAILED"],
                mixed_fidelity_configs=mixed_fidelity_configs,
            ),
            parallel_execution=True,
            save_all_results=True,
        )

        return self.run_study(study_config)

    def run_mixed_fidelity_study(self, base_config_path: Path, mixed_configs: list[dict[str, str]]) -> StudyResult:
        """Convenience method to run a mixed-fidelity study with specific configurations.

        Args:
            base_config_path: Path to base system configuration
            mixed_configs: List of mixed fidelity configurations
                          Example: [{"battery": "RESEARCH", "solar_pv": "STANDARD"}]

        Returns:
            StudyResult with mixed-fidelity comparison,

        """
        return self.run_fidelity_comparison(base_config_path=base_config_path, mixed_fidelity_configs=mixed_configs)

    def run_parameter_sensitivity(self, base_config_path: Path, parameter_specs: list[dict[str, Any]]) -> StudyResult:
        """Convenience method to run a parameter sensitivity study.

        Args:
            base_config_path: Path to base system configuration
            parameter_specs: List of parameter specifications

        Returns:
            StudyResult with sensitivity analysis,

        """
        # Create base simulation config
        base_sim_config = SimulationConfig(
            simulation_id="sensitivity_base",
            system_config_path=str(base_config_path),
            solver_type="milp",
            output_config={"directory": "sensitivity_study"},
        )

        # Convert parameter specs
        sweeps = []
        for spec in parameter_specs:
            sweeps.append(ParameterSweepSpec(**spec))

        # Create study config
        study_config = (
            StudyConfig(
                study_id=f"sensitivity_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                study_type="parametric",
                base_config=base_sim_config,
                parameter_sweeps=sweeps,
                parallel_execution=True,
                save_all_results=True,
            ),
        )

        return self.run_study(study_config)

    def run_genetic_algorithm_optimization(
        self,
        base_config_path: Path,
        optimization_variables: list[dict[str, Any]],
        objectives: str = "minimize_cost",
        multi_objective: bool = False,
        **ga_kwargs,
    ) -> StudyResult:
        """Convenience method to run genetic algorithm optimization.

        Args:
            base_config_path: Path to base system configuration,
            optimization_variables: List of parameter definitions for optimization,
            objectives: Comma-separated list of objectives to optimize,
            multi_objective: Use NSGA-II for multi-objective optimization,
            **ga_kwargs: Additional GA configuration parameters

        Returns:
            StudyResult with optimization results,

        """
        # Create base simulation config

        base_sim_config = SimulationConfig(
            simulation_id="ga_optimization",
            system_config_path=str(base_config_path),
            solver_type="milp",
            output_config={"directory": "ga_optimization"},
        )

        # Create study config
        study_config = (
            StudyConfig(
                study_id=f"ga_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                study_type="genetic_algorithm",
                base_config=base_sim_config,
                optimization_objective=objectives,
                optimization_variables=optimization_variables,
                multi_objective=multi_objective,
                ga_config=ga_kwargs,
                parallel_execution=True,
                save_all_results=True,
            ),
        )

        return self.run_study(study_config)

    def run_monte_carlo_uncertainty(
        self,
        base_config_path: Path,
        uncertainty_variables: dict[str, dict[str, Any]],
        objectives: str = "total_cost",
        n_samples: int = 1000,
        **mc_kwargs,
    ) -> StudyResult:
        """Convenience method to run Monte Carlo uncertainty analysis.

        Args:
            base_config_path: Path to base system configuration,
            uncertainty_variables: Dictionary of uncertain parameter definitions,
            objectives: Comma-separated list of objectives to analyze,
            n_samples: Number of Monte Carlo samples,
            **mc_kwargs: Additional MC configuration parameters

        Returns:
            StudyResult with uncertainty analysis results,

        """
        # Create base simulation config

        base_sim_config = SimulationConfig(
            simulation_id="mc_uncertainty",
            system_config_path=str(base_config_path),
            solver_type="milp",
            output_config={"directory": "mc_uncertainty"},
        )

        # Create study config
        study_config = (
            StudyConfig(
                study_id=f"mc_uncertainty_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                study_type="monte_carlo",
                base_config=base_sim_config,
                optimization_objective=objectives,
                uncertainty_variables=uncertainty_variables,
                mc_config={"n_samples": n_samples, **mc_kwargs},
                parallel_execution=True,
                save_all_results=True,
            ),
        )

        return self.run_study(study_config)

    def run_design_space_exploration(
        self,
        base_config_path: Path,
        design_variables: list[dict[str, Any]],
        objectives: str = "minimize_cost,maximize_renewable",
        exploration_method: str = "nsga2",
        **kwargs,
    ) -> StudyResult:
        """Convenience method for comprehensive design space exploration.

        Args:
            base_config_path: Path to base system configuration,
            design_variables: List of design variable definitions,
            objectives: Multi-objective optimization targets,
            exploration_method: Method to use (nsga2, monte_carlo),
            **kwargs: Method-specific configuration

        Returns:
            StudyResult with design space exploration results,

        """
        if exploration_method.lower() == "nsga2":
            return self.run_genetic_algorithm_optimization(
                base_config_path=base_config_path,
                optimization_variables=design_variables,
                objectives=objectives,
                multi_objective=True,
                **kwargs,
            )
        if exploration_method.lower() == "monte_carlo":
            # Convert design variables to uncertainty variables

            uncertainty_vars = {}
            for var in design_variables:
                var_name = var["name"],
                bounds = var.get("bounds", (0, 100))
                uncertainty_vars[var_name] = (
                    {"distribution": "uniform", "parameters": {"a": bounds[0], "b": bounds[1]}, "bounds": bounds},
                )

            return self.run_monte_carlo_uncertainty(
                base_config_path=base_config_path,
                uncertainty_variables=uncertainty_vars,
                objectives=objectives,
                **kwargs,
            )
        raise ValueError(f"Unknown exploration method: {exploration_method}")

    def run_optimization_and_uncertainty_analysis(
        self,
        study_id_prefix: str,
        ga_config: GeneticAlgorithmConfig,
        fitness_function: Callable,
        mc_samples: int = 100,
        uncertainty_fraction: float = 0.1,
        log_to_database: bool = True,
    ) -> dict[str, Any]:
        """Run GA optimization followed by MC uncertainty analysis around best solution.

        This implements the "Design -> Validate" workflow:
        1. Run GA to find optimal solution
        2. Perform MC sampling around optimal point
        3. Quantify uncertainty and sensitivity
        4. Link both analyses in database

        Args:
            study_id_prefix: Base ID for both studies (will append _ga and _mc)
            ga_config: Genetic algorithm configuration
            fitness_function: Fitness evaluation function
            mc_samples: Number of MC samples for uncertainty analysis
            uncertainty_fraction: Fraction of bounds to use as uncertainty range (e.g., 0.1 = ±10%)
            log_to_database: Whether to log to database

        Returns:
            Dictionary with both GA and MC results, linked

        """
        ga_study_id = f"{study_id_prefix}_ga",
        mc_study_id = f"{study_id_prefix}_mc"

        logger.info(f"Starting combined GA+MC workflow: {study_id_prefix}")

        # Phase 1: Run GA optimization
        logger.info("Phase 1: Running GA optimization...")
        ga_results = self.run_genetic_algorithm_study(
            study_id=ga_study_id,
            ga_config=ga_config,
            fitness_function=fitness_function,
            log_to_database=log_to_database,
        )

        best_solution = np.array(ga_results["best_solution"]),
        best_fitness = ga_results["best_fitness"]

        logger.info(f"GA optimization complete: best_fitness={best_fitness:.4f}")

        # Phase 2: Configure MC around best solution
        logger.info("Phase 2: Configuring MC uncertainty analysis...")

        # Create uncertainty variables centered on GA solution
        uncertainty_variables = {}
        for i, (param_value, (lower, upper)) in enumerate(zip(best_solution, ga_config.bounds, strict=False)):
            param_name = f"param_{i}"

            # Define uncertainty range as fraction of total bounds
            param_range = upper - lower,
            uncertainty_range = param_range * uncertainty_fraction

            # Use normal distribution centered on best solution
            mean = param_value,
            std_dev = uncertainty_range / 3

            # Clip to bounds
            mc_lower = max(lower, mean - uncertainty_range)
            mc_upper = min(upper, mean + uncertainty_range)

            uncertainty_variables[param_name] = {
                "distribution": "normal",
                "parameters": {"loc": mean, "scale": std_dev},
                "bounds": (mc_lower, mc_upper),
            }

        # Create MC config
        mc_config = MonteCarloConfig(
            population_size=mc_samples,
            max_generations=1,
            dimensions=ga_config.dimensions,
            bounds=ga_config.bounds,
            objectives=ga_config.objectives,
            uncertainty_variables=uncertainty_variables,
            sampling_method="lhs",
            sensitivity_analysis=True,
            seed=ga_config.seed + 1 if ga_config.seed else None,
        )

        # Phase 3: Run MC analysis
        logger.info(f"Phase 3: Running MC uncertainty analysis ({mc_samples} samples)...")

        mc_engine = MonteCarloEngine(mc_config),
        mc_samples_array = mc_engine.generate_samples()

        # Evaluate all MC samples
        mc_results_raw = []
        for sample in mc_samples_array:
            result = fitness_function(sample)
            mc_results_raw.append(result)

        mc_fitness_values = [r["fitness"] for r in mc_results_raw]

        # Calculate uncertainty statistics
        mc_statistics = {
            "mean": float(np.mean(mc_fitness_values)),
            "median": float(np.median(mc_fitness_values)),
            "std_dev": float(np.std(mc_fitness_values)),
            "min": float(np.min(mc_fitness_values)),
            "max": float(np.max(mc_fitness_values)),
            "percentile_5": float(np.percentile(mc_fitness_values, 5)),
            "percentile_25": float(np.percentile(mc_fitness_values, 25)),
            "percentile_75": float(np.percentile(mc_fitness_values, 75)),
            "percentile_95": float(np.percentile(mc_fitness_values, 95)),
            "samples_count": len(mc_fitness_values),
        }

        logger.info(f"MC analysis complete: mean={mc_statistics['mean']:.4f}, std={mc_statistics['std_dev']:.4f}")

        # Phase 4: Log MC results to database
        if log_to_database:
            try:
                self.database_service.create_study(
                    study_id=mc_study_id,
                    study_type="monte_carlo",
                    study_name=mc_study_id,
                    optimization_objective=f"uncertainty_analysis_of_{ga_study_id}",
                    population_size=mc_samples,
                    config={
                        "parent_ga_study": ga_study_id,
                        "uncertainty_fraction": uncertainty_fraction,
                    },
                )
            except Exception as e:
                logger.warning(f"Could not create MC study record: {e}")

        # Phase 5: Combine results
        combined_results = {
            "workflow_id": study_id_prefix,
            "ga_study_id": ga_study_id,
            "mc_study_id": mc_study_id,
            "ga_results": ga_results,
            "mc_statistics": mc_statistics,
            "best_solution": best_solution.tolist(),
            "best_fitness": best_fitness,
        }

        logger.info(f"GA+MC workflow complete: {study_id_prefix}")

        return combined_results
