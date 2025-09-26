"""Electric boiler component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import GenerationTechnicalParams, FidelityLevel

logger = logging.getLogger(__name__)


# =============================================================================
# ELECTRIC BOILER-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class ElectricBoilerTechnicalParams(GenerationTechnicalParams):
    """Electric boiler-specific technical parameters extending generation archetype.

    This model inherits from GenerationTechnicalParams and adds electric boiler-specific
    parameters for different fidelity levels.
    """
    # Electric boiler parameters
    heating_element_type: str = Field("resistance", description="Type of heating element")
    temperature_setpoint: Optional[float] = Field(
        None,
        description="Operating temperature setpoint [°C]"
    )

    # STANDARD fidelity additions
    thermal_inertia: Optional[float] = Field(
        None,
        description="Thermal mass and inertia factor"
    )
    modulation_range: Optional[Dict[str, float]] = Field(
        None,
        description="Power modulation capability {min_power, max_power}"
    )

    # DETAILED fidelity parameters
    heat_exchanger_effectiveness: Optional[float] = Field(
        None,
        description="Heat exchanger effectiveness"
    )
    control_algorithm: Optional[Dict[str, Any]] = Field(
        None,
        description="Control algorithm parameters"
    )

    # RESEARCH fidelity parameters
    detailed_thermal_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed thermal modeling parameters"
    )
    emissions_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed emissions modeling"
    )


class ElectricBoilerParams(ComponentParams):
    """Electric boiler parameters using the hierarchical technical parameter system.

    Efficiency and capacity are now specified through the technical parameter block,
    following the archetype inheritance pattern.
    """
    technical: ElectricBoilerTechnicalParams = Field(
        default_factory=lambda: ElectricBoilerTechnicalParams(
            capacity_nominal=10.0,  # Default 10 kW heat output
            efficiency_nominal=0.95,  # Default 95% efficiency
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("ElectricBoiler")
class ElectricBoiler(Component):
    """Electric boiler that converts electricity directly to heat."""

    PARAMS_MODEL = ElectricBoilerParams

    def _post_init(self):
        """Initialize electric boiler-specific attributes from technical parameters.

        All parameters are now sourced from the technical parameter block,
        following the single source of truth principle.
        """
        self.type = "generation"
        self.medium = "heat"

        # Single source of truth: the technical parameter block
        tech = self.technical

        # Core parameters extracted from technical block
        self.P_max = tech.capacity_nominal  # kW heat output capacity
        self.eta = tech.efficiency_nominal  # Electrical to thermal conversion efficiency

        # Maximum electrical input (same as heat output for electric boiler)
        self.P_max_elec = self.P_max / self.eta if self.eta > 0 else 0

        # Store advanced parameters for fidelity-aware constraints
        self.heating_element_type = tech.heating_element_type
        self.temperature_setpoint = tech.temperature_setpoint
        self.thermal_inertia = tech.thermal_inertia
        self.modulation_range = tech.modulation_range
        self.heat_exchanger_effectiveness = tech.heat_exchanger_effectiveness
        self.control_algorithm = tech.control_algorithm

        # EXPLICIT FIDELITY CONTROL
        self.fidelity_level = tech.fidelity_level

        # CVXPY variables (created later by add_optimization_vars)
        self.P_heat = None
        self.P_elec = None

    def add_optimization_vars(self, N: Optional[int] = None):
        """Create CVXPY optimization variables."""
        if N is None:
            N = self.N

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
        """Set CVXPY constraints for electric boiler with fidelity-aware modeling.

        Constraint complexity scales with fidelity level:
        - SIMPLE: Direct electrical to thermal conversion
        - STANDARD: Add thermal inertia and modulation constraints
        - DETAILED: Add heat exchanger effectiveness and control dynamics
        - RESEARCH: Full thermal modeling and emissions tracking
        """
        constraints = []
        N = self.P_heat.shape[0] if self.P_heat is not None else 0

        if self.P_heat is not None and self.P_elec is not None:
            # Get fidelity level
            fidelity = getattr(self, 'fidelity_level', FidelityLevel.STANDARD)

            # Power limits (always active)
            constraints.append(self.P_elec <= self.P_max_elec)
            constraints.append(self.P_heat <= self.P_max)

            # STANDARD: Add modulation constraints (binary variables must be created once)
            if fidelity >= FidelityLevel.STANDARD and self.modulation_range:
                min_power = self.modulation_range.get('min_power', 0) * self.P_max
                max_power = self.modulation_range.get('max_power', 1) * self.P_max

                # Binary variable for on/off state
                self._boiler_state = cp.Variable(N, boolean=True, name=f'{self.name}_state')

                # Modulation constraints for all timesteps
                constraints.append(self.P_heat >= min_power * self._boiler_state)
                constraints.append(self.P_heat <= max_power * self._boiler_state)
                logger.debug("STANDARD: Applied modulation constraints to boiler")

            # Energy conversion constraints with progressive enhancement
            for t in range(N):
                # --- SIMPLE MODEL (OG Systemiser baseline) ---
                # Direct electrical to thermal conversion: P_heat = eta * P_elec
                effective_efficiency = self.eta

                # --- STANDARD ENHANCEMENTS (additive on top of SIMPLE) ---
                if fidelity >= FidelityLevel.STANDARD:
                    # Heat exchanger effectiveness
                    if self.heat_exchanger_effectiveness is not None:
                        effective_efficiency = self.eta * self.heat_exchanger_effectiveness
                        logger.debug("STANDARD: Applied heat exchanger effectiveness to boiler")

                # --- DETAILED ENHANCEMENTS (additive on top of STANDARD) ---
                if fidelity >= FidelityLevel.DETAILED:
                    # Control algorithm would modify efficiency here
                    if self.control_algorithm:
                        logger.debug("DETAILED: Control algorithm would modify effective efficiency")
                        # In practice: effective_efficiency = apply_control_algorithm(effective_efficiency)

                # --- RESEARCH ENHANCEMENTS (additive on top of DETAILED) ---
                if fidelity >= FidelityLevel.RESEARCH:
                    logger.debug("RESEARCH: Full thermal modeling would modify effective efficiency")
                    # In practice: effective_efficiency = apply_thermal_model(effective_efficiency)

                # Apply the energy conversion constraint with all fidelity enhancements
                constraints.append(self.P_heat[t] == effective_efficiency * self.P_elec[t])

                # DETAILED: Add thermal inertia constraints (ramp rate limits)
                if fidelity >= FidelityLevel.DETAILED and self.thermal_inertia and t > 0:
                    # Rate of change constraint based on thermal inertia
                    max_ramp = self.P_max * self.thermal_inertia  # Simplified ramp rate
                    constraints.append(self.P_heat[t] - self.P_heat[t-1] <= max_ramp)
                    constraints.append(self.P_heat[t-1] - self.P_heat[t] <= max_ramp)
                    logger.debug("DETAILED: Applied thermal inertia constraints to boiler")

        return constraints

    def rule_based_operation(self, heat_demand: float, t: int) -> tuple:
        """Rule-based electric boiler operation with fidelity-aware performance.

        Returns:
            (heat_output, electricity_input)
        """
        if heat_demand <= 0:
            return 0.0, 0.0

        # Determine effective efficiency (similar logic as constraints)
        effective_efficiency = self.eta

        # Apply heat exchanger effectiveness if available
        if self.heat_exchanger_effectiveness is not None:
            effective_efficiency = self.eta * self.heat_exchanger_effectiveness

        # Calculate required electricity input
        elec_required = heat_demand / effective_efficiency

        # Apply electrical power limit
        elec_required = min(elec_required, self.P_max_elec)

        # Apply heat output limit
        heat_output = min(elec_required * effective_efficiency, self.P_max)

        # Apply modulation constraints in rule-based mode
        if self.modulation_range:
            min_power = self.modulation_range.get('min_power', 0) * self.P_max
            if heat_output > 0 and heat_output < min_power:
                # Either off or at minimum power
                heat_output = min_power if heat_demand >= min_power else 0.0
                elec_required = heat_output / effective_efficiency if heat_output > 0 else 0.0

        return heat_output, elec_required