"""Tests for analysis strategies."""

import pytest
import numpy as np
from unittest.mock import Mock

from ecosystemiser.analyser.strategies.technical_kpi import TechnicalKPIAnalysis
from ecosystemiser.analyser.strategies.economic import EconomicAnalysis
from ecosystemiser.analyser.strategies.sensitivity import SensitivityAnalysis


@pytest.fixture
def sample_energy_results():
    """Sample energy system results for testing."""
    return {
        "components": {
            "battery": {
                "type": "battery",
                "technical": {"capacity_nominal": 100},
                "economic": {"capex_per_kwh": 500, "opex_per_kwh_year": 10}
            },
            "solar_pv": {
                "type": "solar_pv",
                "technical": {"capacity_nominal": 200},
                "economic": {"capex_per_kw": 1200, "opex_per_kw_year": 20}
            },
            "grid": {
                "type": "grid",
                "economic": {"price_import": 0.25, "price_export": 0.10}
            }
        },
        "flows": {
            "grid_import": {"values": [10, 20, 30, 40, 50]},
            "grid_export": {"values": [5, 0, 0, 0, 0]},
            "solar_pv_output": {"values": [15, 25, 35, 30, 20]},
            "demand_input": {"values": [20, 30, 40, 35, 25]},
            "battery_charge": {"values": [5, 10, 15, 0, 0]},
            "battery_discharge": {"values": [0, 0, 0, 10, 20]}
        },
        "solver_metrics": {
            "status": "optimal",
            "solve_time": 1.234,
            "objective_value": 1000.0
        }
    }


@pytest.fixture
def sample_parametric_results():
    """Sample parametric study results for testing."""
    return {
        "all_results": [
            {
                "status": "optimal",
                "output_config": {
                    "parameter_settings": {
                        "battery_capacity": 100,
                        "solar_capacity": 200
                    }
                },
                "kpis": {
                    "total_cost": 150000,
                    "renewable_fraction": 0.6
                }
            },
            {
                "status": "optimal",
                "output_config": {
                    "parameter_settings": {
                        "battery_capacity": 150,
                        "solar_capacity": 300
                    }
                },
                "kpis": {
                    "total_cost": 200000,
                    "renewable_fraction": 0.8
                }
            },
            {
                "status": "feasible",
                "output_config": {
                    "parameter_settings": {
                        "battery_capacity": 50,
                        "solar_capacity": 100
                    }
                },
                "kpis": {
                    "total_cost": 100000,
                    "renewable_fraction": 0.4
                }
            }
        ]
    }


class TestTechnicalKPIAnalysis:
    """Test suite for TechnicalKPIAnalysis."""

    def test_initialization(self):
        """Test strategy initialization."""
        strategy = TechnicalKPIAnalysis()
        assert strategy.name == "TechnicalKPI"

    def test_energy_system_analysis(self, sample_energy_results):
        """Test analysis of energy system."""
        strategy = TechnicalKPIAnalysis()
        results = strategy.run(sample_energy_results)

        # Check that key metrics are calculated
        assert 'grid_self_sufficiency' in results
        assert 'renewable_fraction' in results
        assert 'total_demand' in results
        assert 'renewable_generation_total' in results

        # Verify calculations
        total_demand = sum(sample_energy_results['flows']['demand_input']['values'])
        grid_import = sum(sample_energy_results['flows']['grid_import']['values'])

        expected_self_sufficiency = max(0, 1 - (grid_import / total_demand))
        assert abs(results['grid_self_sufficiency'] - expected_self_sufficiency) < 0.001

    def test_battery_kpis(self, sample_energy_results):
        """Test battery-specific KPI calculations."""
        strategy = TechnicalKPIAnalysis()
        results = strategy.run(sample_energy_results)

        assert 'battery_cycles' in results
        assert 'battery_efficiency' in results
        assert 'battery_charge_total' in results
        assert 'battery_discharge_total' in results

        # Verify efficiency calculation
        total_charge = sum(sample_energy_results['flows']['battery_charge']['values'])
        total_discharge = sum(sample_energy_results['flows']['battery_discharge']['values'])
        expected_efficiency = total_discharge / total_charge if total_charge > 0 else 0

        assert abs(results['battery_efficiency'] - expected_efficiency) < 0.001

    def test_system_type_detection(self):
        """Test system type detection."""
        strategy = TechnicalKPIAnalysis()

        # Energy system
        energy_data = {"components": {"battery": {"type": "battery"}}}
        assert strategy._detect_system_type(energy_data) == "energy"

        # Water system
        water_data = {"components": {"tank": {"type": "water_storage"}}}
        assert strategy._detect_system_type(water_data) == "water"

        # Mixed system
        mixed_data = {"components": {"battery": {"type": "battery"}, "tank": {"type": "water_storage"}}}
        assert strategy._detect_system_type(mixed_data) == "mixed"

    def test_empty_results(self):
        """Test handling of empty results."""
        strategy = TechnicalKPIAnalysis()
        results = strategy.run({})

        # Should not crash and return basic structure
        assert isinstance(results, dict)


