"""Test water system integration with hierarchical architecture."""

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
from system_model.components.water.water_storage import WaterStorage, WaterStorageParams
from system_model.components.water.water_grid import WaterGrid, WaterGridParams
from system_model.components.water.rainwater_source import RainwaterSource, RainwaterSourceParams
from system_model.components.water.water_demand import WaterDemand, WaterDemandParams
from system_model.components.shared.archetypes import FidelityLevel
from solver.milp_solver import MILPSolver
from solver.base import SolverConfig


def create_water_system():
    """Create system with water components using new hierarchical architecture."""
    N = 24
    system = System('water_test', N)

    # Create profiles
    # Rainfall profile (rain in morning and evening)
    rainfall_profile = np.zeros(N)
    rainfall_profile[6:10] = 8.0   # Morning rain: 8mm/h for 4 hours
    rainfall_profile[16:20] = 5.0  # Evening rain: 5mm/h for 4 hours

    # Water demand profile (higher during day)
    water_demand = np.ones(N) * 0.8  # 0.8 m³/h baseload
    water_demand[6:8] = 2.0    # Morning peak
    water_demand[12:14] = 1.5  # Lunch peak
    water_demand[18:21] = 2.5  # Evening peak

    # ---- Water Components (NEW Architecture) ----
    # NOTE: These will fail until we refactor them to use the new architecture

    water_grid = WaterGrid(
        name='WaterGrid',
        params=WaterGridParams()  # Use defaults, then override
    )
    # Override technical parameters for this test (will fail until WaterGrid is refactored)
    water_grid.technical.capacity_nominal = 10.0    # Max supply capacity
    water_grid.technical.max_import = 10.0          # max_supply_m3h
    water_grid.technical.max_export = 5.0           # max_discharge_m3h
    water_grid.technical.import_tariff = 1.5        # water_price_per_m3
    water_grid.technical.feed_in_tariff = 2.0       # wastewater_price_per_m3
    water_grid.technical.fidelity_level = FidelityLevel.SIMPLE
    system.add_component(water_grid)

    water_storage = WaterStorage(
        name='WaterStorage',
        params=WaterStorageParams()  # Use defaults, then override
    )
    # Override technical parameters for this test (will fail until WaterStorage is refactored)
    water_storage.technical.capacity_nominal = 20.0     # capacity_m3
    water_storage.technical.max_charge_rate = 4.0       # max_flow_in_m3h
    water_storage.technical.max_discharge_rate = 4.0    # max_flow_out_m3h
    water_storage.technical.efficiency_roundtrip = 0.95 # (minimal loss)
    water_storage.technical.initial_soc_pct = 0.5       # 50% full initially
    water_storage.technical.fidelity_level = FidelityLevel.SIMPLE
    system.add_component(water_storage)

    rainwater_source = RainwaterSource(
        name='RainwaterSource',
        params=RainwaterSourceParams()  # Use defaults, then override
    )
    # Override technical parameters for this test (will fail until RainwaterSource is refactored)
    rainwater_source.technical.capacity_nominal = 8.0  # max collection rate
    rainwater_source.technical.efficiency_nominal = 0.90 # collection efficiency
    rainwater_source.technical.fidelity_level = FidelityLevel.SIMPLE
    rainwater_source.profile = rainfall_profile  # Assign rainfall profile separately
    system.add_component(rainwater_source)

    water_demand_load = WaterDemand(
        name='WaterDemand',
        params=WaterDemandParams()  # Use defaults, then override
    )
    # Override technical parameters for this test (will fail until WaterDemand is refactored)
    water_demand_load.technical.capacity_nominal = 3.0  # max demand
    water_demand_load.technical.peak_demand = 3.0       # max demand
    water_demand_load.technical.fidelity_level = FidelityLevel.SIMPLE
    water_demand_load.profile = water_demand  # Assign demand profile separately
    system.add_component(water_demand_load)

    # ---- Water Connections ----
    system.connect('WaterGrid', 'WaterDemand', 'water')
    system.connect('WaterGrid', 'WaterStorage', 'water')
    system.connect('RainwaterSource', 'WaterDemand', 'water')
    system.connect('RainwaterSource', 'WaterStorage', 'water')
    system.connect('WaterStorage', 'WaterDemand', 'water')

    return system


def test_water_system_milp():
    """Test MILP optimization with water components using new architecture."""
    logger.info("="*60)
    logger.info("WATER SYSTEM TEST - MILP OPTIMIZATION")
    logger.info("="*60)

    # Test 1: Minimize cost with water system
    logger.info("\nTest 1: Minimize Cost with Water System")
    logger.info("-"*40)

    system = create_water_system()
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
        # Check water storage operation
        water_storage = system.components['WaterStorage']
        if hasattr(water_storage, 'W') and water_storage.W is not None:
            if hasattr(water_storage.W, 'value'):
                # CVXPY variable with value attribute
                logger.info(f"Water storage range: {water_storage.W.value.min():.2f} - {water_storage.W.value.max():.2f} m³")
            elif isinstance(water_storage.W, np.ndarray):
                # Already extracted as numpy array
                logger.info(f"Water storage range: {water_storage.W.min():.2f} - {water_storage.W.max():.2f} m³")

        # Check grid usage
        water_grid = system.components['WaterGrid']
        if hasattr(water_grid, 'W_import'):
            logger.info(f"Total grid water import: {water_grid.W_import.sum():.2f} m³")
        if hasattr(water_grid, 'W_export'):
            logger.info(f"Total grid water export: {water_grid.W_export.sum():.2f} m³")

        # Check rainwater collection
        rainwater = system.components['RainwaterSource']
        if hasattr(rainwater, 'W_collected'):
            total_rainwater = rainwater.W_collected.value.sum()
            logger.info(f"Total rainwater collected: {total_rainwater:.2f} m³")

    # Test 2: Minimize grid usage with water system
    logger.info("\nTest 2: Minimize Grid Usage with Water System")
    logger.info("-"*40)

    system = create_water_system()
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
        water_grid = system.components['WaterGrid']
        if hasattr(water_grid, 'W_import') and hasattr(water_grid, 'W_export'):
            total_grid = water_grid.W_import.sum() + water_grid.W_export.sum()
            logger.info(f"Total grid interaction: {total_grid:.2f} m³")

    # Summary
    logger.info("\n" + "="*60)
    if result.status == 'optimal':
        logger.info("✅ WATER SYSTEM TEST PASSED!")
        logger.info("Successfully optimized system with 4 water components:")
        logger.info("  - WaterGrid (transmission)")
        logger.info("  - WaterStorage (storage)")
        logger.info("  - RainwaterSource (generation)")
        logger.info("  - WaterDemand (demand)")
    else:
        logger.info("❌ Water system test failed")
    logger.info("="*60)

    return result.status == 'optimal'


def main():
    """Main test runner."""
    success = test_water_system_milp()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())