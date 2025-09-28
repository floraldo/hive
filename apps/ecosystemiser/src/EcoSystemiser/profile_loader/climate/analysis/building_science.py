"""
Building science analytics and derived variables for HVAC and energy system design.

This module combines building load analysis, design conditions calculation, and 
building-specific derived variables for comprehensive building energy analysis.
"""

import xarray as xr
import numpy as np
import pandas as pd
from hive_logging import get_logger
from typing import Dict, Optional, Tuple, List

logger = get_logger(__name__)

def analyze_building_loads(ds: xr.Dataset) -> Dict:
    """
    Analyze climate data for building load patterns.
    
    Args:
        ds: Climate dataset
        
    Returns:
        Dictionary with building load analysis
    """
    analysis = {
        'heating': {},
        'cooling': {},
        'solar': {},
        'ventilation': {}
    }
    
    # Heating analysis
    if 'temp_air' in ds:
        temp = ds['temp_air']
        
        # Heating indicators
        analysis['heating']['hours_below_18C'] = int((temp < 18).sum())
        analysis['heating']['hours_below_15C'] = int((temp < 15).sum())
        analysis['heating']['hours_below_10C'] = int((temp < 10).sum())
        analysis['heating']['min_temperature'] = float(temp.min())
        
        # Calculate HDD if not already present
        if 'time' in temp.dims:
            daily_temp = temp.resample(time='1D').mean()
            hdd = (18 - daily_temp).clip(min=0)
            analysis['heating']['annual_hdd_base18'] = float(hdd.sum())
    
    # Cooling analysis
    if 'temp_air' in ds and 'rel_humidity' in ds:
        temp = ds['temp_air']
        rh = ds['rel_humidity']
        
        # Cooling indicators
        analysis['cooling']['hours_above_24C'] = int((temp > 24).sum())
        analysis['cooling']['hours_above_26C'] = int((temp > 26).sum())
        analysis['cooling']['hours_above_30C'] = int((temp > 30).sum())
        analysis['cooling']['max_temperature'] = float(temp.max())
        
        # High humidity hours (for dehumidification load)
        analysis['cooling']['hours_rh_above_60'] = int((rh > 60).sum())
        analysis['cooling']['hours_rh_above_70'] = int((rh > 70).sum())
        
        # Calculate CDD if not already present
        if 'time' in temp.dims:
            daily_temp = temp.resample(time='1D').mean()
            cdd = (daily_temp - 24).clip(min=0)
            analysis['cooling']['annual_cdd_base24'] = float(cdd.sum())
    
    # Solar analysis
    if 'ghi' in ds:
        ghi = ds['ghi']
        
        analysis['solar']['peak_ghi'] = float(ghi.max())
        analysis['solar']['mean_ghi'] = float(ghi.mean())
        
        # Peak sun hours (equivalent hours at 1000 W/m2)
        if 'time' in ghi.dims:
            daily_energy = ghi.resample(time='1D').sum() / 1000  # kWh/m2/day
            analysis['solar']['mean_peak_sun_hours'] = float(daily_energy.mean())
            analysis['solar']['annual_insolation'] = float(daily_energy.sum())
    
    # Ventilation analysis
    if 'wind_speed' in ds:
        wind = ds['wind_speed']
        
        analysis['ventilation']['mean_wind_speed'] = float(wind.mean())
        analysis['ventilation']['max_wind_speed'] = float(wind.max())
        
        # Natural ventilation potential (moderate wind speeds)
        analysis['ventilation']['hours_2_to_6_ms'] = int(((wind >= 2) & (wind <= 6)).sum())
    
    # Add coincidence analysis if we have temp and solar
    if 'temp_air' in ds and 'ghi' in ds:
        # Peak cooling typically coincides with high solar
        hot_hours = ds['temp_air'] > ds['temp_air'].quantile(0.95)
        high_solar = ds['ghi'] > ds['ghi'].quantile(0.75)
        
        analysis['coincidence'] = {
            'hot_sunny_hours': int((hot_hours & high_solar).sum()),
            'hot_cloudy_hours': int((hot_hours & ~high_solar).sum())
        }
    
    return analysis

