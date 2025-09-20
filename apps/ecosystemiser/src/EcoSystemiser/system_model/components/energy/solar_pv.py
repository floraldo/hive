"""Solar PV generation component."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional
from ..shared.component import Component, ComponentParams

class SolarPVTechnicalParams(BaseModel):
    """Technical parameters for solar PV systems."""
    P_max: float = Field(..., description="Maximum power output (kW)")
    efficiency: float = Field(0.20, description="Panel efficiency (0-1)")
    degradation_rate: float = Field(0.005, description="Annual degradation rate")
    profile_name: Optional[str] = Field(None, description="Name of solar profile to use")

class SolarPVParams(ComponentParams):
    """Complete parameter set for SolarPV component."""
    technical: SolarPVTechnicalParams

class SolarPV(Component):
    """Solar photovoltaic generation component."""

    def __init__(self, name: str, params: SolarPVParams, n: int = 24, profile: Optional[np.ndarray] = None):
        super().__init__(name, params, n)
        self.type = "generation"
        self.medium = "electricity"

        # Extract technical parameters
        tech = params.technical
        self.P_max = tech.P_max
        self.efficiency = tech.efficiency
        self.degradation_rate = tech.degradation_rate

        # Set generation profile
        if profile is not None:
            self.profile = profile * self.P_max
        else:
            # Default flat profile if none provided
            self.profile = np.ones(n) * self.P_max * 0.5

        # For optimization mode
        self.P_gen = cp.Parameter(n, nonneg=True, name=f'{name}_P_gen')
        self.P_gen.value = self.profile

    def set_constraints(self):
        """Solar PV has no additional constraints beyond profile."""
        return []

    def get_generation_at_timestep(self, t: int) -> float:
        """Get solar generation at specific timestep."""
        if t < len(self.profile):
            return self.profile[t]
        return 0.0