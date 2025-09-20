#!/usr/bin/env python3
"""
Generate golden dataset from original Systemiser for validation.

This script runs the original Systemiser with a minimal component set
and saves the results as our ground truth for validating EcoSystemiser.
"""
import sys
import json
from pathlib import Path
import logging

# Setup paths
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'apps'))  # Add apps directory for Systemiser

# Import original Systemiser
from Systemiser.solver.rule_based_solver import ComponentBasedRuleEngine
from Systemiser.utils.system_setup import create_system
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('GoldenDataset')

def create_minimal_energy_system(N=24):
    """
    Create a minimal energy system matching our EcoSystemiser MVP:
    - Grid (transmission)
    - SolarPV (generation)
    - PowerDemand (consumption)
    - Battery (storage)
    """
    from Systemiser.system.components import (
        Grid, SolarPV, PowerDemand, Battery
    )

    # Create components
    components = {
        'grid': Grid(name='grid', N=N),
        'solar_pv': SolarPV(name='solar_pv', N=N, capacity=5.0),
        'power_demand': PowerDemand(name='power_demand', N=N),
        'battery': Battery(
            name='battery',
            N=N,
            E_max=10.0,
            P_charge_max=5.0,
            P_discharge_max=5.0,
            eta_charge=0.95,
            eta_discharge=0.95,
            E_init=5.0
        )
    }

    # Create simplified system object
    class MinimalSystem:
        def __init__(self, components, N):
            self.components = components
            self.N = N
            self.flows = {}

    system = MinimalSystem(components, N)

    # Setup connections (flows will be populated by solver)
    # The solver will handle the actual flow creation

    return system, components

def extract_results(system):
    """Extract results in a format we can compare."""
    results = {
        'storage_levels': {},
        'flows': [],
        'metadata': {
            'N': system.N,
            'components': list(system.components.keys())
        }
    }

    # Extract storage levels
    for name, comp in system.components.items():
        if hasattr(comp, 'E') and comp.type == 'storage':
            levels = []
            for t in range(system.N):
                try:
                    if hasattr(comp.E[t], 'value'):
                        value = float(comp.E[t].value) if comp.E[t].value is not None else 0.0
                    else:
                        value = float(comp.E[t]) if comp.E[t] is not None else 0.0
                except (TypeError, AttributeError, IndexError):
                    value = 0.0
                levels.append(value)
            results['storage_levels'][name] = {
                'values': levels,
                'max_capacity': float(comp.E_max) if hasattr(comp, 'E_max') else None
            }

    # Extract flows
    for flow_id, flow_data in system.flows.items():
        if 'value' in flow_data:
            values = []
            for t in range(system.N):
                try:
                    if isinstance(flow_data['value'], (list, np.ndarray)):
                        if hasattr(flow_data['value'][t], 'value'):
                            val = float(flow_data['value'][t].value) if flow_data['value'][t].value is not None else 0.0
                        else:
                            val = float(flow_data['value'][t]) if flow_data['value'][t] is not None else 0.0
                    else:
                        val = 0.0
                except (TypeError, AttributeError, IndexError):
                    val = 0.0
                values.append(val)

            results['flows'].append({
                'id': flow_id,
                'from': flow_data.get('source', 'unknown'),
                'to': flow_data.get('target', 'unknown'),
                'type': flow_data.get('type', 'electricity'),
                'values': values
            })

    return results

def main():
    """Generate golden dataset."""
    logger.info("Creating minimal energy system from original Systemiser...")

    # Create minimal system
    N = 24
    system, components = create_minimal_energy_system(N)

    logger.info(f"Components: {list(components.keys())}")

    # Create and run solver
    logger.info("Running rule-based solver...")
    engine = ComponentBasedRuleEngine(system)

    # Solve timestep by timestep
    for t in range(N):
        engine.solve_timestep(t)

        # Log progress
        if t % 6 == 0:
            battery = components['battery']
            try:
                level = float(battery.E[t]) if hasattr(battery, 'E') else battery.E_init
                logger.info(f"Timestep {t}: Battery level = {level:.2f} kWh")
            except:
                pass

    logger.info("Extracting results...")
    results = extract_results(system)

    # Save golden dataset
    output_path = Path(__file__).parent / 'tests' / 'systemiser_golden_results.json'
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"✅ Golden dataset saved to: {output_path}")

    # Print summary
    logger.info("\n📊 Summary:")
    logger.info(f"  - Timesteps: {N}")
    logger.info(f"  - Components: {len(components)}")
    logger.info(f"  - Flows captured: {len(results['flows'])}")

    if results['storage_levels']:
        for name, data in results['storage_levels'].items():
            min_val = min(data['values'])
            max_val = max(data['values'])
            logger.info(f"  - {name} range: {min_val:.2f} - {max_val:.2f} kWh")

    return output_path

if __name__ == "__main__":
    try:
        output_path = main()
        print(f"\n✅ SUCCESS: Golden dataset generated at {output_path}")
    except Exception as e:
        logger.error(f"Failed to generate golden dataset: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)