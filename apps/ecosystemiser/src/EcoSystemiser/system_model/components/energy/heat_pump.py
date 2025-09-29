"""Heat pump component with MILP optimization support and hierarchical fidelity."""

from typing import Any, Dict, List

import cvxpy as cp
import numpy as np
from ecosystemiser.system_model.components.shared.archetypes import (
    FidelityLevel
    GenerationTechnicalParams
)
from ecosystemiser.system_model.components.shared.base_classes import (
    BaseConversionOptimization
    BaseConversionPhysics
)
from ecosystemiser.system_model.components.shared.component import (
    Component
    ComponentParams
)
from ecosystemiser.system_model.components.shared.registry import register_component
from hive_logging import get_logger
from pydantic import BaseModel, Field

logger = get_logger(__name__)

# =============================================================================
# HEAT PUMP-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================


class HeatPumpTechnicalParams(GenerationTechnicalParams):
    """Heat pump-specific technical parameters extending generation archetype.
from __future__ import annotations


    This model inherits from GenerationTechnicalParams and adds heat pump-specific
    parameters for different fidelity levels.
    """

    # Core heat pump parameters
    cop_nominal: float = Field(3.5, description="Nominal Coefficient of Performance")
    technology: str = Field("air_to_water", description="Heat pump technology type")

    # STANDARD fidelity additions
    cop_temperature_curve: Optional[Dict[str, float]] = Field(
        None, description="COP variation with temperature {slope, intercept}"
    )
    defrost_power_penalty: float | None = Field(None, description="Power penalty during defrost cycles [%]")

    # DETAILED fidelity parameters
    refrigerant_type: str | None = Field(None, description="Refrigerant type (R410A, R32, etc.)")
    compressor_map: Optional[Dict[str, Any]] = Field(None, description="Detailed compressor performance map")
    heat_exchanger_effectiveness: float | None = Field(None, description="Heat exchanger effectiveness")

    # RESEARCH fidelity parameters
    detailed_refrigerant_model: Optional[Dict[str, Any]] = Field(
        None, description="Detailed refrigerant cycle modeling parameters"
    )
    control_algorithm: Optional[Dict[str, Any]] = Field(None, description="Advanced control algorithm parameters")


class HeatPumpParams(ComponentParams):
    """Heat pump parameters using the hierarchical technical parameter system.

    COP and capacity are now specified through the technical parameter block
    following the archetype inheritance pattern.
    """

    technical: HeatPumpTechnicalParams = Field(
        default_factory=lambda: HeatPumpTechnicalParams(
            capacity_nominal=10.0,  # Default 10 kW heat output
            efficiency_nominal=0.90,  # Pump electrical efficiency
            cop_nominal=3.5,  # Default COP
            fidelity_level=FidelityLevel.STANDARD
        )
        description="Technical parameters following the hierarchical archetype system"
    )


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================


class HeatPumpPhysicsSimple(BaseConversionPhysics):
    """Implements the SIMPLE rule-based physics for a heat pump.

    This is the baseline fidelity level providing:
    - Fixed COP operation: heat_output = electrical_input * COP
    - Basic energy conversion with constant efficiency
    """

    def rule_based_conversion_capacity(self, t: int, from_medium: str, to_medium: str) -> dict:
        """
        Calculate conversion capacities for SIMPLE heat pump physics.

        For heat pump: electricity → heat with COP amplification
        """
        # Get component parameters
        P_max_heat = self.params.technical.capacity_nominal  # Heat output capacity
        COP = self.params.technical.cop_nominal

        # Calculate maximum electrical input based on heat capacity and COP
        P_max_elec = P_max_heat / COP if COP > 0 else 0

        return {
            "max_input": P_max_elec,  # Maximum electrical input (kW)
            "max_output": P_max_heat,  # Maximum heat output (kW)
            "efficiency": COP,  # COP (heat out / electrical in)
        }

    def rule_based_conversion_dispatch(self, t: int, requested_output: float, from_medium: str, to_medium: str) -> dict:
        """
        Calculate actual input/output for requested heat output.

        Args:
            t: Current timestep
            requested_output: Desired heat output (kW)
            from_medium: 'electricity'
            to_medium: 'heat'

        Returns:
            dict: {'input_required': float, 'output_delivered': float}
        """
        capacity = self.rule_based_conversion_capacity(t, from_medium, to_medium)

        # Limit output to maximum capacity
        actual_output = min(requested_output, capacity["max_output"])

        # Calculate required electrical input based on COP
        if capacity["efficiency"] > 0:
            required_input = actual_output / capacity["efficiency"]
        else:
            required_input = 0.0

        # Ensure input doesn't exceed capacity
        if required_input > capacity["max_input"]:
            # Scale back both input and output proportionally
            scale_factor = capacity["max_input"] / required_input
            required_input = capacity["max_input"]
            actual_output = actual_output * scale_factor

        return {"input_required": required_input, "output_delivered": actual_output}


