"""Solar PV component with MILP optimization support and hierarchical fidelity."""

import logging
from typing import Any, Dict, List, Optional

import cvxpy as cp
import numpy as np
from ecosystemiser.system_model.components.shared.archetypes import (
    FidelityLevel,
    GenerationTechnicalParams,
)
from ecosystemiser.system_model.components.shared.base_classes import (
    BaseGenerationOptimization,
    BaseGenerationPhysics,
)
from ecosystemiser.system_model.components.shared.component import (
    Component,
    ComponentParams,
)
from ecosystemiser.system_model.components.shared.registry import register_component
from hive_logging import get_logger
from pydantic import BaseModel, Field

logger = get_logger(__name__)

# =============================================================================
# SOLAR PV-SPECIFIC TECHNICAL PARAMETERS (Co-located with component)
# =============================================================================


class SolarPVTechnicalParams(GenerationTechnicalParams):
    """Solar PV-specific technical parameters extending generation archetype.

    This model inherits from GenerationTechnicalParams and adds solar-specific
    parameters for different fidelity levels.
    """

    # Basic solar parameters (always used)
    technology: str = Field("monocrystalline", description="PV technology type")

    # STANDARD fidelity additions
    panel_efficiency: Optional[float] = Field(0.20, description="Panel efficiency at STC")
    inverter_efficiency: Optional[float] = Field(0.98, description="DC to AC conversion efficiency")

    # DETAILED fidelity parameters
    temperature_coefficient: Optional[float] = Field(None, description="Power temperature coefficient [%/°C]")
    degradation_rate_annual: Optional[float] = Field(None, description="Annual degradation rate [%/year]")
    soiling_factor: Optional[float] = Field(None, description="Soiling derating factor")

    # RESEARCH fidelity parameters
    spectral_model: Optional[Dict[str, Any]] = Field(None, description="Spectral irradiance model parameters")
    bifacial_gain: Optional[float] = Field(None, description="Bifacial module gain factor")


class SolarPVParams(ComponentParams):
    """Solar PV parameters using the hierarchical technical parameter system.

    Profile data should be provided separately through the system's
    profile loading mechanism, not as a component parameter.
    """

    technical: SolarPVTechnicalParams = Field(
        default_factory=lambda: SolarPVTechnicalParams(
            capacity_nominal=10.0,  # Default 10 kW
            efficiency_nominal=1.0,  # Solar uses profile * capacity
            fidelity_level=FidelityLevel.STANDARD,
        ),
        description="Technical parameters following the hierarchical archetype system",
    )


# =============================================================================
# PHYSICS STRATEGIES (Rule-Based & Fidelity)
# =============================================================================


class SolarPVPhysicsSimple(BaseGenerationPhysics):
    """Implements the SIMPLE rule-based physics for a solar PV system.

    This is the baseline fidelity level providing:
    - Basic generation: P_out = profile * P_max
    - Direct profile scaling with nominal capacity
    """

    def rule_based_generate(self, t: int, profile_value: float) -> float:
        """
        Implement SIMPLE solar PV physics with direct profile scaling.

        This matches the exact logic from BaseGenerationComponent for numerical equivalence.
        """
        # Get maximum capacity
        P_max = self.params.technical.capacity_nominal

        # Base generation: profile value * maximum capacity
        # Profile should be normalized (0-1), P_max provides scaling
        base_output = profile_value * P_max

        return max(0.0, base_output)


class SolarPVPhysicsStandard(SolarPVPhysicsSimple):
    """Implements the STANDARD rule-based physics for a solar PV system.

    Inherits from SIMPLE and adds:
    - Inverter efficiency (DC to AC conversion losses)
    - More realistic power conversion modeling
    """

    def rule_based_generate(self, t: int, profile_value: float) -> float:
        """
        Implement STANDARD solar PV physics with inverter efficiency.

        First applies SIMPLE physics, then adds STANDARD-specific effects.
        """
        # 1. Get the baseline result from SIMPLE physics
        generation_after_simple = super().rule_based_generate(t, profile_value)

        # 2. Add STANDARD-specific physics: inverter efficiency
        inverter_efficiency = getattr(self.params.technical, "inverter_efficiency", 0.98)

        # Apply inverter efficiency (DC to AC conversion)
        final_generation = generation_after_simple * inverter_efficiency

        return max(0.0, final_generation)


# =============================================================================
# OPTIMIZATION STRATEGY (MILP)
# =============================================================================


class SolarPVOptimizationSimple(BaseGenerationOptimization):
    """Implements the SIMPLE MILP optimization constraints for solar PV.

    This is the baseline optimization strategy providing:
    - Direct profile scaling: P_out = profile * P_max
    - No efficiency losses or degradation
    """

    def __init__(self, params, component_instance):
        """Initialize with both params and component instance for constraint access."""
        super().__init__(params)
        self.component = component_instance

    def set_constraints(self) -> list:
        """
        Create SIMPLE CVXPY constraints for solar PV optimization.

        Returns constraints for basic solar generation without losses.
        """
        constraints = []
        comp = self.component

        if comp.P_out is not None and hasattr(comp, "profile"):
            # SIMPLE MODEL: Direct profile scaling
            # P_out = profile * P_max
            effective_generation = comp.profile * comp.P_max

            # Apply the generation constraint
            constraints.append(comp.P_out == effective_generation)

        return constraints


