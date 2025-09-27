"""Heat demand component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import DemandTechnicalParams, FidelityLevel
from ..shared.base_classes import BaseDemandPhysics, BaseDemandOptimization

logger = logging.getLogger(__name__)


# =============================================================================
# HEAT DEMAND-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class HeatDemandTechnicalParams(DemandTechnicalParams):
    """Heat demand-specific technical parameters extending demand archetype.

    This model inherits from DemandTechnicalParams and adds thermal demand-specific
    parameters for different fidelity levels.
    """
    # Heat-specific parameters
    demand_type: str = Field("space_heating", description="Type of heat demand")
    temperature_requirement: Optional[float] = Field(
        None,
        description="Required supply temperature [°C]"
    )

    # STANDARD fidelity additions
    thermal_comfort_band: Optional[Dict[str, float]] = Field(
        None,
        description="Acceptable temperature range {min_temp, max_temp}"
    )
    building_thermal_mass: Optional[float] = Field(
        None,
        description="Building thermal inertia factor"
    )

    # DETAILED fidelity parameters
    weather_dependency: Optional[Dict[str, float]] = Field(
        None,
        description="Weather correlation parameters"
    )
    occupancy_schedule: Optional[Dict[str, Any]] = Field(
        None,
        description="Occupancy-driven demand variations"
    )
    demand_response_capability: Optional[Dict[str, float]] = Field(
        None,
        description="Demand response parameters {shift_capacity, shed_capacity}"
    )

    # RESEARCH fidelity parameters
    building_physics_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed building physics model parameters"
    )
    behavioral_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Occupant behavior modeling parameters"
    )


class HeatDemandParams(ComponentParams):
    """Heat demand parameters using the hierarchical technical parameter system.

    Profile data should be provided separately through the system's
    profile loading mechanism, not as a component parameter.
    """
    technical: HeatDemandTechnicalParams = Field(
        default_factory=lambda: HeatDemandTechnicalParams(
            capacity_nominal=5.0,  # Required by base archetype
            peak_demand=5.0,  # Default 5 kW peak heat demand
            load_profile_type="variable",
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================

class HeatDemandPhysicsSimple(BaseDemandPhysics):
    """Implements the SIMPLE rule-based physics for heat demand.

    This is the baseline fidelity level providing:
    - Basic demand: demand = profile * peak_demand
    - Fixed demand pattern with no flexibility
    """

    def rule_based_demand(self, t: int, profile_value: float) -> float:
        """
        Implement SIMPLE heat demand physics with direct profile scaling.

        This matches the exact logic from BaseDemandComponent for numerical equivalence.
        """
        # Get peak demand capacity
        peak_demand = self.params.technical.peak_demand

        # Base demand: profile value * peak demand
        # Profile should be normalized (0-1), peak_demand provides scaling
        base_demand = profile_value * peak_demand

        return max(0.0, base_demand)


class HeatDemandPhysicsStandard(HeatDemandPhysicsSimple):
    """Implements the STANDARD rule-based physics for heat demand.

    Inherits from SIMPLE and adds:
    - Weather-dependent demand variations
    - Thermal comfort flexibility
    """

    def rule_based_demand(self, t: int, profile_value: float) -> float:
        """
        Implement STANDARD heat demand physics with weather dependency.

        First applies SIMPLE physics, then adds STANDARD-specific effects.
        """
        # 1. Get the baseline result from SIMPLE physics
        demand_after_simple = super().rule_based_demand(t, profile_value)

        # 2. Add STANDARD-specific physics: weather dependency
        weather_dependency = getattr(self.params.technical, 'weather_dependency', None)
        if weather_dependency:
            # Simplified weather adjustment
            # In real implementation, would use actual ambient temperature
            temp_factor = weather_dependency.get('temperature_factor', 0.05)
            reference_temp = weather_dependency.get('reference_temp', 18)
            # Assume some temperature deviation for demonstration
            temp_deviation = 5  # Assume 5°C deviation from reference
            weather_multiplier = 1 + temp_factor * temp_deviation
            demand_after_simple = demand_after_simple * max(0.1, weather_multiplier)

        return max(0.0, demand_after_simple)


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================

class HeatDemandOptimizationSimple(BaseDemandOptimization):
    """Implements the SIMPLE MILP optimization constraints for heat demand.

    This is the baseline optimization strategy providing:
    - Fixed heat demand: H_in = profile * H_max
    - Demand must be met exactly
    - No thermal comfort flexibility
    """

    def __init__(self, params, component_instance):
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for heat demand optimization.

        Returns constraints for fixed heat demand without flexibility.
        """
        constraints = []
        comp = self.component

        if comp.H_in is not None and hasattr(comp, 'profile'):
            # Core heat demand constraints
            N = comp.H_in.shape[0]

            for t in range(N):
                # Handle profile bounds
                if t < len(comp.profile):
                    base_demand_t = comp.profile[t] * comp.H_max
                else:
                    base_demand_t = comp.profile[-1] * comp.H_max if len(comp.profile) > 0 else 0

                # SIMPLE MODEL: Fixed heat demand must be met exactly
                constraints.append(comp.H_in[t] == base_demand_t)

        return constraints


