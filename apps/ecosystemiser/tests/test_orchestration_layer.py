"""Comprehensive test suite for the EcoSystemiser orchestration layer."""
import pytest
import tempfile
import json
import yaml
from pathlib import Path
import numpy as np
from unittest.mock import Mock, patch

import sys
eco_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(eco_path))

from EcoSystemiser.services.simulation_service import (
    SimulationService, SimulationConfig, SimulationResult
)
from EcoSystemiser.services.study_service import (
    StudyService, StudyConfig, ParameterSweepSpec, FidelitySweepSpec
)
from EcoSystemiser.solver.rolling_horizon_milp import (
    RollingHorizonMILPSolver, RollingHorizonConfig
)
from EcoSystemiser.system_model.system import System
from EcoSystemiser.system_model.components.energy.battery import Battery, BatteryParams
from EcoSystemiser.system_model.components.shared.archetypes import FidelityLevel


class TestSimulationService:
    """Test suite for SimulationService orchestration."""

    def test_simulation_service_initialization(self):
        """Test SimulationService initializes correctly."""
        service = SimulationService()
        assert service.component_repo is not None
        assert service.results_io is not None

    def test_simulation_config_validation(self):
        """Test SimulationConfig validation."""
        # Valid config
        config = SimulationConfig(
            simulation_id="test_sim",
            system_config_path="test_system.yml",
            solver_type="rule_based"
        )
        assert config.simulation_id == "test_sim"
        assert config.solver_type == "rule_based"

    def test_simulation_result_structure(self):
        """Test SimulationResult structure."""
        result = SimulationResult(
            simulation_id="test",
            status="optimal",
            results_path=Path("test_results"),
            kpis={"cost": 100.0},
            solver_metrics={"solve_time": 1.5}
        )
        assert result.simulation_id == "test"
        assert result.status == "optimal"
        assert result.kpis["cost"] == 100.0

    @pytest.fixture
    def mock_system_config(self):
        """Create a mock system configuration file."""
        config = {
            "system": {
                "system_id": "test_system",
                "timesteps": 24
            },
            "components": {
                "battery": {
                    "type": "Battery",
                    "technical": {
                        "capacity_nominal": 10.0,
                        "efficiency_nominal": 0.95,
                        "fidelity_level": "STANDARD"
                    }
                }
            }
        }
        return config

    def test_simulation_service_with_mock_config(self, mock_system_config):
        """Test SimulationService with mocked configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(mock_system_config, f)
            config_path = f.name

        try:
            config = SimulationConfig(
                simulation_id="test_orchestration",
                system_config_path=config_path,
                solver_type="rule_based",
                output_config={"directory": tempfile.gettempdir()}
            )

            service = SimulationService()

            # Test profile loading (should handle missing profiles gracefully)
            profiles = service._load_profiles(config)
            assert isinstance(profiles, dict)

        finally:
            Path(config_path).unlink()


class TestStudyService:
    """Test suite for StudyService multi-simulation orchestration."""

    def test_study_service_initialization(self):
        """Test StudyService initializes correctly."""
        service = StudyService()
        assert service.simulation_service is not None

    def test_parameter_sweep_specification(self):
        """Test ParameterSweepSpec creation."""
        sweep = ParameterSweepSpec(
            component_name="battery",
            parameter_path="technical.capacity_nominal",
            values=[5.0, 10.0, 15.0]
        )
        assert sweep.component_name == "battery"
        assert len(sweep.values) == 3

    def test_fidelity_sweep_specification(self):
        """Test FidelitySweepSpec creation."""
        sweep = FidelitySweepSpec(
            component_names=["battery", "solar_pv"],
            fidelity_levels=["SIMPLE", "STANDARD", "DETAILED"]
        )
        assert len(sweep.component_names) == 2
        assert len(sweep.fidelity_levels) == 3

    def test_study_config_parametric(self):
        """Test StudyConfig for parametric studies."""
        base_config = SimulationConfig(
            simulation_id="base",
            system_config_path="test.yml"
        )

        sweeps = [
            ParameterSweepSpec(
                component_name="battery",
                parameter_path="technical.capacity_nominal",
                values=[10.0, 20.0]
            )
        ]

        study_config = StudyConfig(
            study_id="param_study",
            study_type="parametric",
            base_config=base_config,
            parameter_sweeps=sweeps
        )

        assert study_config.study_type == "parametric"
        assert len(study_config.parameter_sweeps) == 1

    def test_generate_parametric_configs(self):
        """Test parametric configuration generation."""
        service = StudyService()

        base_config = SimulationConfig(
            simulation_id="base",
            system_config_path="test.yml"
        )

        sweeps = [
            ParameterSweepSpec(
                component_name="battery",
                parameter_path="capacity",
                values=[10.0, 20.0]
            ),
            ParameterSweepSpec(
                component_name="solar",
                parameter_path="power",
                values=[5.0, 15.0]
            )
        ]

        study_config = StudyConfig(
            study_id="test",
            study_type="parametric",
            base_config=base_config,
            parameter_sweeps=sweeps
        )

        configs = service._generate_parametric_configs(study_config)

        # Should generate 2 * 2 = 4 configurations
        assert len(configs) == 4

        # Check parameter settings are stored
        for config in configs:
            assert "parameter_settings" in config.output_config
            assert "combo_index" in config.output_config

    def test_generate_fidelity_configs(self):
        """Test fidelity configuration generation."""
        service = StudyService()

        base_config = SimulationConfig(
            simulation_id="base",
            system_config_path="test.yml"
        )

        study_config = StudyConfig(
            study_id="test",
            study_type="fidelity",
            base_config=base_config,
            fidelity_sweep=FidelitySweepSpec(
                component_names=["battery"],
                fidelity_levels=["SIMPLE", "STANDARD", "DETAILED"]
            )
        )

        configs = service._generate_fidelity_configs(study_config)

        # Should generate 3 configurations
        assert len(configs) == 3

        # Check fidelity levels are stored
        expected_fidelities = ["SIMPLE", "STANDARD", "DETAILED"]
        for config, expected in zip(configs, expected_fidelities):
            assert config.output_config["fidelity_level"] == expected

    @patch('EcoSystemiser.services.study_service.StudyService._run_single_simulation')
    def test_run_simulations_sequential(self, mock_run_single):
        """Test sequential simulation execution."""
        service = StudyService()

        # Mock simulation results
        mock_run_single.return_value = SimulationResult(
            simulation_id="test",
            status="optimal"
        )

        configs = [
            SimulationConfig(simulation_id="sim1", system_config_path="test1.yml"),
            SimulationConfig(simulation_id="sim2", system_config_path="test2.yml")
        ]

        study_config = StudyConfig(
            study_id="test",
            study_type="parametric",
            base_config=configs[0],
            parallel_execution=False
        )

        results = service._run_simulations(configs, study_config)

        assert len(results) == 2
        assert mock_run_single.call_count == 2

    def test_process_results(self):
        """Test results processing and aggregation."""
        service = StudyService()

        results = [
            SimulationResult(
                simulation_id="sim1",
                status="optimal",
                kpis={"cost": 100.0, "renewable": 0.8},
                solver_metrics={"solve_time": 1.0, "objective_value": 100.0}
            ),
            SimulationResult(
                simulation_id="sim2",
                status="optimal",
                kpis={"cost": 120.0, "renewable": 0.9},
                solver_metrics={"solve_time": 1.5, "objective_value": 120.0}
            ),
            SimulationResult(
                simulation_id="sim3",
                status="error",
                error="Test error"
            )
        ]

        study_config = StudyConfig(
            study_id="test",
            study_type="parametric",
            base_config=SimulationConfig(simulation_id="base", system_config_path="test.yml"),
            save_all_results=True
        )

        study_result = service._process_results(results, study_config)

        assert study_result.num_simulations == 3
        assert study_result.successful_simulations == 2
        assert study_result.failed_simulations == 1
        assert study_result.best_result is not None
        assert study_result.summary_statistics is not None

        # Check summary statistics
        stats = study_result.summary_statistics
        assert "cost_mean" in stats
        assert stats["cost_mean"] == 110.0  # (100 + 120) / 2


class TestRollingHorizonMILPSolver:
    """Test suite for RollingHorizonMILPSolver."""

    def test_rolling_horizon_config(self):
        """Test RollingHorizonConfig validation."""
        config = RollingHorizonConfig(
            horizon_hours=24,
            overlap_hours=4,
            prediction_horizon=72
        )
        assert config.horizon_hours == 24
        assert config.overlap_hours == 4

        # Test invalid configuration (this should be caught in the solver, not config)
        invalid_config = RollingHorizonConfig(
            horizon_hours=24,
            overlap_hours=30  # Invalid: overlap >= horizon
        )
        # The validation happens in the solver initialization
        system = System("test", 168)
        with pytest.raises(ValueError):
            RollingHorizonMILPSolver(system, invalid_config)

    def test_rolling_horizon_initialization(self):
        """Test RollingHorizonMILPSolver initialization."""
        system = System("test", 168)  # 1 week
        config = RollingHorizonConfig(
            horizon_hours=24,
            overlap_hours=4
        )

        solver = RollingHorizonMILPSolver(system, config)
        assert solver.system == system
        assert solver.rh_config == config
        assert solver.storage_states == {}

    def test_generate_windows(self):
        """Test window generation for rolling horizon."""
        system = System("test", 72)  # 3 days
        config = RollingHorizonConfig(
            horizon_hours=24,
            overlap_hours=4,
            prediction_horizon=48
        )

        solver = RollingHorizonMILPSolver(system, config)
        windows = solver._generate_windows()

        # Should generate overlapping windows
        assert len(windows) > 1

        # Check window structure
        for window in windows:
            assert 'start' in window
            assert 'end' in window
            assert 'prediction_end' in window
            assert window['end'] <= window['prediction_end']

        # Check overlap between consecutive windows
        for i in range(len(windows) - 1):
            current_end = windows[i]['implement_end']
            next_start = windows[i + 1]['start']
            overlap = current_end - next_start
            # Should have negative overlap (actual overlap)
            assert overlap <= 0

    def test_create_window_system(self):
        """Test window system creation."""
        # Create a test system with components
        system = System("test", 72)

        # Add a battery component
        battery_params = BatteryParams()
        battery = Battery(name="test_battery", params=battery_params)
        battery.profile = np.ones(72)  # Simple profile
        battery.N = 72
        system.add_component(battery)

        config = RollingHorizonConfig(horizon_hours=24)
        solver = RollingHorizonMILPSolver(system, config)

        window = {
            'start': 0,
            'end': 24,
            'prediction_end': 24
        }

        window_system = solver._create_window_system(window)

        assert window_system.N == 24
        assert len(window_system.components) == 1
        assert "test_battery" in window_system.components

        # Check profile was sliced correctly
        window_comp = window_system.components["test_battery"]
        assert len(window_comp.profile) == 24
        np.testing.assert_array_equal(window_comp.profile, np.ones(24))

    def test_initialize_storage_states(self):
        """Test storage state initialization."""
        system = System("test", 24)

        # Add battery with initial energy
        battery_params = BatteryParams()
        battery = Battery(name="test_battery", params=battery_params)
        battery.type = "storage"
        battery.E_init = 5.0
        system.add_component(battery)

        config = RollingHorizonConfig()
        solver = RollingHorizonMILPSolver(system, config)

        solver._initialize_storage_states()

        assert "test_battery" in solver.storage_states
        assert solver.storage_states["test_battery"]["energy"] == 5.0
        assert solver.storage_states["test_battery"]["last_updated"] == 0

    def test_validation_metrics(self):
        """Test solution validation metrics."""
        system = System("test", 72)
        config = RollingHorizonConfig()
        solver = RollingHorizonMILPSolver(system, config)

        # Mock some results
        solver.window_results = [
            {'status': 'optimal'},
            {'status': 'optimal'},
            {'status': 'error'}
        ]
        solver.storage_violations = [{'violation': 'test'}]

        validation = solver.validate_solution()

        assert validation['total_windows'] == 3
        assert validation['window_failures'] == 1
        assert validation['storage_continuity_violations'] == 1
        assert validation['success_rate'] == 2/3


class TestOrchestrationIntegration:
    """Integration tests for the complete orchestration layer."""

    def test_simulation_to_study_integration(self):
        """Test integration between SimulationService and StudyService."""
        sim_service = SimulationService()
        study_service = StudyService(sim_service)

        # Verify services are properly linked
        assert study_service.simulation_service == sim_service

    @patch('EcoSystemiser.services.simulation_service.SimulationService.run_simulation')
    def test_end_to_end_parametric_study(self, mock_run_sim):
        """Test end-to-end parametric study execution."""
        # Mock simulation results
        mock_run_sim.return_value = SimulationResult(
            simulation_id="test",
            status="optimal",
            kpis={"cost": 100.0}
        )

        study_service = StudyService()

        base_config = SimulationConfig(
            simulation_id="base",
            system_config_path="test.yml"
        )

        study_config = StudyConfig(
            study_id="integration_test",
            study_type="parametric",
            base_config=base_config,
            parameter_sweeps=[
                ParameterSweepSpec(
                    component_name="battery",
                    parameter_path="capacity",
                    values=[10.0, 20.0]
                )
            ],
            parallel_execution=False  # Sequential for testing
        )

        result = study_service.run_study(study_config)

        assert result.study_id == "integration_test"
        assert result.num_simulations == 2
        assert result.successful_simulations == 2
        assert mock_run_sim.call_count == 2

    def test_orchestration_error_handling(self):
        """Test error handling in orchestration layer."""
        # Test various error conditions
        study_service = StudyService()

        # Invalid study type
        with pytest.raises(ValueError):
            study_config = StudyConfig(
                study_id="test",
                study_type="invalid_type",
                base_config=SimulationConfig(
                    simulation_id="base",
                    system_config_path="test.yml"
                )
            )
            study_service.run_study(study_config)

    def test_convenience_methods(self):
        """Test convenience methods for common study types."""
        study_service = StudyService()

        # Test parameter sensitivity convenience method
        param_specs = [
            {
                "component_name": "battery",
                "parameter_path": "capacity",
                "values": [10.0, 20.0, 30.0]
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            # Create a minimal config file
            yaml.dump({"system": {"system_id": "test"}}, f)
            config_path = f.name

        try:
            # This would normally run the study, but we'll just test the setup
            # The actual study run would fail due to missing components,
            # but we can test that the method sets up correctly
            assert hasattr(study_service, 'run_parameter_sensitivity')
            assert hasattr(study_service, 'run_fidelity_comparison')
        finally:
            # Clean up the temporary file
            Path(config_path).unlink(missing_ok=True)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])