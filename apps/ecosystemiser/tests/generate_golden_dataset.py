"""
Generate a golden dataset from the original Systemiser for validation.

This script safely extracts a minimal 4-component system from the original
Systemiser without modifying any of the original code. It serves as a
trusted benchmark for validating the new EcoSystemiser architecture.
"""

import sys
from pathlib import Path
import json
import numpy as np
import logging

# Add path to apps directory to import Systemiser
apps_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(apps_path))

# Add Systemiser directory to path to import directly from submodules
systemiser_path = apps_path / 'Systemiser'
sys.path.insert(0, str(systemiser_path))

# Import directly from Systemiser submodules (bypassing broken __init__.py)
from utils.system_setup import create_system
from solver.rule_based_solver import ComponentBasedRuleEngine
from utils.logger import setup_logging

# Setup logging for this script
logger = setup_logging("GoldenDatasetGenerator", level=logging.INFO)


def create_minimal_system(N=24):
    """
    Create a minimal 4-component system from the full Systemiser.

    This function:
    1. Creates the full energy system using original Systemiser
    2. Removes all thermal components
    3. Keeps only: Grid, SolarPV, PowerDemand, Battery

    Args:
        N: Number of timesteps (default 24 for daily simulation)

    Returns:
        Tuple of (system, components) with only the 4 core components
    """
    logger.info("Creating full energy system from original Systemiser...")
    system, components = create_system('energy', N)

    # Components to keep (minimal set for validation)
    keep_components = {'Grid', 'SolarPV', 'PowerDemand', 'Battery'}

    # Components to remove (thermal and water components)
    remove_components = []
    for name in list(components.keys()):
        if name not in keep_components:
            remove_components.append(name)

    logger.info(f"Removing thermal components: {remove_components}")

    # Remove unwanted components from the system
    for comp_name in remove_components:
        if comp_name in system.components:
            del system.components[comp_name]
            del components[comp_name]

    # Also remove flows associated with removed components
    flows_to_remove = []
    for flow_key, flow_data in system.flows.items():
        if (flow_data['source'] not in keep_components or
            flow_data['target'] not in keep_components):
            flows_to_remove.append(flow_key)

    for flow_key in flows_to_remove:
        del system.flows[flow_key]

    logger.info(f"Minimal system created with components: {list(components.keys())}")
    logger.info(f"Remaining flows: {list(system.flows.keys())}")

    return system, components


def run_original_simulation(system, components, N=24):
    """
    Run the original Systemiser's rule-based engine on the minimal system.

    Args:
        system: The minimal system object
        components: Dictionary of component objects
        N: Number of timesteps

    Returns:
        Dictionary containing simulation results
    """
    logger.info("\nRunning original Systemiser simulation...")

    # Create rule engine from original Systemiser
    engine = ComponentBasedRuleEngine(system)

    # Run simulation timestep by timestep
    for t in range(N):
        logger.debug(f"Timestep {t}:")
        engine.solve_timestep(t)

    logger.info("Simulation complete!")

    # Extract results
    results = {
        'metadata': {
            'simulator': 'Systemiser',
            'solver': 'RuleBasedEngine',
            'components': list(components.keys()),
            'timesteps': N,
            'description': 'Golden dataset for 4-component minimal system'
        },
        'flows': {},
        'storage': {}
    }

    # Extract flow results
    for flow_key, flow_data in system.flows.items():
        values = []
        for t in range(N):
            if isinstance(flow_data['value'], np.ndarray):
                val = float(flow_data['value'][t])
            elif hasattr(flow_data['value'], '__getitem__'):
                val = float(flow_data['value'][t])
            else:
                val = 0.0
            values.append(val)

        results['flows'][flow_key] = {
            'source': flow_data['source'],
            'target': flow_data['target'],
            'type': flow_data.get('type', 'electricity'),
            'values': values
        }

    # Extract storage results
    for comp_name, comp in components.items():
        if comp.type == 'storage':
            storage_values = []
            for t in range(N):
                if hasattr(comp, 'E') and comp.E is not None:
                    if isinstance(comp.E, np.ndarray):
                        val = float(comp.E[t])
                    elif hasattr(comp.E, '__getitem__'):
                        val = float(comp.E[t])
                    else:
                        val = getattr(comp, 'E_init', 0.0)
                else:
                    val = getattr(comp, 'E_init', 0.0)
                storage_values.append(val)

            results['storage'][comp_name] = {
                'medium': comp.medium,
                'E_max': float(comp.E_max),
                'E_init': float(getattr(comp, 'E_init', 0.0)),
                'values': storage_values
            }

    # Calculate summary statistics
    results['summary'] = calculate_summary(results)

    return results


