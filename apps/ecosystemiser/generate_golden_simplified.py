#!/usr/bin/env python3
"""
Simplified golden dataset generation - run original Systemiser to get baseline results.
"""
import sys
import json
from pathlib import Path
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('GoldenDataset')

def run_original_systemiser():
    """Run the original Systemiser and capture its output."""

    # Change to Systemiser directory
    systemiser_dir = Path(__file__).parent.parent / 'Systemiser'

    logger.info(f"Running original Systemiser from: {systemiser_dir}")

    # Run the Systemiser
    cmd = [sys.executable, "run.py"]

    result = subprocess.run(
        cmd,
        cwd=str(systemiser_dir),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        logger.error(f"Systemiser failed: {result.stderr}")
        return None

    logger.info("Systemiser completed successfully")

    # Find the output file
    output_file = systemiser_dir / 'output' / 'solved_system_flows_hourly.json'

    if not output_file.exists():
        # Try alternative output location
        output_file = systemiser_dir / 'solved_system_flows_hourly.json'

    if not output_file.exists():
        logger.error(f"Output file not found at {output_file}")
        # List what files we do have
        output_dir = systemiser_dir / 'output'
        if output_dir.exists():
            logger.info(f"Files in output directory: {list(output_dir.glob('*'))}")
        return None

    return output_file

def extract_minimal_components(original_data):
    """
    Extract only the minimal component set from the original results:
    - Grid
    - SolarPV
    - PowerDemand
    - Battery
    """
    minimal_data = {
        'storage_levels': {},
        'flows': [],
        'metadata': original_data.get('metadata', {})
    }

    # Filter storage levels for battery only
    if 'storage_levels' in original_data:
        for comp_name, comp_data in original_data['storage_levels'].items():
            if 'battery' in comp_name.lower():
                minimal_data['storage_levels'][comp_name] = comp_data

    # Filter flows for our minimal components
    minimal_components = ['grid', 'solar', 'pv', 'power_demand', 'demand', 'battery']

    if 'flows' in original_data:
        for flow in original_data['flows']:
            from_comp = flow.get('from', '').lower()
            to_comp = flow.get('to', '').lower()

            # Check if this flow involves our minimal components
            involves_minimal = any(comp in from_comp for comp in minimal_components) or \
                              any(comp in to_comp for comp in minimal_components)

            if involves_minimal:
                minimal_data['flows'].append(flow)

    return minimal_data

def main():
    """Generate golden dataset from original Systemiser."""

    logger.info("Step 1: Running original Systemiser...")
    output_file = run_original_systemiser()

    if not output_file:
        logger.error("Failed to run Systemiser or find output")
        return None

    logger.info(f"Step 2: Loading results from {output_file}")

    with open(output_file, 'r') as f:
        original_data = json.load(f)

    logger.info("Step 3: Extracting minimal component subset...")
    minimal_data = extract_minimal_components(original_data)

    # Save as golden dataset
    output_path = Path(__file__).parent / 'tests' / 'systemiser_golden_results.json'
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(minimal_data, f, indent=2)

    logger.info(f"Golden dataset saved to: {output_path}")

    # Print summary
    logger.info("\nGolden Dataset Summary:")
    logger.info(f"  - Storage components: {len(minimal_data['storage_levels'])}")
    logger.info(f"  - Flows captured: {len(minimal_data['flows'])}")

    if minimal_data['storage_levels']:
        for name, data in minimal_data['storage_levels'].items():
            if 'values' in data:
                values = data['values']
                logger.info(f"  - {name}: {len(values)} timesteps")

    return output_path

if __name__ == "__main__":
    try:
        output_path = main()
        if output_path:
            print(f"\nSUCCESS: Golden dataset generated at {output_path}")
        else:
            print("\nFAILED: Could not generate golden dataset")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to generate golden dataset: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)