#!/usr/bin/env python3
"""Extract 8760-hour yearly profiles from legacy SmartHoodsOptimisationTool Systemiser.

This script extracts working yearly simulation data and configurations from the
legacy Systemiser system and converts them to EcoSystemiser-compatible format.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

eco_path = Path(__file__).parent.parent / "src"
legacy_path = Path("/c/git/SmartHoodsOptimisationTool/Systemiser")

from hive_logging import get_logger

logger = get_logger(__name__)


def load_legacy_output_data(output_path: Path) -> dict[str, Any] | None:
    """Load existing legacy output data if available."""
    hourly_file = output_path / "solved_system_flows_hourly.json"
    if hourly_file.exists():
        logger.info(f"Loading existing legacy output: {hourly_file}")
        with open(hourly_file) as f:
            return json.load(f)
    return None


def extract_profiles_from_output(output_data: dict[str, Any]) -> dict[str, np.ndarray]:
    """Extract component profiles from legacy output flows."""
    profiles = {}

    # Extract flows by component type
    for flow in output_data.get("flows", []):
        from_comp = flow["from"]
        to_comp = flow["to"]
        flow_type = flow["type"]
        values = np.array(flow["values"])

        logger.info(f"Processing flow: {from_comp} -> {to_comp} ({flow_type})")
        logger.info(f"  Values shape: {values.shape}, min: {values.min():.2f}, max: {values.max():.2f}")

        # Solar PV generation profile
        if "SOLAR" in from_comp and flow_type == "electricity":
            if "solar_pv" not in profiles:
                profiles["solar_pv"] = np.zeros_like(values)
            profiles["solar_pv"] += values

        # Power demand profile (sum of all electrical consumption)
        elif to_comp in ["BASE_LOAD"] and flow_type == "electricity":
            if "power_demand" not in profiles:
                profiles["power_demand"] = np.zeros_like(values)
            profiles["power_demand"] += values

        # Heat demand profile
        elif "HEATING" in to_comp or "DHW" in to_comp and flow_type == "heat":
            if "heat_demand" not in profiles:
                profiles["heat_demand"] = np.zeros_like(values)
            profiles["heat_demand"] += values

        # Grid import/export
        elif from_comp == "GRID" and flow_type == "electricity":
            profiles["grid_import"] = values
        elif to_comp == "GRID" and flow_type == "electricity":
            profiles["grid_export"] = values

        # Battery flows
        elif "BATTERIES" in from_comp or "BATTERIES" in to_comp:
            if "BATTERIES" in to_comp:
                profiles["battery_charge"] = values
            else:
                profiles["battery_discharge"] = values

    return profiles


def create_weather_based_profiles(n_hours: int = 8760) -> dict[str, np.ndarray]:
    """Create synthetic weather-based profiles for yearly simulation."""
    logger.info(f"Creating weather-based profiles for {n_hours} hours")

    # Create hourly time index for full year
    hours = np.arange(n_hours)

    # Solar generation profile (sinusoidal with daily and seasonal variation)
    # Daily pattern: peak at hour 12 (noon)
    daily_pattern = np.maximum(0, np.sin(2 * np.pi * hours / 24 - np.pi / 2))

    # Seasonal pattern: peak in summer (hour 4380 = ~June)
    seasonal_pattern = 0.5 + 0.5 * np.sin(2 * np.pi * hours / n_hours - np.pi / 2)

    # Combine patterns with noise
    solar_profile = daily_pattern * seasonal_pattern * (0.9 + 0.1 * np.random.random(n_hours))

    # Power demand profile (base load + seasonal heating)
    base_load = 0.4  # 40% base load
    daily_demand = 0.2 * (np.sin(2 * np.pi * hours / 24 + np.pi / 3) + 1)  # Peak in evening
    seasonal_heating = 0.3 * np.maximum(0, -np.sin(2 * np.pi * hours / n_hours - np.pi / 2))  # Winter heating
    demand_profile = base_load + daily_demand + seasonal_heating + 0.05 * np.random.random(n_hours)

    # Heat demand profile (seasonal with daily variation)
    heat_seasonal = np.maximum(0, -np.sin(2 * np.pi * hours / n_hours - np.pi / 2))  # Winter peak
    heat_daily = 0.3 * (np.sin(2 * np.pi * hours / 24 + np.pi / 4) + 1)  # Morning/evening peaks
    heat_profile = heat_seasonal * (0.5 + heat_daily) + 0.05 * np.random.random(n_hours)

    # Temperature profile (for COP calculations)
    temp_seasonal = 15 + 10 * np.sin(2 * np.pi * hours / n_hours - np.pi / 2)  # 5-25°C range
    temp_daily = 3 * np.sin(2 * np.pi * hours / 24 - np.pi / 2)  # ±3°C daily variation
    temperature = temp_seasonal + temp_daily + np.random.normal(0, 1, n_hours)

    profiles = {
        "solar_pv": solar_profile,
        "power_demand": demand_profile,
        "heat_demand": heat_profile,
        "temperature": temperature,
    }

    # Log profile statistics
    for name, profile in profiles.items():
        logger.info(f"{name}: min={profile.min():.2f}, max={profile.max():.2f}, mean={profile.mean():.2f}")

    return profiles


def create_yearly_system_config() -> dict[str, Any]:
    """Create system configuration for yearly simulation based on legacy."""
    config = {
        "system_id": "yearly_legacy_microgrid",
        "description": "8760-hour yearly microgrid simulation based on legacy Systemiser",
        "timesteps": 8760,
        "timestep_hours": 1.0,
        "components": {
            # Grid configuration based on legacy,
            "Grid": {
                "type": "Grid",
                "params": {
                    "technical": {
                        "capacity_nominal": 800.0,  # kW - from legacy,
                        "import_tariff": 0.25,  # $/kWh,
                        "feed_in_tariff": 0.08,  # $/kWh - lower export price,
                        "fidelity_level": "SIMPLE",
                    }
                },
            },
            # Battery configuration based on legacy (300 kWh, 150 kW)
            "Battery": {
                "type": "Battery",
                "params": {
                    "technical": {
                        "capacity_nominal": 300.0,  # kWh - from legacy,
                        "max_charge_rate": 150.0,  # kW - from legacy,
                        "max_discharge_rate": 150.0,  # kW - from legacy,
                        "efficiency_roundtrip": 0.95,
                        "initial_soc_pct": 0.5,
                        "fidelity_level": "SIMPLE",
                    }
                },
            },
            # Solar PV configuration based on legacy (40 kW)
            "SolarPV": {
                "type": "SolarPV",
                "params": {
                    "technical": {
                        "capacity_nominal": 40.0,  # kW - from legacy,
                        "efficiency_nominal": 1.0,
                        "fidelity_level": "SIMPLE",
                    }
                },
                "profile_file": "solar_pv_yearly.csv",
            },
            # Power demand based on legacy (15 kW peak)
            "PowerDemand": {
                "type": "PowerDemand",
                "params": {
                    "technical": {
                        "capacity_nominal": 15.0,  # kW - from legacy,
                        "peak_demand": 15.0,
                        "load_profile_type": "variable",
                        "fidelity_level": "SIMPLE",
                    }
                },
                "profile_file": "power_demand_yearly.csv",
            },
            # Heat pump for thermal system (legacy COP=4.0, 300 kW)
            "HeatPump": {
                "type": "HeatPump",
                "params": {
                    "technical": {
                        "capacity_nominal": 300.0,  # kW thermal - from legacy,
                        "cop_nominal": 4.0,  # from legacy,
                        "efficiency_nominal": 0.95,  # from legacy,
                        "fidelity_level": "SIMPLE",
                    }
                },
            },
            # Heat demand (15 kW peak)
            "HeatDemand": {
                "type": "HeatDemand",
                "params": {
                    "technical": {
                        "capacity_nominal": 15.0,  # kW - from legacy,
                        "peak_demand": 15.0,
                        "demand_type": "space_heating",
                        "fidelity_level": "SIMPLE",
                    }
                },
                "profile_file": "heat_demand_yearly.csv",
            },
            # Heat buffer/tank (200 kWh, 50 kW)
            "HeatBuffer": {
                "type": "HeatBuffer",
                "params": {
                    "technical": {
                        "capacity_nominal": 200.0,  # kWh - from legacy,
                        "max_charge_rate": 50.0,  # kW - from legacy,
                        "max_discharge_rate": 50.0,  # kW - from legacy,
                        "efficiency_roundtrip": 0.97,  # from legacy,
                        "initial_soc_pct": 0.5,
                        "fidelity_level": "SIMPLE",
                    }
                },
            },
        },
        "connections": [
            # Electrical connections,
            ["Grid", "PowerDemand", "electricity"],
            ["Grid", "Battery", "electricity"],
            ["Battery", "Grid", "electricity"],
            ["SolarPV", "PowerDemand", "electricity"],
            ["SolarPV", "Battery", "electricity"],
            ["SolarPV", "Grid", "electricity"],
            ["Battery", "PowerDemand", "electricity"],
            ["Grid", "HeatPump", "electricity"],  # Heat pump electrical input,
            # Thermal connections,
            ["HeatPump", "HeatDemand", "heat"],
            ["HeatPump", "HeatBuffer", "heat"],
            ["HeatBuffer", "HeatDemand", "heat"],
        ],
    }

    return config


def save_profiles_and_config() -> None:
    """Extract and save yearly profiles and configuration."""
    logger.info("Starting yearly profile extraction from legacy Systemiser")

    # Create output directories
    output_dir = Path(__file__).parent.parent / "data" / "yearly_scenarios"
    profiles_dir = output_dir / "profiles"
    configs_dir = output_dir / "configs"

    for directory in [output_dir, profiles_dir, configs_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Try to load existing legacy output data
    legacy_output_path = Path("/c/git/SmartHoodsOptimisationTool/Systemiser/output")
    legacy_data = load_legacy_output_data(legacy_output_path)

    if legacy_data:
        logger.info("Found legacy output data, extracting profiles...")
        profiles = extract_profiles_from_output(legacy_data)
        n_hours = len(profiles[list(profiles.keys())[0]])
        logger.info(f"Extracted profiles with {n_hours} timesteps")
    else:
        logger.info("No legacy output found, creating synthetic weather-based profiles...")
        profiles = create_weather_based_profiles(8760)
        n_hours = 8760

    # Save profiles as CSV files
    for name, profile in profiles.items():
        if name not in ["grid_import", "grid_export", "battery_charge", "battery_discharge"]:
            csv_path = profiles_dir / f"{name}_yearly.csv"
            df = pd.DataFrame({"hour": range(len(profile)), "value": profile})
            df.to_csv(csv_path, index=False)
            logger.info(f"Saved {name} profile: {csv_path}")

    # Create and save system configuration
    config = create_yearly_system_config()
    config["timesteps"] = n_hours  # Update with actual timesteps

    configs_dir / "yearly_legacy_microgrid.yml"

    # Convert to YAML format (save as JSON for now)
    json_config_path = configs_dir / "yearly_legacy_microgrid.json"
    with open(json_config_path, "w") as f:
        json.dump(config, f, indent=2)

    logger.info(f"Saved system configuration: {json_config_path}")

    # Create summary report
    summary = {
        "extraction_date": pd.Timestamp.now().isoformat(),
        "source": "legacy SmartHoodsOptimisationTool Systemiser" if legacy_data else "synthetic weather-based",
        "timesteps": n_hours,
        "duration_days": n_hours / 24,
        "profiles_extracted": list(profiles.keys()),
        "profiles_saved": [
            name
            for name in profiles.keys()
            if name not in ["grid_import", "grid_export", "battery_charge", "battery_discharge"]
        ],
        "config_file": str(json_config_path),
        "profiles_directory": str(profiles_dir),
    }

    summary_path = output_dir / "extraction_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Extraction complete! Summary saved: {summary_path}")
    return summary


def main() -> None:
    """Main execution."""
    try:
        save_profiles_and_config()
        logger.info("\n=== Yearly Profile Extraction Complete ===")
        logger.info("Source: {summary['source']}")
        logger.info("Timesteps: {summary['timesteps']} ({summary['duration_days']:.1f} days)")
        logger.info("Profiles extracted: {len(summary['profiles_extracted'])}")
        logger.info("Profiles saved: {len(summary['profiles_saved'])}")
        logger.info("Configuration: {summary['config_file']}")
        logger.info("Profiles directory: {summary['profiles_directory']}")
        return True
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
