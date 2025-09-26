"""Heat pump component with MILP optimization support and hierarchical fidelity."""
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
# HEAT PUMP-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class HeatPumpTechnicalParams(GenerationTechnicalParams):
    """Heat pump-specific technical parameters extending generation archetype.

    This model inherits from GenerationTechnicalParams and adds heat pump-specific
    parameters for different fidelity levels.
    """
    # Core heat pump parameters
    cop_nominal: float = Field(3.5, description="Nominal Coefficient of Performance")
    technology: str = Field("air_to_water", description="Heat pump technology type")

    # STANDARD fidelity additions
    cop_temperature_curve: Optional[Dict[str, float]] = Field(
        None,
        description="COP variation with temperature {slope, intercept}"
    )
    defrost_power_penalty: Optional[float] = Field(
        None,
        description="Power penalty during defrost cycles [%]"
    )

    # DETAILED fidelity parameters
    refrigerant_type: Optional[str] = Field(
        None,
        description="Refrigerant type (R410A, R32, etc.)"
    )
    compressor_map: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed compressor performance map"
    )
    heat_exchanger_effectiveness: Optional[float] = Field(
        None,
        description="Heat exchanger effectiveness"
    )

    # RESEARCH fidelity parameters
    detailed_refrigerant_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed refrigerant cycle modeling parameters"
    )
    control_algorithm: Optional[Dict[str, Any]] = Field(
        None,
        description="Advanced control algorithm parameters"
    )


