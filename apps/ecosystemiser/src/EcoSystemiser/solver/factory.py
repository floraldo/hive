"""Factory for creating solver instances."""

from typing import Dict, Optional, Type

from ecosystemiser.solver.base import BaseSolver, SolverConfig
from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.solver.rolling_horizon_milp import RollingHorizonMILPSolver
from ecosystemiser.solver.rule_based_engine import RuleBasedEngine


class SolverFactory:
    """Factory for creating solver instances based on type."""

    # Registry of available solvers
    _solvers: Dict[str, Type[BaseSolver]] = {
        "rule_based": RuleBasedEngine,
        "milp": MILPSolver,
        "rolling_horizon": RollingHorizonMILPSolver,
    }

    @classmethod
    def get_solver(cls, solver_type: str, system, config: Optional[SolverConfig] = None) -> BaseSolver:
        """Get a solver instance of the specified type.

        Args:
            solver_type: Type of solver ('rule_based', 'milp')
            system: System object to solve
            config: Optional solver configuration

        Returns:
            Solver instance

        Raises:
            ValueError: If solver type is unknown
        """
        if solver_type not in cls._solvers:
            available = ", ".join(cls._solvers.keys())
            raise ValueError(f"Unknown solver type: {solver_type}. Available: {available}")

        solver_class = cls._solvers[solver_type]
        return solver_class(system, config)

    @classmethod
    def register_solver(cls, name: str, solver_class: Type[BaseSolver]):
        """Register a new solver type.

        Args:
            name: Name for the solver type
            solver_class: Solver class (must inherit from BaseSolver)
        """
        if not issubclass(solver_class, BaseSolver):
            raise TypeError(f"{solver_class} must inherit from BaseSolver")

        cls._solvers[name] = solver_class

    @classmethod
    def list_available_solvers(cls) -> list:
        """Get list of available solver types."""
        return list(cls._solvers.keys())
