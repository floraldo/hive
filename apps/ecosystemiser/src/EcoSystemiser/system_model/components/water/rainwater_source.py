"""Rainwater harvesting source component with MILP optimization support and hierarchical fidelity."""

from typing import Any, Optional

import cvxpy as cp
from pydantic import Field

from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel, GenerationTechnicalParams
from ecosystemiser.system_model.components.shared.base_classes import BaseGenerationOptimization, BaseGenerationPhysics
from ecosystemiser.system_model.components.shared.component import Component, ComponentParams
from ecosystemiser.system_model.components.shared.registry import register_component
from hive_logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# RAINWATER SOURCE-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================,


class RainwaterSourceTechnicalParams(GenerationTechnicalParams):
    """Rainwater source-specific technical parameters extending generation archetype.
    from __future__ import annotations


        This model inherits from GenerationTechnicalParams and adds rainwater harvesting-specific,
        parameters for different fidelity levels.,
    """

    # Rainwater harvesting parameters
    catchment_area_m2: float = Field(100.0, description="Roof/catchment area [m²]")
    runoff_coefficient: float = Field(0.85, description="Runoff coefficient (0-1)")
    collection_system_type: str = Field("gravity_fed", description="Type of collection system")

    # STANDARD fidelity additions
    first_flush_diversion: float | None = Field(None, description="First flush diversion volume [mm]")
    filtration_stages: Optional[dict[str, float]] = Field(None, description="Multi-stage filtration efficiencies")

    # DETAILED fidelity parameters
    seasonal_collection_factors: Optional[list[float]] = Field(
        None, description="Monthly collection efficiency factors",
    )
    water_quality_model: Optional[dict[str, Any]] = Field(None, description="Water quality degradation model")

    # RESEARCH fidelity parameters
    weather_dependency_model: Optional[dict[str, Any]] = Field(None, description="Advanced weather dependency modeling")
    contamination_model: Optional[dict[str, Any]] = Field(
        None, description="Detailed contamination and treatment modeling",
    )


class RainwaterSourceParams(ComponentParams):
    """Rainwater source parameters using the hierarchical technical parameter system.,

    Rainfall data should be provided separately through the system's,
    profile loading mechanism, not as a component parameter.,
    """

    technical: RainwaterSourceTechnicalParams = Field(
        default_factory=lambda: RainwaterSourceTechnicalParams(
            capacity_nominal=5.0,  # Default 5 m³/h max collection,
            efficiency_nominal=0.90,  # Default 90% collection efficiency,
            fidelity_level=FidelityLevel.STANDARD,
        ),
        description="Technical parameters following the hierarchical archetype system",
    )


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================,


class RainwaterSourcePhysicsSimple(BaseGenerationPhysics):
    """Implements the SIMPLE rule-based physics for rainwater collection.,

    This is the baseline fidelity level providing:
    - Basic collection: collection = rainfall * area * runoff_coeff * efficiency
    - Fixed collection efficiency with no advanced modeling,
    """

    def rule_based_generate(self, t: int, profile_value: float) -> float:
        """
        Implement SIMPLE rainwater collection physics.

        Args:
            t: Current timestep
            profile_value: Rainfall intensity [mm/h] for this timestep

        Returns:
            float: Available water collection in m³/h,
        """
        # Get component parameters
        area_m2 = self.params.technical.catchment_area_m2
        runoff_coeff = self.params.technical.runoff_coefficient
        efficiency = self.params.technical.efficiency_nominal
        max_collection = self.params.technical.capacity_nominal

        # Calculate raw collection: rainfall(mm/h) * area(m²) * runoff * efficiency
        # Convert mm to m: mm/h * m² = mm*m²/h = 0.001*m³/h
        raw_collection = profile_value * area_m2 * runoff_coeff * efficiency / 1000

        # Limit to maximum collection rate
        actual_collection = min(raw_collection, max_collection)

        return max(0.0, actual_collection)


