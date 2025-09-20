"""Power demand component for electricity consumption."""
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional
from ..shared.component import Component, ComponentParams

class PowerDemandTechnicalParams(BaseModel):
    """Technical parameters for power demand."""
    P_max: float = Field(..., description="Maximum power demand (kW)")
    profile_name: str = Field(..., description="Name of demand profile to use")
    base_load: float = Field(0.0, description="Constant base load (kW)")
    demand_response_enabled: bool = Field(False, description="Enable demand response capability")
    flexibility: float = Field(0.0, description="Demand flexibility (0-1)")

class PowerDemandParams(ComponentParams):
    """Complete parameter set for PowerDemand component."""
    technical: PowerDemandTechnicalParams

class PowerDemand(Component):
    """Power demand component representing electricity consumption."""

    def __init__(self, name: str, params: PowerDemandParams, n: int = 24):
        """Initialize power demand component.

        Args:
            name: Demand component identifier
            params: PowerDemandParams with technical, economic, environmental data
            n: Number of timesteps
        """
        super().__init__(name, params, n)
        self.type = "consumption"
        self.medium = "electricity"

        # Profile will be set by SystemBuilder from loaded profiles
        self.profile = None

        # Store base load separately if specified
        self.base_load = self.technical.base_load

    @property
    def P_max(self):
        """Convenience property for maximum power."""
        return self.technical.P_max

    def get_demand_at_timestep(self, t: int) -> float:
        """Get power demand at specific timestep.

        Args:
            t: Timestep index

        Returns:
            Power demand in kW
        """
        demand = self.base_load

        if self.profile is not None and t < len(self.profile):
            demand += self.profile[t]

        # Apply maximum limit
        demand = min(demand, self.technical.P_max)

        return demand

    def set_constraints(self):
        """Define demand constraints for optimization.

        For consumption components, the main constraint is that
        input must meet demand (handled by system balance constraints).
        """
        constraints = []

        # For demand response, could add flexibility constraints here
        if self.technical.demand_response_enabled:
            # Future: Add demand response constraints
            pass

        return constraints

    def get_state_at_timestep(self, t: int) -> dict:
        """Get demand state at specific timestep.

        Args:
            t: Timestep index

        Returns:
            Dictionary with demand state information
        """
        state = super().get_state_at_timestep(t)

        # Add demand-specific state
        state['demand'] = float(self.get_demand_at_timestep(t))
        state['base_load'] = float(self.base_load)

        if self.technical.demand_response_enabled:
            state['flexibility'] = float(self.technical.flexibility)

        return state