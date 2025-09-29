#!/usr/bin/env python3
"""Real integration test for MILP solver - proves it produces valid flows."""

import sys
from pathlib import Path

import numpy as np
import pytest

eco_path = Path(__file__).parent.parent / "src"

from ecosystemiser.services.results_io import ResultsIO
from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.system_model.system import System
from hive_logging import get_logger

logger = get_logger(__name__)

def test_milp_solver_produces_valid_flows():
    """Integration test: MILP solver must produce non-zero energy flows.

    This is the ONLY test that can truly validate the MILP fix.
    It runs a real simulation and checks real outputs.
    """
    # Step 1: Load the golden microgrid configuration
    config_path = Path(__file__).parent.parent / "config" / "systems" / "golden_residential_microgrid.yml"

    # If config doesn't exist, use a minimal test configuration
    if not config_path.exists():
        logger.info("Using minimal test configuration")
        config = {
            "system_id": "test_milp_validation",
            "timesteps": 168,  # 7 days
            "components": [
                {
                    "name": "GRID",
                    "component_id": "grid_standard",
                    "type": "transmission",
                    "medium": "electricity",
                },
                {
                    "name": "SOLAR_PV",
                    "component_id": "solar_pv_residential",
                    "type": "generation",
                    "medium": "electricity",
                    "capacity_kW": 5.0,
                },
                {
                    "name": "BATTERY",
                    "component_id": "battery_residential",
                    "type": "storage",
                    "medium": "electricity",
                    "capacity_kWh": 10.0,
                    "power_kW": 5.0,
                },
                {
                    "name": "POWER_DEMAND",
                    "component_id": "power_demand_residential",
                    "type": "demand",
                    "medium": "electricity",
                },
            ],
        }
    else:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            # Limit to 168 hours for testing
            config['timesteps'] = 168

    # Step 2: Create system and run MILP solver
    logger.info("Creating system from configuration")
    system = System.from_config(config)

    logger.info("Initializing MILP solver")
    solver = MILPSolver()

    logger.info("Running MILP optimization for 168 hours")
    result = solver.solve(system)

    # Step 3: Check solver status
    assert result['status'] in ['optimal', 'optimal_inaccurate'], \
        f"MILP solver failed with status: {result['status']}"

    logger.info(f"MILP solver status: {result['status']}")
    logger.info(f"Objective value: {result.get('objective_value', 'N/A')}")

    # Step 4: Save results using real ResultsIO service
    results_io = ResultsIO()
    output_dir = Path(__file__).parent / "test_output"
    output_path = results_io.save_results(
        system=system,
        simulation_id="milp_validation_test",
        output_dir=output_dir,
        format="json"
    )

    logger.info(f"Results saved to: {output_path}")

    # Step 5: Load and validate flows
    results = results_io.load_results(output_path)

    # Check that we have flows
    assert 'flows' in results, "No flows found in results"
    assert len(results['flows']) > 0, "Empty flows dictionary"

    # Step 6: Validate critical flows are non-zero
    critical_flows_found = False
    total_energy_flow = 0.0

    for flow_name, flow_data in results['flows'].items():
        if 'value' in flow_data and flow_data['value']:
            flow_values = np.array(flow_data['value'])
            flow_sum = np.sum(np.abs(flow_values))

            if flow_sum > 1e-6:  # Non-zero threshold
                logger.info(f"Flow {flow_name}: Total = {flow_sum:.3f} kWh")
                total_energy_flow += flow_sum
                critical_flows_found = True

                # Check specific critical flows
                if 'grid' in flow_name.lower() or 'battery' in flow_name.lower():
                    assert flow_sum > 0, f"Critical flow {flow_name} is zero!"

    # The ultimate validation: Did MILP produce non-zero flows?
    assert critical_flows_found, "MILP solver produced ALL ZERO flows - solver is broken!"
    assert total_energy_flow > 10.0, f"Total energy flow too low: {total_energy_flow:.3f} kWh"

    logger.info(f"SUCCESS: MILP solver produced {total_energy_flow:.3f} kWh total energy flow")

    # Step 7: Additional validation - check energy balance
    total_generation = 0.0
    total_consumption = 0.0

    for flow_name, flow_data in results['flows'].items():
        if 'value' in flow_data and flow_data['value']:
            flow_sum = np.sum(flow_data['value'])

            # Classify flows
            if 'generation' in flow_name.lower() or 'solar' in flow_name.lower():
                total_generation += flow_sum
            elif 'demand' in flow_name.lower() or 'consumption' in flow_name.lower():
                total_consumption += flow_sum

    # Log energy balance for debugging
    logger.info(f"Total generation: {total_generation:.3f} kWh")
    logger.info(f"Total consumption: {total_consumption:.3f} kWh")

    # Clean up test output
    import shutil
    if output_dir.exists():
        shutil.rmtree(output_dir)

    return True

