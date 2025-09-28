"""
End-to-End Integration Test for Discovery Engine

This module performs comprehensive end-to-end testing of the Discovery Engine,
validating the complete workflow from StudyService configuration through
optimization execution to report generation.
"""

import json
import shutil

import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest

from ecosystemiser.datavis.plot_factory import PlotFactory
from ecosystemiser.discovery.algorithms.genetic_algorithm import GeneticAlgorithmConfig
from ecosystemiser.discovery.algorithms.monte_carlo import MonteCarloConfig
from ecosystemiser.reporting.generator import HTMLReportGenerator
from ecosystemiser.services.simulation_service import (
    SimulationResult,
    SimulationService,
)
from ecosystemiser.services.study_service import (
    SimulationConfig,
    StudyConfig,
    StudyService,
)
from hive_logging import get_logger

logger = get_logger(__name__)


class TestDiscoveryEngineE2E:
    """End-to-end integration tests for the Discovery Engine."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for test artifacts."""
        workspace = Path(tempfile.mkdtemp(prefix="discovery_e2e_"))
        yield workspace
        # Cleanup after test
        if workspace.exists():
            shutil.rmtree(workspace)

    @pytest.fixture
    def energy_system_config(self):
        """Create realistic energy system configuration."""
        return {
            "system_id": "residential_microgrid",
            "components": [
                {
                    "name": "solar_pv",
                    "type": "generation",
                    "technology": "solar_photovoltaic",
                    "technical": {
                        "power_capacity_nominal": 10.0,  # kW
                        "efficiency": 0.20,
                        "degradation_rate": 0.005,
                    },
                    "economic": {
                        "capex_per_kw": 1200,
                        "opex_per_kw_year": 20,
                        "lifetime_years": 25,
                    },
                },
                {
                    "name": "battery_storage",
                    "type": "storage",
                    "technology": "lithium_ion",
                    "technical": {
                        "energy_capacity_nominal": 20.0,  # kWh
                        "power_capacity_nominal": 5.0,  # kW
                        "efficiency_charge": 0.95,
                        "efficiency_discharge": 0.95,
                        "soc_min": 0.2,
                        "soc_max": 0.9,
                    },
                    "economic": {
                        "capex_per_kwh": 400,
                        "opex_per_kwh_year": 10,
                        "lifetime_cycles": 5000,
                    },
                },
                {
                    "name": "grid_connection",
                    "type": "grid",
                    "technology": "bidirectional",
                    "technical": {"max_import": 10.0, "max_export": 10.0},  # kW  # kW
                    "economic": {
                        "electricity_price": 0.12,  # $/kWh
                        "feed_in_tariff": 0.08,  # $/kWh
                    },
                },
                {
                    "name": "residential_load",
                    "type": "demand",
                    "technology": "residential",
                    "profile": {
                        "annual_consumption": 10000,  # kWh/year
                        "peak_demand": 5.0,  # kW
                    },
                },
            ],
        }

    @pytest.fixture
    def profile_config(self):
        """Create profile configuration for simulation."""
        return {
            "climate": {
                "location": {
                    "latitude": 37.7749,
                    "longitude": -122.4194,
                },  # San Francisco
                "data_source": "synthetic",
                "resolution": "hourly",
            },
            "demand": {
                "profile_type": "residential_typical",
                "stochastic_variation": 0.1,
            },
        }

    def test_genetic_algorithm_workflow(
        self, temp_workspace, energy_system_config, profile_config
    ):
        """Test complete GA optimization workflow."""
        # Configure base simulation
        base_config = SimulationConfig(
            simulation_id="ga_e2e_test",
            system_config=energy_system_config,
            profile_config=profile_config,
            solver_config={
                "solver_type": "milp",
                "time_horizon": 24 * 7,  # 1 week
                "time_step": 1,  # hourly
            },
            output_config={
                "save_results": True,
                "output_dir": str(temp_workspace / "results"),
            },
        )

        # Configure GA study
        study_config = StudyConfig(
            study_id="ga_optimization_e2e",
            study_type="genetic_algorithm",
            base_config=base_config,
            optimization_variables=[
                {
                    "component": "solar_pv",
                    "parameter": "technical.power_capacity_nominal",
                    "bounds": [5.0, 50.0],
                    "description": "Solar PV capacity (kW)",
                },
                {
                    "component": "battery_storage",
                    "parameter": "technical.energy_capacity_nominal",
                    "bounds": [10.0, 100.0],
                    "description": "Battery energy capacity (kWh)",
                },
                {
                    "component": "battery_storage",
                    "parameter": "technical.power_capacity_nominal",
                    "bounds": [2.0, 20.0],
                    "description": "Battery power capacity (kW)",
                },
            ],
            optimization_objective="multi_objective",
            objectives=["minimize_cost", "maximize_renewable_fraction"],
            algorithm_config={
                "population_size": 20,
                "max_generations": 10,
                "mutation_rate": 0.1,
                "crossover_rate": 0.9,
                "elitism_ratio": 0.1,
            },
        )

        # Create study service (with mock simulation for speed)
        study_service = StudyService()

        # Mock the simulation service for faster testing
        def mock_simulation(config):
            # Simulate realistic results based on component sizes
            solar_capacity = config["system_config"]["components"][0]["technical"][
                "power_capacity_nominal"
            ]
            battery_capacity = config["system_config"]["components"][1]["technical"][
                "energy_capacity_nominal"
            ]

            # Simple cost model
            solar_cost = solar_capacity * 1200
            battery_cost = battery_capacity * 400
            total_cost = solar_cost + battery_cost + np.random.normal(0, 100)

            # Simple renewable fraction model
            renewable_fraction = min(
                0.95, solar_capacity / 50 * 0.7 + battery_capacity / 100 * 0.3
            )
            renewable_fraction += np.random.normal(0, 0.02)
            renewable_fraction = np.clip(renewable_fraction, 0, 1)

            return SimulationResult(
                simulation_id=config["simulation_id"],
                status="optimal",
                solver_metrics={"solve_time": 0.1, "iterations": 10},
                kpis={
                    "total_cost": total_cost,
                    "renewable_fraction": renewable_fraction,
                    "grid_independence": renewable_fraction * 0.8,
                    "co2_emissions": (1 - renewable_fraction) * 1000,
                },
            )

        # Patch the simulation execution
        study_service._run_simulation = mock_simulation

        # Run GA study
        logger.info("Starting GA optimization workflow...")
        start_time = time.time()

        result = study_service.run_study(study_config)

        execution_time = time.time() - start_time
        logger.info(f"GA optimization completed in {execution_time:.2f} seconds")

        # Validate result structure
        assert "study_id" in result
        assert "study_type" in result
        assert result["study_type"] == "genetic_algorithm"
        assert "best_result" in result
        assert "num_simulations" in result
        assert "execution_time" in result

        # Validate GA-specific results
        best_result = result["best_result"]
        assert "best_solution" in best_result
        assert "best_objectives" in best_result
        assert "pareto_front" in best_result or "pareto_objectives" in best_result
        assert "convergence_history" in best_result

        # Check Pareto front quality
        if "pareto_objectives" in best_result:
            pareto_front = np.array(best_result["pareto_objectives"])
            assert len(pareto_front) > 0, "Empty Pareto front"
            assert pareto_front.shape[1] == 2, "Wrong number of objectives"

            # Check for Pareto dominance (no solution should dominate another)
            for i, sol1 in enumerate(pareto_front):
                for j, sol2 in enumerate(pareto_front):
                    if i != j:
                        # For minimization, sol1 dominates sol2 if all objectives are <=
                        dominates = np.all(sol1 <= sol2) and np.any(sol1 < sol2)
                        assert not dominates, f"Solution {i} dominates solution {j}"

        # Save results
        results_file = temp_workspace / "ga_results.json"
        with open(results_file, "w") as f:
            json.dump(result, f, indent=2, default=str)

        logger.info(f"Results saved to {results_file}")

    def test_monte_carlo_workflow(
        self, temp_workspace, energy_system_config, profile_config
    ):
        """Test complete Monte Carlo uncertainty analysis workflow."""
        # Configure base simulation
        base_config = SimulationConfig(
            simulation_id="mc_e2e_test",
            system_config=energy_system_config,
            profile_config=profile_config,
            solver_config={
                "solver_type": "milp",
                "time_horizon": 24 * 30,  # 1 month
                "time_step": 1,
            },
            output_config={
                "save_results": True,
                "output_dir": str(temp_workspace / "results"),
            },
        )

        # Configure MC study
        study_config = StudyConfig(
            study_id="mc_uncertainty_e2e",
            study_type="monte_carlo",
            base_config=base_config,
            uncertainty_variables=[
                {
                    "component": "solar_pv",
                    "parameter": "technical.efficiency",
                    "distribution": "normal",
                    "parameters": {"mean": 0.20, "std": 0.02},
                    "bounds": [0.15, 0.25],
                    "description": "Solar panel efficiency uncertainty",
                },
                {
                    "component": "grid_connection",
                    "parameter": "economic.electricity_price",
                    "distribution": "triangular",
                    "parameters": {"low": 0.08, "mode": 0.12, "high": 0.18},
                    "bounds": [0.08, 0.18],
                    "description": "Electricity price uncertainty",
                },
                {
                    "component": "residential_load",
                    "parameter": "profile.annual_consumption",
                    "distribution": "normal",
                    "parameters": {"mean": 10000, "std": 1500},
                    "bounds": [7000, 13000],
                    "description": "Demand uncertainty",
                },
            ],
            algorithm_config={
                "n_samples": 100,
                "sampling_method": "lhs",
                "confidence_levels": [0.05, 0.25, 0.50, 0.75, 0.95],
                "sensitivity_analysis": True,
                "risk_analysis": True,
            },
        )

        # Create study service
        study_service = StudyService()

        # Mock simulation for speed
        def mock_simulation(config):
            # Extract uncertain parameters
            solar_eff = config["system_config"]["components"][0]["technical"][
                "efficiency"
            ]
            elec_price = config["system_config"]["components"][2]["economic"][
                "electricity_price"
            ]
            annual_demand = config["system_config"]["components"][3]["profile"][
                "annual_consumption"
            ]

            # Simple model with uncertainty propagation
            base_cost = 15000
            cost_variation = (
                (0.20 - solar_eff) * 50000  # Higher efficiency reduces cost
                + (elec_price - 0.12) * 30000  # Higher price increases cost
                + (annual_demand - 10000) * 2  # Higher demand increases cost
            )
            total_cost = base_cost + cost_variation + np.random.normal(0, 500)

            return SimulationResult(
                simulation_id=config["simulation_id"],
                status="optimal",
                solver_metrics={"solve_time": 0.05},
                kpis={
                    "total_cost": total_cost,
                    "lcoe": total_cost / annual_demand,
                    "solar_efficiency": solar_eff,
                    "grid_cost": elec_price * annual_demand * 0.3,
                },
            )

        study_service._run_simulation = mock_simulation

        # Run MC study
        logger.info("Starting Monte Carlo uncertainty analysis...")
        start_time = time.time()

        result = study_service.run_study(study_config)

        execution_time = time.time() - start_time
        logger.info(f"MC analysis completed in {execution_time:.2f} seconds")

        # Validate result structure
        assert "study_id" in result
        assert "study_type" in result
        assert result["study_type"] == "monte_carlo"
        assert "num_simulations" in result

        # Validate MC-specific results
        assert "best_result" in result
        mc_result = result["best_result"]

        assert "uncertainty_analysis" in mc_result
        uncertainty = mc_result["uncertainty_analysis"]

        # Check statistics
        assert "statistics" in uncertainty
        stats = uncertainty["statistics"]
        assert "mean" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats

        # Check confidence intervals
        assert "confidence_intervals" in uncertainty
        ci = uncertainty["confidence_intervals"]
        assert "5%" in ci
        assert "95%" in ci

        # Verify CI ordering
        assert ci["5%"] < ci["25%"] if "25%" in ci else True
        assert ci["75%"] < ci["95%"] if "75%" in ci else True

        # Check sensitivity analysis if enabled
        if study_config.algorithm_config.get("sensitivity_analysis"):
            assert "sensitivity_analysis" in mc_result or "sensitivity" in uncertainty

        # Check risk metrics if enabled
        if study_config.algorithm_config.get("risk_analysis"):
            assert "risk_metrics" in uncertainty or "risk" in uncertainty

        # Save results
        results_file = temp_workspace / "mc_results.json"
        with open(results_file, "w") as f:
            json.dump(result, f, indent=2, default=str)

        logger.info(f"Results saved to {results_file}")

    def test_report_generation(self, temp_workspace):
        """Test HTML report generation for optimization results."""
        # Create mock optimization results
        ga_result = {
            "study_id": "test_ga_report",
            "study_type": "genetic_algorithm",
            "num_simulations": 200,
            "execution_time": 120.5,
            "best_result": {
                "best_solution": [25.5, 50.0, 10.0],
                "best_objectives": [12500, 0.85],
                "pareto_objectives": [
                    [10000, 0.70],
                    [11000, 0.75],
                    [12000, 0.80],
                    [13000, 0.85],
                    [14000, 0.90],
                ],
                "convergence_history": list(range(15000, 12000, -150)),
            },
        }

        mc_result = {
            "study_id": "test_mc_report",
            "study_type": "monte_carlo",
            "num_simulations": 1000,
            "execution_time": 60.3,
            "best_result": {
                "uncertainty_analysis": {
                    "statistics": {
                        "mean": 12500,
                        "std": 1500,
                        "min": 9000,
                        "max": 16000,
                    },
                    "confidence_intervals": {
                        "5%": 9800,
                        "25%": 11500,
                        "50%": 12500,
                        "75%": 13500,
                        "95%": 15200,
                    },
                    "risk_metrics": {"var_95": 15200, "cvar_95": 15800},
                }
            },
        }

        # Create report generator
        report_generator = HTMLReportGenerator()
        plot_factory = PlotFactory()

        # Generate mock plots
        plots = {}

        # Mock Pareto front plot data
        pareto_data = {
            "trade_off_analysis": {
                "pareto_frontier": [
                    {"cost": obj[0], "renewable": obj[1]}
                    for obj in ga_result["best_result"]["pareto_objectives"]
                ]
            }
        }
        plots["pareto_frontier"] = plot_factory.create_pareto_frontier_plot(pareto_data)

        # Mock convergence plot
        plots["convergence"] = plot_factory.create_ga_convergence_plot(
            ga_result["best_result"]
        )

        # Mock uncertainty distribution
        plots["uncertainty"] = plot_factory.create_uncertainty_distribution_plot(
            mc_result["best_result"]
        )

        # Generate GA report
        ga_html = report_generator.generate_ga_optimization_report(ga_result, plots)
        ga_report_file = temp_workspace / "ga_report.html"
        report_generator.save_report(ga_html, ga_report_file)

        assert ga_report_file.exists(), "GA report not created"
        assert ga_report_file.stat().st_size > 1000, "GA report too small"

        # Validate HTML content
        with open(ga_report_file, "r") as f:
            content = f.read()
            assert "Genetic Algorithm" in content
            assert "Pareto Front" in content or "pareto" in content.lower()
            assert "Convergence" in content

        # Generate MC report
        mc_html = report_generator.generate_mc_uncertainty_report(mc_result, plots)
        mc_report_file = temp_workspace / "mc_report.html"
        report_generator.save_report(mc_html, mc_report_file)

        assert mc_report_file.exists(), "MC report not created"
        assert mc_report_file.stat().st_size > 1000, "MC report too small"

        # Validate HTML content
        with open(mc_report_file, "r") as f:
            content = f.read()
            assert "Monte Carlo" in content or "Uncertainty" in content
            assert "Confidence Interval" in content or "confidence" in content.lower()
            assert "Statistics" in content or "Mean" in content

        logger.info(f"Reports generated: {ga_report_file}, {mc_report_file}")

    def test_parallel_execution(self, energy_system_config, profile_config):
        """Test parallel execution of optimization evaluations."""
        # Configure for parallel execution
        base_config = SimulationConfig(
            simulation_id="parallel_test",
            system_config=energy_system_config,
            profile_config=profile_config,
            solver_config={"solver_type": "milp"},
            output_config={"save_results": False},
        )

        study_config = StudyConfig(
            study_id="parallel_execution_test",
            study_type="genetic_algorithm",
            base_config=base_config,
            optimization_variables=[
                {
                    "component": "solar_pv",
                    "parameter": "technical.power_capacity_nominal",
                    "bounds": [5.0, 50.0],
                }
            ],
            algorithm_config={
                "population_size": 10,
                "max_generations": 2,
                "parallel_evaluation": True,
                "max_workers": 4,
            },
        )

        study_service = StudyService()

        # Mock simulation with artificial delay
        def slow_simulation(config):
            time.sleep(0.1)  # Simulate computation time
            return SimulationResult(
                simulation_id=config["simulation_id"],
                status="optimal",
                solver_metrics={},
                kpis={"total_cost": np.random.uniform(10000, 20000)},
            )

        study_service._run_simulation = slow_simulation

        # Measure execution time
        start_time = time.time()
        result = study_service.run_study(study_config)
        parallel_time = time.time() - start_time

        # Run sequential for comparison
        study_config.algorithm_config["parallel_evaluation"] = False
        study_config.algorithm_config["max_workers"] = 1

        start_time = time.time()
        result_seq = study_service.run_study(study_config)
        sequential_time = time.time() - start_time

        # Parallel should be faster (allow some overhead)
        speedup = sequential_time / parallel_time
        logger.info(f"Parallel speedup: {speedup:.2f}x")

        # With 4 workers and 0.1s per simulation, expect at least 2x speedup
        assert speedup > 1.5, f"Insufficient parallel speedup: {speedup:.2f}x"

    def test_error_handling(self, temp_workspace, energy_system_config):
        """Test error handling in optimization workflow."""
        # Configure study with invalid parameters
        base_config = SimulationConfig(
            simulation_id="error_test",
            system_config=energy_system_config,
            profile_config={},
            solver_config={},
            output_config={"output_dir": str(temp_workspace)},
        )

        # Create study with problematic configuration
        study_config = StudyConfig(
            study_id="error_handling_test",
            study_type="genetic_algorithm",
            base_config=base_config,
            optimization_variables=[
                {
                    "component": "nonexistent_component",  # Invalid component
                    "parameter": "technical.capacity",
                    "bounds": [0, 100],
                }
            ],
            algorithm_config={"population_size": 5, "max_generations": 2},
        )

        study_service = StudyService()

        # Simulation that sometimes fails
        fail_count = {"count": 0}

        def unreliable_simulation(config):
            fail_count["count"] += 1
            if fail_count["count"] % 3 == 0:  # Fail every 3rd call
                raise RuntimeError("Simulation failed")

            return SimulationResult(
                simulation_id=config["simulation_id"],
                status="optimal",
                solver_metrics={},
                kpis={"total_cost": 10000},
            )

        study_service._run_simulation = unreliable_simulation

        # Run study - should handle failures gracefully
        result = study_service.run_study(study_config)

        # Check that study completed despite failures
        assert "num_simulations" in result
        assert "failed_simulations" in result or "summary_statistics" in result

        # Verify error tracking
        if "failed_simulations" in result:
            assert result["failed_simulations"] > 0, "Should have some failures"

    def test_performance_metrics(self, temp_workspace):
        """Test performance metric collection during optimization."""
        # Create lightweight study for performance testing
        base_config = SimulationConfig(
            simulation_id="perf_test",
            system_config={"components": []},
            profile_config={},
            solver_config={},
            output_config={"output_dir": str(temp_workspace)},
        )

        study_config = StudyConfig(
            study_id="performance_metrics_test",
            study_type="genetic_algorithm",
            base_config=base_config,
            optimization_variables=[
                {"component": "test", "parameter": "value", "bounds": [0, 1]}
            ],
            algorithm_config={
                "population_size": 20,
                "max_generations": 5,
                "track_metrics": True,
            },
        )

        study_service = StudyService()

        # Fast mock simulation
        eval_count = {"count": 0}

        def counting_simulation(config):
            eval_count["count"] += 1
            return SimulationResult(
                simulation_id=f"sim_{eval_count['count']}",
                status="optimal",
                solver_metrics={"solve_time": 0.01},
                kpis={"objective": np.random.random()},
            )

        study_service._run_simulation = counting_simulation

        # Run study
        start_time = time.time()
        result = study_service.run_study(study_config)
        total_time = time.time() - start_time

        # Validate performance metrics
        assert "execution_time" in result
        assert result["execution_time"] > 0
        assert result["execution_time"] <= total_time + 0.1  # Allow small overhead

        assert "num_simulations" in result
        expected_sims = (
            study_config.algorithm_config["population_size"]
            * study_config.algorithm_config["max_generations"]
        )
        assert result["num_simulations"] <= expected_sims

        # Check for detailed metrics if tracking enabled
        if study_config.algorithm_config.get("track_metrics"):
            assert "best_result" in result
            best = result["best_result"]
            if "convergence_history" in best:
                assert len(best["convergence_history"]) > 0

        # Save performance report
        perf_report = {
            "study_id": result["study_id"],
            "total_evaluations": eval_count["count"],
            "execution_time": total_time,
            "evaluations_per_second": eval_count["count"] / total_time,
            "configuration": study_config.algorithm_config,
        }

        perf_file = temp_workspace / "performance_metrics.json"
        with open(perf_file, "w") as f:
            json.dump(perf_report, f, indent=2)

        logger.info(
            f"Performance: {perf_report['evaluations_per_second']:.1f} evals/sec"
        )


# Main test execution
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
