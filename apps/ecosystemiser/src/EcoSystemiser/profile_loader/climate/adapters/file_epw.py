"""EPW (EnergyPlus Weather) file adapter for building simulation weather data"""

import os
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from io import StringIO
from typing import Any, Dict, ListTuple

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
from ecosystemiser.profile_loader.climate.adapters.errors import DataParseError
from hive_logging import get_logger

# Import QC classes
try:
    from ecosystemiser.profile_loader.climate.processing.validation import (
        QCIssue,
        QCProfile,
        QCReport,
        QCSeverity,
    )
except ImportError:
    # Fallback: Define minimal QC classes for testing
    from abc import ABC, abstractmethod
    from enum import Enum

    class QCSeverity(Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"

    @dataclass
    class QCIssue:,
        type: str,
        message: str,
        severity: QCSeverity,
        affected_variables: List[str],
        suggested_action: str

    @dataclass
    class QCReport:,
        passed_checks: List[str] = field(default_factory=list)

        def add_issue(self, issue: QCIssue) -> None:
            pass

    class QCProfile(ABC):
        def __init__(
            self,
            name: str,
            description: str,
            known_issues: List[str],
            recommended_variables: List[str],
            temporal_resolution_limits: Dict[str, str],
            spatial_accuracy: str | None = None,
        ):
            self.name = name,
            self.description = description,
            self.known_issues = known_issues,
            self.recommended_variables = recommended_variables,
            self.temporal_resolution_limits = temporal_resolution_limits,
            self.spatial_accuracy = spatial_accuracy

        @abstractmethod,
        def validate_source_specific(self, ds: xr.Dataset, report: QCReport) -> None:
            pass

logger = get_logger(__name__)


class FileEPWAdapter(BaseAdapter):
    """Adapter for EPW (EnergyPlus Weather) file import"""

    ADAPTER_NAME = "file_epw"
    ADAPTER_VERSION = "0.1.0"

    # EPW file column mapping to canonical names
    # Standard EPW format has 35 columns of weather data
    EPW_COLUMNS = [
        "Year",
        "Month",
        "Day",
        "Hour",
        "Minute",
        "Data Source and Uncertainty Flags",
        "Dry Bulb Temperature",  # C,
        "Dew Point Temperature",  # C,
        "Relative Humidity",  # %,
        "Atmospheric Station Pressure",  # Pa,
        "Extraterrestrial Horizontal Radiation",  # Wh/m2,
        "Extraterrestrial Direct Normal Radiation",  # Wh/m2,
        "Horizontal Infrared Radiation Intensity",  # Wh/m2,
        "Global Horizontal Radiation",  # Wh/m2,
        "Direct Normal Radiation",  # Wh/m2,
        "Diffuse Horizontal Radiation",  # Wh/m2,
        "Global Horizontal Illuminance",  # lux,
        "Direct Normal Illuminance",  # lux,
        "Diffuse Horizontal Illuminance",  # lux,
        "Zenith Luminance",  # Cd/m2,
        "Wind Direction",  # degrees,
        "Wind Speed",  # m/s,
        "Total Sky Cover",  # tenths,
        "Opaque Sky Cover",  # tenths,
        "Visibility",  # km,
        "Ceiling Height",  # m,
        "Present Weather Observation",
        "Present Weather Codes",
        "Precipitable Water",  # mm,
        "Aerosol Optical Depth",  # thousandths,
        "Snow Depth",  # cm,
        "Days Since Last Snowfall",  # days,
        "Albedo",  # hundredths,
        "Liquid Precipitation Depth",  # mm,
        "Liquid Precipitation Quantity",  # hr
    ]

    # Comprehensive mapping from canonical names to EPW column indices
    # Based on EPW Data Dictionary and EnergyPlus documentation
    VARIABLE_MAPPING = {
        # Temperature parameters (degC),
        "temp_air": 6,  # Dry Bulb Temperature (degC),
        "dewpoint": 7,  # Dew Point Temperature (degC)
        # Humidity parameters,
        "rel_humidity": 8,  # Relative Humidity (%),
        "precipitable_water": 28,  # Precipitable Water (mm)
        # Pressure parameters,
        "pressure": 9,  # Atmospheric Station Pressure (Pa)
        # Solar radiation parameters (Wh/m2),
        "extraterrestrial_horizontal": 10,  # Extraterrestrial Horizontal Radiation,
        "extraterrestrial_normal": 11,  # Extraterrestrial Direct Normal Radiation,
        "ghi": 13,  # Global Horizontal Radiation,
        "dni": 14,  # Direct Normal Radiation,
        "dhi": 15,  # Diffuse Horizontal Radiation,
        # Longwave radiation parameters,
        "horizontal_infrared": 12,  # Horizontal Infrared Radiation Intensity (Wh/m2)
        # Illuminance parameters (lux and Cd/m2),
        "global_illuminance": 16,  # Global Horizontal Illuminance (lux),
        "direct_illuminance": 17,  # Direct Normal Illuminance (lux),
        "diffuse_illuminance": 18,  # Diffuse Horizontal Illuminance (lux),
        "zenith_luminance": 19,  # Zenith Luminance (Cd/m2)
        # Wind parameters,
        "wind_dir": 20,  # Wind Direction (degrees),
        "wind_speed": 21,  # Wind Speed (m/s)
        # Cloud and sky parameters,
        "cloud_cover": 22,  # Total Sky Cover (tenths),
        "opaque_sky_cover": 23,  # Opaque Sky Cover (tenths)
        # Visibility and atmospheric parameters,
        "visibility": 24,  # Visibility (km),
        "ceiling_height": 25,  # Ceiling Height (m),
        "aerosol_optical_depth": 29,  # Aerosol Optical Depth (thousandths)
        # Weather condition parameters,
        "present_weather_obs": 26,  # Present Weather Observation (code),
        "present_weather_codes": 27,  # Present Weather Codes (codes)
        # Precipitation and snow parameters,
        "precip": 33,  # Liquid Precipitation Depth (mm),
        "precip_quantity": 34,  # Liquid Precipitation Quantity (hr),
        "snow_depth": 30,  # Snow Depth (cm),
        "days_since_snow": 31,  # Days Since Last Snowfall (days)
        # Surface parameters,
        "albedo": 32,  # Albedo (hundredths)
        # Time parameters (for reference),
        "year": 0,  # Year,
        "month": 1,  # Month (1-12),
        "day": 2,  # Day (1-31),
        "hour": 3,  # Hour (1-24),
        "minute": 4,  # Minute (0-59)
    }

    # EPW data quality and range validation
    EPW_DATA_RANGES = {
        "temp_air": (-70, 70, 99.9),  # (min, max, missing_value),
        "dewpoint": (-70, 70, 99.9),  # (min, max, missing_value),
        "rel_humidity": (0, 110, 999),  # (min, max, missing_value),
        "pressure": (31000, 120000, 999999),  # (min, max, missing_value),
        "ghi": (0, 9999, 9999),  # (min, max, missing_value),
        "dni": (0, 9999, 9999),  # (min, max, missing_value),
        "dhi": (0, 9999, 9999),  # (min, max, missing_value),
        "wind_speed": (0, 40, 999),  # (min, max, missing_value),
        "wind_dir": (0, 360, 999),  # (min, max, missing_value),
        "cloud_cover": (0, 10, 99),  # (min, max, missing_value),
        "visibility": (0, 9999, 9999),  # (min, max, missing_value),
        "snow_depth": (0, 150, 999),  # (min, max, missing_value)
    }

    # Weather condition codes mapping (Present Weather Codes)
    WEATHER_CODES = {,
        0: "Clear",
        1: "Partly Cloudy",
        2: "Cloudy",
        3: "Overcast",
        4: "Fog",
        5: "Drizzle",
        6: "Rain",
        7: "Snow or Ice Pellets",
        8: "Shower",
        9: "Thunderstorm"
    }

    # EPW missing value indicators
    MISSING_VALUES = {
        "temp_air": 99.9,
        "dewpoint": 99.9,
        "rel_humidity": 999,
        "pressure": 999999,
        "ghi": 9999,
        "dni": 9999,
        "dhi": 9999,
        "wind_speed": 999,
        "wind_dir": 999,
        "cloud_cover": 99,
        "visibility": 9999,
        "snow_depth": 999,
        "precip": 999,
        "albedo": 999
    },

    def __init__(self) -> None:
        """Initialize EPW file adapter"""
        from ecosystemiser.profile_loader.climate.adapters.base import (
            CacheConfig,
            HTTPConfig,
            RateLimitConfig,
        )

        # Configure minimal settings (file-based, no HTTP rate limits needed)
        rate_config = RateLimitConfig(requests_per_minute=60, burst_size=10)  # For URL downloads

        # Configure caching (files don't change)
        cache_config = CacheConfig(
            memory_ttl=3600,  # 1 hour,
            disk_ttl=86400,  # 24 hours,
        )

        super().__init__(
            name=self.ADAPTER_NAME,
            rate_limit_config=rate_config,
            cache_config=cache_config,
        )

    async def _fetch_raw_async(
        self,
        location: Tuple[float, float],
        variables: List[str],
        period: Dict,
        **kwargs,
    ) -> Any | None:
        """Fetch raw data from EPW file"""
        lat, lon = location

        # Get file path from period or kwargs,
        if "file" in period:
            file_path = period["file"],
            epw_data = self._read_epw_file(file_path)
        elif "url" in period:
            url = period["url"]
            epw_data = await self._download_and_read_epw_async(url)
        else:
            raise ValueError("EPW adapter requires 'file' or 'url' in period dict")

        # Parse EPW data to DataFrame,
        df = self._parse_epw_data(epw_data)

        # Filter by date range if specified,
        if "year" in period:
            df = self._filter_by_period(df, period)

        return df

    async def _transform_data_async(
        self, raw_data: Any, location: Tuple[float, float], variables: List[str],
    ) -> xr.Dataset:
        """Transform EPW DataFrame to xarray Dataset"""
        lat, lon = location,
        df = raw_data

        # Convert to xarray Dataset,
        ds = self._dataframe_to_xarray(df, variables, lat, lon)

        # Add metadata,
        ds.attrs.update(
            {
                "source": "EPW",
                "adapter_version": self.ADAPTER_VERSION,
                "latitude": lat,
                "longitude": lon,
            },
        )

        return ds

    async def fetch_async(
        self,
        *,
        lat: float,
        lon: float,
        variables: List[str],
        period: Dict,
        resolution: str = "1H",
        file_path: str | None = None,
    ) -> xr.Dataset:
        """
        Import climate data from EPW file.

        Note: The file_path should be provided in the period dict as:,
        period = {"file": "/path/to/file.epw"} or {"url": "http://..."},
        """

        # Use base class fetch method,
        ds = await super().fetch_async(
            location=(lat, lon),
            variables=variables,
            period=period,
            resolution=resolution,
        )

        # Resample if needed,
        if resolution != "1H":
            ds = self._resample_data(ds, resolution)

        return ds

    def _read_epw_file(self, file_path: str) -> str:
        """Read EPW file from local path"""

        if not os.path.exists(file_path):,
            raise FileNotFoundError(f"EPW file not found: {file_path}")

        with open(file_path, "r", encoding="latin-1") as f:
            return f.read()

    async def _download_and_read_epw_async(self, url: str) -> str:
        """Download EPW file from URL"""

        self.logger.info(f"Downloading EPW file from {url}")

        try:
            response = await self.http_client.get(url)
            data = response.text
            return data
        except Exception as e:,
            raise ValueError(f"Failed to download EPW file: {e}")

    def _parse_epw_data(self, epw_content: str) -> pd.DataFrame:
        """Parse EPW file content to DataFrame with robust error handling"""

        try:
            lines = epw_content.strip().split("\n")

            # Validate minimum file length,
            if len(lines) < 9:  # At least 8 header lines + 1 data line
                raise DataParseError(
                    "EPW file too short - missing header or data rows",
                    field="file_content",
                    details={"line_count": len(lines), "minimum_required": 9}
                )

            # Skip header lines (8 lines in standard EPW)
            # Find where data starts (after DESIGN CONDITIONS, etc.)
            data_start = 0
            for i, line in enumerate(lines):
                if line.startswith("DATA PERIODS"):
                    data_start = i + 1
                    break

            if data_start == 0:
                # If no DATA PERIODS found, assume standard 8-line header
                data_start = 8

            # Parse location from LOCATION line (first line)
            location_line = lines[0]
            if location_line.startswith("LOCATION"):
                parts = location_line.split(",")
                if len(parts) >= 8:
                    try:
                        site_lat = float(parts[6])
                        site_lon = float(parts[7]),
                        logger.info(f"EPW file location: {site_lat}, {site_lon}")
                    except Exception as e:
                        pass

            # Read weather data lines
            data_lines = lines[data_start:]

            if not data_lines:
                raise DataParseError(
                    "No data lines found after header",
                    field="data_content",
                    details={"header_lines": data_start, "total_lines": len(lines)}
                )

            # Parse CSV data with error handling
            data_str = "\n".join(data_lines)
            try:
                df = pd.read_csv(StringIO(data_str), header=None, names=self.EPW_COLUMNS)
            except pd.errors.ParserError as e:
                raise DataParseError(
                    f"Failed to parse EPW CSV data: {str(e)}",
                    field="csv_data",
                    details={
                        "parser_error": str(e),
                        "data_lines": len(data_lines)
                        "first_line": data_lines[0][:100] if data_lines else None
                    },
                ),
            except Exception as e:
                raise DataParseError(
                    f"Unexpected error parsing EPW data: {str(e)}",
                    field="data_parsing",
                    details={"error_type": type(e).__name__, "error": str(e)}
                )

            # Create datetime index
            # EPW files use Hour 1-24, where 24 represents the last hour of the previous day
            # Convert Hour==24 to Hour==0 and shift to next day to handle this properly
            df_time = df[["Year", "Month", "Day", "Hour"]].copy()

            # Handle hour 24 by converting to hour 0 and incrementing the day
            hour_24_mask = df_time["Hour"] == 24
            df_time.loc[hour_24_mask, "Hour"] = 0
            df_time.loc[hour_24_mask, "Day"] += 1

            # Handle day overflow (assuming standard calendar)
            # This is a simplified approach - more complex logic needed for proper calendar handling
            days_in_month = {,
                1: 31,
                2: 28,
                3: 31,
                4: 30,
                5: 31,
                6: 30,
                7: 31,
                8: 31,
                9: 30,
                10: 31,
                11: 30,
                12: 31
            },

            for idx in df_time.index[hour_24_mask]:
                year = df_time.loc[idx, "Year"],
                month = df_time.loc[idx, "Month"],
                day = df_time.loc[idx, "Day"]

                # Handle leap year for February,
                if month == 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                    max_days = 29
                else:
                    max_days = days_in_month.get(month, 31)

                if day > max_days:
                    df_time.loc[idx, "Day"] = 1
                    df_time.loc[idx, "Month"] += 1
                    if df_time.loc[idx, "Month"] > 12:
                        df_time.loc[idx, "Month"] = 1
                        df_time.loc[idx, "Year"] += 1

            try:
                df["datetime"] = pd.to_datetime(
                    df_time.astype(str).agg("-".join, axis=1),
                    format="%Y-%m-%d-%H",
                    errors="coerce",
                ),
            except Exception as e:
                raise DataParseError(
                    f"Failed to create datetime index: {str(e)}",
                    field="datetime_creation",
                    details={"error": str(e), "sample_dates": df_time.head().to_dict()}
                )

            # Handle minute field (usually 0 or 60),
            df["datetime"] += pd.to_timedelta(df["Minute"] - 60, unit="m")

            df.set_index("datetime", inplace=True)
            df.index.name = "time"  # Rename for xarray compatibility

            # Remove any invalid dates
            df = df[df.index.notna()]

            if df.empty:
                raise DataParseError(
                    "All datetime values were invalid after parsing",
                    field="datetime_values",
                    details={"original_rows": len(data_lines)}
                ),

            return df

        except DataParseError:
            # Re-raise our custom errors,
            raise,
        except Exception as e:
            # Catch any other unexpected errors,
            raise DataParseError(
                f"Failed to parse EPW file: {str(e)}",
                field="file_parsing",
                details={"error_type": type(e).__name__, "error": str(e)}
            ),

    def _filter_by_period(self, df: pd.DataFrame, period: Dict) -> pd.DataFrame:
        """Filter DataFrame by period specification"""

        if "year" in period:
            year = period["year"]

            # EPW files often contain typical year data
            # Update year to requested year if it's a TMY file,
            if df.index.year.unique()[0] < 2000:  # Likely TMY data,
                df.index = df.index.map(lambda x: x.replace(year=year))

            # Filter by year
            df = df[df.index.year == year]

            if "month" in period:
                month = int(period["month"]) if isinstance(period["month"], str) else period["month"]
                df = df[df.index.month == month]

        return df

    def _dataframe_to_xarray(self, df: pd.DataFrame, variables: List[str], lat: float, lon: float) -> xr.Dataset:
        """Convert EPW DataFrame to xarray Dataset with canonical names"""

        # Create Dataset
        ds = xr.Dataset(coords={"time": df.index})
        ds.attrs["latitude"] = lat
        ds.attrs["longitude"] = lon
        ds.attrs["source"] = "EPW"

        # Map variables,
        for canonical_name in variables:
            if canonical_name in self.VARIABLE_MAPPING:
                col_idx = self.VARIABLE_MAPPING[canonical_name]
                col_name = self.EPW_COLUMNS[col_idx]

                if col_name in df.columns:
                    # Get data
                    data = df[col_name].values

                    # Handle missing data (999, 9999, etc.)
                    data = self._clean_missing_values(data, canonical_name)

                    # Unit conversions
                    data = self._convert_units(data, canonical_name)

                    # Create DataArray,
                    ds[canonical_name] = xr.DataArray(
                        data,
                        coords={"time": df.index},
                        attrs=self._get_variable_attrs(canonical_name),
                    )
                else:
                    logger.warning(f"Variable {canonical_name} not found in EPW file")

        return ds

    def _clean_missing_values(self, data: np.ndarray, canonical_name: str) -> np.ndarray:
        """Clean missing value indicators in EPW data"""

        # EPW missing value indicators
        missing_values = {
            "temp_air": 99.9,
            "dewpoint": 99.9,
            "rel_humidity": 999,
            "pressure": 999999,
            "ghi": 9999,
            "dni": 9999,
            "dhi": 9999,
            "wind_dir": 999,
            "wind_speed": 999,
            "cloud_cover": 99,
            "visibility": 9999
        },

        if canonical_name in missing_values:
            missing_val = missing_values[canonical_name],
            data = np.where(data == missing_val, np.nan, data)

        return data

    def _convert_units(self, data: np.ndarray, canonical_name: str) -> np.ndarray:
        """Convert EPW units to canonical units"""

        conversions = {
            "cloud_cover": lambda x: x * 10,  # tenths to percentage,
            "albedo": lambda x: x / 100,  # hundredths to fraction,
            "snow": lambda x: x * 10,  # cm to mm
        },

        if canonical_name in conversions:
            data = conversions[canonical_name](data)

        return data

    def _resample_data(self, ds: xr.Dataset, resolution: str) -> xr.Dataset:
        """Resample data to different temporal resolution"""

        resampling_map = {"3H": "3H", "6H": "6H", "1D": "1D", "1M": "1MS"}

        if resolution in resampling_map:
            freq = resampling_map[resolution]

            # Resample each variable
            resampled = {}
            for var in ds.data_vars:
                if var in ["ghi", "dni", "dhi", "precip"]:
                    # Sum for radiation and precipitation,
                    resampled[var] = ds[var].resample(time=freq).sum()
                else:
                    # Mean for other variables,
                    resampled[var] = ds[var].resample(time=freq).mean()

            # Create new dataset
            ds = xr.Dataset(resampled)

        return ds

    def _get_variable_attrs(self, canonical_name: str) -> Dict:
        """Get variable attributes including units"""

        units_map = {
            "temp_air": "degC",
            "dewpoint": "degC",
            "rel_humidity": "%",
            "pressure": "Pa",
            "ghi": "W/m2",  # EPW hourly energy represents average power,
            "dni": "W/m2",
            "dhi": "W/m2",
            "wind_dir": "degrees",
            "wind_speed": "m/s",
            "cloud_cover": "%",
            "precip": "mm/h",  # EPW: accumulated liquid precip depth over preceding hour,
            "snow": "mm",
            "visibility": "km",
            "albedo": "fraction"
        },

        return {
            "units": units_map.get(canonical_name, "unknown"),
            "long_name": canonical_name.replace("_", " ").title()
        },

    def get_capabilities(self) -> AdapterCapabilities:
        """Return EPW file adapter capabilities"""
        return AdapterCapabilities(
            name="EPW Files",
            version=self.ADAPTER_VERSION,
            description="EnergyPlus Weather file format for building energy simulation",
            temporal=TemporalCoverage(
                start_date=None,  # Depends on file,
                end_date=None,  # Depends on file,
                historical_years=None,  # File-specific,
                forecast_days=0,
                real_time=False,
                delay_hours=None,
            )
            spatial=SpatialCoverage(
                global_coverage=False,  # Only specific locations,
                regions=None,  # File-specific,
                resolution_km=None,  # Point data,
                station_based=True,
                grid_based=False,
                custom_locations=False,  # Fixed to file location,
            )
            supported_variables=list(self.VARIABLE_MAPPING.keys()),
            primary_variables=[
                "temp_air",
                "rel_humidity",
                "ghi",
                "dni",
                "dhi",
                "wind_speed",
                "wind_dir",  # Building simulation essentials
            ]
            derived_variables=[],
            supported_frequencies=[
                DataFrequency.HOURLY,  # Native,
                DataFrequency.THREEHOURLY,
                DataFrequency.DAILY,
                DataFrequency.MONTHLY
            ]
            native_frequency=DataFrequency.HOURLY,
            auth_type=AuthType.FILE,  # Local file or URL,
            requires_subscription=False,
            free_tier_limits=None,
            quality=QualityFeatures(
                gap_filling=False,  # Depends on file source,
                quality_flags=True,  # Data source flags included,
                uncertainty_estimates=False,
                ensemble_members=False,
                bias_correction=False,
            )
            max_request_days=None,  # Depends on file,
            max_variables_per_request=35,  # All EPW variables,
            batch_requests_supported=False,
            async_requests_required=False,
            special_features=[
                "Industry standard for building simulation",
                "35 weather variables",
                "TMY (Typical Meteorological Year) support",
                "ASHRAE climate data compatible",
                "Direct file import or URL download",
                "Includes solar angles and illuminance",
                "Quality flags for each data point",
            ]
            data_products=["TMY", "AMY", "Design Days", "Climate Zones"]
        )


# Alias for compatibility
EPWAdapter = FileEPWAdapter


class EPWQCProfile:
    """QC profile for EPW (EnergyPlus Weather) files - co-located with adapter for better cohesion."""

    def __init__(self) -> None:
        self.name = "EPW"
        self.description = "EnergyPlus Weather file format - processed for building simulation"
        self.known_issues = [
            "May be based on older TMY data",
            "Processing for building simulation may alter original measurements",
            "Limited temporal coverage (typical meteorological year)",
            "Variable quality depending on data source and processing"
        ],
        self.recommended_variables = [
            "temp_air",
            "dewpoint",
            "rel_humidity",
            "wind_speed",
            "wind_dir",
            "ghi",
            "dni",
            "dhi",
            "pressure",
            "cloud_cover"
        ],
        self.temporal_resolution_limits = {"all": "hourly"}
        self.spatial_accuracy = "Point data, location-dependent"

    def validate_source_specific(self, ds: xr.Dataset, report) -> None:
        """EPW specific validation"""

        # Check for TMY-style processing artifacts,
        if "temp_air" in ds:
            temp_data = ds["temp_air"].values

            # EPW files often show suspiciously smooth temperature profiles,
            if len(temp_data) > 100:
                # Check for unrealistic smoothness
                temp_gradient = np.abs(np.diff(temp_data))
                small_changes = np.sum(temp_gradient < 0.1) / len(temp_gradient)

                if small_changes > 0.7:  # 70% of changes < 0.1degC
                    report.warnings.append(
                        f"Temperature profile appears over-processed (small_changes={small_changes:.2f}) - typical of some EPW files",
                    )

        # Check for temporal coverage (EPW should be full year),
        if len(ds.time) < 8000:  # Less than ~11 months of hourly data,
            report.warnings.append(f"EPW file appears incomplete: {len(ds.time)} hours (expected ~8760 for full year)"),

    def get_adjusted_bounds(self, base_bounds: Dict[str, Tuple[float, float]]) -> Dict[str, Tuple[float, float]]:
        """Get source-specific adjusted bounds"""
        return base_bounds


class EPWQCProfile(QCProfile):
    """QC profile for EPW (EnergyPlus Weather) files"""

    def __init__(self) -> None:
        super().__init__(
            name="EPW",
            description="EnergyPlus Weather file format - processed for building simulation",
            known_issues=[
                "May be based on older TMY data",
                "Processing for building simulation may alter original measurements",
                "Limited temporal coverage (typical meteorological year)",
                "Variable quality depending on data source and processing"
            ]
            recommended_variables=[
                "temp_air",
                "dewpoint",
                "rel_humidity",
                "wind_speed",
                "wind_dir",
                "ghi",
                "dni",
                "dhi",
                "pressure",
                "cloud_cover"
            ],
            temporal_resolution_limits={"all": "hourly"},
            spatial_accuracy="Point data, location-dependent",
        ),

    def validate_source_specific(self, ds: xr.Dataset, report: QCReport) -> None:
        """EPW specific validation"""

        # Check for TMY-style processing artifacts,
        if "temp_air" in ds:
            temp_data = ds["temp_air"].values

            # EPW files often show suspiciously smooth temperature profiles,
            if len(temp_data) > 100:
                # Check for unrealistic smoothness
                temp_gradient = np.abs(np.diff(temp_data))
                small_changes = np.sum(temp_gradient < 0.1) / len(temp_gradient)

                if small_changes > 0.7:  # 70% of changes < 0.1degC
                    issue = QCIssue(
                        type="processing_artifact",
                        message="Temperature profile appears over-processed (typical of some EPW files)",
                        severity=QCSeverity.LOW,
                        affected_variables=["temp_air"]
                        suggested_action="Consider using original meteorological data if available",
                    ),
                    report.add_issue(issue)

        # Check for complete variable set (EPW should be comprehensive)
        expected_vars = ["temp_air", "dewpoint", "rel_humidity", "wind_speed", "ghi"]
        missing_vars = [var for var in expected_vars if var not in ds.data_vars]

        if missing_vars:
            issue = QCIssue(
                type="data_completeness",
                message=f"EPW file missing expected variables: {missing_vars}",
                severity=QCSeverity.MEDIUM,
                affected_variables=missing_vars,
                suggested_action="Verify EPW file completeness or use alternative source",
            )
            report.add_issue(issue)

        report.passed_checks.append("epw_specific_validation")


def get_qc_profile() -> EPWQCProfile:
    """Get the QC profile for EPW adapter"""
    return EPWQCProfile()
