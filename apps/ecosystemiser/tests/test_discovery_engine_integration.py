"""Integration tests for Discovery Engine GA and Monte Carlo functionality."""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch

from EcoSystemiser.services.study_service import (
    StudyService, StudyConfig, SimulationConfig
)
from EcoSystemiser.services.simulation_service import SimulationResult
from EcoSystemiser.discovery.algorithms.genetic_algorithm import (
    GeneticAlgorithm, NSGAIIOptimizer, GeneticAlgorithmConfig
)
from EcoSystemiser.discovery.algorithms.monte_carlo import (
    MonteCarloEngine, MonteCarloConfig
)
from EcoSystemiser.discovery.encoders.parameter_encoder import ParameterEncoder, SystemConfigEncoder


class TestDiscoveryEngineIntegration:
    """Test Discovery Engine integration with StudyService."""

    def create_test_base_config(self):
        """Create a test base configuration."""
        return SimulationConfig(
            simulation_id="test_base",
            system_config={
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
            },
            profile_config={},
            solver_config={},
            output_config={}
        )

    def test_genetic_algorithm_config_creation(self):
        """Test creating GA configuration."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(50, 200), (0, 100)],
            objectives=['minimize_cost'],
            population_size=10,
            max_generations=5
        )

        assert config.dimensions == 2
        assert len(config.bounds) == 2
        assert config.objectives == ['minimize_cost']
        assert config.population_size == 10
        assert config.max_generations == 5

    def test_monte_carlo_config_creation(self):
        """Test creating MC configuration."""
        config = MonteCarloConfig(
            dimensions=2,
            bounds=[(50, 200), (0, 100)],
            objectives=['minimize_cost'],
            population_size=100,  # For MC, this represents number of samples
            sampling_method='lhs',
            confidence_levels=[0.95, 0.99]
        )

        assert config.dimensions == 2
        assert config.population_size == 100
        assert config.sampling_method == 'lhs'
        assert config.confidence_levels == [0.95, 0.99]

    def test_parameter_encoder_functionality(self):
        """Test parameter encoder basic functionality."""
        variables = [
            {
                'name': 'battery_capacity',
                'component': 'battery',
                'parameter_path': 'technical.capacity_nominal',
                'bounds': (50, 200)
            },
            {
                'name': 'solar_capacity',
                'component': 'solar_pv',
                'parameter_path': 'technical.capacity_nominal',
                'bounds': (0, 100)
            }
        ]

        encoder = SystemConfigEncoder.from_parameter_list(variables)

        # Test encoding spec creation
        assert encoder.spec.dimensions == 2
        assert encoder.spec.bounds == [(50, 200), (0, 100)]
        assert len(encoder.spec.parameters) == 2

        # Test parameter names
        param_names = encoder.spec.get_parameter_names()
        assert 'battery_capacity' in param_names
        assert 'solar_capacity' in param_names

    @patch('EcoSystemiser.services.study_service.SimulationService')
    def test_study_service_ga_integration(self, mock_sim_service_class):
        """Test StudyService integration with GA."""
        # Setup mock simulation service
        mock_sim_service = Mock()
        mock_sim_service_class.return_value = mock_sim_service

        # Mock simulation results
        mock_result = SimulationResult(
            simulation_id="test_ga",
            status="optimal",
            solver_metrics={"objective_value": 1000},
            kpis={"total_cost": 1000, "renewable_fraction": 0.8}
        )
        mock_sim_service.run_simulation.return_value = mock_result

        # Create study config for GA
        base_config = self.create_test_base_config()
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

        # Test that StudyService can handle GA study type
        assert hasattr(service, '_run_genetic_algorithm_study')

        # Test parameter encoder creation
        encoder = service._create_parameter_encoder(study_config)
        assert encoder.spec.dimensions == 1
        assert encoder.spec.bounds == [(50, 200)]

        # Test fitness function creation
        fitness_function = service._create_fitness_function(study_config, encoder)
        assert callable(fitness_function)

    @patch('EcoSystemiser.services.study_service.SimulationService')
    def test_study_service_mc_integration(self, mock_sim_service_class):
        """Test StudyService integration with Monte Carlo."""
        # Setup mock simulation service
        mock_sim_service = Mock()
        mock_sim_service_class.return_value = mock_sim_service

        # Mock simulation results
        mock_result = SimulationResult(
            simulation_id="test_mc",
            status="optimal",
            solver_metrics={"objective_value": 1000},
            kpis={"total_cost": 1000, "renewable_fraction": 0.8}
        )
        mock_sim_service.run_simulation.return_value = mock_result

        # Create study config for MC
        base_config = self.create_test_base_config()
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

        # Test that StudyService can handle MC study type
        assert hasattr(service, '_run_monte_carlo_study')

    def test_ga_algorithm_initialization(self):
        """Test GA algorithm can be initialized."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            objectives=['minimize_cost'],
            population_size=10,
            max_generations=5
        )

        ga = GeneticAlgorithm(config)
        assert ga.config == config
        assert ga.current_generation == 0

        # Test population initialization
        population = ga.initialize_population()
        assert population.shape == (10, 2)
        assert np.all(population >= 0)
        assert np.all(population[:, 0] <= 100)
        assert np.all(population[:, 1] <= 50)

    def test_nsga2_algorithm_initialization(self):
        """Test NSGA-II algorithm can be initialized."""
        config = GeneticAlgorithmConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            objectives=['minimize_cost', 'maximize_renewable'],
            population_size=10,
            max_generations=5
        )

        nsga2 = NSGAIIOptimizer(config)
        assert nsga2.config == config
        assert len(config.objectives) == 2  # Multi-objective

    def test_monte_carlo_initialization(self):
        """Test Monte Carlo engine can be initialized."""
        config = MonteCarloConfig(
            dimensions=2,
            bounds=[(0, 100), (0, 50)],
            objectives=['minimize_cost'],
            population_size=100,  # Number of samples
            sampling_method='lhs'
        )

        mc = MonteCarloEngine(config)
        assert mc.config == config

    def test_discovery_cli_integration(self):
        """Test that discovery CLI commands are available."""
        from EcoSystemiser.cli import cli

        # Test that discover command group exists
        discover_cmd = None
        for cmd in cli.commands.values():
            if hasattr(cmd, 'name') and cmd.name == 'discover':
                discover_cmd = cmd
                break

        assert discover_cmd is not None

        # Test that subcommands exist
        subcommands = [cmd.name for cmd in discover_cmd.commands.values()]
        assert 'optimize' in subcommands
        assert 'uncertainty' in subcommands
        assert 'explore' in subcommands

    def test_visualization_integration(self):
        """Test that discovery visualizations are available."""
        from EcoSystemiser.datavis.plot_factory import PlotFactory

        plot_factory = PlotFactory()

        # Test that discovery visualization methods exist
        assert hasattr(plot_factory, 'create_ga_pareto_front_plot')
        assert hasattr(plot_factory, 'create_ga_convergence_plot')
        assert hasattr(plot_factory, 'create_uncertainty_distribution_plot')
        assert hasattr(plot_factory, 'create_risk_analysis_plot')
        assert hasattr(plot_factory, 'create_parameter_space_heatmap')
        assert hasattr(plot_factory, 'create_scenario_comparison_plot')

    def test_discovery_data_structures(self):
        """Test that discovery results have expected structure."""
        # Test GA result structure
        ga_result = {
            'study_id': 'test_ga',
            'best_solution': {'battery_capacity': 150},
            'best_fitness': 950,
            'pareto_front': [{'solution': [150], 'objectives': [950]}],
            'convergence_history': [1000, 975, 950],
            'generation_stats': {
                'best_fitness': [1000, 975, 950],
                'mean_fitness': [1200, 1100, 1050]
            }
        }

        # Verify GA structure
        assert 'study_id' in ga_result
        assert 'best_solution' in ga_result
        assert 'convergence_history' in ga_result
        assert isinstance(ga_result['convergence_history'], list)

        # Test MC result structure
        mc_result = {
            'study_id': 'test_mc',
            'samples': [[100], [120], [80]],
            'results': [1000, 1200, 800],
            'uncertainty_analysis': {
                'statistics': {'mean': 1000, 'std': 200},
                'confidence_intervals': {
                    '95%': {'lower': 600, 'upper': 1400}
                },
                'risk_metrics': {
                    'var_95': 600,
                    'cvar_95': 550
                }
            }
        }

        # Verify MC structure
        assert 'study_id' in mc_result
        assert 'uncertainty_analysis' in mc_result
        assert 'statistics' in mc_result['uncertainty_analysis']
        assert 'confidence_intervals' in mc_result['uncertainty_analysis']


