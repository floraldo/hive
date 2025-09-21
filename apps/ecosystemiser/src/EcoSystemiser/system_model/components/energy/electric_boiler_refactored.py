"""Electric boiler component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from ..shared.registry import register_component
from ..shared.component_base import Component

logger = logging.getLogger(__name__)


class ElectricBoilerParams(BaseModel):
    """Electric boiler parameters matching original Systemiser."""
    eta: float = Field(0.95, description="Conversion efficiency")
    P_max: Optional[float] = Field(None, description="Max electrical power input [kW]")


@register_component("ElectricBoiler")
class ElectricBoiler(Component):
    """Electric boiler that converts electricity directly to heat."""

    PARAMS_MODEL = ElectricBoilerParams

    def _post_init(self):
        """Initialize electric boiler-specific attributes after DRY parameter unpacking."""
        self.type = "generation"
        self.medium = "heat"

        # Initialize flows structure
        self.flows = {
            'source': {},  # Heat output
            'sink': {},    # Electricity input
            'input': {},   # All inputs
            'output': {}   # All outputs
        }

        # CVXPY variables (created later by add_optimization_vars)
        self.P_heat = None
        self.P_elec = None

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        self.P_heat = cp.Variable(N, name=f'{self.name}_P_heat', nonneg=True)
        self.P_elec = cp.Variable(N, name=f'{self.name}_P_elec', nonneg=True)

        # Add flows
        self.flows['source']['P_heat'] = {
            'type': 'heat',
            'value': self.P_heat
        }
        self.flows['sink']['P_elec'] = {
            'type': 'electricity',
            'value': self.P_elec
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for electric boiler operation."""
        constraints = []
        N = self.P_heat.shape[0] if self.P_heat is not None else 0

        if self.P_heat is not None and self.P_elec is not None:
            for t in range(N):
                # Heat output is eta times the electrical input
                constraints.append(
                    self.P_heat[t] == self.eta * self.P_elec[t]
                )

                # Power limit constraint
                if self.P_max is not None:
                    constraints.append(self.P_elec[t] <= self.P_max)

        return constraints

    def rule_based_operation(self, heat_demand: float, t: int) -> tuple:
        """Rule-based electric boiler operation.

        Returns:
            (heat_output, electricity_input)
        """
        if heat_demand <= 0:
            return 0.0, 0.0

        # Calculate required electricity input
        elec_required = heat_demand / self.eta

        # Apply power limit
        if self.P_max is not None:
            elec_required = min(elec_required, self.P_max)

        # Calculate actual heat output
        heat_output = elec_required * self.eta

        return heat_output, elec_required