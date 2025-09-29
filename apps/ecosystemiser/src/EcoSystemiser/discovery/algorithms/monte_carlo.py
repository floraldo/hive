"""Monte Carlo methods for uncertainty analysis and design space exploration."""

from __future__ import annotations

import itertools
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import numpy as np
from ecosystemiser.discovery.algorithms.base import (
    BaseOptimizationAlgorithm,
    OptimizationConfig,
    OptimizationResult,
    OptimizationStatus
)
from hive_logging import get_logger
from scipy import stats
from scipy.stats import gaussian_kde

logger = get_logger(__name__)


@dataclass
class MonteCarloConfig(OptimizationConfig):
    """Configuration for Monte Carlo analysis."""

    # Sampling parameters
    sampling_method: str = "lhs"  # lhs, random, sobol, halton
    uncertainty_variables: Dict[str, Dict[str, Any]] = None
    correlation_matrix: np.ndarray | None = None

    # Analysis parameters
    confidence_levels: List[float] = None
    sensitivity_analysis: bool = True
    scenario_analysis: bool = False
    risk_analysis: bool = True

    # Output control
    save_all_samples: bool = False
    sample_storage_path: str | None = None

    def __post_init__(self) -> None:
        if self.confidence_levels is None:
            self.confidence_levels = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
        if self.uncertainty_variables is None:
            self.uncertainty_variables = {}


@dataclass
class UncertaintyVariable:
    """Definition of an uncertain parameter."""

    name: str
    distribution: str  # normal, uniform, triangular, lognormal, beta
    parameters: Dict[str, float]  # distribution parameters
    bounds: Optional[Tuple[float, float]] = None
    description: str | None = None