class HeatPumpParams(ComponentParams):
    """Heat pump parameters using the hierarchical technical parameter system.

    COP and capacity are now specified through the technical parameter block,
    following the archetype inheritance pattern.
    """
    technical: HeatPumpTechnicalParams = Field(
        default_factory=lambda: HeatPumpTechnicalParams(
            capacity_nominal=10.0,  # Default 10 kW heat output
            efficiency_nominal=0.90,  # Pump electrical efficiency
            cop_nominal=3.5,  # Default COP
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("HeatPump")
class HeatPump(Component):
    """Heat pump component that converts electricity to heat with COP amplification."""

    PARAMS_MODEL = HeatPumpParams

    def _post_init(self):
        """Initialize heat pump-specific attributes from technical parameters.

        All parameters are now sourced from the technical parameter block,
        following the single source of truth principle.
        """
        self.type = "generation"
        self.medium = "heat"

        # Single source of truth: the technical parameter block
        tech = self.technical

        # Core parameters extracted from technical block
        self.P_max = tech.capacity_nominal  # kW heat output capacity
        self.COP = tech.cop_nominal
        self.eta = tech.efficiency_nominal  # Electrical efficiency

        # Maximum electrical input (derived from heat capacity and COP)
        self.P_max_elec = self.P_max / self.COP if self.COP > 0 else 0

        # Store advanced parameters for fidelity-aware constraints
        self.technology = tech.technology
        self.cop_temperature_curve = tech.cop_temperature_curve
        self.defrost_power_penalty = tech.defrost_power_penalty
        self.refrigerant_type = tech.refrigerant_type
        self.compressor_map = tech.compressor_map
        self.heat_exchanger_effectiveness = tech.heat_exchanger_effectiveness

        # EXPLICIT FIDELITY CONTROL
        self.fidelity_level = tech.fidelity_level

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
        """Set CVXPY constraints for heat pump with fidelity-aware modeling.

        Constraint complexity scales with fidelity level:
        - SIMPLE: Fixed COP, basic energy balance
        - STANDARD: Temperature-dependent COP, defrost penalties
        - DETAILED: Compressor maps, heat exchanger modeling
        - RESEARCH: Full refrigerant cycle modeling
        """
        constraints = []
        N = self.P_heatsource.shape[0] if self.P_heatsource is not None else 0

        if self.P_heatsource is not None:
            # Get fidelity level
            fidelity = getattr(self, 'fidelity_level', FidelityLevel.STANDARD)

            for t in range(N):
                # Calculate input_flows exactly as in original Systemiser
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

                # --- SIMPLE MODEL (OG Systemiser baseline) ---
                # Fixed COP heat pump: P_heat = COP * P_elec
                effective_cop = self.COP

                # --- STANDARD ENHANCEMENTS (additive on top of SIMPLE) ---
                if fidelity >= FidelityLevel.STANDARD:
                    # Temperature-dependent COP curves
                    if self.cop_temperature_curve and hasattr(self, 'system'):
                        if hasattr(self.system, 'profiles') and 'ambient_temperature' in self.system.profiles:
                            temp = self.system.profiles['ambient_temperature'][t] if t < len(self.system.profiles['ambient_temperature']) else 20
                            # COP = baseline + slope * (T_ambient - T_reference)
                            slope = self.cop_temperature_curve.get('slope', 0)
                            # For CVXPY, we need to handle this as a parameter
                            temp_factor = 1 + slope * (temp - 7) / 100  # Reference temp = 7°C
                            effective_cop = self.COP * max(0.5, temp_factor)  # Minimum COP = 50%
                            logger.debug("STANDARD: Applied temperature-dependent COP to heat pump")

                    # Defrost penalties
                    if self.defrost_power_penalty:
                        # Simplified defrost model - reduce effective COP
                        defrost_factor = 1 - self.defrost_power_penalty / 100
                        effective_cop = effective_cop * defrost_factor
                        logger.debug("STANDARD: Applied defrost penalty to heat pump")

                # --- DETAILED ENHANCEMENTS (additive on top of STANDARD) ---
                if fidelity >= FidelityLevel.DETAILED:
                    # Compressor maps for part-load efficiency
                    if self.compressor_map is not None:
                        logger.debug("DETAILED: Compressor map would modify effective COP")
                        # In practice: effective_cop = apply_compressor_map(effective_cop, input_flows)

                    # Heat exchanger effectiveness
                    if self.heat_exchanger_effectiveness is not None:
                        # Heat exchanger losses would reduce effective COP
                        effective_cop = effective_cop * self.heat_exchanger_effectiveness
                        logger.debug("DETAILED: Applied heat exchanger effectiveness to heat pump")

                # --- RESEARCH ENHANCEMENTS (additive on top of DETAILED) ---
                if fidelity >= FidelityLevel.RESEARCH:
                    logger.debug("RESEARCH: Full refrigerant cycle modeling would modify effective COP")
                    # In practice: effective_cop = apply_refrigerant_cycle_model(effective_cop, conditions)

                # Heat pump energy balance
                constraints.append(
                    self.P_heatsource[t] == effective_cop * input_flows
                )
                constraints.append(
                    self.P_loss[t] == input_flows * (1 - self.eta)
                )
                constraints.append(
                    self.P_pump[t] == input_flows * self.eta
                )

                # Power limit constraint (electrical input limit)
                constraints.append(input_flows <= self.P_max_elec)


        return constraints

    def rule_based_operation(self, heat_demand: float, t: int) -> tuple:
        """Rule-based heat pump operation with fidelity-aware performance."""
        if heat_demand <= 0:
            return 0.0, 0.0

        # Determine effective COP (similar logic as constraints)
        effective_cop = self.COP

        # Apply temperature effects if available
        if self.cop_temperature_curve and hasattr(self, 'system'):
            if hasattr(self.system, 'profiles') and 'ambient_temperature' in self.system.profiles:
                temp = self.system.profiles['ambient_temperature'][t] if t < len(self.system.profiles['ambient_temperature']) else 20
                slope = self.cop_temperature_curve.get('slope', 0)
                temp_factor = 1 + slope * (temp - 7) / 100
                effective_cop = self.COP * max(0.5, temp_factor)

        # Calculate required electricity input
        elec_required = heat_demand / effective_cop

        # Apply electrical power limit
        elec_required = min(elec_required, self.P_max_elec)

        # Calculate actual heat output
        heat_output = elec_required * effective_cop

        return heat_output, elec_required