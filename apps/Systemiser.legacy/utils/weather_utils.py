from hive_logging import get_logger

logger = get_logger(__name__)
"""
Weather Utilities for Systemiser

Utility functions for integrating weather data with energy system components.
Provides functions to convert weather data into component profiles and parameters.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
import logging

# Use Systemiser logger
try:
    from Systemiser.utils.logger import setup_logging
    logger = setup_logging("WeatherUtils", level=logging.INFO)
except ImportError:
    logger = logging.getLogger("WeatherUtils_Fallback")
    logger.warning("Could not import Systemiser logger, using fallback.")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


def solar_radiation_to_pv_profile(solar_radiation_wm2: pd.Series,
                                 pv_capacity_kw: float,
                                 efficiency: float = 0.20,
                                 system_losses: float = 0.15) -> pd.Series:
    """
    Convert solar radiation data to PV generation profile.
    
    Args:
        solar_radiation_wm2: Solar radiation time series (W/m²)
        pv_capacity_kw: PV system capacity (kW)
        efficiency: PV panel efficiency (default: 0.20 = 20%)
        system_losses: System losses factor (default: 0.15 = 15% losses)
        
    Returns:
        PV generation time series (kW)
    """
    logger.info(f"Converting solar radiation to PV profile for {pv_capacity_kw} kW system")
    
    # Standard test conditions: 1000 W/m² at 25°C
    stc_irradiance = 1000  # W/m²
    
    # Convert solar radiation to PV output
    # PV output = (irradiance / STC irradiance) * capacity * efficiency * (1 - losses)
    pv_output = (solar_radiation_wm2 / stc_irradiance) * pv_capacity_kw * efficiency * (1 - system_losses)
    
    # Ensure non-negative values
    pv_output = pv_output.clip(lower=0)
    
    logger.info(f"Generated PV profile with max output: {pv_output.max():.2f} kW, "
               f"average: {pv_output.mean():.2f} kW")
    
    return pv_output


def temperature_to_heat_demand_profile(temperature_celsius: pd.Series,
                                     base_demand_kw: float,
                                     heating_threshold_c: float = 15.0,
                                     design_temp_c: float = -10.0,
                                     design_demand_multiplier: float = 3.0) -> pd.Series:
    """
    Convert temperature data to space heating demand profile.
    
    Args:
        temperature_celsius: Temperature time series (°C)
        base_demand_kw: Base heat demand at threshold temperature (kW)
        heating_threshold_c: Temperature below which heating is needed (°C)
        design_temp_c: Design temperature for maximum demand (°C)
        design_demand_multiplier: Multiplier for demand at design temperature
        
    Returns:
        Heat demand time series (kW)
    """
    logger.info(f"Converting temperature to heat demand profile with base demand {base_demand_kw} kW")
    
    # Calculate heating degree hours
    heating_degree_hours = np.maximum(0, heating_threshold_c - temperature_celsius)
    
    # Scale to design conditions
    max_heating_degree = heating_threshold_c - design_temp_c
    
    # Calculate demand
    demand_factor = heating_degree_hours / max_heating_degree
    heat_demand = base_demand_kw + (base_demand_kw * design_demand_multiplier * demand_factor)
    
    # Ensure non-negative values
    heat_demand = heat_demand.clip(lower=0)
    
    logger.info(f"Generated heat demand profile with max demand: {heat_demand.max():.2f} kW, "
               f"average: {heat_demand.mean():.2f} kW")
    
    return heat_demand


def wind_speed_to_wind_profile(wind_speed_ms: pd.Series,
                              turbine_capacity_kw: float,
                              cut_in_speed: float = 3.0,
                              rated_speed: float = 12.0,
                              cut_out_speed: float = 25.0) -> pd.Series:
    """
    Convert wind speed data to wind turbine generation profile.
    
    Args:
        wind_speed_ms: Wind speed time series (m/s)
        turbine_capacity_kw: Wind turbine capacity (kW)
        cut_in_speed: Cut-in wind speed (m/s)
        rated_speed: Rated wind speed for full output (m/s)
        cut_out_speed: Cut-out wind speed (m/s)
        
    Returns:
        Wind generation time series (kW)
    """
    logger.info(f"Converting wind speed to wind turbine profile for {turbine_capacity_kw} kW turbine")
    
    # Initialize output array
    wind_output = pd.Series(0.0, index=wind_speed_ms.index)
    
    # Below cut-in: no output
    # Between cut-in and rated: cubic relationship (simplified)
    ramp_mask = (wind_speed_ms >= cut_in_speed) & (wind_speed_ms < rated_speed)
    wind_output[ramp_mask] = turbine_capacity_kw * ((wind_speed_ms[ramp_mask] - cut_in_speed) / (rated_speed - cut_in_speed)) ** 3
    
    # At rated speed and above (until cut-out): full output
    rated_mask = (wind_speed_ms >= rated_speed) & (wind_speed_ms < cut_out_speed)
    wind_output[rated_mask] = turbine_capacity_kw
    
    # Above cut-out: no output (safety shutdown)
    
    logger.info(f"Generated wind profile with max output: {wind_output.max():.2f} kW, "
               f"average: {wind_output.mean():.2f} kW")
    
    return wind_output


def precipitation_to_rainwater_profile(precipitation_mm_hr: pd.Series,
                                     collection_area_m2: float,
                                     collection_efficiency: float = 0.8) -> pd.Series:
    """
    Convert precipitation data to rainwater collection profile.
    
    Args:
        precipitation_mm_hr: Precipitation time series (mm/hr)
        collection_area_m2: Roof/collection area (m²)
        collection_efficiency: Collection efficiency (default: 0.8 = 80%)
        
    Returns:
        Rainwater collection time series (L/hr)
    """
    logger.info(f"Converting precipitation to rainwater collection for {collection_area_m2} m² area")
    
    # Convert mm/hr to L/hr: 1 mm over 1 m² = 1 L
    rainwater_collection = precipitation_mm_hr * collection_area_m2 * collection_efficiency
    
    # Ensure non-negative values
    rainwater_collection = rainwater_collection.clip(lower=0)
    
    total_annual_collection = rainwater_collection.sum()
    logger.info(f"Generated rainwater profile with max collection: {rainwater_collection.max():.2f} L/hr, "
               f"total annual: {total_annual_collection:.0f} L")
    
    return rainwater_collection


def create_component_profiles_from_weather(weather_df: pd.DataFrame,
                                         component_configs: Dict[str, Dict[str, Any]]) -> Dict[str, pd.Series]:
    """
    Create component profiles from weather data based on configurations.
    
    Args:
        weather_df: Weather DataFrame with standardized columns
        component_configs: Dictionary mapping component names to their configurations
            Example: {
                'pv_system': {
                    'type': 'solar_pv',
                    'capacity_kw': 100,
                    'efficiency': 0.20
                },
                'heat_demand': {
                    'type': 'heat_demand',
                    'base_demand_kw': 50,
                    'heating_threshold_c': 16.0
                }
            }
            
    Returns:
        Dictionary mapping component names to their time series profiles
    """
    logger.info(f"Creating component profiles from weather data for {len(component_configs)} components")
    
    profiles = {}
    
    for comp_name, config in component_configs.items():
        comp_type = config.get('type')
        
        try:
            if comp_type == 'solar_pv':
                if 'solar_radiation_wm2' in weather_df.columns:
                    profiles[comp_name] = solar_radiation_to_pv_profile(
                        weather_df['solar_radiation_wm2'],
                        config['capacity_kw'],
                        config.get('efficiency', 0.20),
                        config.get('system_losses', 0.15)
                    )
                else:
                    logger.warning(f"Solar radiation data not available for {comp_name}")
                    
            elif comp_type == 'heat_demand':
                if 'temperature_celsius' in weather_df.columns:
                    profiles[comp_name] = temperature_to_heat_demand_profile(
                        weather_df['temperature_celsius'],
                        config['base_demand_kw'],
                        config.get('heating_threshold_c', 15.0),
                        config.get('design_temp_c', -10.0),
                        config.get('design_demand_multiplier', 3.0)
                    )
                else:
                    logger.warning(f"Temperature data not available for {comp_name}")
                    
            elif comp_type == 'wind_turbine':
                if 'wind_speed_m_s' in weather_df.columns:
                    profiles[comp_name] = wind_speed_to_wind_profile(
                        weather_df['wind_speed_m_s'],
                        config['capacity_kw'],
                        config.get('cut_in_speed', 3.0),
                        config.get('rated_speed', 12.0),
                        config.get('cut_out_speed', 25.0)
                    )
                else:
                    logger.warning(f"Wind speed data not available for {comp_name}")
                    
            elif comp_type == 'rainwater_collection':
                if 'precipitation_mm_hr' in weather_df.columns:
                    profiles[comp_name] = precipitation_to_rainwater_profile(
                        weather_df['precipitation_mm_hr'],
                        config['collection_area_m2'],
                        config.get('collection_efficiency', 0.8)
                    )
                else:
                    logger.warning(f"Precipitation data not available for {comp_name}")
                    
            else:
                logger.warning(f"Unknown component type '{comp_type}' for {comp_name}")
                
        except Exception as e:
            logger.error(f"Failed to create profile for {comp_name}: {e}")
    
    logger.info(f"Successfully created {len(profiles)} component profiles")
    return profiles


def calculate_weather_statistics(weather_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate useful weather statistics for energy system design.
    
    Args:
        weather_df: Weather DataFrame with standardized columns
        
    Returns:
        Dictionary with weather statistics
    """
    stats = {}
    
    if weather_df.empty:
        return {'status': 'empty'}
    
    # Temperature statistics
    if 'temperature_celsius' in weather_df.columns:
        temp = weather_df['temperature_celsius']
        stats['temperature'] = {
            'mean_annual_c': temp.mean(),
            'min_c': temp.min(),
            'max_c': temp.max(),
            'std_c': temp.std(),
            'heating_degree_hours': np.maximum(0, 15 - temp).sum(),
            'cooling_degree_hours': np.maximum(0, temp - 25).sum()
        }
    
    # Solar radiation statistics
    if 'solar_radiation_wm2' in weather_df.columns:
        solar = weather_df['solar_radiation_wm2']
        stats['solar'] = {
            'mean_annual_wm2': solar.mean(),
            'max_wm2': solar.max(),
            'annual_kwh_m2': solar.sum() / 1000,  # Convert Wh/m² to kWh/m²
            'capacity_factor_estimate': solar.mean() / 1000  # Rough estimate
        }
    
    # Wind statistics
    if 'wind_speed_m_s' in weather_df.columns:
        wind = weather_df['wind_speed_m_s']
        stats['wind'] = {
            'mean_speed_ms': wind.mean(),
            'max_speed_ms': wind.max(),
            'std_speed_ms': wind.std(),
            'hours_above_3ms': (wind >= 3).sum(),  # Typical cut-in speed
            'hours_above_12ms': (wind >= 12).sum()  # Typical rated speed
        }
    
    # Precipitation statistics
    if 'precipitation_mm_hr' in weather_df.columns:
        precip = weather_df['precipitation_mm_hr']
        # Convert to daily totals for annual calculation
        daily_precip = precip.resample('D').sum()
        stats['precipitation'] = {
            'annual_mm': daily_precip.sum(),
            'max_hourly_mm': precip.max(),
            'wet_hours': (precip > 0.1).sum(),  # Hours with meaningful precipitation
            'heavy_rain_hours': (precip > 5).sum()  # Hours with heavy rain
        }
    
    # Add data quality info
    stats['data_quality'] = {
        'total_hours': len(weather_df),
        'date_range': {
            'start': weather_df.index.min(),
            'end': weather_df.index.max()
        },
        'missing_data': {col: weather_df[col].isna().sum() for col in weather_df.columns}
    }
    
    return stats


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Create sample weather data
    dates = pd.date_range('2022-01-01', '2022-12-31', freq='H')
    sample_weather = pd.DataFrame({
        'temperature_celsius': 10 + 10 * np.sin(2 * np.pi * np.arange(len(dates)) / (365.25 * 24)),
        'solar_radiation_wm2': np.maximum(0, 500 * np.sin(2 * np.pi * np.arange(len(dates)) / 24)),
        'wind_speed_m_s': 5 + 3 * np.random.random(len(dates)),
        'precipitation_mm_hr': np.random.exponential(0.1, len(dates))
    }, index=dates)
    
    # Test component profile creation
    component_configs = {
        'pv_system': {
            'type': 'solar_pv',
            'capacity_kw': 100,
            'efficiency': 0.20
        },
        'heat_demand': {
            'type': 'heat_demand',
            'base_demand_kw': 50
        },
        'wind_turbine': {
            'type': 'wind_turbine',
            'capacity_kw': 25
        },
        'rainwater': {
            'type': 'rainwater_collection',
            'collection_area_m2': 200
        }
    }
    
    profiles = create_component_profiles_from_weather(sample_weather, component_configs)
    
    logger.info(f"Created profiles for: {list(profiles.keys())}")
    for name, profile in profiles.items():
        logger.info(f"{name}: mean={profile.mean():.2f}, max={profile.max():.2f}")
    
    # Test weather statistics
    stats = calculate_weather_statistics(sample_weather)
    logger.info(f"\nWeather statistics: {stats}") 