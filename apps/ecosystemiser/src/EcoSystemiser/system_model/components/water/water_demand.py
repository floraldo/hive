"""Water demand component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import DemandTechnicalParams, FidelityLevel
from ..shared.base_classes import BaseDemandComponent, BaseDemandPhysics, BaseDemandOptimization

logger = logging.getLogger(__name__)


# =============================================================================
# WATER DEMAND-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================

class WaterDemandTechnicalParams(DemandTechnicalParams):
    """Water demand-specific technical parameters extending demand archetype.

    This model inherits from DemandTechnicalParams and adds water demand-specific
    parameters for different fidelity levels.
    """
    # Water-specific parameters (in cubic meters and m³/h)
    demand_type: str = Field("residential", description="Type of water demand")
    pressure_requirement: Optional[float] = Field(
        None,
        description="Required supply pressure [bar]"
    )

    # STANDARD fidelity additions
    seasonal_variation: Optional[float] = Field(
        None,
        description="Seasonal variation factor (0-1)"
    )
    pressure_dependency: Optional[Dict[str, float]] = Field(
        None,
        description="Pressure-dependent demand response"
    )

    # DETAILED fidelity parameters
    occupancy_coupling: Optional[Dict[str, Any]] = Field(
        None,
        description="Occupancy-driven demand variations"
    )
    conservation_measures: Optional[Dict[str, float]] = Field(
        None,
        description="Water conservation effectiveness"
    )

    # RESEARCH fidelity parameters
    behavioral_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed user behavior modeling"
    )
    stochastic_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Stochastic demand model parameters"
    )


class WaterDemandParams(ComponentParams):
    """Water demand parameters using the hierarchical technical parameter system.

    Profile data should be provided separately through the system's
    profile loading mechanism, not as a component parameter.
    """
    technical: WaterDemandTechnicalParams = Field(
        default_factory=lambda: WaterDemandTechnicalParams(
            capacity_nominal=3.0,  # Default 3 m³/h peak demand
            peak_demand=3.0,       # Default 3 m³/h peak
            load_profile_type="variable",
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================

class WaterDemandPhysicsSimple(BaseDemandPhysics):
    """Implements the SIMPLE rule-based physics for water demand.

    This is the baseline fidelity level providing:
    - Basic demand: demand = profile * peak_demand
    - Fixed water demand pattern with no flexibility
    """

    def rule_based_demand(self, t: int, profile_value: float) -> float:
        """
        Implement SIMPLE water demand physics with direct profile scaling.

        This matches the exact logic from BaseDemandComponent for numerical equivalence.
        """
        # Get peak demand capacity
        peak_demand = self.params.technical.peak_demand

        # Base demand: profile value * peak demand
        # Profile should be normalized (0-1), peak_demand provides scaling
        base_demand = profile_value * peak_demand

        return max(0.0, base_demand)


class WaterDemandPhysicsStandard(WaterDemandPhysicsSimple):
    """Implements the STANDARD rule-based physics for water demand.

    Inherits from SIMPLE and adds:
    - Seasonal variations
    - Pressure-dependent demand response
    """

    def rule_based_demand(self, t: int, profile_value: float) -> float:
        """
        Implement STANDARD water demand physics with seasonal effects.

        First applies SIMPLE physics, then adds STANDARD-specific effects.
        """
        # 1. Get the baseline result from SIMPLE physics
        demand_after_simple = super().rule_based_demand(t, profile_value)

        # 2. Add STANDARD-specific physics: seasonal variation
        seasonal_variation = getattr(self.params.technical, 'seasonal_variation', None)
        if seasonal_variation:
            # Simplified seasonal adjustment
            # In real implementation, would use actual calendar date
            day_of_year = (t // 24) % 365
            seasonal_factor = 1 + seasonal_variation * np.sin(2 * np.pi * day_of_year / 365)
            demand_after_simple = demand_after_simple * max(0.1, seasonal_factor)

        return max(0.0, demand_after_simple)


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================

class WaterDemandOptimization(BaseDemandOptimization):
    """Handles the MILP (CVXPY) constraints for water demand.

    Encapsulates all optimization logic separately from physics and data.
    This enables clean separation and easy testing of optimization constraints.
    """

    def __init__(self, params, component_instance):
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create CVXPY constraints for water demand optimization.

        This method encapsulates all the MILP constraint logic for water demand.
        """
        constraints = []
        comp = self.component

        if comp.Q_in is not None and hasattr(comp, 'profile'):
            # Get fidelity level
            fidelity = comp.technical.fidelity_level

            # Core water demand constraints
            N = comp.Q_in.shape[0]

            # --- SIMPLE MODEL (baseline) ---
            # Fixed demand: Q_in = profile * Q_max (demand must be met exactly)
            demand_min = comp.profile * comp.Q_max
            demand_max = comp.profile * comp.Q_max

            # --- STANDARD ENHANCEMENTS ---
            if fidelity >= FidelityLevel.STANDARD:
                # Seasonal variations would be handled in profile generation
                seasonal_variation = getattr(comp.technical, 'seasonal_variation', None)
                if seasonal_variation:
                    # For now, STANDARD maintains exact demand satisfaction
                    # In practice: might adjust for seasonal flexibility
                    pass

            # --- DETAILED ENHANCEMENTS ---
            if fidelity >= FidelityLevel.DETAILED:
                # Conservation measures allow some demand reduction
                conservation_measures = getattr(comp.technical, 'conservation_measures', None)
                if conservation_measures:
                    # Allow demand reduction through conservation
                    conservation_factor = conservation_measures.get('efficiency_gain', 0.1)
                    demand_min = comp.profile * comp.Q_max * (1 - conservation_factor)
                    demand_max = comp.profile * comp.Q_max

            # Apply demand constraints with all fidelity enhancements
            if np.array_equal(demand_min, demand_max):
                # Exact demand satisfaction (SIMPLE and STANDARD)
                constraints.append(comp.Q_in == demand_max)
            else:
                # Flexible demand bounds (DETAILED and RESEARCH)
                constraints.append(comp.Q_in >= demand_min)
                constraints.append(comp.Q_in <= demand_max)

        return constraints


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================

