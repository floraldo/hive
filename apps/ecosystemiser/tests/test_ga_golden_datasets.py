"""
Golden Dataset Tests for Genetic Algorithm Validation

This module validates the NSGA-II genetic algorithm implementation against
canonical test functions with known Pareto frontiers from the multi-objective
optimization literature.

References:
- Deb et al. (2002): NSGA-II algorithm paper
- Zitzler et al. (2000): ZDT test problems
- Schaffer (1985): Schaffer function definitions
"""

import pytest
import numpy as np
from pathlib import Path
import json
from typing import List, Tuple, Dict, Any
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist

# Add source directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ecosystemiser.discovery.algorithms.genetic_algorithm import (
    GeneticAlgorithm, NSGAIIOptimizer, GeneticAlgorithmConfig
)


class TestFunctions:
    """Collection of canonical multi-objective test functions."""

    @staticmethod
    def schaffer_n1(x: np.ndarray) -> np.ndarray:
        """
        Schaffer Function N.1 - Simple 2-objective test problem.

        Minimize: f1(x) = x^2
        Minimize: f2(x) = (x-2)^2

        Pareto front: x in [0, 2]
        """
        x = x[0]  # Single variable
        f1 = x**2
        f2 = (x - 2)**2
        return np.array([f1, f2])

    @staticmethod
    def zdt1(x: np.ndarray) -> np.ndarray:
        """
        ZDT1 - Convex Pareto front test problem.

        n = 30 variables
        Pareto front: convex, f2 = 1 - sqrt(f1)
        """
        n = len(x)
        f1 = x[0]
        g = 1 + 9 * np.sum(x[1:]) / (n - 1)
        f2 = g * (1 - np.sqrt(f1 / g))
        return np.array([f1, f2])

    @staticmethod
    def zdt2(x: np.ndarray) -> np.ndarray:
        """
        ZDT2 - Non-convex Pareto front test problem.

        n = 30 variables
        Pareto front: non-convex, f2 = 1 - f1^2
        """
        n = len(x)
        f1 = x[0]
        g = 1 + 9 * np.sum(x[1:]) / (n - 1)
        f2 = g * (1 - (f1 / g)**2)
        return np.array([f1, f2])

    @staticmethod
    def zdt3(x: np.ndarray) -> np.ndarray:
        """
        ZDT3 - Disconnected Pareto front test problem.

        n = 30 variables
        Pareto front: disconnected regions
        """
        n = len(x)
        f1 = x[0]
        g = 1 + 9 * np.sum(x[1:]) / (n - 1)
        f2 = g * (1 - np.sqrt(f1 / g) - (f1 / g) * np.sin(10 * np.pi * f1))
        return np.array([f1, f2])

    @staticmethod
    def kursawe(x: np.ndarray) -> np.ndarray:
        """
        Kursawe Function - Non-convex, disconnected Pareto front.

        n = 3 variables
        Complex Pareto front with multiple segments
        """
        n = len(x)
        f1 = np.sum(-10 * np.exp(-0.2 * np.sqrt(x[:-1]**2 + x[1:]**2)))
        f2 = np.sum(np.abs(x)**0.8 + 5 * np.sin(x**3))
        return np.array([f1, f2])

    @staticmethod
    def get_true_pareto_front(problem: str, n_points: int = 100) -> np.ndarray:
        """Get analytical Pareto front for validation."""
        if problem == "schaffer_n1":
            # Pareto front: x in [0, 2]
            x = np.linspace(0, 2, n_points)
            f1 = x**2
            f2 = (x - 2)**2
            return np.column_stack([f1, f2])

        elif problem == "zdt1":
            # Pareto front: f2 = 1 - sqrt(f1), f1 in [0, 1]
            f1 = np.linspace(0, 1, n_points)
            f2 = 1 - np.sqrt(f1)
            return np.column_stack([f1, f2])

        elif problem == "zdt2":
            # Pareto front: f2 = 1 - f1^2, f1 in [0, 1]
            f1 = np.linspace(0, 1, n_points)
            f2 = 1 - f1**2
            return np.column_stack([f1, f2])

        elif problem == "zdt3":
            # Pareto front: disconnected segments
            f1 = np.linspace(0, 0.852, n_points)
            # Complex formula for ZDT3 Pareto front
            valid_regions = [
                (0.0, 0.0830015349),
                (0.182228780, 0.2577623634),
                (0.4093136748, 0.4538821041),
                (0.6183967944, 0.6525117038),
                (0.8233317983, 0.8518328654)
            ]

            points = []
            for start, end in valid_regions:
                mask = (f1 >= start) & (f1 <= end)
                f1_region = f1[mask]
                if len(f1_region) > 0:
                    f2_region = 1 - np.sqrt(f1_region) - f1_region * np.sin(10 * np.pi * f1_region)
                    points.extend(zip(f1_region, f2_region))

            return np.array(points) if points else np.empty((0, 2))

        else:
            # For Kursawe and others, return None (no analytical solution)
            return None


