"""Power demand component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import DemandTechnicalParams, FidelityLevel

logger = logging.getLogger(__name__)


# =============================================================================
# POWER DEMAND-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class PowerDemandTechnicalParams(DemandTechnicalParams):
    """Power demand-specific technical parameters extending demand archetype.

    This model inherits from DemandTechnicalParams and adds electricity-specific
    parameters for different fidelity levels.
    """
    # STANDARD fidelity additions
    power_factor: Optional[float] = Field(
        0.95,
        description="Power factor for the load"
    )

    # DETAILED fidelity parameters
    demand_flexibility: Optional[Dict[str, float]] = Field(
        None,
        description="Demand response capabilities {shift_capacity_kw, shed_capacity_kw}"
    )

    # RESEARCH fidelity parameters
    stochastic_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Stochastic demand model parameters"
    )
    occupancy_coupling: Optional[Dict[str, Any]] = Field(
        None,
        description="Coupling to occupancy patterns"
    )


class PowerDemandParams(ComponentParams):
    """Power demand parameters using the hierarchical technical parameter system.

    Profile data should be provided separately through the system's
    profile loading mechanism, not as a component parameter.
    """
    technical: PowerDemandTechnicalParams = Field(
        default_factory=lambda: PowerDemandTechnicalParams(
            peak_demand=5.0,  # Default 5 kW peak
            load_profile_type="variable",
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("PowerDemand")
class PowerDemand(Component):
    """Power demand (consumption) component with CVXPY optimization support."""

    PARAMS_MODEL = PowerDemandParams

    def _post_init(self):
        """Initialize power demand-specific attributes from technical parameters.

        Profile data is now loaded separately by the system, not from parameters.
        """
        self.type = "consumption"
        self.medium = "electricity"

        # Single source of truth: the technical parameter block
        tech = self.technical

        # Core parameters extracted from technical block
        self.P_max = tech.peak_demand  # kW

        # Store advanced parameters for fidelity-aware constraints
        self.power_factor = tech.power_factor
        self.demand_flexibility = tech.demand_flexibility

        # EXPLICIT FIDELITY CONTROL
        self.fidelity_level = tech.fidelity_level

        # Profile should be assigned by the system/builder
        if not hasattr(self, 'profile') or self.profile is None:
            logger.warning(f"No demand profile assigned to {self.name}. Using zero demand.")
            self.profile = np.zeros(getattr(self, 'N', 24))
        else:
            self.profile = np.array(self.profile)

        # CVXPY variable (created later by add_optimization_vars)
        self.P_in = None

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        # For demand, input is fixed by profile (unless flexible)
        self.P_in = cp.Variable(N, name=f'{self.name}_P_in', nonneg=True)

        # Add as flow
        self.flows['sink']['P_in'] = {
            'type': 'electricity',
            'value': self.P_in,
            'profile': self.profile
        }

    def rule_based_demand(self, t: int) -> float:
        """Rule-based demand at timestep t.

        Returns the actual power demand in kW.
        Profile is normalized (0-1), multiply by P_max for actual demand.
        """
        if not hasattr(self, 'profile') or self.profile is None or t >= len(self.profile):
            return 0.0

        # Return normalized profile * P_max
        return self.profile[t] * self.P_max

    def set_constraints(self) -> List:
        """Set CVXPY constraints for power demand with fidelity-aware modeling.

        Constraint complexity scales with fidelity level:
        - SIMPLE: Demand must be met exactly
        - STANDARD: Add power factor considerations
        - DETAILED: Add demand flexibility (DR capabilities)
        - RESEARCH: Stochastic demand modeling
        """
        constraints = []

        if self.P_in is not None:
            # Get fidelity level
            fidelity = getattr(self, 'fidelity_level', FidelityLevel.STANDARD)

            # --- SIMPLE MODEL (OG Systemiser baseline) ---
            # Fixed demand: P_in = profile * P_max (demand must be met exactly)
            demand_min = self.profile * self.P_max
            demand_max = self.profile * self.P_max

            # --- STANDARD ENHANCEMENTS (additive on top of SIMPLE) ---
            if fidelity >= FidelityLevel.STANDARD:
                # Power factor considerations would be added here
                if self.power_factor is not None:
                    logger.debug("STANDARD: Power factor considerations would modify demand bounds")
                    # In practice: demand bounds might be adjusted for reactive power
                    # For now, STANDARD maintains exact demand satisfaction

            # --- DETAILED ENHANCEMENTS (additive on top of STANDARD) ---
            if fidelity >= FidelityLevel.DETAILED:
                # Demand response flexibility
                if self.demand_flexibility is not None:
                    # Allow demand response within limits
                    shift_cap = self.demand_flexibility.get('shift_capacity_kw', 0)
                    shed_cap = self.demand_flexibility.get('shed_capacity_kw', 0)

                    # Modify demand bounds to allow flexibility
                    demand_min = self.profile * self.P_max - shed_cap
                    demand_max = self.profile * self.P_max + shift_cap
                    logger.debug("DETAILED: Added demand response flexibility")

            # --- RESEARCH ENHANCEMENTS (additive on top of DETAILED) ---
            if fidelity >= FidelityLevel.RESEARCH:
                logger.debug("RESEARCH: Stochastic demand modeling would modify demand bounds")
                # In practice: demand_min/max = apply_stochastic_model(demand_min, demand_max)

            # Apply demand constraints with all fidelity enhancements
            if np.array_equal(demand_min, demand_max):
                # Exact demand satisfaction (SIMPLE and STANDARD)
                constraints.append(self.P_in == demand_max)
            else:
                # Flexible demand bounds (DETAILED and RESEARCH)
                constraints.append(self.P_in >= demand_min)
                constraints.append(self.P_in <= demand_max)

        return constraints

    def rule_based_demand(self, t: int) -> float:
        """Get power demand in rule-based mode."""
        if t >= len(self.profile):
            return 0.0
        return self.profile[t] * self.P_max