class TestEconomicAnalysis:
    """Test suite for EconomicAnalysis."""

    def test_initialization(self):
        """Test strategy initialization."""
        strategy = EconomicAnalysis()
        assert strategy.name == "Economic"
        assert strategy.discount_rate == 0.05
        assert strategy.project_lifetime == 20

    def test_capex_calculation(self, sample_energy_results):
        """Test CAPEX calculation."""
        strategy = EconomicAnalysis()
        capex = strategy._calculate_capex(sample_energy_results)

        # Battery: 100 kWh * 500 $/kWh = 50,000
        # Solar: 200 kW * 1200 $/kW = 240,000
        expected_capex = 100 * 500 + 200 * 1200
        assert capex == expected_capex

    def test_opex_calculation(self, sample_energy_results):
        """Test OPEX calculation."""
        strategy = EconomicAnalysis()
        opex = strategy._calculate_annual_opex(sample_energy_results)

        # Battery: 100 * 10 = 1,000
        # Solar: 200 * 20 = 4,000
        # Plus maintenance (1.5% of CAPEX)
        capex = strategy._calculate_capex(sample_energy_results)
        expected_opex = 100 * 10 + 200 * 20 + capex * 0.015
        assert abs(opex - expected_opex) < 0.01

    def test_energy_economics(self, sample_energy_results):
        """Test energy economics calculation."""
        strategy = EconomicAnalysis()
        energy_metrics = strategy._calculate_energy_economics(sample_energy_results)

        assert 'annual_grid_cost' in energy_metrics
        assert 'annual_grid_revenue' in energy_metrics
        assert 'annual_net_energy_cost' in energy_metrics

        # Verify calculations
        grid_import = sum(sample_energy_results['flows']['grid_import']['values'])
        grid_export = sum(sample_energy_results['flows']['grid_export']['values'])

        # Scale to annual (5 timesteps -> 8760 hours)
        scale_factor = 8760 / 5
        expected_cost = grid_import * 0.25 * scale_factor
        expected_revenue = grid_export * 0.10 * scale_factor

        assert abs(energy_metrics['annual_grid_cost'] - expected_cost) < 0.01
        assert abs(energy_metrics['annual_grid_revenue'] - expected_revenue) < 0.01

    def test_lcoe_calculation(self, sample_energy_results):
        """Test LCOE calculation."""
        strategy = EconomicAnalysis()

        capex = strategy._calculate_capex(sample_energy_results)
        opex_annual = strategy._calculate_annual_opex(sample_energy_results)
        energy_metrics = strategy._calculate_energy_economics(sample_energy_results)

        lcoe = strategy._calculate_lcoe(capex, opex_annual, energy_metrics, sample_energy_results)

        assert lcoe > 0
        assert isinstance(lcoe, float)

    def test_npv_calculation(self, sample_energy_results):
        """Test NPV calculation."""
        strategy = EconomicAnalysis()

        capex = strategy._calculate_capex(sample_energy_results)
        opex_annual = strategy._calculate_annual_opex(sample_energy_results)
        energy_metrics = strategy._calculate_energy_economics(sample_energy_results)

        npv = strategy._calculate_npv(capex, opex_annual, energy_metrics)

        assert isinstance(npv, float)

    def test_full_economic_analysis(self, sample_energy_results):
        """Test complete economic analysis."""
        strategy = EconomicAnalysis()
        results = strategy.run(sample_energy_results)

        # Check required metrics
        required_metrics = [
            'capex_total', 'opex_annual', 'opex_total',
            'lcoe', 'npv', 'payback_period_years',
            'total_cost_ownership', 'component_costs'
        ]

        for metric in required_metrics:
            assert metric in results

        # Verify component costs structure
        assert 'battery' in results['component_costs']
        assert 'solar_pv' in results['component_costs']
        assert 'capex' in results['component_costs']['battery']
        assert 'opex_annual' in results['component_costs']['battery']


