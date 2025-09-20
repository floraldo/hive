"""Climate data models and contracts"""

from typing import Dict, List, Literal, Optional, Tuple, Any
from pydantic import BaseModel, Field
from ..shared.models import BaseProfileRequest, BaseProfileResponse, ProfileMode

Mode = Literal["observed", "tmy", "average", "synthetic"]
Resolution = Literal["15min", "30min", "1H", "3H", "1D"]

class ClimateRequest(BaseProfileRequest):
    location: Tuple[float, float] | str
    variables: List[str] = Field(
        default_factory=lambda: ["temp_air", "ghi", "dni", "dhi", "wind_speed", "rel_humidity", "precip", "cloud_cover"]
    )
    source: Literal["nasa_power", "meteostat", "pvgis", "era5", "file_epw"] = "nasa_power"
    period: Dict[str, int | str]  # {"year": 2019} or {"start":"1991-01-01","end":"2020-12-31"}
    mode: Mode = "observed"
    resolution: Resolution = "1H"
    timezone: Literal["UTC", "local"] = "UTC"
    subset: Optional[Dict[str, str]] = None  # {"month":"07"} or {"start":"07-10","end":"07-24"}
    synthetic_options: Dict[str, Any] = Field(default_factory=dict)
    seed: Optional[int] = None
    baseline_period: Optional[Tuple[str, str]] = None  # nonstationarity handling (later)
    p_selection: Optional[int] = None  # P50/P90 representative year (later)

class ClimateResponse(BaseProfileResponse):
    manifest: Dict[str, Any]
    path_parquet: str
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