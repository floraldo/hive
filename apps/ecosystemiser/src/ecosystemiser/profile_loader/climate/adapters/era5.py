"""ERA5 reanalysis data adapter from Copernicus/ECMWF"""

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import xarray as xr
from ecosystemiser.profile_loader.climate.adapters.base import BaseAdapter
from ecosystemiser.profile_loader.climate.adapters.capabilities import (
    AdapterCapabilities,
    AuthType,
    DataFrequency,
    QualityFeatures,
    RateLimits,
    SpatialCoverage,
    TemporalCoverage,
)
from ecosystemiser.profile_loader.climate.adapters.errors import DataFetchError, DataParseError, ValidationError
from ecosystemiser.profile_loader.climate.processing.validation import QCIssue, QCProfile, QCReport, QCSeverity
from hive_logging import get_logger

logger = get_logger(__name__)


class ERA5Adapter(BaseAdapter):
    """Adapter for ERA5 reanalysis climate data"""

    ADAPTER_NAME = "era5"
    ADAPTER_VERSION = "0.1.0"

    # Mapping from canonical names to ERA5 parameter codes
    VARIABLE_MAPPING = {
        # Temperature parameters,
        "temp_air": "2m_temperature",  # 2m temperature (K),
        "dewpoint": "2m_dewpoint_temperature",  # 2m dewpoint temperature (K),
        "skin_temperature": "skin_temperature",  # Surface skin temperature (K),
        "sea_surface_temp": "sea_surface_temperature",  # Sea surface temperature (K),
        "surface_temp": "skin_temperature",  # Alias for skin temperature
        # Pressure parameters,
        "pressure": "surface_pressure",  # Surface pressure (Pa),
        "msl_pressure": "mean_sea_level_pressure",  # Mean sea level pressure (Pa)
        # Wind parameters (calculated from components),
        "wind_speed": "10m_wind_speed",  # Wind speed at 10m (calculated),
        "wind_dir": "10m_wind_direction",  # Wind direction at 10m (calculated),
        "wind_u": "10m_u_component_of_wind",  # 10m u-component of wind (m/s),
        "wind_v": "10m_v_component_of_wind",  # 10m v-component of wind (m/s),
        "wind_gust": "10m_wind_gust",  # Wind gust at 10m (m/s)
        # Solar radiation parameters,
        "ghi": "surface_solar_radiation_downwards",  # Global horizontal irradiance (J/m2),
        "dni": "direct_solar_radiation",  # Direct normal irradiance (J/m2),
        "surface_net_solar": "surface_net_solar_radiation",  # Net surface solar radiation (J/m2),
        "surface_net_solar_clear": "surface_net_solar_radiation_clear_sky",  # Clear sky net solar (J/m2),
        "toa_incident_solar": "toa_incident_solar_radiation",  # Top of atmosphere incident solar (J/m2)
        # Longwave radiation parameters,
        "lw_down": "surface_thermal_radiation_downwards",  # Longwave downward (J/m2),
        "surface_net_thermal": "surface_net_thermal_radiation",  # Net surface thermal radiation (J/m2),
        "surface_net_thermal_clear": "surface_net_thermal_radiation_clear_sky",  # Clear sky net thermal (J/m2),
        "toa_outgoing_lw": "toa_outgoing_longwave_radiation",  # TOA outgoing longwave (J/m2)
        # Precipitation parameters,
        "precip": "total_precipitation",  # Total precipitation (m),
        "convective_precip": "convective_precipitation",  # Convective precipitation (m),
        "large_scale_precip": "large_scale_precipitation",  # Large-scale precipitation (m),
        "snowfall": "snowfall",  # Snowfall (m water equivalent),
        "snow_depth": "snow_depth",  # Snow depth (m),
        "snow_density": "snow_density",  # Snow density (kg/m3),
        "snow_albedo": "snow_albedo",  # Snow albedo (0-1)
        # Humidity and water parameters,
        "rel_humidity": "relative_humidity",  # Relative humidity (derived),
        "total_column_water": "total_column_water_vapour",  # Total column water vapor (kg/m2),
        "total_column_water_liquid": "total_column_cloud_liquid_water",  # Cloud liquid water (kg/m2),
        "total_column_water_ice": "total_column_cloud_ice_water",  # Cloud ice water (kg/m2)
        # Cloud parameters,
        "cloud_cover": "total_cloud_cover",  # Total cloud cover (0-1),
        "low_cloud_cover": "low_cloud_cover",  # Low cloud cover (0-1),
        "medium_cloud_cover": "medium_cloud_cover",  # Medium cloud cover (0-1),
        "high_cloud_cover": "high_cloud_cover",  # High cloud cover (0-1)
        # Evaporation and surface fluxes,
        "evaporation": "evaporation",  # Evaporation (m water equivalent),
        "potential_evaporation": "potential_evaporation",  # Potential evaporation (m),
        "runoff": "runoff",  # Runoff (m),
        "sub_surface_runoff": "sub_surface_runoff",  # Sub-surface runoff (m),
        "surface_runoff": "surface_runoff",  # Surface runoff (m)
        # Soil parameters (4 layers),
        "soil_temp_1": "soil_temperature_level_1",  # Soil temp layer 1 (0-7cm) (K),
        "soil_temp_2": "soil_temperature_level_2",  # Soil temp layer 2 (7-28cm) (K),
        "soil_temp_3": "soil_temperature_level_3",  # Soil temp layer 3 (28-100cm) (K),
        "soil_temp_4": "soil_temperature_level_4",  # Soil temp layer 4 (100-289cm) (K),
        "soil_moisture_1": "volumetric_soil_water_layer_1",  # Soil moisture layer 1 (m3/m3),
        "soil_moisture_2": "volumetric_soil_water_layer_2",  # Soil moisture layer 2 (m3/m3),
        "soil_moisture_3": "volumetric_soil_water_layer_3",  # Soil moisture layer 3 (m3/m3),
        "soil_moisture_4": "volumetric_soil_water_layer_4",  # Soil moisture layer 4 (m3/m3)
        # Surface characteristics,
        "surface_roughness": "surface_roughness",  # Surface roughness (m),
        "forecast_albedo": "forecast_albedo",  # Surface albedo (0-1),
        "lake_cover": "lake_cover",  # Lake cover (0-1),
        "lake_ice_depth": "lake_ice_depth",  # Lake ice depth (m),
        "lake_ice_temp": "lake_ice_temperature",  # Lake ice temperature (K),
        "lake_mix_depth": "lake_mix_layer_depth",  # Lake mixing layer depth (m),
        "lake_mix_temp": "lake_mix_layer_temperature",  # Lake mixing layer temperature (K),
        "lake_bottom_temp": "lake_bottom_temperature",  # Lake bottom temperature (K),
        "lake_shape_factor": "lake_shape_factor",  # Lake shape factor (dimensionless),
        "lake_total_depth": "lake_total_layer_temperature",  # Lake total layer temperature (K)
        # Vegetation parameters,
        "lai_high_veg": "leaf_area_index_high_vegetation",  # LAI high vegetation (m2/m2),
        "lai_low_veg": "leaf_area_index_low_vegetation",  # LAI low vegetation (m2/m2)
        # Atmospheric composition,
        "total_ozone": "total_column_ozone",  # Total column ozone (kg/m2)
        # Energy fluxes,
        "sensible_heat_flux": "surface_sensible_heat_flux",  # Sensible heat flux (W/m2),
        "latent_heat_flux": "surface_latent_heat_flux",  # Latent heat flux (W/m2),
        "boundary_layer_height": "boundary_layer_height",  # Boundary layer height (m)
        # Additional atmospheric parameters,
        "visibility": "visibility",  # Visibility (m),
        "total_sky_direct_solar": "total_sky_direct_solar_radiation_at_surface",  # Direct solar at surface (W/m2),
        "cape": "convective_available_potential_energy",  # CAPE (J/kg),
        "cin": "convective_inhibition",  # CIN (J/kg)
        # Standardize soil_temp to use the top layer,
        "soil_temp": "soil_temperature_level_1",  # Standard soil temp (0-7cm),
        "albedo": "forecast_albedo",  # Standardized albedo name,
        "snow": "snow_depth",  # Standardized snow depth
    }

    # Variables that can be derived from hourly data
    DERIVED_VARIABLES = (
        {
            "temp_air_max": "2m_temperature",  # Daily max from hourly temperature,
            "temp_air_min": "2m_temperature",  # Daily min from hourly temperature,
            "wind_speed_max": "10m_wind_speed",  # Max wind speed from hourly
        },
    )

    def __init__(self) -> None:
        """Initialize ERA5 adapter"""
        from ecosystemiser.profile_loader.climate.adapters.base import CacheConfig, HTTPConfig, RateLimitConfig

        # Configure rate limiting (CDS API has no strict limits but be reasonable)
        rate_config = RateLimitConfig(
            requests_per_minute=6, requests_per_hour=60, burst_size=3  # Conservative for large requests,
        )

        # Configure caching (ERA5 data doesn't change)
        cache_config = CacheConfig(
            memory_ttl=3600,  # 1 hour,
            disk_ttl=604800,  # 1 week (data is static)
        )

        super().__init__(name=self.ADAPTER_NAME, rate_limit_config=rate_config, cache_config=cache_config)
        self._cdsapi_available = self._check_cdsapi()

    def _check_cdsapi(self) -> bool:
        """Check if cdsapi library is available"""
        try:
            import cdsapi

            # Check for API key in environment or config file,
            if not os.path.exists(os.path.expanduser("~/.cdsapirc")):
                logger.warning("CDS API key not found. Create ~/.cdsapirc file with your credentials")
                logger.warning("Get your API key from: https://cds.climate.copernicus.eu/api-how-to")
                return False
            return True
        except ImportError:
            logger.warning("cdsapi library not installed. Install with: pip install cdsapi")
            return False

    async def _fetch_raw_async(
        self, location: Tuple[float, float], variables: List[str], period: Dict, **kwargs
    ) -> Any | None:
        """Fetch raw data from ERA5 CDS API"""
        if not self._cdsapi_available:
            raise DataFetchError(
                self.ADAPTER_NAME,
                "cdsapi library not installed or not configured. ",
                "Install with: pip install cdsapi and configure ~/.cdsapirc",
                suggested_action="Visit https://cds.climate.copernicus.eu/api-how-to for setup instructions",
            )

        import tempfile

        import cdsapi

        lat, lon = location

        # Validate request,
        self._validate_request(lat, lon, variables, period)

        # Parse period,
        start_date, end_date = self._parse_period(period)

        # Map variables to ERA5 parameters
        era5_params = self._map_variables(variables)

        if not era5_params:
            raise ValidationError(
                f"No valid variables for ERA5 from: {variables}",
                field="variables",
                value=variables,
                suggested_action=f"Available variables: {list(self.VARIABLE_MAPPING.keys())}",
            )

        # Initialize CDS API client
        client = cdsapi.Client()

        # Determine dataset based on date range
        dataset = self._select_dataset(start_date, end_date)

        # Build request parameters
        request_params = self._build_request(
            lat, lon, era5_params, start_date, end_date, kwargs.get("resolution", "1H")
        )

        self.logger.info(f"Fetching ERA5 data for {lat},{lon} from {start_date} to {end_date}")
        self.logger.info(f"Dataset: {dataset}, Variables: {era5_params}")

        # Download data to temporary file,
        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
            tmp_path = tmp.name

        # Request data from CDS
        try:
            client.retrieve(dataset, request_params, tmp_path)
        except Exception as e:
            raise DataFetchError(
                self.ADAPTER_NAME,
                f"CDS API request failed: {str(e)}",
                details={
                    "dataset": dataset,
                    "params": request_params,
                    "lat": lat,
                    "lon": lon,
                },
                suggested_action="Check CDS API status and request parameters",
            )

        # Load data with xarray
        try:
            import xarray as xr

            ds = xr.open_dataset(tmp_path)
            return ds
        except Exception as e:
            raise DataParseError(
                self.ADAPTER_NAME, f"Failed to load NetCDF data: {str(e)}", details={"file_path": tmp_path}
            )
        finally:
            # Clean up temp file,
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass  # Ignore cleanup errors,

    async def _transform_data_async(
        self, raw_data: Any, location: Tuple[float, float], variables: List[str]
    ) -> xr.Dataset:
        """Transform raw ERA5 data to xarray Dataset"""
        lat, lon = location
        ds = raw_data

        # Process and standardize dataset
        ds = self._process_era5_data(ds, variables, lat, lon)

        # Add metadata,
        ds.attrs.update(
            {
                "source": "ERA5",
                "adapter_version": self.ADAPTER_VERSION,
                "latitude": lat,
                "longitude": lon,
                "license": "Copernicus Climate Change Service",
            }
        )

        return ds

    def _validate_request(self, lat: float, lon: float, variables: List[str], period: Dict) -> None:
        """Validate request parameters"""
        if not (-90 <= lat <= 90):
            raise ValidationError(f"Invalid latitude: {lat}", field="lat", value=lat)
        if not (-180 <= lon <= 180):
            raise ValidationError(f"Invalid longitude: {lon}", field="lon", value=lon)
        if not variables:
            raise ValidationError("Variables list cannot be empty", field="variables", value=variables)

    async def fetch_async(
        self, *, lat: float, lon: float, variables: List[str], period: Dict, resolution: str = "1H"
    ) -> xr.Dataset:
        """
        Fetch climate data from ERA5 reanalysis.

        Args:
            lat: Latitude (-90 to 90),
            lon: Longitude (-180 to 180),
            variables: List of canonical variable names,
            period: Time period (e.g., {"year": 2019}),
            resolution: Time resolution ("1H", "3H", "6H", "1D")

        Returns:
            xarray.Dataset with UTC time index and canonical variable names

        Raises:
            DataFetchError: If CDS API request fails,
            DataParseError: If response cannot be parsed,
            ValidationError: If parameters are invalid,
        """

        if not self._cdsapi_available:
            raise DataFetchError(
                self.ADAPTER_NAME,
                "cdsapi library not installed or not configured. ",
                "Install with: pip install cdsapi and configure ~/.cdsapirc",
                suggested_action="Visit https://cds.climate.copernicus.eu/api-how-to for setup instructions",
            )

        try:
            # Use base class fetch method,
            return await super().fetch_async(
                location=(lat, lon), variables=variables, period=period, resolution=resolution
            )

        except Exception as e:
            # Wrap unexpected errors
            error = DataFetchError(
                self.ADAPTER_NAME,
                f"Unexpected error fetching ERA5 data: {str(e)}",
                details={"lat": lat, "lon": lon, "variables": variables},
            )
            self.logger.error(f"Unexpected error: {error}")
            raise error

    def _parse_period(self, period: Dict) -> tuple:
        """Parse period dict to start and end dates"""

        try:
            if "year" in period:
                year = int(period["year"])

                # ERA5 available from 1940 to present,
                if year < 1940:
                    raise ValidationError(
                        "ERA5 data only available from 1940 onwards",
                        field="period.year",
                        value=year,
                        suggested_action="Use year >= 1940",
                    )

                # Check if year is too recent (ERA5 has ~5 day delay)
                current_year = datetime.now().year
                if year > current_year:
                    raise ValidationError(
                        f"ERA5 data not yet available for year {year}",
                        field="period.year",
                        value=year,
                        suggested_action=f"Use year <= {current_year}",
                    )

                if "month" in period:
                    month = int(period["month"]) if isinstance(period["month"], str) else period["month"]
                    if not 1 <= month <= 12:
                        raise ValidationError("Month must be between 1 and 12", field="period.month", value=month)
                    start_date = datetime(year, month, 1)
                    if month == 12:
                        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
                    else:
                        end_date = datetime(year, month + 1, 1) - timedelta(days=1)
                else:
                    start_date = datetime(year, 1, 1)
                    end_date = datetime(year, 12, 31)

            elif "start" in period and "end" in period:
                try:
                    start_date = pd.to_datetime(period["start"]).to_pydatetime()
                    end_date = pd.to_datetime(period["end"]).to_pydatetime()
                except Exception as e:
                    raise ValidationError(
                        f"Invalid date format in period: {e}",
                        field="period.start/end",
                        value=period,
                        suggested_action="Use ISO format (YYYY-MM-DD) or datetime objects",
                    )

                if start_date > end_date:
                    raise ValidationError("Start date must be before end date", field="period", value=period)

            else:
                # Handle multi-year requests (e.g., 30-year climatology),
                if "start_year" in period and "end_year" in period:
                    start_year = int(period["start_year"])
                    end_year = int(period["end_year"])

                    if start_year < 1940:
                        raise ValidationError(
                            "ERA5 data only available from 1940 onwards", field="period.start_year", value=start_year
                        )

                    if start_year > end_year:
                        raise ValidationError(
                            "Start year must be before or equal to end year", field="period", value=period
                        )
                    start_date = datetime(start_year, 1, 1)
                    end_date = datetime(end_year, 12, 31)
                else:
                    raise ValidationError(
                        f"Invalid period specification: {period}",
                        field="period",
                        value=period,
                        suggested_action="Use 'year', 'start'/'end', or 'start_year'/'end_year'",
                    )

            return start_date, end_date

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Error parsing period: {str(e)}", field="period", value=period)

    def _map_variables(self, variables: List[str]) -> List[str]:
        """Map canonical variable names to ERA5 parameters"""

        era5_params = []
        unavailable_vars = []

        for var in variables:
            if var in self.VARIABLE_MAPPING:
                param = self.VARIABLE_MAPPING[var]

                # Handle derived variables,
                if var == "wind_speed" or var == "wind_dir":
                    # Need both u and v components,
                    era5_params.extend(["10m_u_component_of_wind", "10m_v_component_of_wind"])
                elif var == "rel_humidity":
                    # Need temperature and dewpoint for calculation,
                    era5_params.extend(["2m_temperature", "2m_dewpoint_temperature"])
                else:
                    era5_params.append(param)
            else:
                unavailable_vars.append(var)
                logger.warning(f"Variable {var} not available in ERA5")

        if unavailable_vars:
            logger.warning(f"Unavailable variables will be skipped: {unavailable_vars}")
            logger.info(f"Available ERA5 variables: {list(self.VARIABLE_MAPPING.keys())}")

        # Remove duplicates while preserving order
        seen = set()
        era5_params = [param for param in era5_params if param not in seen and not seen.add(param)]

        return era5_params

    def _select_dataset(self, start_date: datetime, end_date: datetime) -> str:
        """Select appropriate ERA5 dataset"""

        # Use ERA5-Land for land surface variables if available
        # Otherwise use standard ERA5,
        return "reanalysis-era5-single-levels"

    def _build_request(
        self, lat: float, lon: float, variables: List[str], start_date: datetime, end_date: datetime, resolution: str
    ) -> Dict:
        """Build CDS API request parameters"""

        # Define area: North, West, South, East
        # Add small buffer around point
        buffer = 0.25
        area = [lat + buffer, lon - buffer, lat - buffer, lon + buffer]

        # Time selection based on resolution,
        if resolution == "1H":
            times = [f"{h:02d}:00" for h in range(24)]
        elif resolution == "3H":
            times = ([f"{h:02d}:00" for h in range(0, 24, 3)],)
        elif resolution == "6H":
            times = (["00:00", "06:00", "12:00", "18:00"],)
        elif resolution == "1D":
            times = ["12:00"]  # Daily average at noon
        else:
            times = ["00:00", "12:00"]  # Default to twice daily

        # Generate date components efficiently without creating full pandas date range
        years = set()
        months = set()
        days = set()
        current = start_date
        while current <= end_date:
            years.add(current.year)
            months.add(f"{current.month:02d}"),
            days.add(f"{current.day:02d}"),
            current += (timedelta(days=1),)
        request = {
            "product_type": "reanalysis",
            "format": "netcdf",
            "variable": variables,
            "year": sorted(list(years)),
            "month": sorted(list(months)),
            "day": sorted(list(days)),
            "time": times,
            "area": area,
        }

        return request

    def _select_nearest_coordinates(self, ds: xr.Dataset, lat: float, lon: float) -> xr.Dataset:
        """
        Robust coordinate selection that handles different ERA5 coordinate naming conventions.

        Supports:
        - Standard names: 'latitude', 'longitude'
        - Short names: 'lat', 'lon'
        - Stacked coordinates: multi-dimensional coordinate arrays,
        """

        # Common coordinate name variations in ERA5 files
        lat_names = ["latitude", "lat", "y"]
        lon_names = ["longitude", "lon", "x"]

        lat_coord = None
        lon_coord = None

        # Find latitude coordinate,
        for name in lat_names:
            if name in ds.dims:
                lat_coord = name
                break
            elif name in ds.coords:
                lat_coord = name
                break

        # Find longitude coordinate,
        for name in lon_names:
            if name in ds.dims:
                lon_coord = name
                break
            elif name in ds.coords:
                lon_coord = name
                break

        if lat_coord is None or lon_coord is None:
            # Handle stacked coordinates (multi-dimensional),
            if "latitude" in ds.coords and "longitude" in ds.coords:
                lat_values = ds.coords["latitude"].values
                lon_values = ds.coords["longitude"].values

                if lat_values.ndim > 1:  # Multi-dimensional coordinates
                    # Find nearest point in stacked coordinates
                    lat_diff = np.abs(lat_values - lat)
                    lon_diff = np.abs(lon_values - lon)
                    distance = np.sqrt(lat_diff**2 + lon_diff**2)

                    # Get indices of minimum distance
                    min_idx = np.unravel_index(np.argmin(distance), distance.shape)

                    # Select using integer indexing
                    dim_names = list(lat_values.dims)
                    selection = {dim: idx for dim, idx in zip(dim_names, min_idx)}
                    return ds.isel(selection)

            # If we still can't find coordinates, raise informative error
            available_dims = list(ds.dims.keys())
            available_coords = list(ds.coords.keys())
            raise DataParseError(
                self.ADAPTER_NAME,
                f"Could not find latitude/longitude coordinates in ERA5 dataset. "
                f"Available dimensions: {available_dims}, coordinates: {available_coords}",
                details={
                    "requested_lat": lat,
                    "requested_lon": lon,
                    "available_dimensions": available_dims,
                    "available_coordinates": available_coords,
                },
            )

        # Standard coordinate selection
        try:
            return ds.sel({lat_coord: lat, lon_coord: lon}, method="nearest")
        except Exception as e:
            raise DataParseError(
                self.ADAPTER_NAME,
                f"Failed to select coordinates ({lat}, {lon}) from ERA5 dataset: {str(e)}",
                details={"lat_coord": lat_coord, "lon_coord": lon_coord, "requested_lat": lat, "requested_lon": lon},
            )

    def _process_era5_data(self, ds: xr.Dataset, variables: List[str], lat: float, lon: float) -> xr.Dataset:
        """Process and standardize ERA5 data"""

        # Select nearest point to requested coordinates with robust coordinate handling
        ds = self._select_nearest_coordinates(ds, lat, lon)

        # Rename time dimension if needed,
        if "valid_time" in ds.dims:
            ds = ds.rename({"valid_time": "time"})

        # Create output dataset with canonical names
        out_ds = xr.Dataset(coords={"time": ds.time})
        out_ds.attrs["latitude"] = lat
        out_ds.attrs["longitude"] = lon
        out_ds.attrs["source"] = "ERA5"

        # Map ERA5 variables to canonical names,
        for canonical_name in variables:
            if canonical_name == "wind_speed":
                # Calculate from u and v components,
                if "u10" in ds and "v10" in ds:
                    wind_speed = np.sqrt(ds["u10"] ** 2 + ds["v10"] ** 2)
                    out_ds[canonical_name] = wind_speed
                    out_ds[canonical_name].attrs = {"units": "m/s", "long_name": "Wind Speed"}

            elif canonical_name == "wind_dir":
                # Calculate from u and v components,
                if "u10" in ds and "v10" in ds:
                    wind_dir = np.arctan2(ds["v10"], ds["u10"]) * 180 / np.pi
                    wind_dir = (wind_dir + 360) % 360  # Convert to 0-360
                    out_ds[canonical_name] = wind_dir
                    out_ds[canonical_name].attrs = {"units": "degrees", "long_name": "Wind Direction"}

            elif canonical_name == "rel_humidity":
                # Calculate from temperature and dewpoint,
                if "t2m" in ds and "d2m" in ds:
                    # Magnus formula for relative humidity
                    T = ds["t2m"] - 273.15  # Convert K to C
                    Td = ds["d2m"] - 273.15
                    RH = 100 * np.exp((17.625 * Td) / (243.04 + Td)) / np.exp((17.625 * T) / (243.04 + T))
                    out_ds[canonical_name] = RH
                    out_ds[canonical_name].attrs = {"units": "%", "long_name": "Relative Humidity"}

            elif canonical_name == "ghi":
                # Solar radiation in ERA5 is accumulated, need to convert to instantaneous,
                if "ssrd" in ds:
                    # Convert from J/m2 to W/m2
                    # ERA5 gives accumulated values, need to calculate hourly averages
                    ghi_data = ds["ssrd"]
                    # For hourly data, divide by 3600 seconds
                    # For sub-hourly, adjust accordingly
                    time_delta = self._get_time_delta_seconds(ds)
                    ghi = ghi_data / time_delta
                    # Ensure non-negative values (solar radiation can't be negative)
                    ghi = xr.where(ghi < 0, 0, ghi)
                    out_ds[canonical_name] = ghi
                    out_ds[canonical_name].attrs = {"units": "W/m2", "long_name": "Global Horizontal Irradiance"}

            elif canonical_name in self.VARIABLE_MAPPING:
                era5_name = self.VARIABLE_MAPPING[canonical_name]
                # Comprehensive mapping from ERA5 short names to actual variable names in dataset
                var_map = (
                    {
                        # Temperature variables,
                        "2m_temperature": "t2m",
                        "2m_dewpoint_temperature": "d2m",
                        "soil_temperature_level_1": "stl1",
                        # Pressure variables,
                        "surface_pressure": "sp",
                        "mean_sea_level_pressure": "msl",
                        # Wind variables,
                        "10m_u_component_of_wind": "u10",
                        "10m_v_component_of_wind": "v10",
                        "10m_wind_gust": "i10fg",
                        # Precipitation variables,
                        "total_precipitation": "tp",
                        "snowfall": "sf",
                        "evaporation": "e",
                        # Solar radiation variables,
                        "surface_solar_radiation_downwards": "ssrd",
                        "direct_solar_radiation": "fdir",
                        "surface_thermal_radiation_downwards": "strd",
                        # Cloud and humidity variables,
                        "total_cloud_cover": "tcc",
                        "low_cloud_cover": "lcc",
                        "medium_cloud_cover": "mcc",
                        "high_cloud_cover": "hcc",
                        # Soil variables,
                        "volumetric_soil_water_layer_1": "swvl1",
                        "volumetric_soil_water_layer_2": "swvl2",
                        "volumetric_soil_water_layer_3": "swvl3",
                        "volumetric_soil_water_layer_4": "swvl4",
                        # Additional variables,
                        "leaf_area_index_high_vegetation": "lai_hv",
                        "leaf_area_index_low_vegetation": "lai_lv",
                        "forecast_albedo": "fal",
                        "skin_temperature": "skt",
                    },
                )

                if era5_name in var_map and var_map[era5_name] in ds:
                    data = ds[var_map[era5_name]]

                    # Unit conversions,
                    if canonical_name == "temp_air" or canonical_name == "dewpoint" or canonical_name == "soil_temp":
                        data = data - 273.15  # K to C
                    elif canonical_name == "precip" or canonical_name == "snow" or canonical_name == "evaporation":
                        # ERA5 provides accumulation over preceding hour in meters
                        # Convert to mm and treat as mm/h (since it's hourly accumulation)
                        # Note: For hourly data, mm accumulation = mm/h rate
                        data = data * 1000  # m to mm
                    elif canonical_name == "cloud_cover":
                        data = data * 100  # fraction to percentage
                    elif canonical_name == "pressure":
                        # ERA5 surface pressure is already in Pa - no conversion needed,
                        pass

                    out_ds[canonical_name] = (data,)
                    out_ds[canonical_name].attrs = self._get_variable_attrs(canonical_name)

        # Validate that we have at least one variable,
        if not out_ds.data_vars:
            raise DataParseError(
                self.ADAPTER_NAME,
                f"No variables could be processed from ERA5 data",
                details={"requested_variables": variables, "available_in_dataset": list(ds.data_vars.keys())},
            )

        return out_ds

    def _get_time_delta_seconds(self, ds: xr.Dataset) -> float:
        """Calculate time delta in seconds from dataset time coordinates"""
        if len(ds.time) < 2:
            return 3600.0  # Default to 1 hour
        time_diff = ds.time.values[1] - ds.time.values[0]
        # Convert numpy timedelta64 to seconds,
        return float(time_diff / np.timedelta64(1, "s"))

    def _get_variable_attrs(self, canonical_name: str) -> Dict:
        """Get variable attributes including units"""

        units_map = {
            "temp_air": "degC",
            "dewpoint": "degC",
            "pressure": "Pa",
            "wind_speed": "m/s",
            "wind_dir": "degrees",
            "ghi": "W/m2",
            "dni": "W/m2",
            "precip": "mm/h",  # ERA5 provides accumulation over preceding hour,
            "rel_humidity": "%",
            "cloud_cover": "%",
            "snow": "mm/h",  # ERA5 provides accumulation over preceding hour,
            "evaporation": "mm/h",  # ERA5 provides accumulation over preceding hour,
            "soil_temp": "degC",
            "soil_moisture": "m3/m3",
        }

        return (
            {"units": units_map.get(canonical_name, "unknown"), "long_name": canonical_name.replace("_", " ").title()},
        )

    def get_capabilities(self) -> AdapterCapabilities:
        """Return ERA5 adapter capabilities"""
        return AdapterCapabilities(
            name="ERA5",
            version=self.ADAPTER_VERSION,
            description="ECMWF's fifth generation atmospheric reanalysis of global climate",
            temporal=TemporalCoverage(
                start_date=date(1940, 1, 1),
                end_date=None,  # Present (5 days behind real-time)
                historical_years=84,
                forecast_days=0,
                real_time=False,
                delay_hours=120,  # 5 days delay
            ),
            spatial=SpatialCoverage(
                global_coverage=True,
                regions=None,
                resolution_km=31,  # 0.25deg x 0.25deg
                station_based=False,
                grid_based=True,
                custom_locations=True,
            ),
            supported_variables=list(self.VARIABLE_MAPPING.keys()),
            primary_variables=[
                "temp_air",
                "pressure",
                "wind_speed",
                "precip",
                "soil_temp",
                "soil_moisture",  # Unique land surface vars
            ],
            derived_variables=["rel_humidity", "wind_speed", "wind_dir"],
            supported_frequencies=[
                DataFrequency.HOURLY,
                DataFrequency.THREEHOURLY,
                DataFrequency.DAILY,
                DataFrequency.MONTHLY,
            ],
            native_frequency=DataFrequency.HOURLY,
            auth_type=AuthType.API_KEY,
            requires_subscription=False,  # Free with registration
            free_tier_limits=None,  # No hard limits, but be reasonable
            quality=QualityFeatures(
                gap_filling=True,  # Complete coverage
                quality_flags=False,
                uncertainty_estimates=True,  # Through ensemble
                ensemble_members=True,  # 10-member ensemble available
                bias_correction=True,
            ),
            max_request_days=None,  # Can request decades
            max_variables_per_request=20,
            batch_requests_supported=True,
            async_requests_required=True,  # Large requests queued
            special_features=[
                "Most comprehensive reanalysis dataset",
                "Global coverage since 1940",
                "137 atmospheric levels",
                "10-member ensemble for uncertainty",
                "Land, ocean, and atmospheric variables",
                "Consistent long-term climate record",
                "High temporal and spatial resolution",
            ],
            data_products=["Reanalysis", "ERA5-Land", "Ensemble", "Pressure Levels"],
        )


