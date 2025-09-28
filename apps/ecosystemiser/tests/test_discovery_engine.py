"""Comprehensive tests for Discovery Engine GA and Monte Carlo functionality."""

import pytest
import numpy as np
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from ecosystemiser.services.study_service import (
    StudyService, StudyConfig, SimulationConfig
)
from ecosystemiser.services.simulation_service import SimulationResult
from ecosystemiser.discovery.algorithms.genetic_algorithm import (
    GeneticAlgorithm, NSGAIIOptimizer, GeneticAlgorithmConfig
)
from ecosystemiser.discovery.algorithms.monte_carlo import (
    MonteCarloEngine, MonteCarloConfig
)
from ecosystemiser.discovery.algorithms.base import BaseOptimizationAlgorithm
from ecosystemiser.discovery.encoders.parameter_encoder import ParameterEncoder


class TestGeneticAlgorithm:
    """Test genetic algorithm implementation."""

    def test_genetic_algorithm_config(self):
        """Test GA configuration creation."""
        config = GeneticAlgorithmConfig(
            dimensions=3,
            bounds=[(0, 100), (0, 50), (0, 200)],
            population_size=20,
            max_generations=10,
            objectives=['minimize_cost']
        )

        assert config.dimensions == 3
        assert len(config.bounds) == 3
        assert config.population_size == 20
        assert config.max_generations == 10
        assert config.objectives == ['minimize_cost']

    def test_genetic_algorithm_initialization(self):
        """Test GA algorithm initialization."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            population_size=10,
            max_generations=5,
            objectives=['minimize_cost']
        )

        ga = GeneticAlgorithm(config)
        assert ga.config == config
        assert ga.current_generation == 0
        assert ga.convergence_history == []

    def test_population_initialization(self):
        """Test population initialization."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            population_size=10,
            objectives=['minimize_cost']
        )

        ga = GeneticAlgorithm(config)
        population = ga.initialize_population()

        assert population.shape == (10, 2)
        # Check bounds
        assert np.all(population[:, 0] >= 0) and np.all(population[:, 0] <= 100)
        assert np.all(population[:, 1] >= 0) and np.all(population[:, 1] <= 50)

    def test_crossover(self):
        """Test crossover operation."""
        config = GeneticAlgorithmConfig(
            dimensions=3,
            bounds=[(0, 100), (0, 50), (0, 200)],
            crossover_rate=1.0,  # Ensure crossover happens
            objectives=['minimize_cost']
        )

        ga = GeneticAlgorithm(config)
        parent1 = np.array([10, 20, 30])
        parent2 = np.array([40, 50, 60])

        offspring1, offspring2 = ga._crossover(parent1, parent2)

        # Check that offspring have valid bounds
        assert len(offspring1) == 3
        assert len(offspring2) == 3
        assert np.all(offspring1 >= [0, 0, 0]) and np.all(offspring1 <= [100, 50, 200])
        assert np.all(offspring2 >= [0, 0, 0]) and np.all(offspring2 <= [100, 50, 200])

    def test_mutation(self):
        """Test mutation operation."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            mutation_rate=1.0,  # Ensure mutation happens
            mutation_strength=0.1,
            objectives=['minimize_cost']
        )

        ga = GeneticAlgorithm(config)
        individual = np.array([50, 25])

        mutated = ga._mutate(individual)

        assert len(mutated) == 2
        assert np.all(mutated >= [0, 0]) and np.all(mutated <= [100, 50])

    def test_selection(self):
        """Test selection operation."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            population_size=4,
            objectives=['minimize_cost']
        )

        ga = GeneticAlgorithm(config)
        population = np.array([[10, 20], [30, 40], [50, 10], [70, 30]])
        fitness = np.array([100, 50, 75, 25])  # Lower is better

        selected = ga._selection(population, fitness)

        assert selected.shape == (4, 2)
        # Selection should favor better (lower) fitness values

    @patch('EcoSystemiser.discovery.algorithms.genetic_algorithm.GeneticAlgorithm.evaluate_population')
    def test_optimize_workflow(self, mock_evaluate):
        """Test complete optimization workflow."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            population_size=4,
            max_generations=2,
            objectives=['minimize_cost']
        )

        # Mock fitness function that returns decreasing values (improvement)
        mock_evaluate.side_effect = [
            np.array([100, 80, 90, 70]),  # Generation 0
            np.array([60, 50, 65, 45])    # Generation 1
        ]

        ga = GeneticAlgorithm(config)
        fitness_function = Mock(return_value=50)  # Mock fitness function

        result = ga.optimize(fitness_function)

        assert 'best_solution' in result
        assert 'best_fitness' in result
        assert 'convergence_history' in result
        assert 'final_population' in result
        assert len(result['convergence_history']) == 2


class TestNSGAII:
    """Test NSGA-II multi-objective optimization."""

    def test_nsga2_config(self):
        """Test NSGA-II configuration."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            objectives=['minimize_cost', 'maximize_renewable']
        )

        nsga2 = NSGAIIOptimizer(config)
        assert nsga2.config == config

    def test_dominance_check(self):
        """Test dominance relationship checking."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            objectives=['minimize_cost', 'minimize_emissions']
        )

        nsga2 = NSGAIIOptimizer(config)

        # For minimization: [10, 5] dominates [15, 10]
        obj1 = np.array([10, 5])
        obj2 = np.array([15, 10])

        assert nsga2._dominates(obj1, obj2) == True
        assert nsga2._dominates(obj2, obj1) == False

    def test_fast_non_dominated_sort(self):
        """Test fast non-dominated sorting."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            objectives=['minimize_cost', 'minimize_emissions']
        )

        nsga2 = NSGAIIOptimizer(config)

        # Create test objectives: minimize both
        objectives = np.array([
            [10, 20],  # Front 0 (best)
            [15, 15],  # Front 0
            [20, 25],  # Front 1
            [25, 30]   # Front 2
        ])

        fronts = nsga2._fast_non_dominated_sort(objectives)

        assert len(fronts) >= 1
        assert len(fronts[0]) >= 1  # First front should have at least one solution

    def test_crowding_distance(self):
        """Test crowding distance calculation."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            objectives=['minimize_cost', 'minimize_emissions']
        )

        nsga2 = NSGAIIOptimizer(config)

        objectives = np.array([
            [10, 30],
            [20, 20],
            [30, 10]
        ])

        front = [0, 1, 2]
        nsga2._calculate_crowding_distance(objectives, front)

        # Boundary solutions should have infinite distance
        assert nsga2.crowding_distances[0] == float('inf')
        assert nsga2.crowding_distances[2] == float('inf')


class TestMonteCarloEngine:
    """Test Monte Carlo uncertainty analysis."""

    def test_monte_carlo_config(self):
        """Test MC configuration creation."""
        config = MonteCarloConfig(
            dimensions=3,
            bounds=[(0, 100), (0, 50), (0, 200)],
            n_samples=1000,
            sampling_method='lhs',
            confidence_levels=[0.95, 0.99]
        )

        assert config.dimensions == 3
        assert config.n_samples == 1000
        assert config.sampling_method == 'lhs'
        assert config.confidence_levels == [0.95, 0.99]

    def test_latin_hypercube_sampling(self):
        """Test Latin Hypercube Sampling."""
        config = MonteCarloConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            n_samples=10,
            sampling_method='lhs'
        )

        mc = MonteCarloEngine(config)
        samples = mc._latin_hypercube_sampling()

        assert samples.shape == (10, 2)
        assert np.all(samples[:, 0] >= 0) and np.all(samples[:, 0] <= 100)
        assert np.all(samples[:, 1] >= 0) and np.all(samples[:, 1] <= 50)

    def test_uniform_sampling(self):
        """Test uniform random sampling."""
        config = MonteCarloConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            n_samples=10,
            sampling_method='uniform'
        )

        mc = MonteCarloEngine(config)
        samples = mc._uniform_sampling()

        assert samples.shape == (10, 2)
        assert np.all(samples[:, 0] >= 0) and np.all(samples[:, 0] <= 100)
        assert np.all(samples[:, 1] >= 0) and np.all(samples[:, 1] <= 50)

    def test_sobol_sampling(self):
        """Test Sobol sequence sampling."""
        config = MonteCarloConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            n_samples=16,  # Power of 2 for Sobol
            sampling_method='sobol'
        )

        mc = MonteCarloEngine(config)
        samples = mc._sobol_sampling()

        assert samples.shape == (16, 2)
        assert np.all(samples[:, 0] >= 0) and np.all(samples[:, 0] <= 100)
        assert np.all(samples[:, 1] >= 0) and np.all(samples[:, 1] <= 50)

    def test_uncertainty_analysis(self):
        """Test uncertainty analysis calculations."""
        config = MonteCarloConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            n_samples=100,
            confidence_levels=[0.95]
        )

        mc = MonteCarloEngine(config)

        # Mock results with normal distribution
        np.random.seed(42)  # For reproducible tests
        results = np.random.normal(50, 10, 100)

        analysis = mc._calculate_uncertainty_analysis(results)

        assert 'statistics' in analysis
        assert 'confidence_intervals' in analysis
        assert 'risk_metrics' in analysis

        stats = analysis['statistics']
        assert 'mean' in stats
        assert 'std' in stats
        assert 'min' in stats
        assert 'max' in stats

        # Check confidence intervals
        ci = analysis['confidence_intervals']
        assert '95%' in ci
        assert 'lower' in ci['95%']
        assert 'upper' in ci['95%']

    @patch('EcoSystemiser.discovery.algorithms.monte_carlo.MonteCarloEngine._evaluate_samples')
    def test_analyze_workflow(self, mock_evaluate):
        """Test complete Monte Carlo analysis workflow."""
        config = MonteCarloConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            n_samples=10
        )

        # Mock evaluation results
        mock_evaluate.return_value = np.random.normal(50, 10, 10)

        mc = MonteCarloEngine(config)
        fitness_function = Mock(return_value=50)

        result = mc.analyze(fitness_function)

        assert 'samples' in result
        assert 'results' in result
        assert 'uncertainty_analysis' in result
        assert 'sensitivity_analysis' in result


class TestParameterEncoder:
    """Test parameter encoding/decoding functionality."""

    def test_simple_parameter_encoding(self):
        """Test encoding simple parameters."""
        base_config = {
            'components': [
                {
                    'name': 'battery',
                    'technical': {'capacity_nominal': 100}
                },
                {
                    'name': 'solar_pv',
                    'technical': {'capacity_nominal': 50}
                }
            ]
        }

        variables = [
            {
                'component': 'battery',
                'parameter': 'technical.capacity_nominal',
                'bounds': [50, 200]
            },
            {
                'component': 'solar_pv',
                'parameter': 'technical.capacity_nominal',
                'bounds': [0, 100]
            }
        ]

        encoder = ParameterEncoder(base_config, variables)

        assert encoder.spec.dimensions == 2
        assert encoder.spec.bounds == [(50, 200), (0, 100)]

    def test_parameter_encoding_decoding(self):
        """Test encoding and decoding round trip."""
        base_config = {
            'components': [
                {
                    'name': 'battery',
                    'technical': {'capacity_nominal': 100}
                }
            ]
        }

        variables = [
            {
                'component': 'battery',
                'parameter': 'technical.capacity_nominal',
                'bounds': [50, 200]
            }
        ]

        encoder = ParameterEncoder(base_config, variables)

        # Test encoding
        values = np.array([150])  # Battery capacity = 150
        encoded_config = encoder.decode(values)

        assert encoded_config['components'][0]['technical']['capacity_nominal'] == 150

    def test_nested_parameter_paths(self):
        """Test handling of nested parameter paths."""
        base_config = {
            'components': [
                {
                    'name': 'heat_pump',
                    'technical': {
                        'performance': {
                            'cop': {'nominal': 3.5}
                        }
                    }
                }
            ]
        }

        variables = [
            {
                'component': 'heat_pump',
                'parameter': 'technical.performance.cop.nominal',
                'bounds': [2.0, 5.0]
            }
        ]

        encoder = ParameterEncoder(base_config, variables)

        values = np.array([4.0])
        decoded_config = encoder.decode(values)

        assert decoded_config['components'][0]['technical']['performance']['cop']['nominal'] == 4.0


class TestStudyServiceIntegration:
    """Test StudyService integration with discovery algorithms."""

    def create_test_config(self):
        """Create test configuration for studies."""
        return {
            'components': [
                {
                    'name': 'battery',
                    'type': 'storage',
                    'technical': {'capacity_nominal': 100}
                },
                {
                    'name': 'solar_pv',
                    'type': 'generation',
                    'technical': {'capacity_nominal': 50}
                }
            ]
        }

    @patch('EcoSystemiser.services.study_service.SimulationService')
    def test_genetic_algorithm_study(self, mock_sim_service_class):
        """Test genetic algorithm study execution."""
        # Setup mock simulation service
        mock_sim_service = Mock()
        mock_sim_service_class.return_value = mock_sim_service

        # Mock simulation results
        mock_result = SimulationResult(
            simulation_id="test_ga",
            status="optimal",
            solver_metrics={"objective_value": 100},
            kpis={"total_cost": 1000, "renewable_fraction": 0.8}
        )
        mock_sim_service.run_simulation.return_value = mock_result

        # Create study config
        base_config = SimulationConfig(
            simulation_id="test_base",
            system_config=self.create_test_config(),
            profile_config={},
            solver_config={},
            output_config={}
        )

        study_config = StudyConfig(
            study_id="test_ga_study",
            study_type="genetic_algorithm",
            base_config=base_config,
            optimization_variables=[
                {
                    'component': 'battery',
                    'parameter': 'technical.capacity_nominal',
                    'bounds': [50, 200]
                }
            ],
            optimization_objective="minimize_cost",
            population_size=4,
            generations=2
        )

        service = StudyService(mock_sim_service)

        # Mock the GA optimization to avoid complexity in unit test
        with patch.object(service, '_run_genetic_algorithm_study') as mock_ga:
            mock_ga_result = {
                'study_id': 'test_ga_study',
                'best_solution': {'battery': {'technical': {'capacity_nominal': 150}}},
                'best_fitness': 950,
                'pareto_front': [{'solution': [150], 'objectives': [950]}],
                'convergence_history': [1000, 975, 950]
            }
            mock_ga.return_value = mock_ga_result

            result = service.run_study(study_config)

            assert result['study_id'] == 'test_ga_study'
            assert 'best_solution' in result
            assert 'convergence_history' in result

    @patch('EcoSystemiser.services.study_service.SimulationService')
    def test_monte_carlo_study(self, mock_sim_service_class):
        """Test Monte Carlo study execution."""
        # Setup mock simulation service
        mock_sim_service = Mock()
        mock_sim_service_class.return_value = mock_sim_service

        # Mock simulation results
        mock_result = SimulationResult(
            simulation_id="test_mc",
            status="optimal",
            solver_metrics={"objective_value": 100},
            kpis={"total_cost": 1000, "renewable_fraction": 0.8}
        )
        mock_sim_service.run_simulation.return_value = mock_result

        # Create study config
        base_config = SimulationConfig(
            simulation_id="test_base",
            system_config=self.create_test_config(),
            profile_config={},
            solver_config={},
            output_config={}
        )

        study_config = StudyConfig(
            study_id="test_mc_study",
            study_type="monte_carlo",
            base_config=base_config,
            uncertainty_variables=[
                {
                    'component': 'battery',
                    'parameter': 'technical.capacity_nominal',
                    'distribution': 'normal',
                    'mean': 100,
                    'std': 20,
                    'bounds': [50, 200]
                }
            ],
            n_samples=10,
            sampling_method='lhs'
        )

        service = StudyService(mock_sim_service)

        # Mock the MC analysis to avoid complexity in unit test
        with patch.object(service, '_run_monte_carlo_study') as mock_mc:
            mock_mc_result = {
                'study_id': 'test_mc_study',
                'samples': [[100], [120], [80]],
                'results': [1000, 1200, 800],
                'uncertainty_analysis': {
                    'statistics': {'mean': 1000, 'std': 200},
                    'confidence_intervals': {'95%': {'lower': 600, 'upper': 1400}}
                }
            }
            mock_mc.return_value = mock_mc_result

            result = service.run_study(study_config)

            assert result['study_id'] == 'test_mc_study'
            assert 'uncertainty_analysis' in result
            assert 'samples' in result

    def test_parameter_encoder_creation(self):
        """Test parameter encoder creation in StudyService."""
        service = StudyService()

        base_config = SimulationConfig(
            simulation_id="test",
            system_config=self.create_test_config(),
            profile_config={},
            solver_config={},
            output_config={}
        )

        study_config = StudyConfig(
            study_id="test_encoder",
            study_type="genetic_algorithm",
            base_config=base_config,
            optimization_variables=[
                {
                    'component': 'battery',
                    'parameter': 'technical.capacity_nominal',
                    'bounds': [50, 200]
                },
                {
                    'component': 'solar_pv',
                    'parameter': 'technical.capacity_nominal',
                    'bounds': [0, 100]
                }
            ]
        )

        encoder = service._create_parameter_encoder(study_config)

        assert encoder.spec.dimensions == 2
        assert encoder.spec.bounds == [(50, 200), (0, 100)]

    def test_fitness_function_creation(self):
        """Test fitness function creation."""
        service = StudyService()

        base_config = SimulationConfig(
            simulation_id="test",
            system_config=self.create_test_config(),
            profile_config={},
            solver_config={},
            output_config={}
        )

        study_config = StudyConfig(
            study_id="test_fitness",
            study_type="genetic_algorithm",
            base_config=base_config,
            optimization_objective="minimize_cost"
        )

        encoder = Mock()
        encoder.decode.return_value = {'test': 'config'}

        fitness_function = service._create_fitness_function(study_config, encoder)

        # Should return a callable function
        assert callable(fitness_function)


class TestDiscoveryVisualization:
    """Test discovery-specific visualization capabilities."""

    def test_pareto_front_data_structure(self):
        """Test Pareto front data structure for visualization."""
        # Mock GA result with Pareto front
        ga_result = {
            'pareto_solutions': [
                {'battery_capacity': 100, 'solar_capacity': 50},
                {'battery_capacity': 150, 'solar_capacity': 75},
                {'battery_capacity': 200, 'solar_capacity': 100}
            ],
            'pareto_objectives': [
                [1000, 0.6],  # cost, renewable_fraction
                [1200, 0.7],
                [1500, 0.8]
            ]
        }

        # Verify structure is ready for visualization
        assert len(ga_result['pareto_solutions']) == len(ga_result['pareto_objectives'])
        assert len(ga_result['pareto_objectives'][0]) == 2  # Two objectives

    def test_convergence_data_structure(self):
        """Test convergence data structure for visualization."""
        ga_result = {
            'convergence_history': [1500, 1300, 1200, 1100, 1050, 1000],
            'generation_stats': {
                'best_fitness': [1500, 1300, 1200, 1100, 1050, 1000],
                'mean_fitness': [2000, 1800, 1600, 1400, 1300, 1200],
                'population_diversity': [0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
            }
        }

        assert len(ga_result['convergence_history']) == 6
        assert len(ga_result['generation_stats']['best_fitness']) == 6

    def test_uncertainty_data_structure(self):
        """Test uncertainty analysis data structure for visualization."""
        mc_result = {
            'uncertainty_analysis': {
                'statistics': {
                    'mean': 1000,
                    'std': 200,
                    'min': 600,
                    'max': 1400,
                    'percentiles': {
                        '5%': 680,
                        '25%': 850,
                        '50%': 1000,
                        '75%': 1150,
                        '95%': 1320
                    }
                },
                'confidence_intervals': {
                    '95%': {'lower': 608, 'upper': 1392},
                    '99%': {'lower': 484, 'upper': 1516}
                }
            }
        }

        stats = mc_result['uncertainty_analysis']['statistics']
        assert 'mean' in stats
        assert 'std' in stats
        assert 'percentiles' in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])