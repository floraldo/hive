"""
Generate a minimal golden dataset from the original Systemiser.

This is a simplified version that directly imports and runs the minimal
components from Systemiser without using system_setup.
"""

import sys
from pathlib import Path
import json
import numpy as np
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add Systemiser path
systemiser_path = Path(__file__).parent.parent.parent / 'Systemiser'
# Import core components directly
from system.system import System
from system.battery import Battery
from system.grid import Grid
from system.solar_pv import SolarPV
from system.power_demand import PowerDemand
from solver.rule_based_solver import ComponentBasedRuleEngine

def create_minimal_system_direct(N=24):
    """Create minimal 4-component system directly."""
    logger.info("Creating minimal 4-component system...")

    # Create system
    system = System('minimal_energy', N)

    # Create simple profiles
    # Solar profile (peak at midday)
    solar_profile = np.zeros(N)
    for t in range(N):
        if 6 <= t <= 18:  # Daylight hours
            solar_profile[t] = np.sin((t - 6) * np.pi / 12) * 5.0  # Peak 5 kW at noon

    # Demand profile (baseload + peaks)
    demand_profile = np.ones(N) * 1.0  # 1 kW baseload
    demand_profile[7:9] = 2.0   # Morning peak
    demand_profile[18:21] = 2.5  # Evening peak

    # Create components
    components = {
        'Grid': Grid('Grid', P_max=100, n=N),
        'Battery': Battery('Battery', P_max=5, E_max=10, E_init=5, eta=0.95, n=N),
        'SolarPV': SolarPV('SolarPV', P_profile=solar_profile, P_max=10, n=N),
        'PowerDemand': PowerDemand('PowerDemand', P_profile=demand_profile, P_max=5, n=N)
    }

    # Add components to system
    for comp in components.values():
        system.add_component(comp)

    # Create connections (flows) using the System's connect method
    # Grid connections (bidirectional)
    system.connect('Grid', 'PowerDemand', 'electricity', print_connection=False)
    system.connect('PowerDemand', 'Grid', 'electricity', print_connection=False)  # Export back
    system.connect('Grid', 'Battery', 'electricity', print_connection=False)
    system.connect('Battery', 'Grid', 'electricity', print_connection=False)  # Export back

    # Solar connections
    system.connect('SolarPV', 'PowerDemand', 'electricity', print_connection=False)
    system.connect('SolarPV', 'Battery', 'electricity', print_connection=False)
    system.connect('SolarPV', 'Grid', 'electricity', print_connection=False)  # Export

    # Battery to demand
    system.connect('Battery', 'PowerDemand', 'electricity', print_connection=False)

    logger.info(f"Created system with {len(components)} components and {len(system.flows)} flows")

    return system, components

def run_simulation(system, components, N=24):
    """Run the Systemiser rule-based engine."""
    logger.info("Running Systemiser rule-based simulation...")

    # Create and run engine
    engine = ComponentBasedRuleEngine(system)

    # Run timestep by timestep
    for t in range(N):
        engine.solve_timestep(t)

        # Log key values
        if t % 6 == 0:  # Log every 6 hours
            battery = components['Battery']
            logger.info(f"t={t:2d}: Battery SOC={battery.E[t]:.2f}/{battery.E_max:.2f} kWh")

    logger.info("Simulation complete!")

    return extract_results(system, components, N)

def extract_results(system, components, N):
    """Extract results in standardized format."""
    results = {
        'metadata': {
            'simulator': 'Systemiser',
            'solver': 'RuleBasedEngine',
            'components': list(components.keys()),
            'timesteps': N,
            'description': 'Minimal 4-component golden dataset'
        },
        'flows': {},
        'storage': {}
    }

    # Extract flows
    for flow_key, flow_data in system.flows.items():
        values = []
        for t in range(N):
            try:
                val = float(flow_data['value'][t]) if flow_data['value'][t] is not None else 0.0
            except:
                val = 0.0
            values.append(val)

        results['flows'][flow_key] = {
            'source': flow_data['source'],
            'target': flow_data['target'],
            'type': flow_data.get('type', 'electricity'),
            'values': values
        }

    # Extract storage (battery only)
    battery = components['Battery']
    storage_values = []
    for t in range(N):
        try:
            val = float(battery.E[t]) if battery.E[t] is not None else battery.E_init
        except:
            val = battery.E_init
        storage_values.append(val)

    results['storage']['Battery'] = {
        'medium': 'electricity',
        'E_max': float(battery.E_max),
        'E_init': float(battery.E_init),
        'values': storage_values
    }

    # Calculate summary
    results['summary'] = calculate_summary(results)

    return results

def calculate_summary(results):
    """Calculate summary statistics."""
    summary = {}

    # Sum flows by type
    total_generation = 0
    total_consumption = 0
    total_grid_import = 0
    total_grid_export = 0

    for flow_key, flow_data in results['flows'].items():
        total = sum(flow_data['values'])

        if 'SolarPV' in flow_data['source']:
            total_generation += total
        if 'PowerDemand' in flow_data['target']:
            total_consumption += total
        if 'Grid' in flow_data['source'] and 'demand' in flow_key:
            total_grid_import += total
        if 'Grid' in flow_data['target']:
            total_grid_export += total

    summary['total_generation'] = total_generation
    summary['total_consumption'] = total_consumption
    summary['total_grid_import'] = total_grid_import
    summary['total_grid_export'] = total_grid_export

    # Battery cycles
    battery_data = results['storage']['Battery']
    total_discharge = sum(
        max(0, battery_data['values'][t-1] - battery_data['values'][t])
        for t in range(1, len(battery_data['values']))
    )
    summary['battery_cycles'] = total_discharge / battery_data['E_max']

    # Energy balance
    energy_in = total_generation + total_grid_import
    energy_out = total_consumption + total_grid_export
    summary['energy_balance_error'] = abs(energy_in - energy_out)

    return summary

def save_results(results, filepath):
    """Save results to JSON."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"Results saved to: {filepath}")

    # Print summary
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    for key, value in results['summary'].items():
        logger.info(f"{key}: {value:.4f}")
    logger.info("="*60)

def main():
    """Main function."""
    logger.info("="*60)
    logger.info("MINIMAL GOLDEN DATASET GENERATOR")
    logger.info("="*60)

    N = 24
    output_file = Path(__file__).parent / 'systemiser_minimal_golden.json'

    try:
        # Create system
        system, components = create_minimal_system_direct(N)

        # Run simulation
        results = run_simulation(system, components, N)

        # Save results
        save_results(results, output_file)

        logger.info("\nSUCCESS! Golden dataset generated.")

    except Exception as e:
        logger.error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()