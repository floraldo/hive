"""
Direct validation test comparing EcoSystemiser against Systemiser golden dataset.

This test directly creates components without using the SystemBuilder
to avoid import issues during early development.
"""

import json
import numpy as np
from pathlib import Path
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add path for imports
eco_path = Path(__file__).parent.parent / 'src' / 'EcoSystemiser'
# Direct imports
from system_model.system import System
from system_model.components.battery import Battery, BatteryParams
from system_model.components.grid import Grid, GridParams
from system_model.components.solar_pv import SolarPV, SolarPVParams
from system_model.components.power_demand import PowerDemand, PowerDemandParams
from solver.rule_based_engine import RuleBasedEngine

def load_golden_dataset():
    """Load the golden dataset from Systemiser."""
    golden_path = Path(__file__).parent / 'systemiser_minimal_golden.json'
    with open(golden_path, 'r') as f:
        return json.load(f)

def create_eco_system():
    """Create EcoSystemiser system matching golden dataset configuration."""
    N = 24
    system = System('minimal_validation', N)

    # Create profiles matching the golden dataset
    # Solar profile (peak at midday)
    solar_profile = np.zeros(N)
    for t in range(N):
        if 6 <= t <= 18:  # Daylight hours
            solar_profile[t] = np.sin((t - 6) * np.pi / 12) * 5.0

    # Demand profile (baseload + peaks)
    demand_profile = np.ones(N) * 1.0  # 1 kW baseload
    demand_profile[7:9] = 2.0   # Morning peak
    demand_profile[18:21] = 2.5  # Evening peak

    # Create components directly
    grid = Grid(
        name='Grid',
        params=GridParams(P_max=100, import_tariff=0.25, feed_in_tariff=0.08)
    )
    system.add_component(grid)

    battery = Battery(
        name='Battery',
        params=BatteryParams(P_max=5, E_max=10, E_init=5, eta_charge=0.95, eta_discharge=0.95)
    )
    system.add_component(battery)

    solar = SolarPV(
        name='SolarPV',
        params=SolarPVParams(P_profile=solar_profile.tolist(), P_max=10)
    )
    system.add_component(solar)

    demand = PowerDemand(
        name='PowerDemand',
        params=PowerDemandParams(P_profile=demand_profile.tolist(), P_max=5)
    )
    system.add_component(demand)

    # Create connections
    system.connect('Grid', 'PowerDemand', 'electricity')
    system.connect('Grid', 'Battery', 'electricity')
    system.connect('SolarPV', 'PowerDemand', 'electricity')
    system.connect('SolarPV', 'Battery', 'electricity')
    system.connect('SolarPV', 'Grid', 'electricity')
    system.connect('Battery', 'PowerDemand', 'electricity')
    system.connect('Battery', 'Grid', 'electricity')

    return system

def run_eco_simulation(system):
    """Run EcoSystemiser simulation and extract results."""
    N = system.N
    solver = RuleBasedEngine(system)

    # Run simulation
    result = solver.solve()

    # Extract results in same format as golden dataset
    results = {
        'flows': {},
        'storage': {}
    }

    # Extract flows
    for flow_key, flow_data in system.flows.items():
        values = []
        if isinstance(flow_data['value'], np.ndarray):
            values = flow_data['value'].tolist()
        else:
            values = [0.0] * N

        results['flows'][flow_key] = {
            'source': flow_data['source'],
            'target': flow_data['target'],
            'type': flow_data.get('type', 'electricity'),
            'values': values
        }

    # Extract storage
    battery_comp = system.components.get('Battery')
    if battery_comp and hasattr(battery_comp, 'E'):
        results['storage']['Battery'] = {
            'medium': 'electricity',
            'E_max': battery_comp.params.E_max,
            'E_init': battery_comp.params.E_init,
            'values': battery_comp.E.tolist() if isinstance(battery_comp.E, np.ndarray) else [battery_comp.params.E_init] * N
        }

    # Calculate summary
    results['summary'] = {}
    total_generation = 0
    total_consumption = 0

    for flow_key, flow_data in results['flows'].items():
        total = sum(flow_data['values'])
        if 'SolarPV' in flow_data['source']:
            total_generation += total
        if 'PowerDemand' in flow_data['target']:
            total_consumption += total

    results['summary']['total_generation'] = total_generation
    results['summary']['total_consumption'] = total_consumption

    return results

