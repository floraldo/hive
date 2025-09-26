"""Battery storage component with MILP optimization support."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import StorageTechnicalParams, FidelityLevel
from ..shared.base_classes import BaseStorageComponent

logger = logging.getLogger(__name__)


# =============================================================================
# BATTERY-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class BatteryTechnicalParams(StorageTechnicalParams):
    """Battery-specific technical parameters extending storage archetype."""

    # Battery-specific additions
    temperature_coefficient_capacity: Optional[float] = Field(
        None,
        description="Temperature coefficient for capacity (%/°C)"
    )
    temperature_coefficient_charge: Optional[float] = Field(
        None,
        description="Temperature coefficient for charging (%/°C)"
    )

    # STANDARD fidelity additions
    degradation_model: Optional[Dict[str, float]] = Field(
        None,
        description="Battery degradation model parameters"
    )

    # DETAILED fidelity parameters
    voltage_curve: Optional[Dict[str, Any]] = Field(
        None,
        description="Voltage vs SOC curve for detailed modeling"
    )

    # RESEARCH fidelity parameters
    electrochemical_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed electrochemical model parameters"
    )


class BatteryParams(ComponentParams):
    """Battery parameters using the hierarchical technical parameter system."""
    technical: BatteryTechnicalParams = Field(
        default_factory=lambda: BatteryTechnicalParams(
            capacity_nominal=10.0,  # Default 10 kWh
            max_charge_rate=5.0,    # Default 5 kW charge
            max_discharge_rate=5.0, # Default 5 kW discharge
            efficiency_roundtrip=0.95,
            initial_soc_pct=0.5,
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("Battery")
class Battery(BaseStorageComponent):
    """Battery storage component with inherited rule-based physics.

    Inherits rule_based_update_state from BaseStorageComponent for
    proper separation of concerns and DRY principle.
    """

    PARAMS_MODEL = BatteryParams

    def _post_init(self):
        """Initialize battery attributes - matching original Systemiser exactly."""
        self.type = "storage"
        self.medium = "electricity"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original Systemiser expects
        self.E_max = tech.capacity_nominal  # kWh
        self.P_max = max(tech.max_charge_rate, tech.max_discharge_rate)  # kW
        self.eta = tech.efficiency_roundtrip  # Single efficiency value
        self.E_init = tech.capacity_nominal * tech.initial_soc_pct

        # Storage array for rule-based solver
        self.E = None  # Will be initialized by solver

        # CVXPY variables (for MILP solver)
        self.E_opt = None
        self.P_cha = None
        self.P_dis = None

    # The battery inherits rule_based_update_state from BaseStorageComponent
    # This provides proper simultaneous charge/discharge capability
    # while maintaining clean separation of concerns

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables for MILP solver."""
        self.E_opt = cp.Variable(N + 1, name=f'{self.name}_energy', nonneg=True)
        self.P_cha = cp.Variable(N, name=f'{self.name}_charge', nonneg=True)
        self.P_dis = cp.Variable(N, name=f'{self.name}_discharge', nonneg=True)

        # Add flows
        self.flows['sink']['P_cha'] = {
            'type': 'electricity',
            'value': self.P_cha
        }
        self.flows['source']['P_dis'] = {
            'type': 'electricity',
            'value': self.P_dis
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for battery - matching original Systemiser."""
        constraints = []
        N = self.E_opt.shape[0] - 1 if self.E_opt is not None else 0

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

            # Energy balance - EXACTLY as original Systemiser
            for t in range(N):
                constraints.append(
                    self.E_opt[t + 1] == self.E_opt[t] +
                    self.eta * self.P_cha[t] - self.P_dis[t] / self.eta
                )

        return constraints