def calculate_summary(results):
    """Calculate summary statistics for validation."""
    summary = {}

    # Total energy flows
    total_generation = 0
    total_consumption = 0
    total_grid_import = 0
    total_grid_export = 0
    total_battery_charge = 0
    total_battery_discharge = 0

    for flow_key, flow_data in results['flows'].items():
        total = sum(flow_data['values'])

        if 'SolarPV' in flow_data['source']:
            total_generation += total
        elif 'PowerDemand' in flow_data['target']:
            total_consumption += total
        elif 'Grid' in flow_data['source'] and 'draw' in flow_key:
            total_grid_import += total
        elif 'Grid' in flow_data['target'] and 'feed' in flow_key:
            total_grid_export += total
        elif 'Battery' in flow_data['target'] and 'charge' in flow_key:
            total_battery_charge += total
        elif 'Battery' in flow_data['source'] and 'discharge' in flow_key:
            total_battery_discharge += total

    summary['total_generation'] = total_generation
    summary['total_consumption'] = total_consumption
    summary['total_grid_import'] = total_grid_import
    summary['total_grid_export'] = total_grid_export
    summary['total_battery_charge'] = total_battery_charge
    summary['total_battery_discharge'] = total_battery_discharge

    # Battery cycles
    if 'Battery' in results['storage']:
        battery_capacity = results['storage']['Battery']['E_max']
        if battery_capacity > 0:
            summary['battery_cycles'] = total_battery_discharge / battery_capacity
        else:
            summary['battery_cycles'] = 0

    # Energy balance check
    energy_in = total_generation + total_grid_import + total_battery_discharge
    energy_out = total_consumption + total_grid_export + total_battery_charge
    summary['energy_balance_error'] = abs(energy_in - energy_out)
    summary['energy_balance_relative_error'] = (
        summary['energy_balance_error'] / max(energy_in, 1e-6)
    )

    return summary


def save_golden_dataset(results, filepath):
    """Save the golden dataset to JSON file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Convert numpy arrays to lists for JSON serialization
    def convert_to_serializable(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        return obj

    # Recursively convert all numpy types
    serializable_results = json.loads(
        json.dumps(results, default=convert_to_serializable)
    )

    with open(filepath, 'w') as f:
        json.dump(serializable_results, f, indent=2)

    logger.info(f"Golden dataset saved to: {filepath}")

    # Print summary
    logger.info("\n" + "="*60)
    logger.info("GOLDEN DATASET SUMMARY")
    logger.info("="*60)
    for key, value in results['summary'].items():
        logger.info(f"{key}: {value:.4f}")
    logger.info("="*60)


def main():
    """Main function to generate the golden dataset."""
    logger.info("="*60)
    logger.info("GOLDEN DATASET GENERATOR")
    logger.info("="*60)
    logger.info("This script creates a trusted benchmark from the original Systemiser")
    logger.info("without modifying any production code.")
    logger.info("")

    # Configuration
    N = 24  # 24 hours
    output_file = Path(__file__).parent / 'systemiser_minimal_golden.json'

    try:
        # Step 1: Create minimal system
        system, components = create_minimal_system(N)

        # Step 2: Run original simulation
        results = run_original_simulation(system, components, N)

        # Step 3: Save golden dataset
        save_golden_dataset(results, output_file)

        logger.info("\n✅ Golden dataset generation SUCCESSFUL!")
        logger.info(f"Dataset contains {len(components)} components over {N} timesteps")
        logger.info("This dataset can now be used to validate the EcoSystemiser implementation")

    except Exception as e:
        logger.error(f"❌ Failed to generate golden dataset: {e}")
        raise


if __name__ == "__main__":
    main()