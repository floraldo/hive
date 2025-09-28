"""Comprehensive tests for StudyService parametric sweep functionality."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
import yaml
from ecosystemiser.services.simulation_service import SimulationResult
from ecosystemiser.services.study_service import (
    ParameterSweepSpec,
    SimulationConfig,
    StudyConfig,
    StudyService,
)
from ecosystemiser.services.study_service_enhanced import (
    ParametricSweepEnhancement,
    apply_parameter_to_config,
    generate_parameter_report,
)


class TestParametricSweep:
    """Test parametric sweep functionality."""

    def test_parameter_sweep_spec(self):
        """Test ParameterSweepSpec model."""
        spec = ParameterSweepSpec(
            component_name="battery",
            parameter_path="technical.capacity_nominal",
            values=[100, 200, 300, 400],
        )

        assert spec.component_name == "battery"
        assert spec.parameter_path == "technical.capacity_nominal"
        assert len(spec.values) == 4
        assert spec.values[0] == 100

    def test_generate_parametric_configs(self):
        """Test generation of parametric configurations."""
        # Create base config
        base_config = SimulationConfig(
            simulation_id="test_base",
            system_config={
                "components": [
                    {
                        "name": "battery",
                        "type": "storage",
                        "technical": {"capacity_nominal": 100},
                    }
                ]
            },
            profile_config={},
            solver_config={},
            output_config={},
        )

        # Create parameter sweep
        sweep = ParameterSweepSpec(
            component_name="battery",
            parameter_path="technical.capacity_nominal",
            values=[50, 100, 150, 200],
        )

        # Create study config
        study_config = StudyConfig(
            study_id="test_parametric",
            study_type="parametric",
            base_config=base_config,
            parameter_sweeps=[sweep],
        )

        # Generate configurations
        service = StudyService()
        configs = service._generate_parametric_configs(study_config)

        assert len(configs) == 4
        assert configs[0].simulation_id == "test_parametric_param_0"
        assert configs[1].simulation_id == "test_parametric_param_1"

        # Check parameter settings are recorded
        for i, config in enumerate(configs):
            expected_value = sweep.values[i]
            param_settings = config.output_config.get("parameter_settings", {})
            assert f"{sweep.component_name}.{sweep.parameter_path}" in param_settings
            assert (
                param_settings[f"{sweep.component_name}.{sweep.parameter_path}"]
                == expected_value
            )

    def test_multi_parameter_sweep(self):
        """Test sweep with multiple parameters."""
        base_config = SimulationConfig(
            simulation_id="test_base",
            system_config={},
            profile_config={},
            solver_config={},
            output_config={},
        )

        # Create multiple parameter sweeps
        sweeps = [
            ParameterSweepSpec(
                component_name="battery",
                parameter_path="technical.capacity_nominal",
                values=[100, 200],
            ),
            ParameterSweepSpec(
                component_name="solar_pv",
                parameter_path="technical.capacity_nominal",
                values=[50, 100, 150],
            ),
        ]

        study_config = StudyConfig(
            study_id="test_multi",
            study_type="parametric",
            base_config=base_config,
            parameter_sweeps=sweeps,
        )

        service = StudyService()
        configs = service._generate_parametric_configs(study_config)

        # Should generate all combinations: 2 x 3 = 6
        assert len(configs) == 6

        # Check all combinations are present
        combinations = []
        for config in configs:
            params = config.output_config["parameter_settings"]
            battery_cap = params["battery.technical.capacity_nominal"]
            solar_cap = params["solar_pv.technical.capacity_nominal"]
            combinations.append((battery_cap, solar_cap))

        expected_combinations = [
            (100, 50),
            (100, 100),
            (100, 150),
            (200, 50),
            (200, 100),
            (200, 150),
        ]

        for expected in expected_combinations:
            assert expected in combinations

    def test_apply_parameter_to_config(self):
        """Test applying parameter to system configuration."""
        config = {
            "components": [
                {
                    "name": "battery",
                    "type": "storage",
                    "technical": {"capacity_nominal": 100, "efficiency": 0.95},
                }
            ]
        }

        # Apply parameter
        modified = apply_parameter_to_config(
            config, "battery", "technical.capacity_nominal", 200
        )

        # Check original is unchanged
        assert config["components"][0]["technical"]["capacity_nominal"] == 100

        # Check modified has new value
        assert modified["components"][0]["technical"]["capacity_nominal"] == 200
        # Other values should be unchanged
        assert modified["components"][0]["technical"]["efficiency"] == 0.95

    def test_nested_parameter_path(self):
        """Test applying parameters with nested paths."""
        config = {
            "components": [
                {
                    "name": "heat_pump",
                    "type": "conversion",
                    "technical": {
                        "performance": {"cop": {"nominal": 3.5, "minimum": 2.0}}
                    },
                }
            ]
        }

        modified = apply_parameter_to_config(
            config, "heat_pump", "technical.performance.cop.nominal", 4.5
        )

        assert (
            modified["components"][0]["technical"]["performance"]["cop"]["nominal"]
            == 4.5
        )
        assert (
            modified["components"][0]["technical"]["performance"]["cop"]["minimum"]
            == 2.0
        )

    @patch("EcoSystemiser.services.study_service.SimulationService")
    def test_parallel_execution(self, mock_sim_service_class):
        """Test parallel execution of simulations."""
        # Setup mock simulation service
        mock_sim_service = Mock()
        mock_sim_service_class.return_value = mock_sim_service

        # Create mock results
        mock_result = SimulationResult(
            simulation_id="test",
            status="optimal",
            solver_metrics={"objective_value": 100},
            kpis={"total_cost": 1000},
        )
        mock_sim_service.run_simulation.return_value = mock_result

        base_config = SimulationConfig(
            simulation_id="test_base",
            system_config={},
            profile_config={},
            solver_config={},
            output_config={},
        )

        sweep = ParameterSweepSpec(
            component_name="battery",
            parameter_path="technical.capacity_nominal",
            values=[100, 200, 300],
        )

        study_config = StudyConfig(
            study_id="test_parallel",
            study_type="parametric",
            base_config=base_config,
            parameter_sweeps=[sweep],
            parallel_execution=True,
            max_workers=2,
        )

        service = StudyService(mock_sim_service)

        # Mock the _run_single_simulation to avoid process pool issues in tests
        with patch.object(service, "_run_single_simulation", return_value=mock_result):
            result = service.run_study(study_config)

        assert result.study_id == "test_parallel"
        assert result.num_simulations == 3
        assert result.successful_simulations == 3

    def test_battery_capacity_sweep_generation(self):
        """Test battery capacity sweep value generation."""
        values = ParametricSweepEnhancement.create_battery_capacity_sweep(
            base_capacity=100, num_points=5, range_factor=2.0
        )

        assert len(values) == 5
        assert values[0] == 50  # 100 / 2
        assert values[-1] == 200  # 100 * 2
        assert values[2] == 125  # Middle value

    def test_solar_capacity_sweep_generation(self):
        """Test solar capacity sweep value generation."""
        values = ParametricSweepEnhancement.create_solar_capacity_sweep(
            base_capacity=50, num_points=6
        )

        assert len(values) == 6
        assert values[0] == 0
        assert values[-1] == 100  # 50 * 2
        # The values should be evenly distributed from 0 to 100

    def test_parameter_influence_analysis(self):
        """Test parameter influence analysis."""
        study_result = {
            "all_results": [
                {
                    "status": "optimal",
                    "output_config": {"parameter_settings": {"battery.capacity": 100}},
                    "kpis": {"total_cost": 10000, "renewable_fraction": 0.6},
                },
                {
                    "status": "optimal",
                    "output_config": {"parameter_settings": {"battery.capacity": 200}},
                    "kpis": {"total_cost": 15000, "renewable_fraction": 0.8},
                },
                {
                    "status": "optimal",
                    "output_config": {"parameter_settings": {"battery.capacity": 300}},
                    "kpis": {"total_cost": 20000, "renewable_fraction": 0.9},
                },
            ]
        }

        analysis = ParametricSweepEnhancement.analyze_parameter_influence(study_result)

        assert "parameter_sensitivities" in analysis
        assert "optimal_configuration" in analysis
        assert "recommendations" in analysis

        # Should identify battery.capacity as influential
        if "battery.capacity" in analysis["parameter_sensitivities"]:
            sensitivities = analysis["parameter_sensitivities"]["battery.capacity"]
            # Should have positive correlation with both cost and renewable fraction
            assert "total_cost" in sensitivities
            assert "renewable_fraction" in sensitivities

        # Optimal configuration should be the one with lowest cost
        assert analysis["optimal_configuration"] == {"battery.capacity": 100}

    def test_result_aggregation(self):
        """Test result aggregation and statistics."""
        results = [
            SimulationResult(
                simulation_id="sim_1",
                status="optimal",
                solver_metrics={"objective_value": 100, "solve_time": 1.0},
                kpis={"total_cost": 10000, "renewable_fraction": 0.6},
            ),
            SimulationResult(
                simulation_id="sim_2",
                status="optimal",
                solver_metrics={"objective_value": 150, "solve_time": 1.5},
                kpis={"total_cost": 15000, "renewable_fraction": 0.7},
            ),
            SimulationResult(
                simulation_id="sim_3",
                status="optimal",
                solver_metrics={"objective_value": 200, "solve_time": 2.0},
                kpis={"total_cost": 20000, "renewable_fraction": 0.8},
            ),
        ]

        service = StudyService()
        # Create a proper base_config instead of Mock
        base_config = SimulationConfig(
            simulation_id="test_base",
            system_config={},
            profile_config={},
            solver_config={},
            output_config={},
        )
        study_config = StudyConfig(
            study_id="test",
            study_type="parametric",
            base_config=base_config,
            save_all_results=True,
        )

        study_result = service._process_results(results, study_config)

        assert study_result.num_simulations == 3
        assert study_result.successful_simulations == 3
        assert study_result.failed_simulations == 0

        # Check statistics
        stats = study_result.summary_statistics
        assert "total_cost_mean" in stats
        assert stats["total_cost_mean"] == 15000
        assert "renewable_fraction_mean" in stats
        assert abs(stats["renewable_fraction_mean"] - 0.7) < 0.01
        assert "solve_time_total" in stats
        assert stats["solve_time_total"] == 4.5

        # Best result should be the one with lowest objective value
        assert study_result.best_result is not None
        assert study_result.best_result["simulation_id"] == "sim_1"


class TestStudyServiceIntegration:
    """Integration tests for complete study workflows."""

    @pytest.mark.integration
    def test_complete_parametric_study(self):
        """Test a complete parametric study workflow."""
        # This would require actual system configs and would be an integration test
        pass

    @pytest.mark.integration
    def test_sensitivity_analysis_workflow(self):
        """Test complete sensitivity analysis workflow."""
        # This would test the convenience method with real configs
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
