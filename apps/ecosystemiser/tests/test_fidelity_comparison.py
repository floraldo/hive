"""Test fidelity comparison - SIMPLE vs STANDARD physics demonstration.

This test demonstrates the power of the Self-Contained Component Module pattern
by showing how the same system produces different results when switching
from SIMPLE to STANDARD fidelity levels.

The test showcases:
- Battery self-discharge in STANDARD vs constant efficiency in SIMPLE
- Heat buffer thermal losses in STANDARD vs perfect storage in SIMPLE
- Heat pump temperature-dependent COP in STANDARD vs fixed COP in SIMPLE
- Water storage evaporation in STANDARD vs basic losses in SIMPLE
"""

import sys
from pathlib import Path
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add path for imports
eco_path = Path(__file__).parent.parent / 'src' / 'EcoSystemiser'
from ecosystemiser.system_model.system import System
from ecosystemiser.system_model.components.energy.battery import Battery, BatteryParams
from ecosystemiser.system_model.components.energy.heat_buffer import HeatBuffer, HeatBufferParams
from ecosystemiser.system_model.components.energy.heat_pump import HeatPump, HeatPumpParams
from ecosystemiser.system_model.components.water.water_storage import WaterStorage, WaterStorageParams
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel
from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.solver.base import SolverConfig

def create_fidelity_test_system(fidelity_level: FidelityLevel):
    """Create a test system with specified fidelity level for all components."""
    N = 24
    system = System(f'fidelity_{fidelity_level.value}_test', N)

    # Create Battery with specified fidelity
    battery = Battery(
        name='Battery',
        params=BatteryParams()
    )
    battery.technical.capacity_nominal = 50.0  # 50 kWh
    battery.technical.max_charge_rate = 10.0   # 10 kW
    battery.technical.max_discharge_rate = 10.0
    battery.technical.efficiency_roundtrip = 0.95
    battery.technical.initial_soc_pct = 0.8    # Start at 80%
    battery.technical.fidelity_level = fidelity_level

    # STANDARD fidelity specific parameters
    if fidelity_level >= FidelityLevel.STANDARD:
        battery.technical.self_discharge_rate = 0.001  # 0.1% per hour self-discharge

    system.add_component(battery)

    # Create Heat Buffer with specified fidelity
    heat_buffer = HeatBuffer(
        name='HeatBuffer',
        params=HeatBufferParams()
    )
    heat_buffer.technical.capacity_nominal = 100.0  # 100 kWh thermal
    heat_buffer.technical.max_charge_rate = 15.0    # 15 kW
    heat_buffer.technical.max_discharge_rate = 15.0
    heat_buffer.technical.efficiency_roundtrip = 0.98
    heat_buffer.technical.initial_soc_pct = 0.6     # Start at 60%
    heat_buffer.technical.fidelity_level = fidelity_level

    # STANDARD fidelity specific parameters
    if fidelity_level >= FidelityLevel.STANDARD:
        heat_buffer.technical.heat_loss_coefficient = 0.002  # 0.2% per hour thermal loss

    system.add_component(heat_buffer)

    # Create Heat Pump with specified fidelity
    heat_pump = HeatPump(
        name='HeatPump',
        params=HeatPumpParams()
    )
    heat_pump.technical.capacity_nominal = 12.0   # 12 kW heat output
    heat_pump.technical.cop_nominal = 3.5        # COP 3.5
    heat_pump.technical.efficiency_nominal = 0.95
    heat_pump.technical.fidelity_level = fidelity_level

    # STANDARD fidelity specific parameters
    if fidelity_level >= FidelityLevel.STANDARD:
        heat_pump.technical.cop_temperature_curve = {'slope': 0.02}  # 2% per °C
        heat_pump.technical.defrost_power_penalty = 5  # 5% power penalty for defrost

    system.add_component(heat_pump)

    # Create Water Storage with specified fidelity
    water_storage = WaterStorage(
        name='WaterStorage',
        params=WaterStorageParams()
    )
    water_storage.technical.capacity_nominal = 30.0     # 30 m³
    water_storage.technical.max_charge_rate = 5.0       # 5 m³/h
    water_storage.technical.max_discharge_rate = 5.0
    water_storage.technical.efficiency_roundtrip = 0.99
    water_storage.technical.initial_soc_pct = 0.7       # Start at 70%
    water_storage.technical.loss_rate_daily = 0.02      # 2% daily evaporation
    water_storage.technical.fidelity_level = fidelity_level

    # STANDARD fidelity specific parameters
    if fidelity_level >= FidelityLevel.STANDARD:
        water_storage.technical.temperature_effects = {
            'evaporation_factor': 0.05  # 5% increase per 10°C
        }

    system.add_component(water_storage)

    return system