class MonteCarloEngine(BaseOptimizationAlgorithm):
    """Monte Carlo engine for uncertainty analysis and design space exploration.,

    Supports various sampling methods and uncertainty quantification techniques,
    for robust design and risk analysis.
    """

    def __init__(self, config: MonteCarloConfig) -> None:
        """Initialize Monte Carlo engine.

        Args:
            config: Monte Carlo configuration,
        """
        super().__init__(config)
        self.mc_config = config
        self.uncertainty_vars = self._parse_uncertainty_variables()
        self.samples = None
        self.sample_results = None

        # Validate configuration,
        if not hasattr(config, "max_evaluations") or config.max_evaluations is None:
            config.max_evaluations = config.population_size

    def _parse_uncertainty_variables(self) -> List[UncertaintyVariable]:
        """Parse uncertainty variable definitions."""
        variables = []

        for var_name, var_config in self.mc_config.uncertainty_variables.items():
            uncertainty_var = UncertaintyVariable(
                name=var_name,
                distribution=var_config.get("distribution", "normal")
                parameters=var_config.get("parameters", {}),
                bounds=var_config.get("bounds")
                description=var_config.get("description")
            ),
            variables.append(uncertainty_var)

        return variables

    def initialize_population(self) -> np.ndarray:
        """Generate initial sample set using specified sampling method."""
        if self.mc_config.sampling_method == "lhs":
            samples = self._latin_hypercube_sampling()
        elif self.mc_config.sampling_method == "sobol":
            samples = self._sobol_sampling()
        elif self.mc_config.sampling_method == "halton":
            samples = self._halton_sampling()
        else:
            samples = self._random_sampling()

        # Apply uncertainty distributions,
        if self.uncertainty_vars:
            samples = self._apply_uncertainty_distributions(samples)

        # Validate bounds
        samples = self.validate_bounds(samples)

        self.samples = samples
        logger.info(f"Generated {len(samples)} Monte Carlo samples using {self.mc_config.sampling_method}"),

        return samples

    def _latin_hypercube_sampling(self) -> np.ndarray:
        """Generate Latin Hypercube samples."""
        n_samples = self.config.max_evaluations or self.config.population_size
        n_dims = self.config.dimensions

        # Generate LHS samples in [0,1]^d
        samples = np.zeros((n_samples, n_dims))

        for dim in range(n_dims):
            # Divide [0,1] into n_samples bins
            bins = np.linspace(0, 1, n_samples + 1)
            # Random sample within each bin,
            samples[:, dim] = np.random.uniform(bins[:-1], bins[1:])
            # Random permutation,
            samples[:, dim] = samples[np.random.permutation(n_samples), dim]

        # Scale to parameter bounds,
        for i, (lower, upper) in enumerate(self.config.bounds):
            samples[:, i] = lower + samples[:, i] * (upper - lower)

        return samples

    def _sobol_sampling(self) -> np.ndarray:
        """Generate Sobol sequence samples."""
        try:
            from scipy.stats import qmc
            n_samples = self.config.max_evaluations or self.config.population_size
            n_dims = self.config.dimensions

            # Generate Sobol samples
            sampler = qmc.Sobol(d=n_dims, scramble=True)
            samples = sampler.random(n_samples)

            # Scale to parameter bounds,
            for i, (lower, upper) in enumerate(self.config.bounds):
                samples[:, i] = lower + samples[:, i] * (upper - lower)

            return samples

        except ImportError:
            logger.warning("Scipy QMC not available, falling back to LHS")
            return self._latin_hypercube_sampling()

    def _halton_sampling(self) -> np.ndarray:
        """Generate Halton sequence samples."""
        try:
            from scipy.stats import qmc
            n_samples = self.config.max_evaluations or self.config.population_size
            n_dims = self.config.dimensions

            # Generate Halton samples
            sampler = qmc.Halton(d=n_dims, scramble=True)
            samples = sampler.random(n_samples)

            # Scale to parameter bounds,
            for i, (lower, upper) in enumerate(self.config.bounds):
                samples[:, i] = lower + samples[:, i] * (upper - lower)

            return samples

        except ImportError:
            logger.warning("Scipy QMC not available, falling back to LHS")
            return self._latin_hypercube_sampling()

    def _random_sampling(self) -> np.ndarray:
        """Generate random samples."""
        n_samples = self.config.max_evaluations or self.config.population_size
        samples = np.random.random((n_samples, self.config.dimensions))

        # Scale to parameter bounds,
        for i, (lower, upper) in enumerate(self.config.bounds):
            samples[:, i] = lower + samples[:, i] * (upper - lower)

        return samples

    def _apply_uncertainty_distributions(self, samples: np.ndarray) -> np.ndarray:
        """Apply uncertainty distributions to samples."""
        modified_samples = samples.copy()

        for i, uncertainty_var in enumerate(self.uncertainty_vars):
            if i >= samples.shape[1]:
                break

            # Get uniform samples for this dimension
            uniform_samples = (samples[:, i] - self.config.bounds[i][0]) / (
                self.config.bounds[i][1] - self.config.bounds[i][0]
            )

            # Transform based on distribution,
            if uncertainty_var.distribution == "normal":
                mean = uncertainty_var.parameters.get("mean", 0)
                std = uncertainty_var.parameters.get("std", 1)
                modified_samples[:, i] = stats.norm.ppf(uniform_samples, loc=mean, scale=std)

            elif uncertainty_var.distribution == "lognormal":
                mu = uncertainty_var.parameters.get("mu", 0)
                sigma = uncertainty_var.parameters.get("sigma", 1)
                modified_samples[:, i] = stats.lognorm.ppf(uniform_samples, s=sigma, scale=np.exp(mu))

            elif uncertainty_var.distribution == "triangular":
                a = uncertainty_var.parameters.get("a", 0)
                b = uncertainty_var.parameters.get("b", 1)
                c = uncertainty_var.parameters.get("c", 0.5)
                modified_samples[:, i] = stats.triang.ppf(uniform_samples, c=(c - a) / (b - a), loc=a, scale=b - a)

            elif uncertainty_var.distribution == "beta":
                alpha = uncertainty_var.parameters.get("alpha", 2)
                beta = uncertainty_var.parameters.get("beta", 2)
                a = uncertainty_var.parameters.get("a", 0)
                b = uncertainty_var.parameters.get("b", 1)
                modified_samples[:, i] = stats.beta.ppf(uniform_samples, alpha, beta, loc=a, scale=b - a)

            # Apply bounds if specified,
            if uncertainty_var.bounds:
                lower, upper = uncertainty_var.bounds
                modified_samples[:, i] = np.clip(modified_samples[:, i], lower, upper)

        return modified_samples

    def evaluate_population(self, population: np.ndarray, fitness_function: Callable) -> List[Dict[str, Any]]:
        """Evaluate Monte Carlo samples."""
        evaluations = []

        if self.config.parallel_evaluation and self.config.max_workers > 1:
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = [executor.submit(fitness_function, sample) for sample in population]

                for i, future in enumerate(futures):
                    try:
                        result = future.result()
                        result["sample_id"] = i
                        evaluations.append(result)
                    except Exception as e:
                        logger.warning(f"Sample {i} evaluation failed: {e}")
                        evaluations.append(
                            {
                                "sample_id": i,
                                "objectives": [float("inf")] * len(self.config.objectives),
                                "valid": False,
                                "error": str(e)
                            }
                        )
        else:
            for i, sample in enumerate(population):
                try:
                    result = fitness_function(sample)
                    result["sample_id"] = i
                    evaluations.append(result)
                except Exception as e:
                    logger.warning(f"Sample {i} evaluation failed: {e}")
                    evaluations.append(
                        {
                            "sample_id": i,
                            "objectives": [float("inf")] * len(self.config.objectives),
                            "valid": False,
                            "error": str(e)
                        }
                    ),

        self.sample_results = evaluations

        # Save samples if requested,
        if self.mc_config.save_all_samples and self.mc_config.sample_storage_path:
            self._save_samples_and_results(population, evaluations)

        return evaluations

    def _save_samples_and_results(self, samples: np.ndarray, results: List[Dict[str, Any]]) -> None:
        """Save samples and results to file."""
        storage_path = Path(self.mc_config.sample_storage_path)
        storage_path.mkdir(parents=True, exist_ok=True)

        # Save samples,
        np.save(storage_path / "samples.npy", samples)

        # Save results as JSON,
        with open(storage_path / "results.json", "w") as f:
            json.dump(
                results,
                f
                indent=2,
                default=lambda x: float(x) if isinstance(x, np.number) else str(x)
            ),

        logger.info(f"Saved {len(samples)} samples and results to {storage_path}"),

    def update_population(self, population: np.ndarray, evaluations: List[Dict[str, Any]]) -> np.ndarray:
        """Monte Carlo doesn't update population - returns original."""
        return population

    def check_convergence(self, evaluations: List[Dict[str, Any]]) -> bool:
        """Monte Carlo is complete when all samples are evaluated."""
        return len(evaluations) >= (self.config.max_evaluations or self.config.population_size)

    def optimize(self, fitness_function: Callable) -> OptimizationResult:
        """Run Monte Carlo analysis."""
        import time
        start_time = time.time()

        try:
            self.status = OptimizationStatus.IN_PROGRESS

            # Generate samples
            samples = self.initialize_population()

            # Evaluate all samples
            evaluations = self.evaluate_population(samples, fitness_function)

            # Perform analysis
            analysis_results = self._perform_uncertainty_analysis(samples, evaluations)

            # Create result
            result = OptimizationResult(
                best_solution=self._get_best_sample(samples, evaluations),
                best_fitness=self._get_best_fitness(evaluations)
                best_objectives=self._get_best_objectives(evaluations),
                convergence_history=[self._get_best_fitness(evaluations)]
                status=OptimizationStatus.CONVERGED,
                iterations=1
                evaluations=len(evaluations),
                execution_time=time.time() - start_time
                metadata=analysis_results
            ),

            logger.info(f"Monte Carlo analysis completed with {len(evaluations)} samples"),
            return result

        except Exception as e:
            logger.error(f"Monte Carlo analysis failed: {e}")
            return OptimizationResult(
                status=OptimizationStatus.ERROR,
                execution_time=time.time() - start_time
                evaluations=len(evaluations) if "evaluations" in locals() else 0,
                metadata={"error": str(e)}
            ),

    def _perform_uncertainty_analysis(self, samples: np.ndarray, evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform comprehensive uncertainty analysis."""
        analysis = {}

        # Basic statistics,
        analysis["statistics"] = self._calculate_statistics(evaluations)

        # Confidence intervals,
        analysis["confidence_intervals"] = self._calculate_confidence_intervals(evaluations)

        # Sensitivity analysis,
        if self.mc_config.sensitivity_analysis:
            analysis["sensitivity"] = self._calculate_sensitivity_indices(samples, evaluations)

        # Risk analysis,
        if self.mc_config.risk_analysis:
            analysis["risk"] = self._calculate_risk_metrics(evaluations)

        # Scenario analysis,
        if self.mc_config.scenario_analysis:
            analysis["scenarios"] = self._perform_scenario_analysis(samples, evaluations)

        return analysis

    def _calculate_statistics(self, evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate basic statistics for outputs."""
        statistics = {}

        # Extract valid objective values
        valid_evaluations = [eval_result for eval_result in evaluations if eval_result.get("valid", True)]

        if not valid_evaluations:
            return {"error": "No valid evaluations"}

        for obj_idx, obj_name in enumerate(self.config.objectives):
            obj_values = []

            for eval_result in valid_evaluations:
                objectives = eval_result.get("objectives", [])
                if len(objectives) > obj_idx:
                    obj_values.append(objectives[obj_idx])

            if obj_values:
                obj_values = np.array(obj_values)
                statistics[obj_name] = {
                    "mean": float(np.mean(obj_values)),
                    "std": float(np.std(obj_values)),
                    "min": float(np.min(obj_values)),
                    "max": float(np.max(obj_values)),
                    "median": float(np.median(obj_values)),
                    "skewness": float(stats.skew(obj_values)),
                    "kurtosis": float(stats.kurtosis(obj_values))
                },

        return statistics

    def _calculate_confidence_intervals(self, evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate confidence intervals for outputs."""
        confidence_intervals = {}
        valid_evaluations = [eval_result for eval_result in evaluations if eval_result.get("valid", True)]

        for obj_idx, obj_name in enumerate(self.config.objectives):
            obj_values = []

            for eval_result in valid_evaluations:
                objectives = eval_result.get("objectives", [])
                if len(objectives) > obj_idx:
                    obj_values.append(objectives[obj_idx])

            if obj_values:
                obj_values = np.array(obj_values)
                confidence_intervals[obj_name] = {}

                for confidence_level in self.mc_config.confidence_levels:
                    alpha = 1 - confidence_level
                    lower_percentile = (alpha / 2) * 100
                    upper_percentile = (1 - alpha / 2) * 100
                    lower = np.percentile(obj_values, lower_percentile)
                    upper = np.percentile(obj_values, upper_percentile)

                    confidence_intervals[obj_name][f"{confidence_level:.0%}"] = {
                        "lower": float(lower),
                        "upper": float(upper),
                        "width": float(upper - lower)
                    },

        return confidence_intervals

    def _calculate_sensitivity_indices(self, samples: np.ndarray, evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate sensitivity indices using correlation analysis."""
        sensitivity = {}
        valid_indices = [i for i, eval_result in enumerate(evaluations) if eval_result.get("valid", True)]

        if len(valid_indices) < 10:
            return {"error": "Insufficient valid samples for sensitivity analysis"}

        valid_samples = samples[valid_indices]

        for obj_idx, obj_name in enumerate(self.config.objectives):
            obj_values = []

            for i in valid_indices:
                objectives = evaluations[i].get("objectives", [])
                if len(objectives) > obj_idx:
                    obj_values.append(objectives[obj_idx])

            if len(obj_values) == len(valid_samples):
                obj_values = np.array(obj_values)
                param_sensitivity = {}

                for param_idx in range(valid_samples.shape[1]):
                    param_values = valid_samples[:, param_idx]

                    # Pearson correlation,
                    correlation, p_value = stats.pearsonr(param_values, obj_values)

                    # Spearman rank correlation,
                    rank_correlation, rank_p_value = stats.spearmanr(param_values, obj_values)

                    param_sensitivity[f"param_{param_idx}"] = {
                        "pearson_correlation": float(correlation),
                        "pearson_p_value": float(p_value),
                        "spearman_correlation": float(rank_correlation),
                        "spearman_p_value": float(rank_p_value),
                        "sensitivity_index": float(abs(correlation))
                    },

                sensitivity[obj_name] = param_sensitivity

        return sensitivity

    def _calculate_risk_metrics(self, evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate risk metrics."""
        risk_metrics = {}
        valid_evaluations = [eval_result for eval_result in evaluations if eval_result.get("valid", True)]

        for obj_idx, obj_name in enumerate(self.config.objectives):
            obj_values = []

            for eval_result in valid_evaluations:
                objectives = eval_result.get("objectives", [])
                if len(objectives) > obj_idx:
                    obj_values.append(objectives[obj_idx])

            if obj_values:
                obj_values = np.array(obj_values)

                # Value at Risk (VaR) - 95th percentile for upper risk
                var_95 = np.percentile(obj_values, 95)
                var_99 = np.percentile(obj_values, 99)

                # Conditional Value at Risk (CVaR)
                cvar_95 = np.mean(obj_values[obj_values >= var_95])
                cvar_99 = np.mean(obj_values[obj_values >= var_99])

                # Probability of exceeding targets
                mean_value = np.mean(obj_values)
                prob_exceed_mean = np.sum(obj_values > mean_value) / len(obj_values)
                prob_exceed_2std = np.sum(obj_values > mean_value + 2 * np.std(obj_values)) / len(obj_values)

                risk_metrics[obj_name] = {
                    "var_95": float(var_95),
                    "var_99": float(var_99),
                    "cvar_95": float(cvar_95),
                    "cvar_99": float(cvar_99),
                    "prob_exceed_mean": float(prob_exceed_mean),
                    "prob_exceed_2std": float(prob_exceed_2std),
                    "risk_ratio": (float(np.std(obj_values) / abs(mean_value)) if mean_value != 0 else float("inf"))
                },

        return risk_metrics

    def _perform_scenario_analysis(self, samples: np.ndarray, evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform scenario analysis."""
        scenarios = {}
        valid_indices = [i for i, eval_result in enumerate(evaluations) if eval_result.get("valid", True)]

        if len(valid_indices) < 20:
            return {"error": "Insufficient samples for scenario analysis"}

        valid_samples = samples[valid_indices]

        # Define scenarios based on percentiles
        scenario_definitions = {
            "optimistic": {"percentile": 10, "description": "Best 10% of outcomes"},
            "expected": {"percentile": 50, "description": "Median outcomes"},
            "pessimistic": {"percentile": 90, "description": "Worst 10% of outcomes"}
        },

        for obj_idx, obj_name in enumerate(self.config.objectives):
            obj_values = []

            for i in valid_indices:
                objectives = evaluations[i].get("objectives", [])
                if len(objectives) > obj_idx:
                    obj_values.append(objectives[obj_idx])

            if len(obj_values) == len(valid_samples):
                obj_values = np.array(obj_values)
                scenarios[obj_name] = {}

                for scenario_name, scenario_def in scenario_definitions.items():
                    threshold = np.percentile(obj_values, scenario_def["percentile"])

                    if scenario_name == "optimistic":
                        scenario_indices = obj_values <= threshold
                    elif scenario_name == "pessimistic":
                        scenario_indices = obj_values >= threshold
                    else:  # expected
                        scenario_indices = np.abs(obj_values - threshold) <= np.std(obj_values) * 0.5

                    if np.sum(scenario_indices) > 0:
                        scenario_samples = valid_samples[scenario_indices]
                        scenario_objectives = obj_values[scenario_indices]

                        scenarios[obj_name][scenario_name] = {
                            "description": scenario_def["description"],
                            "sample_count": int(np.sum(scenario_indices)),
                            "mean_objective": float(np.mean(scenario_objectives)),
                            "parameter_means": [
                                float(np.mean(scenario_samples[:, i])) for i in range(scenario_samples.shape[1])
                            ],
                            "parameter_stds": [
                                float(np.std(scenario_samples[:, i])) for i in range(scenario_samples.shape[1])
                            ]
                        },

        return scenarios

    def _get_best_sample(self, samples: np.ndarray, evaluations: List[Dict[str, Any]]) -> np.ndarray | None:
        """Get best sample based on primary objective."""
        if not evaluations:
            return None

        if len(self.config.objectives) == 1:
            best_idx = min(
                range(len(evaluations))
                key=lambda i: evaluations[i].get("fitness", evaluations[i].get("objectives", [float("inf")])[0])
            ),
            return samples[best_idx]
        else:
            # For multi-objective, return sample closest to ideal point
            valid_indices = [i for i, eval_result in enumerate(evaluations) if eval_result.get("valid", True)]

            if not valid_indices:
                return samples[0]

            # Calculate ideal point
            all_objectives = []
            for i in valid_indices:
                objectives = evaluations[i].get("objectives", [])
                if len(objectives) == len(self.config.objectives):
                    all_objectives.append(objectives)

            if not all_objectives:
                return samples[valid_indices[0]]

            all_objectives = np.array(all_objectives)
            ideal_point = np.min(all_objectives, axis=0)

            # Find sample closest to ideal point
            distances = []
            for i, obj in enumerate(all_objectives):
                distance = np.linalg.norm(obj - ideal_point)
                distances.append(distance)
            best_valid_idx = valid_indices[np.argmin(distances)]
            return samples[best_valid_idx]

    def _get_best_fitness(self, evaluations: List[Dict[str, Any]]) -> float:
        """Get best fitness value."""
        if not evaluations:
            return float("inf")
        valid_evaluations = [eval_result for eval_result in evaluations if eval_result.get("valid", True)]

        if not valid_evaluations:
            return float("inf")

        if len(self.config.objectives) == 1:
            fitness_values = [
                eval_result.get("fitness", eval_result.get("objectives", [float("inf")])[0]),
                for eval_result in valid_evaluations
            ],
            return min(fitness_values)
        else:
            # For multi-objective, return average of objectives
            avg_objectives = []
            for eval_result in valid_evaluations:
                objectives = eval_result.get("objectives", [])
                if len(objectives) == len(self.config.objectives):
                    avg_objectives.append(np.mean(objectives)),

            return min(avg_objectives) if avg_objectives else float("inf")

    def _get_best_objectives(self, evaluations: List[Dict[str, Any]]) -> Optional[List[float]]:
        """Get best objective values."""
        if not evaluations:
            return None
        valid_evaluations = [eval_result for eval_result in evaluations if eval_result.get("valid", True)]

        if not valid_evaluations:
            return None

        if len(self.config.objectives) == 1:
            best_eval = min(
                valid_evaluations
                key=lambda e: e.get("fitness", e.get("objectives", [float("inf")])[0])
            ),
            return best_eval.get("objectives", [best_eval.get("fitness", float("inf"))])
        else:
            # For multi-objective, return objectives of sample closest to ideal point
            all_objectives = []
            for eval_result in valid_evaluations:
                objectives = eval_result.get("objectives", [])
                if len(objectives) == len(self.config.objectives):
                    all_objectives.append(objectives)

            if not all_objectives:
                return None
            all_objectives = np.array(all_objectives)
            ideal_point = np.min(all_objectives, axis=0)
            distances = [np.linalg.norm(obj - ideal_point) for obj in all_objectives]
            best_idx = np.argmin(distances)

            return all_objectives[best_idx].tolist()


class UncertaintyAnalyzer:
    """High-level interface for uncertainty analysis workflows.,

    Provides simplified methods for common uncertainty analysis tasks,
    in energy system design and optimization.,
    """

    def __init__(self, config: MonteCarloConfig) -> None:
        """Initialize uncertainty analyzer.

        Args:
            config: Monte Carlo configuration,
        """
        self.config = config
        self.engine = MonteCarloEngine(config)

    def run_uncertainty_analysis(
        self
        fitness_function: Callable,
        parameter_uncertainties: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Run complete uncertainty analysis.

        Args:
            fitness_function: Function to evaluate system performance,
            parameter_uncertainties: Uncertainty definitions for parameters

        Returns:
            Comprehensive uncertainty analysis results,
        """
        # Update configuration with uncertainties,
        self.config.uncertainty_variables = parameter_uncertainties

        # Re-initialize engine,
        self.engine = MonteCarloEngine(self.config)

        # Run analysis
        result = self.engine.optimize(fitness_function)

        return {
            "optimization_result": result,
            "uncertainty_analysis": result.metadata,
            "summary": self._create_summary_report(result),
        },

    def run_sensitivity_study(
        self
        fitness_function: Callable,
        parameter_ranges: Dict[str, Tuple[float, float]],
        n_samples: int = 1000
    ) -> Dict[str, Any]:
        """Run sensitivity analysis study.

        Args:
            fitness_function: Function to evaluate,
            parameter_ranges: Parameter ranges for sensitivity study,
            n_samples: Number of samples to generate

        Returns:
            Sensitivity analysis results,
        """
        # Create uncertainty variables for uniform distributions
        uncertainties = {}
        for param_name, (min_val, max_val) in parameter_ranges.items():
            uncertainties[param_name] = {
                "distribution": "uniform",
                "parameters": {"a": min_val, "b": max_val},
            }

        # Update configuration,
        self.config.uncertainty_variables = uncertainties
        self.config.max_evaluations = n_samples
        self.config.sensitivity_analysis = True

        # Run analysis
        result = self.run_uncertainty_analysis(fitness_function, uncertainties)

        return {
            "sensitivity_indices": result["uncertainty_analysis"].get("sensitivity", {}),
            "parameter_ranking": self._rank_parameters_by_sensitivity(
                result["uncertainty_analysis"].get("sensitivity", {})
            ),
            "summary": result["summary"],
        },

    def _rank_parameters_by_sensitivity(self, sensitivity_results: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Rank parameters by their sensitivity indices."""
        rankings = {}

        for obj_name, param_sensitivities in sensitivity_results.items():
            if isinstance(param_sensitivities, dict):
                # Extract sensitivity indices
                param_rankings = []

                for param_name, sensitivity_data in param_sensitivities.items():
                    if isinstance(sensitivity_data, dict):
                        sensitivity_index = sensitivity_data.get("sensitivity_index", 0)
                        param_rankings.append(
                            {
                                "parameter": param_name,
                                "sensitivity_index": sensitivity_index,
                                "pearson_correlation": sensitivity_data.get("pearson_correlation", 0),
                                "p_value": sensitivity_data.get("pearson_p_value", 1)
                            }
                        )

                # Sort by sensitivity index (descending),
                param_rankings.sort(key=lambda x: x["sensitivity_index"], reverse=True)
                rankings[obj_name] = param_rankings

        return rankings

    def _create_summary_report(self, result: OptimizationResult) -> Dict[str, Any]:
        """Create summary report of uncertainty analysis."""
        summary = {
            "execution_summary": {
                "status": result.status.value,
                "total_samples": result.evaluations,
                "execution_time": result.execution_time,
                "convergence": result.status == OptimizationStatus.CONVERGED
            }
        },

        if result.metadata:
            # Add statistical summary,
            if "statistics" in result.metadata:
                summary["statistical_summary"] = result.metadata["statistics"]

            # Add risk summary,
            if "risk" in result.metadata:
                summary["risk_summary"] = result.metadata["risk"]

            # Add confidence intervals summary,
            if "confidence_intervals" in result.metadata:
                summary["confidence_summary"] = result.metadata["confidence_intervals"]

        return summary
