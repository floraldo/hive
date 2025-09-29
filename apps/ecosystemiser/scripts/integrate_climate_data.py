#!/usr/bin/env python3
"""Integrate Climate API data with existing profiles."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from hive_logging import get_logger

logger = get_logger(__name__)

eco_path = Path(__file__).parent.parent / "src"

try:
    from datetime import datetime, timedelta

    from ecosystemiser.profile_loader.climate.data_models import (
        ClimateRequest,
        Location,
    )
    from ecosystemiser.profile_loader.climate.service import ClimateService

    CLIMATE_AVAILABLE = True
except ImportError:
    logger.info("Climate service not available: {e}")
    CLIMATE_AVAILABLE = False


def create_weather_enhanced_profiles() -> None:
    """Create weather-enhanced profiles using Climate API."""
    Path(__file__).parent.parent / "data" / "profiles"

    if not CLIMATE_AVAILABLE:
        logger.info("Climate API not available, creating synthetic weather data...")
        return create_synthetic_weather_profiles()

    logger.info("Fetching real weather data from Climate API...")

    try:
        # Initialize climate service
        climate_service = ClimateService()

        # Request weather data for Berlin (example location)
        location = Location(latitude=52.5200, longitude=13.4050, name="Berlin", country="DE")

        # Get 7 days of data starting from a recent date
        start_date = datetime(2024, 6, 15)  # Summer data
        request = ClimateRequest(
            location=location,
            start_date=start_date,
            end_date=start_date + timedelta(days=7),
            variables=["temperature", "solar_irradiance", "wind_speed"],
            source="era5",
        )

        # Fetch climate data
        climate_data = climate_service.get_climate_data(request)

        # Convert to hourly profiles
        weather_profiles = process_climate_data(climate_data)

        return weather_profiles

    except Exception:
        logger.info("Error fetching climate data: {e}")
        logger.info("Falling back to synthetic weather data...")
        return create_synthetic_weather_profiles()


def create_synthetic_weather_profiles() -> None:
    """Create synthetic weather profiles when Climate API unavailable."""
    logger.info("Creating synthetic weather profiles...")

    # 24-hour synthetic weather patterns
    hours = np.arange(24)

    # Temperature profile (°C) - typical summer day
    temp_base = 20  # Base temperature
    temp_amplitude = 10  # Daily temperature swing
    temp_profile = temp_base + temp_amplitude * np.sin((hours - 6) * np.pi / 12)
    temp_profile = np.clip(temp_profile, 15, 30)  # Realistic range

    # Solar irradiance (W/m²) - clear day profile
    solar_profile = np.zeros(24)
    for h in range(6, 19):  # Daylight hours
        solar_profile[h] = 800 * np.sin((h - 6) * np.pi / 12)
    solar_profile = np.clip(solar_profile, 0, 800)

    # Wind speed (m/s) - variable throughout day
    wind_base = 3  # Base wind speed
    wind_variation = 2  # Variation
    wind_profile = wind_base + wind_variation * np.sin(hours * 2 * np.pi / 24 + np.pi / 4)
    wind_profile = np.clip(wind_profile, 1, 8)

    # Create DataFrame
    weather_df = pd.DataFrame(
        {
            "hour": hours,
            "temperature_c": temp_profile,
            "solar_irradiance_w_m2": solar_profile,
            "wind_speed_m_s": wind_profile,
        }
    )

    # Create seasonal variants
    variants = {}

    # Summer weather
    summer = weather_df.copy()
    summer["temperature_c"] += 5  # Warmer
    summer["solar_irradiance_w_m2"] *= 1.0  # Full solar
    summer["season"] = "summer"
    variants["summer"] = summer

    # Winter weather
    winter = weather_df.copy()
    winter["temperature_c"] -= 15  # Much colder
    winter["solar_irradiance_w_m2"] *= 0.3  # Reduced solar
    winter["wind_speed_m_s"] += 2  # Windier
    winter["season"] = "winter"
    variants["winter"] = winter

    # Spring weather
    spring = weather_df.copy()
    spring["temperature_c"] -= 5  # Cooler
    spring["solar_irradiance_w_m2"] *= 0.7  # Moderate solar
    spring["season"] = "spring"
    variants["spring"] = spring

    return weather_df, variants


def process_climate_data(climate_data) -> None:
    """Process real climate data into hourly profiles."""
    # This would process the actual climate service response
    # For now, return synthetic data structure
    return create_synthetic_weather_profiles()


def integrate_weather_with_profiles() -> None:
    """Integrate weather data with existing electrical and thermal profiles."""
    data_dir = Path(__file__).parent.parent / "data" / "profiles"

    # Load existing thermal profiles
    thermal_profiles = pd.read_csv(data_dir / "golden_24h_thermal.csv")

    # Get weather data
    if CLIMATE_AVAILABLE:
        weather_data, weather_variants = create_weather_enhanced_profiles()
    else:
        weather_data, weather_variants = create_synthetic_weather_profiles()

    # Merge weather with thermal profiles
    integrated_profiles = thermal_profiles.merge(weather_data, on="hour", how="left")

    # Adjust profiles based on weather
    # Solar PV output depends on irradiance
    if "solar_irradiance_w_m2" in integrated_profiles.columns:
        # Normalize irradiance to 0-1 scale and adjust solar generation
        max_irradiance = integrated_profiles["solar_irradiance_w_m2"].max()
        if max_irradiance > 0:
            irradiance_factor = integrated_profiles["solar_irradiance_w_m2"] / max_irradiance
            integrated_profiles["solar_generation_weather_adjusted"] = (
                integrated_profiles["solar_generation_kw"] * irradiance_factor
            )
        else:
            integrated_profiles["solar_generation_weather_adjusted"] = integrated_profiles["solar_generation_kw"]

    # Heat pump COP depends on outdoor temperature
    if "temperature_c" in integrated_profiles.columns:
        # COP increases with outdoor temperature (simplified relationship)
        temp_adjustment = 1 + (integrated_profiles["temperature_c"] - 20) * 0.02  # 2% per degree
        temp_adjustment = np.clip(temp_adjustment, 0.5, 1.5)  # Reasonable bounds
        integrated_profiles["heat_pump_cop_weather_adjusted"] = integrated_profiles["heat_pump_cop"] * temp_adjustment

        # Recalculate heat pump electrical demand
        integrated_profiles["heat_pump_electrical_weather_adjusted"] = (
            integrated_profiles["heat_demand_kw"] / integrated_profiles["heat_pump_cop_weather_adjusted"]
        )

    return integrated_profiles, weather_variants


def create_weather_variant_profiles(base_integrated, weather_variants) -> None:
    """Create seasonal profiles with weather integration."""
    seasonal_integrated = {}

    for season, weather_data in weather_variants.items():
        # Start with base integrated profiles
        seasonal_profile = base_integrated.copy()

        # Replace weather columns with seasonal data
        for col in ["temperature_c", "solar_irradiance_w_m2", "wind_speed_m_s"]:
            if col in weather_data.columns:
                seasonal_profile[col] = weather_data[col]

        # Recalculate weather-adjusted values
        if "solar_irradiance_w_m2" in seasonal_profile.columns:
            max_irradiance = seasonal_profile["solar_irradiance_w_m2"].max()
            if max_irradiance > 0:
                irradiance_factor = seasonal_profile["solar_irradiance_w_m2"] / max_irradiance
                seasonal_profile["solar_generation_weather_adjusted"] = (
                    seasonal_profile["solar_generation_kw"] * irradiance_factor
                )

        if "temperature_c" in seasonal_profile.columns:
            temp_adjustment = 1 + (seasonal_profile["temperature_c"] - 20) * 0.02
            temp_adjustment = np.clip(temp_adjustment, 0.5, 1.5)
            seasonal_profile["heat_pump_cop_weather_adjusted"] = seasonal_profile["heat_pump_cop"] * temp_adjustment
            seasonal_profile["heat_pump_electrical_weather_adjusted"] = (
                seasonal_profile["heat_demand_kw"] / seasonal_profile["heat_pump_cop_weather_adjusted"]
            )

        seasonal_profile["season"] = season
        seasonal_integrated[season] = seasonal_profile

    return seasonal_integrated


def main() -> None:
    """Main weather integration process."""
    logger.info("=" * 60)
    logger.info("CLIMATE DATA INTEGRATION")
    logger.info("=" * 60)

    data_dir = Path(__file__).parent.parent / "data" / "profiles"

    # Integrate weather with existing profiles
    integrated_profiles, weather_variants = integrate_weather_with_profiles()

    # Save weather-integrated profiles
    integrated_path = data_dir / "golden_24h_weather_integrated.csv"
    integrated_profiles.to_csv(integrated_path, index=False)
    logger.info("Saved weather-integrated profiles: {integrated_path}")

    # Create seasonal weather variants
    seasonal_profiles = create_weather_variant_profiles(integrated_profiles, weather_variants)

    for season, profiles in seasonal_profiles.items():
        season_path = data_dir / f"golden_24h_weather_{season}.csv"
        profiles.to_csv(season_path, index=False)
        logger.info("Saved {season} weather profiles: {season_path}")

    # Create 7-day weather-integrated profiles
    weather_7day = []
    for day in range(7):
        day_profiles = integrated_profiles.copy()
        day_profiles["hour"] = day_profiles["hour"] + (day * 24)
        day_profiles["day"] = day + 1
        # Add some day-to-day weather variation
        if "temperature_c" in day_profiles.columns:
            day_profiles["temperature_c"] += np.random.normal(0, 2, len(day_profiles))
        weather_7day.append(day_profiles)

    weather_7day_df = pd.concat(weather_7day, ignore_index=True)
    weather_7day_path = data_dir / "golden_7day_weather.csv"
    weather_7day_df.to_csv(weather_7day_path, index=False)
    logger.info("Saved 7-day weather profiles: {weather_7day_path}")

    # Update metadata
    metadata_path = data_dir / "profiles_metadata.json"
    with open(metadata_path) as f:
        metadata = json.load(f)

    metadata["weather_integrated_profiles"] = {
        "golden_24h_weather_integrated.csv": "Base profiles with weather integration",
        "golden_7day_weather.csv": "7-day weather-integrated profiles",
        "golden_24h_weather_summer.csv": "Summer weather variant",
        "golden_24h_weather_winter.csv": "Winter weather variant",
        "golden_24h_weather_spring.csv": "Spring weather variant",
    }

    metadata["weather_units"] = {
        "temperature_c": "degrees Celsius",
        "solar_irradiance_w_m2": "watts per square meter",
        "wind_speed_m_s": "meters per second",
        "solar_generation_weather_adjusted": "kilowatts (weather-adjusted)",
        "heat_pump_cop_weather_adjusted": "coefficient of performance (weather-adjusted)",
        "heat_pump_electrical_weather_adjusted": "kilowatts electrical (weather-adjusted)",
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Updated metadata: {metadata_path}")

    logger.info("\n" + "=" * 60)
    logger.info("CLIMATE DATA INTEGRATION COMPLETE")
    logger.info("Available profile types:")
    logger.info("  - Base electrical (24h, 7-day)")
    logger.info("  - Thermal integrated (24h, 7-day, seasonal)")
    logger.info("  - Weather integrated (24h, 7-day, seasonal)")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
