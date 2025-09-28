from hive_logging import get_logger

logger = get_logger(__name__)
"""
NASA POWER Weather Data Provider

Implementation of BaseWeatherProvider for NASA POWER API.
Based on the existing meteo_client.py but integrated into the modular architecture.
"""

import requests
import json
import pandas as pd
from datetime import datetime
import urllib.parse
import numpy as np
from collections import defaultdict
from typing import Dict, Any, Optional
import logging

from .base_provider import BaseWeatherProvider


class NasaPowerProvider(BaseWeatherProvider):
    """NASA POWER API weather data provider."""

    BASE_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"

    def __init__(self):
        """Initialize NASA POWER provider."""
        super().__init__("NASA POWER")

        # NASA POWER parameters we fetch
        self.api_parameters = [
            "T2M",  # Temperature (°C)
            "WS10M",  # Wind Speed (m/s)
            "ALLSKY_SFC_SW_DWN",  # Solar Radiation (W/m²)
            "PRECTOTCORR",  # Precipitation (mm/hour)
            "RH2M",  # Relative Humidity (%)
        ]

        # Mapping from NASA POWER parameter names to standardized names
        self.parameter_map = {
            "T2M": "temperature_celsius",
            "PRECTOTCORR": "precipitation_mm_hr",
            "ALLSKY_SFC_SW_DWN": "solar_radiation_wm2",
            "WS10M": "wind_speed_m_s",
            "RH2M": "relative_humidity_percent",
        }

        # Request timeout in seconds
        self.timeout = 30

    def get_available_parameters(self) -> Dict[str, str]:
        """Get available parameters from NASA POWER."""
        return self.parameter_map.copy()

    def validate_location(self, latitude: float, longitude: float) -> bool:
        """
        Validate location for NASA POWER (global coverage).

        Args:
            latitude: Latitude (-90 to 90)
            longitude: Longitude (-180 to 180)

        Returns:
            True if valid coordinates, False otherwise
        """
        return (-90 <= latitude <= 90) and (-180 <= longitude <= 180)

    def validate_date_range(self, start_date: str, end_date: str) -> bool:
        """
        Validate date range for NASA POWER.

        NASA POWER typically has data from 1981 onwards.
        Dates should be in YYYYMMDD format.

        Args:
            start_date: Start date as YYYYMMDD string
            end_date: End date as YYYYMMDD string

        Returns:
            True if valid date range, False otherwise
        """
        try:
            # Parse dates
            start = datetime.strptime(start_date, "%Y%m%d")
            end = datetime.strptime(end_date, "%Y%m%d")

            # Check that start is before end
            if start >= end:
                return False

            # NASA POWER data typically starts from 1981
            earliest_date = datetime(1981, 1, 1)
            if start < earliest_date:
                self.logger.warning(f"Start date {start_date} is before NASA POWER data availability (1981)")
                return False

            return True

        except ValueError:
            self.logger.error(f"Invalid date format. Expected YYYYMMDD, got start={start_date}, end={end_date}")
            return False

    def fetch_raw_data(
        self, latitude: float, longitude: float, start_date: str, end_date: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch raw weather data from NASA POWER API.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            **kwargs: Additional parameters (unused for NASA POWER)

        Returns:
            Raw JSON data from API or None if failed
        """
        params = {
            "start": start_date,
            "end": end_date,
            "latitude": f"{float(latitude):.4f}",
            "longitude": f"{float(longitude):.4f}",
            "parameters": ",".join(self.api_parameters),
            "community": "RE",  # Renewable Energy community
            "format": "JSON",
            "time_standard": "UTC",
        }

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        self.logger.info(f"Fetching data from NASA POWER: {url}")

        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)

            self.logger.info("Successfully fetched raw data from NASA POWER API")
            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching NASA POWER data: {e}")
            return None

    def process_raw_data(self, raw_data: Dict[str, Any]) -> pd.DataFrame:
        """
        Process raw JSON data from NASA POWER API into a standardized DataFrame.

        Args:
            raw_data: Raw JSON data from NASA POWER API

        Returns:
            Processed DataFrame with standardized column names and datetime index
        """
        if not raw_data:
            self.logger.warning("No raw data provided for processing")
            return pd.DataFrame()

        processed_data: Dict[str, Dict[pd.Timestamp, float]] = defaultdict(dict)

        try:
            parameters_data = raw_data.get("properties", {}).get("parameter", {})
            if not parameters_data:
                self.logger.error("Raw data JSON is missing 'properties.parameter' keys")
                return pd.DataFrame()

            for param_api, values_dict in parameters_data.items():
                if param_api in self.api_parameters:
                    col_name = self.parameter_map.get(param_api, param_api)

                    for date_key, value in values_dict.items():
                        try:
                            # Handle missing/invalid values (NASA POWER uses -999 for missing)
                            if isinstance(value, (int, float)) and value < -990:
                                val_numeric = np.nan
                            else:
                                val_numeric = float(value)

                            # Parse datetime (expecting YYYYMMDDHH format for hourly data)
                            if len(date_key) == 10:  # YYYYMMDDHH
                                dt = pd.to_datetime(datetime.strptime(date_key, "%Y%m%d%H"))
                            elif len(date_key) == 8:  # YYYYMMDD
                                self.logger.warning(
                                    f"Received daily date key '{date_key}' for param '{param_api}'. Expected hourly (YYYYMMDDHH)"
                                )
                                continue
                            else:
                                self.logger.warning(f"Skipping malformed date key: {date_key} for param {param_api}")
                                continue

                            processed_data[col_name][dt] = val_numeric

                        except ValueError as e:
                            self.logger.warning(
                                f"Skipping value '{value}' for date '{date_key}' in param '{param_api}' due to ValueError: {e}"
                            )
                            continue

            # Convert processed_data to DataFrame
            df_series = {}
            for col, data_dict in processed_data.items():
                if data_dict:  # Only create series if there is data
                    df_series[col] = pd.Series(data_dict)
                else:
                    self.logger.warning(f"No data processed for column: {col}")

            if not df_series:
                self.logger.warning("No data series were created. Returning empty DataFrame")
                return pd.DataFrame()

            df = pd.DataFrame(df_series)
            df.index.name = "datetime"
            df = df.sort_index()  # Ensure chronological order

        except Exception as e:
            self.logger.error(f"Error processing NASA POWER data: {e}", exc_info=True)
            return pd.DataFrame()

        # Validate processed data
        for col in df.columns:
            if pd.isna(df[col]).all():
                self.logger.warning(f"All values for column '{col}' are NaN. This might indicate a data issue")

        self.logger.info(f"Processed NASA POWER data into DataFrame with shape: {df.shape}")
        return df


# Example usage for testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    provider = NasaPowerProvider()

    # Test with Wageningen, NL coordinates
    lat_wageningen = 51.97
    lon_wageningen = 5.66

    # Test a small date range
    start = "20220101"
    end = "20220131"

    # Test the complete workflow
    df = provider.get_data(lat_wageningen, lon_wageningen, start, end)

    if df is not None and not df.empty:
        logger.info("Successfully fetched and processed data:")
        logger.info(df.head())
        logger.info(f"\nDataFrame shape: {df.shape}")
        logger.info(f"Columns: {df.columns.tolist()}")
        logger.info("\nBasic statistics:")
        logger.info(df.describe())
    else:
        logger.error("Failed to fetch or process data")