class SolarPVOptimizationStandard(SolarPVOptimizationSimple):
    """Implements the STANDARD MILP optimization constraints for solar PV.

    Inherits from SIMPLE and adds:
    - Inverter efficiency (DC to AC conversion losses)
    - More realistic power conversion modeling
    """

    def set_constraints(self) -> list:
        """
        Create STANDARD CVXPY constraints for solar PV optimization.

        Adds inverter efficiency to the generation constraints.
        """
        constraints = []
        comp = self.component

        if comp.P_out is not None and hasattr(comp, "profile"):
            # Start with SIMPLE model: profile * P_max
            effective_generation = comp.profile * comp.P_max

            # STANDARD enhancement: add inverter efficiency
            inverter_efficiency = getattr(comp.technical, "inverter_efficiency", 0.98)
            effective_generation = effective_generation * inverter_efficiency

            # Apply the generation constraint with efficiency losses
            constraints.append(comp.P_out == effective_generation)

        return constraints


# =============================================================================
# MAIN COMPONENT CLASS (Factory)
# =============================================================================


@register_component("SolarPV")
class SolarPV(Component):
    """Solar PV generation component with Strategy Pattern architecture.

    This class acts as a factory and container for solar PV strategies:
    - Physics strategies: Handle fidelity-specific rule-based generation calculations
    - Optimization strategies: Handle MILP constraint generation
    - Clean separation: Data contract + strategy selection only

    The component delegates physics and optimization to strategy objects
    based on the configured fidelity level.
    """

    PARAMS_MODEL = SolarPVParams

    def _post_init(self):
        """Initialize solar PV attributes and strategy objects."""
        self.type = "generation"
        self.medium = "electricity"

        # Extract parameters from technical block
        tech = self.technical

        # Core parameters - EXACTLY as original solar PV expects
        self.P_max = tech.capacity_nominal  # kW

        # Store solar-specific parameters
        self.panel_efficiency = tech.panel_efficiency
        self.inverter_efficiency = tech.inverter_efficiency
        self.temperature_coefficient = tech.temperature_coefficient
        self.degradation_rate = tech.degradation_rate_annual

        # Profile should be assigned by the system/builder after initialization
        # Initialize as None, will be set later by profile assignment
        self.profile = None

        # CVXPY variable (for MILP solver)
        self.P_out = None

        # STRATEGY PATTERN: Instantiate the correct strategies
        self.physics = self._get_physics_strategy()
        self.optimization = self._get_optimization_strategy()

    def _get_physics_strategy(self):
        """Factory method: Select physics strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return SolarPVPhysicsSimple(self.params)
        elif fidelity == FidelityLevel.STANDARD:
            return SolarPVPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD physics (can be extended later)
            return SolarPVPhysicsStandard(self.params)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD physics (can be extended later)
            return SolarPVPhysicsStandard(self.params)
        else:
            raise ValueError(f"Unknown fidelity level for SolarPV: {fidelity}")

    def _get_optimization_strategy(self):
        """Factory method: Select optimization strategy based on fidelity level."""
        fidelity = self.technical.fidelity_level

        if fidelity == FidelityLevel.SIMPLE:
            return SolarPVOptimizationSimple(self.params, self)
        elif fidelity == FidelityLevel.STANDARD:
            return SolarPVOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.DETAILED:
            # For now, DETAILED uses STANDARD optimization (can be extended later)
            return SolarPVOptimizationStandard(self.params, self)
        elif fidelity == FidelityLevel.RESEARCH:
            # For now, RESEARCH uses STANDARD optimization (can be extended later)
            return SolarPVOptimizationStandard(self.params, self)
        else:
            raise ValueError(f"Unknown fidelity level for SolarPV optimization: {fidelity}")

    def rule_based_generate(self, t: int) -> float:
        """
        Delegate to physics strategy for generation calculation.

        This maintains the same interface as BaseGenerationComponent but
        delegates the actual physics calculation to the strategy object.
        """
        # Check bounds
        if not hasattr(self, "profile") or self.profile is None or t >= len(self.profile):
            return 0.0

        # Get normalized profile value for this timestep
        profile_value = self.profile[t]

        # Delegate to physics strategy
        generation_output = self.physics.rule_based_generate(t, profile_value)

        # Log for debugging if needed
        if t == 0 and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"{self.name} at t={t}: profile={profile_value:.3f}, " f"output={generation_output:.3f}kW")

        return generation_output

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        # For solar, output is fixed by profile
        self.P_out = cp.Variable(N, name=f"{self.name}_P_out", nonneg=True)

        # Add as flow
        self.flows["source"]["P_out"] = {
            "type": "electricity",
            "value": self.P_out,
            "profile": self.profile,
        }

    def set_constraints(self) -> List:
        """Delegate constraint creation to optimization strategy."""
        return self.optimization.set_constraints()
