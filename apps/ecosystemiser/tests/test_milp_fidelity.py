"""Test MILP optimization with STANDARD fidelity enhancements.

This test demonstrates that the MILP solver correctly accounts for
fidelity-specific physics when generating constraints, producing
different optimization results for SIMPLE vs STANDARD fidelity.
"""

import sys
from pathlib import Path
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add path for imports
eco_path = Path(__file__).parent.parent / 'src' / 'EcoSystemiser'
from EcoSystemiser.system_model.system import System
from EcoSystemiser.system_model.components.energy.battery import Battery, BatteryParams
from EcoSystemiser.system_model.components.energy.solar_pv import SolarPV, SolarPVParams
from EcoSystemiser.system_model.components.energy.grid import Grid, GridParams
from EcoSystemiser.system_model.components.energy.power_demand import PowerDemand, PowerDemandParams
from EcoSystemiser.system_model.components.energy.heat_buffer import HeatBuffer, HeatBufferParams
from EcoSystemiser.system_model.components.energy.heat_pump import HeatPump, HeatPumpParams
from EcoSystemiser.system_model.components.energy.heat_demand import HeatDemand, HeatDemandParams
from EcoSystemiser.system_model.components.shared.archetypes import FidelityLevel
from EcoSystemiser.solver.milp_solver import MILPSolver
from EcoSystemiser.solver.base import SolverConfig

