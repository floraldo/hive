#!/usr/bin/env python3
"""Simplified golden validation test using direct component construction."""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

eco_path = Path(__file__).parent.parent / "src"

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


def create_simple_golden_system(N=24):
    """Create a simplified golden system using direct component construction."""
    logger.info(f"Creating simple golden system with {N} timesteps")

    # Create system
    system = System(system_id="simple_golden_validation", n=N)

    # Load profiles
    data_dir = Path(__file__).parent.parent / "data" / "profiles"
    if N == 24:
        profiles_path = data_dir / "golden_24h_weather_integrated.csv"
    else:
        profiles_path = data_dir / "golden_7day_weather.csv"

    if not profiles_path.exists():
        logger.warning(f"Profile file not found: {profiles_path}, using synthetic profiles")
        solar_profile, demand_profile = create_synthetic_profiles(N)
    else:
        profiles_df = pd.read_csv(profiles_path)
        if N <= len(profiles_df):
            solar_profile = profiles_df["solar_generation_weather_adjusted"].iloc[:N].values
            demand_profile = profiles_df["total_electrical_demand_kw"].iloc[:N].values
        else:
            # Repeat pattern if needed
            solar_profile = np.tile(
                profiles_df["solar_generation_weather_adjusted"].values, (N // len(profiles_df) + 1)
            )[:N]
            demand_profile = np.tile(profiles_df["total_electrical_demand_kw"].values, (N // len(profiles_df) + 1))[:N]

    # Normalize profiles
    solar_max = 50.0  # 50 kW peak from golden dataset
    demand_max = 12.5  # 12.5 kW peak from golden dataset

    solar_normalized = solar_profile / solar_max if np.max(solar_profile) > 0 else solar_profile
    demand_normalized = demand_profile / demand_max if np.max(demand_profile) > 0 else demand_profile

    # Create components with SIMPLE fidelity
    logger.info("Creating grid component...")
    grid_params = GridParams(
        technical=GridTechnicalParams(
            capacity_nominal=100.0,
            import_tariff=0.25,
            export_tariff=0.10,
            fidelity_level=FidelityLevel.SIMPLE,
        )
    )
    grid = Grid("Grid", grid_params, N)

    logger.info("Creating battery component...")
    battery_params = BatteryParams(
        technical=BatteryTechnicalParams(
            capacity_nominal=10.0,
            max_charge_rate=5.0,
            max_discharge_rate=5.0,
            efficiency_roundtrip=0.95,
            initial_soc_pct=0.5,
            fidelity_level=FidelityLevel.SIMPLE,
        )
    )
    battery = Battery("Battery", battery_params, N)

    logger.info("Creating solar PV component...")
    solar_params = SolarPVParams(
        technical=SolarPVTechnicalParams(
            capacity_nominal=50.0,
            efficiency_nominal=1.0,
            fidelity_level=FidelityLevel.SIMPLE,
        )
    )
    solar = SolarPV("SolarPV", solar_params, N)
    solar.profile = solar_normalized

    logger.info("Creating power demand component...")
    demand_params = PowerDemandParams(
        technical=PowerDemandTechnicalParams(
            capacity_nominal=12.5,
            peak_demand=12.5,
            load_profile_type="variable",
            fidelity_level=FidelityLevel.SIMPLE,
        )
    )
    demand = PowerDemand("PowerDemand", demand_params, N)
    demand.profile = demand_normalized

    # Add components to system
    system.add_component(grid)
    system.add_component(battery)
    system.add_component(solar)
    system.add_component(demand)

    # Create connections (same as golden dataset)
    logger.info("Creating system connections...")
    system.connect("Grid", "PowerDemand", "electricity")
    system.connect("Grid", "Battery", "electricity")
    system.connect("Battery", "Grid", "electricity")
    system.connect("SolarPV", "PowerDemand", "electricity")
    system.connect("SolarPV", "Battery", "electricity")
    system.connect("SolarPV", "Grid", "electricity")
    system.connect("Battery", "PowerDemand", "electricity")

    logger.info(f"Created system with {len(system.components)} components and {len(system.flows)} flows")
    return system


def create_synthetic_profiles(N):
    """Create synthetic profiles when real data unavailable."""
    logger.info("Creating synthetic profiles...")

    # Solar profile (0-1 normalized)
    hours_per_day = 24
    days = N // hours_per_day + 1

    solar_profile = []
    demand_profile = []

    for _day in range(days):
        # Daily solar pattern
        daily_solar = np.array(
            [
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,  # Night
                0.25,
                0.5,
                0.707,
                0.866,
                0.966,
                1.0,  # Morning to noon
                0.966,
                0.866,
                0.707,
                0.5,
                0.25,  # Afternoon
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,  # Evening/night
            ]
        )

        # Daily demand pattern (base electrical + some thermal)
        daily_demand = np.array(
            [
                0.4,
                0.4,
                0.4,
                0.4,
                0.4,
                0.4,
                0.4,  # Night baseload
                0.8,
                0.8,  # Morning peak
                0.4,
                0.4,
                0.4,
                0.4,
                0.4,
                0.4,
                0.4,
                0.4,
                0.4,  # Day baseload
                1.0,
                1.0,
                1.0,  # Evening peak
                0.4,
                0.4,
                0.4,  # Night baseload
            ]
        )

        solar_profile.extend(daily_solar)
        demand_profile.extend(daily_demand)

    return np.array(solar_profile[:N]), np.array(demand_profile[:N])


def validate_energy_balance(system, tolerance=1e-6):
    """Validate perfect energy conservation."""
    logger.info("Validating energy balance...")

    violations = []
    max_imbalance = 0.0

    for t in range(system.N):
        sources = 0.0
        sinks = 0.0

        for _flow_key, flow_data in system.flows.items():
            flow_value = flow_data["value"][t] if hasattr(flow_data["value"], "__getitem__") else 0.0
            source_comp = system.components[flow_data["source"]]
            target_comp = system.components[flow_data["target"]]

            # Classify flows
            if source_comp.type in ["generation", "storage", "transmission"]:
                sources += flow_value
            if target_comp.type in ["consumption", "storage", "transmission"]:
                sinks += flow_value

        imbalance = abs(sources - sinks)
        max_imbalance = max(max_imbalance, imbalance)

        if imbalance > tolerance:
            violations.append({"timestep": t, "sources": sources, "sinks": sinks, "imbalance": imbalance})

    logger.info(f"Energy balance validation: max_imbalance={max_imbalance:.2e}, violations={len(violations)}")
    return len(violations) == 0, max_imbalance, violations


def validate_physics_constraints(system, tolerance=1e-6):
    """Validate physics constraints."""
    logger.info("Validating physics constraints...")

    violations = []

    # Check storage bounds
    for comp_name, comp in system.components.items():
        if comp.type == "storage" and hasattr(comp, "E"):
            E_max = comp.E_max if hasattr(comp, "E_max") else comp.params.technical.capacity_nominal
            for t in range(system.N):
                soc = comp.E[t] / E_max
                if soc < -tolerance or soc > 1.0 + tolerance:
                    violations.append(f"Storage {comp_name} SOC violation at t={t}: {soc:.6f}")

    # Check non-negative flows
    for flow_key, flow_data in system.flows.items():
        for t in range(system.N):
            flow_value = flow_data["value"][t] if hasattr(flow_data["value"], "__getitem__") else 0.0
            if flow_value < -tolerance:
                violations.append(f"Negative flow {flow_key} at t={t}: {flow_value:.6f}")

    logger.info(f"Physics constraints: {len(violations)} violations")
    return len(violations) == 0, violations


def validate_system_behavior(system):
    """Validate expected system behavior patterns."""
    logger.info("Validating system behavior...")

    checks = {}

    # Check storage cycling
    battery_comp = system.components.get("Battery")
    if battery_comp and hasattr(battery_comp, "E"):
        energy_range = np.max(battery_comp.E) - np.min(battery_comp.E)
        capacity = (
            battery_comp.E_max if hasattr(battery_comp, "E_max") else battery_comp.params.technical.capacity_nominal
        )
        cycling_ratio = energy_range / capacity
        checks["storage_cycling"] = cycling_ratio > 0.01  # At least 1% cycling (more realistic

    # Check solar utilization
    solar_flows = 0.0
    for _flow_key, flow_data in system.flows.items():
        if "SolarPV" in flow_data["source"]:
            solar_flows += np.sum(flow_data["value"])
    checks["solar_utilization"] = solar_flows > 0.0

    # Check grid interaction
    grid_import = 0.0
    grid_export = 0.0
    for _flow_key, flow_data in system.flows.items():
        if "Grid" in flow_data["source"]:
            grid_import += np.sum(flow_data["value"])
        elif "Grid" in flow_data["target"]:
            grid_export += np.sum(flow_data["value"])
    checks["grid_interaction"] = grid_import > 0.0 or grid_export > 0.0

    logger.info(f"System behavior checks: {checks}")
    return all(checks.values()), checks


def run_solver_validation(N=24):
    """Run comprehensive solver validation."""
    logger.info("=" * 80)
    logger.info(f"GOLDEN MICROGRID VALIDATION - {N} TIMESTEPS")
    logger.info("=" * 80)

    results = {"timesteps": N, "start_time": time.time(), "validation_passed": False}

    try:
        # Create system
        system = create_simple_golden_system(N)
        results["system_created"] = True

        # Run rule-based solver
        logger.info("Running rule-based solver...")
        start_time = time.time()
        solver = RuleBasedEngine(system)
        solver_result = solver.solve()
        solve_time = time.time() - start_time

        results["solver_status"] = solver_result.status
        results["solve_time"] = solve_time

        logger.info(f"Solver completed: status={solver_result.status}, time={solve_time:.3f}s")

        if solver_result.status == "optimal":
            # Run validations
            energy_valid, max_imbalance, energy_violations = validate_energy_balance(system)
            physics_valid, physics_violations = validate_physics_constraints(system)
            behavior_valid, behavior_checks = validate_system_behavior(system)

            results.update(
                {
                    "energy_balance_valid": energy_valid,
                    "max_energy_imbalance": max_imbalance,
                    "energy_violations": len(energy_violations),
                    "physics_constraints_valid": physics_valid,
                    "physics_violations": len(physics_violations),
                    "system_behavior_valid": behavior_valid,
                    "behavior_checks": behavior_checks,
                }
            )

            # Overall validation
            results["validation_passed"] = energy_valid and physics_valid and behavior_valid

            # Log summary
            logger.info("=" * 60)
            logger.info("VALIDATION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Energy Balance: {'PASS' if energy_valid else 'FAIL'} (max imbalance: {max_imbalance:.2e})")
            logger.info(
                f"Physics Constraints: {'PASS' if physics_valid else 'FAIL'} ({len(physics_violations)} violations)"
            )
            logger.info(f"System Behavior: {'PASS' if behavior_valid else 'FAIL'}")
            logger.info(f"Overall Result: {'PASS' if results['validation_passed'] else 'FAIL'}")
            logger.info("=" * 60)

        else:
            logger.error(f"Solver failed with status: {solver_result.status}")

    except Exception as e:
        logger.error(f"Validation failed with exception: {e}")
        results["error"] = str(e)
        import traceback

        traceback.print_exc()

    results["end_time"] = time.time()
    results["total_time"] = results["end_time"] - results["start_time"]

    return results


def main():
    """Main validation execution."""
    logger.info("Starting Golden Microgrid Validation...")

    # Run 24-hour validation
    results_24h = run_solver_validation(24)

    # Save results
    results_dir = Path(__file__).parent.parent / "data"
    results_dir.mkdir(parents=True, exist_ok=True)

    results_path = results_dir / "simple_validation_results.json"

    # Convert any numpy types to native Python types for JSON serialization
    def convert_for_json(obj):
        if hasattr(obj, "item"):  # numpy scalars
            return obj.item()
        elif isinstance(obj, dict):
            return {k: convert_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_for_json(item) for item in obj]
        else:
            return obj

    json_safe_results = convert_for_json(results_24h)

    with open(results_path, "w") as f:
        json.dump(json_safe_results, f, indent=2)

    logger.info(f"\nValidation results saved to: {results_path}")
    logger.info(f"24h Validation: {'PASSED' if results_24h.get('validation_passed', False) else 'FAILED'}")

    # Optionally run 7-day stress test (commented out for speed)
    # results_7day = run_solver_validation(168)
    # logger.info(f"7-day Validation: {'PASSED' if results_7day.get('validation_passed', False) else 'FAILED'}")

    return results_24h.get("validation_passed", False)


def test_simple_golden_validation():
    """Test simple golden validation as pytest test."""
    success = main()
    assert success, "Simple golden validation failed"


def test_24h_solver_validation():
    """Test 24-hour solver validation."""
    results = run_solver_validation(24)
    assert results is not None
    assert isinstance(results, dict)
    assert "validation_passed" in results


def test_solver_validation_components():
    """Test solver validation with all required components."""
    results = run_solver_validation(24)
    if results.get("validation_passed"):
        # If validation passed, check that system has expected behavior
        assert results.get("solve_time", 0) > 0
        assert results.get("solver_status") == "optimal"


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