class HeatPumpPhysicsStandard(HeatPumpPhysicsSimple):
    """Implements the STANDARD rule-based physics for a heat pump.

    Inherits from SIMPLE and adds:
    - Temperature-dependent COP variation
    - Defrost cycle power penalties
    """

    def rule_based_conversion_capacity(self, t: int, from_medium: str, to_medium: str) -> dict:
        """
        Calculate conversion capacities with temperature effects.

        First applies SIMPLE physics, then adds STANDARD-specific effects.
        """
        # 1. Get the baseline result from SIMPLE physics
        capacity = super().rule_based_conversion_capacity(t, from_medium, to_medium)

        # 2. Add STANDARD-specific physics: temperature-dependent COP
        COP_adjusted = capacity["efficiency"]

        # Apply temperature variation if available
        cop_curve = getattr(self.params.technical, "cop_temperature_curve", None)
        if cop_curve:
            # Simplified temperature adjustment
            # In real implementation, would use actual ambient temperature
            temp_adjustment = cop_curve.get("slope", 0) * 5  # Assume 5°C deviation
            COP_adjusted = capacity["efficiency"] * (1 + temp_adjustment)

        # Apply defrost penalty if configured
        defrost_penalty = getattr(self.params.technical, "defrost_power_penalty", 0)
        if defrost_penalty:
            COP_adjusted = COP_adjusted * (1 - defrost_penalty / 100)

        # Update capacity with adjusted COP
        capacity["efficiency"] = max(COP_adjusted, 0.5)  # Minimum COP for stability

        # Recalculate max_input with adjusted COP
        capacity["max_input"] = capacity["max_output"] / capacity["efficiency"]

        return capacity


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================


class HeatPumpOptimizationSimple(BaseConversionOptimization):
    """Implements the SIMPLE MILP optimization constraints for heat pump.

    This is the baseline optimization strategy providing:
    - Fixed COP operation
    - Basic energy balance: Heat output = Electrical input * COP
    - Capacity constraints
    """

    def __init__(self, params, component_instance) -> None:
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for heat pump optimization.

        Returns constraints for basic heat pump operation with fixed COP.
        """
        constraints = []
        comp = self.component

        if hasattr(comp, "P_heatsource") and comp.P_heatsource is not None:
            # Core heat pump constraints
            N = comp.P_heatsource.shape[0]

            # SIMPLE MODEL: Fixed COP operation
            COP = comp.COP

            # Energy balance: Heat output = Electrical input * COP
            for t in range(N):
                # P_heatsource = (P_loss + P_pump) * COP
                constraints.append(comp.P_heatsource[t] == (comp.P_loss[t] + comp.P_pump[t]) * COP)

            # Capacity constraints
            constraints.append(comp.P_heatsource <= comp.P_max)
            constraints.append(comp.P_loss + comp.P_pump <= comp.P_max_elec)

        return constraints


class HeatPumpOptimizationStandard(HeatPumpOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for heat pump.

    Inherits from SIMPLE and adds:
    - Temperature-dependent COP adjustments
    - More realistic heat pump modeling
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for heat pump optimization.

        Adds temperature-dependent COP adjustments to the constraints.
        """
        constraints = []
        comp = self.component

        if hasattr(comp, "P_heatsource") and comp.P_heatsource is not None:
            # Core heat pump constraints
            N = comp.P_heatsource.shape[0]

            # Start with SIMPLE COP
            COP = comp.COP

            # STANDARD enhancement: temperature-dependent COP adjustments
            cop_curve = getattr(comp.technical, "cop_temperature_curve", None)
            if cop_curve:
                # Simplified adjustment for optimization
                temp_factor = cop_curve.get("slope", 0) * 5 + 1
                COP = COP * max(temp_factor, 0.5)

            # Energy balance with adjusted COP
            for t in range(N):
                # P_heatsource = (P_loss + P_pump) * COP
                constraints.append(comp.P_heatsource[t] == (comp.P_loss[t] + comp.P_pump[t]) * COP)

            # Capacity constraints
            constraints.append(comp.P_heatsource <= comp.P_max)
            constraints.append(comp.P_loss + comp.P_pump <= comp.P_max_elec)

        return constraints


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================


