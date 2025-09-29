"""Base classes for optimization algorithms."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, ListTuple

import numpy as np
from hive_logging import get_logger

logger = get_logger(__name__)


class OptimizationStatus(Enum):
    """Status of optimization algorithm."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    CONVERGED = "converged"
    MAX_ITERATIONS = "max_iterations"
    TERMINATED = "terminated"
    ERROR = "error"


@dataclass
class OptimizationResult:
    """Result of an optimization run."""

    best_solution: np.ndarray | None = None
    best_fitness: float | None = None
    best_objectives: Optional[List[float]] = None
    pareto_front: Optional[List[np.ndarray]] = None
    pareto_objectives: Optional[List[List[float]]] = None
    convergence_history: Optional[List[float]] = None
    status: OptimizationStatus = OptimizationStatus.NOT_STARTED
    iterations: int = 0
    evaluations: int = 0
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


@dataclass
class OptimizationConfig:
    """Configuration for optimization algorithms."""

    # Problem definition
    dimensions: int
    bounds: List[Tuple[float, float]]  # (min, max) for each dimension
    objectives: List[str]  # List of objective names
    constraints: Optional[List[Callable]] = None

    # Algorithm parameters
    population_size: int = 50
    max_generations: int = 100
    max_evaluations: int | None = None
    convergence_tolerance: float = 1e-6
    convergence_patience: int = 10

    # Multi-objective parameters
    crowding_distance_weight: float = 1.0
    diversity_weight: float = 0.5

    # Execution parameters
    parallel_evaluation: bool = True
    max_workers: int = 4
    seed: int | None = None
    verbose: bool = True

    # Termination criteria
    target_fitness: float | None = None
    time_limit: float | None = None  # seconds


