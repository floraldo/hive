#!/usr/bin/env python3
"""Test both rule-based and MILP solvers on yearly 8760-hour scenarios."""

import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psutil

eco_path = Path(__file__).parent.parent / "src"

from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.solver.rule_based_engine import RuleBasedEngine
from ecosystemiser.system_model.components.energy.battery import Battery, BatteryParams, BatteryTechnicalParams
from ecosystemiser.system_model.components.energy.grid import Grid, GridParams, GridTechnicalParams
from ecosystemiser.system_model.components.energy.power_demand import (
    PowerDemand,
    PowerDemandParams,
    PowerDemandTechnicalParams,
)
from ecosystemiser.system_model.components.energy.solar_pv import SolarPV, SolarPVParams, SolarPVTechnicalParams
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel
from ecosystemiser.system_model.system import System

from hive_logging import get_logger

logger = get_logger(__name__)


def load_yearly_profile(profile_name: str) -> np.ndarray:
    """Load a yearly profile from CSV."""
    profile_path = (
        Path(__file__).parent.parent / "data" / "yearly_scenarios" / "profiles" / f"{profile_name}_yearly.csv"
    )

    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    df = pd.read_csv(profile_path)
    profile = df["value"].values

    logger.info(f"Loaded {profile_name}: {len(profile)} timesteps, range [{profile.min():.2f}, {profile.max():.2f}]")
    return profile


