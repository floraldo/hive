"""Rolling Horizon Meta-Solver for long-term optimization with computational efficiency.

This solver implements a hybrid strategy that combines the speed of rule-based
approaches with the optimality of MILP, making it suitable for long horizons
(weeks to years) that would be computationally intractable with pure MILP.

The strategy:
1. Run a fast rule-based solver for the entire horizon to get a baseline
2. Divide the horizon into manageable blocks (e.g., daily or weekly)
3. Run MILP optimization on each block using the baseline as guidance
4. Stitch the optimal blocks together for the final solution
"""

import numpy as np
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from .base import BaseSolver, SolverResult, SolverConfig
from .rule_based_engine import RuleBasedEngine
from .milp_solver import MILPSolver

logger = logging.getLogger(__name__)


@dataclass
class RollingHorizonConfig(SolverConfig):
    """Configuration specific to rolling horizon solver."""
    block_size_hours: int = 24  # Size of each optimization block (default: 1 day)
    overlap_hours: int = 4       # Overlap between blocks for continuity
    warm_start: bool = True      # Use rule-based solution as warm start
    parallel_blocks: bool = False  # Run blocks in parallel (future enhancement)
    max_iterations: int = 3      # Maximum refinement iterations
    convergence_tolerance: float = 0.01  # Convergence criterion


