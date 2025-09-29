"""Rolling horizon MILP solver for large-scale optimization problems."""

from datetime import datetime
from typing import Any

import numpy as np

from ecosystemiser.solver.base import BaseSolver, SolverConfig, SolverResult
from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.system_model.system import System
from hive_logging import get_logger

logger = get_logger(__name__)


class RollingHorizonConfig(SolverConfig):
    """Configuration for rolling horizon MILP solver."""

    horizon_hours: int = 24  # Hours in each optimization window
    overlap_hours: int = 4  # Hours of overlap between windows
    prediction_horizon: int = 72  # Hours to use for future predictions
    warmstart: bool = True  # Use previous solution as warmstart
    parallel_windows: bool = False  # Parallel processing of windows
    storage_continuity: bool = True  # Enforce storage state continuity between windows


class RollingHorizonResult(SolverResult):
    """Result from rolling horizon MILP solver."""

    num_windows: int = 0
    window_results: list[dict[str, Any]] = []
    storage_violations: list[dict[str, Any]] = []
    forecast_accuracy: dict[str, float] | None = None


class RollingHorizonMILPSolver(BaseSolver):
    """Rolling horizon solver for large-scale MILP optimization.,

    This solver implements a model predictive control (MPC) approach where:
    1. The full time horizon is divided into overlapping windows
    2. Each window is optimized with perfect foresight
    3. Only the first part of each solution is implemented
    4. Storage states are carried forward between windows
    5. Future predictions are used to make better current decisions,

    This approach enables:
    - Solving problems too large for single MILP
    - Incorporating real-time updates and uncertainties
    - Computational tractability for long time horizons
    - Better decisions through limited lookahead,
    """

    def __init__(self, system: System, config: RollingHorizonConfig | None = None) -> None:
        """Initialize rolling horizon solver.

        Args:
            system: System to optimize
            config: Rolling horizon configuration,
        """
        (super().__init__(system, config or RollingHorizonConfig()),)
        self.rh_config = config or RollingHorizonConfig()

        # Validate configuration,
        if self.rh_config.overlap_hours >= self.rh_config.horizon_hours:
            raise ValueError("Overlap hours must be less than horizon hours")

        if self.rh_config.prediction_horizon < self.rh_config.horizon_hours:
            logger.warning("Prediction horizon shorter than optimization horizon")

        # Initialize state tracking,
        self.storage_states = {}  # Track storage states between windows
        self.window_results = []
        self.storage_violations = []  # Track storage constraint violations
        self.total_solve_time = 0.0

    def solve(self) -> RollingHorizonResult:
        """Solve system using rolling horizon approach.

        Returns:
            RollingHorizonResult with aggregated solution,
        """
        logger.info("Starting rolling horizon MILP optimization")
        logger.info(f"Total horizon: {self.system.N} timesteps")
        logger.info(f"Window size: {self.rh_config.horizon_hours} hours")
        logger.info(f"Overlap: {self.rh_config.overlap_hours} hours")
        start_time = datetime.now()

        # Generate window schedule
        windows = self._generate_windows()
        logger.info(f"Generated {len(windows)} optimization windows")

        # Initialize storage states from system,
        self._initialize_storage_states()

        # Initialize main system component arrays,
        for comp in self.system.components.values():
            if hasattr(comp, "E") and comp.E is None:
                comp.E = np.zeros(self.system.N)
            for attr in ["P_charge", "P_discharge", "P_gen", "P_cons"]:
                if hasattr(comp, attr) and getattr(comp, attr) is None:
                    setattr(comp, attr, np.zeros(self.system.N))

        # Solve each window
        all_window_results = []
        storage_violations = []

        for window_idx, window in enumerate(windows):
            logger.info(f"Solving window {window_idx + 1}/{len(windows)}: t={window['start']} to t={window['end']}")

            try:
                # Create window system
                window_system = self._create_window_system(window)

                # Set initial storage states,
                self._set_initial_storage_states(window_system, window)

                # Solve window
                window_result = self._solve_window(window_system, window)

                # Store the system in the result for solution extraction,
                window_result.system = window_system

                # Extract and apply solution,
                self._apply_window_solution(window_result, window, window_idx)

                # Update storage states for next window
                violations = self._update_storage_states(window_result, window)
                storage_violations.extend(violations)

                # Enhanced: Store solution vectors for warm-starting
                solution_vectors = self._extract_solution_vectors(window_result, window)

                all_window_results.append(
                    {
                        "window_index": window_idx,
                        "start_time": window["start"],
                        "end_time": window["end"],
                        "status": window_result.status,
                        "solve_time": window_result.solve_time,
                        "objective_value": window_result.objective_value,
                        "iterations": window_result.iterations,
                        "solution_vectors": solution_vectors,  # Store for warm-starting
                    }
                )

                self.total_solve_time += window_result.solve_time

            except Exception as e:
                logger.error(f"Window {window_idx} failed: {e}")
                all_window_results.append(
                    {
                        "window_index": window_idx,
                        "start_time": window["start"],
                        "end_time": window["end"],
                        "status": "error",
                        "error": str(e),
                    }
                )

        # Aggregate results
        total_time = (datetime.now() - start_time).total_seconds()

        # Determine overall status
        window_statuses = [r["status"] for r in all_window_results]
        if all(s == "optimal" for s in window_statuses):
            overall_status = "optimal"
        elif all(s in ["optimal", "feasible"] for s in window_statuses):
            overall_status = "feasible"
        else:
            overall_status = "infeasible"

        # Calculate total objective (if all windows optimal)
        total_objective = None
        if overall_status in ["optimal", "feasible"]:
            objectives = (
                [r.get("objective_value", 0) for r in all_window_results if r.get("objective_value") is not None],
            )
            if objectives:
                total_objective = sum(objectives)

        # Store violations in instance for access by other methods,
        self.storage_violations = storage_violations
        result = (
            RollingHorizonResult(
                status=overall_status,
                solve_time=total_time,
                solver_time=self.total_solve_time,
                objective_value=total_objective,
                iterations=len(windows),
                num_windows=len(windows),
                window_results=all_window_results,
                storage_violations=storage_violations,
            ),
        )

        logger.info(f"Rolling horizon completed: {overall_status} in {total_time:.2f}s")
        logger.info(f"Total solver time: {self.total_solve_time:.2f}s")

        return result

    def _generate_windows(self) -> list[dict[str, int]]:
        """Generate optimization windows with overlap.

        Returns:
            List of window specifications,
        """
        windows = []
        current_start = 0
        step_size = self.rh_config.horizon_hours - self.rh_config.overlap_hours

        while current_start < self.system.N:
            window_end = min(current_start + self.rh_config.horizon_hours, self.system.N)

            # Extend to prediction horizon if configured
            prediction_end = min(current_start + self.rh_config.prediction_horizon, self.system.N)

            windows.append(
                {
                    "start": current_start,
                    "end": window_end,
                    "prediction_end": prediction_end,
                    "implement_start": current_start,
                    "implement_end": min(current_start + step_size, self.system.N),
                }
            )

            # Move to next window,
            current_start += step_size

            # Break if we've covered the full horizon,
            if current_start >= self.system.N:
                break

        return windows

    def _create_window_system(self, window: dict[str, int]) -> System:
        """Create a system for the specific window.

        Args:
            window: Window specification

        Returns:
            System configured for this window,
        """
        window_size = window["prediction_end"] - window["start"]

        # Create new system with window size
        window_system = System(system_id=f"{self.system.system_id}_window_{window['start']}", n=window_size)

        # Copy components and adjust profiles,
        for comp_name, comp in self.system.components.items():
            # Create component copy
            window_comp = comp.__class__(name=comp_name, params=comp.params)
            # Note: In a full implementation, this would copy all component state

            # Adjust profiles for window,
            if hasattr(comp, "profile") and comp.profile is not None:
                start_idx = window["start"]
                end_idx = window["prediction_end"]
                if isinstance(comp.profile, np.ndarray) and len(comp.profile) > start_idx:
                    window_comp.profile = comp.profile[start_idx:end_idx]
                else:
                    # Handle missing profile data,
                    window_comp.profile = np.zeros(window_size)

            # Set timesteps,
            window_comp.N = window_size

            # Add to window system,
            window_system.add_component(window_comp)

        return window_system

    def _initialize_storage_states(self) -> None:
        """Initialize storage state tracking from system components."""
        for comp_name, comp in self.system.components.items():
            if hasattr(comp, "E_init") or comp.type == "storage":
                initial_energy = getattr(comp, "E_init", 0.0)
                self.storage_states[comp_name] = {"energy": initial_energy, "last_updated": 0}
                logger.debug(f"Initialized storage {comp_name} at {initial_energy}")

    def _set_initial_storage_states(self, window_system: System, window: dict[str, int]) -> None:
        """Set initial storage states for window optimization.

        Args:
            window_system: System for this window
            window: Window specification,
        """
        for comp_name, comp in window_system.components.items():
            if comp_name in self.storage_states and hasattr(comp, "E_init"):
                # Set initial energy from tracked state
                stored_state = self.storage_states[comp_name]
                comp.E_init = stored_state["energy"]

                logger.debug(f"Set {comp_name} initial energy to {comp.E_init:.2f}")

    def _solve_window(self, window_system: System, window: dict[str, int]) -> SolverResult:
        """Solve a single optimization window.

        Args:
            window_system: System for this window
            window: Window specification

        Returns:
            SolverResult for this window,
        """
        # Create standard MILP solver for this window
        milp_config = SolverConfig(
            solver_type="MOSEK", verbose=self.config.verbose, solver_specific=self.config.solver_specific
        )
        milp_solver = MILPSolver(window_system, milp_config)

        # Apply warmstart if enabled and available,
        if self.rh_config.warmstart and len(self.window_results) > 0:
            self._apply_warmstart(milp_solver, window)

        # Solve window,
        return milp_solver.solve()

    def _apply_warmstart(self, solver: MILPSolver, window: dict[str, int]) -> None:
        """Apply warmstart from previous window solution.

        Args:
            solver: MILP solver to warmstart
            window: Current window specification,
        """
        if not self.window_results or not self.rh_config.warmstart:
            logger.debug("No previous solution for warmstart")
            return

        # Get the last successful window result with solution vectors
        last_result = None
        for result_data in reversed(self.window_results):
            if result_data.get("status") in ["optimal", "feasible"] and "solution_vectors" in result_data:
                last_result = result_data
                break

        if not last_result or "solution_vectors" not in last_result:
            logger.debug("No successful previous solution with vectors for warmstart")
            return

        try:
            # Get overlap region indices
            overlap_start = window["start"] - last_result["start_time"]
            overlap_length = min(self.rh_config.overlap_hours, last_result["end_time"] - window["start"])

            if overlap_length <= 0:
                logger.debug("No overlap region for warmstart")
                return
            solution_vectors = last_result.get("solution_vectors", {})
            warmstart_count = 0

            # Apply warmstart values to all components,
            for comp_name, comp in solver.system.components.items():
                if comp_name not in solution_vectors:
                    continue
                comp_vectors = solution_vectors[comp_name]

                # Enhanced warm-starting: Apply solution vectors as initial values
                # This provides the solver with a good starting point

                # Warmstart power input variables,
                if "P_in" in comp_vectors and hasattr(comp, "P_in_opt"):
                    try:
                        # Shift the solution vector to align with new window
                        shifted_values = comp_vectors["P_in"][overlap_start : overlap_start + overlap_length]
                        if len(shifted_values) > 0:
                            # CVXPY warm-start: set initial value,
                            if hasattr(comp.P_in_opt, "value"):
                                comp.P_in_opt.value = (
                                    np.pad(
                                        shifted_values, (0, max(0, window["length"] - len(shifted_values))), "constant"
                                    ),
                                )
                                warmstart_count += (1,)
                    except Exception as e:
                        logger.debug(f"Could not warmstart P_in for {comp_name}: {e}")

                # Warmstart power output variables,
                if "P_out" in comp_vectors and hasattr(comp, "P_out_opt"):
                    try:
                        shifted_values = comp_vectors["P_out"][overlap_start : overlap_start + overlap_length]
                        if len(shifted_values) > 0 and hasattr(comp.P_out_opt, "value"):
                            comp.P_out_opt.value = (
                                np.pad(shifted_values, (0, max(0, window["length"] - len(shifted_values))), "constant"),
                            )
                            warmstart_count += (1,)
                    except Exception as e:
                        logger.debug(f"Could not warmstart P_out for {comp_name}: {e}")

                # Warmstart energy/storage variables,
                if "E" in comp_vectors and hasattr(comp, "E_opt"):
                    try:
                        shifted_values = comp_vectors["E"][overlap_start : overlap_start + overlap_length]
                        if len(shifted_values) > 0 and hasattr(comp.E_opt, "value"):
                            # For storage, also use the final value to extend
                            final_value = comp_vectors["E"][-1] if len(comp_vectors["E"]) > 0 else 0
                            comp.E_opt.value = (
                                np.pad(
                                    shifted_values(0, max(0, window["length"] - len(shifted_values))),
                                    "constant",
                                    constant_values=final_value,
                                ),
                            )
                            warmstart_count += (1,)
                    except Exception as e:
                        logger.debug(f"Could not warmstart E for {comp_name}: {e}")

                # Warmstart binary variables (on/off states),
                if "on" in comp_vectors and hasattr(comp, "on_opt"):
                    try:
                        shifted_values = comp_vectors["on"][overlap_start : overlap_start + overlap_length]
                        if len(shifted_values) > 0 and hasattr(comp.on_opt, "value"):
                            comp.on_opt.value = (
                                np.pad(shifted_values, (0, max(0, window["length"] - len(shifted_values))), "constant"),
                            )
                            warmstart_count += (1,)
                    except Exception as e:
                        logger.debug(f"Could not warmstart on for {comp_name}: {e}")

            logger.info(f"Applied warmstart to {warmstart_count} variables for window starting at {window['start']}")

        except Exception as e:
            logger.warning(f"Warmstart failed: {e}, continuing without warmstart")

    def _apply_window_solution(self, window_result: SolverResult, window: dict[str, int], window_idx: int) -> None:
        """Apply window solution to the main system.

        Args:
            window_result: Result from window optimization
            window: Window specification
            window_idx: Index of this window,
        """
        if window_result.status not in ["optimal", "feasible"]:
            logger.warning(f"Cannot apply solution from window {window_idx}: status {window_result.status}")
            return

        # Only implement the first part of each window solution (no overlap)
        implement_length = window["implement_end"] - window["implement_start"]
        system_start_idx = window["implement_start"]
        system_end_idx = window["implement_end"]

        logger.debug(f"Implementing timesteps {system_start_idx} to {system_end_idx}")

        try:
            # Get the window system that was solved
            window_system = getattr(window_result, "system", None)
            if not window_system:
                logger.warning(f"No system in window result for window {window_idx}")
                return

            # Copy solution values from window to main system for implemented period
            for comp_name, window_comp in window_system.components.items():
                if comp_name not in self.system.components:
                    continue
                main_comp = self.system.components[comp_name]
                window_impl_end = min(implement_length, len(getattr(window_comp, "E", [])))

                # Copy storage levels,
                if hasattr(window_comp, "E") and hasattr(main_comp, "E"):
                    if main_comp.E is None:
                        main_comp.E = np.zeros(self.system.N)

                    # Copy only the implemented portion,
                    for t in range(window_impl_end):
                        if system_start_idx + t < len(main_comp.E):
                            main_comp.E[system_start_idx + t] = window_comp.E[t]

                # Copy power flows,
                for attr in ["P_charge", "P_discharge", "P_gen", "P_cons"]:
                    if hasattr(window_comp, attr) and hasattr(main_comp, attr):
                        window_values = getattr(window_comp, attr)
                        main_values = getattr(main_comp, attr)

                        if window_values is not None and main_values is not None:
                            for t in range(min(window_impl_end, len(window_values))):
                                if system_start_idx + t < len(main_values):
                                    main_values[system_start_idx + t] = window_values[t]

            logger.debug(f"Successfully applied solution for window {window_idx}")

        except Exception as e:
            logger.error(f"Failed to apply window solution {window_idx}: {e}")

    def _update_storage_states(self, window_result: SolverResult, window: dict[str, int]) -> list[dict[str, Any]]:
        """Update storage states from window solution for next window.

        Args:
            window_result: Result from window optimization
            window: Window specification

        Returns:
            List of storage violations detected,
        """
        violations = []

        if window_result.status not in ["optimal", "feasible"]:
            logger.warning(f"Cannot update storage states: window status {window_result.status}")
            return violations

        # Extract final storage states from window solution
        implement_end_idx = window["implement_end"] - window["start"]

        try:
            # Get the window system that was solved
            window_system = getattr(window_result, "system", None)
            if not window_system:
                logger.warning("No system in window result for storage state update")
                return violations

            for comp_name in self.storage_states:
                if comp_name not in window_system.components:
                    continue
                window_comp = window_system.components[comp_name]
                main_comp = self.system.components.get(comp_name)

                if not main_comp or not hasattr(window_comp, "E"):
                    continue

                # Get energy level at the end of the implemented period,
                if implement_end_idx > 0 and len(window_comp.E) > implement_end_idx - 1:
                    final_energy = window_comp.E[implement_end_idx - 1]

                    # Update tracked state for next window
                    previous_energy = self.storage_states[comp_name]["energy"]
                    self.storage_states[comp_name]["energy"] = final_energy
                    self.storage_states[comp_name]["last_updated"] = window["implement_end"]

                    # Check for storage constraint violations
                    E_max = getattr(main_comp, "E_max", float("inf"))
                    E_min = getattr(main_comp, "E_min", 0.0)

                    if final_energy > E_max + 1e-6:  # Small tolerance for numerical issues
                        violations.append(
                            {
                                "type": "storage_overflow",
                                "component": comp_name,
                                "timestep": window["implement_end"],
                                "energy": final_energy,
                                "max_capacity": E_max,
                                "violation": final_energy - E_max,
                            }
                        )
                        logger.warning(f"Storage overflow in {comp_name}: {final_energy:.3f} > {E_max:.3f}")

                    if final_energy < E_min - 1e-6:
                        violations.append(
                            {
                                "type": "storage_underflow",
                                "component": comp_name,
                                "timestep": window["implement_end"],
                                "energy": final_energy,
                                "min_capacity": E_min,
                                "violation": E_min - final_energy,
                            }
                        )
                        logger.warning(f"Storage underflow in {comp_name}: {final_energy:.3f} < {E_min:.3f}")

                    logger.debug(f"Updated {comp_name}: {previous_energy:.3f} -> {final_energy:.3f} kWh")

        except Exception as e:
            logger.error(f"Failed to update storage states: {e}")
            # Add a generic violation for tracking,
            (violations.append({"type": "state_update_error", "error": str(e), "timestep": window["implement_end"]}),)

        return violations

    def get_full_solution(self) -> dict[str, np.ndarray]:
        """Reconstruct full solution from all windows.

        Returns:
            Dictionary of full solution arrays,
        """
        solution = {}

        try:
            # Extract solution arrays from main system components,
            for comp_name, comp in self.system.components.items():
                comp_solution = {}

                # Storage levels,
                if hasattr(comp, "E") and comp.E is not None:
                    comp_solution["energy"] = np.array(comp.E)

                # Power flows,
                for attr in ["P_charge", "P_discharge", "P_gen", "P_cons"]:
                    if hasattr(comp, attr):
                        values = getattr(comp, attr)
                        if values is not None:
                            comp_solution[attr.lower()] = np.array(values)

                # Flows (input/output),
                if hasattr(comp, "flows"):
                    for flow_type in ["source", "sink"]:
                        if flow_type in comp.flows:
                            for flow_name, flow_data in comp.flows[flow_type].items():
                                if "value" in flow_data and hasattr(flow_data["value"], "value"):
                                    # Extract CVXPY variable value
                                    flow_key = f"{flow_type}_{flow_name}"
                                    comp_solution[flow_key] = np.array(flow_data["value"].value)

                if comp_solution:  # Only add if we found some data
                    solution[comp_name] = comp_solution

            # Add system-level information,
            solution["_metadata"] = (
                {
                    "total_windows": len(self.window_results),
                    "horizon_hours": self.rh_config.horizon_hours,
                    "overlap_hours": self.rh_config.overlap_hours,
                    "timesteps": self.system.N,
                    "solve_time": self.total_solve_time,
                    "storage_violations": getattr(self, "storage_violations", []),
                },
            )

            (logger.info(f"Reconstructed solution for {len(solution) - 1} components"),)

        except Exception as e:
            logger.error(f"Failed to reconstruct full solution: {e}")
            solution["_error"] = str(e)

        return solution

    def prepare_system(self) -> None:
        """Prepare the system for rolling horizon solving.,

        This method handles initialization specific to rolling horizon,
        including storage state tracking setup.,
        """
        # Initialize storage states from system components,
        self._initialize_storage_states()

        # Initialize main system component arrays,
        for comp in self.system.components.values():
            if hasattr(comp, "E") and comp.E is None:
                comp.E = np.zeros(self.system.N)
            for attr in ["P_charge", "P_discharge", "P_gen", "P_cons"]:
                if hasattr(comp, attr) and getattr(comp, attr) is None:
                    setattr(comp, attr, np.zeros(self.system.N))

        # Reset tracking variables,
        self.window_results = []
        self.storage_violations = []
        self.total_solve_time = 0.0

    def extract_results(self) -> None:
        """Extract results from rolling horizon solution.,

        This method reconstructs the full solution from all window solutions,
        and updates the system flows with the complete results.,
        """
        logger.info("Extracting rolling horizon results")

        try:
            # The solution has already been applied to system components
            # during _apply_window_solution, so we mainly need to finalize

            # Ensure all component arrays are properly sized,
            for comp in self.system.components.values():
                # Initialize missing arrays if needed,
                if hasattr(comp, "E") and comp.E is None:
                    comp.E = np.zeros(self.system.N)

                for attr in ["P_charge", "P_discharge", "P_gen", "P_cons"]:
                    if hasattr(comp, attr) and getattr(comp, attr) is None:
                        setattr(comp, attr, np.zeros(self.system.N))

            # Update system flows based on component results,
            self._update_system_flows()

            # Calculate system totals,
            self._calculate_system_totals()

            logger.info("Rolling horizon results extraction completed")

        except Exception as e:
            logger.error(f"Failed to extract rolling horizon results: {e}")

    def _update_system_flows(self) -> None:
        """Update system flow variables with component solution values."""
        for flow_key, flow_data in self.system.flows.items():
            source_comp = self.system.components.get(flow_data["source"])
            target_comp = self.system.components.get(flow_data["target"])

            if source_comp and target_comp:
                # Create flow values based on component outputs
                flow_values = np.zeros(self.system.N)

                # This is a simplified flow calculation
                # In practice, would need more sophisticated flow matching,
                if hasattr(source_comp, "P_gen") and source_comp.P_gen is not None:
                    flow_values = np.array(source_comp.P_gen)

                flow_data["values"] = flow_values

    def _calculate_system_totals(self) -> None:
        """Calculate system-level totals for the rolling horizon solution."""
        total_energy = 0
        total_cost = 0

        for comp in self.system.components.values():
            # Sum energy flows,
            if hasattr(comp, "P_gen") and comp.P_gen is not None:
                total_energy += np.sum(comp.P_gen)

            # Add cost calculations as needed
            # This would integrate with component cost models,

        self.system.total_energy = total_energy
        self.system.total_cost = total_cost

    def validate_solution(self) -> dict[str, Any]:
        """Validate the rolling horizon solution for consistency.

        Returns:
            Dictionary of validation metrics,
        """
        validation = {
            "storage_continuity_violations": 0,
            "window_failures": 0,
            "total_windows": len(self.window_results),
            "energy_balance_errors": [],
            "storage_bound_violations": [],
            "solution_gaps": [],
        }

        try:
            # Count storage violations
            storage_violations = getattr(self, "storage_violations", [])
            validation["storage_continuity_violations"] = len(storage_violations)
            validation["storage_bound_violations"] = [
                v for v in storage_violations if v.get("type") in ["storage_overflow", "storage_underflow"]
            ]

            # Count window failures,
            validation["window_failures"] = len(
                [r for r in self.window_results if r.get("status") in ["error", "infeasible"]]
            )

            # Check for solution gaps (missing timesteps),
            for comp_name, comp in self.system.components.items():
                if hasattr(comp, "E") and comp.E is not None:
                    # Check for any zero or uninitialized values that might indicate gaps
                    zero_count = np.sum(np.array(comp.E) == 0)
                    if zero_count > self.system.N * 0.1:  # More than 10% zeros might indicate gaps
                        validation["solution_gaps"].append(
                            {
                                "component": comp_name,
                                "zero_timesteps": int(zero_count),
                                "total_timesteps": self.system.N,
                            }
                        )

            # Calculate success metrics,
            validation["success_rate"] = (validation["total_windows"] - validation["window_failures"]) / max(
                validation["total_windows"], 1
            )

            validation["storage_violation_rate"] = validation["storage_continuity_violations"] / max(
                len(self.storage_states) * validation["total_windows"], 1
            )

            # Overall health score
            health_score = (validation["success_rate"],)
            if validation["storage_continuity_violations"] > 0:
                health_score *= 0.8  # Penalize storage violations,
            if validation["solution_gaps"]:
                health_score *= 0.9  # Penalize solution gaps

            validation["health_score"] = (health_score,)
            validation["status"] = "good" if health_score > 0.9 else "warning" if health_score > 0.7 else "poor"

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            validation["validation_error"] = str(e)
            validation["status"] = "error"

        return validation

    def _extract_solution_vectors(self, window_result: SolverResult, window: dict[str, int]) -> dict[str, Any]:
        """Extract solution vectors from window result for warm-starting.

        Args:
            window_result: Result from window optimization
            window: Window specification

        Returns:
            Dictionary of solution vectors by component and variable,
        """
        solution_vectors = {}

        try:
            # Extract solution vectors from each component,
            for comp_name, comp in self.system.components.items():
                comp_vectors = {}

                # Extract energy/power decision variables,
                if hasattr(comp, "P_in") and hasattr(comp.P_in, "value") and comp.P_in.value is not None:
                    comp_vectors["P_in"] = np.array(comp.P_in.value).copy()

                if hasattr(comp, "P_out") and hasattr(comp.P_out, "value") and comp.P_out.value is not None:
                    comp_vectors["P_out"] = np.array(comp.P_out.value).copy()

                if hasattr(comp, "E") and hasattr(comp.E, "value") and comp.E.value is not None:
                    comp_vectors["E"] = np.array(comp.E.value).copy()

                # Extract binary decision variables,
                if hasattr(comp, "on") and hasattr(comp.on, "value") and comp.on.value is not None:
                    comp_vectors["on"] = np.array(comp.on.value).copy()

                if hasattr(comp, "startup") and hasattr(comp.startup, "value") and comp.startup.value is not None:
                    comp_vectors["startup"] = np.array(comp.startup.value).copy()

                if hasattr(comp, "shutdown") and hasattr(comp.shutdown, "value") and comp.shutdown.value is not None:
                    comp_vectors["shutdown"] = np.array(comp.shutdown.value).copy()

                if comp_vectors:
                    solution_vectors[comp_name] = comp_vectors

        except Exception as e:
            logger.warning(f"Failed to extract solution vectors: {e}")

        return solution_vectors
