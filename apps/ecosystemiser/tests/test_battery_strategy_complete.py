"""Test that Battery has complete Strategy Pattern implementation.

This validates that Battery correctly implements separate strategy classes
for both physics AND optimization at each fidelity level.
"""

import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add path for imports
eco_path = Path(__file__).parent.parent / 'src' / 'EcoSystemiser'
from system_model.components.shared.archetypes import FidelityLevel
from system_model.components.energy.battery import (
    Battery, BatteryParams,
    BatteryPhysicsSimple, BatteryPhysicsStandard,
    BatteryOptimizationSimple, BatteryOptimizationStandard
)

def test_battery_complete_strategy():
    """Test that Battery has complete strategy pattern implementation."""
    logger.info("="*70)
    logger.info("BATTERY COMPLETE STRATEGY PATTERN TEST")
    logger.info("="*70)

    # Test 1: All strategy classes exist
    logger.info("\n1. Checking strategy classes exist...")
    assert BatteryPhysicsSimple is not None, "BatteryPhysicsSimple missing"
    assert BatteryPhysicsStandard is not None, "BatteryPhysicsStandard missing"
    assert BatteryOptimizationSimple is not None, "BatteryOptimizationSimple missing"
    assert BatteryOptimizationStandard is not None, "BatteryOptimizationStandard missing"
    logger.info("   ✅ All 4 strategy classes exist")

    # Test 2: Inheritance chains are correct
    logger.info("\n2. Checking inheritance chains...")
    assert issubclass(BatteryPhysicsStandard, BatteryPhysicsSimple), \
        "BatteryPhysicsStandard should inherit from BatteryPhysicsSimple"
    assert issubclass(BatteryOptimizationStandard, BatteryOptimizationSimple), \
        "BatteryOptimizationStandard should inherit from BatteryOptimizationSimple"
    logger.info("   ✅ Both inheritance chains correct")

    # Test 3: Factory methods select correct strategies
    logger.info("\n3. Testing factory methods...")

    # Create SIMPLE battery
    battery_simple = Battery(name='SimpleBattery', params=BatteryParams())
    battery_simple.technical.fidelity_level = FidelityLevel.SIMPLE
    physics_simple = battery_simple._get_physics_strategy()
    optimization_simple = battery_simple._get_optimization_strategy()

    assert isinstance(physics_simple, BatteryPhysicsSimple), \
        "SIMPLE battery should get BatteryPhysicsSimple"
    assert not isinstance(physics_simple, BatteryPhysicsStandard), \
        "SIMPLE battery should NOT get BatteryPhysicsStandard"
    assert isinstance(optimization_simple, BatteryOptimizationSimple), \
        "SIMPLE battery should get BatteryOptimizationSimple"
    assert not isinstance(optimization_simple, BatteryOptimizationStandard), \
        "SIMPLE battery should NOT get BatteryOptimizationStandard"
    logger.info("   ✅ SIMPLE fidelity selects correct strategies")

    # Create STANDARD battery
    battery_standard = Battery(name='StandardBattery', params=BatteryParams())
    battery_standard.technical.fidelity_level = FidelityLevel.STANDARD
    physics_standard = battery_standard._get_physics_strategy()
    optimization_standard = battery_standard._get_optimization_strategy()

    assert isinstance(physics_standard, BatteryPhysicsStandard), \
        "STANDARD battery should get BatteryPhysicsStandard"
    assert isinstance(physics_standard, BatteryPhysicsSimple), \
        "BatteryPhysicsStandard should also be instance of BatteryPhysicsSimple (inheritance)"
    assert isinstance(optimization_standard, BatteryOptimizationStandard), \
        "STANDARD battery should get BatteryOptimizationStandard"
    assert isinstance(optimization_standard, BatteryOptimizationSimple), \
        "BatteryOptimizationStandard should also be instance of BatteryOptimizationSimple (inheritance)"
    logger.info("   ✅ STANDARD fidelity selects correct strategies")

    # Test 4: Strategies have required methods
    logger.info("\n4. Checking required methods...")
    assert hasattr(physics_simple, 'rule_based_update_state'), \
        "Physics strategy must have rule_based_update_state"
    assert hasattr(optimization_simple, 'set_constraints'), \
        "Optimization strategy must have set_constraints"
    logger.info("   ✅ All required methods present")

    # Test 5: Different behaviors for different fidelities
    logger.info("\n5. Testing different behaviors...")

    # Test physics difference
    initial_energy = 10.0
    charge = 0.0
    discharge = 0.0

    # SIMPLE physics (no self-discharge)
    battery_simple.technical.self_discharge_rate = 0.01
    physics_simple = battery_simple._get_physics_strategy()
    energy_simple = physics_simple.rule_based_update_state(0, initial_energy, charge, discharge)

    # STANDARD physics (with self-discharge)
    battery_standard.technical.self_discharge_rate = 0.01
    physics_standard = battery_standard._get_physics_strategy()
    energy_standard = physics_standard.rule_based_update_state(0, initial_energy, charge, discharge)

    assert energy_simple == initial_energy, \
        "SIMPLE physics should have no self-discharge"
    assert energy_standard < initial_energy, \
        "STANDARD physics should have self-discharge losses"
    assert abs(initial_energy - energy_standard - 0.1) < 0.001, \
        "STANDARD should lose 0.1 kWh (1% of 10 kWh)"
    logger.info(f"   ✅ SIMPLE: {energy_simple:.2f} kWh (no loss)")
    logger.info(f"   ✅ STANDARD: {energy_standard:.2f} kWh (with self-discharge)")

    logger.info("\n" + "="*70)
    logger.info("✅ BATTERY COMPLETE STRATEGY PATTERN TEST PASSED!")
    logger.info("="*70)
    logger.info("\n🎯 Battery Implementation Summary:")
    logger.info("• 2 Physics strategies: Simple & Standard")
    logger.info("• 2 Optimization strategies: Simple & Standard")
    logger.info("• Correct inheritance: Standard inherits from Simple")
    logger.info("• Factory methods select based on fidelity level")
    logger.info("• Different behaviors for different fidelities")
    logger.info("\n🏆 This is the GOLD STANDARD for all components!")
    logger.info("="*70)

    return True

if __name__ == "__main__":
    success = test_battery_complete_strategy()
    sys.exit(0 if success else 1)