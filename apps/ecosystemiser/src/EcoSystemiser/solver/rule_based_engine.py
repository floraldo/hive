"""Rule-based solver for system simulation."""
import numpy as np
import time
import logging
from typing import Dict, Any
from .base import BaseSolver, SolverResult

logger = logging.getLogger(__name__)

class RuleBasedEngine(BaseSolver):
    """Rule-based control solver using priority-based dispatch."""

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
            if not isinstance(flow_data['value'], np.ndarray):
                flow_data['value'] = np.zeros(self.system.N)
            else:
                flow_data['value'].fill(0.0)

        # Initialize storage arrays
        for comp in self.system.components.values():
            if comp.type == "storage":
                if not hasattr(comp, 'E') or not isinstance(comp.E, np.ndarray):
                    comp.E = np.zeros(self.system.N)
                comp.E[0] = getattr(comp, 'E_init', 0.0)

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
                message="Rule-based solution completed"
            )

        except Exception as e:
            logger.error(f"Error in rule-based solver: {e}")
            result = SolverResult(
                status="error",
                solve_time=time.time() - start_time,
                message=str(e)
            )

        self.result = result
        return result

    def _solve_timestep(self, t: int):
        """Solve a single timestep using priority dispatch."""
        # Get system state
        state = self._get_system_state(t)

        # Sort flows by priority
        sorted_flow_keys = sorted(
            self.system.flows.keys(),
            key=lambda k: self._get_priority(
                self.system.components[self.system.flows[k]['source']].type,
                self.system.components[self.system.flows[k]['target']].type
            )
        )

        # Process flows in priority order
        for flow_key in sorted_flow_keys:
            flow_data = self.system.flows[flow_key]
            from_name = flow_data['source']
            to_name = flow_data['target']

            # Get available and required amounts from state
            available = state[from_name]['available_output']
            required = state[to_name]['required_input']

            # Determine actual flow
            flow_amount = min(available, required)

            if flow_amount > 1e-6:
                # Record flow
                flow_data['value'][t] = flow_amount

                # Update state
                state[from_name]['available_output'] -= flow_amount
                state[to_name]['required_input'] -= flow_amount

                # Update storage if applicable
                self._update_storage_flow(from_name, to_name, flow_amount, t, state)

        # Finalize storage levels
        self._finalize_storage_levels(t)

    def _get_system_state(self, t: int) -> Dict[str, Dict[str, Any]]:
        """Get current state of all components."""
        state = {}

        for name, comp in self.system.components.items():
            comp_state = {
                'type': comp.type,
                'medium': comp.medium,
                'available_output': 0.0,
                'required_input': 0.0,
                'charge_eff': 1.0,
                'discharge_eff': 1.0
            }

            if comp.type == "generation":
                # Get generation profile value
                if hasattr(comp, 'profile'):
                    comp_state['available_output'] = comp.profile[t] if t < len(comp.profile) else 0.0
                elif hasattr(comp, 'get_generation_at_timestep'):
                    comp_state['available_output'] = comp.get_generation_at_timestep(t)

            elif comp.type == "consumption":
                # Get demand profile value
                if hasattr(comp, 'profile'):
                    comp_state['required_input'] = comp.profile[t] if t < len(comp.profile) else 0.0

            elif comp.type == "transmission":
                # Grid can both supply and consume
                comp_state['available_output'] = getattr(comp, 'P_max', float('inf'))
                comp_state['required_input'] = getattr(comp, 'P_max', float('inf'))

            elif comp.type == "storage":
                # Calculate available charge/discharge
                current_level = comp.E[t-1] if t > 0 else comp.E_init
                max_level = comp.E_max
                power_limit = getattr(comp, 'P_max', float('inf'))

                comp_state['available_output'] = min(current_level, power_limit)
                comp_state['required_input'] = min(max_level - current_level, power_limit)
                comp_state['charge_eff'] = getattr(comp, 'eta_charge', getattr(comp, 'eta', 1.0))
                comp_state['discharge_eff'] = getattr(comp, 'eta_discharge', getattr(comp, 'eta', 1.0))
                comp_state['current_level'] = current_level

            state[name] = comp_state

        return state

    def _get_priority(self, from_type: str, to_type: str) -> int:
        """Get priority for a flow between component types."""
        return self.priorities.get((from_type, to_type), 99)

    def _update_storage_flow(self, from_name: str, to_name: str, flow_amount: float,
                            t: int, state: Dict):
        """Update storage levels based on flow."""
        from_comp = self.system.components[from_name]
        to_comp = self.system.components[to_name]

        if from_comp.type == "storage":
            # Discharge from storage
            eta_discharge = state[from_name]['discharge_eff']
            energy_drawn = flow_amount / eta_discharge
            state[from_name]['current_level'] -= energy_drawn

        if to_comp.type == "storage":
            # Charge to storage
            eta_charge = state[to_name]['charge_eff']
            energy_stored = flow_amount * eta_charge
            state[to_name]['current_level'] += energy_stored

    def _finalize_storage_levels(self, t: int):
        """Update storage component E arrays after timestep."""
        for comp_name, comp in self.system.components.items():
            if comp.type == "storage":
                # Calculate net energy change from flows
                charge = sum(
                    self.system.flows[key]['value'][t]
                    for key in self.system.flows
                    if self.system.flows[key]['target'] == comp_name
                )

                discharge = sum(
                    self.system.flows[key]['value'][t]
                    for key in self.system.flows
                    if self.system.flows[key]['source'] == comp_name
                )

                # Apply efficiencies
                eta_charge = getattr(comp, 'eta_charge', getattr(comp, 'eta', 1.0))
                eta_discharge = getattr(comp, 'eta_discharge', getattr(comp, 'eta', 1.0))

                initial_level = comp.E[t-1] if t > 0 else comp.E_init
                net_change = (charge * eta_charge) - (discharge / eta_discharge)

                # Update level with bounds checking
                final_level = initial_level + net_change
                final_level = max(0, min(final_level, comp.E_max))
                comp.E[t] = final_level

                # Propagate to next timestep if not last
                if t < self.system.N - 1:
                    comp.E[t + 1] = comp.E[t]

    def extract_results(self):
        """Results are already in numpy arrays, nothing to extract."""
        pass