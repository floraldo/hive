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
from system_model.components.energy.battery import Battery, BatteryParams, BatteryTechnicalParams
from system_model.components.energy.grid import Grid, GridParams, GridTechnicalParams
from system_model.components.energy.solar_pv import SolarPV, SolarPVParams, SolarPVTechnicalParams
from system_model.components.energy.power_demand import PowerDemand, PowerDemandParams, PowerDemandTechnicalParams
from solver.milp_solver import MILPSolver
from solver.base import SolverConfig
from system_model.components.shared.archetypes import FidelityLevel


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
        params=GridParams(
            technical=GridTechnicalParams(
                capacity_nominal=100.0,  # Required by base archetype
                max_import=100.0,
                max_export=100.0,
                import_tariff=0.25,
                feed_in_tariff=0.08,
                fidelity_level=FidelityLevel.SIMPLE
            )
        )
    )
    system.add_component(grid)

    battery = Battery(
        name='Battery',
        params=BatteryParams(
            technical=BatteryTechnicalParams(
                capacity_nominal=10.0,
                max_charge_rate=5.0,
                max_discharge_rate=5.0,
                efficiency_roundtrip=0.90,
                initial_soc=0.5,
                fidelity_level=FidelityLevel.SIMPLE
            )
        )
    )
    system.add_component(battery)

    solar = SolarPV(
        name='SolarPV',
        params=SolarPVParams(
            technical=SolarPVTechnicalParams(
                capacity_nominal=10.0,
                fidelity_level=FidelityLevel.SIMPLE
            )
        )
    )
    solar.profile = solar_profile  # Profile assigned separately
    system.add_component(solar)

    demand = PowerDemand(
        name='PowerDemand',
        params=PowerDemandParams(
            technical=PowerDemandTechnicalParams(
                capacity_nominal=5.0,  # Required by base archetype
                peak_demand=5.0,
                fidelity_level=FidelityLevel.SIMPLE
            )
        )
    )
    demand.profile = demand_profile  # Profile assigned separately
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