"""
Comprehensive comparison test between original Systemiser and EcoSystemiser.

This test runs identical 4-component systems in both frameworks and
compares the MILP optimization results.
"""

import sys
from pathlib import Path
import json
import numpy as np
import logging
import cvxpy as cp

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add paths for imports
eco_path = Path(__file__).parent.parent / 'src' / 'EcoSystemiser'
systemiser_path = Path(__file__).parent.parent.parent / 'legacy' / 'Systemiser'

def run_original_systemiser_milp():
    """Run MILP optimization with original Systemiser."""
    logger.info("Running Original Systemiser MILP...")

    # Import from original Systemiser
    from system.system import System as OrigSystem
    from system.battery import Battery as OrigBattery
    from system.grid import Grid as OrigGrid
    from system.solar_pv import SolarPV as OrigSolarPV
    from system.power_demand import PowerDemand as OrigPowerDemand

    N = 24
    system = OrigSystem('original_test', N)

    # Create profiles
    solar_profile = np.zeros(N)
    for t in range(N):
        if 6 <= t <= 18:
            solar_profile[t] = np.sin((t - 6) * np.pi / 12) * 5.0

    demand_profile = np.ones(N) * 1.0
    demand_profile[7:9] = 2.0
    demand_profile[18:21] = 2.5

    # Create components
    grid = OrigGrid('Grid', P_max=100, n=N)
    system.add_component(grid)

    battery = OrigBattery('Battery', P_max=5, E_max=10, E_init=5, eta=0.95, n=N)
    system.add_component(battery)

    solar = OrigSolarPV('SolarPV', P_profile=solar_profile, P_max=10, n=N)
    system.add_component(solar)

    demand = OrigPowerDemand('PowerDemand', P_profile=demand_profile, P_max=5, n=N)
    system.add_component(demand)

    # Create connections
    system.connect('Grid', 'PowerDemand', 'electricity', print_connection=False)
    system.connect('Grid', 'Battery', 'electricity', print_connection=False)
    system.connect('SolarPV', 'PowerDemand', 'electricity', print_connection=False)
    system.connect('SolarPV', 'Battery', 'electricity', print_connection=False)
    system.connect('SolarPV', 'Grid', 'electricity', print_connection=False)
    system.connect('Battery', 'PowerDemand', 'electricity', print_connection=False)
    system.connect('Battery', 'Grid', 'electricity', print_connection=False)

    # Collect constraints
    constraints = []
    for comp in system.components.values():
        constraints.extend(comp.set_constraints())

    # Create objective (minimize cost)
    cost = 0
    import_tariff = 0.25
    export_tariff = 0.08

    # Grid costs
    if 'P_draw' in grid.flows['source']:
        cost += cp.sum(grid.flows['source']['P_draw']['value']) * import_tariff
    if 'P_feed' in grid.flows['sink']:
        cost -= cp.sum(grid.flows['sink']['P_feed']['value']) * export_tariff

    objective = cp.Minimize(cost)

    # Solve
    problem = cp.Problem(objective, constraints)
    problem.solve(verbose=False)

    # Extract results
    results = {
        'status': problem.status,
        'objective': problem.value,
        'battery_energy': battery.E.value.tolist() if battery.E.value is not None else [],
        'grid_import': grid.flows['source']['P_draw']['value'].value.tolist() if grid.flows['source']['P_draw']['value'].value is not None else [],
        'grid_export': grid.flows['sink']['P_feed']['value'].value.tolist() if grid.flows['sink']['P_feed']['value'].value is not None else [],
        'solar_output': solar.flows['source']['P_out']['value'].value.tolist() if solar.flows['source']['P_out']['value'].value is not None else [],
        'demand_input': demand.flows['sink']['P_in']['value'].value.tolist() if demand.flows['sink']['P_in']['value'].value is not None else []
    }

    return results

def run_ecosystemiser_milp():
    """Run MILP optimization with EcoSystemiser."""
    logger.info("Running EcoSystemiser MILP...")

    # Import from EcoSystemiser
    from EcoSystemiser.system_model.system import System
    from EcoSystemiser.system_model.components.energy.battery import Battery, BatteryParams
    from EcoSystemiser.system_model.components.energy.grid import Grid, GridParams
    from EcoSystemiser.system_model.components.energy.solar_pv import SolarPV, SolarPVParams
    from EcoSystemiser.system_model.components.energy.power_demand import PowerDemand, PowerDemandParams
    from EcoSystemiser.solver.milp_solver import MILPSolver
    from EcoSystemiser.solver.base import SolverConfig

    N = 24
    system = System('eco_test', N)

    # Create profiles
    solar_profile = np.zeros(N)
    for t in range(N):
        if 6 <= t <= 18:
            solar_profile[t] = np.sin((t - 6) * np.pi / 12) * 5.0

    demand_profile = np.ones(N) * 1.0
    demand_profile[7:9] = 2.0
    demand_profile[18:21] = 2.5

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

    # Create connections
    system.connect('Grid', 'PowerDemand', 'electricity')
    system.connect('Grid', 'Battery', 'electricity')
    system.connect('SolarPV', 'PowerDemand', 'electricity')
    system.connect('SolarPV', 'Battery', 'electricity')
    system.connect('SolarPV', 'Grid', 'electricity')
    system.connect('Battery', 'PowerDemand', 'electricity')
    system.connect('Battery', 'Grid', 'electricity')

    # Solve with MILP
    config = SolverConfig(verbose=False, solver_specific={'objective': 'min_cost'})
    solver = MILPSolver(system, config)
    result = solver.solve()

    # Extract results
    results = {
        'status': result.status,
        'objective': result.objective_value,
        'battery_energy': battery.E.tolist() if hasattr(battery, 'E') and battery.E is not None else [],
        'grid_import': grid.P_import.tolist() if hasattr(grid, 'P_import') and grid.P_import is not None else [],
        'grid_export': grid.P_export.tolist() if hasattr(grid, 'P_export') and grid.P_export is not None else [],
        'solar_output': solar.P_generation.tolist() if hasattr(solar, 'P_generation') and solar.P_generation is not None else [],
        'demand_input': demand.P_consumption.tolist() if hasattr(demand, 'P_consumption') and demand.P_consumption is not None else []
    }

    return results