class ERA5QCProfile(QCProfile):
    """QC profile for ERA5 reanalysis data - co-located with adapter for better cohesion."""

    def __init__(self) -> None:
        super().__init__(
            name="ERA5",
            description="ECMWF's fifth-generation atmospheric reanalysis",
            known_issues=[
                "Smoothed data due to reanalysis model constraints",
                "May not capture extreme local weather events accurately",
                "Precipitation and cloud fields have known biases",
                "Surface variables affected by model topography vs real topography",
            ],
            recommended_variables=["temp_air", "dewpoint", "wind_speed", "wind_dir", "pressure", "rel_humidity"],
            temporal_resolution_limits={"all": "hourly"},
            spatial_accuracy="0.25deg x 0.25deg (~30km resolution)",
        )

    def validate_source_specific(self, ds: xr.Dataset, report: QCReport) -> None:
        """ERA5 specific validation"""

        # Check for over-smoothed data (typical of reanalysis),
        for var_name in ["temp_air", "wind_speed"]:
            if var_name not in ds:
                continue
            data = ds[var_name].values
            valid_data = data[~np.isnan(data)]

            if len(valid_data) > 24:  # At least 24 hours
                # Check for unnaturally smooth data
                # Calculate second derivative to detect lack of high-frequency variation
                second_derivative = np.abs(np.diff(valid_data, n=2))
                smooth_ratio = np.mean(second_derivative < 0.01)  # Very small changes

                if smooth_ratio > 0.8:  # 80% of changes are very small
                    issue = QCIssue(
                        type="reanalysis_smoothing",
                        message=f"Data appears over-smoothed in {var_name} (typical of reanalysis)",
                        severity=QCSeverity.LOW,
                        affected_variables=[var_name],
                        metadata={"smooth_ratio": float(smooth_ratio)},
                        suggested_action="Consider supplementing with higher-resolution data for local applications",
                    )
                    report.add_issue(issue)

        # Warn about precipitation biases,
        if "precip" in ds:
            issue = QCIssue(
                type="reanalysis_limitation",
                message="ERA5 precipitation has known regional biases and may not represent local extremes",
                severity=QCSeverity.LOW,
                affected_variables=["precip"],
                suggested_action="Validate against local observations for precipitation-sensitive applications",
            )
            report.add_issue(issue)

        report.passed_checks.append("era5_specific_validation")