def get_design_conditions(ds: xr.Dataset, 
                         percentiles: List[float] = [0.4, 1, 2, 99, 99.6]) -> Dict:
    """
    Calculate ASHRAE-style design conditions for HVAC sizing.
    
    Args:
        ds: Climate dataset
        percentiles: Design percentiles (e.g., 0.4% for extreme, 99.6% for common)
        
    Returns:
        Dictionary with design conditions
    """
    design = {
        'heating': {},
        'cooling': {},
        'humidity': {}
    }
    
    # Temperature design conditions
    if 'temp_air' in ds:
        temp = ds['temp_air'].values
        temp_sorted = np.sort(temp[~np.isnan(temp)])
        n = len(temp_sorted)
        
        for p in percentiles:
            idx = int(n * p / 100)
            if p < 50:  # Heating design (cold percentiles)
                design['heating'][f'temp_{p}pct'] = float(temp_sorted[idx])
            else:  # Cooling design (hot percentiles)
                design['cooling'][f'temp_{p}pct'] = float(temp_sorted[idx])
    
    # Coincident wet bulb for cooling design
    if 'temp_air' in ds and 'temp_wetbulb' in ds:
        # Find wet bulb at design dry bulb conditions
        for p in [99, 99.6]:
            if f'temp_{p}pct' in design['cooling']:
                design_temp = design['cooling'][f'temp_{p}pct']
                # Get wet bulb when temp is near design condition
                mask = np.abs(ds['temp_air'].values - design_temp) < 0.5
                if mask.any():
                    coincident_wb = ds['temp_wetbulb'].values[mask].mean()
                    design['cooling'][f'wetbulb_at_{p}pct'] = float(coincident_wb)
    
    # Humidity extremes
    if 'dewpoint' in ds:
        dp = ds['dewpoint'].values
        dp_sorted = np.sort(dp[~np.isnan(dp)])
        n = len(dp_sorted)
        
        for p in percentiles:
            idx = int(n * p / 100)
            if p < 50:
                design['humidity'][f'dewpoint_{p}pct'] = float(dp_sorted[idx])
            else:
                design['humidity'][f'dewpoint_{p}pct'] = float(dp_sorted[idx])
    
    # Add mean coincident values
    if 'temp_air' in ds and 'rel_humidity' in ds:
        # Mean coincident humidity at peak temperatures
        hot_hours = ds['temp_air'] > ds['temp_air'].quantile(0.99)
        design['cooling']['mean_rh_at_peak'] = float(
            ds['rel_humidity'].where(hot_hours).mean()
        )
        
        cold_hours = ds['temp_air'] < ds['temp_air'].quantile(0.01)
        design['heating']['mean_rh_at_peak'] = float(
            ds['rel_humidity'].where(cold_hours).mean()
        )
    
    return design

def calculate_peak_periods(ds: xr.Dataset, 
                          window: str = '1D',
                          variables: Optional[List[str]] = None) -> Dict:
    """
    Identify peak periods for different variables.
    
    Args:
        ds: Climate dataset
        window: Time window for peaks (e.g., '1D' for daily, '1H' for hourly)
        variables: Variables to analyze (default: temp, solar, wind)
        
    Returns:
        Dictionary with peak timing information
    """
    if variables is None:
        variables = ['temp_air', 'ghi', 'wind_speed', 'cooling_load', 'heating_load']
    
    peaks = {}
    
    for var in variables:
        if var not in ds and var in ['cooling_load', 'heating_load']:
            # Estimate loads if not present
            if 'temp_air' in ds:
                if var == 'cooling_load':
                    load = (ds['temp_air'] - 24).clip(min=0)
                else:  # heating_load
                    load = (18 - ds['temp_air']).clip(min=0)
                ds[var] = load
        
        if var in ds and 'time' in ds[var].dims:
            data = ds[var]
            
            # Find overall peak
            peak_idx = data.argmax()
            peak_time = pd.Timestamp(data.time[peak_idx].values)
            
            peaks[var] = {
                'peak_value': float(data.max()),
                'peak_time': peak_time.isoformat(),
                'peak_hour': peak_time.hour,
                'peak_month': peak_time.month,
                'peak_day_of_year': peak_time.dayofyear
            }
            
            # Calculate typical peak timing (mode of peak hours)
            if window == '1D':
                daily_max = data.resample(time='1D').max()
                daily_max_time = data.resample(time='1D').apply(
                    lambda x: x.time[x.argmax()].values if len(x) > 0 else pd.NaT
                )
                
                # Most common hour for daily peaks
                peak_hours = pd.DatetimeIndex(daily_max_time.values).hour
                peak_hours = peak_hours[~pd.isna(peak_hours)]
                if len(peak_hours) > 0:
                    peaks[var]['typical_peak_hour'] = int(
                        pd.Series(peak_hours).mode().iloc[0]
                    )
            
            # Seasonal variation
            monthly_max = data.resample(time='1M').max()
            peaks[var]['peak_month_value'] = {
                int(m.month): float(v) 
                for m, v in zip(pd.DatetimeIndex(monthly_max.time.values), 
                               monthly_max.values)
            }
    
    return peaks

