"""Solar PV component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import GenerationTechnicalParams, FidelityLevel
from ..shared.base_classes import BaseGenerationComponent

logger = logging.getLogger(__name__)


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
    panel_efficiency: Optional[float] = Field(
        0.20,
        description="Panel efficiency at STC"
    )
    inverter_efficiency: Optional[float] = Field(
        0.98,
        description="DC to AC conversion efficiency"
    )

    # DETAILED fidelity parameters
    temperature_coefficient: Optional[float] = Field(
        None,
        description="Power temperature coefficient [%/°C]"
    )
    degradation_rate_annual: Optional[float] = Field(
        None,
        description="Annual degradation rate [%/year]"
    )
    soiling_factor: Optional[float] = Field(
        None,
        description="Soiling derating factor"
    )

    # RESEARCH fidelity parameters
    spectral_model: Optional[Dict[str, Any]] = Field(
        None,
        description="Spectral irradiance model parameters"
    )
    bifacial_gain: Optional[float] = Field(
        None,
        description="Bifacial module gain factor"
    )


class SolarPVParams(ComponentParams):
    """Solar PV parameters using the hierarchical technical parameter system.

    Profile data should be provided separately through the system's
    profile loading mechanism, not as a component parameter.
    """
    technical: SolarPVTechnicalParams = Field(
        default_factory=lambda: SolarPVTechnicalParams(
            capacity_nominal=10.0,  # Default 10 kW
            efficiency_nominal=1.0,  # Solar uses profile * capacity
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("SolarPV")
class SolarPV(BaseGenerationComponent):
    """Solar PV generation component with CVXPY optimization support."""

    PARAMS_MODEL = SolarPVParams

    def _post_init(self):
        """Initialize solar PV-specific attributes from technical parameters.

        Profile data is now loaded separately by the system, not from parameters.
        """
        self.type = "generation"
        self.medium = "electricity"

        # Single source of truth: the technical parameter block
        tech = self.technical

        # Core parameters extracted from technical block
        self.P_max = tech.capacity_nominal  # kW

        # Store advanced parameters for fidelity-aware constraints
        self.panel_efficiency = tech.panel_efficiency
        self.inverter_efficiency = tech.inverter_efficiency
        self.temperature_coefficient = tech.temperature_coefficient
        self.degradation_rate = tech.degradation_rate_annual

        # EXPLICIT FIDELITY CONTROL
        self.fidelity_level = tech.fidelity_level

        # Profile should be assigned by the system/builder
        # Initialize as None, will be set by assign_profiles
        if not hasattr(self, 'profile') or self.profile is None:
            logger.warning(f"No generation profile assigned to {self.name}. Using zero output.")
            self.profile = np.zeros(getattr(self, 'N', 24))
        else:
            self.profile = np.array(self.profile)

        # CVXPY variable (created later by add_optimization_vars)
        self.P_out = None

    # rule_based_generate() method is now inherited from BaseGenerationComponent
    # No need to override - the base implementation handles profile * P_max logic

    def add_optimization_vars(self, N: int):
        """Create CVXPY optimization variables."""
        # For solar, output is fixed by profile
        self.P_out = cp.Variable(N, name=f'{self.name}_P_out', nonneg=True)

        # Add as flow
        self.flows['source']['P_out'] = {
            'type': 'electricity',
            'value': self.P_out,
            'profile': self.profile
        }

    def set_constraints(self) -> List:
        """Set CVXPY constraints for solar generation with fidelity-aware modeling.

        Constraint complexity scales with fidelity level:
        - SIMPLE: Basic output = profile * capacity
        - STANDARD: Add inverter efficiency
        - DETAILED: Add temperature and degradation effects
        - RESEARCH: Full spectral and bifacial modeling
        """
        constraints = []

        if self.P_out is not None:
            # Get fidelity level
            fidelity = getattr(self, 'fidelity_level', FidelityLevel.STANDARD)

            # --- SIMPLE MODEL (OG Systemiser baseline) ---
            # Direct profile scaling: P_out = profile * P_max
            effective_generation = self.profile * self.P_max

            # --- STANDARD ENHANCEMENTS (additive on top of SIMPLE) ---
            if fidelity >= FidelityLevel.STANDARD:
                # Inverter efficiency (DC to AC conversion losses)
                if self.inverter_efficiency:
                    effective_generation = effective_generation * self.inverter_efficiency
                    logger.debug("STANDARD: Applied inverter efficiency to solar")

            # --- DETAILED ENHANCEMENTS (additive on top of STANDARD) ---
            if fidelity >= FidelityLevel.DETAILED:
                # Temperature derating
                if self.temperature_coefficient is not None:
                    if hasattr(self, 'system') and hasattr(self.system, 'profiles'):
                        if 'ambient_temperature' in self.system.profiles:
                            temp = self.system.profiles['ambient_temperature']
                            # Temperature derating (reference = 25°C)
                            temp_factor = 1 + (temp - 25) * self.temperature_coefficient / 100
                            effective_generation = effective_generation * temp_factor
                            logger.debug("DETAILED: Applied temperature derating to solar")

                # Annual degradation
                if self.degradation_rate is not None:
                    # Simple linear degradation over time
                    N = len(self.profile)
                    time_years = np.arange(N) / (365 * 24)  # Convert hours to years
                    degradation_factor = 1 - time_years * self.degradation_rate / 100
                    effective_generation = effective_generation * degradation_factor
                    logger.debug("DETAILED: Applied degradation to solar")

            # --- RESEARCH ENHANCEMENTS (additive on top of DETAILED) ---
            if fidelity >= FidelityLevel.RESEARCH:
                logger.debug("RESEARCH: Full spectral modeling would modify effective generation")
                # In practice: effective_generation = apply_spectral_model(effective_generation)
                # In practice: effective_generation = apply_bifacial_effects(effective_generation)

            # Apply the generation constraint with all fidelity enhancements
            constraints.append(self.P_out == effective_generation)

        return constraints

    def rule_based_generate(self, t: int) -> float:
        """Generate power in rule-based mode."""
        if t >= len(self.profile):
            return 0.0
        return self.profile[t] * self.P_max