"""Electric boiler component with MILP optimization support and hierarchical fidelity."""

from typing import Any, Optional

import cvxpy as cp
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel, GenerationTechnicalParams
from ecosystemiser.system_model.components.shared.base_classes import BaseConversionOptimization, BaseConversionPhysics
from ecosystemiser.system_model.components.shared.component import Component, ComponentParams
from ecosystemiser.system_model.components.shared.registry import register_component
from hive_logging import get_logger
from pydantic import Field

logger = get_logger(__name__)

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
    temperature_setpoint: float | None = Field(None, description="Operating temperature setpoint [°C]")

    # STANDARD fidelity additions
    thermal_inertia: float | None = Field(None, description="Thermal mass and inertia factor")
    modulation_range: Optional[dict[str, float]] = Field(
        None, description="Power modulation capability {min_power, max_power}"
    )

    # DETAILED fidelity parameters
    heat_exchanger_effectiveness: float | None = Field(None, description="Heat exchanger effectiveness")
    control_algorithm: Optional[dict[str, Any]] = Field(None, description="Control algorithm parameters")

    # RESEARCH fidelity parameters
    detailed_thermal_model: Optional[dict[str, Any]] = Field(None, description="Detailed thermal modeling parameters")
    emissions_model: Optional[dict[str, Any]] = Field(None, description="Detailed emissions modeling")


class ElectricBoilerParams(ComponentParams):
    """Electric boiler parameters using the hierarchical technical parameter system.

    Efficiency and capacity are now specified through the technical parameter block
    following the archetype inheritance pattern.
    """

    technical: ElectricBoilerTechnicalParams = Field(
        default_factory=lambda: ElectricBoilerTechnicalParams(
            capacity_nominal=10.0,  # Default 10 kW heat output
            efficiency_nominal=0.95,  # Default 95% efficiency
            fidelity_level=FidelityLevel.STANDARD,
        ),
        description="Technical parameters following the hierarchical archetype system",
    )


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================


