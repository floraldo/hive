"""Heat buffer (thermal storage) component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class HeatBufferParams(BaseModel):
    """Heat buffer parameters matching original Systemiser."""
    P_max: float = Field(5.0, description="Max charge/discharge power [kW]")
    E_max: float = Field(20.0, description="Storage capacity [kWh]")
    E_init: float = Field(10.0, description="Initial energy [kWh]")
    eta: float = Field(0.90, description="Round-trip efficiency")


class HeatBuffer:
    """Heat buffer (thermal storage) component with CVXPY optimization support."""

    def __init__(self, name: str, params: HeatBufferParams):
        """Initialize heat buffer matching original Systemiser structure."""
        self.name = name
        self.type = "storage"
        self.type2 = "heat"  # Secondary type for thermal storage
        self.medium = "heat"
        self.params = params

        # Extract parameters
        self.P_max = params.P_max
        self.E_max = params.E_max
        self.E_init = params.E_init
        self.eta = params.eta
        self.capacity = params.E_max

        # Initialize flows structure
        self.flows = {
            'sink': {},    # Incoming flows (charging)
            'source': {},  # Outgoing flows (discharging)
            'input': {},   # All inputs
            'output': {}   # All outputs
        }

        # Storage array for rule-based solver
        self.E = None  # Will be initialized by solver

        # CVXPY variables (created later by add_optimization_vars)
        self.E_opt = None
        self.P_cha = None
        self.P_dis = None

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        self.E_opt = cp.Variable(N, name=f'{self.name}_E')
        self.P_cha = cp.Variable(N, name=f'{self.name}_P_cha', nonneg=True)
        self.P_dis = cp.Variable(N, name=f'{self.name}_P_dis', nonneg=True)

        # Store as E for compatibility
        self.E = self.E_opt

        # Add charge/discharge as flows
        self.flows['sink']['P_cha'] = {
            'type': 'heat',
            'value': self.P_cha
        }
        self.flows['source']['P_dis'] = {
            'type': 'heat',
            'value': self.P_dis
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for heat buffer operation."""
        constraints = []
        N = self.E_opt.shape[0] if self.E_opt is not None else 0

        if self.E_opt is not None:
            # Initial state
            constraints.append(self.E_opt[0] == self.E_init)

            # Energy bounds
            constraints.append(self.E_opt >= 0)
            constraints.append(self.E_opt <= self.E_max)

            # Power limits
            if self.P_cha is not None:
                constraints.append(self.P_cha <= self.P_max)
            if self.P_dis is not None:
                constraints.append(self.P_dis <= self.P_max)

            # Energy balance dynamics (matching original Systemiser)
            for t in range(1, N):
                constraints.append(
                    self.E_opt[t] == self.E_opt[t-1] +
                    self.eta * (self.P_cha[t] - self.P_dis[t])
                )

        return constraints

    def rule_based_charge(self, power: float, t: int) -> float:
        """Charge heat buffer in rule-based mode."""
        if self.E is None:
            return 0.0

        # Available capacity
        available_capacity = self.E_max - self.E[t]

        # Maximum charge power considering efficiency
        max_charge = min(power, self.P_max, available_capacity / self.eta)

        # Update state
        actual_energy = max_charge * self.eta
        self.E[t+1] = self.E[t] + actual_energy if t < len(self.E)-1 else self.E[t]

        return max_charge

    def rule_based_discharge(self, power: float, t: int) -> float:
        """Discharge heat buffer in rule-based mode."""
        if self.E is None:
            return 0.0

        # Available energy
        available_energy = self.E[t]

        # Maximum discharge power considering efficiency
        max_discharge = min(power, self.P_max, available_energy * self.eta)

        # Update state
        actual_energy = max_discharge / self.eta
        self.E[t+1] = self.E[t] - actual_energy if t < len(self.E)-1 else self.E[t]

        return max_discharge