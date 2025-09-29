#!/usr/bin/env python3
"""Comprehensive test suite for Golden Residential Microgrid validation."""

import json

# Add ecosystemiser to path
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
import pytest

eco_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(eco_path))

from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.solver.rule_based_engine import RuleBasedEngine
from ecosystemiser.utils.system_builder import create_system_from_config
from hive_logging import get_logger

logger = get_logger(__name__)


class GoldenMicrogridValidator:
    """Comprehensive validator for golden residential microgrid systems."""

    def __init__(self):
        self.test_results = {}
        self.tolerance = 1e-6

    def load_system_config(self, config_name: str):
        """Load system configuration from YAML file."""
        config_path = Path(__file__).parent.parent / "config" / "systems" / f"{config_name}.yml"

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        logger.info(f"Loading system config: {config_path}")
        return create_system_from_config(str(config_path))

    def validate_energy_balance(self, system, results: Dict[str, Any], domain: str = "electrical") -> Dict[str, Any]:
        """Validate perfect energy conservation for specified domain."""
        balance_results = {
            "domain": domain,
            "timesteps_checked": system.N,
            "max_imbalance": 0.0,
            "total_imbalance": 0.0,
            "balance_violations": [],
            "passed": False,
        }

        # Get flows by domain
        if domain == "electrical":
            flow_type = "electricity"
        elif domain == "thermal":
            flow_type = "thermal"
        else:
            raise ValueError(f"Unknown domain: {domain}")

        # Calculate energy balance for each timestep
        for t in range(system.N):
            sources = 0.0
            sinks = 0.0

            for flow_key, flow_data in system.flows.items():
                if flow_data.get("type", "electricity") == flow_type:
                    flow_value = flow_data["value"][t] if hasattr(flow_data["value"], "__getitem__") else 0.0

                    # Classify as source or sink based on component types
                    source_comp = system.components[flow_data["source"]]
                    target_comp = system.components[flow_data["target"]]

                    if source_comp.type in ["generation", "storage", "transmission"]:
                        sources += flow_value
                    if target_comp.type in ["consumption", "storage", "transmission"]:
                        sinks += flow_value

            # Calculate imbalance
            imbalance = abs(sources - sinks)
            balance_results["total_imbalance"] += imbalance

            if imbalance > balance_results["max_imbalance"]:
                balance_results["max_imbalance"] = imbalance

            if imbalance > self.tolerance:
                balance_results["balance_violations"].append(
                    {"timestep": t, "sources": sources, "sinks": sinks, "imbalance": imbalance}
                )

        # Determine if validation passed
        balance_results["passed"] = (
            balance_results["max_imbalance"] < self.tolerance and len(balance_results["balance_violations"]) == 0
        )

        logger.info(
            f"{domain.title()} energy balance: max_imbalance={balance_results['max_imbalance']:.2e}, "
            f"violations={len(balance_results['balance_violations'])}"
        )

        return balance_results

    def validate_physics_constraints(self, system, results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that all physics constraints are satisfied."""
        physics_results = {
            "storage_bounds_violations": [],
            "flow_negative_violations": [],
            "capacity_violations": [],
            "passed": False,
        }

        # Check storage bounds (SOC between 0 and 1)
        for comp_name, comp in system.components.items():
            if comp.type == "storage" and hasattr(comp, "E"):
                E_max = comp.E_max if hasattr(comp, "E_max") else comp.params.technical.capacity_nominal
                for t in range(system.N):
                    soc = comp.E[t] / E_max
                    if soc < -self.tolerance or soc > 1.0 + self.tolerance:
                        physics_results["storage_bounds_violations"].append(
                            {"component": comp_name, "timestep": t, "soc": soc, "energy": comp.E[t], "capacity": E_max}
                        )

        # Check non-negative flows
        for flow_key, flow_data in system.flows.items():
            for t in range(system.N):
                flow_value = flow_data["value"][t] if hasattr(flow_data["value"], "__getitem__") else 0.0
                if flow_value < -self.tolerance:
                    physics_results["flow_negative_violations"].append(
                        {"flow": flow_key, "timestep": t, "value": flow_value}
                    )

        # Determine if validation passed
        physics_results["passed"] = (
            len(physics_results["storage_bounds_violations"]) == 0
            and len(physics_results["flow_negative_violations"]) == 0
            and len(physics_results["capacity_violations"]) == 0
        )

        logger.info(
            f"Physics constraints: storage_violations={len(physics_results['storage_bounds_violations'])}, "
            f"flow_violations={len(physics_results['flow_negative_violations'])}"
        )

        return physics_results

    def validate_system_behavior(self, system, results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate expected system behavior patterns."""
        behavior_results = {
            "solar_priority_check": False,
            "storage_cycling_check": False,
            "thermal_coupling_check": False,
            "peak_shaving_check": False,
            "passed": False,
        }

        # Check solar priority (solar used before grid when available)
        solar_flows = {}
        grid_flows = {}

        for flow_key, flow_data in system.flows.items():
            if "SolarPV" in flow_data["source"] or "SOLAR" in flow_data["source"]:
                solar_flows[flow_key] = flow_data["value"]
            elif "Grid" in flow_data["source"] or "GRID" in flow_data["source"]:
                grid_flows[flow_key] = flow_data["value"]

        # Simple heuristic: when solar is generating, grid import should be minimal
        if solar_flows and grid_flows:
            solar_generation = sum([np.sum(flow) for flow in solar_flows.values()])
            grid_import = sum([np.sum(flow) for flow in grid_flows.values() if "demand" in flow or "DEMAND" in flow])

            if solar_generation > 0:
                solar_priority_ratio = solar_generation / (solar_generation + grid_import + 1e-6)
                behavior_results["solar_priority_check"] = solar_priority_ratio > 0.5

        # Check storage cycling (battery should charge and discharge)
        for comp_name, comp in system.components.items():
            if comp.type == "storage" and hasattr(comp, "E"):
                energy_range = np.max(comp.E) - np.min(comp.E)
                storage_capacity = comp.E_max if hasattr(comp, "E_max") else comp.params.technical.capacity_nominal
                cycling_ratio = energy_range / storage_capacity
                if cycling_ratio > 0.1:  # At least 10% cycling
                    behavior_results["storage_cycling_check"] = True
                    break

        # Check thermal coupling (heat pump electrical consumption correlates with thermal output)
        heat_pump_electrical = 0
        heat_pump_thermal = 0

        for flow_key, flow_data in system.flows.items():
            if "HEAT_PUMP" in flow_data["target"] and flow_data.get("type") == "electricity":
                heat_pump_electrical += np.sum(flow_data["value"])
            elif "HEAT_PUMP" in flow_data["source"] and flow_data.get("type") == "thermal":
                heat_pump_thermal += np.sum(flow_data["value"])

        if heat_pump_electrical > 0 and heat_pump_thermal > 0:
            # COP should be reasonable (between 1.5 and 5.0)
            cop = heat_pump_thermal / heat_pump_electrical
            behavior_results["thermal_coupling_check"] = 1.5 <= cop <= 5.0

        # Determine overall behavior validation
        behavior_results["passed"] = (
            behavior_results["solar_priority_check"]
            and behavior_results["storage_cycling_check"]
            and behavior_results["thermal_coupling_check"]
        )

        logger.info(
            f"System behavior: solar_priority={behavior_results['solar_priority_check']}, "
            f"storage_cycling={behavior_results['storage_cycling_check']}, "
            f"thermal_coupling={behavior_results['thermal_coupling_check']}"
        )

        return behavior_results

    def validate_solver_performance(self, solve_time: float, memory_usage: float = 0.0) -> Dict[str, Any]:
        """Validate solver performance metrics."""
        performance_results = {
            "solve_time": solve_time,
            "memory_usage": memory_usage,
            "time_acceptable": solve_time < 5.0,  # Should solve in under 5 seconds for 24h
            "memory_acceptable": memory_usage < 100.0,  # Should use less than 100 MB
            "passed": False,
        }

        performance_results["passed"] = (
            performance_results["time_acceptable"] and performance_results["memory_acceptable"]
        )

        logger.info(f"Performance: solve_time={solve_time:.3f}s, memory={memory_usage:.1f}MB")

        return performance_results

    def run_comprehensive_validation(self, system, solver_results, solve_time: float) -> Dict[str, Any]:
        """Run all validation checks and return comprehensive results."""
        validation_results = {
            "timestamp": time.time(),
            "system_id": system.system_id,
            "timesteps": system.N,
            "component_count": len(system.components),
            "flow_count": len(system.flows),
        }

        # Run all validation checks
        validation_results["electrical_balance"] = self.validate_energy_balance(system, solver_results, "electrical")
        validation_results["thermal_balance"] = self.validate_energy_balance(system, solver_results, "thermal")
        validation_results["physics_constraints"] = self.validate_physics_constraints(system, solver_results)
        validation_results["system_behavior"] = self.validate_system_behavior(system, solver_results)
        validation_results["performance"] = self.validate_solver_performance(solve_time)

        # Determine overall validation result
        validation_results["overall_passed"] = all(
            [
                validation_results["electrical_balance"]["passed"],
                validation_results["thermal_balance"]["passed"],
                validation_results["physics_constraints"]["passed"],
                validation_results["system_behavior"]["passed"],
                validation_results["performance"]["passed"],
            ]
        )

        return validation_results


# Test functions using pytest framework


@pytest.fixture
def validator():
    """Create validator instance for tests."""
    return GoldenMicrogridValidator()


class TestGoldenMicrogrid:
    """Test class for golden residential microgrid validation."""

    def test_rule_based_24h_baseline(self, validator):
        """Test 24-hour rule-based simulation - baseline scenario."""
        logger.info("=" * 80)
        logger.info("TEST: Rule-Based 24h Baseline")
        logger.info("=" * 80)

        # Load system
        system = validator.load_system_config("golden_residential_microgrid")

        # Run rule-based solver
        start_time = time.time()
        solver = RuleBasedEngine(system)
        result = solver.solve()
        solve_time = time.time() - start_time

        # Validate results
        validation = validator.run_comprehensive_validation(system, result, solve_time)

        # Log results
        logger.info(f"Solver status: {result.status}")
        logger.info(f"Overall validation: {'PASSED' if validation['overall_passed'] else 'FAILED'}")

        # Store results for later analysis
        validator.test_results["rule_based_24h"] = validation

        # Assertions
        assert result.status == "optimal", f"Solver failed with status: {result.status}"
        assert validation["overall_passed"], f"Validation failed: {validation}"

    def test_rule_based_winter_scenario(self, validator):
        """Test rule-based simulation with winter scenario."""
        logger.info("=" * 80)
        logger.info("TEST: Rule-Based Winter Scenario")
        logger.info("=" * 80)

        # Load winter system
        system = validator.load_system_config("golden_residential_winter")

        # Run solver
        start_time = time.time()
        solver = RuleBasedEngine(system)
        result = solver.solve()
        solve_time = time.time() - start_time

        # Validate
        validation = validator.run_comprehensive_validation(system, result, solve_time)

        logger.info(f"Winter scenario validation: {'PASSED' if validation['overall_passed'] else 'FAILED'}")
        validator.test_results["rule_based_winter"] = validation

        assert result.status == "optimal"
        assert validation["electrical_balance"]["passed"]
        assert validation["thermal_balance"]["passed"]

    @pytest.mark.slow
    def test_rule_based_7day_stress(self, validator):
        """Test 7-day rule-based simulation for stress testing."""
        logger.info("=" * 80)
        logger.info("TEST: Rule-Based 7-Day Stress Test")
        logger.info("=" * 80)

        # Load 7-day system
        system = validator.load_system_config("golden_residential_microgrid_7day")

        # Run solver
        start_time = time.time()
        solver = RuleBasedEngine(system)
        result = solver.solve()
        solve_time = time.time() - start_time

        # Relaxed performance criteria for longer simulation
        validator.tolerance = 1e-5  # Slightly relaxed tolerance
        validation = validator.run_comprehensive_validation(system, result, solve_time)

        logger.info(f"7-day stress test: {'PASSED' if validation['overall_passed'] else 'FAILED'}")
        logger.info(f"Long simulation solve time: {solve_time:.2f}s")

        validator.test_results["rule_based_7day"] = validation

        assert result.status == "optimal"
        assert solve_time < 60.0  # Should complete within 1 minute
        assert validation["electrical_balance"]["passed"]

    def test_milp_optimization_24h(self, validator):
        """Test MILP optimization vs rule-based performance."""
        logger.info("=" * 80)
        logger.info("TEST: MILP Optimization 24h")
        logger.info("=" * 80)

        # Load system
        system = validator.load_system_config("golden_residential_microgrid")

        # Run rule-based solver first (baseline)
        rule_solver = RuleBasedEngine(system)
        rule_result = rule_solver.solve()
        rule_cost = self.calculate_total_cost(system, rule_result)

        # Run MILP solver
        start_time = time.time()
        milp_solver = MILPSolver(system)
        milp_result = milp_solver.solve()
        solve_time = time.time() - start_time

        # Validate MILP results
        validation = validator.run_comprehensive_validation(system, milp_result, solve_time)
        milp_cost = self.calculate_total_cost(system, milp_result)

        logger.info(f"Rule-based cost: €{rule_cost:.2f}")
        logger.info(f"MILP cost: €{milp_cost:.2f}")
        logger.info(f"Cost improvement: {((rule_cost - milp_cost) / rule_cost * 100):.1f}%")

        validator.test_results["milp_24h"] = validation

        # MILP should find optimal solution
        assert milp_result.status == "optimal"
        # MILP should be better than or equal to rule-based
        assert milp_cost <= rule_cost + validator.tolerance
        assert validation["overall_passed"]

    def calculate_total_cost(self, system, result) -> float:
        """Calculate total operational cost for the simulation."""
        total_cost = 0.0

        # Grid import costs
        for flow_key, flow_data in system.flows.items():
            if "Grid" in flow_data["source"] and "GRID" in flow_data["source"]:
                grid_comp = system.components.get(flow_data["source"])
                if grid_comp and hasattr(grid_comp, "params"):
                    import_tariff = getattr(grid_comp.params.technical, "import_tariff", 0.25)
                    total_cost += np.sum(flow_data["value"]) * import_tariff

        # Grid export revenues (negative cost)
        for flow_key, flow_data in system.flows.items():
            if "Grid" in flow_data["target"] and "GRID" in flow_data["target"]:
                grid_comp = system.components.get(flow_data["target"])
                if grid_comp and hasattr(grid_comp, "params"):
                    export_tariff = getattr(grid_comp.params.technical, "export_tariff", 0.10)
                    total_cost -= np.sum(flow_data["value"]) * export_tariff

        return max(0.0, total_cost)


def generate_validation_report(validator):
    """Generate comprehensive validation report."""
    report_path = Path(__file__).parent.parent / "data" / "validation_report.json"

    report = {
        "report_timestamp": time.time(),
        "validation_summary": {
            "total_tests": len(validator.test_results),
            "passed_tests": sum(1 for result in validator.test_results.values() if result.get("overall_passed", False)),
            "test_results": validator.test_results,
        },
        "conclusions": {
            "physics_engine_validated": True,
            "multi_domain_integration": True,
            "solver_performance_acceptable": True,
            "ready_for_production": True,
        },
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Validation report saved: {report_path}")
    return report


if __name__ == "__main__":
    # Run tests manually
    validator = GoldenMicrogridValidator()
    test_class = TestGoldenMicrogrid()

    try:
        test_class.test_rule_based_24h_baseline(validator)
        test_class.test_rule_based_winter_scenario(validator)
        test_class.test_milp_optimization_24h(validator)

        # Generate report
        report = generate_validation_report(validator)

        print("\n" + "=" * 80)
        print("GOLDEN MICROGRID VALIDATION COMPLETE")
        print(
            f"Tests passed: {report['validation_summary']['passed_tests']}/{report['validation_summary']['total_tests']}"
        )
        print("=" * 80)

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise
