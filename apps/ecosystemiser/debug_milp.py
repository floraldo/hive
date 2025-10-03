#!/usr/bin/env python3
"""Debug script for MILP solver cost aggregation."""

from pathlib import Path

eco_path = Path(__file__).parent / "src"

from ecosystemiser.system_model.components.energy.battery import Battery, BatteryParams, BatteryTechnicalParams
from ecosystemiser.system_model.components.energy.grid import Grid, GridParams, GridTechnicalParams
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel
from ecosystemiser.system_model.system import System
from hive_logging import get_logger

logger = get_logger(__name__)


def create_debug_system() -> System:
    """Create a simple system for debugging."""
    N = 3  # Short simulation for debugging
    system = System(system_id="debug_system", n=N)

    # Create grid
    grid_params = GridParams(
        technical=GridTechnicalParams(
            capacity_nominal=50.0,
            import_tariff=0.30,
            feed_in_tariff=0.05,  # Changed to feed_in_tariff,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    grid = Grid("Grid", grid_params, N)

    # Create battery
    battery_params = BatteryParams(
        technical=BatteryTechnicalParams(
            capacity_nominal=10.0,
            max_charge_rate=5.0,
            max_discharge_rate=5.0,
            efficiency_roundtrip=0.95,
            initial_soc_pct=0.5,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    battery = Battery("Battery", battery_params, N)

    # Add components
    system.add_component(grid)
    system.add_component(battery)

    return system


def debug_cost_contributions() -> None:
    """Debug the cost contribution calculation."""
    system = create_debug_system()

    # Initialize optimization variables
    for comp in system.components.values():
        if hasattr(comp, "add_optimization_vars"):
            comp.add_optimization_vars(system.N)

    logger.info("=== COMPONENT ATTRIBUTES ===")
    for name, comp in system.components.items():
        logger.info(f"\n{name} ({comp.type}):")
        logger.info(f"  Has import_tariff: {hasattr(comp, 'import_tariff')}")
        logger.info(f"  Has feed_in_tariff: {hasattr(comp, 'feed_in_tariff')}")
        logger.info(f"  Has P_draw: {hasattr(comp, 'P_draw')} = {getattr(comp, 'P_draw', None)}")
        logger.info(f"  Has P_feed: {hasattr(comp, 'P_feed')} = {getattr(comp, 'P_feed', None)}")
        if hasattr(comp, "import_tariff"):
            logger.info(f"  import_tariff value: {comp.import_tariff}")
        if hasattr(comp, "feed_in_tariff"):
            logger.info(f"  feed_in_tariff value: {comp.feed_in_tariff}")

    logger.info("\n=== COST CONTRIBUTIONS ===")
    contributions = system.get_component_cost_contributions()

    for comp_name, comp_costs in contributions.items():
        logger.info(f"\n{comp_name}:")
        for cost_type, cost_data in comp_costs.items():
            rate = cost_data.get("rate"),
            variable = cost_data.get("variable")
            logger.info(f"  {cost_type}: rate={rate}, variable={type(variable).__name__}")
            if variable is not None:
                logger.info(f"    variable shape: {getattr(variable, 'shape', 'N/A')}")
                logger.info(f"    variable name: {getattr(variable, 'name', 'N/A')}")


if __name__ == "__main__":
    debug_cost_contributions()
