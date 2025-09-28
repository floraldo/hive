"""Base solver abstract class for all solver implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from hive_logging import get_logger
from pydantic import BaseModel

logger = get_logger(__name__)


class SolverConfig(BaseModel):
    """Configuration for solver behavior."""

    max_iterations: int = 1000
    tolerance: float = 1e-6
    verbose: bool = False
    solver_specific: Dict[str, Any] = {}

    # Multi-objective configuration
    objective_weights: Optional[Dict[str, float]] = None  # e.g., {"cost": 0.7, "emissions": 0.3}
    normalize_objectives: bool = True  # Normalize objectives before combining
    pareto_mode: bool = False  # Generate Pareto frontier instead of single solution


class SolverResult(BaseModel):
    """Result structure from solver execution."""

    status: str  # "optimal", "infeasible", "error"
    objective_value: Optional[float] = None
    solve_time: float
    iterations: int = 0
    message: str = ""


class BaseSolver(ABC):
    """Abstract base class for all system solvers."""

    def __init__(self, system, config: Optional[SolverConfig] = None):
        """Initialize solver with system and configuration.

        Args:
            system: System object to solve
            config: Solver configuration
        """
        self.system = system
        self.config = config or SolverConfig()
        self.result = None

    @abstractmethod
    def solve(self) -> SolverResult:
        """Solve the system and return results.

        Returns:
            SolverResult object containing solution status and metrics
        """
        pass

    @abstractmethod
    def prepare_system(self):
        """Prepare the system for solving.

        This method should handle any solver-specific initialization,
        such as creating optimization variables or initializing arrays.
        """
        pass

    @abstractmethod
    def extract_results(self):
        """Extract results from solved system.

        This method should convert solver-specific results into
        standard numpy arrays in the system flows.
        """
        pass

    def validate_solution(self) -> bool:
        """Validate that the solution satisfies all constraints.

        Returns:
            True if solution is valid, False otherwise
        """
        # Default implementation - can be overridden
        violations = []

        for component in self.system.components.values():
            # Check storage bounds
            if component.type == "storage":
                if hasattr(component, "E"):
                    E = component.E
                    E_max = getattr(component, "E_max", float("inf"))
                    if any(e < -1e-6 or e > E_max + 1e-6 for e in E if e is not None):
                        violations.append(f"{component.name}: Storage bounds violated")

        if violations:
            logger.warning(f"Solution validation failed: {violations}")
            return False

        return True
