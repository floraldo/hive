"""Hybrid solver combining rule-based speed with MILP precision."""

import time

import numpy as np

from ecosystemiser.solver.base import BaseSolver, SolverResult
from ecosystemiser.solver.rolling_horizon_milp import RollingHorizonConfig, RollingHorizonMILPSolver
from ecosystemiser.solver.rule_based_engine import RuleBasedEngine
from hive_logging import get_logger

logger = get_logger(__name__)


class HybridSolver(BaseSolver):
    """Intelligent hybrid solver combining rule-based scout with MILP surveyor.

    Strategy:
    1. Scout Phase: RuleBasedEngine generates fast initial solution (seconds for 8760h)
    2. Surveyor Phase: RollingHorizonMILPSolver refines using scout as warm start

    This provides near-optimal solutions 2-3x faster than cold-start MILP by leveraging
    existing warm start infrastructure in RollingHorizonMILPSolver.
    """

    def __init__(
        self,
        system,
        config: RollingHorizonConfig | None = None,
    ) -> None:
        """Initialize hybrid solver with scout and surveyor components.

        Args:
            system: EnergySystem to optimize
            config: Configuration for surveyor phase (RollingHorizonMILPSolver)

        """
        super().__init__(system, config)

        # Scout: Fast rule-based engine for initial solution
        self.scout = RuleBasedEngine(system, config)

        # Surveyor: MILP rolling horizon with warmstart enabled
        rh_config = config or RollingHorizonConfig(warmstart=True)
        # Ensure warmstart is enabled for the hybrid approach
        if not rh_config.warmstart:
            logger.warning("Forcing warmstart=True for hybrid solver")
            rh_config.warmstart = True
        self.surveyor = RollingHorizonMILPSolver(system, rh_config)

    def solve(self) -> SolverResult:
        """Execute hybrid solving strategy: scout then surveyor.

        Returns:
            SolverResult from surveyor phase (refined MILP solution)

        """
        start_time = time.time()

        try:
            # Phase 1: Scout with rule-based engine (fast initial solution)
            logger.info("Hybrid Phase 1: Running rule-based scout")
            scout_result = self.scout.solve()

            if scout_result.status == "error":
                logger.error("Scout phase failed, cannot proceed with surveyor")
                return scout_result

            logger.info(
                "Scout completed",
                extra={
                    "status": scout_result.status,
                    "solve_time": scout_result.solve_time,
                },
            )

            # Phase 2: Extract solution vectors for warm start
            solution_vectors = self._extract_solution_vectors()

            # Create mock window result to inject as first warm start
            mock_result = {
                "status": scout_result.status,
                "start_time": 0,
                "end_time": self.system.N,
                "solution_vectors": solution_vectors,
            }

            # Inject scout solution as warm start for surveyor
            self.surveyor.window_results = [mock_result]

            logger.info(
                "Hybrid Phase 2: Running MILP surveyor with scout warm start",
                extra={"components": len(solution_vectors)},
            )

            # Phase 3: Surveyor refines with rolling horizon MILP
            surveyor_result = self.surveyor.solve()

            # Enhance result metadata with hybrid information
            surveyor_result.message = (
                f"Hybrid solution: scout={scout_result.solve_time:.1f}s, "
                f"surveyor={surveyor_result.solve_time:.1f}s, "
                f"total={time.time() - start_time:.1f}s"
            )

            logger.info(
                "Hybrid solver completed",
                extra={
                    "scout_time": scout_result.solve_time,
                    "surveyor_time": surveyor_result.solve_time,
                    "total_time": time.time() - start_time,
                    "status": surveyor_result.status,
                },
            )

            self.result = surveyor_result
            return surveyor_result

        except Exception as e:
            logger.error(f"Error in hybrid solver: {e}")
            result = SolverResult(
                status="error", solve_time=time.time() - start_time, message=f"Hybrid solver error: {e!s}",
            )
            self.result = result
            return result

    def _extract_solution_vectors(self) -> dict[str, dict[str, np.ndarray]]:
        """Extract solution vectors from system after scout solve.

        This adapter method translates the system state (populated by RuleBasedEngine)
        into the format expected by RollingHorizonMILPSolver._apply_warmstart().

        Returns:
            Dictionary mapping component names to their solution arrays

        """
        vectors = {}

        for name, comp in self.system.components.items():
            comp_vectors = {}

            # Extract storage state if available
            if hasattr(comp, "E") and comp.E is not None:
                comp_vectors["E"] = comp.E.copy()

            # Extract power/flow variables if available
            if hasattr(comp, "P_charge") and comp.P_charge is not None:
                comp_vectors["P_charge"] = comp.P_charge.copy()
            if hasattr(comp, "P_discharge") and comp.P_discharge is not None:
                comp_vectors["P_discharge"] = comp.P_discharge.copy()
            if hasattr(comp, "P_gen") and comp.P_gen is not None:
                comp_vectors["P_gen"] = comp.P_gen.copy()
            if hasattr(comp, "P") and comp.P is not None:
                comp_vectors["P"] = comp.P.copy()

            # Only add if we found any vectors
            if comp_vectors:
                vectors[name] = comp_vectors

        logger.debug(
            "Extracted solution vectors from scout",
            extra={"components": len(vectors), "total_arrays": sum(len(v) for v in vectors.values())},
        )

        return vectors

    def prepare_system(self) -> None:
        """Prepare system for solving - delegated to surveyor.

        The hybrid solver delegates system preparation to the surveyor (MILP)
        since it produces the final results.
        """
        self.surveyor.prepare_system()

    def extract_results(self) -> None:
        """Extract results from solved system - delegated to surveyor.

        The surveyor's results are the final hybrid solution, so we delegate
        result extraction to it.
        """
        self.surveyor.extract_results()
