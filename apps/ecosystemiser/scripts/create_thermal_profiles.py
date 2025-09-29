#!/usr/bin/env python3
"""Create thermal profiles for multi-domain testing."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from hive_logging import get_logger

logger = get_logger(__name__)


def create_thermal_profiles() -> None:
    """Create realistic thermal demand profiles for heating."""
    # Load the base electrical profiles
    data_dir = Path(__file__).parent.parent / "data" / "profiles"
    base_profiles = pd.read_csv(data_dir / "golden_24h_profiles.csv")

    logger.info("Creating thermal profiles...")

    # Thermal demand profile (typical residential heating)
    # Higher in morning and evening, lower during day and night
    thermal_profile_normalized = np.array(
        [
            0.6,
            0.5,
            0.4,
            0.4,
            0.4,
            0.5,  # Night: moderate heating
            0.8,
            1.0,
            0.7,
            0.3,
            0.3,
            0.3,  # Morning: peak then reduce
            0.3,
            0.3,
            0.3,
            0.4,
            0.5,
            0.7,  # Day: low then increasing
            1.0,
            0.9,
            0.8,
            0.7,
            0.6,
            0.6,  # Evening: high then moderate
        ]
    )

    # Scale to realistic thermal demand (typical residential: 5-15 kW thermal)
    thermal_peak_kw = 15.0
    thermal_demand_kw = thermal_profile_normalized * thermal_peak_kw

    # Heat pump COP profile (temperature dependent, lower at night/morning)
    cop_profile = np.array(
        [
            2.5,
            2.3,
            2.2,
            2.2,
            2.2,
            2.3,  # Night: lower COP
            2.4,
            2.6,
            2.8,
            3.2,
            3.4,
            3.5,  # Morning to noon: improving COP
            3.5,
            3.4,
            3.2,
            3.0,
            2.8,
            2.6,  # Afternoon: decreasing COP
            2.5,
            2.4,
            2.4,
            2.4,
            2.5,
            2.5,  # Evening: moderate COP
        ]
    )

    # Calculate electrical demand for heat pump (thermal_demand / COP)
    heat_pump_electrical_kw = thermal_demand_kw / cop_profile

    # Add thermal columns to base profiles
    thermal_profiles = base_profiles.copy()
    thermal_profiles["heat_demand_kw"] = thermal_demand_kw
    thermal_profiles["heat_pump_cop"] = cop_profile
    thermal_profiles["heat_pump_electrical_kw"] = heat_pump_electrical_kw
    thermal_profiles["heat_demand_normalized"] = thermal_profile_normalized

    # Calculate total electrical demand (original + heat pump)
    thermal_profiles["total_electrical_demand_kw"] = (
        thermal_profiles["power_demand_kw"] + thermal_profiles["heat_pump_electrical_kw"]
    )

    # Print statistics
    logger.info("\nThermal Profile Statistics:")
    logger.info("  Heat demand peak: {max(thermal_demand_kw):.1f} kW")
    logger.info("  Heat demand daily total: {sum(thermal_demand_kw):.1f} kWh")
    logger.info("  COP range: {min(cop_profile):.1f} - {max(cop_profile):.1f}")
    logger.info("  Heat pump electrical peak: {max(heat_pump_electrical_kw):.1f} kW")
    logger.info("  Total electrical demand peak: {max(thermal_profiles['total_electrical_demand_kw']):.1f} kW")

    return thermal_profiles


def create_thermal_seasonal_variants(base_thermal) -> None:
    """Create seasonal variants with different thermal demands."""
    variants = {}

    # Winter: High thermal demand, low COP
    winter = base_thermal.copy()
    winter["heat_demand_kw"] *= 2.0  # Double heating demand
    winter["heat_pump_cop"] *= 0.7  # 30% lower COP (cold weather)
    winter["heat_pump_electrical_kw"] = winter["heat_demand_kw"] / winter["heat_pump_cop"]
    winter["total_electrical_demand_kw"] = winter["power_demand_kw"] + winter["heat_pump_electrical_kw"]
    winter["season"] = "winter"
    variants["winter"] = winter

    # Summer: Minimal thermal demand (hot water only)
    summer = base_thermal.copy()
    summer["heat_demand_kw"] *= 0.2  # 20% demand (hot water only)
    summer["heat_pump_cop"] *= 1.2  # 20% higher COP (warm weather)
    summer["heat_pump_electrical_kw"] = summer["heat_demand_kw"] / summer["heat_pump_cop"]
    summer["total_electrical_demand_kw"] = summer["power_demand_kw"] + summer["heat_pump_electrical_kw"]
    summer["season"] = "summer"
    variants["summer"] = summer

    # Spring/Fall: Moderate thermal demand
    spring = base_thermal.copy()
    spring["heat_demand_kw"] *= 1.0  # Baseline demand
    spring["heat_pump_cop"] *= 1.0  # Baseline COP
    spring["heat_pump_electrical_kw"] = spring["heat_demand_kw"] / spring["heat_pump_cop"]
    spring["total_electrical_demand_kw"] = spring["power_demand_kw"] + spring["heat_pump_electrical_kw"]
    spring["season"] = "spring"
    variants["spring"] = spring

    return variants


def create_thermal_storage_profile() -> None:
    """Create heat buffer (thermal storage) parameters."""
    # Heat buffer sizing: typically 200-500L for residential
    heat_buffer_params = {
        "capacity_thermal_kwh": 20.0,  # 20 kWh thermal storage
        "max_charge_rate_kw": 15.0,  # Can absorb full heat pump output
        "max_discharge_rate_kw": 15.0,  # Can supply full thermal demand
        "thermal_efficiency": 0.95,  # 5% thermal losses
        "initial_energy_pct": 0.5,  # Start 50% charged
        "temperature_range_c": {"min": 40, "max": 80, "nominal": 60},
    }

    return heat_buffer_params


def main() -> None:
    """Main thermal profile creation."""
    logger.info("=" * 60)
    logger.info("THERMAL PROFILE CREATION")
    logger.info("=" * 60)

    data_dir = Path(__file__).parent.parent / "data" / "profiles"

    # Create base thermal profiles
    thermal_profiles = create_thermal_profiles()

    # Save base thermal profiles
    thermal_path = data_dir / "golden_24h_thermal.csv"
    thermal_profiles.to_csv(thermal_path, index=False)
    logger.info("Saved thermal profiles: {thermal_path}")

    # Create 7-day thermal profiles
    thermal_7day = []
    for day in range(7):
        day_profiles = thermal_profiles.copy()
        day_profiles["hour"] = day_profiles["hour"] + (day * 24)
        day_profiles["day"] = day + 1
        thermal_7day.append(day_profiles)

    thermal_7day_df = pd.concat(thermal_7day, ignore_index=True)
    thermal_7day_path = data_dir / "golden_7day_thermal.csv"
    thermal_7day_df.to_csv(thermal_7day_path, index=False)
    logger.info("Saved 7-day thermal profiles: {thermal_7day_path}")

    # Create seasonal thermal variants
    thermal_variants = create_thermal_seasonal_variants(thermal_profiles)
    for season, profiles in thermal_variants.items():
        season_path = data_dir / f"golden_24h_thermal_{season}.csv"
        profiles.to_csv(season_path, index=False)
        logger.info("Saved {season} thermal profiles: {season_path}")

    # Create heat buffer parameters
    heat_buffer_params = create_thermal_storage_profile()
    buffer_path = data_dir / "heat_buffer_params.json"
    with open(buffer_path, "w") as f:
        json.dump(heat_buffer_params, f, indent=2)
    logger.info("Saved heat buffer params: {buffer_path}")

    # Update metadata
    metadata_path = data_dir / "profiles_metadata.json"
    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    metadata["thermal_profiles"] = {
        "golden_24h_thermal.csv": "Base 24h electrical + thermal profiles",
        "golden_7day_thermal.csv": "Extended 7-day thermal profiles",
        "golden_24h_thermal_winter.csv": "Winter thermal (2x demand, 0.7x COP)",
        "golden_24h_thermal_summer.csv": "Summer thermal (0.2x demand, 1.2x COP)",
        "golden_24h_thermal_spring.csv": "Spring thermal (baseline)",
        "heat_buffer_params.json": "Thermal storage parameters",
    }

    metadata["thermal_units"] = {
        "heat_demand_kw": "kilowatts thermal",
        "heat_pump_cop": "coefficient of performance (dimensionless)",
        "heat_pump_electrical_kw": "kilowatts electrical",
        "total_electrical_demand_kw": "kilowatts electrical (power + heat pump)",
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Updated metadata: {metadata_path}")

    logger.info("\n" + "=" * 60)
    logger.info("THERMAL PROFILE CREATION COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