class RainwaterSourcePhysicsStandard(RainwaterSourcePhysicsSimple):
    """Implements the STANDARD rule-based physics for rainwater collection.,

    Inherits from SIMPLE and adds:
    - First flush diversion losses
    - Multi-stage filtration efficiency,
    """

    def rule_based_generate(self, t: int, profile_value: float) -> float:
        """
        Implement STANDARD rainwater collection physics with first flush diversion.,

        First applies SIMPLE physics, then adds STANDARD-specific effects.,
        """
        # 1. Get the baseline result from SIMPLE physics
        collection_after_simple = super().rule_based_generate(t, profile_value)

        # 2. Add STANDARD-specific physics: first flush diversion
        first_flush = getattr(self.params.technical, "first_flush_diversion", None)
        if first_flush and profile_value > 0:
            # Simplified first flush loss (assumes some rain is diverted)
            # In practice, this would track cumulative rainfall
            first_flush_loss_factor = min(0.1, first_flush / profile_value) if profile_value > 0 else 0
            collection_after_simple = collection_after_simple * (1 - first_flush_loss_factor)

        # 3. Add filtration stage losses
        filtration_stages = getattr(self.params.technical, "filtration_stages", None)
        if filtration_stages:
            # Apply combined filtration efficiency
            total_filtration_eff = 1.0
            for stage, efficiency in filtration_stages.items():
                total_filtration_eff *= efficiency
            collection_after_simple = collection_after_simple * total_filtration_eff

        return max(0.0, collection_after_simple)


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================,


class RainwaterSourceOptimizationSimple(BaseGenerationOptimization):
    """Implements the SIMPLE MILP optimization constraints for rainwater source.,

    This is the baseline optimization strategy providing:
    - Basic rainwater collection based on rainfall profile
    - Simple runoff coefficient and efficiency
    - No first flush or filtration losses,
    """

    def __init__(self, params, component_instance) -> None:
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for rainwater source optimization.,

        Returns constraints for basic rainwater collection without losses.,
        """
        constraints = []
        comp = self.component

        if comp.Q_out is not None and hasattr(comp, "profile"):
            # Core rainwater source constraints
            N = comp.Q_out.shape[0]

            for t in range(N):
                # Handle profile bounds,
                if t < len(comp.profile):
                    rainfall_t = comp.profile[t]
                else:
                    rainfall_t = comp.profile[-1] if len(comp.profile) > 0 else 0

                # SIMPLE MODEL: Basic collection calculation
                area_m2 = comp.technical.catchment_area_m2
                runoff_coeff = comp.technical.runoff_coefficient
                efficiency = comp.technical.efficiency_nominal

                # Basic collection calculation
                raw_collection = rainfall_t * area_m2 * runoff_coeff * efficiency / 1000
                available_collection = min(raw_collection, comp.technical.capacity_nominal)

                # Collection constraint: output = available collection
                constraints.append(comp.Q_out[t] <= available_collection)

            # Maximum capacity constraint,
            constraints.append(comp.Q_out <= comp.technical.capacity_nominal)

        return constraints


class RainwaterSourceOptimizationStandard(RainwaterSourceOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for rainwater source.,

    Inherits from SIMPLE and adds:
    - First flush diversion losses
    - Multi-stage filtration efficiency
    - More realistic water quality modeling,
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for rainwater source optimization.,

        Adds first flush and filtration losses to the constraints.,
        """
        constraints = []
        comp = self.component

        if comp.Q_out is not None and hasattr(comp, "profile"):
            # Core rainwater source constraints
            N = comp.Q_out.shape[0]

            for t in range(N):
                # Handle profile bounds,
                if t < len(comp.profile):
                    rainfall_t = comp.profile[t]
                else:
                    rainfall_t = comp.profile[-1] if len(comp.profile) > 0 else 0

                # Start with SIMPLE collection calculation
                area_m2 = comp.technical.catchment_area_m2
                runoff_coeff = comp.technical.runoff_coefficient
                efficiency = comp.technical.efficiency_nominal

                # Basic collection calculation
                raw_collection = rainfall_t * area_m2 * runoff_coeff * efficiency / 1000
                available_collection = min(raw_collection, comp.technical.capacity_nominal)

                # STANDARD ENHANCEMENTS: First flush diversion
                first_flush = getattr(comp.technical, "first_flush_diversion", None)
                if first_flush and rainfall_t > 0:
                    first_flush_loss = min(0.1, first_flush / rainfall_t) if rainfall_t > 0 else 0
                    available_collection = available_collection * (1 - first_flush_loss)

                # STANDARD ENHANCEMENTS: Multi-stage filtration
                filtration_stages = getattr(comp.technical, "filtration_stages", None)
                if filtration_stages:
                    total_filtration_eff = 1.0
                    for stage, eff in filtration_stages.items():
                        total_filtration_eff *= eff
                    available_collection = available_collection * total_filtration_eff

                # Collection constraint with enhanced losses,
                constraints.append(comp.Q_out[t] <= available_collection)

            # Maximum capacity constraint,
            constraints.append(comp.Q_out <= comp.technical.capacity_nominal)

        return constraints


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================