class RollingHorizonMILPSolver(BaseSolver):
    """Meta-solver that orchestrates hybrid rule-based and MILP optimization.

    This solver is designed for long-horizon problems where pure MILP would be
    computationally expensive. It uses a rolling horizon approach with warm-starting
    from rule-based solutions to achieve near-optimal results efficiently.
    """

    def __init__(self, system, config: Optional[RollingHorizonConfig] = None):
        """Initialize the rolling horizon solver.

        Args:
            system: System object to optimize
            config: Rolling horizon specific configuration
        """
        super().__init__(system, config or RollingHorizonConfig())
        self.config: RollingHorizonConfig = config or RollingHorizonConfig()

        # Internal solvers
        self.rule_based_solver = None
        self.milp_solver = None

        # Results storage
        self.baseline_solution = None
        self.block_solutions = []
        self.final_solution = None

    def solve(self) -> SolverResult:
        """Execute the rolling horizon optimization strategy."""
        start_time = time.time()
        logger.info(f"Starting rolling horizon optimization for {self.system.N} timesteps")

        try:
            # Step 1: Generate baseline with rule-based solver
            logger.info("Step 1: Generating baseline solution with rule-based engine")
            self.baseline_solution = self._generate_baseline()

            if self.baseline_solution.status != "optimal":
                logger.warning("Baseline solution not optimal, continuing anyway")

            # Step 2: Determine optimization blocks
            blocks = self._determine_blocks()
            logger.info(f"Step 2: Divided horizon into {len(blocks)} blocks of {self.config.block_size_hours} hours")

            # Step 3: Optimize each block with MILP
            logger.info("Step 3: Optimizing individual blocks with MILP")
            self.block_solutions = []
            total_objective = 0.0

            for block_idx, (start_t, end_t) in enumerate(blocks):
                logger.info(f"  Optimizing block {block_idx + 1}/{len(blocks)}: t={start_t} to t={end_t}")

                # Create sub-system for this block
                block_system = self._create_block_system(start_t, end_t, block_idx)

                # Set boundary conditions from baseline or previous block
                self._set_boundary_conditions(block_system, start_t, block_idx)

                # Run MILP on this block
                block_result = self._optimize_block(block_system, block_idx)

                if block_result.status != "optimal":
                    logger.warning(f"Block {block_idx} not optimal: {block_result.status}")

                # Store block solution
                self.block_solutions.append({
                    'block_idx': block_idx,
                    'start_t': start_t,
                    'end_t': end_t,
                    'result': block_result,
                    'system': block_system
                })

                if block_result.objective_value:
                    total_objective += block_result.objective_value

            # Step 4: Stitch block solutions together
            logger.info("Step 4: Stitching block solutions into final result")
            self._stitch_solutions()

            # Calculate final metrics
            solve_time = time.time() - start_time

            # Determine overall status
            if all(block['result'].status == "optimal" for block in self.block_solutions):
                status = "optimal"
                message = f"All {len(blocks)} blocks solved optimally"
            else:
                status = "suboptimal"
                optimal_blocks = sum(1 for b in self.block_solutions if b['result'].status == "optimal")
                message = f"{optimal_blocks}/{len(blocks)} blocks solved optimally"

            result = SolverResult(
                status=status,
                objective_value=total_objective,
                solve_time=solve_time,
                message=message,
                iterations=len(blocks)
            )

            # Store results in system
            self._apply_final_solution()

        except Exception as e:
            logger.error(f"Error in rolling horizon solver: {e}")
            result = SolverResult(
                status="error",
                solve_time=time.time() - start_time,
                message=str(e)
            )

        self.result = result
        return result

    def _generate_baseline(self) -> SolverResult:
        """Generate baseline solution using rule-based engine."""
        # Create rule-based solver
        rule_config = SolverConfig(
            verbose=False,
            solver_specific={'dispatch_order': 'merit_order'}
        )
        self.rule_based_solver = RuleBasedEngine(self.system, rule_config)

        # Run baseline optimization
        baseline_result = self.rule_based_solver.solve()

        # Store baseline solution for warm-starting
        if baseline_result.status == "optimal":
            self._store_baseline_values()

        return baseline_result

    def _determine_blocks(self) -> List[tuple[int, int]]:
        """Divide the time horizon into optimization blocks.

        Returns:
            List of (start_t, end_t) tuples for each block
        """
        blocks = []
        block_size = self.config.block_size_hours
        overlap = self.config.overlap_hours
        N = self.system.N

        # Create overlapping blocks
        t = 0
        while t < N:
            # Determine block end (with possible extension for last block)
            end_t = min(t + block_size, N)

            # Add overlap for all blocks except the last
            if end_t < N and overlap > 0:
                end_t = min(end_t + overlap, N)

            blocks.append((t, end_t))

            # Move to next block (accounting for overlap)
            t += block_size

        return blocks

    def _create_block_system(self, start_t: int, end_t: int, block_idx: int):
        """Create a sub-system for a specific time block.

        Args:
            start_t: Start timestep
            end_t: End timestep (exclusive)
            block_idx: Block index

        Returns:
            Modified system object for this block
        """
        from copy import deepcopy

        # Create a shallow copy of the system
        # (We'll modify timesteps but keep component references)
        block_system = deepcopy(self.system)

        # Adjust timesteps
        block_system.N = end_t - start_t

        # Adjust profiles to match block
        if hasattr(block_system, 'profiles'):
            for profile_name, profile_data in block_system.profiles.items():
                if isinstance(profile_data, (list, np.ndarray)):
                    block_system.profiles[profile_name] = profile_data[start_t:end_t]

        # Adjust component profiles
        for component in block_system.components.values():
            if hasattr(component, 'profile') and component.profile is not None:
                if isinstance(component.profile, (list, np.ndarray)):
                    component.profile = component.profile[start_t:end_t]

            # Update timestep count
            component.N = block_system.N

        return block_system

    def _set_boundary_conditions(self, block_system, start_t: int, block_idx: int):
        """Set initial conditions for a block based on previous solutions.

        Args:
            block_system: System object for this block
            start_t: Starting timestep in original horizon
            block_idx: Index of this block
        """
        # For first block, use actual initial conditions
        if block_idx == 0:
            return

        # For subsequent blocks, use ending state from previous block
        prev_block = self.block_solutions[block_idx - 1] if self.block_solutions else None

        if prev_block and self.config.warm_start:
            prev_system = prev_block['system']

            # Transfer storage states
            for comp_name, component in block_system.components.items():
                if component.type == "storage":
                    prev_comp = prev_system.components.get(comp_name)
                    if prev_comp and hasattr(prev_comp, 'E'):
                        # Use final storage level from previous block
                        if isinstance(prev_comp.E, np.ndarray):
                            component.E_init = prev_comp.E[-1]
                        elif hasattr(prev_comp, 'E_opt') and prev_comp.E_opt is not None:
                            if hasattr(prev_comp.E_opt, 'value'):
                                component.E_init = prev_comp.E_opt.value[-1]

                        logger.debug(f"Set initial storage for {comp_name}: {component.E_init}")

        # Alternative: use baseline solution if available
        elif self.baseline_solution and self.config.warm_start:
            # Use baseline values at start_t
            for comp_name, component in block_system.components.items():
                if component.type == "storage":
                    baseline_comp = self.system.components.get(comp_name)
                    if baseline_comp and hasattr(baseline_comp, 'E'):
                        if isinstance(baseline_comp.E, np.ndarray) and start_t < len(baseline_comp.E):
                            component.E_init = baseline_comp.E[start_t]

    def _optimize_block(self, block_system, block_idx: int) -> SolverResult:
        """Optimize a single block using MILP.

        Args:
            block_system: System for this block
            block_idx: Block index

        Returns:
            Solver result for this block
        """
        # Configure MILP solver for this block
        milp_config = SolverConfig(
            verbose=False,
            solver_specific={'objective': 'min_cost'}
        )

        # Create MILP solver for this block
        block_milp = MILPSolver(block_system, milp_config)

        # Solve the block
        block_result = block_milp.solve()

        return block_result

    def _stitch_solutions(self):
        """Combine block solutions into a complete solution."""
        if not self.block_solutions:
            logger.error("No block solutions to stitch")
            return

        # Initialize storage for complete solution
        N = self.system.N

        # Process each component
        for comp_name, component in self.system.components.items():
            if component.type == "storage":
                # Initialize storage trajectory
                E_complete = np.zeros(N + 1)
                P_charge_complete = np.zeros(N)
                P_discharge_complete = np.zeros(N)

                # Fill in values from each block
                for block_data in self.block_solutions:
                    start_t = block_data['start_t']
                    end_t = block_data['end_t']
                    block_system = block_data['system']
                    block_comp = block_system.components.get(comp_name)

                    if block_comp:
                        # Extract storage levels
                        if hasattr(block_comp, 'E') and isinstance(block_comp.E, np.ndarray):
                            # Copy non-overlapping portion
                            actual_end = min(start_t + self.config.block_size_hours, end_t)
                            block_size = actual_end - start_t
                            E_complete[start_t:actual_end] = block_comp.E[:block_size]

                        # Extract charge/discharge
                        if hasattr(block_comp, 'P_charge'):
                            actual_end = min(start_t + self.config.block_size_hours, end_t)
                            block_size = actual_end - start_t
                            P_charge_complete[start_t:actual_end] = block_comp.P_charge[:block_size]

                        if hasattr(block_comp, 'P_discharge'):
                            actual_end = min(start_t + self.config.block_size_hours, end_t)
                            block_size = actual_end - start_t
                            P_discharge_complete[start_t:actual_end] = block_comp.P_discharge[:block_size]

                # Store stitched solution
                component.E = E_complete[:N]
                component.P_charge = P_charge_complete
                component.P_discharge = P_discharge_complete

            elif component.type in ["generation", "transmission", "consumption"]:
                # Similar stitching for other component types
                # This would be expanded based on component-specific variables
                pass

        logger.info("Solution stitching complete")

    def _apply_final_solution(self):
        """Apply the final stitched solution to the system."""
        # The solution is already stored in component attributes
        # This method could perform additional post-processing if needed
        pass

    def _store_baseline_values(self):
        """Store baseline solution values for warm-starting."""
        # Store rule-based solution for reference
        # This helps with warm-starting MILP blocks
        for component in self.system.components.values():
            if hasattr(component, 'E') and component.E is not None:
                # Storage values already in component.E from rule-based solver
                logger.debug(f"Stored baseline for {component.name}")

    def extract_results(self):
        """Extract and format results from the rolling horizon solution."""
        # Results are already applied in _stitch_solutions
        logger.info("Rolling horizon results extracted")

    def get_solver_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics about the rolling horizon solve.

        Returns:
            Dictionary with solver statistics
        """
        stats = {
            'total_blocks': len(self.block_solutions),
            'block_size_hours': self.config.block_size_hours,
            'overlap_hours': self.config.overlap_hours,
            'baseline_status': self.baseline_solution.status if self.baseline_solution else None,
            'block_statuses': [b['result'].status for b in self.block_solutions],
            'total_solve_time': self.result.solve_time if self.result else None,
            'warm_start_used': self.config.warm_start
        }

        # Add per-block timing
        if self.block_solutions:
            block_times = [b['result'].solve_time for b in self.block_solutions]
            stats['block_solve_times'] = block_times
            stats['avg_block_time'] = np.mean(block_times)
            stats['max_block_time'] = np.max(block_times)

        return stats