@register_component("WaterDemand")
class WaterDemand(Component):
    """Water demand component with Strategy Pattern architecture.

    This class acts as a factory and container for water demand strategies:
    - Physics strategies: Handle fidelity-specific rule-based demand calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only

    The component delegates physics and optimization to strategy objects
    based on the configured fidelity level.
    """

    PARAMS_MODEL = WaterDemandParams

    def _post_init(self):
        """Initialize water demand attributes and strategy objects."""
        self.type = "consumption"
        self.medium = "water"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original water demand expects (m³/h)
        self.Q_max = tech.peak_demand  # m³/h peak water demand

        # Store water demand-specific parameters
        self.demand_type = tech.demand_type
        self.pressure_requirement = tech.pressure_requirement
        self.seasonal_variation = tech.seasonal_variation
        self.pressure_dependency = tech.pressure_dependency
        self.occupancy_coupling = tech.occupancy_coupling
        self.conservation_measures = tech.conservation_measures

        # Profile should be assigned by the system/builder
        # Initialize as None, will be set by assign_profiles
        if not hasattr(self, 'profile') or self.profile is None:
            logger.warning(f"No water demand profile assigned to {self.name}. Using zero demand.")
            self.profile = np.zeros(getattr(self, 'N', 24))
        else:
            self.profile = np.array(self.profile)

        # CVXPY variables (for MILP solver)
        self.Q_in = None

        # STRATEGY PATTERN: Instantiate the correct strategies
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return WaterDemandPhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return WaterDemandPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later)
            return WaterDemandPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later)
            return WaterDemandPhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for WaterDemand: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy."""
        # For now, all fidelity levels use the same optimization strategy
        # Future: Could have different optimization strategies per fidelity
        return WaterDemandOptimization(self.params, self)

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
                f"demand={demand_output:.3f}m³/h"
            )

        return demand_output

    def add_optimization_vars(self, N: Optional[int] = None):
        """Create CVXPY optimization variables."""
        if N is None:
            N = self.N

        # For demand, input is fixed by profile (unless flexible)
        self.Q_in = cp.Variable(N, name=f'{self.name}_Q_in', nonneg=True)

        # Add as flow
        self.flows['sink']['Q_in'] = {
            'type': 'water',
            'value': self.Q_in,
            'profile': self.profile
        }

    def set_constraints(self) -> List:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()

    def rule_based_consumption(self, t: int) -> float:
        """Get water demand at time t for rule-based operation with fidelity awareness."""
        return self.rule_based_demand(t)

    def __repr__(self):
        """String representation."""
        return (f"WaterDemand(name='{self.name}', "
                f"peak_demand={self.Q_max}m³/h, "
                f"fidelity={self.technical.fidelity_level.value})")