def compare_results(orig_results, eco_results):
    """Compare results from both systems."""
    logger.info("\n" + "="*60)
    logger.info("COMPARISON RESULTS")
    logger.info("="*60)

    # Status comparison
    logger.info(f"\nOptimization Status:")
    logger.info(f"  Original Systemiser: {orig_results['status']}")
    logger.info(f"  EcoSystemiser: {eco_results['status']}")

    # Objective comparison
    logger.info(f"\nObjective Value (Cost):")
    logger.info(f"  Original Systemiser: ${orig_results['objective']:.2f}")
    logger.info(f"  EcoSystemiser: ${eco_results['objective']:.2f}")
    if orig_results['objective'] and eco_results['objective']:
        diff = abs(orig_results['objective'] - eco_results['objective'])
        logger.info(f"  Difference: ${diff:.4f}")

    # Battery energy comparison
    if orig_results['battery_energy'] and eco_results['battery_energy']:
        orig_battery = np.array(orig_results['battery_energy'])
        eco_battery = np.array(eco_results['battery_energy'])

        logger.info(f"\nBattery Energy Levels:")
        logger.info(f"  Original range: {orig_battery.min():.2f} - {orig_battery.max():.2f} kWh")
        logger.info(f"  Eco range: {eco_battery.min():.2f} - {eco_battery.max():.2f} kWh")

        max_diff = np.max(np.abs(orig_battery - eco_battery))
        logger.info(f"  Max difference: {max_diff:.6f} kWh")

    # Grid usage comparison
    if orig_results['grid_import'] and eco_results['grid_import']:
        orig_import = np.array(orig_results['grid_import'])
        eco_import = np.array(eco_results['grid_import'])

        logger.info(f"\nGrid Import:")
        logger.info(f"  Original total: {orig_import.sum():.2f} kWh")
        logger.info(f"  Eco total: {eco_import.sum():.2f} kWh")
        logger.info(f"  Difference: {abs(orig_import.sum() - eco_import.sum()):.4f} kWh")

    if orig_results['grid_export'] and eco_results['grid_export']:
        orig_export = np.array(orig_results['grid_export'])
        eco_export = np.array(eco_results['grid_export'])

        logger.info(f"\nGrid Export:")
        logger.info(f"  Original total: {orig_export.sum():.2f} kWh")
        logger.info(f"  Eco total: {eco_export.sum():.2f} kWh")
        logger.info(f"  Difference: {abs(orig_export.sum() - eco_export.sum()):.4f} kWh")

    # Determine if results match
    TOLERANCE = 1e-3  # Allow small numerical differences

    match = True
    if orig_results['status'] != eco_results['status']:
        match = False
        logger.warning("Status mismatch!")

    if abs(orig_results['objective'] - eco_results['objective']) > TOLERANCE:
        match = False
        logger.warning("Objective value mismatch!")

    logger.info("\n" + "="*60)
    if match:
        logger.info("✅ VALIDATION SUCCESSFUL! Both systems produce equivalent results!")
    else:
        logger.warning("⚠️ Results differ between systems - investigation needed")
    logger.info("="*60)

    return match

def main():
    """Main comparison test."""
    logger.info("="*60)
    logger.info("SYSTEMISER vs ECOSYSTEMISER COMPARISON")
    logger.info("="*60)

    try:
        # Run original Systemiser
        orig_results = run_original_systemiser_milp()
        logger.info("✅ Original Systemiser completed")

    except Exception as e:
        logger.error(f"❌ Original Systemiser failed: {e}")
        orig_results = None

    try:
        # Run EcoSystemiser
        eco_results = run_ecosystemiser_milp()
        logger.info("✅ EcoSystemiser completed")

    except Exception as e:
        logger.error(f"❌ EcoSystemiser failed: {e}")
        eco_results = None

    # Compare if both succeeded
    if orig_results and eco_results:
        match = compare_results(orig_results, eco_results)
        return match
    else:
        logger.error("Could not complete comparison due to failures")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)