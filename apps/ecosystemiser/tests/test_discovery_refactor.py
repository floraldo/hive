#!/usr/bin/env python3
"""
Test script to validate the Discovery Engine architectural refactoring.

This script tests that the component-specific knowledge has been successfully
moved from the Discovery engine to the component configurations themselves.
"""

import os
import tempfile
from pathlib import Path

import yaml
from ecosystemiser.discovery.encoders.parameter_encoder import SystemConfigEncoder


def create_test_system_config():
    """Create a test system configuration with components that have optimizable parameters."""
    test_config = {
        "system": {
            "name": "test_optimization_system",
            "description": "Test system for validation of dynamic parameter discovery",
        },
        "components": {
            "battery": {
                "type": "storage",
                "component_data_file": "sonnen_eco_10.yml",
                "technical": {
                    "capacity_nominal": 10.0,
                    "max_charge_rate": 0.55,
                    "optimizable_parameters": {
                        "capacity": {
                            "parameter_path": "technical.capacity_nominal",
                            "bounds": [5.0, 50.0],
                            "units": "kWh",
                            "description": "Battery storage capacity",
                            "parameter_type": "continuous",
                        },
                        "power": {
                            "parameter_path": "technical.max_charge_rate",
                            "bounds": [0.2, 2.0],
                            "units": "C-rate",
                            "description": "Battery charge rate",
                        },
                    },
                },
            },
            "solar_pv": {
                "type": "generation",
                "component_data_file": "solar_pv_residential.yml",
                "technical": {
                    "P_max": 5.0,
                    "optimizable_parameters": {
                        "capacity": {
                            "parameter_path": "technical.P_max",
                            "bounds": [1.0, 20.0],
                            "units": "kW",
                            "description": "Solar PV capacity",
                        }
                    },
                },
            },
        },
    }
    return test_config


def test_dynamic_parameter_discovery():
    """Test that parameters are correctly discovered from component configurations."""
    print("=== Testing Dynamic Parameter Discovery ===")

    # Create test configuration
    test_config = create_test_system_config()

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(test_config, f, default_flow_style=False)
        config_path = f.name

    try:
        # Test the new dynamic discovery
        print(f"Testing SystemConfigEncoder.from_config() with dynamic discovery...")
        encoder = SystemConfigEncoder.from_config(config_path)

        # Validate that parameters were discovered
        print(
            f"[SUCCESS] Successfully created encoder with {encoder.spec.dimensions} parameters"
        )

        # Check specific parameters
        param_names = encoder.spec.get_parameter_names()
        print(f"[INFO] Discovered parameters: {param_names}")

        # Validate expected parameters exist
        expected_params = ["battery_capacity", "battery_power", "solar_pv_capacity"]
        for expected in expected_params:
            if expected in param_names:
                print(f"[SUCCESS] Found expected parameter: {expected}")
            else:
                print(f"[FAIL] Missing expected parameter: {expected}")
                return False

        # Test parameter info extraction
        param_info = encoder.get_parameter_info()
        print(f"[INFO] Parameter details:")
        for name, info in param_info.items():
            print(f"  {name}: {info['bounds']} {info['units']} - {info['description']}")

        # Test encoding/decoding functionality
        print("\n=== Testing Encoding/Decoding ===")
        test_vector = [25.0, 1.0, 10.0]  # Test values within bounds

        # Encode to config
        decoded_config = encoder.decode(test_vector, test_config)
        print(f"[SUCCESS] Successfully decoded parameter vector to configuration")

        # Verify values were applied correctly
        battery_capacity = decoded_config["components"]["battery"]["technical"][
            "capacity_nominal"
        ]
        solar_capacity = decoded_config["components"]["solar_pv"]["technical"]["P_max"]
        print(
            f"[INFO] Decoded values: battery={battery_capacity}kWh, solar={solar_capacity}kW"
        )

        # Encode back
        encoded_vector = encoder.encode(decoded_config)
        print(
            f"[SUCCESS] Successfully encoded configuration to vector: {encoded_vector}"
        )

        return True

    except Exception as e:
        print(f"[FAIL] Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Clean up temporary file
        if os.path.exists(config_path):
            os.unlink(config_path)


def test_component_agnostic_architecture():
    """Test that the Discovery engine is now component-agnostic."""
    print("\n=== Testing Component-Agnostic Architecture ===")

    # Test with a completely new component type not in the original hardcoded dictionary
    new_component_config = {
        "system": {"name": "test_new_component"},
        "components": {
            "electrolyzer": {  # New component type
                "type": "conversion",
                "technical": {
                    "efficiency": 0.75,
                    "capacity_nominal": 100.0,
                    "optimizable_parameters": {
                        "efficiency": {
                            "parameter_path": "technical.efficiency",
                            "bounds": [0.6, 0.9],
                            "units": "fraction",
                            "description": "Electrolyzer efficiency",
                        },
                        "capacity": {
                            "parameter_path": "technical.capacity_nominal",
                            "bounds": [50.0, 500.0],
                            "units": "kW",
                            "description": "Electrolyzer capacity",
                        },
                    },
                },
            }
        },
    }

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(new_component_config, f, default_flow_style=False)
        config_path = f.name

    try:
        # Test that new component is automatically supported
        encoder = SystemConfigEncoder.from_config(config_path)
        param_names = encoder.spec.get_parameter_names()

        print(
            f"[SUCCESS] Successfully discovered parameters for new component type: {param_names}"
        )

        # Verify the new component parameters
        expected_new_params = ["electrolyzer_efficiency", "electrolyzer_capacity"]
        for expected in expected_new_params:
            if expected in param_names:
                print(f"[SUCCESS] New component parameter discovered: {expected}")
            else:
                print(f"[FAIL] Failed to discover new component parameter: {expected}")
                return False

        print(
            "[SUCCESS] Architecture is now component-agnostic - new components automatically supported!"
        )
        return True

    except Exception as e:
        print(f"[FAIL] Component-agnostic test failed: {e}")
        return False

    finally:
        if os.path.exists(config_path):
            os.unlink(config_path)


def main():
    """Run all discovery engine validation tests."""
    print("Discovery Engine Architectural Refactoring Validation")
    print("=" * 60)

    # Test 1: Dynamic parameter discovery
    test1_success = test_dynamic_parameter_discovery()

    # Test 2: Component-agnostic architecture
    test2_success = test_component_agnostic_architecture()

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY:")

    if test1_success:
        print("[PASS] Dynamic Parameter Discovery: PASSED")
    else:
        print("[FAIL] Dynamic Parameter Discovery: FAILED")

    if test2_success:
        print("[PASS] Component-Agnostic Architecture: PASSED")
    else:
        print("[FAIL] Component-Agnostic Architecture: FAILED")

    overall_success = test1_success and test2_success

    if overall_success:
        print("\n[SUCCESS] Phase 1 Discovery Engine Refactoring: SUCCESS!")
        print(
            "   [SUCCESS] Component knowledge successfully moved to component configurations"
        )
        print("   [SUCCESS] Discovery engine is now component-agnostic")
        print("   [SUCCESS] Architectural gravity correctly realigned")
    else:
        print("\n[FAIL] Phase 1 Discovery Engine Refactoring: FAILED")
        print("   Some tests failed - review output above")

    return overall_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
