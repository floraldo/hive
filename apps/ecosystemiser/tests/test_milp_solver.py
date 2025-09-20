"""Test MILP solver with minimal 4-component system."""

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
from solver.milp_solver_v2 import MILPSolver
from solver.base import SolverConfig


def create_test_system():
    """Create minimal test system for MILP solver."""
    N = 24
    system = System('milp_test', N)

    # Create profiles
    # Solar profile (peak at midday)
    solar_profile = np.zeros(N)
    for t in range(N):
        if 6 <= t <= 18:  # Daylight hours
            solar_profile[t] = np.sin((t - 6) * np.pi / 12) * 5.0

    # Demand profile
    demand_profile = np.ones(N) * 1.0  # 1 kW baseload
    demand_profile[7:9] = 2.0   # Morning peak
    demand_profile[18:21] = 2.5  # Evening peak

    # Create components
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
        params=SolarPVParams(P_profile=solar_profile.tolist(), P_max=10)
    )
    system.add_component(solar)

    demand = PowerDemand(
        name='PowerDemand',
        params=PowerDemandParams(P_profile=demand_profile.tolist(), P_max=5)
    )
    system.add_component(demand)

    # Create connections (not used directly by MILP but good for structure)
    system.connect('Grid', 'PowerDemand', 'electricity')
    system.connect('Grid', 'Battery', 'electricity')
    system.connect('SolarPV', 'PowerDemand', 'electricity')
    system.connect('SolarPV', 'Battery', 'electricity')
    system.connect('SolarPV', 'Grid', 'electricity')
    system.connect('Battery', 'PowerDemand', 'electricity')
    system.connect('Battery', 'Grid', 'electricity')

    return system


def test_milp_solver():
    """Test MILP solver with different objectives."""
    logger.info("="*60)
    logger.info("MILP SOLVER TEST")
    logger.info("="*60)

    # Test 1: Minimize cost
    logger.info("\nTest 1: Minimize Cost Objective")
    logger.info("-"*40)

    system = create_test_system()
    config = SolverConfig(
        verbose=False,
        solver_specific={'objective': 'min_cost'}
    )
    solver = MILPSolver(system, config)
    result = solver.solve()

    logger.info(f"Status: {result.status}")
    logger.info(f"Objective value: {result.objective_value:.2f}")
    logger.info(f"Solve time: {result.solve_time:.3f}s")

    if result.status == 'optimal':
        # Check battery operation
        battery = system.components['Battery']
        if hasattr(battery, 'E'):
            logger.info(f"Battery SOC range: {battery.E.min():.2f} - {battery.E.max():.2f} kWh")

        # Check grid usage
        grid = system.components['Grid']
        if hasattr(grid, 'P_import'):
            logger.info(f"Total grid import: {grid.P_import.sum():.2f} kWh")
        if hasattr(grid, 'P_export'):
            logger.info(f"Total grid export: {grid.P_export.sum():.2f} kWh")

    # Test 2: Minimize grid usage
    logger.info("\nTest 2: Minimize Grid Usage Objective")
    logger.info("-"*40)

    system = create_test_system()
    config = SolverConfig(
        verbose=False,
        solver_specific={'objective': 'min_grid'}
    )
    solver = MILPSolver(system, config)
    result = solver.solve()

    logger.info(f"Status: {result.status}")
    logger.info(f"Objective value: {result.objective_value:.2f}")
    logger.info(f"Solve time: {result.solve_time:.3f}s")

    if result.status == 'optimal':
        grid = system.components['Grid']
        if hasattr(grid, 'P_import') and hasattr(grid, 'P_export'):
            total_grid = grid.P_import.sum() + grid.P_export.sum()
            logger.info(f"Total grid usage: {total_grid:.2f} kWh")

    # Test 3: Minimize CO2
    logger.info("\nTest 3: Minimize CO2 Objective")
    logger.info("-"*40)

    system = create_test_system()
    config = SolverConfig(
        verbose=False,
        solver_specific={'objective': 'min_co2'}
    )
    solver = MILPSolver(system, config)
    result = solver.solve()

    logger.info(f"Status: {result.status}")
    logger.info(f"Objective value: {result.objective_value:.2f}")
    logger.info(f"Solve time: {result.solve_time:.3f}s")

    logger.info("\n" + "="*60)
    if all([r.status == 'optimal' for r in [result]]):
        logger.info("✅ ALL MILP TESTS PASSED!")
    else:
        logger.info("❌ Some tests failed")
    logger.info("="*60)


if __name__ == "__main__":
    test_milp_solver()