def analyze_diurnal_profiles(ds: xr.Dataset,
                            variables: Optional[List[str]] = None,
                            by_month: bool = True) -> Dict:
    """
    Calculate average diurnal (hourly) profiles.
    
    Args:
        ds: Climate dataset
        variables: Variables to analyze
        by_month: Whether to separate by month
        
    Returns:
        Dictionary with diurnal profiles
    """
    if variables is None:
        variables = ['temp_air', 'ghi', 'wind_speed', 'rel_humidity']
    
    profiles = {}
    
    for var in variables:
        if var not in ds or 'time' not in ds[var].dims:
            continue
        
        data = ds[var]
        
        if by_month:
            # Monthly diurnal profiles
            monthly_hourly = data.groupby(
                [data.time.dt.month, data.time.dt.hour]
            ).mean()
            
            profiles[var] = {
                'monthly_hourly': {
                    f'month_{m:02d}': {
                        f'hour_{h:02d}': float(monthly_hourly.sel(month=m, hour=h))
                        for h in range(24)
                        if (m, h) in monthly_hourly.coords
                    }
                    for m in range(1, 13)
                }
            }
        else:
            # Overall hourly profile
            hourly_mean = data.groupby(data.time.dt.hour).mean()
            profiles[var] = {
                'hourly_mean': {
                    f'hour_{h:02d}': float(hourly_mean.sel(hour=h))
                    for h in range(24)
                    if h in hourly_mean.coords
                }
            }
        
        # Add daily statistics
        if 'time' in data.dims:
            daily_range = (data.resample(time='1D').max() - 
                          data.resample(time='1D').min())
            profiles[var]['mean_daily_range'] = float(daily_range.mean())
            profiles[var]['max_daily_range'] = float(daily_range.max())
    
    return profiles

def calculate_simultaneity(ds: xr.Dataset) -> Dict:
    """
    Calculate simultaneity factors between different loads.
    
    Useful for understanding coincidence of peak loads.
    
    Args:
        ds: Climate dataset
        
    Returns:
        Dictionary with simultaneity factors
    """
    simultaneity = {}
    
    # Temperature and solar coincidence
    if 'temp_air' in ds and 'ghi' in ds:
        # Correlation during daytime hours
        if 'time' in ds.dims:
            daytime = pd.DatetimeIndex(ds.time.values).hour.isin(range(6, 19))
            corr = np.corrcoef(
                ds['temp_air'].values[daytime],
                ds['ghi'].values[daytime]
            )[0, 1]
            simultaneity['temp_solar_correlation'] = float(corr)
        
        # Peak coincidence
        temp_peak_time = ds.time[ds['temp_air'].argmax()]
        solar_peak_time = ds.time[ds['ghi'].argmax()]
        
        time_diff = abs(
            pd.Timestamp(temp_peak_time.values) - 
            pd.Timestamp(solar_peak_time.values)
        ).total_seconds() / 3600
        
        simultaneity['temp_solar_peak_lag_hours'] = float(time_diff)
    
    # Heating and wind (infiltration) coincidence
    if 'temp_air' in ds and 'wind_speed' in ds:
        cold_hours = ds['temp_air'] < 10
        simultaneity['mean_wind_during_heating'] = float(
            ds['wind_speed'].where(cold_hours).mean()
        )
        simultaneity['max_wind_during_heating'] = float(
            ds['wind_speed'].where(cold_hours).max()
        )
    
    return simultaneity

