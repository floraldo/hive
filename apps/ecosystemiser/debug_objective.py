#!/usr/bin/env python3
"""Debug script for MILP objective construction."""

import sys
from pathlib import Path

import cvxpy as cp

# Add ecosystemiser to path
eco_path = Path(__file__).parent / "src"
sys.path.insert(0, str(eco_path))

import numpy as np
from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.system_model.components.energy.grid import (
    Grid,
    GridParams,
    GridTechnicalParams,
)
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel
from ecosystemiser.system_model.system import System
from hive_logging import get_logger


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
        )
    )
    grid = Grid("Grid", grid_params, N)
    system.add_component(grid)

    # Create MILP solver
    solver = MILPSolver(system)

    print("=== DEBUGGING OBJECTIVE CONSTRUCTION ===")

    # Prepare system
    solver.prepare_system()

    # Get contributions
    contributions = system.get_component_cost_contributions()
    print(f"Contributions: {contributions}")

    # Manual objective construction to debug
    cost_terms = []
    for comp_name, comp_costs in contributions.items():
        for cost_type, cost_data in comp_costs.items():
            rate = cost_data.get("rate", 0)
            variable = cost_data.get("variable")

            print(f"\nProcessing {comp_name}.{cost_type}:")
            print(f"  rate: {rate}")
            print(f"  variable: {variable}")
            print(f"  variable type: {type(variable)}")

            if variable is not None and rate != 0:
                if hasattr(variable, "shape") and len(variable.shape) > 0:
                    print(f"  variable is array-like, shape: {variable.shape}")
                    cost_term = cp.sum(variable) * rate
                else:
                    print(f"  variable is scalar")
                    cost_term = variable * rate

                print(f"  cost_term: {cost_term}")
                print(f"  cost_term type: {type(cost_term)}")
                print(f"  cost_term is_scalar: {cost_term.is_scalar()}")

                cost_terms.append(cost_term)

    print(f"\nCost terms: {cost_terms}")

    if cost_terms:
        print(f"Building total_cost with cp.sum({len(cost_terms)} terms)")
        total_cost = cp.sum(cost_terms)
        print(f"total_cost: {total_cost}")
        print(f"total_cost type: {type(total_cost)}")
        print(f"total_cost is_scalar: {total_cost.is_scalar()}")

        print(f"Creating cp.Minimize(total_cost)")
        objective = cp.Minimize(total_cost)
        print(f"objective: {objective}")
        print(f"objective type: {type(objective)}")
    else:
        print("No cost terms found")


if __name__ == "__main__":
    debug_objective()
