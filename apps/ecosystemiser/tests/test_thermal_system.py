"""Test expanded system with thermal components."""

import sys
from pathlib import Path
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add path for imports
eco_path = Path(__file__).parent.parent / 'src' / 'EcoSystemiser'
sys.path.insert(0, str(eco_path))

from system_model.system import System
from component_model.battery import Battery, BatteryParams
from component_model.grid import Grid, GridParams
from component_model.solar_pv import SolarPV, SolarPVParams
from component_model.power_demand import PowerDemand, PowerDemandParams
from component_model.heat_pump import HeatPump, HeatPumpParams
from component_model.electric_boiler import ElectricBoiler, ElectricBoilerParams
from component_model.heat_buffer import HeatBuffer, HeatBufferParams
from component_model.heat_demand import HeatDemand, HeatDemandParams
from solver.milp_solver_v2 import MILPSolver
from solver.base import SolverConfig


def create_thermal_system():
    """Create system with both electrical and thermal components."""
    N = 24
    system = System('thermal_test', N)

    # Create profiles
    # Solar profile (peak at midday)
    solar_profile = np.zeros(N)
    for t in range(N):
        if 6 <= t <= 18:  # Daylight hours
            solar_profile[t] = np.sin((t - 6) * np.pi / 12) * 8.0

    # Electrical demand profile
    power_demand = np.ones(N) * 1.5  # 1.5 kW baseload
    power_demand[7:9] = 3.0   # Morning peak
    power_demand[18:21] = 4.0  # Evening peak

    # Heat demand profile (higher in morning and evening)
    heat_demand = np.ones(N) * 2.0  # 2 kW baseload
    heat_demand[6:9] = 5.0    # Morning heating
    heat_demand[18:22] = 4.5  # Evening heating
    heat_demand[0:6] = 1.0    # Night setback
    heat_demand[22:24] = 1.0  # Night setback

    # ---- Electrical Components ----
    grid = Grid(
        name='Grid',
        params=GridParams(P_max=100, import_tariff=0.25, feed_in_tariff=0.08)
    )
    system.add_component(grid)

    battery = Battery(
        name='Battery',
        params=BatteryParams(P_max=5, E_max=10, E_init=5, eta_charge=0.95, eta_discharge=0.95)
    )
    system.add_component(battery)

    solar = SolarPV(
        name='SolarPV',
        params=SolarPVParams(P_profile=solar_profile.tolist(), P_max=12)
    )
    system.add_component(solar)

    power_load = PowerDemand(
        name='PowerDemand',
        params=PowerDemandParams(P_profile=power_demand.tolist(), P_max=6)
    )
    system.add_component(power_load)

    # ---- Thermal Components ----
    heat_pump = HeatPump(
        name='HeatPump',
        params=HeatPumpParams(COP=3.5, eta=0.90, P_max=3)
    )
    system.add_component(heat_pump)

    electric_boiler = ElectricBoiler(
        name='ElectricBoiler',
        params=ElectricBoilerParams(eta=0.95, P_max=5)
    )
    system.add_component(electric_boiler)

    heat_buffer = HeatBuffer(
        name='HeatBuffer',
        params=HeatBufferParams(P_max=4, E_max=20, E_init=10, eta=0.90)
    )
    system.add_component(heat_buffer)

    heat_load = HeatDemand(
        name='HeatDemand',
        params=HeatDemandParams(H_profile=heat_demand.tolist(), H_max=6)
    )
    system.add_component(heat_load)

    # ---- Electrical Connections ----
    system.connect('Grid', 'PowerDemand', 'electricity')
    system.connect('Grid', 'Battery', 'electricity')
    system.connect('Grid', 'HeatPump', 'electricity')
    system.connect('Grid', 'ElectricBoiler', 'electricity')
    system.connect('SolarPV', 'PowerDemand', 'electricity')
    system.connect('SolarPV', 'Battery', 'electricity')
    system.connect('SolarPV', 'HeatPump', 'electricity')
    system.connect('SolarPV', 'ElectricBoiler', 'electricity')
    system.connect('SolarPV', 'Grid', 'electricity')
    system.connect('Battery', 'PowerDemand', 'electricity')
    system.connect('Battery', 'HeatPump', 'electricity')
    system.connect('Battery', 'ElectricBoiler', 'electricity')
    system.connect('Battery', 'Grid', 'electricity')

    # ---- Thermal Connections ----
    system.connect('HeatPump', 'HeatDemand', 'heat')
    system.connect('HeatPump', 'HeatBuffer', 'heat')
    system.connect('ElectricBoiler', 'HeatDemand', 'heat')
    system.connect('ElectricBoiler', 'HeatBuffer', 'heat')
    system.connect('HeatBuffer', 'HeatDemand', 'heat')

    return system


