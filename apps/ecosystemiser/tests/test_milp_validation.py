#!/usr/bin/env python3
"""MILP solver validation and comparison with rule-based."""

import json
import time
from pathlib import Path

import numpy as np

eco_path = Path(__file__).parent.parent / "src"

from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.solver.rule_based_engine import RuleBasedEngine
from ecosystemiser.system_model.components.energy.battery import (
    Battery,
    BatteryParams,
    BatteryTechnicalParams,
)
from ecosystemiser.system_model.components.energy.grid import (
    Grid,
    GridParams,
    GridTechnicalParams,
)
from ecosystemiser.system_model.components.energy.power_demand import (
    PowerDemand,
    PowerDemandParams,
    PowerDemandTechnicalParams,
)
from ecosystemiser.system_model.components.energy.solar_pv import (
    SolarPV,
    SolarPVParams,
    SolarPVTechnicalParams,
)
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel
from ecosystemiser.system_model.system import System

from hive_logging import get_logger

logger = get_logger(__name__)


def create_optimization_test_system():
    """Create system for MILP optimization testing."""
    N = 24
    system = System(system_id="milp_optimization_test", n=N)

    # Use profiles that create optimization opportunities
    # More variable solar and demand to create price arbitrage opportunities
    solar_profile = np.array(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,  # Night,
            0.2,
            0.4,
            0.6,
            0.8,
            0.9,
            1.0,  # Morning to noon,
            0.9,
            0.8,
            0.6,
            0.4,
            0.2,  # Afternoon,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,  # Evening/night
        ],
    )

    # Demand with clear peaks for optimization
    demand_profile = np.array(
        [
            0.3,
            0.3,
            0.3,
            0.3,
            0.3,
            0.3,
            0.4,  # Night low,
            0.8,
            0.9,  # Morning peak,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.5,  # Day moderate,
            1.0,
            0.9,
            0.8,  # Evening peak,
            0.4,
            0.3,
            0.3,  # Night low
        ],
    )

    # Create components with parameters that enable meaningful optimization
    grid_params = GridParams(
        technical=GridTechnicalParams(
            capacity_nominal=50.0,  # Smaller grid capacity to encourage storage use,
            import_tariff=0.30,  # Higher import tariff,
            export_tariff=0.05,  # Lower export tariff to discourage export,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    grid = Grid("Grid", grid_params, N)

    battery_params = BatteryParams(
        technical=BatteryTechnicalParams(
            capacity_nominal=20.0,  # Larger battery for more optimization potential,
            max_charge_rate=8.0,  # Higher charge rate,
            max_discharge_rate=8.0,  # Higher discharge rate,
            efficiency_roundtrip=0.90,  # Realistic efficiency for optimization,
            initial_soc_pct=0.5,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    battery = Battery("Battery", battery_params, N)

    solar_params = SolarPVParams(
        technical=SolarPVTechnicalParams(
            capacity_nominal=30.0,  # 30 kW solar,
            efficiency_nominal=1.0,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    solar = SolarPV("SolarPV", solar_params, N)
    solar.profile = solar_profile

    demand_params = PowerDemandParams(
        technical=PowerDemandTechnicalParams(
            capacity_nominal=15.0,  # 15 kW peak demand,
            peak_demand=15.0,
            load_profile_type="variable",
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    demand = PowerDemand("PowerDemand", demand_params, N)
    demand.profile = demand_profile

    # Add components
    system.add_component(grid)
    system.add_component(battery)
    system.add_component(solar)
    system.add_component(demand)

    # Connect components
    system.connect("Grid", "PowerDemand", "electricity")
    system.connect("Grid", "Battery", "electricity")
    system.connect("Battery", "Grid", "electricity")
    system.connect("SolarPV", "PowerDemand", "electricity")
    system.connect("SolarPV", "Battery", "electricity")
    system.connect("SolarPV", "Grid", "electricity")
    system.connect("Battery", "PowerDemand", "electricity")

    return system


def calculate_operational_cost(system):
    """Calculate total operational cost based on grid interactions."""
    total_cost = 0.0

    # Get grid component for tariff information
    grid_comp = system.components.get("Grid")
    if not grid_comp:
        return 0.0

    import_tariff = grid_comp.params.technical.import_tariff
    export_tariff = grid_comp.params.technical.export_tariff

    # Calculate import costs and export revenues
    for _flow_key, flow_data in system.flows.items():
        if flow_data["source"] == "Grid":
            # Grid import (cost)
            total_cost += np.sum(flow_data["value"]) * import_tariff
        elif flow_data["target"] == "Grid" and flow_data["source"] != "Grid":
            # Export to grid (revenue, negative cost)
            total_cost -= np.sum(flow_data["value"]) * export_tariff

    return total_cost


def analyze_battery_strategy(system, label=""):
    """Analyze battery charging/discharging strategy."""
    battery_comp = system.components.get("Battery")
    if not battery_comp or not hasattr(battery_comp, "E"):
        return {}

    # Get battery flows
    charge_flows = []
    discharge_flows = []

    for _flow_key, flow_data in system.flows.items():
        if flow_data["target"] == "Battery":
            charge_flows.extend(flow_data["value"])
        elif flow_data["source"] == "Battery":
            discharge_flows.extend(flow_data["value"])

    total_charge = sum(charge_flows) if charge_flows else 0
    total_discharge = sum(discharge_flows) if discharge_flows else 0

    energy_range = np.max(battery_comp.E) - np.min(battery_comp.E)
    cycling_ratio = energy_range / battery_comp.E_max

    strategy = {
        "total_charge": float(total_charge),
        "total_discharge": float(total_discharge),
        "energy_range": float(energy_range),
        "cycling_ratio": float(cycling_ratio),
        "final_soc": float(battery_comp.E[-1] / battery_comp.E_max),
    }

    logger.info(f"{label} Battery Strategy:")
    logger.info(f"  Charge: {total_charge:.1f} kWh, Discharge: {total_discharge:.1f} kWh")
    logger.info(f"  Cycling: {cycling_ratio:.1%}, Final SOC: {strategy['final_soc']:.1%}")

    return strategy


def run_milp_validation():
    """Run MILP validation against rule-based solver."""
    logger.info("=" * 80)
    logger.info("MILP OPTIMIZATION VALIDATION")
    logger.info("=" * 80)

    results = {"validation_start": time.time()}

    try:
        # Create system
        system = create_optimization_test_system()
        logger.info(f"Created optimization test system with {len(system.components)} components")

        # Run rule-based solver first (baseline)
        logger.info("\n--- RULE-BASED SOLVER (Baseline) ---")
        rule_start = time.time()
        rule_solver = RuleBasedEngine(system)
        rule_result = rule_solver.solve()
        rule_time = time.time() - rule_start

        if rule_result.status != "optimal":
            raise Exception(f"Rule-based solver failed: {rule_result.status}")

        rule_cost = calculate_operational_cost(system)
        rule_strategy = analyze_battery_strategy(system, "Rule-based")

        logger.info(f"Rule-based: cost=€{rule_cost:.2f}, time={rule_time:.4f}s")

        # Store rule-based results
        rule_flows = {}
        for flow_key, flow_data in system.flows.items():
            rule_flows[flow_key] = np.array(flow_data["value"]).tolist()

        # Reset system for MILP (create fresh instance)
        system = create_optimization_test_system()

        # Run MILP solver
        logger.info("\n--- MILP SOLVER (Optimization) ---")
        milp_start = time.time()

        try:
            milp_solver = MILPSolver(system)
            milp_result = milp_solver.solve()
            milp_time = time.time() - milp_start

            if milp_result.status == "optimal":
                milp_cost = calculate_operational_cost(system)
                milp_strategy = analyze_battery_strategy(system, "MILP")

                logger.info(f"MILP: cost=€{milp_cost:.2f}, time={milp_time:.4f}s")

                # Calculate improvement
                cost_improvement = ((rule_cost - milp_cost) / rule_cost * 100) if rule_cost > 0 else 0
                optimization_valid = milp_cost <= rule_cost + 1e-3  # MILP should be better or equal

                logger.info(f"Cost improvement: {cost_improvement:.1f}%")
                logger.info(f"Optimization valid: {optimization_valid}")

                results.update(
                    {
                        "rule_based_cost": float(rule_cost),
                        "milp_cost": float(milp_cost),
                        "cost_improvement_pct": float(cost_improvement),
                        "rule_based_time": float(rule_time),
                        "milp_time": float(milp_time),
                        "rule_based_strategy": rule_strategy,
                        "milp_strategy": milp_strategy,
                        "optimization_valid": optimization_valid,
                        "milp_status": milp_result.status,
                        "milp_success": True,
                    },
                )

            else:
                logger.error(f"MILP solver failed: {milp_result.status}")
                results.update(
                    {
                        "milp_success": False,
                        "milp_status": milp_result.status,
                        "milp_error": "Solver did not reach optimal status",
                    },
                )

        except Exception as milp_e:
            logger.error(f"MILP solver exception: {milp_e}")
            results.update({"milp_success": False, "milp_error": str(milp_e)})

        # Overall validation
        results["validation_passed"] = (
            rule_result.status == "optimal"
            and results.get("milp_success", False)
            and results.get("optimization_valid", False)
        )

        # Log summary
        logger.info("\n" + "=" * 60)
        logger.info("MILP VALIDATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Rule-based solver: {'SUCCESS' if rule_result.status == 'optimal' else 'FAILED'}")
        logger.info(f"MILP solver: {'SUCCESS' if results.get('milp_success', False) else 'FAILED'}")
        if results.get("milp_success", False):
            logger.info(f"Cost optimization: {results.get('cost_improvement_pct', 0):.1f}% improvement")
            logger.info(f"Optimization validity: {'PASS' if results.get('optimization_valid', False) else 'FAIL'}")
        logger.info(f"Overall validation: {'PASSED' if results['validation_passed'] else 'FAILED'}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Validation failed with exception: {e}")
        results["error"] = str(e)
        results["validation_passed"] = False
        import traceback

        traceback.print_exc()

    results["validation_end"] = time.time()
    results["total_time"] = results["validation_end"] - results["validation_start"]

    return results


def main():
    """Main execution."""
    results = run_milp_validation()

    # Save results
    results_dir = Path(__file__).parent.parent / "data"
    results_dir.mkdir(parents=True, exist_ok=True)

    results_path = results_dir / "milp_validation_results.json"

    # Convert numpy types for JSON
    def convert_for_json(obj):
        if isinstance(obj, (np.integer, np.floating, np.bool_)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convert_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_for_json(v) for v in obj]
        return obj

    json_results = convert_for_json(results)

    with open(results_path, "w") as f:
        json.dump(json_results, f, indent=2)

    logger.info("\nMILP validation complete!")
    logger.info(f"Results saved to: {results_path}")
    logger.info(f"Status: {'PASSED' if results.get('validation_passed', False) else 'FAILED'}")

    return results.get("validation_passed", False)


def test_milp_validation():
    """Test MILP validation as pytest test."""
    success = main()
    assert success, "MILP validation failed"


def test_milp_optimization_system_creation():
    """Test creation of optimization test system."""
    system = create_optimization_test_system()
    assert system is not None
    assert len(system.components) == 4
    assert "Battery" in system.components
    assert "Grid" in system.components


def test_operational_cost_calculation():
    """Test operational cost calculation function."""
    system = create_optimization_test_system()
    # Run solver to generate flows
    solver = RuleBasedEngine(system)
    solver.solve()
    cost = calculate_operational_cost(system)
    assert isinstance(cost, float)
    assert cost != 0.0  # Should have some cost


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
