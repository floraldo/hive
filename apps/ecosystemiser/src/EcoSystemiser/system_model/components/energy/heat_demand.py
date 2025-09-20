"""Heat demand component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class HeatDemandParams(BaseModel):
    """Heat demand parameters."""
    H_profile: List[float] = Field(..., description="Heat demand profile [kW]")
    H_max: Optional[float] = Field(None, description="Maximum heat demand [kW]")


class HeatDemand:
    """Heat demand component representing thermal energy consumption."""

    def __init__(self, name: str, params: HeatDemandParams):
        """Initialize heat demand with profile."""
        self.name = name
        self.type = "consumption"
        self.medium = "heat"
        self.params = params

        # Extract parameters
        self.H_profile = np.array(params.H_profile)
        self.H_max = params.H_max or max(self.H_profile)

        # Initialize flows structure
        self.flows = {
            'sink': {},    # Incoming heat
            'source': {},  # No output
            'input': {},   # All inputs
            'output': {}   # All outputs
        }

        # CVXPY variables (created later by add_optimization_vars)
        self.H_in = None

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        self.H_in = cp.Variable(N, name=f'{self.name}_H_in', nonneg=True)

        # Add as sink flow
        self.flows['sink']['H_in'] = {
            'type': 'heat',
            'value': self.H_in
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for heat demand."""
        constraints = []
        N = self.H_in.shape[0] if self.H_in is not None else 0

        if self.H_in is not None:
            for t in range(N):
                # Heat demand must be satisfied
                if t < len(self.H_profile):
                    constraints.append(self.H_in[t] == self.H_profile[t])
                else:
                    # If profile is shorter than N, use last value
                    constraints.append(self.H_in[t] == self.H_profile[-1])

        return constraints

    def rule_based_consumption(self, t: int) -> float:
        """Get heat demand at time t for rule-based operation."""
        if t < len(self.H_profile):
            return self.H_profile[t]
        else:
            return self.H_profile[-1]