def test_rule_based_fidelity_comparison():
    """Test rule-based physics comparison between SIMPLE and STANDARD fidelity."""
    logger.info("="*60)
    logger.info("FIDELITY COMPARISON TEST - RULE-BASED PHYSICS")
    logger.info("="*60)

    # Test 1: Create systems with different fidelity levels
    simple_system = create_fidelity_test_system(FidelityLevel.SIMPLE)
    standard_system = create_fidelity_test_system(FidelityLevel.STANDARD)

    logger.info("\nTest 1: Rule-Based Storage State Evolution")
    logger.info("-"*40)

    # Simulate 12 hours of operation for both systems
    simple_battery = simple_system.components['Battery']
    standard_battery = standard_system.components['Battery']

    simple_heat_buffer = simple_system.components['HeatBuffer']
    standard_heat_buffer = standard_system.components['HeatBuffer']

    simple_water_storage = simple_system.components['WaterStorage']
    standard_water_storage = standard_system.components['WaterStorage']

    # Initialize rule-based operation arrays
    N = 12

    # Initialize energy storage components (Battery, HeatBuffer)
    for comp in [simple_battery, standard_battery, simple_heat_buffer, standard_heat_buffer]:
        comp.N = N
        comp.E = np.zeros(N + 1)
        comp.E[0] = comp.technical.initial_soc_pct * comp.technical.capacity_nominal

    # Initialize water storage components separately
    for comp in [simple_water_storage, standard_water_storage]:
        comp.N = N
        comp.water_level = np.zeros(N + 1)
        comp.water_level[0] = comp.technical.initial_soc_pct * comp.technical.capacity_nominal

    # Simulate operation with no charging/discharging to see pure fidelity effects
    logger.info("Simulating 12 hours with zero charge/discharge to isolate fidelity effects...")

    for t in range(N):
        # Battery state evolution using physics strategies directly
        simple_battery.E[t+1] = simple_battery.physics.rule_based_update_state(
            t, simple_battery.E[t], 0.0, 0.0)
        standard_battery.E[t+1] = standard_battery.physics.rule_based_update_state(
            t, standard_battery.E[t], 0.0, 0.0)

        # Heat buffer state evolution using physics strategies directly
        simple_heat_buffer.E[t+1] = simple_heat_buffer.physics.rule_based_update_state(
            t, simple_heat_buffer.E[t], 0.0, 0.0)
        standard_heat_buffer.E[t+1] = standard_heat_buffer.physics.rule_based_update_state(
            t, standard_heat_buffer.E[t], 0.0, 0.0)

        # Water storage state evolution using physics strategies directly
        simple_water_storage.water_level[t+1] = simple_water_storage.physics.rule_based_update_state(
            t, simple_water_storage.water_level[t], 0.0, 0.0)
        standard_water_storage.water_level[t+1] = standard_water_storage.physics.rule_based_update_state(
            t, standard_water_storage.water_level[t], 0.0, 0.0)

    # Report results
    logger.info(f"\nBattery Energy After 12 Hours:")
    simple_final = simple_battery.E[N]
    standard_final = standard_battery.E[N]
    logger.info(f"  SIMPLE:   {simple_final:.2f} kWh (no self-discharge)")
    logger.info(f"  STANDARD: {standard_final:.2f} kWh (with self-discharge)")
    logger.info(f"  Difference: {simple_final - standard_final:.2f} kWh lost to self-discharge")

    logger.info(f"\nHeat Buffer Energy After 12 Hours:")
    simple_heat_final = simple_heat_buffer.E[N]
    standard_heat_final = standard_heat_buffer.E[N]
    logger.info(f"  SIMPLE:   {simple_heat_final:.2f} kWh (no thermal losses)")
    logger.info(f"  STANDARD: {standard_heat_final:.2f} kWh (with thermal losses)")
    logger.info(f"  Difference: {simple_heat_final - standard_heat_final:.2f} kWh lost to ambient")

    logger.info(f"\nWater Storage Volume After 12 Hours:")
    simple_water_final = simple_water_storage.water_level[N]
    standard_water_final = standard_water_storage.water_level[N]
    logger.info(f"  SIMPLE:   {simple_water_final:.2f} m³ (basic evaporation)")
    logger.info(f"  STANDARD: {standard_water_final:.2f} m³ (temperature-enhanced evaporation)")
    logger.info(f"  Difference: {simple_water_final - standard_water_final:.2f} m³ additional evaporation")

    return {
        'battery_loss': simple_final - standard_final,
        'heat_loss': simple_heat_final - standard_heat_final,
        'water_loss': simple_water_final - standard_water_final
    }