def test_thermal_system_milp():
    """Test MILP optimization with thermal components."""
    logger.info("="*60)
    logger.info("THERMAL SYSTEM TEST - MILP OPTIMIZATION")
    logger.info("="*60)

    # Test 1: Minimize cost with thermal components
    logger.info("\nTest 1: Minimize Cost with Thermal System")
    logger.info("-"*40)

    system = create_thermal_system()
    config = SolverConfig(
        verbose=False,
        solver_specific={'objective': 'min_cost'}
    )
    solver = MILPSolver(system, config)
    result = solver.solve()

    logger.info(f"Status: {result.status}")
    logger.info(f"Objective value (cost): ${result.objective_value:.2f}")
    logger.info(f"Solve time: {result.solve_time:.3f}s")

    if result.status == 'optimal':
        # Check battery operation
        battery = system.components['Battery']
        if hasattr(battery, 'E'):
            logger.info(f"Battery SOC range: {battery.E.min():.2f} - {battery.E.max():.2f} kWh")

        # Check heat buffer operation
        heat_buffer = system.components['HeatBuffer']
        if hasattr(heat_buffer, 'E') and heat_buffer.E is not None:
            if hasattr(heat_buffer.E, 'value'):
                # CVXPY variable with value attribute
                logger.info(f"Heat buffer range: {heat_buffer.E.value.min():.2f} - {heat_buffer.E.value.max():.2f} kWh")
            elif isinstance(heat_buffer.E, np.ndarray):
                # Already extracted as numpy array
                logger.info(f"Heat buffer range: {heat_buffer.E.min():.2f} - {heat_buffer.E.max():.2f} kWh")

        # Check grid usage
        grid = system.components['Grid']
        if hasattr(grid, 'P_import'):
            logger.info(f"Total grid import: {grid.P_import.sum():.2f} kWh")
        if hasattr(grid, 'P_export'):
            logger.info(f"Total grid export: {grid.P_export.sum():.2f} kWh")

        # Check heat pump operation
        heat_pump = system.components['HeatPump']
        if hasattr(heat_pump, 'P_heatsource'):
            total_heat_from_hp = heat_pump.P_heatsource.value.sum()
            logger.info(f"Total heat from heat pump: {total_heat_from_hp:.2f} kWh")

        # Check electric boiler operation
        electric_boiler = system.components['ElectricBoiler']
        if hasattr(electric_boiler, 'P_heat'):
            total_heat_from_eb = electric_boiler.P_heat.value.sum()
            logger.info(f"Total heat from electric boiler: {total_heat_from_eb:.2f} kWh")

    # Test 2: Minimize grid usage with thermal components
    logger.info("\nTest 2: Minimize Grid Usage with Thermal System")
    logger.info("-"*40)

    system = create_thermal_system()
    config = SolverConfig(
        verbose=False,
        solver_specific={'objective': 'min_grid'}
    )
    solver = MILPSolver(system, config)
    result = solver.solve()

    logger.info(f"Status: {result.status}")
    logger.info(f"Objective value (grid usage): {result.objective_value:.2f}")
    logger.info(f"Solve time: {result.solve_time:.3f}s")

    if result.status == 'optimal':
        grid = system.components['Grid']
        if hasattr(grid, 'P_import') and hasattr(grid, 'P_export'):
            total_grid = grid.P_import.sum() + grid.P_export.sum()
            logger.info(f"Total grid interaction: {total_grid:.2f} kWh")

    # Summary
    logger.info("\n" + "="*60)
    if result.status == 'optimal':
        logger.info("✅ THERMAL SYSTEM TEST PASSED!")
        logger.info("Successfully optimized system with 8 components:")
        logger.info("  - 4 Electrical: Grid, Battery, SolarPV, PowerDemand")
        logger.info("  - 4 Thermal: HeatPump, ElectricBoiler, HeatBuffer, HeatDemand")
    else:
        logger.info("❌ Thermal system test failed")
    logger.info("="*60)

    return result.status == 'optimal'


def main():
    """Main test runner."""
    success = test_thermal_system_milp()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())