class TestGeneticAlgorithmGoldenDatasets:
    """Test GA implementation against canonical problems."""

    def calculate_igd(self, obtained_front: np.ndarray, true_front: np.ndarray) -> float:
        """
        Calculate Inverted Generational Distance (IGD) metric.

        Lower is better, 0 means perfect convergence.
        """
        if len(obtained_front) == 0 or len(true_front) == 0:
            return float('inf')

        # Calculate minimum distance from each true point to obtained front
        distances = cdist(true_front, obtained_front)
        min_distances = np.min(distances, axis=1)
        return np.mean(min_distances)

    def calculate_hypervolume(self, front: np.ndarray, reference_point: np.ndarray) -> float:
        """
        Calculate hypervolume indicator (simplified 2D version).

        Higher is better.
        """
        if len(front) == 0:
            return 0.0

        # Sort by first objective
        sorted_front = front[front[:, 0].argsort()]

        hypervolume = 0.0
        prev_x = 0.0

        for point in sorted_front:
            if point[0] < reference_point[0] and point[1] < reference_point[1]:
                width = point[0] - prev_x
                height = reference_point[1] - point[1]
                hypervolume += width * height
                prev_x = point[0]

        # Add final rectangle
        if prev_x < reference_point[0]:
            hypervolume += (reference_point[0] - prev_x) * reference_point[1]

        return hypervolume

    def test_schaffer_n1_convergence(self):
        """Test NSGA-II on Schaffer N.1 function."""
        # Configure GA for Schaffer N.1
        config = GeneticAlgorithmConfig(
            dimensions=1,
            bounds=[(0, 4)],
            population_size=50,
            max_generations=100,
            objectives=['f1', 'f2'],
            mutation_rate=0.1,
            crossover_rate=0.9
        )

        # Create optimizer
        optimizer = NSGAIIOptimizer(config)

        # Define fitness function wrapper
        def fitness_function(x):
            objectives = TestFunctions.schaffer_n1(x)
            return {
                'objectives': objectives,
                'fitness': np.sum(objectives),  # For single-objective fallback
                'valid': True
            }

        # Run optimization
        result = optimizer.optimize(fitness_function)

        # Get Pareto front from result
        pareto_front = result.get('pareto_objectives', [])
        if len(pareto_front) == 0:
            pareto_front = result.get('pareto_front', [])

        # Convert to numpy array
        obtained_front = np.array(pareto_front) if pareto_front else np.empty((0, 2))

        # Get true Pareto front
        true_front = TestFunctions.get_true_pareto_front('schaffer_n1')

        # Calculate quality metrics
        igd = self.calculate_igd(obtained_front, true_front)

        # Validate convergence (IGD should be small)
        assert igd < 0.1, f"Poor convergence on Schaffer N.1: IGD = {igd:.4f}"

        # Check that we found diverse solutions
        assert len(obtained_front) >= 10, f"Insufficient diversity: only {len(obtained_front)} solutions"

    def test_zdt1_convergence(self):
        """Test NSGA-II on ZDT1 (convex Pareto front)."""
        # Configure GA for ZDT1
        config = GeneticAlgorithmConfig(
            dimensions=30,
            bounds=[(0, 1)] * 30,
            population_size=100,
            max_generations=250,
            objectives=['f1', 'f2'],
            mutation_rate=1/30,  # 1/n as recommended
            crossover_rate=0.9,
            mutation_strength=0.1
        )

        # Create optimizer
        optimizer = NSGAIIOptimizer(config)

        # Define fitness function wrapper
        def fitness_function(x):
            objectives = TestFunctions.zdt1(x)
            return {
                'objectives': objectives,
                'fitness': np.sum(objectives),
                'valid': True
            }

        # Run optimization
        result = optimizer.optimize(fitness_function)

        # Get Pareto front
        pareto_front = result.get('pareto_objectives', [])
        obtained_front = np.array(pareto_front) if pareto_front else np.empty((0, 2))

        # Get true Pareto front
        true_front = TestFunctions.get_true_pareto_front('zdt1')

        # Calculate metrics
        igd = self.calculate_igd(obtained_front, true_front)
        hypervolume = self.calculate_hypervolume(obtained_front, np.array([1.1, 1.1]))
        true_hypervolume = self.calculate_hypervolume(true_front, np.array([1.1, 1.1]))

        # Validate convergence
        assert igd < 0.05, f"Poor convergence on ZDT1: IGD = {igd:.4f}"

        # Validate hypervolume (should be close to true value)
        hv_ratio = hypervolume / true_hypervolume if true_hypervolume > 0 else 0
        assert hv_ratio > 0.95, f"Poor hypervolume on ZDT1: {hv_ratio:.2%} of optimal"

    def test_zdt2_nonconvex(self):
        """Test NSGA-II on ZDT2 (non-convex Pareto front)."""
        config = GeneticAlgorithmConfig(
            dimensions=30,
            bounds=[(0, 1)] * 30,
            population_size=100,
            max_generations=250,
            objectives=['f1', 'f2'],
            mutation_rate=1/30,
            crossover_rate=0.9
        )

        optimizer = NSGAIIOptimizer(config)

        def fitness_function(x):
            objectives = TestFunctions.zdt2(x)
            return {
                'objectives': objectives,
                'fitness': np.sum(objectives),
                'valid': True
            }

        result = optimizer.optimize(fitness_function)

        pareto_front = result.get('pareto_objectives', [])
        obtained_front = np.array(pareto_front) if pareto_front else np.empty((0, 2))

        true_front = TestFunctions.get_true_pareto_front('zdt2')

        igd = self.calculate_igd(obtained_front, true_front)

        # Non-convex problems are harder, allow slightly higher IGD
        assert igd < 0.08, f"Poor convergence on ZDT2: IGD = {igd:.4f}"

    def test_diversity_preservation(self):
        """Test that NSGA-II maintains diversity along Pareto front."""
        config = GeneticAlgorithmConfig(
            dimensions=1,
            bounds=[(0, 4)],
            population_size=50,
            max_generations=100,
            objectives=['f1', 'f2'],
            diversity_preservation=True,
            crowding_factor=2.0
        )

        optimizer = NSGAIIOptimizer(config)

        def fitness_function(x):
            objectives = TestFunctions.schaffer_n1(x)
            return {
                'objectives': objectives,
                'fitness': np.sum(objectives),
                'valid': True
            }

        result = optimizer.optimize(fitness_function)

        pareto_front = result.get('pareto_objectives', [])
        obtained_front = np.array(pareto_front) if pareto_front else np.empty((0, 2))

        # Check diversity: solutions should be spread along front
        if len(obtained_front) > 1:
            # Sort by first objective
            sorted_front = obtained_front[obtained_front[:, 0].argsort()]

            # Calculate spacing between consecutive solutions
            spacings = np.diff(sorted_front[:, 0])

            # Check that spacing is relatively uniform (low variance)
            if len(spacings) > 0:
                spacing_cv = np.std(spacings) / (np.mean(spacings) + 1e-10)
                assert spacing_cv < 1.0, f"Poor diversity: spacing CV = {spacing_cv:.2f}"

    def test_convergence_metrics(self):
        """Test that convergence metrics are properly tracked."""
        config = GeneticAlgorithmConfig(
            dimensions=1,
            bounds=[(0, 4)],
            population_size=20,
            max_generations=50,
            objectives=['f1', 'f2']
        )

        optimizer = NSGAIIOptimizer(config)

        def fitness_function(x):
            objectives = TestFunctions.schaffer_n1(x)
            return {
                'objectives': objectives,
                'fitness': np.sum(objectives),
                'valid': True
            }

        result = optimizer.optimize(fitness_function)

        # Verify convergence history exists
        assert 'convergence_history' in result, "Missing convergence history"
        history = result['convergence_history']
        assert len(history) > 0, "Empty convergence history"

        # Check that fitness generally improves (decreases for minimization)
        if len(history) > 10:
            early_avg = np.mean(history[:5])
            late_avg = np.mean(history[-5:])
            assert late_avg <= early_avg, "No improvement in fitness over generations"

        # Verify other metrics
        assert 'num_evaluations' in result, "Missing evaluation count"
        assert 'final_population' in result, "Missing final population"
        assert result['num_evaluations'] > 0, "No evaluations performed"

    def test_pareto_dominance(self):
        """Test that Pareto dominance is correctly identified."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 1)] * 2,
            objectives=['f1', 'f2']
        )

        optimizer = NSGAIIOptimizer(config)

        # Test dominance relationships
        # For minimization: [1, 1] dominates [2, 2]
        assert optimizer._dominates(np.array([1, 1]), np.array([2, 2])) == True
        assert optimizer._dominates(np.array([2, 2]), np.array([1, 1])) == False

        # Non-dominated solutions
        assert optimizer._dominates(np.array([1, 2]), np.array([2, 1])) == False
        assert optimizer._dominates(np.array([2, 1]), np.array([1, 2])) == False

        # Equal solutions don't dominate
        assert optimizer._dominates(np.array([1, 1]), np.array([1, 1])) == False

    def save_validation_results(self, test_name: str, metrics: Dict[str, Any]):
        """Save validation results for reporting."""
        results_dir = Path("tests/validation_results")
        results_dir.mkdir(exist_ok=True)

        results_file = results_dir / f"ga_{test_name}_results.json"

        with open(results_file, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)

    def generate_pareto_plot(self, obtained_front: np.ndarray, true_front: np.ndarray,
                            test_name: str):
        """Generate visualization of obtained vs true Pareto front."""
        plt.figure(figsize=(10, 8))

        if true_front is not None and len(true_front) > 0:
            plt.plot(true_front[:, 0], true_front[:, 1], 'b-',
                    label='True Pareto Front', linewidth=2)

        if len(obtained_front) > 0:
            plt.scatter(obtained_front[:, 0], obtained_front[:, 1],
                       c='r', marker='o', s=50, label='NSGA-II Solutions')

        plt.xlabel('Objective 1', fontsize=12)
        plt.ylabel('Objective 2', fontsize=12)
        plt.title(f'Pareto Front Validation: {test_name}', fontsize=14)
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Save plot
        plots_dir = Path("tests/validation_plots")
        plots_dir.mkdir(exist_ok=True)
        plt.savefig(plots_dir / f"ga_{test_name}_pareto.png", dpi=300, bbox_inches='tight')
        plt.close()


class TestGANumericalAccuracy:
    """Test numerical accuracy of GA operations."""

    def test_crossover_bounds_compliance(self):
        """Test that crossover respects variable bounds."""
        config = GeneticAlgorithmConfig(
            dimensions=5,
            bounds=[(0, 10), (-5, 5), (100, 200), (-1, 1), (0, 1)],
            crossover_method='sbx'
        )

        ga = GeneticAlgorithm(config)

        # Test multiple crossover operations
        for _ in range(100):
            parent1 = np.array([5, 0, 150, 0, 0.5])
            parent2 = np.array([7, -2, 180, -0.5, 0.8])

            offspring1, offspring2 = ga._crossover(parent1, parent2)

            # Check bounds compliance
            for i, (lower, upper) in enumerate(config.bounds):
                assert lower <= offspring1[i] <= upper, \
                    f"Offspring1 violates bounds at dim {i}: {offspring1[i]} not in [{lower}, {upper}]"
                assert lower <= offspring2[i] <= upper, \
                    f"Offspring2 violates bounds at dim {i}: {offspring2[i]} not in [{lower}, {upper}]"

    def test_mutation_distribution(self):
        """Test that mutation follows expected distribution."""
        config = GeneticAlgorithmConfig(
            dimensions=1,
            bounds=[(0, 100)],
            mutation_rate=1.0,  # Always mutate for testing
            mutation_strength=0.1,
            mutation_method='polynomial'
        )

        ga = GeneticAlgorithm(config)

        # Collect mutation results
        original = np.array([50])  # Middle of range
        mutations = []

        for _ in range(1000):
            mutated = ga._mutate(original.copy())
            mutations.append(mutated[0])

        mutations = np.array(mutations)

        # Check that mutations are centered around original
        mean_mutation = np.mean(mutations)
        assert abs(mean_mutation - 50) < 5, \
            f"Mutation bias detected: mean = {mean_mutation:.2f}, expected ~50"

        # Check that mutations have reasonable spread
        std_mutation = np.std(mutations)
        assert 5 < std_mutation < 30, \
            f"Unexpected mutation spread: std = {std_mutation:.2f}"

    def test_selection_pressure(self):
        """Test that selection properly favors better solutions."""
        config = GeneticAlgorithmConfig(
            dimensions=1,
            bounds=[(0, 10)],
            population_size=10,
            tournament_size=3,
            selection_method='tournament'
        )

        ga = GeneticAlgorithm(config)

        # Create population with clear fitness gradient
        population = np.linspace(0, 10, 10).reshape(-1, 1)
        fitness = np.arange(10)  # Lower is better

        # Perform many selections
        selected_indices = []
        for _ in range(1000):
            selected = ga._selection(population, fitness)
            # Find which individuals were selected
            for individual in selected:
                idx = np.where((population == individual).all(axis=1))[0][0]
                selected_indices.append(idx)

        # Better individuals (lower indices) should be selected more often
        selection_counts = np.bincount(selected_indices, minlength=10)

        # Check that selection pressure exists (monotonic decrease expected)
        for i in range(len(selection_counts) - 1):
            # Allow some noise but general trend should be decreasing
            if i < 5:  # Stronger expectation for clearly better solutions
                assert selection_counts[i] >= selection_counts[i+5], \
                    f"Selection pressure violation: worse solution selected more"


# Main test execution
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])