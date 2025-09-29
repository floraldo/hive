#!/usr/bin/env python3
"""
Fidelity validation test comparing SIMPLE vs STANDARD physics.

This test verifies that fidelity levels produce different but realistic results,
showing that the Strategy Pattern implementation works correctly.
"""

import logging
import sys
from pathlib import Path

import numpy as np

# golden-rule-ignore: no-syspath-hacks - Legacy archive script for validation
 for imports
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

def create_system_with_fidelity(fidelity_level: FidelityLevel) -> None:
    """Create a test system with specified fidelity level."""

    system = System(system_id=f"fidelity_test_{fidelity_level.value}", n=24)

    # Solar generation profile - same for both fidelity levels
    solar_profile = np.array([
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  # Night hours
        0.25881905, 0.5, 0.70710678, 0.8660254, 0.96592583, 1.0,  # Morning to noon
        0.96592583, 0.8660254, 0.70710678, 0.5, 0.25881905,  # Afternoon
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0  # Evening/night
    ])

    # Power demand profile - same for both fidelity levels
    demand_profile = np.array([
        0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4,  # Night baseload
        0.8, 0.8,  # Morning peak
        0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4,  # Day baseload
        1.0, 1.0, 1.0,  # Evening peak
        0.4, 0.4, 0.4  # Night baseload
    ])

    # Grid component - same for both
    grid_params = GridParams(
        technical=GridTechnicalParams(
            capacity_nominal=100.0,
            import_tariff=0.25,
            export_tariff=0.10,
            fidelity_level=fidelity_level,
        )
    )
    grid = Grid("Grid", grid_params, system.N)

    # Battery component - same for both
    battery_params = BatteryParams(
        technical=BatteryTechnicalParams(
            capacity_nominal=10.0,
            max_charge_rate=5.0,
            max_discharge_rate=5.0,
            efficiency_roundtrip=0.95,
            initial_soc_pct=0.5,
            fidelity_level=fidelity_level,
        )
    )
    battery = Battery("Battery", battery_params, system.N)

    # Solar PV component - key difference between fidelity levels
    solar_params = SolarPVParams(
        technical=SolarPVTechnicalParams(
            capacity_nominal=50.0,
            efficiency_nominal=1.0,
            inverter_efficiency=0.98 if fidelity_level == FidelityLevel.STANDARD else 1.0,
            fidelity_level=fidelity_level,
        )
    )
    solar = SolarPV("SolarPV", solar_params, system.N)
    solar.profile = solar_profile

    # Power demand component - key difference between fidelity levels
    demand_params = PowerDemandParams(
        technical=PowerDemandTechnicalParams(
            capacity_nominal=12.5,
            peak_demand=12.5,
            load_profile_type="variable",
            power_factor=0.95 if fidelity_level == FidelityLevel.STANDARD else 1.0,
            fidelity_level=fidelity_level,
        )
    )
    demand = PowerDemand("PowerDemand", demand_params, system.N)
    demand.profile = demand_profile

    # Add components to system
    system.add_component(grid)
    system.add_component(battery)
    system.add_component(solar)
    system.add_component(demand)

    # Connect components
    system.connect("Grid", "PowerDemand", "electricity")
    system.connect("PowerDemand", "Grid", "electricity")
    system.connect("Grid", "Battery", "electricity")
    system.connect("Battery", "Grid", "electricity")
    system.connect("SolarPV", "PowerDemand", "electricity")
    system.connect("SolarPV", "Battery", "electricity")
    system.connect("SolarPV", "Grid", "electricity")
    system.connect("Battery", "PowerDemand", "electricity")

    return system

def extract_key_metrics(system) -> None:
    """Extract key metrics for comparison."""

    metrics = {
        "total_solar_generation": 0.0,
        "total_demand_met": 0.0,
        "total_grid_import": 0.0,
        "total_grid_export": 0.0,
        "peak_solar_flow": 0.0,
        "peak_demand_flow": 0.0,
    }

    # Sum all flows to get totals
    for flow_key, flow_data in system.flows.items():
        values = flow_data["value"]
        flow_total = np.sum(values)
        peak_flow = np.max(values)

        if "SolarPV" in flow_key and flow_data["source"] == "SolarPV":
            metrics["total_solar_generation"] += flow_total
            metrics["peak_solar_flow"] = max(metrics["peak_solar_flow"], peak_flow)

        if flow_data["target"] == "PowerDemand":
            metrics["total_demand_met"] += flow_total
            if flow_data["source"] == "PowerDemand":
                metrics["peak_demand_flow"] = max(metrics["peak_demand_flow"], peak_flow)

        if flow_data["source"] == "Grid":
            metrics["total_grid_import"] += flow_total
        if flow_data["target"] == "Grid":
            metrics["total_grid_export"] += flow_total

    return metrics