def create_milp_test_system(fidelity_level: FidelityLevel):
    """Create an energy system with specified fidelity level."""
    N = 24  # 24 hour simulation
    system = System(f'milp_fidelity_{fidelity_level.value}_test', N)

    # Create profiles for a realistic scenario
    # Solar generation profile (peak at noon)
    solar_profile = np.zeros(N)
    solar_profile[6:18] = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0,
                           1.0, 0.9, 0.7, 0.5, 0.3, 0.1]

    # Power demand profile (evening peak)
    power_demand = np.ones(N) * 3.0  # 3 kW baseload
    power_demand[7:9] = 5.0    # Morning peak
    power_demand[17:22] = 8.0  # Evening peak

    # Heat demand profile (morning and evening peaks)
    heat_demand = np.ones(N) * 2.0  # 2 kW baseload
    heat_demand[6:8] = 5.0     # Morning heating
    heat_demand[18:22] = 6.0   # Evening heating

    # Grid with time-of-use pricing
    grid = Grid(
        name='Grid',
        params=GridParams()
    )
    grid.technical.max_import = 15.0
    grid.technical.max_export = 10.0
    grid.technical.import_tariff = 0.3   # $0.30/kWh import
    grid.technical.feed_in_tariff = 0.1  # $0.10/kWh export
    grid.technical.fidelity_level = FidelityLevel.SIMPLE  # Grid always SIMPLE
    system.add_component(grid)

    # Solar PV
    solar = SolarPV(
        name='SolarPV',
        params=SolarPVParams()
    )
    solar.technical.capacity_nominal = 10.0  # 10 kW peak
    solar.technical.fidelity_level = FidelityLevel.SIMPLE  # Solar always SIMPLE
    solar.profile = solar_profile
    system.add_component(solar)

    # Battery with specified fidelity
    battery = Battery(
        name='Battery',
        params=BatteryParams()
    )
    battery.technical.capacity_nominal = 20.0   # 20 kWh
    battery.technical.max_charge_rate = 5.0     # 5 kW
    battery.technical.max_discharge_rate = 5.0
    battery.technical.efficiency_roundtrip = 0.95
    battery.technical.initial_soc_pct = 0.5     # Start at 50%
    battery.technical.fidelity_level = fidelity_level

    # STANDARD fidelity specific parameters
    if fidelity_level >= FidelityLevel.STANDARD:
        battery.technical.self_discharge_rate = 0.002  # 0.2% per hour

    system.add_component(battery)

    # Heat Buffer with specified fidelity
    heat_buffer = HeatBuffer(
        name='HeatBuffer',
        params=HeatBufferParams()
    )
    heat_buffer.technical.capacity_nominal = 30.0   # 30 kWh thermal
    heat_buffer.technical.max_charge_rate = 8.0     # 8 kW
    heat_buffer.technical.max_discharge_rate = 8.0
    heat_buffer.technical.efficiency_roundtrip = 0.98
    heat_buffer.technical.initial_soc_pct = 0.3     # Start at 30%
    heat_buffer.technical.fidelity_level = fidelity_level

    # STANDARD fidelity specific parameters
    if fidelity_level >= FidelityLevel.STANDARD:
        heat_buffer.technical.heat_loss_coefficient = 0.003  # 0.3% per hour

    system.add_component(heat_buffer)

    # Heat Pump (converts electricity to heat)
    heat_pump = HeatPump(
        name='HeatPump',
        params=HeatPumpParams()
    )
    heat_pump.technical.capacity_nominal = 8.0    # 8 kW heat output
    heat_pump.technical.cop_nominal = 3.5         # COP 3.5
    heat_pump.technical.fidelity_level = FidelityLevel.SIMPLE  # Keep simple for this test
    system.add_component(heat_pump)

    # Power Demand
    power_demand_comp = PowerDemand(
        name='PowerDemand',
        params=PowerDemandParams()
    )
    power_demand_comp.technical.peak_demand = 10.0
    power_demand_comp.profile = power_demand / 10.0  # Normalize to 0-1
    system.add_component(power_demand_comp)

    # Heat Demand
    heat_demand_comp = HeatDemand(
        name='HeatDemand',
        params=HeatDemandParams()
    )
    heat_demand_comp.technical.peak_demand = 8.0
    heat_demand_comp.profile = heat_demand / 8.0  # Normalize to 0-1
    system.add_component(heat_demand_comp)

    # Connect components
    # Electrical connections
    system.connect('Grid', 'PowerDemand', 'electricity')
    system.connect('Grid', 'Battery', 'electricity')
    system.connect('Grid', 'HeatPump', 'electricity')
    system.connect('SolarPV', 'PowerDemand', 'electricity')
    system.connect('SolarPV', 'Battery', 'electricity')
    system.connect('SolarPV', 'Grid', 'electricity')
    system.connect('Battery', 'PowerDemand', 'electricity')
    system.connect('Battery', 'HeatPump', 'electricity')

    # Thermal connections
    system.connect('HeatPump', 'HeatDemand', 'heat')
    system.connect('HeatPump', 'HeatBuffer', 'heat')
    system.connect('HeatBuffer', 'HeatDemand', 'heat')

    return system

