"""Generic Technical Parameter Archetypes for Component Categories.

This module defines ONLY the abstract, high-level archetype parameter models
that are common to entire categories of components (storage, generation, etc.).

Specific component parameters (e.g., BatteryTechnicalParams) are defined
in their respective component files, following the co-location principle.

The hierarchy follows: Base → Category Archetypes
Specific models inherit from these archetypes in their component files.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from enum import Enum


class FidelityLevel(str, Enum):
    """Fidelity levels for simulation accuracy vs speed trade-offs.

    Explicit fidelity control enables users to consciously choose
    the trade-off between computational speed and model accuracy.
    """
    SIMPLE = "simple"      # Fast, basic constraints only
    STANDARD = "standard"  # Normal operation, most constraints (default)
    DETAILED = "detailed"  # High-fidelity with advanced models
    RESEARCH = "research"  # Maximum fidelity for research studies

    def __ge__(self, other):
        """Enable comparison: self >= other."""
        if not isinstance(other, FidelityLevel):
            return NotImplemented
        order = [self.SIMPLE, self.STANDARD, self.DETAILED, self.RESEARCH]
        return order.index(self.value) >= order.index(other.value)

    def __gt__(self, other):
        """Enable comparison: self > other."""
        if not isinstance(other, FidelityLevel):
            return NotImplemented
        order = [self.SIMPLE, self.STANDARD, self.DETAILED, self.RESEARCH]
        return order.index(self.value) > order.index(other.value)

    def __le__(self, other):
        """Enable comparison: self <= other."""
        if not isinstance(other, FidelityLevel):
            return NotImplemented
        return not self.__gt__(other)

    def __lt__(self, other):
        """Enable comparison: self < other."""
        if not isinstance(other, FidelityLevel):
            return NotImplemented
        order = [self.SIMPLE, self.STANDARD, self.DETAILED, self.RESEARCH]
        return order.index(self.value) < order.index(other.value)


# =============================================================================
# BASE TECHNICAL PARAMETERS
# =============================================================================

class BaseTechnicalParams(BaseModel):
    """Universal technical parameters for all components.

    These parameters are always required and form the foundation
    of any component model, regardless of fidelity level.
    """
    capacity_nominal: float = Field(..., description="Nameplate rating (e.g., kW, kWh, m³/h)")
    lifetime_years: float = Field(20.0, description="Expected operational lifetime [years]")
    availability_factor: float = Field(1.0, description="Fraction of time component is available")

    # Explicit fidelity control (required for all components)
    fidelity_level: FidelityLevel = Field(
        default=FidelityLevel.STANDARD,
        description="Explicit simulation fidelity level controlling model complexity"
    )

    class Config:
        extra = "allow"  # Allow additional fields for future extensions


# =============================================================================
# STORAGE CATEGORY PARAMETERS
# =============================================================================

class StorageTechnicalParams(BaseTechnicalParams):
    """Generic parameters common to ALL storage components.

    This archetype defines only the fundamental parameters that every
    storage device (battery, thermal storage, water tank) must have.
    Specific storage types extend this with their own parameters.
    """
    efficiency_roundtrip: float = Field(0.90, description="Round-trip efficiency")
    soc_min: float = Field(0.0, description="Minimum state of charge [fraction]")
    soc_max: float = Field(1.0, description="Maximum state of charge [fraction]")
    initial_soc_pct: float = Field(0.5, description="Initial state of charge [fraction]")


# NOTE: Specific storage types (BatteryTechnicalParams, ThermalStorageTechnicalParams, etc.)
# are defined in their respective component files following the co-location principle.
# For example:
# - BatteryTechnicalParams is in components/energy/battery.py
# - ThermalStorageTechnicalParams is in components/energy/heat_buffer.py


# =============================================================================
# GENERATION CATEGORY PARAMETERS
# =============================================================================

class GenerationTechnicalParams(BaseTechnicalParams):
    """Generic parameters common to ALL generation components.

    This archetype covers solar, wind, and other generation types.
    Specific generators extend this with their own parameters.
    """
    efficiency_nominal: float = Field(0.85, description="Nominal conversion efficiency")
    min_load_factor: float = Field(0.0, description="Minimum operating load [fraction]")


# NOTE: Specific generation types (SolarPVTechnicalParams, WindTurbineTechnicalParams, etc.)
# are defined in their respective component files following the co-location principle.
# For example:
# - SolarPVTechnicalParams is in components/energy/solar_pv.py
# - WindTurbineTechnicalParams is in components/energy/wind_turbine.py


# =============================================================================
# CONVERSION CATEGORY PARAMETERS
# =============================================================================

class ConversionTechnicalParams(BaseTechnicalParams):
    """Generic parameters common to ALL conversion components.

    This archetype covers heat pumps, boilers, and other converters.
    Specific converters extend this with their own parameters.
    """
    efficiency_nominal: float = Field(0.90, description="Nominal conversion efficiency")
    input_medium: str = Field("electricity", description="Input energy medium")
    output_medium: str = Field("heat", description="Output energy medium")


# NOTE: Specific conversion types (HeatPumpTechnicalParams, ElectricBoilerTechnicalParams, etc.)
# are defined in their respective component files following the co-location principle.
# For example:
# - HeatPumpTechnicalParams is in components/energy/heat_pump.py
# - ElectricBoilerTechnicalParams is in components/energy/electric_boiler.py


# =============================================================================
# TRANSMISSION CATEGORY PARAMETERS
# =============================================================================

class TransmissionTechnicalParams(BaseTechnicalParams):
    """Generic parameters common to ALL transmission/grid components.

    This archetype covers grid connections and transmission lines.
    """
    max_import: float = Field(float('inf'), description="Maximum import capacity [kW]")
    max_export: float = Field(float('inf'), description="Maximum export capacity [kW]")


# =============================================================================
# DEMAND CATEGORY PARAMETERS
# =============================================================================

class DemandTechnicalParams(BaseTechnicalParams):
    """Generic parameters common to ALL demand components.

    This archetype covers electrical, thermal, and water demands.
    """
    peak_demand: float = Field(0.0, description="Peak demand [kW or m³/h]")
    load_profile_type: str = Field("variable", description="Profile type (fixed, variable, stochastic)")


# =============================================================================
# WATER SYSTEM PARAMETERS
# =============================================================================

# NOTE: Water domain archetypes are defined when water components are added.
# The pattern follows the same principle: generic archetype here,
# specific models in component files.


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_fidelity_consistency(components: List[BaseTechnicalParams]) -> bool:
    """Check if all components have consistent fidelity levels.

    This is useful for ensuring a simulation uses consistent fidelity
    across all components, though mixed fidelity is also supported.

    Args:
        components: List of component technical parameters

    Returns:
        True if fidelity levels are consistent
    """
    if not components:
        return True

    fidelity_levels = [c.fidelity_level for c in components if hasattr(c, 'fidelity_level')]

    if not fidelity_levels:
        return True

    # Check if all components have the same fidelity level
    return len(set(fidelity_levels)) == 1