def compare_fidelity_results(simple_metrics, standard_metrics) -> None:
    """Compare metrics between fidelity levels."""

    logger.info("FIDELITY COMPARISON:")
    logger.info("===================")

    differences = {}
    for key in simple_metrics:
        simple_val = simple_metrics[key]
        standard_val = standard_metrics[key]

        if simple_val > 0:
            diff_pct = ((standard_val - simple_val) / simple_val) * 100
        else:
            diff_pct = 0.0

        differences[key] = diff_pct

        logger.info(f"{key}:")
        logger.info(f"  SIMPLE:   {simple_val:.3f}")
        logger.info(f"  STANDARD: {standard_val:.3f}")
        logger.info(f"  Difference: {diff_pct:+.2f}%")
        logger.info("")

    return differences

def validate_fidelity_realism(differences) -> None:
    """Validate that fidelity differences are realistic."""

    logger.info("VALIDATION CHECKS:")
    logger.info("==================")

    checks_passed = 0
    total_checks = 0

    # Check 1: Solar generation should be lower in STANDARD (inverter losses)
    total_checks += 1
    if differences["total_solar_generation"] < 0:
        logger.info("PASS: Solar generation lower in STANDARD (inverter efficiency)")
        checks_passed += 1
    else:
        logger.error("FAIL: Solar generation should be lower in STANDARD")

    # Check 2: Inverter efficiency loss should be around 2% (98% efficiency)
    total_checks += 1
    expected_loss = -2.0  # 2% loss
    actual_loss = differences["total_solar_generation"]
    if abs(actual_loss - expected_loss) < 1.0:  # Within 1% tolerance
        logger.info(f"PASS: Inverter loss ~2% (actual: {actual_loss:.2f}%)")
        checks_passed += 1
    else:
        logger.error(f"FAIL: Expected ~2% loss, got {actual_loss:.2f}%")

    # Check 3: Grid interactions should be affected (less export due to lower solar)
    total_checks += 1
    if differences["total_grid_export"] < 0:
        logger.info("PASS: Grid export lower in STANDARD (less solar)")
        checks_passed += 1
    else:
        logger.error("FAIL: Grid export should be lower in STANDARD")

    # Check 4: Demand met should be SAME (STANDARD keeps active power unchanged)
    total_checks += 1
    demand_diff = abs(differences["total_demand_met"])
    if demand_diff < 0.01:  # Should be essentially the same
        logger.info(f"PASS: Demand unchanged in STANDARD (active power preserved, {demand_diff:.2f}%)")
        checks_passed += 1
    else:
        logger.error(f"FAIL: Demand should be same in STANDARD (got {demand_diff:.2f}% difference)")

    logger.info(f"\nValidation Results: {checks_passed}/{total_checks} checks passed")
    return checks_passed == total_checks

def main() -> None:
    """Main fidelity validation function."""

    logger.info("=" * 80)
    logger.info("FIDELITY LEVEL PHYSICS VALIDATION")
    logger.info("=" * 80)

    try:
        # Step 1: Create SIMPLE fidelity system
        logger.info("Creating SIMPLE fidelity system...")
        simple_system = create_system_with_fidelity(FidelityLevel.SIMPLE)

        # Step 2: Run SIMPLE simulation
        logger.info("Running SIMPLE fidelity simulation...")
        simple_solver = RuleBasedEngine(simple_system)
        simple_result = simple_solver.solve()
        logger.info(f"SIMPLE solver status: {simple_result.status}")

        # Step 3: Create STANDARD fidelity system
        logger.info("Creating STANDARD fidelity system...")
        standard_system = create_system_with_fidelity(FidelityLevel.STANDARD)

        # Step 4: Run STANDARD simulation
        logger.info("Running STANDARD fidelity simulation...")
        standard_solver = RuleBasedEngine(standard_system)
        standard_result = standard_solver.solve()
        logger.info(f"STANDARD solver status: {standard_result.status}")

        # Step 5: Extract metrics
        logger.info("Extracting metrics...")
        simple_metrics = extract_key_metrics(simple_system)
        standard_metrics = extract_key_metrics(standard_system)

        # Step 6: Compare results
        logger.info("Comparing fidelity results...")
        differences = compare_fidelity_results(simple_metrics, standard_metrics)

        # Step 7: Validate realism
        logger.info("Validating fidelity realism...")
        is_realistic = validate_fidelity_realism(differences)

        # Step 8: Report outcome
        logger.info("\n" + "=" * 80)
        if is_realistic:
            logger.info("SUCCESS: Fidelity levels produce realistic physics differences")
            logger.info("Strategy Pattern implementation working correctly")
        else:
            logger.error("FAILURE: Fidelity differences are not realistic")
            logger.error("Check Strategy Pattern implementation")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"FIDELITY VALIDATION ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