@register_component("RainwaterSource")
class RainwaterSource(Component):
    """Rainwater harvesting source component with Strategy Pattern architecture.,

    This class acts as a factory and container for rainwater source strategies:
    - Physics strategies: Handle fidelity-specific rule-based collection calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only,

    The component delegates physics and optimization to strategy objects,
    based on the configured fidelity level.,
    """

    PARAMS_MODEL = RainwaterSourceParams

    def _post_init(self) -> None:
        """Initialize rainwater source attributes and strategy objects."""
        self.type = "generation"
        self.medium = "water"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as rainwater source expects (m³/h, m²),
        self.Q_max = tech.capacity_nominal  # m³/h max collection capacity
        self.catchment_area_m2 = tech.catchment_area_m2
        self.runoff_coefficient = tech.runoff_coefficient
        self.collection_efficiency = tech.efficiency_nominal

        # Store rainwater source-specific parameters,
        self.collection_system_type = tech.collection_system_type
        self.first_flush_diversion = tech.first_flush_diversion
        self.filtration_stages = tech.filtration_stages
        self.seasonal_collection_factors = tech.seasonal_collection_factors
        self.water_quality_model = tech.water_quality_model

        # Profile should be assigned by the system/builder after initialization
        # Initialize as None, will be set later by profile assignment,
        self.profile = None

        # CVXPY variables (for MILP solver),
        self.Q_out = None

        # STRATEGY PATTERN: Instantiate the correct strategies,
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return RainwaterSourcePhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return RainwaterSourcePhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later),
            return RainwaterSourcePhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later),
            return RainwaterSourcePhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for RainwaterSource: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return RainwaterSourceOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return RainwaterSourceOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later),
            return RainwaterSourceOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later),
            return RainwaterSourceOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for RainwaterSource optimization: {fidelity}")

    def rule_based_generate(self, t: int) -> float:
        """
        Delegate to physics strategy for collection calculation.,

        This maintains the same interface as BaseGenerationComponent but,
        delegates the actual physics calculation to the strategy object.,
        """
        # Check bounds,
        if not hasattr(self, "profile") or self.profile is None or t >= len(self.profile):
            return 0.0

        # Get rainfall intensity for this timestep (mm/h)
        rainfall_intensity = self.profile[t]

        # Delegate to physics strategy
        collection_output = self.physics.rule_based_generate(t, rainfall_intensity)

        # Log for debugging if needed,
        if t == 0 and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"{self.name} at t={t}: rainfall={rainfall_intensity:.3f}mm/h, ",
                f"collection={collection_output:.3f}m³/h",
            )

        return collection_output

    def add_optimization_vars(self, N: int | None = None) -> None:
        """Create CVXPY optimization variables."""
        if N is None:
            N = self.N

        self.Q_out = cp.Variable(N, name=f"{self.name}_Q_out", nonneg=True)

        # Add as flow,
        self.flows["source"]["Q_out"] = ({"type": "water", "value": self.Q_out, "profile": self.profile},)

    def set_constraints(self) -> list:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()

    def rule_based_operation(self, t: int) -> float:
        """Rule-based rainwater collection operation with fidelity-aware performance."""
        return self.rule_based_generate(t)

    def __repr__(self) -> None:
        """String representation."""
        return (
            f"RainwaterSource(name='{self.name}', ",
            f"area={self.catchment_area_m2}m², ",
            f"max_collection={self.Q_max}m³/h, ",
            f"fidelity={self.technical.fidelity_level.value})",
        )