class BaseOptimizationAlgorithm(ABC):
    """Abstract base class for all optimization algorithms.

    This class defines the interface that all optimization algorithms
    must implement to be compatible with the Discovery Engine.
    """

    def __init__(self, config: OptimizationConfig) -> None:
        """Initialize the optimization algorithm.

        Args:
            config: Optimization configuration
        """
        self.config = config
        self.status = OptimizationStatus.NOT_STARTED
        self.current_generation = 0
        self.current_evaluations = 0
        self.convergence_history = []

        # Set random seed for reproducibility
        if config.seed is not None:
            np.random.seed(config.seed)

    @abstractmethod
    def initialize_population(self) -> np.ndarray:
        """Initialize the population for optimization.

        Returns:
            Initial population array of shape (population_size, dimensions)
        """
        pass

    @abstractmethod
    def evaluate_population(self, population: np.ndarray, fitness_function: Callable) -> List[Dict[str, Any]]:
        """Evaluate the fitness of a population.

        Args:
            population: Population array
            fitness_function: Function to evaluate fitness

        Returns:
            List of evaluation results containing objectives and metadata
        """
        pass

    @abstractmethod
    def update_population(self, population: np.ndarray, evaluations: List[Dict[str, Any]]) -> np.ndarray:
        """Update the population based on evaluation results.

        Args:
            population: Current population
            evaluations: Evaluation results

        Returns:
            Updated population
        """
        pass

    @abstractmethod
    def check_convergence(self, evaluations: List[Dict[str, Any]]) -> bool:
        """Check if the algorithm has converged.

        Args:
            evaluations: Current evaluation results

        Returns:
            True if converged, False otherwise
        """
        pass

    def optimize(self, fitness_function: Callable) -> OptimizationResult:
        """Run the optimization algorithm.

        Args:
            fitness_function: Function to optimize

        Returns:
            Optimization result
        """
        import time

        start_time = time.time()

        try:
            self.status = OptimizationStatus.IN_PROGRESS

            # Initialize population
            population = self.initialize_population()
            logger.info(f"Initialized population with {len(population)} individuals")

            # Main optimization loop
            for generation in range(self.config.max_generations):
                self.current_generation = generation

                # Evaluate population
                evaluations = self.evaluate_population(population, fitness_function)
                self.current_evaluations += len(evaluations)

                # Update convergence history
                best_fitness = self._get_best_fitness(evaluations)
                self.convergence_history.append(best_fitness)

                if self.config.verbose and generation % 10 == 0:
                    logger.info(f"Generation {generation}: Best fitness = {best_fitness:.6f}")

                # Check termination criteria
                if self._should_terminate(evaluations, start_time):
                    break

                # Update population for next generation
                population = self.update_population(population, evaluations)

            # Create final result
            result = self._create_result(population, evaluations, start_time)

            if self.status == OptimizationStatus.IN_PROGRESS:
                if self.check_convergence(evaluations):
                    self.status = OptimizationStatus.CONVERGED
                else:
                    self.status = OptimizationStatus.MAX_ITERATIONS

            result.status = self.status
            logger.info(f"Optimization completed with status: {self.status}")

            return result

        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            self.status = OptimizationStatus.ERROR

            return OptimizationResult(
                status=OptimizationStatus.ERROR,
                execution_time=time.time() - start_time,
                iterations=self.current_generation,
                evaluations=self.current_evaluations,
                metadata={"error": str(e)}
            )

    def _get_best_fitness(self, evaluations: List[Dict[str, Any]]) -> float:
        """Get the best fitness from current evaluations.

        Args:
            evaluations: Current evaluation results

        Returns:
            Best fitness value
        """
        if not evaluations:
            return float("inf")

        # For single objective, return minimum
        if len(self.config.objectives) == 1:
            fitnesses = [eval_result.get("fitness", float("inf")) for eval_result in evaluations]
            return min(fitnesses)
        else:
            # For multi-objective, return hypervolume or other metric
            # For now, return average of all objectives
            avg_objectives = []
            for eval_result in evaluations:
                objectives = eval_result.get("objectives", [])
                if objectives:
                    avg_objectives.append(np.mean(objectives))

            return min(avg_objectives) if avg_objectives else float("inf")

    def _should_terminate(self, evaluations: List[Dict[str, Any]], start_time: float) -> bool:
        """Check if optimization should terminate.

        Args:
            evaluations: Current evaluation results
            start_time: Optimization start time

        Returns:
            True if should terminate
        """
        # Check convergence
        if self.check_convergence(evaluations):
            self.status = OptimizationStatus.CONVERGED
            return True

        # Check maximum evaluations
        if self.config.max_evaluations and self.current_evaluations >= self.config.max_evaluations:
            return True

        # Check time limit
        if self.config.time_limit and time.time() - start_time >= self.config.time_limit:
            self.status = OptimizationStatus.TERMINATED
            return True

        # Check target fitness
        if self.config.target_fitness:
            best_fitness = self._get_best_fitness(evaluations)
            if best_fitness <= self.config.target_fitness:
                self.status = OptimizationStatus.CONVERGED
                return True

        return False

    def _create_result(
        self,
        population: np.ndarray,
        evaluations: List[Dict[str, Any]],
        start_time: float
    ) -> OptimizationResult:
        """Create optimization result.

        Args:
            population: Final population
            evaluations: Final evaluations
            start_time: Optimization start time

        Returns:
            Optimization result
        """
        if not evaluations:
            return OptimizationResult(
                status=self.status,
                execution_time=time.time() - start_time,
                iterations=self.current_generation,
                evaluations=self.current_evaluations
            )

        # Find best solution
        if len(self.config.objectives) == 1:
            # Single objective - find minimum
            best_idx = min(
                range(len(evaluations)),
                key=lambda i: evaluations[i].get("fitness", float("inf"))
            )

            return OptimizationResult(
                best_solution=population[best_idx],
                best_fitness=evaluations[best_idx].get("fitness"),
                best_objectives=evaluations[best_idx].get("objectives"),
                convergence_history=self.convergence_history,
                status=self.status,
                iterations=self.current_generation,
                evaluations=self.current_evaluations,
                execution_time=time.time() - start_time,
                metadata={
                    "final_population_size": len(population),
                    "convergence_generations": len(self.convergence_history)
                }
            )
        else:
            # Multi-objective - return Pareto front
            pareto_indices = self._find_pareto_front(evaluations)
            pareto_solutions = [population[i] for i in pareto_indices]
            pareto_objectives = [evaluations[i].get("objectives", []) for i in pareto_indices]

            # Best solution is the one with minimum distance to ideal point
            best_idx = self._find_best_compromise_solution(evaluations, pareto_indices)

            return OptimizationResult(
                best_solution=population[best_idx] if best_idx is not None else None,
                best_fitness=(evaluations[best_idx].get("fitness") if best_idx is not None else None),
                best_objectives=(evaluations[best_idx].get("objectives") if best_idx is not None else None),
                pareto_front=pareto_solutions,
                pareto_objectives=pareto_objectives,
                convergence_history=self.convergence_history,
                status=self.status,
                iterations=self.current_generation,
                evaluations=self.current_evaluations,
                execution_time=time.time() - start_time,
                metadata={
                    "pareto_front_size": len(pareto_solutions),
                    "final_population_size": len(population)
                }
            )

    def _find_pareto_front(self, evaluations: List[Dict[str, Any]]) -> List[int]:
        """Find Pareto front indices from evaluations.

        Args:
            evaluations: Evaluation results

        Returns:
            List of indices belonging to Pareto front
        """
        objectives_list = []
        valid_indices = []

        for i, eval_result in enumerate(evaluations):
            objectives = eval_result.get("objectives")
            if objectives and all(obj is not None for obj in objectives):
                objectives_list.append(objectives)
                valid_indices.append(i)

        if not objectives_list:
            return []

        objectives_array = np.array(objectives_list)
        pareto_indices = []

        for i in range(len(objectives_array)):
            is_dominated = False

            for j in range(len(objectives_array)):
                if i != j:
                    # Check if j dominates i (assuming minimization)
                    if np.all(objectives_array[j] <= objectives_array[i]) and np.any(
                        objectives_array[j] < objectives_array[i]
                    ):
                        is_dominated = True
                        break

            if not is_dominated:
                pareto_indices.append(valid_indices[i])

        return pareto_indices

    def _find_best_compromise_solution(
        self, evaluations: List[Dict[str, Any]], pareto_indices: List[int]
    ) -> int | None:
        """Find best compromise solution from Pareto front.

        Args:
            evaluations: Evaluation results
            pareto_indices: Indices of Pareto front solutions

        Returns:
            Index of best compromise solution
        """
        if not pareto_indices:
            return None

        # Calculate ideal and nadir points
        pareto_objectives = []
        for idx in pareto_indices:
            objectives = evaluations[idx].get("objectives")
            if objectives:
                pareto_objectives.append(objectives)

        if not pareto_objectives:
            return pareto_indices[0]

        objectives_array = np.array(pareto_objectives)
        ideal_point = np.min(objectives_array, axis=0)
        nadir_point = np.max(objectives_array, axis=0)

        # Normalize objectives
        range_values = nadir_point - ideal_point
        range_values[range_values == 0] = 1  # Avoid division by zero

        normalized_objectives = (objectives_array - ideal_point) / range_values

        # Find solution closest to origin (compromise solution)
        distances = np.linalg.norm(normalized_objectives, axis=1)
        best_pareto_idx = np.argmin(distances)

        return pareto_indices[best_pareto_idx]

    def validate_bounds(self, population: np.ndarray) -> np.ndarray:
        """Ensure population stays within bounds.

        Args:
            population: Population to validate

        Returns:
            Population with bounds enforced
        """
        bounded_population = population.copy()

        for i, (lower, upper) in enumerate(self.config.bounds):
            bounded_population[:, i] = np.clip(bounded_population[:, i], lower, upper)

        return bounded_population
