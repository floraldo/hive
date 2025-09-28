"""Rule-based solver for system simulation - SIMPLIFIED VERSION."""

import time
from typing import Any, Dict

import numpy as np
from ecosystemiser.solver.base import BaseSolver, SolverResult
from hive_logging import get_logger

logger = get_logger(__name__)


class RuleBasedEngine(BaseSolver):
    """Simple rule-based control solver - just a traffic cop, NO component logic."""

    def __init__(self, system, config=None):
        super().__init__(system, config)

        # Priority mapping for different flow types
        self.priorities = {
            ("generation", "consumption"): 1,
            ("generation", "storage"): 2,
            ("storage", "consumption"): 3,
            ("transmission", "consumption"): 4,
            ("generation", "transmission"): 5,
            ("storage", "transmission"): 6,
            ("transmission", "storage"): 7,
        }

    def prepare_system(self):
        """Initialize all flows and storage arrays as numpy arrays."""
        logger.info("Preparing system for rule-based solving")

        # Convert all flow values to numpy arrays
        for flow_key, flow_data in self.system.flows.items():
            if not isinstance(flow_data["value"], np.ndarray):
                flow_data["value"] = np.zeros(self.system.N)
            else:
                flow_data["value"].fill(0.0)

        # Initialize storage arrays - components handle their own state
        for comp in self.system.components.values():
            if comp.type == "storage":
                if not hasattr(comp, "E") or not isinstance(comp.E, np.ndarray):
                    # State array has N elements, E[t] = state at END of timestep t
                    comp.E = np.zeros(self.system.N)

    def solve(self) -> SolverResult:
        """Solve system using rule-based priority dispatch."""
        start_time = time.time()

        try:
            # Prepare system
            self.prepare_system()

            # Solve each timestep
            for t in range(self.system.N):
                self._solve_timestep(t)

            # Extract and validate results
            self.extract_results()
            is_valid = self.validate_solution()

            result = SolverResult(
                status="optimal" if is_valid else "feasible",
                solve_time=time.time() - start_time,
                iterations=self.system.N,
                message="Rule-based solution completed",
            )

        except Exception as e:
            logger.error(f"Error in rule-based solver: {e}")
            result = SolverResult(
                status="error", solve_time=time.time() - start_time, message=str(e)
            )

        self.result = result
        return result

    def _solve_timestep(self, t: int):
        """Solve a single timestep using priority dispatch with finalization."""
        # Get system state from components
        state = self._get_system_state(t)

        # Sort flows by priority
        sorted_flow_keys = sorted(
            self.system.flows.keys(),
            key=lambda k: self._get_priority(
                self.system.components[self.system.flows[k]["source"]].type,
                self.system.components[self.system.flows[k]["target"]].type,
            ),
        )

        # Process flows in priority order (single pass)
        for flow_key in sorted_flow_keys:
            flow_data = self.system.flows[flow_key]
            from_name = flow_data["source"]
            to_name = flow_data["target"]

            # Get available and required amounts
            available = state[from_name]["available_output"]
            required = state[to_name]["required_input"]

            # Determine actual flow
            flow_amount = min(available, required)

            if flow_amount > 1e-6:
                # Record flow
                flow_data["value"][t] = flow_amount

                # Update state tracking for next flow in priority
                state[from_name]["available_output"] -= flow_amount
                state[to_name]["required_input"] -= flow_amount

                if t == 0 and logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Flow {from_name} -> {to_name}: {flow_amount:.3f} kW")

        # After all flows are decided, finalize storage states
        # This allows simultaneous charge/discharge operations
        self._finalize_storage_levels(t)

    def _get_system_state(self, t: int) -> Dict[str, Dict[str, Any]]:
        """Get current state of all components - ASK components for their state."""
        state = {}

        for name, comp in self.system.components.items():
            comp_state = {
                "type": comp.type,
                "medium": comp.medium,
                "available_output": 0.0,
                "required_input": 0.0,
            }

            if comp.type == "generation":
                # Ask component for its generation
                if hasattr(comp, "rule_based_generate"):
                    comp_state["available_output"] = comp.rule_based_generate(t)
                elif hasattr(comp, "profile") and hasattr(comp, "P_max"):
                    # Fallback for components without the method
                    comp_state["available_output"] = (
                        comp.profile[t] * comp.P_max if t < len(comp.profile) else 0.0
                    )

            elif comp.type == "consumption":
                # Ask component for its demand
                if hasattr(comp, "rule_based_demand"):
                    comp_state["required_input"] = comp.rule_based_demand(t)
                elif hasattr(comp, "profile") and hasattr(comp, "P_max"):
                    # Fallback for components without the method
                    comp_state["required_input"] = (
                        comp.profile[t] * comp.P_max if t < len(comp.profile) else 0.0
                    )

            elif comp.type == "transmission":
                # Grid can both supply and consume
                comp_state["available_output"] = getattr(comp, "P_max", float("inf"))
                comp_state["required_input"] = getattr(comp, "P_max", float("inf"))

            elif comp.type == "storage":
                # The solver ASKS the component for its state - NO physics here!
                # Components know their own physics (efficiency, limits, etc.)

                if hasattr(comp, "get_available_discharge"):
                    comp_state["available_output"] = comp.get_available_discharge(t)
                else:
                    # Fallback for components without the method
                    comp_state["available_output"] = 0.0

                if hasattr(comp, "get_available_charge"):
                    comp_state["required_input"] = comp.get_available_charge(t)
                else:
                    # Fallback for components without the method
                    comp_state["required_input"] = 0.0

            state[name] = comp_state

        return state

    def _get_priority(self, from_type: str, to_type: str) -> int:
        """Get priority for a flow between component types."""
        return self.priorities.get((from_type, to_type), 99)

    def _finalize_storage_levels(self, t: int):
        """
        Ask storage components to update their state after all flows are decided.

        This method is the key to simultaneous charge/discharge:
        - It runs AFTER all flow decisions are made
        - It sums total charge and discharge for each storage
        - It delegates physics to the component via rule_based_update_state

        The solver knows NOTHING about eta, E_max, or energy balance equations!
        """
        for comp in self.system.components.values():
            # Check if component has the update method (duck typing)
            if hasattr(comp, "rule_based_update_state"):
                # Sum all charging flows (flows TO this component)
                total_charge = 0.0
                for flow_key, flow_data in self.system.flows.items():
                    if flow_data["target"] == comp.name:
                        total_charge += flow_data["value"][t]

                # Sum all discharging flows (flows FROM this component)
                total_discharge = 0.0
                for flow_key, flow_data in self.system.flows.items():
                    if flow_data["source"] == comp.name:
                        total_discharge += flow_data["value"][t]

                # Tell component to update itself using its OWN physics
                # The component knows about eta, E_max, etc.
                # The solver is just a messenger!
                comp.rule_based_update_state(t, total_charge, total_discharge)

    def extract_results(self):
        """Results are already in numpy arrays, nothing to extract."""
        pass

    def validate_solution(self) -> bool:
        """Basic validation of solution."""
        return True  # Components handle their own constraints