def create_yearly_system() -> System:
    """Create system for yearly testing using extracted profiles."""
    N = 8760  # Full year
    system = System(system_id="yearly_test_system", n=N)

    # Load profiles
    solar_profile = load_yearly_profile("solar_pv")
    demand_profile = load_yearly_profile("power_demand")

    # Ensure profiles are correct length
    if len(solar_profile) != N:
        logger.warning(f"Solar profile length {len(solar_profile)} != {N}, truncating/padding")
        solar_profile = np.resize(solar_profile, N)
    if len(demand_profile) != N:
        logger.warning(f"Demand profile length {len(demand_profile)} != {N}, truncating/padding")
        demand_profile = np.resize(demand_profile, N)

    # Create Grid component (from legacy: 800 kW capacity)
    grid_params = GridParams(
        technical=GridTechnicalParams(
            capacity_nominal=800.0,  # kW - legacy value,
            import_tariff=0.25,  # $/kWh,
            feed_in_tariff=0.08,  # $/kWh,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    grid = Grid("Grid", grid_params, N)

    # Create Battery component (from legacy: 300 kWh, 150 kW)
    battery_params = BatteryParams(
        technical=BatteryTechnicalParams(
            capacity_nominal=300.0,  # kWh - legacy value,
            max_charge_rate=150.0,  # kW - legacy value,
            max_discharge_rate=150.0,  # kW - legacy value,
            efficiency_roundtrip=0.95,
            initial_soc_pct=0.5,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    battery = Battery("Battery", battery_params, N)

    # Create Solar PV component (from legacy: 40 kW)
    solar_params = SolarPVParams(
        technical=SolarPVTechnicalParams(
            capacity_nominal=40.0,  # kW - legacy value,
            efficiency_nominal=1.0,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    solar = SolarPV("SolarPV", solar_params, N)
    solar.profile = solar_profile

    # Create Power Demand component (from legacy: 15 kW peak)
    demand_params = PowerDemandParams(
        technical=PowerDemandTechnicalParams(
            capacity_nominal=15.0,  # kW - legacy value,
            peak_demand=15.0,
            load_profile_type="variable",
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    demand = PowerDemand("PowerDemand", demand_params, N)
    demand.profile = demand_profile

    # Add components to system
    system.add_component(grid)
    system.add_component(battery)
    system.add_component(solar)
    system.add_component(demand)

    # Connect components (electrical grid)
    system.connect("Grid", "PowerDemand", "electricity")
    system.connect("Grid", "Battery", "electricity")
    system.connect("Battery", "Grid", "electricity")
    system.connect("SolarPV", "PowerDemand", "electricity")
    system.connect("SolarPV", "Battery", "electricity")
    system.connect("SolarPV", "Grid", "electricity")
    system.connect("Battery", "PowerDemand", "electricity")

    logger.info(f"Created yearly system: {len(system.components)} components, {len(system.flows)} flows")
    return system


def monitor_memory_usage():
    """Get current memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def validate_energy_balance(system: System, tolerance: float = 1e-3) -> dict[str, float]:
    """Validate energy balance for yearly simulation."""
    max_imbalance = 0.0
    total_imbalances = []

    for t in range(system.N):
        sources = 0.0
        sinks = 0.0

        for _flow_key, flow_data in system.flows.items():
            if flow_data["value"] is None or len(flow_data["value"]) <= t:
                continue  # Skip flows with no data

            flow_value = flow_data["value"][t]
            if flow_value is None:
                continue  # Skip None values

            source_comp = system.components[flow_data["source"]]
            target_comp = system.components[flow_data["target"]]

            if source_comp.type in ["generation", "storage", "transmission"]:
                sources += flow_value
            if target_comp.type in ["consumption", "storage", "transmission"]:
                sinks += flow_value

        imbalance = abs(sources - sinks)
        total_imbalances.append(imbalance)
        max_imbalance = max(max_imbalance, imbalance)

    mean_imbalance = np.mean(total_imbalances)
    energy_balance_ok = max_imbalance < tolerance

    return {
        "max_imbalance": max_imbalance,
        "mean_imbalance": mean_imbalance,
        "energy_balance_ok": energy_balance_ok,
        "violation_count": sum(1 for imb in total_imbalances if imb > tolerance),
    }


def analyze_yearly_performance(system: System) -> dict[str, Any]:
    """Analyze system performance over the full year."""
    analysis = {}

    # Solar generation analysis
    solar_total = 0.0
    demand_total = 0.0
    grid_import_total = 0.0
    grid_export_total = 0.0

    for _flow_key, flow_data in system.flows.items():
        if flow_data["value"] is None:
            continue  # Skip flows with no data

        flow_total = np.sum(flow_data["value"])
        if flow_total is None:
            continue  # Skip None totals

        if "SolarPV" in flow_data["source"]:
            solar_total += flow_total
        elif flow_data["target"] == "PowerDemand":
            demand_total += flow_total
        elif flow_data["source"] == "Grid" and flow_data["target"] != "Grid":
            grid_import_total += flow_total
        elif flow_data["target"] == "Grid" and flow_data["source"] != "Grid":
            grid_export_total += flow_total

    # Battery analysis
    battery_comp = system.components.get("Battery")
    if battery_comp and hasattr(battery_comp, "E"):
        yearly_range = np.max(battery_comp.E) - np.min(battery_comp.E)
        equivalent_cycles = yearly_range / battery_comp.E_max
        avg_soc = np.mean(battery_comp.E) / battery_comp.E_max
    else:
        yearly_range = equivalent_cycles = avg_soc = 0.0

    analysis = {
        "solar_generation_mwh": solar_total / 1000,
        "total_demand_mwh": demand_total / 1000,
        "grid_import_mwh": grid_import_total / 1000,
        "grid_export_mwh": grid_export_total / 1000,
        "net_grid_mwh": (grid_import_total - grid_export_total) / 1000,
        "self_consumption_ratio": min(1.0, demand_total / solar_total) if solar_total > 0 else 0,
        "self_sufficiency_ratio": min(1.0, (solar_total - grid_export_total) / demand_total) if demand_total > 0 else 0,
        "battery_cycles": equivalent_cycles,
        "battery_avg_soc": avg_soc,
        "battery_range_kwh": yearly_range,
    }

    return analysis


def test_rule_based_yearly():
    """Test rule-based solver on yearly scenario."""
    logger.info("=== TESTING RULE-BASED SOLVER ON YEARLY SCENARIO ===")

    results = {"test_start": time.time()}

    try:
        # Monitor memory
        initial_memory = monitor_memory_usage()
        logger.info(f"Initial memory: {initial_memory:.1f} MB")

        # Create system
        system = create_yearly_system()
        system_memory = monitor_memory_usage()
        logger.info(f"Memory after system creation: {system_memory:.1f} MB")

        # Run rule-based solver
        logger.info("Running rule-based solver on 8760-hour scenario...")
        solve_start = time.time()
        solver = RuleBasedEngine(system)
        result = solver.solve()
        solve_time = time.time() - solve_start

        solve_memory = monitor_memory_usage()
        logger.info(f"Solve completed: status={result.status}, time={solve_time:.2f}s")
        logger.info(f"Memory after solving: {solve_memory:.1f} MB")

        if result.status == "optimal":
            # Validate energy balance
            balance_results = validate_energy_balance(system)

            # Analyze performance
            performance = analyze_yearly_performance(system)

            results.update(
                {
                    "solver_status": result.status,
                    "solve_time_seconds": solve_time,
                    "memory_usage": {
                        "initial_mb": initial_memory,
                        "peak_mb": solve_memory,
                        "increase_mb": solve_memory - initial_memory,
                    },
                    "energy_balance": balance_results,
                    "yearly_performance": performance,
                    "validation_passed": balance_results["energy_balance_ok"],
                },
            )

            # Log summary
            logger.info("\\n" + "=" * 60)
            logger.info("YEARLY RULE-BASED SOLVER RESULTS")
            logger.info("=" * 60)
            logger.info(f"Solve time: {solve_time:.1f}s")
            logger.info(f"Memory usage: {initial_memory:.1f} -> {solve_memory:.1f} MB")
            logger.info(f"Energy balance: {'PASS' if balance_results['energy_balance_ok'] else 'FAIL'}")
            logger.info(f"Max imbalance: {balance_results['max_imbalance']:.2e}")
            logger.info(f"Solar generation: {performance['solar_generation_mwh']:.1f} MWh")
            logger.info(f"Total demand: {performance['total_demand_mwh']:.1f} MWh")
            logger.info(f"Self-consumption: {performance['self_consumption_ratio']:.1%}")
            logger.info(f"Self-sufficiency: {performance['self_sufficiency_ratio']:.1%}")
            logger.info(f"Battery cycles: {performance['battery_cycles']:.1f}")
            logger.info("=" * 60)
        else:
            logger.error(f"Rule-based solver failed: {result.status}")
            results["validation_passed"] = False

    except Exception as e:
        logger.error(f"Rule-based yearly test failed: {e}")
        results["error"] = str(e)
        results["validation_passed"] = False
        import traceback

        traceback.print_exc()

    results["test_end"] = time.time()
    results["total_time"] = results["test_end"] - results["test_start"]

    return results


def test_milp_yearly():
    """Test MILP solver on yearly scenario (smaller subset due to performance)."""
    logger.info("=== TESTING MILP SOLVER ON YEARLY SUBSET ===")

    # For MILP, use a smaller subset (1 week = 168 hours) due to computational complexity
    N_subset = 168  # 1 week
    logger.info(f"Using {N_subset}-hour subset for MILP testing")

    results = {"test_start": time.time(), "timesteps": N_subset}

    try:
        # Create smaller system
        system = System(system_id="milp_yearly_subset", n=N_subset)

        # Load and truncate profiles
        solar_profile = load_yearly_profile("solar_pv")[:N_subset]
        demand_profile = load_yearly_profile("power_demand")[:N_subset]

        # Create components (same as yearly but smaller N)
        grid_params = GridParams(
            technical=GridTechnicalParams(
                capacity_nominal=800.0,
                import_tariff=0.25,
                feed_in_tariff=0.08,
                fidelity_level=FidelityLevel.SIMPLE,
            ),
        )
        grid = Grid("Grid", grid_params, N_subset)

        battery_params = BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=300.0,
                max_charge_rate=150.0,
                max_discharge_rate=150.0,
                efficiency_roundtrip=0.95,
                initial_soc_pct=0.5,
                fidelity_level=FidelityLevel.SIMPLE,
            ),
        )
        battery = Battery("Battery", battery_params, N_subset)

        solar_params = SolarPVParams(
            technical=SolarPVTechnicalParams(
                capacity_nominal=40.0,
                efficiency_nominal=1.0,
                fidelity_level=FidelityLevel.SIMPLE,
            ),
        )
        solar = SolarPV("SolarPV", solar_params, N_subset)
        solar.profile = solar_profile

        demand_params = PowerDemandParams(
            technical=PowerDemandTechnicalParams(
                capacity_nominal=15.0,
                peak_demand=15.0,
                load_profile_type="variable",
                fidelity_level=FidelityLevel.SIMPLE,
            ),
        )
        demand = PowerDemand("PowerDemand", demand_params, N_subset)
        demand.profile = demand_profile

        # Add components and connections
        system.add_component(grid)
        system.add_component(battery)
        system.add_component(solar)
        system.add_component(demand)

        system.connect("Grid", "PowerDemand", "electricity")
        system.connect("Grid", "Battery", "electricity")
        system.connect("Battery", "Grid", "electricity")
        system.connect("SolarPV", "PowerDemand", "electricity")
        system.connect("SolarPV", "Battery", "electricity")
        system.connect("SolarPV", "Grid", "electricity")
        system.connect("Battery", "PowerDemand", "electricity")

        # Run MILP solver
        initial_memory = monitor_memory_usage()
        solve_start = time.time()

        solver = MILPSolver(system)
        result = solver.solve()

        solve_time = time.time() - solve_start
        solve_memory = monitor_memory_usage()

        logger.info(f"MILP solve completed: status={result.status}, time={solve_time:.2f}s")

        if result.status == "optimal":
            # Validate and analyze
            balance_results = validate_energy_balance(system)
            performance = analyze_yearly_performance(system)

            results.update(
                {
                    "solver_status": result.status,
                    "solve_time_seconds": solve_time,
                    "memory_usage": {
                        "initial_mb": initial_memory,
                        "peak_mb": solve_memory,
                        "increase_mb": solve_memory - initial_memory,
                    },
                    "energy_balance": balance_results,
                    "performance": performance,
                    "validation_passed": balance_results["energy_balance_ok"],
                },
            )

            logger.info("\\n" + "=" * 60)
            logger.info("MILP SOLVER SUBSET RESULTS")
            logger.info("=" * 60)
            logger.info(f"Timesteps: {N_subset} hours")
            logger.info(f"Solve time: {solve_time:.1f}s")
            logger.info(f"Energy balance: {'PASS' if balance_results['energy_balance_ok'] else 'FAIL'}")
            logger.info("=" * 60)
        else:
            logger.error(f"MILP solver failed: {result.status}")
            results["validation_passed"] = False

    except Exception as e:
        logger.error(f"MILP yearly test failed: {e}")
        results["error"] = str(e)
        results["validation_passed"] = False
        import traceback

        traceback.print_exc()

    results["test_end"] = time.time()
    results["total_time"] = results["test_end"] - results["test_start"]

    return results


def main():
    """Main execution."""
    logger.info("Starting yearly scenario validation tests")

    all_results = {"test_suite_start": time.time(), "rule_based_yearly": None, "milp_subset": None}

    # Test rule-based solver on full year
    all_results["rule_based_yearly"] = test_rule_based_yearly()

    # Test MILP solver on subset
    all_results["milp_subset"] = test_milp_yearly()

    all_results["test_suite_end"] = time.time()
    all_results["total_suite_time"] = all_results["test_suite_end"] - all_results["test_suite_start"]

    # Save results
    results_dir = Path(__file__).parent.parent / "data"
    results_path = results_dir / "yearly_validation_results.json"

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

    json_results = convert_for_json(all_results)

    with open(results_path, "w") as f:
        json.dump(json_results, f, indent=2)

    # Print summary
    logger.info("\\n" + "=" * 80)
    logger.info("YEARLY SCENARIO VALIDATION SUMMARY")
    logger.info("=" * 80)

    rule_passed = all_results["rule_based_yearly"]["validation_passed"] if all_results["rule_based_yearly"] else False
    milp_passed = all_results["milp_subset"]["validation_passed"] if all_results["milp_subset"] else False

    logger.info(f"Rule-based yearly (8760h): {'PASSED' if rule_passed else 'FAILED'}")
    logger.info(f"MILP subset (168h): {'PASSED' if milp_passed else 'FAILED'}")
    logger.info(f"Overall validation: {'PASSED' if rule_passed and milp_passed else 'FAILED'}")
    logger.info(f"Total test time: {all_results['total_suite_time']:.1f}s")
    logger.info(f"Results saved: {results_path}")
    logger.info("=" * 80)

    return rule_passed and milp_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
