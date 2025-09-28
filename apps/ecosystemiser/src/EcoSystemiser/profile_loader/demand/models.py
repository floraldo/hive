"""
Demand profile data models.

This module defines data structures specific to demand/load profiles
for electricity, heating, cooling, and other energy demands.
"""

from typing import Dict, List, Literal, Optional, Tuple, Any
from pydantic import BaseModel, Field
from ecosystemiser.profile_loader.shared.models import BaseProfileRequest, BaseProfileResponse, ProfileMode


# Demand types
DemandType = Literal[
    "electricity",
    "heating", 
    "cooling",
    "hot_water",
    "process_heat",
    "total_energy"
]

# Building types for standard profiles
BuildingType = Literal[
    "residential_single",
    "residential_multi",
    "office",
    "retail",
    "industrial",
    "warehouse",
    "school",
    "hospital",
    "hotel",
    "restaurant",
    "data_center",
    "mixed_use"
]


class DemandRequest(BaseProfileRequest):
    """
    Request for demand profile data.
    
    Extends BaseProfileRequest with demand-specific parameters.
    """
    # Demand-specific fields
    demand_type: DemandType = "electricity"
    
    # Building characteristics (for standard profiles)
    building_type: Optional[BuildingType] = None
    floor_area_m2: Optional[float] = None
    occupancy: Optional[int] = None
    
    # Override base class defaults for typical demand variables
    variables: List[str] = Field(
        default_factory=lambda: ["power_kw", "energy_kwh"]
    )
    
    # Demand-specific sources
    source: Optional[Literal[
        "standard_profile",  # Standard load profiles
        "smart_meter",      # Smart meter data
        "scada",           # SCADA system data
        "simulation",      # Building simulation
        "benchmark"        # Benchmark profiles
    ]] = None
    
    # Scaling/normalization options
    normalize: bool = False
    scale_factor: Optional[float] = None
    
    # Day type filtering
    day_types: Optional[List[Literal["weekday", "weekend", "holiday"]]] = None


class DemandResponse(BaseProfileResponse):
    """
    Response containing demand profile data.
    
    Extends BaseProfileResponse with demand-specific metrics.
    """
    # Demand-specific metrics
    peak_demand_kw: Optional[float] = None
    total_energy_kwh: Optional[float] = None
    load_factor: Optional[float] = None
    
    # Time-of-use breakdown
    tou_breakdown: Optional[Dict[str, float]] = None  # peak, off-peak, shoulder
    
    # Demand statistics
    demand_stats: Optional[Dict[str, Any]] = None


# Common demand profile variables
DEMAND_VARIABLES = {
    # Power/demand variables
    "power_kw": {"unit": "kW", "type": "state"},
    "power_mw": {"unit": "MW", "type": "state"},
    "reactive_power_kvar": {"unit": "kVAR", "type": "state"},
    "apparent_power_kva": {"unit": "kVA", "type": "state"},
    
    # Energy variables
    "energy_kwh": {"unit": "kWh", "type": "cumulative"},
    "energy_mwh": {"unit": "MWh", "type": "cumulative"},
    
    # Thermal demands
    "heating_demand_kw": {"unit": "kW", "type": "state"},
    "cooling_demand_kw": {"unit": "kW", "type": "state"},
    "hot_water_demand_kw": {"unit": "kW", "type": "state"},
    
    # Grid interaction
    "import_kw": {"unit": "kW", "type": "state"},
    "export_kw": {"unit": "kW", "type": "state"},
    "net_demand_kw": {"unit": "kW", "type": "state"},
    
    # Power quality
    "voltage_v": {"unit": "V", "type": "state"},
    "current_a": {"unit": "A", "type": "state"},
    "power_factor": {"unit": "dimensionless", "type": "state"},
    "frequency_hz": {"unit": "Hz", "type": "state"},
}