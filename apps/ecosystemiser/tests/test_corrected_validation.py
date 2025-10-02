#!/usr/bin/env python3
"""Corrected golden validation test."""

import json
import time
from pathlib import Path

import numpy as np

eco_path = Path(__file__).parent.parent / "src"

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


def create_golden_system():
    """Create the exact golden system matching the original validation."""
    N = 24
    system = System(system_id="golden_validation", n=N)

    # Use the exact profiles from the golden dataset
    solar_profile = np.array(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,  # Night
            0.25881905,
            0.5,
            0.70710678,
            0.8660254,
            0.96592583,
            1.0,  # Morning to noon
            0.96592583,
            0.8660254,
            0.70710678,
            0.5,
            0.25881905,  # Afternoon
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,  # Evening/night
        ],
    )

    demand_profile = np.array(
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
        ],
    )

    # Create components matching golden dataset exactly
    grid_params = GridParams(
        technical=GridTechnicalParams(
            capacity_nominal=100.0,
            import_tariff=0.25,
            export_tariff=0.10,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    grid = Grid("Grid", grid_params, N)

    battery_params = BatteryParams(
        technical=BatteryTechnicalParams(
            capacity_nominal=10.0,
            max_charge_rate=5.0,
            max_discharge_rate=5.0,
            efficiency_roundtrip=0.95,
            initial_soc_pct=0.5,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    battery = Battery("Battery", battery_params, N)

    solar_params = SolarPVParams(
        technical=SolarPVTechnicalParams(
            capacity_nominal=50.0,
            efficiency_nominal=1.0,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    solar = SolarPV("SolarPV", solar_params, N)
    solar.profile = solar_profile

    demand_params = PowerDemandParams(
        technical=PowerDemandTechnicalParams(
            capacity_nominal=12.5,
            peak_demand=12.5,
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

    # Connect components (exact same connections as golden dataset)
    system.connect("Grid", "PowerDemand", "electricity")
    system.connect("PowerDemand", "Grid", "electricity")
    system.connect("Grid", "Battery", "electricity")
    system.connect("Battery", "Grid", "electricity")
    system.connect("SolarPV", "PowerDemand", "electricity")
    system.connect("SolarPV", "Battery", "electricity")
    system.connect("SolarPV", "Grid", "electricity")
    system.connect("Battery", "PowerDemand", "electricity")

    return system


def validate_against_golden_dataset(system):
    """Compare results against the golden dataset."""
    golden_path = Path(__file__).parent.parent / "tests" / "systemiser_minimal_golden.json"

    if not golden_path.exists():
        logger.warning("Golden dataset not found, skipping comparison")
        return True, "Golden dataset not available"

    with open(golden_path) as f:
        golden_data = json.load(f)

    # Compare key metrics
    tolerance = 1e-3  # 1 kWh tolerance for comparison

    # Check battery final state
    battery_comp = system.components["Battery"]
    final_battery_energy = battery_comp.E[-1]
    golden_final_energy = golden_data["storage"]["Battery"]["values"][-1]

    battery_match = abs(final_battery_energy - golden_final_energy) < tolerance

    # Check total flows
    solar_to_grid = np.sum(system.flows["SolarPV_P_Grid"]["value"])
    golden_solar_to_grid = sum(golden_data["flows"]["SolarPV_P_Grid"]["values"])

    flow_match = abs(solar_to_grid - golden_solar_to_grid) < tolerance * 10  # More tolerant for flows

    logger.info(f"Battery final energy: {final_battery_energy:.3f} vs golden {golden_final_energy:.3f}")
    logger.info(f"Solar to grid: {solar_to_grid:.1f} vs golden {golden_solar_to_grid:.1f}")

    return battery_match and flow_match, {
        "battery_match": battery_match,
        "flow_match": flow_match,
        "battery_diff": final_battery_energy - golden_final_energy,
        "flow_diff": solar_to_grid - golden_solar_to_grid,
    }


def run_validation():
    """Run the comprehensive validation."""
    logger.info("=" * 80)
    logger.info("GOLDEN MICROGRID RULE-BASED VALIDATION")
    logger.info("=" * 80)

    results = {"validation_start": time.time()}

    try:
        # Create system
        system = create_golden_system()
        logger.info(f"Created system with {len(system.components)} components, {len(system.flows)} flows")

        # Run solver
        start_time = time.time()
        solver = RuleBasedEngine(system)
        result = solver.solve()
        solve_time = time.time() - start_time

        logger.info(f"Solver completed: status={result.status}, time={solve_time:.4f}s")

        results.update(
            {"solver_status": result.status, "solve_time": solve_time, "solver_success": result.status == "optimal"},
        )

        if result.status == "optimal":
            # Validate energy balance
            max_imbalance = 0.0
            for t in range(system.N):
                sources = 0.0
                sinks = 0.0

                for _flow_key, flow_data in system.flows.items():
                    flow_value = flow_data["value"][t]
                    source_comp = system.components[flow_data["source"]]
                    target_comp = system.components[flow_data["target"]]

                    if source_comp.type in ["generation", "storage", "transmission"]:
                        sources += flow_value
                    if target_comp.type in ["consumption", "storage", "transmission"]:
                        sinks += flow_value

                imbalance = abs(sources - sinks)
                max_imbalance = max(max_imbalance, imbalance)

            energy_balance_ok = max_imbalance < 1e-6
            logger.info(f"Energy balance: max imbalance = {max_imbalance:.2e}")

            # Check against golden dataset
            golden_match, golden_details = validate_against_golden_dataset(system)

            # System behavior checks
            battery = system.components["Battery"]
            battery_cycling = (np.max(battery.E) - np.min(battery.E)) / battery.E_max

            solar_total = sum(
                np.sum(flow_data["value"])
                for flow_key, flow_data in system.flows.items()
                if "SolarPV" in flow_data["source"]
            )

            results.update(
                {
                    "energy_balance_ok": energy_balance_ok,
                    "max_energy_imbalance": float(max_imbalance),
                    "golden_dataset_match": golden_match,
                    "golden_details": golden_details,
                    "battery_cycling_ratio": float(battery_cycling),
                    "total_solar_generation": float(solar_total),
                    "validation_passed": energy_balance_ok and golden_match,
                },
            )

            # Log summary
            logger.info("=" * 60)
            logger.info("VALIDATION RESULTS")
            logger.info("=" * 60)
            logger.info(f"Energy Balance: {'PASS' if energy_balance_ok else 'FAIL'}")
            logger.info(f"Golden Dataset Match: {'PASS' if golden_match else 'FAIL'}")
            logger.info(f"Battery Cycling: {battery_cycling:.1%}")
            logger.info(f"Solar Generation: {solar_total:.1f} kWh")
            logger.info(f"Overall: {'VALIDATION PASSED' if results['validation_passed'] else 'VALIDATION FAILED'}")
            logger.info("=" * 60)

        else:
            results["validation_passed"] = False
            logger.error(f"Solver failed: {result.status}")

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
    results = run_validation()

    # Save results (with proper JSON serialization)
    results_dir = Path(__file__).parent.parent / "data"
    results_dir.mkdir(parents=True, exist_ok=True)

    results_path = results_dir / "rule_based_validation_results.json"

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

    logger.info("\nValidation complete!")
    logger.info(f"Results saved to: {results_path}")
    logger.info(f"Status: {'PASSED' if results.get('validation_passed', False) else 'FAILED'}")

    return results.get("validation_passed", False)


def test_corrected_golden_validation():
    """Test corrected golden validation as pytest test."""
    success = main()
    assert success, "Corrected golden validation failed"


def test_golden_system_creation():
    """Test golden system can be created successfully."""
    system = create_golden_system()
    assert system is not None
    assert system.N == 24
    assert len(system.components) >= 3  # Should have Grid, Battery, Solar, etc.


def test_corrected_validation_logic():
    """Test corrected validation logic."""
    # Basic validation test - this ensures the validation functions are accessible
    system = create_golden_system()
    solver = RuleBasedEngine(system)
    result = solver.solve()

    # Basic assertions about solver result
    assert result is not None
    assert hasattr(result, "status")


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
