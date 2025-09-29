"""Meteostat API adapter for climate data"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, ListTuple

import numpy as np
import pandas as pd
import xarray as xr
from ecosystemiser.profile_loader.climate.adapters.base import BaseAdapter
from ecosystemiser.profile_loader.climate.adapters.capabilities import (
    AdapterCapabilities
    AuthType
    DataFrequency
    QualityFeatures
    RateLimits
    SpatialCoverage
    TemporalCoverage
)
from ecosystemiser.profile_loader.climate.adapters.errors import (
    DataFetchError
    DataParseError
    ValidationError
)
from ecosystemiser.profile_loader.climate.data_models import CANONICAL_VARIABLES
from ecosystemiser.profile_loader.climate.processing.validation import (
    QCIssue
    QCProfile
    QCReport
    QCSeverity
)
from hive_logging import get_logger

logger = get_logger(__name__)


class MeteostatAdapter(BaseAdapter):
    """Adapter for Meteostat climate data API"""
from __future__ import annotations


    ADAPTER_NAME = "meteostat"
    ADAPTER_VERSION = "0.1.0"

    # Mapping from canonical names to Meteostat parameter codes
    VARIABLE_MAPPING = {
        # Temperature parameters
        "temp_air": "temp",  # Current air temperature (degC) - hourly data
        "temp_air_avg": "tavg",  # Average temperature (degC) - daily/monthly data
        "temp_air_min": "tmin",  # Minimum temperature (degC) - daily/monthly data
        "temp_air_max": "tmax",  # Maximum temperature (degC) - daily/monthly data
        "dewpoint": "dwpt",  # Dew point temperature (degC)
        # Humidity parameters
        "rel_humidity": "rhum",  # Relative humidity (%)
        # Precipitation parameters
        "precip": "prcp",  # Total precipitation (mm)
        "snow": "snow",  # Snow depth (m)
        # Wind parameters
        "wind_dir": "wdir",  # Wind (from) direction (degrees)
        "wind_speed": "wspd",  # Average wind speed (km/h)
        "wind_gust": "wpgt",  # Wind peak gust (km/h)
        # Pressure parameters
        "pressure": "pres",  # Sea-level air pressure (hPa)
        # Solar/sunshine parameters
        "sunshine_duration": "tsun",  # Total sunshine duration (minutes)
        # Weather condition
        "weather_code": "coco",  # Weather condition code (1-27)
    }

    # Variables that require special processing or unit conversion
    SPECIAL_VARIABLES = {
        "cloud_cover": "coco",  # Derive cloud cover from weather condition codes
        "ghi": "tsun",  # Estimate GHI from sunshine duration
        "visibility": "coco",  # Derive visibility from weather codes
    }

    # Weather condition code mappings (COCO parameter values 1-27)
    WEATHER_CONDITIONS = {
        1: {"name": "Clear", "cloud_cover": 0, "visibility": "good"}
        2: {"name": "Fair", "cloud_cover": 25, "visibility": "good"}
        3: {"name": "Cloudy", "cloud_cover": 75, "visibility": "moderate"}
        4: {"name": "Overcast", "cloud_cover": 100, "visibility": "moderate"}
        5: {"name": "Fog", "cloud_cover": 100, "visibility": "poor"}
        6: {"name": "Freezing Fog", "cloud_cover": 100, "visibility": "poor"}
        7: {"name": "Light Rain", "cloud_cover": 100, "visibility": "moderate"}
        8: {"name": "Rain", "cloud_cover": 100, "visibility": "poor"}
        9: {"name": "Heavy Rain", "cloud_cover": 100, "visibility": "poor"}
        10: {"name": "Freezing Rain", "cloud_cover": 100, "visibility": "poor"}
        11: {"name": "Heavy Freezing Rain", "cloud_cover": 100, "visibility": "poor"}
        12: {"name": "Sleet", "cloud_cover": 100, "visibility": "poor"}
        13: {"name": "Heavy Sleet", "cloud_cover": 100, "visibility": "poor"}
        14: {"name": "Light Snowfall", "cloud_cover": 100, "visibility": "moderate"}
        15: {"name": "Snowfall", "cloud_cover": 100, "visibility": "poor"}
        16: {"name": "Heavy Snowfall", "cloud_cover": 100, "visibility": "poor"}
        17: {"name": "Rain Shower", "cloud_cover": 100, "visibility": "moderate"}
        18: {"name": "Heavy Rain Shower", "cloud_cover": 100, "visibility": "poor"}
        19: {"name": "Sleet Shower", "cloud_cover": 100, "visibility": "poor"}
        20: {"name": "Heavy Sleet Shower", "cloud_cover": 100, "visibility": "poor"}
        21: {"name": "Snow Shower", "cloud_cover": 100, "visibility": "moderate"}
        22: {"name": "Heavy Snow Shower", "cloud_cover": 100, "visibility": "poor"}
        23: {"name": "Lightning", "cloud_cover": 100, "visibility": "poor"}
        24: {"name": "Hail", "cloud_cover": 100, "visibility": "poor"}
        25: {"name": "Thunderstorm", "cloud_cover": 100, "visibility": "poor"}
        26: {
            "name": "Heavy Thunderstorm"
            "cloud_cover": 100
            "visibility": "very_poor"
        }
        27: {"name": "Storm", "cloud_cover": 100, "visibility": "very_poor"}
    }

    def __init__(self) -> None:
        """Initialize Meteostat adapter"""
        from ecosystemiser.profile_loader.climate.adapters.base import (
            CacheConfig
            HTTPConfig
            RateLimitConfig
        )

        # Configure rate limiting (Meteostat has limits)
        rate_config = RateLimitConfig(
            requests_per_minute=60,  # Conservative for free tier
            requests_per_hour=500
            burst_size=10
        )

        # Configure caching
        cache_config = CacheConfig(
            memory_ttl=1800,  # 30 minutes
            disk_ttl=86400,  # 24 hours (station data changes slowly)
        )

        super().__init__(
            name=self.ADAPTER_NAME
            rate_limit_config=rate_config
            cache_config=cache_config
        )
        self._meteostat_available = self._check_meteostat()

    def _check_meteostat(self) -> bool:
        """Check if meteostat library is available"""
        try:
            import meteostat

            return True
        except ImportError:
            logger.warning("Meteostat library not installed. Install with: pip install meteostat")
            return False

    async def _fetch_raw_async(
        self
        location: Tuple[float, float]
        variables: List[str]
        period: Dict
        **kwargs
    ) -> Any | None:
        """Fetch raw data from Meteostat"""
        if not self._meteostat_available:
            raise DataFetchError(
                "Meteostat library not installed. Install with: pip install meteostat"
                adapter_name="meteostat"
            )

        lat, lon = location

        # Validate request
        self._validate_request(lat, lon, variables, period)

        from meteostat import Daily, Hourly, Monthly, Point

        # Parse period
        start_date, end_date = self._parse_period(period)

        # Create location point
        meteo_location = Point(lat, lon)

        # Default to hourly resolution
        resolution = kwargs.get("resolution", "1H")

        # Select appropriate temporal class based on resolution
        if resolution == "1H":
            data_class = Hourly
        elif resolution == "1D":
            data_class = Daily
        elif resolution == "1M":
            data_class = Monthly
        else:
            data_class = Hourly  # Default

        # Fetch data
        self.logger.info(
            f"Fetching Meteostat data for {lat:.3f},{lon:.3f} from {start_date.date()} to {end_date.date()}"
        )

        # Get data from Meteostat
        weather_data = data_class(meteo_location, start_date, end_date)
        df = weather_data.fetch_async()

        if df.empty:
            self.logger.warning(f"No data returned from Meteostat for location {lat:.3f},{lon:.3f}")
            return None

        return df

    async def _transform_data_async(
        self, raw_data: Any, location: Tuple[float, float], variables: List[str]
    ) -> xr.Dataset:
        """Transform Meteostat DataFrame to xarray Dataset"""
        lat, lon = location
        df = raw_data

        # Separate regular and special variables
        regular_vars = [v for v in variables if v in self.VARIABLE_MAPPING]
        special_vars = [v for v in variables if v in self.SPECIAL_VARIABLES]

        # Convert to xarray Dataset
        ds = self._dataframe_to_xarray(df, regular_vars, lat, lon)

        # Process special variables if requested
        if special_vars:
            ds = self._process_special_variables(ds, df, special_vars)

        # Ensure UTC timezone
        if ds.time.dtype.kind == "M":  # datetime type
            ds["time"] = pd.DatetimeIndex(ds.time.values).tz_localize(None)

        # Add quality control
        ds = self._apply_quality_control(ds)

        # Add metadata
        ds.attrs.update(
            {
                "source": "Meteostat"
                "adapter_version": self.ADAPTER_VERSION
                "latitude": lat
                "longitude": lon
            }
        )

        self.logger.info(f"Successfully processed {len(ds.time)} time steps with {len(ds.data_vars)} variables")
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
        self
        *
        lat: float
        lon: float
        variables: List[str]
        period: Dict
        resolution: str = "1H"
    ) -> xr.Dataset:
        """Fetch climate data from Meteostat API"""

        if not self._meteostat_available:
            raise DataFetchError(
                "Meteostat library not installed. Install with: pip install meteostat"
                adapter_name="meteostat"
            )

        try:
            # Separate regular and special variables
            regular_vars = [v for v in variables if v in self.VARIABLE_MAPPING]
            special_vars = [v for v in variables if v in self.SPECIAL_VARIABLES]
            unavailable_vars = [
                v for v in variables if v not in self.VARIABLE_MAPPING and v not in self.SPECIAL_VARIABLES
            ]

            if unavailable_vars:
                logger.warning(f"Variables not available in Meteostat: {unavailable_vars}")

            if not regular_vars and not special_vars:
                raise ValidationError(
                    f"No supported variables requested. Available: {list(self.VARIABLE_MAPPING.keys()) + list(self.SPECIAL_VARIABLES.keys())}"
                )

            # Use base class fetch method
            return await super().fetch_async(
                location=(lat, lon)
                variables=variables
                period=period
                resolution=resolution
            )

        except Exception as e:
            self.logger.error(f"Error fetching Meteostat data: {e}")
            raise DataFetchError(
                f"Failed to fetch data from Meteostat: {str(e)}"
                adapter_name="meteostat"
            ) from e

    def _parse_period(self, period: Dict) -> tuple:
        """Parse period dict to start and end dates"""
        if "year" in period:
            year = period["year"]
            if "month" in period:
                month = int(period["month"]) if isinstance(period["month"], str) else period["month"]
                start_date = datetime(year, month, 1)
                # Get last day of month
                if month == 12:
                    end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = datetime(year, month + 1, 1) - timedelta(days=1)
            else:
                start_date = datetime(year, 1, 1)
                end_date = datetime(year, 12, 31)
        elif "start" in period and "end" in period:
            start_date = datetime.fromisoformat(period["start"])
            end_date = datetime.fromisoformat(period["end"])
        else:
            raise ValueError(f"Invalid period specification: {period}")

        return start_date, end_date

    def _dataframe_to_xarray(self, df: pd.DataFrame, variables: List[str], lat: float, lon: float) -> xr.Dataset:
        """Convert Meteostat DataFrame to xarray Dataset"""

        # Create Dataset with time coordinate
        ds = xr.Dataset(coords={"time": df.index})

        # Add location attributes
        ds.attrs["latitude"] = lat
        ds.attrs["longitude"] = lon
        ds.attrs["source"] = "Meteostat"

        # Map and add variables
        for canonical_name in variables:
            if canonical_name in self.VARIABLE_MAPPING:
                meteo_name = self.VARIABLE_MAPPING[canonical_name]

                if meteo_name in df.columns:
                    # Convert data
                    data = df[meteo_name].values

                    # Handle unit conversions
                    data = self._convert_units(data, canonical_name, meteo_name)

                    # Create DataArray
                    da = xr.DataArray(
                        data
                        coords={"time": df.index}
                        name=canonical_name
                        attrs=self._get_variable_attrs(canonical_name)
                    )

                    ds[canonical_name] = da
                else:
                    logger.warning(f"Variable {meteo_name} not in Meteostat response")
                    # Add NaN array
                    ds[canonical_name] = xr.DataArray(
                        np.full(len(df), np.nan)
                        coords={"time": df.index}
                        attrs=self._get_variable_attrs(canonical_name)
                    )

        return ds

    def _convert_units(self, data: np.ndarray, canonical_name: str, meteo_name: str) -> np.ndarray:
        """Convert Meteostat units to canonical units"""

        conversions = {
            # Meteostat provides mm (total precipitation for the period)
            # For hourly data, this is effectively mm/h
            "prcp": lambda x: x,  # Already in appropriate units (mm/h for hourly)
            # Meteostat pressure in hPa, we want Pa
            "pres": lambda x: x * 100
            # Meteostat wind speed in km/h, we want m/s
            "wspd": lambda x: x * 0.277778
            # Meteostat wind gust in km/h, we want m/s
            "wpgt": lambda x: x * 0.277778
            # Snow depth from m to mm (canonical unit)
            "snow": lambda x: x * 1000
            # Cloud cover from oktas (0-8) to percentage (0-100)
            "coco": lambda x: x * 12.5
            # Wind direction already in degrees - no conversion needed
            "wdir": lambda x: x
            # Temperature fields already in degC - no conversion needed
            "temp": lambda x: x
            "tavg": lambda x: x
            "tmin": lambda x: x
            "tmax": lambda x: x
            "dwpt": lambda x: x
            # Humidity already in % - no conversion needed
            "rhum": lambda x: x
            # Sunshine duration already in minutes - no conversion needed
            "tsun": lambda x: x
        }

        if meteo_name in conversions:
            return conversions[meteo_name](data)

        return data

    def _process_special_variables(self, ds: xr.Dataset, df: pd.DataFrame, special_vars: List[str]) -> xr.Dataset:
        """Process special variables that need custom handling"""

        for var in special_vars:
            if var == "cloud_cover" and "coco" in df.columns:
                # Convert weather condition code to cloud cover percentage
                cloud_data = np.zeros(len(df))
                for i, code in enumerate(df["coco"].values):
                    if pd.notna(code):
                        try:
                            code_int = int(code)
                            if code_int in self.WEATHER_CONDITIONS:
                                cloud_data[i] = self.WEATHER_CONDITIONS[code_int]["cloud_cover"]
                            else:
                                cloud_data[i] = np.nan
                        except (ValueError, TypeError):
                            cloud_data[i] = np.nan
                    else:
                        cloud_data[i] = np.nan

                ds[var] = xr.DataArray(
                    cloud_data
                    coords={"time": ds.time}
                    attrs=self._get_variable_attrs(var)
                )
                logger.info("Derived cloud cover from weather condition codes")

            elif var == "visibility" and "coco" in df.columns:
                # Derive visibility from weather condition codes
                visibility_map = {
                    "very_poor": 0.5
                    "poor": 2.0
                    "moderate": 10.0
                    "good": 20.0
                }
                visibility_data = np.zeros(len(df))
                for i, code in enumerate(df["coco"].values):
                    if pd.notna(code):
                        try:
                            code_int = int(code)
                            if code_int in self.WEATHER_CONDITIONS:
                                vis_qual = self.WEATHER_CONDITIONS[code_int]["visibility"]
                                visibility_data[i] = visibility_map.get(vis_qual, 10.0)
                            else:
                                visibility_data[i] = np.nan
                        except (ValueError, TypeError):
                            visibility_data[i] = np.nan
                    else:
                        visibility_data[i] = np.nan

                ds[var] = xr.DataArray(
                    visibility_data
                    coords={"time": ds.time}
                    attrs=self._get_variable_attrs(var)
                )
                logger.info("Derived visibility from weather condition codes")

            elif var == "ghi" and "tsun" in df.columns:
                # Convert sunshine duration to GHI using Ångström-Prescott model
                ghi_data = self._sunshine_to_ghi(df["tsun"].values, ds.time.values, ds.attrs.get("latitude", 0))
                ds[var] = xr.DataArray(
                    ghi_data
                    coords={"time": ds.time}
                    attrs=self._get_variable_attrs(var)
                )
                logger.info("Converted sunshine duration to GHI using Ångström-Prescott model")

        return ds

    def _get_angstrom_coefficients(self, latitude: float) -> tuple[float, float]:
        """
        Get region-specific Ångström-Prescott coefficients based on latitude.

        These coefficients are calibrated for different climate zones and improve
        solar radiation estimation accuracy compared to global constants.

        Args:
            latitude: Location latitude in degrees

        Returns:
            Tuple of (a_coefficient, b_coefficient)

        References:
            - Prescott, J.A. (1940). "Evaporation from a water surface in relation to solar radiation"
            - Ångström, A. (1924). "Solar and terrestrial radiation"
            - Regional calibrations from multiple meteorological studies
        """

        # Region-specific coefficients based on climate zones and latitude bands
        # Values calibrated from meteorological station data worldwide

        abs_lat = abs(latitude)

        if abs_lat >= 60:  # Polar regions
            # Higher atmospheric turbidity, lower clear-sky transmission
            # Calibrated for Scandinavia, northern Canada, Antarctica
            return (0.20, 0.45)

        elif abs_lat >= 50:  # Sub-polar regions
            # Moderate atmospheric conditions, seasonal variations
            # Calibrated for northern Europe, southern Chile/Argentina
            return (0.22, 0.48)

        elif abs_lat >= 40:  # Temperate regions
            # Standard mid-latitude conditions
            # Calibrated for continental Europe, central North America
            return (0.25, 0.50)

        elif abs_lat >= 30:  # Subtropical regions
            # Higher solar elevation, moderate humidity
            # Calibrated for Mediterranean, southern USA, northern Africa
            return (0.28, 0.52)

        elif abs_lat >= 20:  # Tropical-subtropical transition
            # High solar elevation, variable humidity
            # Calibrated for Mexico, northern India, Sahara margins
            return (0.30, 0.54)

        elif abs_lat >= 10:  # Tropical regions
            # High humidity, frequent clouds, high atmospheric water vapor
            # Calibrated for central Africa, northern South America
            return (0.26, 0.48)

        else:  # Equatorial regions (|lat| < 10deg)
            # Very high humidity, frequent convective clouds
            # Calibrated for Amazon, Congo Basin, Indonesia
            return (0.24, 0.46)

    def _sunshine_to_ghi(self, sunshine_minutes: np.ndarray, timestamps: np.ndarray, latitude: float) -> np.ndarray:
        """
        Convert sunshine duration to GHI using Ångström-Prescott model.

        This implements a more accurate solar radiation model based on sunshine duration
        and solar geometry calculations.
        """
        import math
        from datetime import datetime

        ghi_estimates = np.zeros_like(sunshine_minutes, dtype=float)

        # Ångström-Prescott coefficients (region-specific values)
        a_coeff, b_coeff = self._get_angstrom_coefficients(latitude)

        for i, ts in enumerate(timestamps):
            if hasattr(ts, "timetuple"):
                dt = ts
            else:
                dt = pd.to_datetime(ts)

            # Get day of year and hour
            day_of_year = dt.timetuple().tm_yday
            hour = dt.hour + dt.minute / 60.0

            # Calculate sunshine fraction
            sunshine_hours = sunshine_minutes[i] / 60.0
            max_possible_sunshine = 1.0  # For hourly data
            sunshine_fraction = np.clip(sunshine_hours / max_possible_sunshine, 0, 1)

            # Solar declination angle (radians)
            declination = math.radians(23.45 * math.sin(math.radians(360 * (284 + day_of_year) / 365)))

            # Hour angle (radians)
            hour_angle = math.radians(15 * (hour - 12))

            # Solar elevation angle
            lat_rad = math.radians(latitude)
            elevation = math.asin(
                math.sin(declination) * math.sin(lat_rad)
                + math.cos(declination) * math.cos(lat_rad) * math.cos(hour_angle)
            )

            # Only calculate if sun is above horizon
            if elevation > 0:
                # Solar zenith angle
                zenith = math.pi / 2 - elevation

                # Air mass (simplified formula)
                air_mass = 1 / math.cos(zenith) if zenith < math.radians(85) else 10

                # Extraterrestrial radiation (W/m2)
                # Solar constant adjusted for Earth-Sun distance
                solar_constant = 1367  # W/m2
                earth_sun_factor = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
                extraterrestrial = solar_constant * earth_sun_factor * math.sin(elevation)

                # Clear sky radiation (Beer's law approximation)
                clear_sky_ghi = extraterrestrial * (0.75 ** (air_mass**0.678))

                # Ångström-Prescott model
                # GHI = (a + b * n/N) * H0
                # where n/N is sunshine fraction, H0 is extraterrestrial radiation
                angstrom_factor = a_coeff + b_coeff * sunshine_fraction
                ghi_estimates[i] = angstrom_factor * extraterrestrial

                # Limit to reasonable maximum (clear sky conditions)
                ghi_estimates[i] = min(ghi_estimates[i], clear_sky_ghi)
            else:
                ghi_estimates[i] = 0

        # Apply additional quality control
        ghi_estimates = np.clip(ghi_estimates, 0, 1400)  # Physical limits

        return ghi_estimates

    def _apply_quality_control(self, ds: xr.Dataset) -> xr.Dataset:
        """Apply quality control checks to the dataset"""

        for var_name in ds.data_vars:
            da = ds[var_name]

            # Apply physical bounds based on variable type
            if var_name == "temp_air":
                # Temperature bounds: -80degC to +60degC
                da = da.where((da >= -80) & (da <= 60))
            elif var_name == "rel_humidity":
                # Humidity bounds: 0-100%
                da = da.where((da >= 0) & (da <= 100))
            elif var_name == "wind_speed":
                # Wind speed: non-negative, max ~200 m/s
                da = da.where((da >= 0) & (da <= 200))
            elif var_name == "pressure":
                # Surface pressure: 850-1100 hPa (85000-110000 Pa)
                da = da.where((da >= 85000) & (da <= 110000))
            elif var_name == "precip":
                # Precipitation: non-negative, max 1000mm/hr
                da = da.where((da >= 0) & (da <= 1000))
            elif var_name == "ghi":
                # Solar irradiance: 0-1500 W/m2
                da = da.where((da >= 0) & (da <= 1500))

            # Update dataset
            ds[var_name] = da

        return ds

    def _get_variable_attrs(self, canonical_name: str) -> Dict:
        """Get variable attributes including units"""

        units_map = {
            "temp_air": "degC"
            "dewpoint": "degC"
            "rel_humidity": "%"
            "precip": "mm/h",  # Total precipitation for the time period
            "snow": "mm"
            "wind_dir": "degrees"
            "wind_speed": "m/s"
            "pressure": "Pa"
            "cloud_cover": "%"
            "ghi": "W/m2"
        }

        return {
            "units": units_map.get(canonical_name, "unknown")
            "long_name": canonical_name.replace("_", " ").title()
        }

    def get_capabilities(self) -> AdapterCapabilities:
        """Return Meteostat adapter capabilities"""
        return AdapterCapabilities(
            name="Meteostat"
            version=self.ADAPTER_VERSION
            description="Global weather station data with quality control and gap filling"
            temporal=TemporalCoverage(
                start_date=None,  # Varies by station (some from 1900s)
                end_date=None,  # Present
                historical_years=50,  # Typical station coverage
                forecast_days=0
                real_time=True
                delay_hours=1,  # Near real-time
            )
            spatial=SpatialCoverage(
                global_coverage=True
                regions=None
                resolution_km=None,  # Station-based, varies
                station_based=True
                grid_based=False
                custom_locations=True,  # Finds nearest station
            )
            supported_variables=list(self.VARIABLE_MAPPING.keys()) + list(self.SPECIAL_VARIABLES.keys())
            primary_variables=[
                "temp_air"
                "precip"
                "wind_speed",  # Best for basic met vars
                "pressure"
                "rel_humidity"
            ]
            derived_variables=[]
            supported_frequencies=[
                DataFrequency.HOURLY
                DataFrequency.DAILY
                DataFrequency.MONTHLY
            ]
            native_frequency=DataFrequency.HOURLY
            auth_type=AuthType.NONE,  # Uses RapidAPI internally but handled by library
            requires_subscription=False,  # Free tier available
            free_tier_limits=RateLimits(
                requests_per_month=500
                requests_per_day=None
                requests_per_hour=None
                data_points_per_request=None
            )
            quality=QualityFeatures(
                gap_filling=True,  # Statistical gap filling
                quality_flags=True,  # QC flags available
                uncertainty_estimates=False
                ensemble_members=False
                bias_correction=False
            )
            max_request_days=None,  # No hard limit
            max_variables_per_request=None
            batch_requests_supported=False
            async_requests_required=False
            special_features=[
                "Weather station network data"
                "Statistical gap filling"
                "Quality control flags"
                "Historical data from 1900s for some stations"
                "Near real-time updates"
                "Automatic station selection by proximity"
            ]
            data_products=["Hourly", "Daily", "Monthly", "Normals"]
        )


class MeteostatQCProfile(QCProfile):
    """QC profile for Meteostat data - co-located with adapter for better cohesion."""

    def __init__(self) -> None:
        super().__init__(
            name="Meteostat"
            description="Weather station data aggregated from multiple national weather services"
            known_issues=[
                "Data gaps common due to station maintenance"
                "Quality varies by region and station density"
                "Some stations may have exposure or instrumentation issues"
                "Interpolation used between stations can introduce artifacts"
            ]
            recommended_variables=[
                "temp_air"
                "rel_humidity"
                "precip"
                "wind_speed"
                "pressure"
            ]
            temporal_resolution_limits={"all": "hourly"}
            spatial_accuracy="Point measurements, station-dependent"
        )

    def validate_source_specific(self, ds: xr.Dataset, report: QCReport) -> None:
        """Meteostat specific validation"""

        # Check for excessive data gaps (common with station data)
        for var_name in ds.data_vars:
            data = ds[var_name].values
            gap_length = self._check_consecutive_gaps(data)

            if gap_length > 24:  # Gaps longer than 24 hours
                issue = QCIssue(
                    type="data_gaps"
                    message=f"Long data gaps detected in {var_name} (max: {gap_length} consecutive NaN values)"
                    severity=QCSeverity.MEDIUM if gap_length < 72 else QCSeverity.HIGH
                    affected_variables=[var_name]
                    metadata={"max_gap_hours": int(gap_length)}
                    suggested_action="Check station maintenance schedules and consider gap filling"
                )
                report.add_issue(issue)

        # Check for station-specific issues (simplified)
        if "wind_speed" in ds:
            wind_data = ds["wind_speed"].values
            # Check for suspiciously low wind variability (sheltered station)
            wind_std = np.nanstd(wind_data)
            if wind_std < 0.5:  # Very low wind variability
                issue = QCIssue(
                    type="station_exposure"
                    message=f"Very low wind speed variability (std={wind_std:.2f}) suggests sheltered station"
                    severity=QCSeverity.LOW
                    affected_variables=["wind_speed"]
                    metadata={"wind_std": float(wind_std)}
                    suggested_action="Consider station exposure conditions in analysis"
                )
                report.add_issue(issue)

        report.passed_checks.append("meteostat_specific_validation")

    def _check_consecutive_gaps(self, data: np.ndarray) -> int:
        """Find maximum length of consecutive NaN values"""
        is_nan = np.isnan(data)
        if not np.any(is_nan):
            return 0

        # Find consecutive NaN sequences
        groups = np.split(np.arange(len(is_nan)), np.where(np.diff(is_nan))[0] + 1)
        max_gap = 0

        for group in groups:
            if len(group) > 0 and is_nan[group[0]]:
                max_gap = max(max_gap, len(group))

        return max_gap

    def get_adjusted_bounds(self, base_bounds: Dict[str, Tuple[float, float]]) -> Dict[str, Tuple[float, float]]:
        """Get source-specific adjusted bounds"""
        return base_bounds