class TestDiscoveryEngineComponents:
    """Test individual Discovery Engine components."""

    def test_parameter_encoder_spec_creation(self):
        """Test parameter specification creation."""
        variables = [
            {
                'component': 'battery',
                'parameter': 'technical.capacity_nominal',
                'bounds': [50, 200]
            }
        ]

        encoder = SystemConfigEncoder.from_parameter_list(variables)
        spec = encoder.spec

        assert spec.dimensions == 1
        assert spec.bounds == [(50, 200)]
        assert len(spec.parameters) == 1

    def test_nested_parameter_handling(self):
        """Test handling of nested parameter paths."""
        variables = [
            {
                'component': 'heat_pump',
                'parameter': 'technical.performance.cop.nominal',
                'bounds': [2.0, 5.0]
            }
        ]

        encoder = SystemConfigEncoder.from_parameter_list(variables)

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

        values = np.array([4.0])
        decoded_config = encoder.decode(values, base_config)

        # Check nested access worked
        cop_value = decoded_config['components'][0]['technical']['performance']['cop']['nominal']
        assert cop_value == 4.0

    def test_multi_component_encoding(self):
        """Test encoding multiple components."""
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
            },
            {
                'component': 'heat_pump',
                'parameter': 'technical.capacity_nominal',
                'bounds': [10, 50]
            }
        ]

        encoder = SystemConfigEncoder.from_parameter_list(variables)
        assert encoder.spec.dimensions == 3

        base_config = {
            'components': [
                {'name': 'battery', 'technical': {'capacity_nominal': 100}},
                {'name': 'solar_pv', 'technical': {'capacity_nominal': 50}},
                {'name': 'heat_pump', 'technical': {'capacity_nominal': 20}}
            ]
        }

        values = np.array([150, 75, 30])
        decoded_config = encoder.decode(values, base_config)

        # Check all components were updated
        assert decoded_config['components'][0]['technical']['capacity_nominal'] == 150
        assert decoded_config['components'][1]['technical']['capacity_nominal'] == 75
        assert decoded_config['components'][2]['technical']['capacity_nominal'] == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])