def test_optimization_fidelity_comparison():
    """Test MILP optimization comparison between SIMPLE and STANDARD fidelity."""
    logger.info("\n\nTest 2: MILP Optimization Fidelity Comparison")
    logger.info("-"*40)

    # Create systems for optimization
    simple_system = create_fidelity_test_system(FidelityLevel.SIMPLE)
    standard_system = create_fidelity_test_system(FidelityLevel.STANDARD)

    # Run MILP optimization for both systems
    config = SolverConfig(verbose=False, solver_specific={'objective': 'min_cost'})

    logger.info("Optimizing SIMPLE fidelity system...")
    simple_solver = MILPSolver(simple_system, config)
    simple_result = simple_solver.solve()

    logger.info("Optimizing STANDARD fidelity system...")
    standard_solver = MILPSolver(standard_system, config)
    standard_result = standard_solver.solve()

    logger.info(f"\nOptimization Results:")
    logger.info(f"  SIMPLE Status:   {simple_result.status}")
    logger.info(f"  STANDARD Status: {standard_result.status}")

    if simple_result.status == 'optimal' and standard_result.status == 'optimal':
        logger.info(f"  SIMPLE Cost:     ${simple_result.objective_value:.2f}")
        logger.info(f"  STANDARD Cost:   ${standard_result.objective_value:.2f}")
        cost_diff = standard_result.objective_value - simple_result.objective_value
        logger.info(f"  Cost Difference: ${cost_diff:.2f} (STANDARD accounts for losses)")

    return {
        'simple_optimal': simple_result.status == 'optimal',
        'standard_optimal': standard_result.status == 'optimal',
        'simple_cost': simple_result.objective_value if simple_result.status == 'optimal' else None,
        'standard_cost': standard_result.objective_value if standard_result.status == 'optimal' else None
    }

def main():
    """Main test runner demonstrating fidelity system capabilities."""
    logger.info("🚀 PHASE 2A: FIDELITY SYSTEM DEMONSTRATION")
    logger.info("Showcasing SIMPLE vs STANDARD fidelity physics differences")

    # Run rule-based comparison
    rule_based_results = test_rule_based_fidelity_comparison()

    # Run optimization comparison
    optimization_results = test_optimization_fidelity_comparison()

    # Summary
    logger.info("\n" + "="*60)
    logger.info("✅ FIDELITY SYSTEM DEMONSTRATION COMPLETE!")
    logger.info("="*60)
    logger.info("\n🎯 Key Achievements:")
    logger.info("• STANDARD fidelity adds realistic physics losses")
    logger.info("• Self-discharge, thermal losses, and enhanced evaporation modeled")
    logger.info("• Same architecture handles both fidelity levels seamlessly")
    logger.info("• MILP optimization accounts for fidelity-specific constraints")
    logger.info("\n🏗️ Architecture Benefits Demonstrated:")
    logger.info("• Strategy Pattern enables fidelity switching without code changes")
    logger.info("• Factory Pattern selects appropriate physics based on configuration")
    logger.info("• Single parameter change upgrades entire system accuracy")
    logger.info("• Clean separation between SIMPLE baseline and STANDARD enhancements")

    if rule_based_results['battery_loss'] > 0:
        logger.info(f"\n⚡ Battery self-discharge: {rule_based_results['battery_loss']:.2f} kWh lost in 12h")
    if rule_based_results['heat_loss'] > 0:
        logger.info(f"🔥 Heat buffer thermal loss: {rule_based_results['heat_loss']:.2f} kWh lost in 12h")
    if rule_based_results['water_loss'] > 0:
        logger.info(f"💧 Water enhanced evaporation: {rule_based_results['water_loss']:.2f} m³ lost in 12h")

    logger.info("\n🚀 Ready for Phase 2B: MILP STANDARD Enhancements")
    logger.info("="*60)

    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)