def derive_building_variables(ds: xr.Dataset, config: Optional[Dict] = None) -> xr.Dataset:
    """
    Derive building-specific variables for HVAC and energy calculations.
    This is postprocessing - computes metrics for building energy analysis.
    
    Args:
        ds: Dataset with base climate variables
        config: Optional configuration dict with parameters like base temperatures
        
    Returns:
        Dataset with building variables added
    """
    ds_building = ds.copy()
    config = config or {}
    
    # Calculate wet bulb temperature if we have temp and humidity
    if config.get('calculate_wet_bulb', True):
        if 'temp_air' in ds_building and 'rel_humidity' in ds_building:
            pressure = ds_building.get('pressure', 101325)  # Use standard pressure if not available
            ds_building['temp_wetbulb'] = calculate_wetbulb(
                ds_building['temp_air'],
                ds_building['rel_humidity'],
                pressure
            )
            ds_building['temp_wetbulb'].attrs = {
                'units': 'degC',
                'type': 'state',
                'derived': True,
                'description': 'Wet bulb temperature for cooling tower design'
            }
            logger.info("Calculated wet bulb temperature")
    
    # Calculate apparent temperature (heat index) for comfort
    if config.get('calculate_heat_index', True):
        if 'temp_air' in ds_building and 'rel_humidity' in ds_building:
            ds_building['temp_apparent'] = calculate_heat_index(
                ds_building['temp_air'],
                ds_building['rel_humidity']
            )
            ds_building['temp_apparent'].attrs = {
                'units': 'degC',
                'type': 'state',
                'derived': True,
                'description': 'Apparent temperature (heat index) for thermal comfort'
            }
            logger.info("Calculated heat index")
    
    # Calculate degree days if requested
    if config.get('calculate_degree_days', False):
        if 'temp_air' in ds_building:
            base_heat = config.get('hdd_base_temp', 18.0)
            base_cool = config.get('cdd_base_temp', 24.0)
            
            dd_results = calculate_degree_days(
                ds_building['temp_air'],
                base_heat=base_heat,
                base_cool=base_cool
            )
            
            if 'hdd' in dd_results:
                ds_building['hdd'] = dd_results['hdd']
                logger.info(f"Calculated heating degree days (base {base_heat}degC)")
            
            if 'cdd' in dd_results:
                ds_building['cdd'] = dd_results['cdd']
                logger.info(f"Calculated cooling degree days (base {base_cool}degC)")
    
    # Calculate wind power density if wind speed available
    if config.get('calculate_wind_power', False):
        if 'wind_speed' in ds_building:
            ds_building['wind_power_density'] = calculate_wind_power_density(
                ds_building['wind_speed'],
                ds_building.get('temp_air', None),
                ds_building.get('pressure', None)
            )
            logger.info("Calculated wind power density")
    
    return ds_building

def calculate_wetbulb(temp_air: xr.DataArray, 
                     rel_humidity: xr.DataArray,
                     pressure: xr.DataArray | float) -> xr.DataArray:
    """
    Calculate wet bulb temperature using simplified psychrometric formula.
    
    Args:
        temp_air: Air temperature in degC
        rel_humidity: Relative humidity in %
        pressure: Atmospheric pressure in Pa
        
    Returns:
        Wet bulb temperature in degC
    """
    # Convert to proper units
    T = temp_air  # degC
    RH = rel_humidity / 100.0  # fraction
    
    # Simplified wet bulb calculation (Stull 2011)
    # Good for T: -20 to 50degC, RH: 5-99%
    tw = T * np.arctan(0.151977 * np.sqrt(RH + 8.313659)) + \
         np.arctan(T + RH) - \
         np.arctan(RH - 1.676331) + \
         0.00391838 * RH**(3/2) * np.arctan(0.023101 * RH) - \
         4.686035
    
    return tw

