"""Power demand component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class PowerDemandParams(BaseModel):
    """Power demand parameters matching original Systemiser."""
    P_profile: List[float] = Field(..., description="Demand profile [kW]")
    P_max: float = Field(5.0, description="Maximum power demand [kW]")


class PowerDemand:
    """Power demand (consumption) component with CVXPY optimization support."""

    def __init__(self, name: str, params: PowerDemandParams):
        """Initialize power demand matching original Systemiser structure."""
        self.name = name
        self.type = "consumption"
        self.medium = "electricity"
        self.params = params

        # Extract parameters
        self.P_max = params.P_max
        self.profile = np.array(params.P_profile)

        # Initialize flows structure
        self.flows = {
            'sink': {},    # Demand input
            'input': {}    # All inputs
        }

        # CVXPY variable (created later by add_optimization_vars)
        self.P_in = None

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        # For demand, input is fixed by profile
        self.P_in = cp.Variable(N, name=f'{self.name}_P_in', nonneg=True)

        # Add as flow
        self.flows['sink']['P_in'] = {
            'type': 'electricity',
            'value': self.P_in,
            'profile': self.profile
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for power demand."""
        constraints = []

        if self.P_in is not None:
            # Demand must be met exactly
            constraints.append(self.P_in == self.profile * self.P_max)

        return constraints

    def rule_based_demand(self, t: int) -> float:
        """Get power demand in rule-based mode."""
        if t >= len(self.profile):
            return 0.0
        return self.profile[t] * self.P_max