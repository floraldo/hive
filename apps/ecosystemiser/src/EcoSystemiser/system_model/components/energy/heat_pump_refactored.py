"""Heat pump component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from ..shared.registry import register_component
from ..shared.component_base import Component

logger = logging.getLogger(__name__)


class HeatPumpParams(BaseModel):
    """Heat pump parameters matching original Systemiser."""
    COP: float = Field(3.5, description="Coefficient of Performance")
    eta: float = Field(0.90, description="Pump efficiency")
    P_max: Optional[float] = Field(None, description="Max electrical power input [kW]")


@register_component("HeatPump")
class HeatPump(Component):
    """Heat pump component that converts electricity to heat with COP amplification."""

    PARAMS_MODEL = HeatPumpParams

    def _post_init(self):
        """Initialize heat pump-specific attributes after DRY parameter unpacking."""
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
        self.P_heatsource = None
        self.P_loss = None
        self.P_pump = None

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        self.P_heatsource = cp.Variable(N, name=f'{self.name}_P_heatsource', nonneg=True)
        self.P_loss = cp.Variable(N, name=f'{self.name}_P_loss', nonneg=True)
        self.P_pump = cp.Variable(N, name=f'{self.name}_P_pump', nonneg=True)

        # Add flows
        self.flows['source']['P_heatsource'] = {
            'type': 'heat',
            'value': self.P_heatsource
        }
        self.flows['sink']['P_loss'] = {
            'type': 'electricity',
            'value': self.P_loss
        }
        self.flows['sink']['P_pump'] = {
            'type': 'electricity',
            'value': self.P_pump
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for heat pump operation - matching original Systemiser exactly."""
        constraints = []
        N = self.P_heatsource.shape[0] if self.P_heatsource is not None else 0

        if self.P_heatsource is not None:
            for t in range(N):
                # Calculate input_flows exactly as in original Systemiser
                # This sums all flows in the 'input' dict
                input_flows = cp.sum([
                    flow['value'][t] for flow_name, flow in self.flows.get('input', {}).items()
                    if isinstance(flow.get('value'), cp.Variable)
                ])

                # If no input flows exist yet, create a default one
                if not self.flows.get('input'):
                    if not hasattr(self, 'P_elec_default'):
                        self.P_elec_default = cp.Variable(N, name=f'{self.name}_P_elec', nonneg=True)
                        self.flows['input'] = {
                            'P_elec': {'type': 'electricity', 'value': self.P_elec_default}
                        }
                    input_flows = self.P_elec_default[t]

                # Heat pump produces (COP - 1) times more heat than electricity input
                # This is the exact equation from original Systemiser
                constraints.append(
                    self.P_heatsource[t] == (self.COP - 1) * input_flows
                )
                constraints.append(
                    self.P_loss[t] == input_flows * (1 - self.eta)
                )
                constraints.append(
                    self.P_pump[t] == input_flows * self.eta
                )

                # Power limit constraint
                if self.P_max is not None:
                    constraints.append(input_flows <= self.P_max)

        return constraints

    def rule_based_operation(self, heat_demand: float, t: int) -> tuple:
        """Rule-based heat pump operation.

        Returns:
            (heat_output, electricity_input)
        """
        if heat_demand <= 0:
            return 0.0, 0.0

        # Calculate required electricity input
        elec_required = heat_demand / self.COP

        # Apply power limit
        if self.P_max is not None:
            elec_required = min(elec_required, self.P_max)

        # Calculate actual heat output
        heat_output = elec_required * self.COP

        return heat_output, elec_required