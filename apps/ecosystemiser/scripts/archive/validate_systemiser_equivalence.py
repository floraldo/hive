from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
Re-validation test comparing EcoSystemiser against the golden Systemiser dataset.

This test verifies that recent changes haven't broken the core logic by
ensuring numerical equivalence with the original, trusted Systemiser implementation.
"""

import json
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

# Import EcoSystemiser components
from ecosystemiser.system_model.system import System

def load_golden_dataset():
    """Load the golden dataset from the Systemiser baseline."""
    golden_path = Path(__file__).parent.parent.parent / "tests" / "systemiser_minimal_golden.json"
    with open(golden_path, "r") as f:
        return json.load(f)

def create_minimal_ecosystemiser() -> None:
    """Create the minimal 4-component system matching the golden dataset configuration."""

    # Create system with 24 timesteps
    system = System(system_id="minimal_validation", n=24)

    # Solar generation profile - NORMALIZED (0-1 scale) with PRECISE VALUES
    # These values will be scaled by P_max in the component's rule_based_generate method
    # Values extracted from golden dataset with full precision to eliminate numerical discrepancies
    solar_profile = np.array(
        [
            0.0000000000,
            0.0000000000,
            0.0000000000,
            0.0000000000,
            0.0000000000,
            0.0000000000,
            0.0000000000,
            0.2588190451,
            0.5000000000,
            0.7071067812,
            0.8660254038,
            0.9659258263,
            1.0000000000,
            0.9659258263,
            0.8660254038,
            0.7071067812,
            0.5000000000,
            0.2588190451,
            0.0000000000,
            0.0000000000,
            0.0000000000,
            0.0000000000,
            0.0000000000,
            0.0000000000,
        ]
    )

    # Power demand profile - NORMALIZED (0-1 scale)
    # These values will be scaled by P_max in the component's rule_based_demand method
    demand_profile = np.array(
        [
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,  # Hours 0-6: night baseload (5/12.5)
            0.8,
            0.8,  # Hours 7-8: morning peak (10/12.5)
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,
            0.4,  # Hours 9-17: day baseload
            1.0,
            1.0,
            1.0,  # Hours 18-20: evening peak (12.5/12.5)
            0.4,
            0.4,
            0.4,  # Hours 21-23: night baseload
        ]
    )

    # Grid component (100 kW capacity, matching golden dataset)
    grid_params = GridParams(
        technical=GridTechnicalParams(
            capacity_nominal=100.0,  # 100 kW grid capacity
            import_tariff=0.25,  # Import tariff
            export_tariff=0.10,  # Export tariff
            fidelity_level=FidelityLevel.SIMPLE,
        )
    )
    grid = Grid("Grid", grid_params, system.N)

    # Battery component (10 kWh, 95% efficiency, 50% initial SOC, matching golden dataset)
    battery_params = BatteryParams(
        technical=BatteryTechnicalParams(
            capacity_nominal=10.0,  # 10 kWh (E_max)
            max_charge_rate=5.0,  # 5 kW (P_max)
            max_discharge_rate=5.0,  # 5 kW (P_max)
            efficiency_roundtrip=0.95,  # 95% efficiency (eta)
            initial_soc_pct=0.5,  # 50% initial SOC (E_init = 5 kWh)
            fidelity_level=FidelityLevel.SIMPLE,  # Use SIMPLE fidelity (OG Systemiser baseline)
        )
    )
    battery = Battery("Battery", battery_params, system.N)

    # Solar PV component (50 kW peak, matching golden dataset)
    solar_params = SolarPVParams(
        technical=SolarPVTechnicalParams(
            capacity_nominal=50.0,  # 50 kW peak (P_max) - matches golden dataset
            efficiency_nominal=1.0,  # Direct profile scaling
            fidelity_level=FidelityLevel.SIMPLE,  # Use SIMPLE fidelity (no inverter losses)
        )
    )
    solar = SolarPV("SolarPV", solar_params, system.N)
    print(f"DEBUG: Before assignment - solar.profile: {getattr(solar, 'profile', 'NOT_SET')}")
    print(f"DEBUG: Assigning solar_profile with daylight values: {solar_profile[7:13]}")  # Show daylight hours
    solar.profile = solar_profile  # Already normalized (0-1)
    print(
        f"DEBUG: After assignment - solar.profile daylight: {solar.profile[7:13] if solar.profile is not None else 'None'}"
    )

    # Power demand component (12.5 kW peak, matching golden dataset)
    demand_params = PowerDemandParams(
        technical=PowerDemandTechnicalParams(
            capacity_nominal=12.5,  # Required field for the archetype
            peak_demand=12.5,  # 12.5 kW peak demand (P_max)
            load_profile_type="variable",  # Variable demand with peaks
            fidelity_level=FidelityLevel.SIMPLE,  # Use SIMPLE fidelity (fixed demand)
        )
    )
    demand = PowerDemand("PowerDemand", demand_params, system.N)
    print(f"DEBUG: Before assignment - demand.profile: {getattr(demand, 'profile', 'NOT_SET')}")
    print(f"DEBUG: Assigning demand_profile with values: {demand_profile[:5]}")
    demand.profile = demand_profile  # Already normalized (0-1)
    print(f"DEBUG: After assignment - demand.profile: {demand.profile[:5] if demand.profile is not None else 'None'}")

    # Add components to system
    system.add_component(grid)
    system.add_component(battery)
    system.add_component(solar)
    system.add_component(demand)

    # Connect components (matching golden dataset flow structure exactly)
    # Grid connections (bidirectional)
    system.connect("Grid", "PowerDemand", "electricity")
    system.connect("PowerDemand", "Grid", "electricity")  # Export back
    system.connect("Grid", "Battery", "electricity")
    system.connect("Battery", "Grid", "electricity")  # Export back

    # Solar connections
    system.connect("SolarPV", "PowerDemand", "electricity")
    system.connect("SolarPV", "Battery", "electricity")
    system.connect("SolarPV", "Grid", "electricity")  # Export

    # Battery to demand
    system.connect("Battery", "PowerDemand", "electricity")

    return system

def extract_ecosystemiser_results(system) -> None:
    """Extract results from ecosystemiser in the same format as golden dataset."""

    results = {
        "metadata": {
            "simulator": "EcoSystemiser",
            "solver": "RuleBasedEngine",
            "components": [comp.name for comp in system.components.values()],
            "timesteps": system.N,
            "description": "EcoSystemiser validation against Systemiser golden dataset",
        },
        "flows": {},
        "storage": {},
        "summary": {},
    }

    # Extract flow results from the solved system
    for flow_key, flow_data in system.flows.items():
        values = []
        if isinstance(flow_data["value"], np.ndarray):
            values = flow_data["value"].tolist()
        else:
            values = [0.0] * system.N

        results["flows"][flow_key] = {
            "source": flow_data["source"],
            "target": flow_data["target"],
            "type": flow_data.get("type", "electricity"),
            "values": values,
        }

    # Extract storage results
    battery_comp = system.components.get("Battery")
    if battery_comp and hasattr(battery_comp, "E"):
        # Our E array now has N elements, E[t] = state at END of timestep t
        # The golden dataset has the same structure (24 values for 24 timesteps)
        results["storage"]["Battery"] = {
            "medium": "electricity",
            "E_max": battery_comp.E_max,
            "E_init": battery_comp.E_init,
            "values": battery_comp.E.tolist(),  # All N values: E[0] to E[N-1]
        }

    return results

def compare_results(golden_data, ecosystemiser_data, tolerance=1e-6) -> None:
    """Compare EcoSystemiser results against golden dataset with strict tolerance."""

    logger.info("Performing numerical comparison...")
    logger.info(f"Tolerance: {tolerance}")

    failures = []
    total_comparisons = 0

    # Compare flows
    logger.info("\nComparing flows...")
    for flow_key in golden_data["flows"]:
        if flow_key not in ecosystemiser_data["flows"]:
            failures.append(f"Flow {flow_key} missing in EcoSystemiser results")
            continue

        golden_values = np.array(golden_data["flows"][flow_key]["values"])
        eco_values = np.array(ecosystemiser_data["flows"][flow_key]["values"])

        if not np.allclose(golden_values, eco_values, atol=tolerance):
            max_diff = np.max(np.abs(golden_values - eco_values))
            failures.append(f"Flow {flow_key}: max difference = {max_diff:.2e}")
        else:
            logger.info(f"  OK {flow_key}: MATCH")

        total_comparisons += 1

    # Compare storage
    logger.info("\nComparing storage...")
    for storage_key in golden_data["storage"]:
        if storage_key not in ecosystemiser_data["storage"]:
            failures.append(f"Storage {storage_key} missing in EcoSystemiser results")
            continue

        golden_values = np.array(golden_data["storage"][storage_key]["values"])
        eco_values = np.array(ecosystemiser_data["storage"][storage_key]["values"])

        if not np.allclose(golden_values, eco_values, atol=tolerance):
            max_diff = np.max(np.abs(golden_values - eco_values))
            failures.append(f"Storage {storage_key}: max difference = {max_diff:.2e}")
        else:
            logger.info(f"  OK {storage_key}: MATCH")

        total_comparisons += 1

    return failures, total_comparisons

def main() -> None:
    """Main validation function."""

    logger.info("=" * 80)
    logger.info("ECOSYSTEMISER vs SYSTEMISER VALIDATION TEST")
    logger.info("=" * 80)

    try:
        # Step 1: Load golden dataset
        logger.info("\nLoading golden dataset...")
        golden_data = load_golden_dataset()
        logger.info(
            f"  OK Loaded {len(golden_data['flows'])} flows and {len(golden_data['storage'])} storage components"
        )

        # Step 2: Create minimal EcoSystemiser system
        logger.info("\nCreating minimal EcoSystemiser system...")
        system = create_minimal_ecosystemiser()
        logger.info(f"  OK Created system with {len(system.components)} components")

        # Step 3: Run EcoSystemiser simulation
        logger.info("\nRunning EcoSystemiser simulation...")

        # Debug: Check profiles before solving
        logger.debug("\nDebug - Component profiles:")
        for name, comp in system.components.items():
            if hasattr(comp, "profile") and comp.profile is not None:
                logger.info(f"  {name}: profile shape={comp.profile.shape}, P_max={getattr(comp, 'P_max', 'N/A')}")
                if name == "SolarPV":
                    logger.info(f"    Sample values: {comp.profile[:5]}")
            else:
                logger.info(f"  {name}: no profile or profile is None")

        solver = RuleBasedEngine(system)

        # Run the actual simulation
        result = solver.solve()
        logger.info(f"  OK Solver completed with status: {result.status}")
        logger.info(f"  OK Solve time: {result.solve_time:.4f} seconds")

        # Step 4: Extract results from solved system
        logger.info("\nExtracting results...")
        ecosystemiser_data = extract_ecosystemiser_results(system)
        logger.info(
            f"  OK Extracted {len(ecosystemiser_data['flows'])} flows and {len(ecosystemiser_data['storage'])} storage components"
        )

        # Step 5: Compare results
        logger.info("\nComparing results...")
        failures, total_comparisons = compare_results(golden_data, ecosystemiser_data)

        # Step 6: Report outcome
        logger.info("\n" + "=" * 80)
        if not failures:
            logger.info("SUCCESS: Numerical equivalence with the original Systemiser is confirmed.")
            logger.info(f"All {total_comparisons} comparisons passed within tolerance.")
        else:
            logger.error("VALIDATION FAILED:")
            for failure in failures:
                logger.error(f"  FAIL {failure}")
            logger.error(f"\n{len(failures)} failures out of {total_comparisons} comparisons")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"\nVALIDATION ERROR: {str(e)}")
        import traceback

        traceback.print_exc()

if __name__ == "__main__":
    main()