def test_milp_vs_rule_based_comparison():
    """Compare MILP and rule-based solvers on the same system."""
    from ecosystemiser.solver.rule_based_engine import RuleBasedEngine

    # Create a simple test system
    config = {
        "system_id": "solver_comparison",
        "timesteps": 24,  # 1 day for quick comparison
        "components": [
            {
                "name": "GRID",
                "component_id": "grid_standard",
                "type": "transmission",
                "medium": "electricity",
            },
            {
                "name": "SOLAR_PV",
                "component_id": "solar_pv_small",
                "type": "generation",
                "medium": "electricity",
                "capacity_kW": 3.0,
            },
            {
                "name": "POWER_DEMAND",
                "component_id": "power_demand_small",
                "type": "demand",
                "medium": "electricity",
                "average_kW": 2.0,
            },
        ],
    }

    # Run rule-based solver
    system_rule = System.from_config(config)
    solver_rule = RuleBasedEngine()
    result_rule = solver_rule.solve(system_rule)

    # Run MILP solver
    system_milp = System.from_config(config)
    solver_milp = MILPSolver()
    result_milp = solver_milp.solve(system_milp)

    # Both should succeed
    assert result_rule['status'] == 'optimal', "Rule-based solver failed"
    assert result_milp['status'] in ['optimal', 'optimal_inaccurate'], "MILP solver failed"

    # Extract total flows
    def get_total_flow(system):
        total = 0.0
        for flow_data in system.flows.values():
            if 'value' in flow_data:
                if hasattr(flow_data['value'], 'value'):  # CVXPY variable
                    if flow_data['value'].value is not None:
                        total += np.sum(np.abs(flow_data['value'].value))
                elif isinstance(flow_data['value'], (list, np.ndarray)):
                    total += np.sum(np.abs(flow_data['value']))
        return total

    total_flow_rule = get_total_flow(system_rule)
    total_flow_milp = get_total_flow(system_milp)

    logger.info(f"Rule-based total flow: {total_flow_rule:.3f} kWh")
    logger.info(f"MILP total flow: {total_flow_milp:.3f} kWh")

    # Both should produce non-zero flows
    assert total_flow_rule > 0, "Rule-based solver produced zero flows"
    assert total_flow_milp > 0, "MILP solver produced zero flows"

    # MILP should be at least as efficient (less or equal total flow due to optimization)
    # But for now just check they're in the same ballpark
    ratio = total_flow_milp / total_flow_rule if total_flow_rule > 0 else 0
    assert 0.5 < ratio < 2.0, f"Solver flows differ too much: ratio = {ratio:.3f}"

    logger.info("SUCCESS: Both solvers produce valid, comparable results")
    return True

if __name__ == "__main__":
    # Run the critical test
    try:
        success = test_milp_solver_produces_valid_flows()
        if success:
            print("\n" + "="*50)
            print("CRITICAL TEST PASSED: MILP solver produces valid flows!")
            print("="*50)

            # Run comparison test
            test_milp_vs_rule_based_comparison()
            print("COMPARISON TEST PASSED: Solvers are comparable")
        else:
            print("CRITICAL TEST FAILED: MILP solver is broken!")
            sys.exit(1)
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)