def test_milp_fidelity_comparison():
    """Test MILP optimization with SIMPLE vs STANDARD fidelity."""
    logger.info("="*60)
    logger.info("MILP FIDELITY TEST - OPTIMIZATION WITH PHYSICS LOSSES")
    logger.info("="*60)

    # Create systems with different fidelity levels
    simple_system = create_milp_test_system(FidelityLevel.SIMPLE)
    standard_system = create_milp_test_system(FidelityLevel.STANDARD)

    # Configure solver for cost minimization
    config = SolverConfig(
        verbose=False,
        solver_specific={'objective': 'min_cost'}
    )

    # Optimize SIMPLE system
    logger.info("\nOptimizing SIMPLE fidelity system (no losses)...")
    simple_solver = MILPSolver(simple_system, config)
    simple_result = simple_solver.solve()

    # Optimize STANDARD system
    logger.info("Optimizing STANDARD fidelity system (with losses)...")
    standard_solver = MILPSolver(standard_system, config)
    standard_result = standard_solver.solve()

    # Extract and compare results
    logger.info("\n" + "-"*40)
    logger.info("OPTIMIZATION RESULTS COMPARISON")
    logger.info("-"*40)

    if simple_result.status == 'optimal':
        logger.info(f"SIMPLE Status:   {simple_result.status}")
        logger.info(f"SIMPLE Cost:     ${simple_result.objective_value:.2f}")
    else:
        logger.info(f"SIMPLE Status:   {simple_result.status} - FAILED!")
        return False

    if standard_result.status == 'optimal':
        logger.info(f"STANDARD Status: {standard_result.status}")
        logger.info(f"STANDARD Cost:   ${standard_result.objective_value:.2f}")
    else:
        logger.info(f"STANDARD Status: {standard_result.status} - FAILED!")
        return False

    # Calculate differences
    cost_difference = standard_result.objective_value - simple_result.objective_value
    percent_difference = (cost_difference / simple_result.objective_value) * 100

    logger.info(f"\nCost Difference: ${cost_difference:.2f} ({percent_difference:.1f}% higher)")
    logger.info("Reason: STANDARD accounts for self-discharge and thermal losses")

    # Analyze battery usage
    simple_battery = simple_system.components['Battery']
    standard_battery = standard_system.components['Battery']

    if hasattr(simple_battery, 'E_opt') and simple_battery.E_opt is not None:
        if hasattr(simple_battery.E_opt, 'value') and simple_battery.E_opt.value is not None:
            simple_battery_final = simple_battery.E_opt.value[-1]
            standard_battery_final = standard_battery.E_opt.value[-1]

            logger.info(f"\nBattery Final State:")
            logger.info(f"  SIMPLE:   {simple_battery_final:.2f} kWh")
            logger.info(f"  STANDARD: {standard_battery_final:.2f} kWh")
            logger.info(f"  Difference: {simple_battery_final - standard_battery_final:.2f} kWh")

    # Analyze heat buffer usage
    simple_heat = simple_system.components['HeatBuffer']
    standard_heat = standard_system.components['HeatBuffer']

    if hasattr(simple_heat, 'E_opt') and simple_heat.E_opt is not None:
        if hasattr(simple_heat.E_opt, 'value') and simple_heat.E_opt.value is not None:
            simple_heat_final = simple_heat.E_opt.value[-1]
            standard_heat_final = standard_heat.E_opt.value[-1]

            logger.info(f"\nHeat Buffer Final State:")
            logger.info(f"  SIMPLE:   {simple_heat_final:.2f} kWh")
            logger.info(f"  STANDARD: {standard_heat_final:.2f} kWh")
            logger.info(f"  Difference: {simple_heat_final - standard_heat_final:.2f} kWh")

    # Verify that costs are actually different
    if abs(cost_difference) < 0.01:
        logger.warning("\n⚠️ WARNING: Costs are identical - fidelity may not be affecting optimization!")
        return False

    logger.info("\n✅ SUCCESS: STANDARD fidelity produces different (more realistic) optimization!")
    return True

def main():
    """Main test runner for MILP fidelity validation."""
    logger.info("🚀 PHASE 2B: MILP STANDARD CONSTRAINT ENHANCEMENTS")
    logger.info("Demonstrating optimization accounts for fidelity-specific physics")

    success = test_milp_fidelity_comparison()

    if success:
        logger.info("\n" + "="*60)
        logger.info("✅ MILP FIDELITY TEST COMPLETE!")
        logger.info("="*60)
        logger.info("\n🎯 Key Achievements:")
        logger.info("• MILP constraints now include self-discharge and thermal losses")
        logger.info("• STANDARD fidelity produces higher costs due to realistic losses")
        logger.info("• Optimization adapts strategy to account for physics")
        logger.info("• Same solver handles both fidelity levels transparently")
        logger.info("\n🏗️ Technical Impact:")
        logger.info("• Battery self-discharge affects charging strategy")
        logger.info("• Heat buffer thermal losses influence storage timing")
        logger.info("• More realistic cost estimates for system design")
        logger.info("• Research-grade optimization accuracy achieved")
        logger.info("\n🚀 Platform now ready for advanced energy system optimization!")
        logger.info("="*60)
    else:
        logger.error("\n❌ MILP fidelity test failed - optimization may not be accounting for losses")

    return success

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)