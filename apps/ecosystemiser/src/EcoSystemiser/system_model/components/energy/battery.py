"""Battery energy storage component with enhanced parameter handling."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, Dict
from ..shared.component import Component, ComponentParams

class BatteryTechnicalParams(BaseModel):
    """Technical parameters specific to batteries."""
    P_max: float = Field(..., description="Maximum charge/discharge power (kW)")
    E_max: float = Field(..., description="Maximum energy capacity (kWh)")
    E_init: float = Field(..., description="Initial state of charge (kWh)")
    eta: float = Field(0.95, description="Round-trip efficiency (0-1)")
    eta_charge: Optional[float] = None
    eta_discharge: Optional[float] = None
    soc_min: float = Field(0.1, description="Minimum SoC (fraction)")
    soc_max: float = Field(0.9, description="Maximum SoC (fraction)")
    degradation_rate: float = Field(0.0002, description="Degradation per cycle")

class BatteryParams(ComponentParams):
    """Complete parameter set for Battery component."""
    technical: BatteryTechnicalParams

class Battery(Component):
    """Battery energy storage system component with cleaner parameter access."""

    def __init__(self, name: str, params: BatteryParams, n: int = 24):
        """Initialize battery with validated parameters.

        Args:
            name: Battery identifier
            params: BatteryParams with technical, economic, environmental data
            n: Number of timesteps
        """
        super().__init__(name, params, n)
        self.type = "storage"
        self.medium = "electricity"

        # Now we can access parameters cleanly via self.technical
        # No need to manually unpack everything
        # Calculate derived efficiencies if not specified
        if self.technical.eta_charge is None:
            self.technical.eta_charge = np.sqrt(self.technical.eta)
        if self.technical.eta_discharge is None:
            self.technical.eta_discharge = np.sqrt(self.technical.eta)

        # Storage level array (numpy for rule-based, cvxpy for optimization)
        self.E = np.zeros(n)
        self.E[0] = self.technical.E_init

        # For optimization mode (keeping cvxpy coupling for now per Plan B)
        self.E_opt = None  # Will be initialized in add_optimization_vars()

    @property
    def P_max(self):
        """Convenience property for maximum power."""
        return self.technical.P_max

    @property
    def E_max(self):
        """Convenience property for maximum energy."""
        return self.technical.E_max

    @property
    def E_init(self):
        """Convenience property for initial energy."""
        return self.technical.E_init

    @property
    def eta(self):
        """Convenience property for round-trip efficiency."""
        return self.technical.eta

    @property
    def eta_charge(self):
        """Convenience property for charge efficiency."""
        return self.technical.eta_charge

    @property
    def eta_discharge(self):
        """Convenience property for discharge efficiency."""
        return self.technical.eta_discharge

    def add_optimization_vars(self):
        """Initialize CVXPY variables for optimization mode."""
        if self.E_opt is None:
            self.E_opt = cp.Variable(self.N, nonneg=True, name=f'{self.name}_E')

    def set_constraints(self):
        """Define battery operational constraints for optimization."""
        constraints = []

        # Only add constraints if optimization variables exist
        if self.E_opt is not None:
            # Energy capacity constraints
            constraints.append(self.E_opt >= self.technical.soc_min * self.technical.E_max)
            constraints.append(self.E_opt <= self.technical.soc_max * self.technical.E_max)

            # Initial state constraint
            constraints.append(self.E_opt[0] == self.technical.E_init)

            # Energy balance constraints for each timestep
            for t in range(1, self.N):
                charge_flow = 0
                discharge_flow = 0

                # Sum charging flows
                for flow_name, flow in self.flows.get('input', {}).items():
                    if isinstance(flow['value'], cp.Variable):
                        charge_flow += flow['value'][t] * self.technical.eta_charge

                for flow_name, flow in self.flows.get('sink', {}).items():
                    if isinstance(flow['value'], cp.Variable):
                        charge_flow += flow['value'][t] * self.technical.eta_charge

                # Sum discharging flows
                for flow_name, flow in self.flows.get('output', {}).items():
                    if isinstance(flow['value'], cp.Variable):
                        discharge_flow += flow['value'][t] / self.technical.eta_discharge

                for flow_name, flow in self.flows.get('source', {}).items():
                    if isinstance(flow['value'], cp.Variable):
                        discharge_flow += flow['value'][t] / self.technical.eta_discharge

                # Energy balance: E[t] = E[t-1] + charge - discharge
                constraints.append(
                    self.E_opt[t] == self.E_opt[t-1] + charge_flow - discharge_flow
                )

        return constraints

    def get_state_at_timestep(self, t: int) -> Dict[str, float]:
        """Get battery state at specific timestep.

        Args:
            t: Timestep index

        Returns:
            Dictionary with battery state information
        """
        state = super().get_state_at_timestep(t)

        # Add battery-specific state
        if t < len(self.E):
            state['energy_level'] = float(self.E[t])
            state['soc'] = float(self.E[t] / self.technical.E_max)

        state['max_charge_power'] = float(self.technical.P_max)
        state['max_discharge_power'] = float(self.technical.P_max)

        return state