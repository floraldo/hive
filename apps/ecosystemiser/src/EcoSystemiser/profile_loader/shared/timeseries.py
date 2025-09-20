"""Shared time series utilities for both climate and demand profiles"""

import pandas as pd
import numpy as np
from typing import Literal, Dict, Any, Union
import xarray as xr

def aggregate_policy(var_type: Literal["state", "flux"]) -> str:
    """
    Get aggregation policy for variable type.
    
    Args:
        var_type: Type of variable
        
    Returns:
        Aggregation method name
    """
    if var_type == "state":
        return "mean"
    elif var_type == "flux":
        return "sum"
    else:
        return "mean"

def resample_timeseries(
    data: Union[pd.DataFrame, xr.Dataset],
    target_freq: str,
    policy_map: Dict[str, str]
) -> Union[pd.DataFrame, xr.Dataset]:
    """
    Resample time series data with specified policies.
    
    Args:
        data: Time series data (DataFrame or Dataset)
        target_freq: Target frequency
        policy_map: Map of variable names to aggregation policies
        
    Returns:
        Resampled data
    """
    if isinstance(data, pd.DataFrame):
        resampled = {}
        
        for col in data.columns:
            policy = policy_map.get(col, 'mean')
            
            if policy == 'mean':
                resampled[col] = data[col].resample(target_freq).mean()
            elif policy == 'sum':
                resampled[col] = data[col].resample(target_freq).sum()
            elif policy == 'max':
                resampled[col] = data[col].resample(target_freq).max()
            elif policy == 'min':
                resampled[col] = data[col].resample(target_freq).min()
            else:
                resampled[col] = data[col].resample(target_freq).mean()
        
        return pd.DataFrame(resampled)
    
    elif isinstance(data, xr.Dataset):
        resampled_vars = {}
        
        for var in data.data_vars:
            policy = policy_map.get(var, 'mean')
            
            if policy == 'mean':
                resampled_vars[var] = data[var].resample(time=target_freq).mean()
            elif policy == 'sum':
                resampled_vars[var] = data[var].resample(time=target_freq).sum()
            elif policy == 'max':
                resampled_vars[var] = data[var].resample(time=target_freq).max()
            elif policy == 'min':
                resampled_vars[var] = data[var].resample(time=target_freq).min()
            else:
                resampled_vars[var] = data[var].resample(time=target_freq).mean()
        
        return xr.Dataset(resampled_vars)
    
    else:
        raise TypeError("Data must be pandas DataFrame or xarray Dataset")

def qc_bounds(
    data: Union[pd.Series, np.ndarray],
    bounds: tuple,
    clip: bool = True
) -> Union[pd.Series, np.ndarray]:
    """
    Apply quality control bounds to data.
    
    Args:
        data: Data to check
        bounds: (min, max) tuple
        clip: Whether to clip or just flag
        
    Returns:
        Processed data
    """
    min_val, max_val = bounds
    
    if clip:
        if isinstance(data, pd.Series):
            return data.clip(lower=min_val, upper=max_val)
        else:
            return np.clip(data, min_val, max_val)
    else:
        # Just flag out-of-bounds values
        mask = (data >= min_val) & (data <= max_val)
        return data, mask

def gap_fill(
    data: pd.Series,
    method: str = 'linear',
    limit: int = 6
) -> pd.Series:
    """
    Fill gaps in time series data.
    
    Args:
        data: Time series with gaps
        method: Filling method
        limit: Maximum gap size to fill
        
    Returns:
        Filled time series
    """
    if method == 'linear':
        return data.interpolate(method='linear', limit=limit)
    elif method == 'forward':
        return data.fillna(method='ffill', limit=limit)
    elif method == 'backward':
        return data.fillna(method='bfill', limit=limit)
    elif method == 'seasonal':
        # Simple seasonal filling
        month = data.index.month
        hour = data.index.hour if hasattr(data.index, 'hour') else 0
        
        filled = data.copy()
        for i, val in enumerate(data):
            if pd.isna(val):
                # Find similar times
                mask = (month == month[i])
                if hasattr(data.index, 'hour'):
                    mask = mask & (hour == hour[i])
                
                similar_values = data[mask].dropna()
                if len(similar_values) > 0:
                    filled.iloc[i] = similar_values.median()
        
        return filled
    else:
        return data


def zero_night_irradiance(ds: xr.Dataset, var_name: str) -> xr.Dataset:
    """
    Set solar irradiance to zero during night hours using proper solar position calculations.
    
    Uses solar elevation angle to determine if sun is above horizon.
    Much more accurate than fixed hour-based approach.
    
    Args:
        ds: Dataset containing solar radiation variable
        var_name: Name of solar radiation variable
        
    Returns:
        Dataset with night values zeroed
    """
    if var_name not in ds:
        return ds
    
    ds_copy = ds.copy()
    
    # Get latitude from dataset attributes 
    lat = ds.attrs.get('latitude', 50.0)  # Default to mid-latitude if not available
    
    # Calculate solar elevation angles for all timestamps
    times = pd.DatetimeIndex(ds.time.values)
    night_mask = calculate_night_mask(times, lat)
    
    # Set night values to zero
    ds_copy[var_name].values[night_mask] = 0
    
    return ds_copy


def calculate_night_mask(times: pd.DatetimeIndex, lat: float) -> np.ndarray:
    """
    Calculate night mask using solar position calculations.
    
    Args:
        times: Array of datetime values
        lat: Latitude in degrees
        
    Returns:
        Boolean mask where True indicates night time (sun below horizon)
    """
    # Convert to numpy array for vectorized operations
    times_array = times.values
    
    # Calculate solar elevation angle for each timestamp
    solar_elevations = calculate_solar_elevation(times_array, lat)
    
    # Sun is below horizon when elevation angle <= 0
    # Add small margin (0.5deg) to account for atmospheric refraction
    night_mask = solar_elevations <= 0.5
    
    return night_mask


def calculate_solar_elevation(times: Union[np.ndarray, pd.DatetimeIndex], lat: float) -> np.ndarray:
    """
    Calculate solar elevation angle using vectorized operations.
    
    Based on simplified solar position algorithm.
    Accurate to within ~1deg for most applications.
    
    Args:
        times: Array of datetime64 values or DatetimeIndex
        lat: Latitude in degrees
        
    Returns:
        Array of solar elevation angles in degrees
    """
    # Convert numpy datetime64 to pandas for easier manipulation
    if isinstance(times, np.ndarray):
        dt_index = pd.DatetimeIndex(times)
    else:
        dt_index = times
    
    # Day of year (1-365/366)
    day_of_year = dt_index.dayofyear
    
    # Hour of day in decimal (0-24)
    hour = dt_index.hour + dt_index.minute/60.0 + dt_index.second/3600.0
    
    # Solar declination angle (degrees)
    # Simplified formula accurate to ~0.5deg
    declination = 23.45 * np.sin(np.radians(360 * (284 + day_of_year) / 365))
    
    # Hour angle (degrees from solar noon)
    hour_angle = 15 * (hour - 12)
    
    # Convert to radians
    lat_rad = np.radians(lat)
    dec_rad = np.radians(declination)
    hour_rad = np.radians(hour_angle)
    
    # Solar elevation angle using spherical trigonometry
    elevation_rad = np.arcsin(
        np.sin(lat_rad) * np.sin(dec_rad) + 
        np.cos(lat_rad) * np.cos(dec_rad) * np.cos(hour_rad)
    )
    
    # Convert to degrees
    elevation_deg = np.degrees(elevation_rad)
    
    return elevation_deg