class ElectricBoilerPhysicsSimple(BaseConversionPhysics):
    """Implements the SIMPLE rule-based physics for an electric boiler.

    This is the baseline fidelity level providing:
    - Direct electrical to thermal conversion: heat_output = electrical_input * efficiency
    - Basic energy conversion with constant efficiency
    """

    def rule_based_conversion_capacity(self, t: int, from_medium: str, to_medium: str) -> dict:
        """
        Calculate conversion capacities for SIMPLE electric boiler physics.

        For electric boiler: electricity → heat with efficiency < 1
        """
        # Get component parameters
        P_max_heat = self.params.technical.capacity_nominal  # Heat output capacity
        efficiency = self.params.technical.efficiency_nominal

        # Calculate maximum electrical input based on heat capacity and efficiency
        P_max_elec = P_max_heat / efficiency if efficiency > 0 else 0

        return {
            "max_input": P_max_elec,  # Maximum electrical input (kW)
            "max_output": P_max_heat,  # Maximum heat output (kW)
            "efficiency": efficiency,  # Electrical to thermal efficiency
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

        # Calculate required electrical input based on efficiency
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


class ElectricBoilerPhysicsStandard(ElectricBoilerPhysicsSimple):
    """Implements the STANDARD rule-based physics for an electric boiler.

    Inherits from SIMPLE and adds:
    - Heat exchanger effectiveness losses
    - Modulation constraints (minimum operating power)
    """

    def rule_based_conversion_capacity(self, t: int, from_medium: str, to_medium: str) -> dict:
        """
        Calculate conversion capacities with heat exchanger effects.

        First applies SIMPLE physics, then adds STANDARD-specific effects.
        """
        # 1. Get the baseline result from SIMPLE physics
        capacity = super().rule_based_conversion_capacity(t, from_medium, to_medium)

        # 2. Add STANDARD-specific physics: heat exchanger effectiveness
        effectiveness = getattr(self.params.technical, "heat_exchanger_effectiveness", None)
        if effectiveness:
            # Reduce overall efficiency by heat exchanger effectiveness
            capacity["efficiency"] = capacity["efficiency"] * effectiveness

        # 3. Recalculate max_input with adjusted efficiency
        if capacity["efficiency"] > 0:
            capacity["max_input"] = capacity["max_output"] / capacity["efficiency"]
        else:
            capacity["max_input"] = 0.0

        return capacity


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================


class ElectricBoilerOptimizationSimple(BaseConversionOptimization):
    """Implements the SIMPLE MILP optimization constraints for electric boiler.

    This is the baseline optimization strategy providing:
    - Direct electric-to-heat conversion with fixed efficiency
    - Basic capacity constraints
    - No modulation or heat exchanger effects
    """

    def __init__(self, params, component_instance) -> None:
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for electric boiler optimization.

        Returns constraints for basic electric-to-heat conversion.
        """
        constraints = []
        comp = self.component

        if hasattr(comp, "P_heat") and comp.P_heat is not None:
            # Core electric boiler constraints
            N = comp.P_heat.shape[0]

            # SIMPLE MODEL: Direct conversion efficiency
            efficiency = comp.technical.efficiency_nominal

            # Energy balance: Heat output = Electrical input * efficiency
            for t in range(N):
                constraints.append(comp.P_heat[t] == efficiency * comp.P_elec[t])

            # Capacity constraints
            constraints.append(comp.P_heat <= comp.P_max)
            constraints.append(comp.P_elec <= comp.P_max_elec)

        return constraints


class ElectricBoilerOptimizationStandard(ElectricBoilerOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for electric boiler.

    Inherits from SIMPLE and adds:
    - Heat exchanger effectiveness
    - Modulation constraints with minimum operating power
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for electric boiler optimization.

        Adds heat exchanger and modulation constraints.
        """
        constraints = []
        comp = self.component

        if hasattr(comp, "P_heat") and comp.P_heat is not None:
            # Core electric boiler constraints
            N = comp.P_heat.shape[0]

            # STANDARD: Apply heat exchanger effectiveness
            efficiency = comp.technical.efficiency_nominal
            effectiveness = getattr(comp.technical, "heat_exchanger_effectiveness", None)
            if effectiveness:
                efficiency = efficiency * effectiveness

            # Energy balance with adjusted efficiency
            for t in range(N):
                constraints.append(comp.P_heat[t] == efficiency * comp.P_elec[t])

            # Capacity constraints
            constraints.append(comp.P_heat <= comp.P_max)
            constraints.append(comp.P_elec <= comp.P_max_elec)

            # STANDARD: Modulation constraints
            modulation_range = getattr(comp.technical, "modulation_range", None)
            if modulation_range:
                min_power = modulation_range.get("min_power", 0) * comp.P_max
                max_power = modulation_range.get("max_power", 1) * comp.P_max

                # Binary variable for on/off state
                if not hasattr(comp, "_boiler_state"):
                    comp._boiler_state = cp.Variable(N, boolean=True, name=f"{comp.name}_state")

                # Modulation constraints
                constraints.append(comp.P_heat >= min_power * comp._boiler_state)
                constraints.append(comp.P_heat <= max_power * comp._boiler_state)

        return constraints


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================


@register_component("ElectricBoiler")
class ElectricBoiler(Component):
    """Electric boiler component with Strategy Pattern architecture.

    This class acts as a factory and container for electric boiler strategies:
    - Physics strategies: Handle fidelity-specific rule-based conversion calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only

    The component delegates physics and optimization to strategy objects
    based on the configured fidelity level.
    """

    PARAMS_MODEL = ElectricBoilerParams

    def _post_init(self) -> None:
        """Initialize electric boiler attributes and strategy objects."""
        self.type = "generation"
        self.medium = "heat"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original electric boiler expects
        self.P_max = tech.capacity_nominal  # kW heat output capacity
        self.eta = tech.efficiency_nominal  # Electrical to thermal conversion efficiency

        # Maximum electrical input (derived from heat capacity and efficiency)
        self.P_max_elec = self.P_max / self.eta if self.eta > 0 else 0

        # Store electric boiler-specific parameters
        self.heating_element_type = tech.heating_element_type
        self.temperature_setpoint = tech.temperature_setpoint
        self.thermal_inertia = tech.thermal_inertia
        self.modulation_range = tech.modulation_range
        self.heat_exchanger_effectiveness = tech.heat_exchanger_effectiveness
        self.control_algorithm = tech.control_algorithm

        # CVXPY variables (for MILP solver)
        self.P_heat = None
        self.P_elec = None

        # STRATEGY PATTERN: Instantiate the correct strategies
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return ElectricBoilerPhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return ElectricBoilerPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later)
            return ElectricBoilerPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later)
            return ElectricBoilerPhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for ElectricBoiler: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return ElectricBoilerOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return ElectricBoilerOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later)
            return ElectricBoilerOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later)
            return ElectricBoilerOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for ElectricBoiler optimization: {fidelity}")

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

    def add_optimization_vars(self, N: int | None = None) -> None:
        """Create CVXPY optimization variables."""
        if N is None:
            N = self.N

        self.P_heat = cp.Variable(N, name=f"{self.name}_P_heat", nonneg=True)
        self.P_elec = cp.Variable(N, name=f"{self.name}_P_elec", nonneg=True)

        # Add flows
        self.flows["source"]["P_heat"] = {"type": "heat", "value": self.P_heat}
        self.flows["sink"]["P_elec"] = {"type": "electricity", "value": self.P_elec}

    def set_constraints(self) -> list:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()

    def rule_based_operation(self, heat_demand: float, t: int) -> tuple:
        """Rule-based electric boiler operation with fidelity-aware performance.

        Returns:
            (heat_output, electricity_input)
        """
        if heat_demand <= 0:
            return 0.0, 0.0

        # Use the conversion dispatch strategy
        dispatch = self.rule_based_conversion_dispatch(t, heat_demand, "electricity", "heat")

        heat_output = dispatch["output_delivered"]
        elec_required = dispatch["input_required"]

        # Apply modulation constraints in rule-based mode
        if self.modulation_range:
            min_power = self.modulation_range.get("min_power", 0) * self.P_max
            if heat_output > 0 and heat_output < min_power:
                # Either off or at minimum power
                heat_output = min_power if heat_demand >= min_power else 0.0
                # Recalculate electricity requirement
                if heat_output > 0:
                    capacity = self.rule_based_conversion_capacity(t, "electricity", "heat")
                    elec_required = heat_output / capacity["efficiency"] if capacity["efficiency"] > 0 else 0.0
                else:
                    elec_required = 0.0

        return heat_output, elec_required
