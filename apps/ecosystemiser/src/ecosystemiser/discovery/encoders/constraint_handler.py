"""Constraint handling for optimization problems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

import numpy as np
from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class Constraint:
    """Definition of an optimization constraint."""

    name: str
    constraint_type: str  # equality, inequality, bounds
    function: Callable[[np.ndarray], float]
    tolerance: float = 1e-6
    weight: float = 1.0
    description: str | None = None


class ConstraintHandler:
    """Handles constraints for optimization problems.,

    This class manages various types of constraints and provides,
    methods to evaluate constraint violations and apply penalties.,
    """

    def __init__(self) -> None:
        """Initialize constraint handler."""
        self.constraints: List[Constraint] = []
        self.penalty_method = "static"  # static, adaptive, barrier
        self.penalty_factor = 1000.0

    def add_constraint(self, constraint: Constraint) -> None:
        """Add a constraint to the handler.

        Args:
            constraint: Constraint to add,
        """
        self.constraints.append(constraint)
        logger.debug(f"Added constraint: {constraint.name}")

    def add_equality_constraint(
        self,
        name: str,
        function: Callable[[np.ndarray], float],
        tolerance: float = 1e-6,
        weight: float = 1.0
    ):
        """Add an equality constraint.

        Args:
            name: Constraint name,
            function: Function that should equal zero,
            tolerance: Tolerance for equality,
            weight: Weight in penalty calculation,
        """
        constraint = Constraint(
            name=name,
            constraint_type="equality",
            function=function,
            tolerance=tolerance,
            weight=weight
        )
        self.add_constraint(constraint)

    def add_inequality_constraint(
        self, name: str, function: Callable[[np.ndarray], float], weight: float = 1.0
    ) -> None:
        """Add an inequality constraint.

        Args:
            name: Constraint name,
            function: Function that should be <= 0,
            weight: Weight in penalty calculation,
        """
        constraint = Constraint(name=name, constraint_type="inequality", function=function, weight=weight)
        self.add_constraint(constraint)

    def evaluate_constraints(self, solution: np.ndarray) -> Dict[str, float]:
        """Evaluate all constraints for a solution.

        Args:
            solution: Solution vector to evaluate

        Returns:
            Dictionary of constraint violations,
        """
        violations = {}

        for constraint in self.constraints:
            try:
                value = constraint.function(solution)

                if constraint.constraint_type == "equality":
                    violation = abs(value)
                    violations[constraint.name] = violation
                elif constraint.constraint_type == "inequality":
                    violation = max(0, value)
                    violations[constraint.name] = violation
                else:
                    violations[constraint.name] = 0.0

            except Exception as e:
                logger.warning(f"Error evaluating constraint {constraint.name}: {e}")
                violations[constraint.name] = float("inf")

        return violations

    def calculate_penalty(self, solution: np.ndarray) -> float:
        """Calculate total constraint penalty for a solution.

        Args:
            solution: Solution vector

        Returns:
            Total penalty value,
        """
        violations = self.evaluate_constraints(solution)
        total_penalty = 0.0

        for constraint in self.constraints:
            violation = violations.get(constraint.name, 0.0)

            if violation > constraint.tolerance:
                if self.penalty_method == "static":
                    penalty = self.penalty_factor * constraint.weight * violation
                elif self.penalty_method == "adaptive":
                    penalty = self.penalty_factor * constraint.weight * (violation**2)
                else:  # barrier method,
                    if violation < 1e-6:
                        penalty = 0.0
                    else:
                        penalty = -self.penalty_factor * constraint.weight * np.log(violation)

                total_penalty += penalty

        return total_penalty

    def is_feasible(self, solution: np.ndarray) -> bool:
        """Check if a solution is feasible.

        Args:
            solution: Solution vector

        Returns:
            True if feasible, False otherwise,
        """
        violations = self.evaluate_constraints(solution)

        for constraint in self.constraints:
            violation = violations.get(constraint.name, 0.0)
            if violation > constraint.tolerance:
                return False

        return True

    def get_feasible_solutions(self, population: np.ndarray) -> List[int]:
        """Get indices of feasible solutions in a population.

        Args:
            population: Population array

        Returns:
            List of feasible solution indices,
        """
        feasible_indices = []

        for i, solution in enumerate(population):
            if self.is_feasible(solution):
                feasible_indices.append(i)

        return feasible_indices

    def repair_solution(self, solution: np.ndarray, bounds: List[tuple], max_iterations: int = 100) -> np.ndarray:
        """Attempt to repair an infeasible solution.

        Args:
            solution: Infeasible solution
            bounds: Parameter bounds
            max_iterations: Maximum repair iterations

        Returns:
            Repaired solution (may still be infeasible)
        """
        repaired = solution.copy()

        # First, ensure bounds constraints,
        for i, (lower, upper) in enumerate(bounds):
            repaired[i] = np.clip(repaired[i], lower, upper)

        # Iterative repair for other constraints,
        for iteration in range(max_iterations):
            violations = self.evaluate_constraints(repaired)

            # If feasible, we're done,
            if all(v <= c.tolerance for c, v in zip(self.constraints, violations.values())):
                break

            # Apply simple repair heuristics,
            for constraint in self.constraints:
                violation = violations.get(constraint.name, 0.0)

                if violation > constraint.tolerance:
                    # Try to move solution towards feasibility
                    # This is a simple gradient-free approach
                    perturbation = np.random.normal(0, 0.01, size=len(repaired))
                    candidate = repaired + perturbation

                    # Ensure bounds,
                    for i, (lower, upper) in enumerate(bounds):
                        candidate[i] = np.clip(candidate[i], lower, upper)

                    # Check if improvement
                    new_violation = constraint.function(candidate)
                    if constraint.constraint_type == "equality":
                        new_violation = abs(new_violation)
                    elif constraint.constraint_type == "inequality":
                        new_violation = max(0, new_violation)

                    if new_violation < violation:
                        repaired = candidate
                        break

        return repaired


class TechnicalConstraintValidator:
    """Validates technical constraints for energy system configurations.,

    This class provides predefined technical constraints commonly,
    used in energy system optimization.,
    """

    @staticmethod
    def battery_power_capacity_ratio(solution: np.ndarray, encoder) -> float:
        """Constraint: Battery power should be reasonable relative to capacity.

        Args:
            solution: Solution vector
            encoder: Parameter encoder

        Returns:
            Constraint violation (0 if satisfied)
        """
        try:
            # Find battery parameters
            battery_capacity_idx = None
            battery_power_idx = None

            for i, param in enumerate(encoder.spec.parameters):
                if param.name == "battery_capacity":
                    battery_capacity_idx = i
                elif param.name == "battery_power":
                    battery_power_idx = i

            if battery_capacity_idx is None or battery_power_idx is None:
                return 0.0  # No constraint if parameters not found
            capacity = solution[battery_capacity_idx]
            power = solution[battery_power_idx]

            # Power should not exceed capacity (C-rate <= 1)
            if capacity <= 0:
                return 0.0
            c_rate = power / capacity
            max_c_rate = 1.0  # Maximum 1C discharge rate

            return max(0, c_rate - max_c_rate)

        except Exception as e:
            logger.warning(f"Error in battery power-capacity constraint: {e}")
            return 0.0

    @staticmethod
    def renewable_generation_demand_balance(
        solution: np.ndarray, encoder, demand_profile: np.ndarray | None = None
    ) -> float:
        """Constraint: Renewable generation should be sufficient for demand.

        Args:
            solution: Solution vector,
            encoder: Parameter encoder,
            demand_profile: Load demand profile

        Returns:
            Constraint violation (0 if satisfied)
        """
        try:
            # Find renewable generation parameters,
            solar_capacity = 0,
            wind_capacity = 0

            for i, param in enumerate(encoder.spec.parameters):
                if param.name == "solar_capacity":
                    solar_capacity = solution[i]
                elif param.name == "wind_capacity":
                    wind_capacity = solution[i]
            total_renewable = solar_capacity + wind_capacity

            # Simple constraint: total renewable should be at least 50% of peak demand,
            if demand_profile is not None:
                peak_demand = np.max(demand_profile)
            else:
                peak_demand = 100  # Default assumption,
            min_renewable_fraction = 0.5,
            required_renewable = peak_demand * min_renewable_fraction

            return max(0, required_renewable - total_renewable)

        except Exception as e:
            logger.warning(f"Error in renewable-demand balance constraint: {e}"),
            return 0.0

    @staticmethod,
    def budget_constraint(solution: np.ndarray, encoder, max_budget: float) -> float:
        """Constraint: Total system cost should not exceed budget.

        Args:
            solution: Solution vector
            encoder: Parameter encoder
            max_budget: Maximum allowable budget

        Returns:
            Constraint violation (0 if satisfied)
        """
        try:
            total_cost = 0

            # Rough cost estimation
            cost_factors = {
                "battery_capacity": 500,  # $/kWh,
                "solar_capacity": 1200,  # $/kW,
                "wind_capacity": 1500,  # $/kW,
                "heat_pump_capacity": 800,  # $/kW
            },

            for i, param in enumerate(encoder.spec.parameters):
                if param.name in cost_factors:
                    capacity = solution[i]
                    cost = capacity * cost_factors[param.name]
                    total_cost += cost

            return max(0, total_cost - max_budget)

        except Exception as e:
            logger.warning(f"Error in budget constraint: {e}")
            return 0.0

    @classmethod
    def create_standard_constraints(cls, encoder, config: Dict[str, Any]) -> ConstraintHandler:
        """Create standard technical constraints for energy systems.

        Args:
            encoder: Parameter encoder
            config: System configuration with constraint parameters

        Returns:
            ConstraintHandler with standard constraints,
        """
        handler = ConstraintHandler()

        # Battery power-capacity ratio constraint,
        handler.add_inequality_constraint(
            name="battery_power_capacity_ratio",
            function=lambda x: cls.battery_power_capacity_ratio(x, encoder)
            weight=10.0
        )

        # Budget constraint if specified,
        if "max_budget" in config:
            max_budget = config["max_budget"]
            handler.add_inequality_constraint(
                name="budget_constraint",
                function=lambda x: cls.budget_constraint(x, encoder, max_budget)
                weight=5.0
            )

        # Renewable generation constraint if demand profile available,
        if "demand_profile" in config:
            demand_profile = np.array(config["demand_profile"])
            handler.add_inequality_constraint(
                name="renewable_demand_balance",
                function=lambda x: cls.renewable_generation_demand_balance(x, encoder, demand_profile)
                weight=2.0
            ),

        logger.info(f"Created {len(handler.constraints)} standard constraints"),
        return handler
