#!/usr/bin/env python3
"""Debug script for MILP objective construction."""

from pathlib import Path

import cvxpy as cp

from hive_logging import get_logger

logger = get_logger(__name__)

eco_path = Path(__file__).parent / "src"

from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.system_model.components.energy.grid import Grid, GridParams, GridTechnicalParams
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel
from ecosystemiser.system_model.system import System


def debug_objective() -> None:
    """Debug the objective function construction."""
    N = 3
    system = System(system_id="debug_system", n=N)

    # Create grid
    grid_params = GridParams(
        technical=GridTechnicalParams(
            capacity_nominal=50.0,
            import_tariff=0.30,
            feed_in_tariff=0.05,
            fidelity_level=FidelityLevel.SIMPLE,
        ),
    )
    grid = Grid("Grid", grid_params, N)
    system.add_component(grid)

    # Create MILP solver
    solver = MILPSolver(system)

    logger.info("=== DEBUGGING OBJECTIVE CONSTRUCTION ===")

    # Prepare system
    solver.prepare_system()

    # Get contributions
    contributions = system.get_component_cost_contributions()
    logger.info(f"Contributions: {contributions}")

    # Manual objective construction to debug
    cost_terms = []
    for comp_name, comp_costs in contributions.items():
        for cost_type, cost_data in comp_costs.items():
            rate = cost_data.get("rate", 0)
            variable = cost_data.get("variable")

            logger.info(f"\nProcessing {comp_name}.{cost_type}:")
            logger.info(f"  rate: {rate}")
            logger.info(f"  variable: {variable}")
            logger.info(f"  variable type: {type(variable)}")

            if variable is not None and rate != 0:
                if hasattr(variable, "shape") and len(variable.shape) > 0:
                    logger.info(f"  variable is array-like, shape: {variable.shape}")
                    cost_term = cp.sum(variable) * rate
                else:
                    logger.info("  variable is scalar")
                    cost_term = variable * rate

                logger.info(f"  cost_term: {cost_term}")
                logger.info(f"  cost_term type: {type(cost_term)}")
                logger.info(f"  cost_term is_scalar: {cost_term.is_scalar()}")

                cost_terms.append(cost_term)

    logger.info(f"\nCost terms: {cost_terms}")

    if cost_terms:
        logger.info(f"Building total_cost with cp.sum({len(cost_terms)} terms)")
        total_cost = cp.sum(cost_terms)
        logger.info(f"total_cost: {total_cost}")
        logger.info(f"total_cost type: {type(total_cost)}")
        logger.info(f"total_cost is_scalar: {total_cost.is_scalar()}")

        logger.info("Creating cp.Minimize(total_cost)")
        objective = cp.Minimize(total_cost)
        logger.info(f"objective: {objective}")
        logger.info(f"objective type: {type(objective)}")
    else:
        logger.info("No cost terms found")


if __name__ == "__main__":
    debug_objective()
