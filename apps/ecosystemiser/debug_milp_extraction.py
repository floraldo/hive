#!/usr/bin/env python3
"""Debug MILP flow extraction to ensure non-zero values."""

import sys
import os

import json
from pathlib import Path
from ecosystemiser.services.results_io import ResultsIO
from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.system_model.system import System
from ecosystemiser.core.logging import get_logger

logger = get_logger(__name__)

def test_milp_flow_extraction() -> None:
    """Test MILP solver flow extraction with enhanced logic."""

    # Load existing golden system configuration
    config_path = "config/systems/golden_residential_microgrid.yml"
    if not Path(config_path).exists():
        config_path = "data/yearly_scenarios/golden_residential_yearly.json"

    if not Path(config_path).exists():
        print("No test configuration found")
        return

    # Load configuration
    if config_path.endswith('.json'):
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

    print(f"Testing MILP flow extraction with: {config_path}")

    # Create system and run MILP solver for short test (24 hours)
    try:
        # Limit to 24 timesteps for quick test
        if isinstance(config, dict) and 'N' in config:
            config['N'] = 24
        elif isinstance(config, dict) and 'timesteps' in config:
            config['timesteps'] = 24

        system = System.from_config(config)

        # Run MILP solver
        solver = MILPSolver()
        result = solver.solve(system)

        print(f"MILP Status: {result['status']}")
        print(f"MILP Objective: {result.get('objective_value', 'N/A')}")

        # Extract results using enhanced logic
        results_io = ResultsIO()
        extracted_results = results_io._extract_system_results(system)

        # Check flow extraction
        total_flows = 0
        non_zero_flows = 0

        for flow_name, flow_data in extracted_results["flows"].items():
            if "value" in flow_data:
                flow_values = flow_data["value"]
                if flow_values:
                    total_flows += 1
                    flow_sum = sum(abs(v) for v in flow_values if v is not None)
                    if flow_sum > 1e-9:  # Non-zero threshold
                        non_zero_flows += 1
                        print(f"✅ Flow {flow_name}: Sum = {flow_sum:.3f} kW")
                    else:
                        print(f"❌ Flow {flow_name}: All zeros")

        print(f"\nFlow Extraction Summary:")
        print(f"  Total flows: {total_flows}")
        print(f"  Non-zero flows: {non_zero_flows}")
        print(f"  Success rate: {non_zero_flows/total_flows*100:.1f}%" if total_flows > 0 else "No flows found")

        # Check component states
        total_components = 0
        valid_components = 0

        for comp_name, comp_data in extracted_results["components"].items():
            total_components += 1
            if "E" in comp_data and comp_data["E"]:
                storage_sum = sum(abs(v) for v in comp_data["E"] if v is not None)
                if storage_sum > 1e-9:
                    valid_components += 1
                    print(f"✅ Component {comp_name}: Energy sum = {storage_sum:.3f} kWh")

        if total_components > 0:
            print(f"\nComponent Extraction Summary:")
            print(f"  Total components: {total_components}")
            print(f"  Valid components: {valid_components}")

        # Save test results
        output_path = "data/milp_extraction_test_results.json"
        results_io.save_results(system, "milp_extraction_test", Path("data"), format="json")
        print(f"\nTest results saved to: {output_path}")

        return non_zero_flows > 0

    except Exception as e:
        print(f"❌ MILP test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_milp_flow_extraction()
    sys.exit(0 if success else 1)
