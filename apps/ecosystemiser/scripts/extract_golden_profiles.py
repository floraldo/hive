#!/usr/bin/env python3
"""Extract profiles from golden dataset for standardized testing."""

import json
from pathlib import Path

import numpy as np
import pandas as pd


def extract_profiles_from_golden() -> None:
    """Extract solar and demand profiles from the golden dataset."""

from hive_logging import get_logger

logger = get_logger(__name__)
    # Load golden dataset
    golden_path = Path(__file__).parent.parent / "tests" / "systemiser_minimal_golden.json"

    with open(golden_path, "r") as f:
        golden_data = json.load(f)

    logger.info("Extracting profiles from golden dataset...")
    logger.info("Components: {golden_data['metadata']['components']}")
    logger.info("Timesteps: {golden_data['metadata']['timesteps']}")

    # Extract solar generation profile
    solar_to_demand = np.array(golden_data["flows"]["SolarPV_P_PowerDemand"]["values"])
    solar_to_battery = np.array(golden_data["flows"]["SolarPV_P_Battery"]["values"])
    solar_to_grid = np.array(golden_data["flows"]["SolarPV_P_Grid"]["values"])

    # Total solar generation per timestep
    solar_generation = solar_to_demand + solar_to_battery + solar_to_grid

    # Extract demand profile
    grid_to_demand = np.array(golden_data["flows"]["Grid_P_PowerDemand"]["values"])
    solar_to_demand = np.array(golden_data["flows"]["SolarPV_P_PowerDemand"]["values"])
    battery_to_demand = np.array(golden_data["flows"]["Battery_P_PowerDemand"]["values"])

    # Total demand per timestep
    total_demand = grid_to_demand + solar_to_demand + battery_to_demand

    # Create profiles dataframe
    hours = list(range(24))
    profiles_df = pd.DataFrame(
        {
            "hour": hours,
            "solar_generation_kw": solar_generation,
            "power_demand_kw": total_demand,
            "solar_normalized": solar_generation / max(solar_generation)
            if max(solar_generation) > 0
            else solar_generation,
            "demand_normalized": total_demand / max(total_demand) if max(total_demand) > 0 else total_demand,
        }
    )

    # Print profile statistics
    logger.info("\nSolar Generation Profile:")
    logger.info("  Peak: {max(solar_generation):.2f} kW at hour {np.argmax(solar_generation)}")
    logger.info("  Daily total: {sum(solar_generation):.2f} kWh")
    logger.info("  Non-zero hours: {np.count_nonzero(solar_generation)}")

    logger.info("\nPower Demand Profile:")
    logger.info("  Peak: {max(total_demand):.2f} kW at hour {np.argmax(total_demand)}")
    logger.info("  Daily total: {sum(total_demand):.2f} kWh")
    logger.info("  Base load: {min(total_demand[total_demand > 0]):.2f} kW")

    return profiles_df


def create_extended_profiles(base_profiles, days=7):
    """Create extended profiles for multi-day testing."""
    extended_profiles = []

    for day in range(days):
        day_profiles = base_profiles.copy()
        day_profiles["hour"] = day_profiles["hour"] + (day * 24)
        day_profiles["day"] = day + 1
        extended_profiles.append(day_profiles)

    return pd.concat(extended_profiles, ignore_index=True)


def create_seasonal_variants(base_profiles) -> None:
    """Create seasonal variants of the base profiles."""
    variants = {}

    # Winter: Reduced solar, increased heating demand
    winter = base_profiles.copy()
    winter["solar_generation_kw"] *= 0.3  # 30% of summer solar
    winter["power_demand_kw"] *= 1.5  # 50% more demand for heating
    winter["season"] = "winter"
    variants["winter"] = winter

    # Summer: Peak solar, reduced demand
    summer = base_profiles.copy()
    summer["solar_generation_kw"] *= 1.0  # Baseline is summer
    summer["power_demand_kw"] *= 0.8  # 20% less demand
    summer["season"] = "summer"
    variants["summer"] = summer

    # Spring/Fall: Moderate values
    spring = base_profiles.copy()
    spring["solar_generation_kw"] *= 0.7  # 70% of summer solar
    spring["power_demand_kw"] *= 1.1  # 10% more demand
    spring["season"] = "spring"
    variants["spring"] = spring

    return variants


def main() -> None:
    """Main profile extraction and organization."""
    logger.info("=" * 60)
    logger.info("GOLDEN DATASET PROFILE EXTRACTION")
    logger.info("=" * 60)

    # Create data directory
    data_dir = Path(__file__).parent.parent / "data" / "profiles"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Extract base profiles
    base_profiles = extract_profiles_from_golden()

    # Save base 24-hour profiles
    base_path = data_dir / "golden_24h_profiles.csv"
    base_profiles.to_csv(base_path, index=False)
    logger.info("\nSaved base profiles: {base_path}")

    # Create 7-day extended profiles
    week_profiles = create_extended_profiles(base_profiles, days=7)
    week_path = data_dir / "golden_7day_profiles.csv"
    week_profiles.to_csv(week_path, index=False)
    logger.info("Saved 7-day profiles: {week_path}")

    # Create seasonal variants
    seasonal_variants = create_seasonal_variants(base_profiles)
    for season, profiles in seasonal_variants.items():
        season_path = data_dir / f"golden_24h_{season}.csv"
        profiles.to_csv(season_path, index=False)
        logger.info("Saved {season} profiles: {season_path}")

    # Create summary metadata
    metadata = {
        "source": "systemiser_minimal_golden.json",
        "extraction_date": "2025-09-29",
        "baseline_system": "4-component residential microgrid",
        "time_resolution": "hourly",
        "profiles_available": [
            "golden_24h_profiles.csv - Base 24-hour profiles",
            "golden_7day_profiles.csv - Extended 7-day profiles",
            "golden_24h_winter.csv - Winter variant (30% solar, 150% demand)",
            "golden_24h_summer.csv - Summer variant (100% solar, 80% demand)",
            "golden_24h_spring.csv - Spring variant (70% solar, 110% demand)",
        ],
        "units": {
            "solar_generation_kw": "kilowatts",
            "power_demand_kw": "kilowatts",
            "solar_normalized": "0-1 scale",
            "demand_normalized": "0-1 scale",
        },
    }

    metadata_path = data_dir / "profiles_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved metadata: {metadata_path}")

    logger.info("\n" + "=" * 60)
    logger.info("PROFILE EXTRACTION COMPLETE")
    logger.info("Data location: {data_dir}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
