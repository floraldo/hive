#!/usr/bin/env python3
"""
Validation script to compare EcoSystemiser output against golden dataset from original Systemiser.

This script:
1. Runs EcoSystemiser with the same configuration as original Systemiser
2. Compares the results against the golden dataset
3. Reports any numerical discrepancies
"""
import json
import logging
import sys
from pathlib import Path

import numpy as np

# Setup paths
project_root = Path(__file__).parent.parent.parent
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Validation")


def run_ecosystemiser():
    """Run the new EcoSystemiser and get results."""
    logger.info("Running EcoSystemiser...")

    # Import EcoSystemiser components
    from ecosystemiser.src.EcoSystemiser.services.simulation_service import (
        SimulationService,
    )
    from ecosystemiser.src.EcoSystemiser.system_model.system_builder import (
        SystemBuilder,
    )

    # Create minimal system configuration
    config = {
        "name": "validation_system",
        "timesteps": 24,
        "components": {
            "grid": {
                "type": "Grid",
                "params": {"max_import_kw": 1000.0, "max_export_kw": 1000.0},
            },
            "solar_pv": {"type": "SolarPV", "params": {"capacity_kw": 5.0}},
            "battery": {
                "type": "Battery",
                "params": {
                    "capacity_kwh": 10.0,
                    "max_charge_kw": 5.0,
                    "max_discharge_kw": 5.0,
                    "round_trip_efficiency": 0.92,
                    "min_soc": 0.1,
                    "max_soc": 0.9,
                    "initial_soc": 0.5,
                },
            },
            "power_demand": {
                "type": "PowerDemand",
                "params": {
                    "profile_data": [8.0] * 24  # Simple flat demand for testing
                },
            },
        },
        "connections": [
            {"from": "grid", "to": "battery"},
            {"from": "battery", "to": "grid"},
            {"from": "solar_pv", "to": "battery"},
            {"from": "solar_pv", "to": "power_demand"},
            {"from": "battery", "to": "power_demand"},
            {"from": "grid", "to": "power_demand"},
        ],
    }

    # Build system
    builder = SystemBuilder()
    system = builder.build_from_config(config)

    # Run simulation
    service = SimulationService()
    results = service.simulate(system=system, solver_type="rule_based")

    return results


def extract_comparable_data(data):
    """Extract key metrics for comparison."""
    metrics = {"flows": {}, "storage": {}}

    # Extract flows
    if "flows" in data:
        for flow in data["flows"]:
            key = f"{flow.get('from', 'unknown')}_{flow.get('to', 'unknown')}"
            metrics["flows"][key] = {
                "values": flow.get("values", []),
                "total": flow.get("total", 0),
                "mean": flow.get("mean", 0),
            }

    # Extract storage levels (if present)
    if "storage_levels" in data:
        for name, levels in data["storage_levels"].items():
            metrics["storage"][name] = levels

    return metrics


def compare_results(golden_data, new_data, tolerance=1e-6):
    """Compare results and report discrepancies."""
    logger.info("\nComparing results against golden dataset...")

    golden_metrics = extract_comparable_data(golden_data)
    new_metrics = extract_comparable_data(new_data)

    discrepancies = []
    matches = []

    # Compare flows
    logger.info("\nFlow Comparison:")
    logger.info("-" * 50)

    for flow_key, golden_flow in golden_metrics["flows"].items():
        if flow_key in new_metrics["flows"]:
            new_flow = new_metrics["flows"][flow_key]

            # Compare values array
            if "values" in golden_flow and "values" in new_flow:
                golden_vals = np.array(golden_flow["values"])
                new_vals = np.array(new_flow["values"])

                if len(golden_vals) == len(new_vals):
                    if np.allclose(golden_vals, new_vals, atol=tolerance):
                        matches.append(f"Flow {flow_key}: MATCH")
                    else:
                        max_diff = np.max(np.abs(golden_vals - new_vals))
                        avg_diff = np.mean(np.abs(golden_vals - new_vals))
                        discrepancies.append(
                            f"Flow {flow_key}: MISMATCH (max_diff={max_diff:.6f}, avg_diff={avg_diff:.6f})"
                        )
                else:
                    discrepancies.append(
                        f"Flow {flow_key}: LENGTH MISMATCH (golden={len(golden_vals)}, new={len(new_vals)})"
                    )
        else:
            discrepancies.append(f"Flow {flow_key}: MISSING in new results")

    # Check for extra flows in new results
    for flow_key in new_metrics["flows"]:
        if flow_key not in golden_metrics["flows"]:
            discrepancies.append(
                f"Flow {flow_key}: EXTRA in new results (not in golden)"
            )

    # Print results
    logger.info(f"\n✅ Matches: {len(matches)}")
    for match in matches[:5]:  # Show first 5 matches
        logger.info(f"  {match}")

    if discrepancies:
        logger.warning(f"\n⚠️ Discrepancies: {len(discrepancies)}")
        for disc in discrepancies:
            logger.warning(f"  {disc}")
    else:
        logger.info("\n🎉 Perfect match! All values within tolerance.")

    # Calculate overall similarity
    total_comparisons = len(golden_metrics["flows"])
    successful_matches = len(matches)
    similarity_percentage = (
        (successful_matches / total_comparisons * 100) if total_comparisons > 0 else 0
    )

    logger.info(f"\n📊 Overall Similarity: {similarity_percentage:.1f}%")

    return len(discrepancies) == 0, similarity_percentage


def main():
    """Run validation test."""
    logger.info("=" * 60)
    logger.info("EcoSystemiser Validation Test")
    logger.info("=" * 60)

    # Load golden dataset
    golden_path = Path(__file__).parent / "tests" / "systemiser_golden_results.json"

    if not golden_path.exists():
        logger.error(f"Golden dataset not found at {golden_path}")
        logger.error("Please run generate_golden_dataset.py first")
        return False

    logger.info(f"Loading golden dataset from {golden_path}")
    with open(golden_path, "r") as f:
        golden_data = json.load(f)

    # Run EcoSystemiser
    try:
        new_results = run_ecosystemiser()

        # Save new results for inspection
        output_path = (
            Path(__file__).parent / "tests" / "ecosystemiser_test_results.json"
        )
        with open(output_path, "w") as f:
            json.dump(new_results, f, indent=2)
        logger.info(f"New results saved to {output_path}")

    except Exception as e:
        logger.error(f"Failed to run EcoSystemiser: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Compare results
    success, similarity = compare_results(golden_data, new_results)

    logger.info("\n" + "=" * 60)
    if success:
        logger.info("✅ VALIDATION PASSED: Results match golden dataset")
    elif similarity > 90:
        logger.info("⚠️ VALIDATION WARNING: Results are close but not exact")
    else:
        logger.error("❌ VALIDATION FAILED: Significant discrepancies found")

    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Validation script failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
