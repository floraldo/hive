"""Power demand component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import DemandTechnicalParams, FidelityLevel
from ..shared.base_classes import BaseDemandPhysics, BaseDemandOptimization

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
            capacity_nominal=5.0,  # Required by base archetype
            peak_demand=5.0,  # Default 5 kW peak
            load_profile_type="variable",
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================

class PowerDemandPhysicsSimple(BaseDemandPhysics):
    """Implements the SIMPLE rule-based physics for power demand.

    This is the baseline fidelity level providing:
    - Basic demand: demand = profile * peak_demand
    - Fixed electrical demand pattern with no flexibility
    """

    def rule_based_demand(self, t: int, profile_value: float) -> float:
        """
        Implement SIMPLE power demand physics with direct profile scaling.

        This matches the exact logic from BaseDemandComponent for numerical equivalence.
        """
        # Get peak demand capacity
        peak_demand = self.params.technical.peak_demand

        # Base demand: profile value * peak demand
        # Profile should be normalized (0-1), peak_demand provides scaling
        base_demand = profile_value * peak_demand

        return max(0.0, base_demand)


class PowerDemandPhysicsStandard(PowerDemandPhysicsSimple):
    """Implements the STANDARD rule-based physics for power demand.

    Inherits from SIMPLE and adds:
    - Power factor considerations
    - Basic electrical load characteristics
    """

    def rule_based_demand(self, t: int, profile_value: float) -> float:
        """
        Implement STANDARD power demand physics with power factor considerations.

        First applies SIMPLE physics, then adds STANDARD-specific effects.
        """
        # 1. Get the baseline result from SIMPLE physics
        demand_after_simple = super().rule_based_demand(t, profile_value)

        # 2. Add STANDARD-specific physics: power factor considerations
        power_factor = getattr(self.params.technical, 'power_factor', 0.95)
        if power_factor and power_factor != 1.0:
            # For now, keep active power the same but note reactive power would be calculated
            # In a more detailed implementation, we might adjust for apparent power needs
            pass

        return max(0.0, demand_after_simple)


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================

class PowerDemandOptimizationSimple(BaseDemandOptimization):
    """Implements the SIMPLE MILP optimization constraints for power demand.

    This is the baseline optimization strategy providing:
    - Fixed demand: P_in = profile * P_max
    - Demand must be met exactly
    - No flexibility or power factor consideration
    """

    def __init__(self, params, component_instance):
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for power demand optimization.

        Returns constraints for fixed power demand without flexibility.
        """
        constraints = []
        comp = self.component

        if comp.P_in is not None and hasattr(comp, 'profile'):
            # SIMPLE MODEL: Fixed demand must be met exactly
            # P_in = profile * P_max
            demand_exact = comp.profile * comp.P_max

            # Apply exact demand constraint
            constraints.append(comp.P_in == demand_exact)

        return constraints


class PowerDemandOptimizationStandard(PowerDemandOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for power demand.

    Inherits from SIMPLE and adds:
    - Power factor acknowledgment (for logging/monitoring)
    - Preparation for reactive power modeling (future enhancement)

    Note: Actual power factor implementation requires reactive power variables
    which is a DETAILED/RESEARCH feature.
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for power demand optimization.

        Currently same as SIMPLE but logs power factor for awareness.
        """
        constraints = []
        comp = self.component

        if comp.P_in is not None and hasattr(comp, 'profile'):
            # STANDARD MODEL: Same as SIMPLE for real power
            # but acknowledges power factor for future enhancements
            demand_exact = comp.profile * comp.P_max

            # Log power factor awareness (but don't modify constraints)
            power_factor = getattr(comp.technical, 'power_factor', 1.0)
            if power_factor < 1.0:
                logger.debug(f"STANDARD fidelity: Acknowledging power factor of {power_factor}, "
                           f"but not modifying real power constraints.")

            # Apply exact demand constraint (same as SIMPLE)
            constraints.append(comp.P_in == demand_exact)

        return constraints


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================

@register_component("PowerDemand")
class PowerDemand(Component):
    """Power demand component with Strategy Pattern architecture.

    This class acts as a factory and container for power demand strategies:
    - Physics strategies: Handle fidelity-specific rule-based demand calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only

    The component delegates physics and optimization to strategy objects
    based on the configured fidelity level.
    """

    PARAMS_MODEL = PowerDemandParams

    def _post_init(self):
        """Initialize power demand attributes and strategy objects."""
        self.type = "consumption"
        self.medium = "electricity"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original power demand expects
        self.P_max = tech.peak_demand  # kW peak electrical demand

        # Store power demand-specific parameters
        self.power_factor = tech.power_factor
        self.demand_flexibility = tech.demand_flexibility
        self.stochastic_model = tech.stochastic_model
        self.occupancy_coupling = tech.occupancy_coupling

        # Profile should be assigned by the system/builder
        # Initialize as None, will be set by assign_profiles
        if not hasattr(self, 'profile') or self.profile is None:
            logger.warning(f"No demand profile assigned to {self.name}. Using zero demand.")
            self.profile = np.zeros(getattr(self, 'N', 24))
        else:
            self.profile = np.array(self.profile)

        # CVXPY variables (for MILP solver)
        self.P_in = None

        # STRATEGY PATTERN: Instantiate the correct strategies
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return PowerDemandPhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return PowerDemandPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later)
            return PowerDemandPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later)
            return PowerDemandPhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for PowerDemand: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return PowerDemandOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return PowerDemandOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later)
            return PowerDemandOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later)
            return PowerDemandOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for PowerDemand optimization: {fidelity}")

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

    def set_constraints(self) -> List:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()