from hive_logging import get_logger

logger = get_logger(__name__)
"""
Profile Manager for Systemiser

Unified interface for loading component profiles from different data sources.
Provides backward compatibility with legacy data while enabling weather-based profiles.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import logging
from typing import Dict, Any, Optional, Union, Tuple
from enum import Enum

# Import existing system_setup for backward compatibility
from .system_setup import load_profiles as load_legacy_profiles

# Import weather utilities
from .weather_utils import create_component_profiles_from_weather, calculate_weather_statistics

# Use Systemiser logger
try:
    from Systemiser.utils.logger import setup_logging

    logger = setup_logging("ProfileManager", level=logging.INFO)
except ImportError:
    logger = logging.getLogger("ProfileManager_Fallback")
    logger.warning("Could not import Systemiser logger, using fallback.")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


class ProfileSource(Enum):
    """Enumeration of available profile data sources."""

    LEGACY = "legacy"  # Use existing CSV/JSON data sources
    WEATHER = "weather"  # Use weather-based profile generation
    HYBRID = "hybrid"  # Combine both sources (weather for some, legacy for others)


class ProfileManager:
    """
    Unified profile management system for Systemiser.

    Provides a single interface to load component profiles from different sources
    while maintaining backward compatibility with existing data.
    """

    def __init__(self, default_source: ProfileSource = ProfileSource.LEGACY):
        """
        Initialize the profile manager.

        Args:
            default_source: Default data source for profile loading
        """
        self.default_source = default_source
        self.logger = logger

        # Weather manager (lazy initialization)
        self._weather_manager = None

        # Cache for loaded profiles
        self._profile_cache = {}

        self.logger.info(f"Initialized ProfileManager with default source: {default_source.value}")

    @property
    def weather_manager(self):
        """Lazy initialization of weather manager."""
        if self._weather_manager is None:
            try:
                from ..data.weather import WeatherDataManager

                self._weather_manager = WeatherDataManager()
                self.logger.info("Initialized WeatherDataManager")
            except ImportError as e:
                self.logger.error(f"Failed to import WeatherDataManager: {e}")
                raise ImportError("Weather module not available. Install weather dependencies or use legacy profiles.")
        return self._weather_manager

    def load_profiles(
        self,
        N: int = 24,
        source: Optional[ProfileSource] = None,
        weather_config: Optional[Dict[str, Any]] = None,
        legacy_override: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Load component profiles from the specified source.

        Args:
            N: Number of time steps
            source: Profile data source (uses default if None)
            weather_config: Configuration for weather-based profiles
            legacy_override: Force use of legacy profiles for all components

        Returns:
            Dictionary of profiles in legacy format for backward compatibility
        """
        source = source or self.default_source

        if legacy_override or source == ProfileSource.LEGACY:
            return self._load_legacy_profiles(N)
        elif source == ProfileSource.WEATHER:
            return self._load_weather_profiles(N, weather_config)
        elif source == ProfileSource.HYBRID:
            return self._load_hybrid_profiles(N, weather_config)
        else:
            raise ValueError(f"Unknown profile source: {source}")

    def _load_legacy_profiles(self, N: int) -> Dict[str, Dict[str, Any]]:
        """Load profiles using the existing legacy system."""
        self.logger.info(f"Loading legacy profiles for N={N}")

        try:
            # Use existing load_profiles function
            profiles = load_legacy_profiles(N)
            self.logger.info(f"Successfully loaded {len(profiles)} legacy profiles")
            return profiles

        except Exception as e:
            self.logger.error(f"Failed to load legacy profiles: {e}")
            raise

    def _load_weather_profiles(self, N: int, weather_config: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Load profiles from weather data."""
        self.logger.info(f"Loading weather-based profiles for N={N}")

        if weather_config is None:
            raise ValueError("weather_config is required for weather-based profiles")

        # Extract weather data parameters
        location = weather_config.get("location", {})
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        date_range = weather_config.get("date_range", {})

        if latitude is None or longitude is None:
            raise ValueError("latitude and longitude must be specified in weather_config.location")

        # Get weather data
        weather_df = self._get_weather_data(latitude, longitude, date_range, N)

        # Get component configurations
        component_configs = weather_config.get("components", {})

        # Generate weather-based profiles
        weather_profiles = create_component_profiles_from_weather(weather_df, component_configs)

        # Convert to legacy format
        legacy_profiles = self._convert_to_legacy_format(weather_profiles, N)

        # Add weather statistics for reference
        legacy_profiles["_weather_stats"] = {"data": calculate_weather_statistics(weather_df)}

        self.logger.info(f"Successfully loaded {len(legacy_profiles)} weather-based profiles")
        return legacy_profiles

    def _load_hybrid_profiles(self, N: int, weather_config: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Load profiles using a combination of weather and legacy sources."""
        self.logger.info(f"Loading hybrid profiles for N={N}")

        # Start with legacy profiles as base
        profiles = self._load_legacy_profiles(N)

        # Override with weather-based profiles if configuration is provided
        if weather_config is not None:
            try:
                weather_profiles = self._load_weather_profiles(N, weather_config)

                # Define which profiles to override with weather data
                weather_overrides = weather_config.get("overrides", [])

                for profile_name in weather_overrides:
                    if profile_name in weather_profiles:
                        profiles[profile_name] = weather_profiles[profile_name]
                        self.logger.info(f"Overrode '{profile_name}' with weather-based profile")

                # Add weather statistics
                if "_weather_stats" in weather_profiles:
                    profiles["_weather_stats"] = weather_profiles["_weather_stats"]

            except Exception as e:
                self.logger.warning(f"Failed to load weather profiles for hybrid mode, using legacy only: {e}")

        return profiles

    def _get_weather_data(self, latitude: float, longitude: float, date_range: Dict[str, Any], N: int) -> pd.DataFrame:
        """Get weather data for the specified location and date range."""

        # Default date range if not specified
        if not date_range:
            # Use a representative year
            start_date = "20220101"
            end_date = "20221231"
        else:
            start_date = date_range.get("start_date", "20220101")
            end_date = date_range.get("end_date", "20221231")

        weather_df = self.weather_manager.get_data(
            latitude=latitude, longitude=longitude, start_date=start_date, end_date=end_date, use_cache=True
        )

        if weather_df is None or weather_df.empty:
            raise RuntimeError("Failed to fetch weather data")

        # Resample or truncate to match N timesteps
        if len(weather_df) > N:
            # Take first N timesteps
            weather_df = weather_df.iloc[:N]
        elif len(weather_df) < N:
            # Repeat the data cyclically
            repeats = N // len(weather_df) + 1
            indices = np.tile(range(len(weather_df)), repeats)[:N]
            weather_df = weather_df.iloc[indices]
            weather_df.index = range(N)  # Reset index for consistency

        return weather_df

    def _convert_to_legacy_format(self, profiles: Dict[str, pd.Series], N: int) -> Dict[str, Dict[str, Any]]:
        """Convert weather-based profiles to legacy format."""
        legacy_format = {}

        for name, series in profiles.items():
            if series is not None and not series.empty:
                # Ensure correct length
                data = series.values
                if len(data) > N:
                    data = data[:N]
                elif len(data) < N:
                    # Pad with zeros or repeat
                    repeats = N // len(data) + 1
                    data = np.tile(data, repeats)[:N]

                # Normalize to match legacy behavior
                max_val = max(abs(data).max(), 1e-6)
                legacy_format[name] = {"data": data / max_val}
            else:
                # Empty profile
                legacy_format[name] = {"data": np.zeros(N)}

        return legacy_format

    def get_profile_mapping_guide(self) -> Dict[str, str]:
        """
        Get a mapping guide between legacy profile names and weather-based component types.

        Returns:
            Dictionary mapping legacy names to weather component types
        """
        return {
            # Legacy -> Weather component type
            "solar_pv": "solar_pv",
            "solar_thermal": "solar_pv",  # Can use same solar data
            "base_load": None,  # No direct weather correlation
            "space_heating": "heat_demand",
            "dhw": "heat_demand",  # Domestic hot water
            "temperature": "temperature",  # Direct mapping
            "rainfall": "rainwater_collection",
            "water_demand": None,  # Typically based on occupancy, not weather
        }

    def create_weather_config_template(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Create a template weather configuration for the given location.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Template weather configuration dictionary
        """
        return {
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "name": f"Location_{latitude:.2f}_{longitude:.2f}",
            },
            "date_range": {"start_date": "20220101", "end_date": "20221231", "description": "Full year 2022"},
            "components": {
                "solar_pv": {
                    "type": "solar_pv",
                    "capacity_kw": 40,  # Match legacy system
                    "efficiency": 0.20,
                    "system_losses": 0.15,
                },
                "solar_thermal": {
                    "type": "solar_pv",  # Use solar data for thermal as well
                    "capacity_kw": 20,
                    "efficiency": 0.60,  # Higher efficiency for thermal
                    "system_losses": 0.10,
                },
                "space_heating": {
                    "type": "heat_demand",
                    "base_demand_kw": 15,
                    "heating_threshold_c": 16.0,
                    "design_temp_c": -10.0,
                    "design_demand_multiplier": 3.0,
                },
                "dhw": {
                    "type": "heat_demand",
                    "base_demand_kw": 15,
                    "heating_threshold_c": 10.0,  # Lower threshold for DHW
                    "design_temp_c": -10.0,
                    "design_demand_multiplier": 2.0,
                },
                "rainfall": {"type": "rainwater_collection", "collection_area_m2": 200, "collection_efficiency": 0.8},
            },
            "overrides": ["solar_pv", "solar_thermal", "space_heating", "dhw", "rainfall"],
            "fallback_to_legacy": True,
        }


# Backward compatibility functions
def load_profiles_with_source(
    N: int = 24, source: ProfileSource = ProfileSource.LEGACY, weather_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Backward compatible function for loading profiles with source selection.

    Args:
        N: Number of time steps
        source: Profile data source
        weather_config: Weather configuration (required for weather/hybrid sources)

    Returns:
        Dictionary of profiles in legacy format
    """
    manager = ProfileManager(default_source=source)
    return manager.load_profiles(N=N, weather_config=weather_config)


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test legacy loading
    manager = ProfileManager(ProfileSource.LEGACY)
    try:
        legacy_profiles = manager.load_profiles(N=24)
        logger.info(f"Legacy profiles loaded: {list(legacy_profiles.keys())}")
    except Exception as e:
        logger.error(f"Legacy loading failed: {e}")

    # Test weather-based loading
    weather_config = manager.create_weather_config_template(51.97, 5.66)
    logger.info(f"\nWeather config template: {json.dumps(weather_config, indent=2)}")

    try:
        weather_profiles = manager.load_profiles(N=24, source=ProfileSource.WEATHER, weather_config=weather_config)
        logger.info(f"Weather profiles loaded: {list(weather_profiles.keys())}")
    except Exception as e:
        logger.error(f"Weather loading failed: {e}")
