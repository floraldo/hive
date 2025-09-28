"""Climate data models and contracts"""

from typing import Dict, List, Literal, Optional, Tuple, Any
from pydantic import BaseModel, Field
from EcoSystemiser.profile_loader.shared.models import BaseProfileRequest, BaseProfileResponse, ProfileMode

# Climate-specific types for validation
ClimateSource = Literal["nasa_power", "meteostat", "pvgis", "era5", "file_epw"]
ClimateResolution = Literal["15min", "30min", "1H", "3H", "1D"]

class ClimateRequest(BaseProfileRequest):
    """
    Climate data request extending the unified profile interface.

    Uses BaseProfileRequest for common fields and adds climate-specific parameters.
    """

    # Override base defaults with climate-specific values
    variables: List[str] = Field(
        default_factory=lambda: ["temp_air", "ghi", "dni", "dhi", "wind_speed", "rel_humidity", "precip", "cloud_cover"],
        description="Climate variables to fetch"
    )
    source: Optional[ClimateSource] = Field(
        default="nasa_power",
        description="Climate data source preference"
    )
    resolution: Optional[ClimateResolution] = Field(
        default="1H",
        description="Data temporal resolution"
    )

    # Climate-specific extensions
    subset: Optional[Dict[str, str]] = Field(
        default=None,
        description="Time subset specification: {'month':'07'} or {'start':'07-10','end':'07-24'}"
    )
    synthetic_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Options for synthetic data generation"
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible synthetic generation"
    )
    baseline_period: Optional[Tuple[str, str]] = Field(
        default=None,
        description="Baseline period for nonstationarity handling"
    )
    p_selection: Optional[int] = Field(
        default=None,
        description="Percentile selection for representative year (P50, P90, etc.)"
    )

    @property
    def mode_legacy(self) -> str:
        """Legacy mode field for backward compatibility."""
        if self.mode == ProfileMode.OBSERVED:
            return "observed"
        elif self.mode == ProfileMode.TYPICAL:
            return "tmy"
        elif self.mode == ProfileMode.AVERAGE:
            return "average"
        elif self.mode == ProfileMode.SYNTHETIC:
            return "synthetic"
        else:
            return "observed"

    @classmethod
    def from_legacy_mode(cls, mode_str: str, **kwargs):
        """Create ClimateRequest from legacy mode string."""
        mode_mapping = {
            "observed": ProfileMode.OBSERVED,
            "tmy": ProfileMode.TYPICAL,
            "average": ProfileMode.AVERAGE,
            "synthetic": ProfileMode.SYNTHETIC
        }
        kwargs["mode"] = mode_mapping.get(mode_str, ProfileMode.OBSERVED)
        return cls(**kwargs)

class ClimateResponse(BaseProfileResponse):
    manifest: Dict[str, Any]
    path_parquet: Optional[str] = None  # Made optional for cases where caching is disabled
    shape: Tuple[int, int]
    stats: Optional[Dict[str, Any]] = None  # Changed to Any to handle nested dicts

# Canonical variable mappings - Core variables available across most services
CANONICAL_VARIABLES = {
    # Temperature variables
    "temp_air": {"unit": "degC", "type": "state"},
    "temp_air_max": {"unit": "degC", "type": "state"}, 
    "temp_air_min": {"unit": "degC", "type": "state"},
    "dewpoint": {"unit": "degC", "type": "state"},
    "surface_temp": {"unit": "degC", "type": "state"},
    
    # Humidity variables
    "rel_humidity": {"unit": "%", "type": "state"},
    "specific_humidity": {"unit": "g/kg", "type": "state"},
    
    # Wind variables  
    "wind_speed": {"unit": "m/s", "type": "state"},
    "wind_speed_max": {"unit": "m/s", "type": "state"},
    "wind_gust": {"unit": "m/s", "type": "state"},
    "wind_dir": {"unit": "deg", "type": "state"},
    
    # Solar radiation variables
    "ghi": {"unit": "W/m2", "type": "state"},  # Global horizontal irradiance
    "dni": {"unit": "W/m2", "type": "state"},  # Direct normal irradiance  
    "dhi": {"unit": "W/m2", "type": "state"},  # Diffuse horizontal irradiance
    "ghi_clearsky": {"unit": "W/m2", "type": "state"},
    
    # Longwave radiation variables
    "lw_down": {"unit": "W/m2", "type": "state"},
    "lw_net": {"unit": "W/m2", "type": "state"},
    
    # Precipitation variables
    "precip": {"unit": "mm/h", "type": "flux"},
    "snow": {"unit": "mm", "type": "state"},  # Snow depth or water equivalent
    "snowfall": {"unit": "mm/h", "type": "flux"},
    
    # Atmospheric variables
    "pressure": {"unit": "Pa", "type": "state"},
    "cloud_cover": {"unit": "%", "type": "state"},
    "visibility": {"unit": "km", "type": "state"},
    "sunshine_duration": {"unit": "min", "type": "state"},
    
    # Surface and soil variables (basic)
    "albedo": {"unit": "fraction", "type": "state"},
    "evaporation": {"unit": "mm/h", "type": "flux"},
    "soil_temp": {"unit": "degC", "type": "state"},      # Top soil layer
    "soil_moisture": {"unit": "m3/m3", "type": "state"}, # Top soil layer
}