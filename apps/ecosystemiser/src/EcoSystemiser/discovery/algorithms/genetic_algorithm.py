"""NSGA-II genetic algorithm implementation for multi-objective optimization."""

import copy
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from ecosystemiser.discovery.algorithms.base import (
    BaseOptimizationAlgorithm,
    OptimizationConfig,
    OptimizationResult,
)
from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class GeneticAlgorithmConfig(OptimizationConfig):
    """Extended configuration for genetic algorithms."""

    # Genetic operators
    mutation_rate: float = 0.1
    mutation_strength: float = 0.2
    crossover_rate: float = 0.9
    tournament_size: int = 3
    elitism_ratio: float = 0.1

    # Selection methods
    selection_method: str = "tournament"  # tournament, roulette, rank
    crossover_method: str = "sbx"  # sbx, uniform, arithmetic
    mutation_method: str = "polynomial"  # polynomial, uniform, gaussian

    # NSGA-II specific
    crowding_factor: float = 2.0
    diversity_preservation: bool = True


class GeneticAlgorithm(BaseOptimizationAlgorithm):
    """Single-objective genetic algorithm implementation.

    Implements a standard genetic algorithm with tournament selection,
    simulated binary crossover, and polynomial mutation.
    """

    def __init__(self, config: GeneticAlgorithmConfig):
        """Initialize genetic algorithm.

        Args:
            config: Genetic algorithm configuration
        """
        super().__init__(config)
        self.ga_config = config

        # Validate configuration
        if not 0 <= config.mutation_rate <= 1:
            raise ValueError("Mutation rate must be between 0 and 1")
        if not 0 <= config.crossover_rate <= 1:
            raise ValueError("Crossover rate must be between 0 and 1")
        if config.tournament_size < 1:
            raise ValueError("Tournament size must be at least 1")

    def initialize_population(self) -> np.ndarray:
        """Initialize random population within bounds."""
        population = np.random.random(
            (self.config.population_size, self.config.dimensions)
        )

        # Scale to bounds
        for i, (lower, upper) in enumerate(self.config.bounds):
            population[:, i] = lower + population[:, i] * (upper - lower)

        # Ensure bounds compliance
        population = self.validate_bounds(population)

        logger.info(f"Initialized population of {len(population)} individuals")
        return population

    def evaluate_population(
        self, population: np.ndarray, fitness_function: Callable
    ) -> List[Dict[str, Any]]:
        """Evaluate fitness of population."""
        evaluations = []

        if self.config.parallel_evaluation and self.config.max_workers > 1:
            # Parallel evaluation
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = [
                    executor.submit(fitness_function, individual)
                    for individual in population
                ]

                for future in futures:
                    try:
                        result = future.result()
                        evaluations.append(result)
                    except Exception as e:
                        logger.warning(f"Evaluation failed: {e}")
                        evaluations.append(
                            {
                                "fitness": float("inf"),
                                "objectives": [float("inf")]
                                * len(self.config.objectives),
                                "valid": False,
                                "error": str(e),
                            }
                        )
        else:
            # Sequential evaluation
            for individual in population:
                try:
                    result = fitness_function(individual)
                    evaluations.append(result)
                except Exception as e:
                    logger.warning(f"Evaluation failed: {e}")
                    evaluations.append(
                        {
                            "fitness": float("inf"),
                            "objectives": [float("inf")] * len(self.config.objectives),
                            "valid": False,
                            "error": str(e),
                        }
                    )

        return evaluations

    def update_population(
        self, population: np.ndarray, evaluations: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Update population using genetic operators."""
        # Selection
        parent_indices = self._selection(evaluations)
        parents = population[parent_indices]

        # Create offspring through crossover and mutation
        offspring = self._create_offspring(parents)

        # Ensure bounds compliance
        offspring = self.validate_bounds(offspring)

        # Combine parents and offspring for replacement
        combined_population = np.vstack([population, offspring])
        combined_evaluations = evaluations + self.evaluate_population(
            offspring, lambda x: {"fitness": 0}
        )

        # Environmental selection (keep best individuals)
        survivor_indices = self._environmental_selection(
            combined_population, combined_evaluations
        )

        return combined_population[survivor_indices]

    def _selection(self, evaluations: List[Dict[str, Any]]) -> np.ndarray:
        """Select parents for reproduction."""
        if self.ga_config.selection_method == "tournament":
            return self._tournament_selection(evaluations)
        elif self.ga_config.selection_method == "roulette":
            return self._roulette_selection(evaluations)
        else:
            return self._rank_selection(evaluations)

    def _tournament_selection(self, evaluations: List[Dict[str, Any]]) -> np.ndarray:
        """Tournament selection for parent selection."""
        selected_indices = []
        population_size = len(evaluations)

        for _ in range(self.config.population_size):
            # Select random individuals for tournament
            tournament_indices = np.random.choice(
                population_size,
                size=min(self.ga_config.tournament_size, population_size),
                replace=False,
            )

            # Find best in tournament (lowest fitness for minimization)
            tournament_fitness = [
                evaluations[i].get("fitness", float("inf")) for i in tournament_indices
            ]
            winner_idx = tournament_indices[np.argmin(tournament_fitness)]
            selected_indices.append(winner_idx)

        return np.array(selected_indices)

    def _roulette_selection(self, evaluations: List[Dict[str, Any]]) -> np.ndarray:
        """Roulette wheel selection."""
        fitness_values = np.array(
            [eval_result.get("fitness", float("inf")) for eval_result in evaluations]
        )

        # Convert to probabilities (invert for minimization)
        if np.all(np.isfinite(fitness_values)):
            max_fitness = np.max(fitness_values)
            probabilities = max_fitness - fitness_values + 1e-10
            probabilities = probabilities / np.sum(probabilities)
        else:
            # Uniform selection if all fitness values are infinite
            probabilities = np.ones(len(evaluations)) / len(evaluations)

        selected_indices = np.random.choice(
            len(evaluations),
            size=self.config.population_size,
            p=probabilities,
            replace=True,
        )

        return selected_indices

    def _rank_selection(self, evaluations: List[Dict[str, Any]]) -> np.ndarray:
        """Rank-based selection."""
        fitness_values = np.array(
            [eval_result.get("fitness", float("inf")) for eval_result in evaluations]
        )

        # Rank individuals (best rank = 0)
        ranks = np.argsort(np.argsort(fitness_values))

        # Convert ranks to selection probabilities
        probabilities = (len(evaluations) - ranks) / np.sum(
            np.arange(1, len(evaluations) + 1)
        )

        selected_indices = np.random.choice(
            len(evaluations),
            size=self.config.population_size,
            p=probabilities,
            replace=True,
        )

        return selected_indices

    def _create_offspring(self, parents: np.ndarray) -> np.ndarray:
        """Create offspring through crossover and mutation."""
        offspring = []

        for i in range(0, len(parents), 2):
            parent1 = parents[i]
            parent2 = parents[(i + 1) % len(parents)]

            # Crossover
            if np.random.random() < self.ga_config.crossover_rate:
                child1, child2 = self._crossover(parent1, parent2)
            else:
                child1, child2 = parent1.copy(), parent2.copy()

            # Mutation
            child1 = self._mutate(child1)
            child2 = self._mutate(child2)

            offspring.extend([child1, child2])

        # Trim to desired offspring size
        offspring = offspring[: self.config.population_size]

        return np.array(offspring)

    def _crossover(
        self, parent1: np.ndarray, parent2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Crossover operation between two parents."""
        if self.ga_config.crossover_method == "sbx":
            return self._simulated_binary_crossover(parent1, parent2)
        elif self.ga_config.crossover_method == "uniform":
            return self._uniform_crossover(parent1, parent2)
        else:
            return self._arithmetic_crossover(parent1, parent2)

    def _simulated_binary_crossover(
        self, parent1: np.ndarray, parent2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Simulated binary crossover (SBX)."""
        eta = 20.0  # Distribution index
        child1, child2 = parent1.copy(), parent2.copy()

        for i in range(len(parent1)):
            if np.random.random() <= 0.5:
                y1, y2 = min(parent1[i], parent2[i]), max(parent1[i], parent2[i])

                if abs(y2 - y1) > 1e-14:
                    # Calculate beta
                    rand = np.random.random()
                    if rand <= 0.5:
                        beta = (2 * rand) ** (1.0 / (eta + 1))
                    else:
                        beta = (1.0 / (2 * (1 - rand))) ** (1.0 / (eta + 1))

                    # Create children
                    child1[i] = 0.5 * ((y1 + y2) - beta * abs(y2 - y1))
                    child2[i] = 0.5 * ((y1 + y2) + beta * abs(y2 - y1))

        return child1, child2

    def _uniform_crossover(
        self, parent1: np.ndarray, parent2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Uniform crossover."""
        mask = np.random.random(len(parent1)) < 0.5
        child1 = np.where(mask, parent1, parent2)
        child2 = np.where(mask, parent2, parent1)
        return child1, child2

    def _arithmetic_crossover(
        self, parent1: np.ndarray, parent2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Arithmetic crossover."""
        alpha = np.random.random()
        child1 = alpha * parent1 + (1 - alpha) * parent2
        child2 = (1 - alpha) * parent1 + alpha * parent2
        return child1, child2

    def _mutate(self, individual: np.ndarray) -> np.ndarray:
        """Mutate individual."""
        if self.ga_config.mutation_method == "polynomial":
            return self._polynomial_mutation(individual)
        elif self.ga_config.mutation_method == "uniform":
            return self._uniform_mutation(individual)
        else:
            return self._gaussian_mutation(individual)

    def _polynomial_mutation(self, individual: np.ndarray) -> np.ndarray:
        """Polynomial mutation."""
        eta = 20.0  # Distribution index
        mutated = individual.copy()

        for i in range(len(individual)):
            if np.random.random() < self.ga_config.mutation_rate:
                lower, upper = self.config.bounds[i]

                delta1 = (individual[i] - lower) / (upper - lower)
                delta2 = (upper - individual[i]) / (upper - lower)

                rand = np.random.random()
                mut_pow = 1.0 / (eta + 1.0)

                if rand < 0.5:
                    xy = 1.0 - delta1
                    val = 2.0 * rand + (1.0 - 2.0 * rand) * (xy ** (eta + 1.0))
                    delta_q = val**mut_pow - 1.0
                else:
                    xy = 1.0 - delta2
                    val = 2.0 * (1.0 - rand) + 2.0 * (rand - 0.5) * (xy ** (eta + 1.0))
                    delta_q = 1.0 - val**mut_pow

                mutated[i] = individual[i] + delta_q * (upper - lower)

        return mutated

    def _uniform_mutation(self, individual: np.ndarray) -> np.ndarray:
        """Uniform mutation."""
        mutated = individual.copy()

        for i in range(len(individual)):
            if np.random.random() < self.ga_config.mutation_rate:
                lower, upper = self.config.bounds[i]
                mutated[i] = np.random.uniform(lower, upper)

        return mutated

    def _gaussian_mutation(self, individual: np.ndarray) -> np.ndarray:
        """Gaussian mutation."""
        mutated = individual.copy()

        for i in range(len(individual)):
            if np.random.random() < self.ga_config.mutation_rate:
                lower, upper = self.config.bounds[i]
                std = self.ga_config.mutation_strength * (upper - lower)
                mutated[i] += np.random.normal(0, std)

        return mutated

    def _environmental_selection(
        self, population: np.ndarray, evaluations: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Select survivors for next generation."""
        # Simple elitist selection for single-objective
        fitness_values = np.array(
            [eval_result.get("fitness", float("inf")) for eval_result in evaluations]
        )

        # Select best individuals
        sorted_indices = np.argsort(fitness_values)
        return sorted_indices[: self.config.population_size]

    def check_convergence(self, evaluations: List[Dict[str, Any]]) -> bool:
        """Check convergence based on fitness improvement."""
        if len(self.convergence_history) < self.config.convergence_patience:
            return False

        recent_fitness = self.convergence_history[-self.config.convergence_patience :]
        fitness_change = max(recent_fitness) - min(recent_fitness)

        return fitness_change < self.config.convergence_tolerance


class NSGAIIOptimizer(BaseOptimizationAlgorithm):
    """NSGA-II implementation for multi-objective optimization.

    Implements the Non-dominated Sorting Genetic Algorithm II (NSGA-II)
    for solving multi-objective optimization problems.
    """

    def __init__(self, config: GeneticAlgorithmConfig):
        """Initialize NSGA-II optimizer.

        Args:
            config: Genetic algorithm configuration
        """
        super().__init__(config)
        self.ga_config = config

        if len(config.objectives) < 2:
            raise ValueError("NSGA-II requires at least 2 objectives")

    def initialize_population(self) -> np.ndarray:
        """Initialize random population within bounds."""
        population = np.random.random(
            (self.config.population_size, self.config.dimensions)
        )

        # Scale to bounds
        for i, (lower, upper) in enumerate(self.config.bounds):
            population[:, i] = lower + population[:, i] * (upper - lower)

        population = self.validate_bounds(population)

        logger.info(f"Initialized NSGA-II population of {len(population)} individuals")
        return population

    def evaluate_population(
        self, population: np.ndarray, fitness_function: Callable
    ) -> List[Dict[str, Any]]:
        """Evaluate population objectives."""
        evaluations = []

        if self.config.parallel_evaluation and self.config.max_workers > 1:
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = [
                    executor.submit(fitness_function, individual)
                    for individual in population
                ]

                for future in futures:
                    try:
                        result = future.result()
                        # Ensure objectives are present
                        if "objectives" not in result:
                            result["objectives"] = [result.get("fitness", float("inf"))]
                        evaluations.append(result)
                    except Exception as e:
                        logger.warning(f"Evaluation failed: {e}")
                        evaluations.append(
                            {
                                "objectives": [float("inf")]
                                * len(self.config.objectives),
                                "valid": False,
                                "error": str(e),
                            }
                        )
        else:
            for individual in population:
                try:
                    result = fitness_function(individual)
                    if "objectives" not in result:
                        result["objectives"] = [result.get("fitness", float("inf"))]
                    evaluations.append(result)
                except Exception as e:
                    logger.warning(f"Evaluation failed: {e}")
                    evaluations.append(
                        {
                            "objectives": [float("inf")] * len(self.config.objectives),
                            "valid": False,
                            "error": str(e),
                        }
                    )

        return evaluations

    def update_population(
        self, population: np.ndarray, evaluations: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Update population using NSGA-II selection."""
        # Create offspring
        offspring = self._create_offspring_nsga2(population, evaluations)
        offspring = self.validate_bounds(offspring)

        # Evaluate offspring
        offspring_evaluations = self.evaluate_population(
            offspring, lambda x: {"objectives": [0] * len(self.config.objectives)}
        )

        # Combine parent and offspring populations
        combined_population = np.vstack([population, offspring])
        combined_evaluations = evaluations + offspring_evaluations

        # NSGA-II environmental selection
        survivor_indices = self._nsga2_selection(
            combined_population, combined_evaluations
        )

        return combined_population[survivor_indices]

    def _create_offspring_nsga2(
        self, population: np.ndarray, evaluations: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Create offspring using tournament selection and genetic operators."""
        offspring = []

        for _ in range(self.config.population_size // 2):
            # Tournament selection for parents
            parent1_idx = self._tournament_selection_nsga2(evaluations)
            parent2_idx = self._tournament_selection_nsga2(evaluations)

            parent1 = population[parent1_idx]
            parent2 = population[parent2_idx]

            # Crossover
            if np.random.random() < self.ga_config.crossover_rate:
                child1, child2 = self._simulated_binary_crossover(parent1, parent2)
            else:
                child1, child2 = parent1.copy(), parent2.copy()

            # Mutation
            child1 = self._polynomial_mutation(child1)
            child2 = self._polynomial_mutation(child2)

            offspring.extend([child1, child2])

        return np.array(offspring)

    def _tournament_selection_nsga2(self, evaluations: List[Dict[str, Any]]) -> int:
        """Tournament selection based on dominance and crowding distance."""
        tournament_size = min(self.ga_config.tournament_size, len(evaluations))
        tournament_indices = np.random.choice(
            len(evaluations), size=tournament_size, replace=False
        )

        # Find best individual in tournament
        best_idx = tournament_indices[0]

        for idx in tournament_indices[1:]:
            if self._dominates(evaluations[idx], evaluations[best_idx]):
                best_idx = idx
            elif not self._dominates(evaluations[best_idx], evaluations[idx]):
                # Both are non-dominated, use crowding distance
                if evaluations[idx].get("crowding_distance", 0) > evaluations[
                    best_idx
                ].get("crowding_distance", 0):
                    best_idx = idx

        return best_idx

    def _nsga2_selection(
        self, population: np.ndarray, evaluations: List[Dict[str, Any]]
    ) -> np.ndarray:
        """NSGA-II environmental selection with non-dominated sorting and crowding distance."""
        # Perform non-dominated sorting
        fronts = self._fast_non_dominated_sort(evaluations)

        # Calculate crowding distance for each front
        for front in fronts:
            self._calculate_crowding_distance(evaluations, front)

        # Select individuals for next generation
        selected_indices = []

        for front in fronts:
            if len(selected_indices) + len(front) <= self.config.population_size:
                # Include entire front
                selected_indices.extend(front)
            else:
                # Include part of front based on crowding distance
                remaining_slots = self.config.population_size - len(selected_indices)

                # Sort front by crowding distance (descending)
                front_with_distance = [
                    (idx, evaluations[idx].get("crowding_distance", 0)) for idx in front
                ]
                front_with_distance.sort(key=lambda x: x[1], reverse=True)

                selected_indices.extend(
                    [idx for idx, _ in front_with_distance[:remaining_slots]]
                )
                break

        return np.array(selected_indices)

    def _fast_non_dominated_sort(
        self, evaluations: List[Dict[str, Any]]
    ) -> List[List[int]]:
        """Fast non-dominated sorting algorithm."""
        n = len(evaluations)
        domination_count = [0] * n  # Number of individuals that dominate i
        dominated_set = [[] for _ in range(n)]  # Set of individuals that i dominates
        fronts = [[]]

        # Find first front and domination relationships
        for i in range(n):
            for j in range(n):
                if i != j:
                    if self._dominates(evaluations[i], evaluations[j]):
                        dominated_set[i].append(j)
                    elif self._dominates(evaluations[j], evaluations[i]):
                        domination_count[i] += 1

            if domination_count[i] == 0:
                fronts[0].append(i)

        # Find remaining fronts
        current_front = 0
        while len(fronts[current_front]) > 0:
            next_front = []

            for i in fronts[current_front]:
                for j in dominated_set[i]:
                    domination_count[j] -= 1
                    if domination_count[j] == 0:
                        next_front.append(j)

            if len(next_front) > 0:
                fronts.append(next_front)
                current_front += 1
            else:
                break

        return fronts

    def _dominates(self, eval_a: Dict[str, Any], eval_b: Dict[str, Any]) -> bool:
        """Check if solution A dominates solution B."""
        objectives_a = eval_a.get("objectives", [])
        objectives_b = eval_b.get("objectives", [])

        if len(objectives_a) != len(objectives_b):
            return False

        # Assuming minimization for all objectives
        at_least_one_better = False

        for obj_a, obj_b in zip(objectives_a, objectives_b):
            if obj_a > obj_b:  # A is worse in this objective
                return False
            elif obj_a < obj_b:  # A is better in this objective
                at_least_one_better = True

        return at_least_one_better

    def _calculate_crowding_distance(
        self, evaluations: List[Dict[str, Any]], front: List[int]
    ):
        """Calculate crowding distance for individuals in a front."""
        if len(front) <= 2:
            # Boundary solutions get infinite distance
            for idx in front:
                evaluations[idx]["crowding_distance"] = float("inf")
            return

        # Initialize distances
        for idx in front:
            evaluations[idx]["crowding_distance"] = 0

        num_objectives = len(evaluations[front[0]].get("objectives", []))

        for obj_idx in range(num_objectives):
            # Sort front by objective value
            front_with_obj = [
                (idx, evaluations[idx]["objectives"][obj_idx]) for idx in front
            ]
            front_with_obj.sort(key=lambda x: x[1])

            # Boundary solutions get infinite distance
            evaluations[front_with_obj[0][0]]["crowding_distance"] = float("inf")
            evaluations[front_with_obj[-1][0]]["crowding_distance"] = float("inf")

            # Calculate distance for middle solutions
            obj_range = front_with_obj[-1][1] - front_with_obj[0][1]
            if obj_range > 0:
                for i in range(1, len(front_with_obj) - 1):
                    idx = front_with_obj[i][0]
                    distance = (
                        front_with_obj[i + 1][1] - front_with_obj[i - 1][1]
                    ) / obj_range
                    evaluations[idx]["crowding_distance"] += distance

    def _simulated_binary_crossover(
        self, parent1: np.ndarray, parent2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Simulated binary crossover for real-valued variables."""
        eta = 20.0  # Distribution index
        child1, child2 = parent1.copy(), parent2.copy()

        for i in range(len(parent1)):
            if np.random.random() <= 0.5:
                lower, upper = self.config.bounds[i]

                if abs(parent1[i] - parent2[i]) > 1e-14:
                    y1, y2 = min(parent1[i], parent2[i]), max(parent1[i], parent2[i])

                    # Calculate beta
                    rand = np.random.random()
                    if rand <= 0.5:
                        beta = (2 * rand) ** (1.0 / (eta + 1))
                    else:
                        beta = (1.0 / (2 * (1 - rand))) ** (1.0 / (eta + 1))

                    # Create children
                    child1[i] = 0.5 * ((y1 + y2) - beta * abs(y2 - y1))
                    child2[i] = 0.5 * ((y1 + y2) + beta * abs(y2 - y1))

                    # Ensure bounds
                    child1[i] = np.clip(child1[i], lower, upper)
                    child2[i] = np.clip(child2[i], lower, upper)

        return child1, child2

    def _polynomial_mutation(self, individual: np.ndarray) -> np.ndarray:
        """Polynomial mutation for real-valued variables."""
        eta = 20.0  # Distribution index
        mutated = individual.copy()

        for i in range(len(individual)):
            if np.random.random() < self.ga_config.mutation_rate:
                lower, upper = self.config.bounds[i]

                delta1 = (individual[i] - lower) / (upper - lower)
                delta2 = (upper - individual[i]) / (upper - lower)

                rand = np.random.random()
                mut_pow = 1.0 / (eta + 1.0)

                if rand < 0.5:
                    xy = 1.0 - delta1
                    val = 2.0 * rand + (1.0 - 2.0 * rand) * (xy ** (eta + 1.0))
                    delta_q = val**mut_pow - 1.0
                else:
                    xy = 1.0 - delta2
                    val = 2.0 * (1.0 - rand) + 2.0 * (rand - 0.5) * (xy ** (eta + 1.0))
                    delta_q = 1.0 - val**mut_pow

                mutated[i] = individual[i] + delta_q * (upper - lower)
                mutated[i] = np.clip(mutated[i], lower, upper)

        return mutated

    def check_convergence(self, evaluations: List[Dict[str, Any]]) -> bool:
        """Check convergence based on hypervolume or front spread."""
        if len(self.convergence_history) < self.config.convergence_patience:
            return False

        # Simple convergence check based on average objective improvement
        if len(evaluations) == 0:
            return False

        current_avg_objectives = []
        for obj_idx in range(len(self.config.objectives)):
            obj_values = [
                eval_result.get("objectives", [float("inf")])[obj_idx]
                for eval_result in evaluations
                if len(eval_result.get("objectives", [])) > obj_idx
            ]
            if obj_values:
                current_avg_objectives.append(np.mean(obj_values))
            else:
                current_avg_objectives.append(float("inf"))

        current_metric = np.mean(current_avg_objectives)

        if len(self.convergence_history) >= self.config.convergence_patience:
            recent_history = self.convergence_history[
                -self.config.convergence_patience :
            ]
            improvement = max(recent_history) - min(recent_history)
            return improvement < self.config.convergence_tolerance

        return False
