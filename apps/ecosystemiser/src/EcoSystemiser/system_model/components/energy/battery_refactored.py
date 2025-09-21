"""Battery component with MILP optimization support - Refactored with Registry Pattern.

This module implements the Battery energy storage component using the
self-registering pattern for plug-and-play extensibility.
"""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from ..shared.component_base import Component
from ..shared.registry import register_component

logger = logging.getLogger(__name__)


class BatteryParams(BaseModel):
    """Battery parameters matching original Systemiser."""
    P_max: float = Field(5.0, description="Max charge/discharge power [kW]")
    E_max: float = Field(10.0, description="Storage capacity [kWh]")
    E_init: float = Field(5.0, description="Initial energy [kWh]")
    eta_charge: float = Field(0.95, description="Charge efficiency")
    eta_discharge: float = Field(0.95, description="Discharge efficiency")


@register_component("Battery")  # Self-registering component!
class Battery(Component):
    """Battery storage component with CVXPY optimization support.

    This component is now DRY - parameter unpacking is handled by the base class.
    """

    # Declare the parameter model for this component
    PARAMS_MODEL = BatteryParams

    def _post_init(self):
        """Component-specific initialization (no parameter unpacking needed!)."""
        # Set component metadata
        self.type = "storage"
        self.medium = "electricity"

        # Calculate derived values (parameters already unpacked as attributes)
        # The base class has already set self.P_max, self.E_max, etc.
        self.eta = self.eta_charge  # Use charge efficiency as base

        # Initialize solver-specific attributes
        self.E = None  # Storage array for rule-based solver

        # CVXPY variables (created later by add_optimization_vars)
        self.E_opt = None
        self.P_cha = None
        self.P_dis = None

        logger.debug(f"Battery {self.name} initialized: P_max={self.P_max}, E_max={self.E_max}")

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        self.E_opt = cp.Variable(N, name=f'{self.name}_E', nonneg=True)
        self.P_cha = cp.Variable(N, name=f'{self.name}_P_cha', nonneg=True)
        self.P_dis = cp.Variable(N, name=f'{self.name}_P_dis', nonneg=True)

        # Add charge/discharge as flows
        self.flows['sink']['P_cha'] = {
            'type': 'electricity',
            'value': self.P_cha
        }
        self.flows['source']['P_dis'] = {
            'type': 'electricity',
            'value': self.P_dis
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for battery operation.

        Battery energy balance from original Systemiser:
        E[t+1] = E[t] + η*(P_cha[t] - P_dis[t])

        This matches the original equation exactly for numerical equivalence.
        """
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

            # Energy balance dynamics (matching original Systemiser exactly)
            for t in range(1, N):
                constraints.append(
                    self.E_opt[t] == self.E_opt[t-1] +
                    self.eta * (self.P_cha[t] - self.P_dis[t])
                )

        return constraints

    def rule_based_charge(self, power: float, t: int) -> float:
        """Charge battery in rule-based mode."""
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
        """Discharge battery in rule-based mode."""
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