class HeatDemandOptimizationStandard(HeatDemandOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for heat demand.

    Inherits from SIMPLE and adds:
    - Thermal comfort bands for flexibility
    - Temperature-dependent demand variation
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for heat demand optimization.

        Adds thermal comfort flexibility to the constraints.
        """
        constraints = []
        comp = self.component

        if comp.H_in is not None and hasattr(comp, 'profile'):
            # Core heat demand constraints
            N = comp.H_in.shape[0]

            for t in range(N):
                # Handle profile bounds
                if t < len(comp.profile):
                    base_demand_t = comp.profile[t] * comp.H_max
                else:
                    base_demand_t = comp.profile[-1] * comp.H_max if len(comp.profile) > 0 else 0

                # STANDARD: Thermal comfort bands allow some flexibility
                thermal_comfort_band = getattr(comp.technical, 'thermal_comfort_band', None)
                if thermal_comfort_band:
                    comfort_flexibility = 0.1  # 10% flexibility for thermal comfort
                    demand_min = base_demand_t * (1 - comfort_flexibility)
                    demand_max = base_demand_t * (1 + comfort_flexibility)

                    # Apply flexible demand bounds
                    constraints.append(comp.H_in[t] >= demand_min)
                    constraints.append(comp.H_in[t] <= demand_max)
                else:
                    # If no flexibility specified, use exact demand
                    constraints.append(comp.H_in[t] == base_demand_t)

        return constraints


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================

@register_component("HeatDemand")
class HeatDemand(Component):
    """Heat demand component with Strategy Pattern architecture.

    This class acts as a factory and container for heat demand strategies:
    - Physics strategies: Handle fidelity-specific rule-based demand calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only

    The component delegates physics and optimization to strategy objects
    based on the configured fidelity level.
    """

    PARAMS_MODEL = HeatDemandParams

    def _post_init(self):
        """Initialize heat demand attributes and strategy objects."""
        self.type = "consumption"
        self.medium = "heat"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original heat demand expects
        self.H_max = tech.peak_demand  # kW peak heat demand
        self.P_max = tech.peak_demand  # Alias for compatibility with BaseDemandComponent

        # Store heat demand-specific parameters
        self.demand_type = tech.demand_type
        self.temperature_requirement = tech.temperature_requirement
        self.thermal_comfort_band = tech.thermal_comfort_band
        self.building_thermal_mass = tech.building_thermal_mass
        self.weather_dependency = tech.weather_dependency
        self.occupancy_schedule = tech.occupancy_schedule
        self.demand_response_capability = tech.demand_response_capability

        # Profile should be assigned by the system/builder
        # Initialize as None, will be set by assign_profiles
        if not hasattr(self, 'profile') or self.profile is None:
            logger.warning(f"No heat demand profile assigned to {self.name}. Using zero demand.")
            self.profile = np.zeros(getattr(self, 'N', 24))
        else:
            self.profile = np.array(self.profile)

        # Legacy compatibility: also set H_profile
        self.H_profile = self.profile

        # CVXPY variables (for MILP solver)
        self.H_in = None

        # STRATEGY PATTERN: Instantiate the correct strategies
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return HeatDemandPhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return HeatDemandPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later)
            return HeatDemandPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later)
            return HeatDemandPhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for HeatDemand: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return HeatDemandOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return HeatDemandOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later)
            return HeatDemandOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later)
            return HeatDemandOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for HeatDemand optimization: {fidelity}")

    def rule_based_demand(self, t: int) -> float:
        """
        Delegate to physics strategy for demand calculation.

        This maintains the same interface as BaseDemandComponent but
        delegates the actual physics calculation to the strategy object.
        """
        # Check bounds
        if not hasattr(self, 'profile') or self.profile is None or t >= len(self.profile):
            return 0.0

        # Get normalized profile value for this timestep
        profile_value = self.profile[t]

        # Delegate to physics strategy
        demand_output = self.physics.rule_based_demand(t, profile_value)

        # Log for debugging if needed
        if t == 0 and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"{self.name} at t={t}: profile={profile_value:.3f}, "
                f"demand={demand_output:.3f}kW"
            )

        return demand_output

    def add_optimization_vars(self, N: Optional[int] = None):
        """Create CVXPY optimization variables."""
        if N is None:
            N = self.N

        self.H_in = cp.Variable(N, name=f'{self.name}_H_in', nonneg=True)

        # Add as sink flow
        self.flows['sink']['H_in'] = {
            'type': 'heat',
            'value': self.H_in
        }

    def set_constraints(self) -> List:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()

    def rule_based_consumption(self, t: int) -> float:
        """Get heat demand at time t for rule-based operation with fidelity awareness."""
        return self.rule_based_demand(t)