@register_component("HeatPump")
class HeatPump(Component):
    """Heat pump component with Strategy Pattern architecture.

    This class acts as a factory and container for heat pump strategies:
    - Physics strategies: Handle fidelity-specific rule-based conversion calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only

    The component delegates physics and optimization to strategy objects
    based on the configured fidelity level.
    """

    PARAMS_MODEL = HeatPumpParams

    def _post_init(self) -> None:
        """Initialize heat pump attributes and strategy objects."""
        self.type = "generation"
        self.medium = "heat"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original heat pump expects
        self.P_max = tech.capacity_nominal  # kW heat output capacity
        self.COP = tech.cop_nominal
        self.eta = tech.efficiency_nominal  # Electrical efficiency

        # Maximum electrical input (derived from heat capacity and COP)
        self.P_max_elec = self.P_max / self.COP if self.COP > 0 else 0

        # Store heat pump-specific parameters
        self.technology = tech.technology
        self.cop_temperature_curve = tech.cop_temperature_curve
        self.defrost_power_penalty = tech.defrost_power_penalty
        self.refrigerant_type = tech.refrigerant_type
        self.compressor_map = tech.compressor_map
        self.heat_exchanger_effectiveness = tech.heat_exchanger_effectiveness

        # CVXPY variables (for MILP solver)
        self.P_heatsource = None
        self.P_loss = None
        self.P_pump = None

        # STRATEGY PATTERN: Instantiate the correct strategies
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return HeatPumpPhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return HeatPumpPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later)
            return HeatPumpPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later)
            return HeatPumpPhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for HeatPump: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return HeatPumpOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return HeatPumpOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later)
            return HeatPumpOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later)
            return HeatPumpOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for HeatPump optimization: {fidelity}")

    def rule_based_conversion_capacity(self, t: int, from_medium: str, to_medium: str) -> dict:
        """
        Delegate to physics strategy for conversion capacity calculation.

        This maintains the same interface as BaseConversionComponent but
        delegates the actual physics calculation to the strategy object.
        """
        return self.physics.rule_based_conversion_capacity(t, from_medium, to_medium)

    def rule_based_conversion_dispatch(self, t: int, requested_output: float, from_medium: str, to_medium: str) -> dict:
        """
        Delegate to physics strategy for conversion dispatch calculation.

        This maintains the same interface as BaseConversionComponent but
        delegates the actual physics calculation to the strategy object.
        """
        return self.physics.rule_based_conversion_dispatch(t, requested_output, from_medium, to_medium)

    def add_optimization_vars(self, N: int) -> None:
        """Create CVXPY optimization variables."""
        self.P_heatsource = cp.Variable(N, name=f"{self.name}_P_heatsource", nonneg=True)
        self.P_loss = cp.Variable(N, name=f"{self.name}_P_loss", nonneg=True)
        self.P_pump = cp.Variable(N, name=f"{self.name}_P_pump", nonneg=True)

        # Add flows
        self.flows["source"]["P_heatsource"] = {
            "type": "heat"
            "value": self.P_heatsource
        }
        self.flows["sink"]["P_loss"] = {"type": "electricity", "value": self.P_loss}
        self.flows["sink"]["P_pump"] = {"type": "electricity", "value": self.P_pump}

    def set_constraints(self) -> List:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()

    def rule_based_operation(self, heat_demand: float, t: int) -> tuple:
        """Rule-based heat pump operation with fidelity-aware performance."""
        if heat_demand <= 0:
            return 0.0, 0.0

        # Determine effective COP (similar logic as constraints)
        effective_cop = self.COP

        # Apply temperature effects if available
        if self.cop_temperature_curve and hasattr(self, "system"):
            if hasattr(self.system, "profiles") and "ambient_temperature" in self.system.profiles:
                temp = (
                    self.system.profiles["ambient_temperature"][t]
                    if t < len(self.system.profiles["ambient_temperature"])
                    else 20
                )
                slope = self.cop_temperature_curve.get("slope", 0)
                temp_factor = 1 + slope * (temp - 7) / 100
                effective_cop = self.COP * max(0.5, temp_factor)

        # Calculate required electricity input
        elec_required = heat_demand / effective_cop

        # Apply electrical power limit
        elec_required = min(elec_required, self.P_max_elec)

        # Calculate actual heat output
        heat_output = elec_required * effective_cop

        return heat_output, elec_required
