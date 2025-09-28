#!/usr/bin/env python3
"""
Final comprehensive test for complete Strategy Pattern implementation.
Validates that ALL components have separate Simple and Standard optimization strategies.
"""

import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add path for imports
eco_path = Path(__file__).parent.parent / 'src' / 'EcoSystemiser'
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel

def test_complete_strategy_pattern():
    """Test that all components have complete Strategy Pattern implementation."""

    # List of all components to check
    components_to_check = [
        ('energy.battery', 'Battery'),
        ('energy.heat_buffer', 'HeatBuffer'),
        ('energy.solar_pv', 'SolarPV'),
        ('energy.heat_pump', 'HeatPump'),
        ('energy.power_demand', 'PowerDemand'),
        ('energy.electric_boiler', 'ElectricBoiler'),
        ('energy.heat_demand', 'HeatDemand'),
        ('energy.grid', 'Grid'),
        ('water.water_grid', 'WaterGrid'),
        ('water.water_demand', 'WaterDemand'),
        ('water.water_storage', 'WaterStorage'),
        ('water.rainwater_source', 'RainwaterSource')
    ]

    logger.info("=" * 70)
    logger.info("COMPLETE STRATEGY PATTERN VALIDATION")
    logger.info("=" * 70)
    logger.info("\nChecking all 12 components for complete implementation...")

    complete = []
    incomplete = []
    errors = []

    for module_path, component_name in components_to_check:
        try:
            module = __import__(f'system_model.components.{module_path}', fromlist=[component_name])

            # Check for physics strategies
            has_simple_physics = hasattr(module, f'{component_name}PhysicsSimple')
            has_standard_physics = hasattr(module, f'{component_name}PhysicsStandard')

            # Check for optimization strategies
            has_simple_opt = hasattr(module, f'{component_name}OptimizationSimple')
            has_standard_opt = hasattr(module, f'{component_name}OptimizationStandard')

            # Check inheritance
            inheritance_ok = True
            if has_standard_physics and has_simple_physics:
                StandardPhysics = getattr(module, f'{component_name}PhysicsStandard')
                SimplePhysics = getattr(module, f'{component_name}PhysicsSimple')
                if not issubclass(StandardPhysics, SimplePhysics):
                    inheritance_ok = False

            if has_standard_opt and has_simple_opt:
                StandardOpt = getattr(module, f'{component_name}OptimizationStandard')
                SimpleOpt = getattr(module, f'{component_name}OptimizationSimple')
                if not issubclass(StandardOpt, SimpleOpt):
                    inheritance_ok = False

            # Determine status
            physics_complete = has_simple_physics and has_standard_physics
            opt_complete = has_simple_opt and has_standard_opt

            if physics_complete and opt_complete and inheritance_ok:
                complete.append(component_name)
                logger.info(f"[COMPLETE] {component_name}: All 4 strategies with proper inheritance")
            else:
                incomplete.append(component_name)
                issues = []
                if not physics_complete:
                    issues.append("missing physics strategies")
                if not opt_complete:
                    issues.append("missing optimization strategies")
                if not inheritance_ok:
                    issues.append("incorrect inheritance")
                logger.warning(f"[INCOMPLETE] {component_name}: {', '.join(issues)}")

        except Exception as e:
            errors.append((component_name, str(e)))
            logger.error(f"[ERROR] {component_name}: {e}")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)

    logger.info(f"\nComplete: {len(complete)}/{len(components_to_check)} components")
    if complete:
        for comp in complete:
            logger.info(f"  - {comp}")

    if incomplete:
        logger.warning(f"\nIncomplete: {len(incomplete)} components")
        for comp in incomplete:
            logger.warning(f"  - {comp}")

    if errors:
        logger.error(f"\nErrors: {len(errors)} components")
        for comp, err in errors:
            logger.error(f"  - {comp}: {err}")

    # Final verdict
    logger.info("\n" + "=" * 70)
    if len(complete) == len(components_to_check):
        logger.info("SUCCESS: All components have complete Strategy Pattern!")
        logger.info("Architecture: 100% COMPLIANT")
    else:
        completion_pct = (len(complete) / len(components_to_check)) * 100
        logger.warning(f"PARTIAL: {completion_pct:.1f}% complete")
        logger.warning(f"Remaining work: {len(incomplete)} components need updates")

    logger.info("=" * 70)

    return len(complete) == len(components_to_check)

def test_factory_methods():
    """Test that factory methods correctly select strategies based on fidelity."""

    logger.info("\n" + "=" * 70)
    logger.info("FACTORY METHOD VALIDATION")
    logger.info("=" * 70)

    # Test a few components
    test_components = [
        ('energy.battery', 'Battery', 'BatteryParams'),
        ('energy.heat_buffer', 'HeatBuffer', 'HeatBufferParams'),
        ('energy.solar_pv', 'SolarPV', 'SolarPVParams'),
    ]

    all_good = True

    for module_path, component_name, params_name in test_components:
        try:
            module = __import__(f'system_model.components.{module_path}', fromlist=[component_name, params_name])
            Component = getattr(module, component_name)
            Params = getattr(module, params_name)

            # Test SIMPLE fidelity
            params_simple = Params()
            params_simple.technical.fidelity_level = FidelityLevel.SIMPLE
            comp_simple = Component(name='test_simple', params=params_simple)

            physics_simple = comp_simple._get_physics_strategy()
            opt_simple = comp_simple._get_optimization_strategy()

            assert physics_simple.__class__.__name__ == f'{component_name}PhysicsSimple'
            assert opt_simple.__class__.__name__ == f'{component_name}OptimizationSimple'

            # Test STANDARD fidelity
            params_standard = Params()
            params_standard.technical.fidelity_level = FidelityLevel.STANDARD
            comp_standard = Component(name='test_standard', params=params_standard)

            physics_standard = comp_standard._get_physics_strategy()
            opt_standard = comp_standard._get_optimization_strategy()

            assert physics_standard.__class__.__name__ == f'{component_name}PhysicsStandard'
            assert opt_standard.__class__.__name__ == f'{component_name}OptimizationStandard'

            logger.info(f"[PASSED] {component_name}: Factory methods correctly select strategies")

        except AssertionError as e:
            all_good = False
            logger.error(f"[FAILED] {component_name}: Factory method assertion failed")
        except Exception as e:
            all_good = False
            logger.error(f"[ERROR] {component_name}: {e}")

    if all_good:
        logger.info("\nFactory methods: ALL TESTS PASSED")
    else:
        logger.warning("\nFactory methods: SOME TESTS FAILED")

    return all_good

if __name__ == "__main__":
    # Run tests
    pattern_complete = test_complete_strategy_pattern()
    factory_ok = test_factory_methods()

    # Exit code
    if pattern_complete and factory_ok:
        logger.info("\n" + "=" * 70)
        logger.info("FINAL RESULT: ALL TESTS PASSED!")
        logger.info("The Strategy Pattern implementation is COMPLETE.")
        logger.info("=" * 70)
        sys.exit(0)
    else:
        logger.warning("\n" + "=" * 70)
        logger.warning("FINAL RESULT: IMPLEMENTATION INCOMPLETE")
        logger.warning("Please complete the remaining components.")
        logger.warning("=" * 70)
        sys.exit(1)