class TestSensitivityAnalysis:
    """Test suite for SensitivityAnalysis."""

    def test_initialization(self):
        """Test strategy initialization."""
        strategy = SensitivityAnalysis()
        assert strategy.name == "Sensitivity"

    def test_single_simulation_analysis(self, sample_energy_results):
        """Test analysis of single simulation."""
        strategy = SensitivityAnalysis()
        results = strategy.run(sample_energy_results)

        assert 'component_utilization' in results
        assert 'temporal_sensitivity' in results
        assert results['analysis_method'] == 'single'

    def test_parametric_study_analysis(self, sample_parametric_results):
        """Test analysis of parametric study."""
        strategy = SensitivityAnalysis()
        results = strategy.run(sample_parametric_results)

        assert 'parameter_sensitivities' in results
        assert 'most_influential_parameters' in results
        assert 'optimal_configurations' in results
        assert 'trade_off_analysis' in results
        assert 'robustness_metrics' in results
        assert results['analysis_method'] == 'parametric'

    def test_sensitivity_indices_calculation(self):
        """Test sensitivity indices calculation."""
        strategy = SensitivityAnalysis()

        param_data = {
            "battery_capacity": [100, 150, 200],
            "solar_capacity": [200, 250, 300]
        }

        kpi_data = {
            "total_cost": [150000, 200000, 250000],
            "renewable_fraction": [0.6, 0.7, 0.8]
        }

        indices = strategy._calculate_sensitivity_indices(param_data, kpi_data)

        assert 'battery_capacity' in indices
        assert 'solar_capacity' in indices
        assert 'total_cost' in indices['battery_capacity']
        assert 'renewable_fraction' in indices['battery_capacity']

    def test_influential_parameters(self):
        """Test identification of influential parameters."""
        strategy = SensitivityAnalysis()

        sensitivity_indices = {
            "param1": {"kpi1": 0.8, "kpi2": 0.3},
            "param2": {"kpi1": 0.2, "kpi2": 0.9},
            "param3": {"kpi1": 0.1, "kpi2": 0.1}
        }

        influential = strategy._identify_influential_parameters(sensitivity_indices)

        assert len(influential) <= 5
        assert influential[0]['parameter'] in ['param1', 'param2']  # Should be most influential

        for param in influential:
            assert 'parameter' in param
            assert 'average_sensitivity' in param
            assert 'max_sensitivity' in param
            assert 'most_affected_kpi' in param

    def test_optimal_configurations(self, sample_parametric_results):
        """Test finding optimal configurations."""
        strategy = SensitivityAnalysis()

        optimal = strategy._find_optimal_configurations(sample_parametric_results['all_results'])

        assert 'minimum_cost' in optimal
        assert 'maximum_renewable' in optimal
        assert 'balanced' in optimal

        # Verify minimum cost configuration
        min_cost_config = optimal['minimum_cost']
        assert min_cost_config['cost'] == 100000  # Should be the lowest cost

        # Verify maximum renewable configuration
        max_renewable_config = optimal['maximum_renewable']
        assert max_renewable_config['renewable_fraction'] == 0.8  # Should be highest renewable

    def test_pareto_frontier(self, sample_parametric_results):
        """Test Pareto frontier analysis."""
        strategy = SensitivityAnalysis()

        trade_offs = strategy._analyze_trade_offs(sample_parametric_results['all_results'])

        assert 'cost_renewable_correlation' in trade_offs
        assert 'pareto_frontier_points' in trade_offs
        assert 'pareto_frontier' in trade_offs

        # Should have identified some Pareto points
        assert trade_offs['pareto_frontier_points'] > 0

    def test_robustness_metrics(self, sample_parametric_results):
        """Test robustness metrics calculation."""
        strategy = SensitivityAnalysis()

        metrics = strategy._calculate_robustness_metrics(sample_parametric_results['all_results'])

        assert 'success_rate' in metrics
        assert metrics['success_rate'] == 1.0  # All results are optimal/feasible

        # Should have stability metrics for KPIs
        assert any(key.endswith('_stability') for key in metrics.keys())

    def test_empty_parametric_results(self):
        """Test handling of empty parametric results."""
        strategy = SensitivityAnalysis()

        empty_results = {"all_results": []}
        results = strategy.run(empty_results)

        # Should not crash and return basic structure
        assert 'analysis_method' in results
        assert results['analysis_method'] == 'parametric'