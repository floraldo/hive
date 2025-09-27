"""
Formal validation test comparing EcoSystemiser against Systemiser golden dataset.

This test ensures numerical equivalence between the new architecture and
the original Systemiser for a minimal 4-component system.
"""

import json
import numpy as np
import pytest
from pathlib import Path

# Add parent directories to path for imports
import sys
eco_path = Path(__file__).parent.parent / 'src' / 'EcoSystemiser'
from system_model.system import System
from system_model.system_builder import SystemBuilder
from solver.rule_based_engine import RuleBasedEngine

class TestSystemEquivalence:
    """Test suite for validating EcoSystemiser against Systemiser golden dataset."""

    @pytest.fixture
    def golden_dataset(self):
        """Load the golden dataset from Systemiser."""
        golden_path = Path(__file__).parent / 'systemiser_minimal_golden.json'
        with open(golden_path, 'r') as f:
            return json.load(f)

    @pytest.fixture
    def eco_system(self):
        """Create EcoSystemiser system matching golden dataset configuration."""
        N = 24
        system = System('minimal_validation', N)

        # Create profiles matching the golden dataset
        # Solar profile (peak at midday)
        solar_profile = np.zeros(N)
        for t in range(N):
            if 6 <= t <= 18:  # Daylight hours
                solar_profile[t] = np.sin((t - 6) * np.pi / 12) * 5.0  # Peak 5 kW at noon

        # Demand profile (baseload + peaks)
        demand_profile = np.ones(N) * 1.0  # 1 kW baseload
        demand_profile[7:9] = 2.0   # Morning peak
        demand_profile[18:21] = 2.5  # Evening peak

        # Use SystemBuilder to create components
        builder = SystemBuilder()

        # Grid
        grid = builder.create_component('Grid', {
            'P_max': 100,
            'import_tariff': 0.25,
            'feed_in_tariff': 0.08
        })
        system.add_component(grid)

        # Battery
        battery = builder.create_component('Battery', {
            'P_max': 5,
            'E_max': 10,
            'E_init': 5,
            'eta_charge': 0.95,
            'eta_discharge': 0.95
        })
        system.add_component(battery)

        # SolarPV
        solar = builder.create_component('SolarPV', {
            'P_profile': solar_profile.tolist(),
            'P_max': 10
        })
        system.add_component(solar)

        # PowerDemand
        demand = builder.create_component('PowerDemand', {
            'P_profile': demand_profile.tolist(),
            'P_max': 5
        })
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

    def run_eco_simulation(self, system):
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
                'E_max': battery_comp.E_max,
                'E_init': battery_comp.E_init,
                'values': battery_comp.E.tolist() if isinstance(battery_comp.E, np.ndarray) else [battery_comp.E_init] * N
            }

        return results

    def test_minimal_system_equivalence(self, golden_dataset, eco_system):
        """
        Test that EcoSystemiser produces identical results to Systemiser
        for the minimal 4-component system.
        """
        # Run EcoSystemiser simulation
        eco_results = self.run_eco_simulation(eco_system)

        # Tolerance for numerical comparison
        TOLERANCE = 1e-6

        # Compare flows
        for flow_key in golden_dataset['flows']:
            assert flow_key in eco_results['flows'], f"Flow {flow_key} missing in EcoSystemiser results"

            golden_flow = golden_dataset['flows'][flow_key]
            eco_flow = eco_results['flows'][flow_key]

            # Check metadata
            assert golden_flow['source'] == eco_flow['source'], f"Source mismatch for {flow_key}"
            assert golden_flow['target'] == eco_flow['target'], f"Target mismatch for {flow_key}"
            assert golden_flow['type'] == eco_flow['type'], f"Type mismatch for {flow_key}"

            # Check values
            golden_values = np.array(golden_flow['values'])
            eco_values = np.array(eco_flow['values'])

            max_diff = np.max(np.abs(golden_values - eco_values))
            assert max_diff < TOLERANCE, (
                f"Flow {flow_key} values differ by {max_diff:.6e}\n"
                f"Golden: {golden_values[:5]}...\n"
                f"Eco: {eco_values[:5]}..."
            )

        # Compare storage
        for storage_key in golden_dataset['storage']:
            assert storage_key in eco_results['storage'], f"Storage {storage_key} missing in EcoSystemiser"

            golden_storage = golden_dataset['storage'][storage_key]
            eco_storage = eco_results['storage'][storage_key]

            # Check metadata
            assert abs(golden_storage['E_max'] - eco_storage['E_max']) < TOLERANCE, f"E_max mismatch for {storage_key}"
            assert abs(golden_storage['E_init'] - eco_storage['E_init']) < TOLERANCE, f"E_init mismatch for {storage_key}"

            # Check values
            golden_values = np.array(golden_storage['values'])
            eco_values = np.array(eco_storage['values'])

            max_diff = np.max(np.abs(golden_values - eco_values))
            assert max_diff < TOLERANCE, (
                f"Storage {storage_key} values differ by {max_diff:.6e}\n"
                f"Golden: {golden_values[:5]}...\n"
                f"Eco: {eco_values[:5]}..."
            )

        print("\n✅ VALIDATION SUCCESSFUL!")
        print(f"EcoSystemiser matches Systemiser within tolerance {TOLERANCE}")

    def test_energy_balance(self, eco_system):
        """Test that energy balance is maintained at each timestep."""
        # Run simulation
        eco_results = self.run_eco_simulation(eco_system)

        N = eco_system.N
        for t in range(N):
            generation = 0
            consumption = 0
            battery_change = 0

            # Sum flows
            for flow_key, flow_data in eco_results['flows'].items():
                value = flow_data['values'][t]

                if 'SolarPV' in flow_data['source']:
                    generation += value
                if 'PowerDemand' in flow_data['target']:
                    consumption += value

            # Battery change
            if 'Battery' in eco_results['storage']:
                battery_values = eco_results['storage']['Battery']['values']
                if t > 0:
                    battery_change = battery_values[t] - battery_values[t-1]
                else:
                    battery_change = battery_values[t] - eco_results['storage']['Battery']['E_init']

            # Energy balance (allowing for small numerical errors)
            balance_error = abs((generation - consumption - battery_change))
            assert balance_error < 0.01, f"Energy imbalance at t={t}: {balance_error:.6f} kWh"

        print("\n✅ Energy balance validated for all timesteps")

if __name__ == "__main__":
    # Run tests directly
    test = TestSystemEquivalence()

    # Load fixtures
    golden_path = Path(__file__).parent / 'systemiser_minimal_golden.json'
    with open(golden_path, 'r') as f:
        golden_dataset = json.load(f)

    # Create eco system
    eco_system = test.eco_system()

    # Run validation
    try:
        test.test_minimal_system_equivalence(golden_dataset, eco_system)
        test.test_energy_balance(eco_system)
        print("\n" + "="*60)
        print("ALL VALIDATION TESTS PASSED!")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        raise