def calculate_heat_index(temp_air: xr.DataArray, 
                         rel_humidity: xr.DataArray) -> xr.DataArray:
    """
    Calculate heat index (apparent temperature) for thermal comfort.
    
    Uses simplified heat index equation valid for temps > 20degC.
    For cooler temps, returns the actual temperature.
    
    Args:
        temp_air: Air temperature in degC
        rel_humidity: Relative humidity in %
        
    Returns:
        Apparent temperature in degC
    """
    # Convert to Fahrenheit for calculation (NOAA formula)
    T_F = temp_air * 9/5 + 32
    RH = rel_humidity
    
    # Simple formula for moderate conditions
    HI_simple = 0.5 * (T_F + 61.0 + ((T_F - 68.0) * 1.2) + (RH * 0.094))
    
    # Full formula for T > 80degF (26.7degC)
    HI_full = (-42.379 + 
               2.04901523 * T_F + 
               10.14333127 * RH - 
               0.22475541 * T_F * RH - 
               6.83783e-3 * T_F**2 - 
               5.481717e-2 * RH**2 + 
               1.22874e-3 * T_F**2 * RH + 
               8.5282e-4 * T_F * RH**2 - 
               1.99e-6 * T_F**2 * RH**2)
    
    # Use full formula when average > 80degF
    HI_F = xr.where((HI_simple + T_F) / 2 > 80, HI_full, HI_simple)
    
    # For cool temperatures, use actual temperature
    HI_F = xr.where(T_F < 68, T_F, HI_F)
    
    # Convert back to Celsius
    HI_C = (HI_F - 32) * 5/9
    
    return HI_C

def calculate_degree_days(temp_air: xr.DataArray,
                          base_heat: float = 18.0,
                          base_cool: float = 24.0) -> Dict[str, xr.DataArray]:
    """
    Calculate heating and cooling degree days.
    
    Args:
        temp_air: Air temperature in degC
        base_heat: Base temperature for heating (default 18degC)
        base_cool: Base temperature for cooling (default 24degC)
        
    Returns:
        Dictionary with 'hdd' and 'cdd' DataArrays
    """
    # Ensure we have daily data
    if 'time' in temp_air.dims:
        # Calculate daily average if hourly
        freq = None
        if hasattr(temp_air.time, 'dt'):
            time_diff = temp_air.time.diff('time')
            median_diff = np.median(time_diff.values)
            # Check if hourly (around 1 hour in nanoseconds)
            if median_diff < np.timedelta64(2, 'h'):
                freq = '1D'
        
        if freq:
            daily_temp = temp_air.resample(time=freq).mean()
        else:
            daily_temp = temp_air
        
        # Calculate degree days
        hdd = (base_heat - daily_temp).clip(min=0)
        cdd = (daily_temp - base_cool).clip(min=0)
        
        # Set attributes
        hdd.attrs = {
            'units': 'degC·day',
            'long_name': f'Heating degree days (base {base_heat}degC)',
            'type': 'state',
            'derived': True,
            'description': f'Daily heating degree days with base temperature {base_heat}degC'
        }
        cdd.attrs = {
            'units': 'degC·day',
            'long_name': f'Cooling degree days (base {base_cool}degC)',
            'type': 'state',
            'derived': True,
            'description': f'Daily cooling degree days with base temperature {base_cool}degC'
        }
        
        return {'hdd': hdd, 'cdd': cdd}
    else:
        logger.warning("Cannot calculate degree days without time dimension")
        return {}

def calculate_wind_power_density(wind_speed: xr.DataArray,
                                 temp_air: Optional[xr.DataArray] = None,
                                 pressure: Optional[xr.DataArray] = None) -> xr.DataArray:
    """
    Calculate wind power density for wind energy assessment.
    
    Args:
        wind_speed: Wind speed in m/s
        temp_air: Optional air temperature in degC for accurate air density
        pressure: Optional atmospheric pressure in Pa for accurate air density
        
    Returns:
        Wind power density in W/m2
    """
    # Calculate air density
    if temp_air is not None and pressure is not None:
        # Accurate air density using ideal gas law
        # ρ = P / (R * T) where R = 287.05 J/(kg·K) for dry air
        air_density = pressure / (287.05 * (temp_air + 273.15))
    else:
        # Standard air density at sea level, 15degC
        air_density = 1.225  # kg/m3
    
    # Wind power density = 0.5 * ρ * v3
    wpd = 0.5 * air_density * wind_speed**3
    
    wpd.attrs = {
        'units': 'W/m2',
        'type': 'flux',
        'derived': True,
        'description': 'Wind power density for wind energy assessment'
    }
    
    return wpd