def validate_results(golden_dataset, eco_results):
    """Validate EcoSystemiser results against golden dataset."""
    TOLERANCE = 1e-6
    errors = []

    # Compare flows
    logger.info("Comparing flows...")
    for flow_key in golden_dataset['flows']:
        if flow_key not in eco_results['flows']:
            errors.append(f"Flow {flow_key} missing in EcoSystemiser results")
            continue

        golden_flow = golden_dataset['flows'][flow_key]
        eco_flow = eco_results['flows'][flow_key]

        # Check metadata
        if golden_flow['source'] != eco_flow['source']:
            errors.append(f"Source mismatch for {flow_key}")
        if golden_flow['target'] != eco_flow['target']:
            errors.append(f"Target mismatch for {flow_key}")

        # Check values
        golden_values = np.array(golden_flow['values'])
        eco_values = np.array(eco_flow['values'])

        max_diff = np.max(np.abs(golden_values - eco_values))
        if max_diff >= TOLERANCE:
            errors.append(
                f"Flow {flow_key} values differ by {max_diff:.6e}\n"
                f"  Golden (first 5): {golden_values[:5]}\n"
                f"  Eco (first 5): {eco_values[:5]}"
            )

    # Compare storage
    logger.info("Comparing storage...")
    for storage_key in golden_dataset['storage']:
        if storage_key not in eco_results['storage']:
            errors.append(f"Storage {storage_key} missing in EcoSystemiser")
            continue

        golden_storage = golden_dataset['storage'][storage_key]
        eco_storage = eco_results['storage'][storage_key]

        # Check metadata
        if abs(golden_storage['E_max'] - eco_storage['E_max']) >= TOLERANCE:
            errors.append(f"E_max mismatch for {storage_key}")
        if abs(golden_storage['E_init'] - eco_storage['E_init']) >= TOLERANCE:
            errors.append(f"E_init mismatch for {storage_key}")

        # Check values
        golden_values = np.array(golden_storage['values'])
        eco_values = np.array(eco_storage['values'])

        max_diff = np.max(np.abs(golden_values - eco_values))
        if max_diff >= TOLERANCE:
            errors.append(
                f"Storage {storage_key} values differ by {max_diff:.6e}\n"
                f"  Golden (first 5): {golden_values[:5]}\n"
                f"  Eco (first 5): {eco_values[:5]}"
            )

    return errors

def main():
    """Main validation function."""
    logger.info("="*60)
    logger.info("ECOSYSTEMISER VALIDATION TEST")
    logger.info("="*60)

    try:
        # Load golden dataset
        logger.info("\nLoading golden dataset...")
        golden_dataset = load_golden_dataset()
        logger.info(f"Golden dataset loaded: {len(golden_dataset['flows'])} flows, {len(golden_dataset['storage'])} storage components")

        # Create EcoSystemiser system
        logger.info("\nCreating EcoSystemiser system...")
        eco_system = create_eco_system()
        logger.info(f"System created with {len(eco_system.components)} components")

        # Run simulation
        logger.info("\nRunning EcoSystemiser simulation...")
        eco_results = run_eco_simulation(eco_system)
        logger.info("Simulation complete!")

        # Validate results
        logger.info("\nValidating results...")
        errors = validate_results(golden_dataset, eco_results)

        if errors:
            logger.error("\n❌ VALIDATION FAILED!")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        else:
            logger.info("\n✅ VALIDATION SUCCESSFUL!")
            logger.info("EcoSystemiser matches Systemiser golden dataset!")

            # Print summaries
            logger.info("\nSummary Comparison:")
            logger.info(f"  Golden Generation: {golden_dataset['summary']['total_generation']:.2f} kWh")
            logger.info(f"  Eco Generation: {eco_results['summary']['total_generation']:.2f} kWh")
            logger.info(f"  Golden Consumption: {golden_dataset['summary']['total_consumption']:.2f} kWh")
            logger.info(f"  Eco Consumption: {eco_results['summary']['total_consumption']:.2f} kWh")

            return True

    except Exception as e:
        logger.error(f"\n❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)