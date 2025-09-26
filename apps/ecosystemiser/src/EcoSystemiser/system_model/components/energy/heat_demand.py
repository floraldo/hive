"""Heat demand component with MILP optimization support and hierarchical fidelity."""
import cvxpy as cp
import numpy as np
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from ..shared.registry import register_component
from ..shared.component import Component, ComponentParams
from ..shared.archetypes import DemandTechnicalParams, FidelityLevel
from ..shared.base_classes import BaseDemandComponent

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
            peak_demand=5.0,  # Default 5 kW peak heat demand
            load_profile_type="variable",
            fidelity_level=FidelityLevel.STANDARD
        ),
        description="Technical parameters following the hierarchical archetype system"
    )


@register_component("HeatDemand")
class HeatDemand(BaseDemandComponent):
    """Heat demand component representing thermal energy consumption."""

    PARAMS_MODEL = HeatDemandParams

    def _post_init(self):
        """Initialize heat demand-specific attributes from technical parameters.

        Profile data is now loaded separately by the system, not from parameters.
        """
        self.type = "consumption"
        self.medium = "heat"

        # Single source of truth: the technical parameter block
        tech = self.technical

        # Core parameters extracted from technical block
        self.H_max = tech.peak_demand  # kW
        self.P_max = tech.peak_demand  # Alias for compatibility with BaseDemandComponent

        # Store advanced parameters for fidelity-aware constraints
        self.demand_type = tech.demand_type
        self.temperature_requirement = tech.temperature_requirement
        self.thermal_comfort_band = tech.thermal_comfort_band
        self.building_thermal_mass = tech.building_thermal_mass
        self.weather_dependency = tech.weather_dependency
        self.occupancy_schedule = tech.occupancy_schedule
        self.demand_response_capability = tech.demand_response_capability

        # EXPLICIT FIDELITY CONTROL
        self.fidelity_level = tech.fidelity_level

        # Profile should be assigned by the system/builder
        if not hasattr(self, 'profile') or self.profile is None:
            logger.warning(f"No heat demand profile assigned to {self.name}. Using zero demand.")
            self.profile = np.zeros(getattr(self, 'N', 24))
        else:
            self.profile = np.array(self.profile)

        # Legacy compatibility: also set H_profile
        self.H_profile = self.profile

        # CVXPY variables (created later by add_optimization_vars)
        self.H_in = None

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
        """Set CVXPY constraints for heat demand with fidelity-aware modeling.

        Constraint complexity scales with fidelity level:
        - SIMPLE: Demand must be met exactly
        - STANDARD: Add thermal comfort bands and building inertia
        - DETAILED: Add weather correlation and demand response
        - RESEARCH: Full building physics and behavioral modeling
        """
        constraints = []
        N = self.H_in.shape[0] if self.H_in is not None else 0

        if self.H_in is not None:
            # Get fidelity level
            fidelity = getattr(self, 'fidelity_level', FidelityLevel.STANDARD)

            # Heat demand constraints with progressive enhancement
            for t in range(N):
                # Handle profile bounds
                if t < len(self.profile):
                    base_demand_t = self.profile[t] * self.H_max
                else:
                    base_demand_t = self.profile[-1] * self.H_max if len(self.profile) > 0 else 0

                # --- SIMPLE MODEL (OG Systemiser baseline) ---
                # Fixed heat demand: H_in = profile * H_max (demand must be met exactly)
                demand_min = base_demand_t
                demand_max = base_demand_t

                # --- STANDARD ENHANCEMENTS (additive on top of SIMPLE) ---
                if fidelity >= FidelityLevel.STANDARD:
                    # Thermal comfort bands allow some flexibility
                    if self.thermal_comfort_band is not None:
                        comfort_flexibility = 0.1  # 10% flexibility for thermal comfort
                        demand_min = base_demand_t * (1 - comfort_flexibility)
                        demand_max = base_demand_t * (1 + comfort_flexibility)
                        logger.debug("STANDARD: Applied thermal comfort flexibility to heat demand")

                # --- DETAILED ENHANCEMENTS (additive on top of STANDARD) ---
                if fidelity >= FidelityLevel.DETAILED:
                    # Demand response capabilities
                    if self.demand_response_capability is not None:
                        shift_capacity = self.demand_response_capability.get('shift_capacity', 0)
                        shed_capacity = self.demand_response_capability.get('shed_capacity', 0)

                        # Expand flexibility bounds for demand response
                        demand_min = base_demand_t * (1 - shed_capacity)
                        demand_max = base_demand_t * (1 + shift_capacity)
                        logger.debug("DETAILED: Added demand response capabilities to heat demand")

                # --- RESEARCH ENHANCEMENTS (additive on top of DETAILED) ---
                if fidelity >= FidelityLevel.RESEARCH:
                    logger.debug("RESEARCH: Building physics modeling would modify demand bounds")
                    # In practice: demand_min/max = apply_building_physics(demand_min, demand_max, weather, occupancy)

                # Apply heat demand constraints with all fidelity enhancements
                if demand_min == demand_max:
                    # Exact demand satisfaction (SIMPLE, or no flexibility parameters)
                    constraints.append(self.H_in[t] == demand_max)
                else:
                    # Flexible demand bounds (STANDARD+, with flexibility parameters)
                    constraints.append(self.H_in[t] >= demand_min)
                    constraints.append(self.H_in[t] <= demand_max)

            # DETAILED: Building thermal mass constraints (global, not per-timestep)
            if fidelity >= FidelityLevel.DETAILED and self.building_thermal_mass is not None:
                logger.debug("DETAILED: Building thermal mass constraints would be added here")
                # In practice, this would require temperature state variables and thermal dynamics

        return constraints

    def rule_based_consumption(self, t: int) -> float:
        """Get heat demand at time t for rule-based operation with fidelity awareness."""
        if t >= len(self.profile):
            return 0.0

        # Base demand from profile
        base_demand = self.profile[t] * self.H_max

        # Apply weather dependency if available
        if self.weather_dependency and hasattr(self, 'system'):
            if hasattr(self.system, 'profiles') and 'ambient_temperature' in self.system.profiles:
                temp = self.system.profiles['ambient_temperature'][t] if t < len(self.system.profiles['ambient_temperature']) else 20
                # Simple weather correlation: higher demand at lower temperatures
                temp_factor = self.weather_dependency.get('temperature_factor', 0.05)
                reference_temp = self.weather_dependency.get('reference_temp', 18)
                weather_multiplier = 1 + temp_factor * (reference_temp - temp)
                base_demand = base_demand * max(0.1, weather_multiplier)  # Minimum 10% of base

        return base_demand