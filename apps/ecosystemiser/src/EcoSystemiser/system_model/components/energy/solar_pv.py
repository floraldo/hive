"""Solar PV component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from ..shared.registry import register_component
from ..shared.component import Component

logger = logging.getLogger(__name__)


class SolarPVParams(BaseModel):
    """Solar PV parameters matching original Systemiser."""
    P_profile: List[float] = Field(..., description="Generation profile [kW]")
    P_max: float = Field(10.0, description="Maximum power capacity [kW]")


@register_component("SolarPV")
class SolarPV(Component):
    """Solar PV generation component with CVXPY optimization support."""

    PARAMS_MODEL = SolarPVParams

    def _post_init(self):
        """Initialize solar PV-specific attributes after DRY parameter unpacking."""
        self.type = "generation"
        self.medium = "electricity"

        # DRY pattern eliminates these lines (auto-unpacked):
        # self.P_max = params.P_max
        # self.P_profile = params.P_profile

        # Convert profile to numpy array
        self.profile = np.array(self.P_profile)

        # CVXPY variable (created later by add_optimization_vars)
        self.P_out = None

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        # For solar, output is fixed by profile
        self.P_out = cp.Variable(N, name=f'{self.name}_P_out', nonneg=True)

        # Add as flow
        self.flows['source']['P_out'] = {
            'type': 'electricity',
            'value': self.P_out,
            'profile': self.profile
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for solar generation."""
        constraints = []

        if self.P_out is not None:
            # Solar output is fixed by the profile
            constraints.append(self.P_out == self.profile * self.P_max)

        return constraints

    def rule_based_generate(self, t: int) -> float:
        """Generate power in rule-based mode."""
        if t >= len(self.profile):
            return 0.0
        return self.profile[t] * self.P_max