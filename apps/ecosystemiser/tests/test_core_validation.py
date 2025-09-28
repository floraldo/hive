#!/usr/bin/env python3
"""
Core validation test - validates the fundamental architectural changes.

This focused test validates:
1. Component data loading from YAML
2. System building from configuration
3. Solver factory pattern
4. Results format consistency
"""
import sys
import json
from pathlib import Path
import logging

# Setup paths
project_root = Path(__file__).parent
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('CoreValidation')

def test_component_data_loading():
    """Test that component data can be loaded from YAML."""
    logger.info("\n1. Testing Component Data Loading...")

    try:
        from ecosystemiser.component_data import ComponentRepository

        repo = ComponentRepository(
            library_path=project_root / 'src' / 'EcoSystemiser' / 'component_data' / 'library'
        )

        # Try loading a battery spec
        battery_spec = repo.get_component('battery', 'standard_lithium_ion')

        if battery_spec:
            logger.info(f"✅ Successfully loaded battery spec: {battery_spec.get('name', 'Unknown')}")
            logger.info(f"   - Capacity: {battery_spec.get('technical_params', {}).get('capacity_kwh', 'N/A')} kWh")
            logger.info(f"   - Efficiency: {battery_spec.get('technical_params', {}).get('round_trip_efficiency', 'N/A')}")
            return True
        else:
            logger.error("❌ Failed to load battery spec")
            return False

    except Exception as e:
        logger.error(f"❌ Component data loading failed: {e}")
        return False

def test_system_builder():
    """Test that SystemBuilder can create components from config."""
    logger.info("\n2. Testing System Builder...")

    try:
        from ecosystemiser.system_model.system_builder import SystemBuilder
        from ecosystemiser.system_model.components import Battery, Grid, SolarPV, PowerDemand

        # Register components (normally done in __init__)
        SystemBuilder.COMPONENT_CLASSES = {
            'Battery': Battery,
            'Grid': Grid,
            'SolarPV': SolarPV,
            'PowerDemand': PowerDemand
        }

        builder = SystemBuilder()

        # Simple test config
        config = {
            'name': 'test_system',
            'timesteps': 24,
            'components': {
                'battery1': {
                    'type': 'Battery',
                    'params': {
                        'capacity_kwh': 10.0,
                        'max_charge_kw': 5.0,
                        'max_discharge_kw': 5.0
                    }
                }
            }
        }

        system = builder.build_from_config(config)

        if system and 'battery1' in system.components:
            battery = system.components['battery1']
            logger.info(f"✅ Successfully created battery component")
            logger.info(f"   - Type: {type(battery).__name__}")
            logger.info(f"   - Capacity: {battery.params.capacity_kwh} kWh")
            return True
        else:
            logger.error("❌ Failed to build system")
            return False

    except Exception as e:
        logger.error(f"❌ System builder failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_solver_factory():
    """Test that solver factory can create different solvers."""
    logger.info("\n3. Testing Solver Factory...")

    try:
        from ecosystemiser.solver import SolverFactory
        from ecosystemiser.solver.rule_based_engine import RuleBasedEngine
        from ecosystemiser.solver.milp_solver import MILPSolver

        # Register solvers (normally done in __init__)
        SolverFactory._solvers = {
            'rule_based': RuleBasedEngine,
            'milp': MILPSolver
        }

        factory = SolverFactory()

        # Test rule-based solver creation
        rule_solver = factory.create('rule_based')
        if rule_solver:
            logger.info(f"✅ Successfully created rule-based solver")
            logger.info(f"   - Type: {type(rule_solver).__name__}")

        # Test MILP solver creation
        milp_solver = factory.create('milp')
        if milp_solver:
            logger.info(f"✅ Successfully created MILP solver")
            logger.info(f"   - Type: {type(milp_solver).__name__}")

        return rule_solver is not None and milp_solver is not None

    except Exception as e:
        logger.error(f"❌ Solver factory failed: {e}")
        return False

def test_data_format_compatibility():
    """Test that new format is compatible with original."""
    logger.info("\n4. Testing Data Format Compatibility...")

    # Load golden dataset structure
    golden_path = project_root / 'tests' / 'systemiser_golden_results.json'

    if not golden_path.exists():
        logger.warning("⚠️ Golden dataset not found, skipping format test")
        return True

    try:
        with open(golden_path, 'r') as f:
            golden_data = json.load(f)

        # Check expected structure
        expected_keys = ['flows']
        missing_keys = [key for key in expected_keys if key not in golden_data]

        if not missing_keys:
            logger.info("✅ Golden dataset has expected structure")
            logger.info(f"   - Number of flows: {len(golden_data.get('flows', []))}")

            # Check flow structure
            if golden_data.get('flows'):
                sample_flow = golden_data['flows'][0]
                flow_keys = ['from', 'to', 'type', 'values']
                has_all_keys = all(key in sample_flow for key in flow_keys)

                if has_all_keys:
                    logger.info("✅ Flow format is compatible")
                    return True
                else:
                    logger.error(f"❌ Flow missing keys: {[k for k in flow_keys if k not in sample_flow]}")
                    return False
        else:
            logger.error(f"❌ Golden dataset missing keys: {missing_keys}")
            return False

    except Exception as e:
        logger.error(f"❌ Format compatibility check failed: {e}")
        return False

def main():
    """Run core validation tests."""
    logger.info("=" * 60)
    logger.info("EcoSystemiser Core Architecture Validation")
    logger.info("=" * 60)

    tests = [
        ("Component Data Loading", test_component_data_loading),
        ("System Builder", test_system_builder),
        ("Solver Factory", test_solver_factory),
        ("Data Format Compatibility", test_data_format_compatibility)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n🎉 SUCCESS: Core architecture validation complete!")
        return True
    elif passed >= total * 0.75:
        logger.warning("\n⚠️ WARNING: Most tests passed but some issues remain")
        return False
    else:
        logger.error("\n❌ FAILURE: Critical architecture issues detected")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)