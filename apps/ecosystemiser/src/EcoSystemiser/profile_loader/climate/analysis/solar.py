"""Solar-specific derived variables for postprocessing - PV and solar energy metrics"""

import xarray as xr
import numpy as np
import pandas as pd
from hive_logging import get_logger
from typing import Optional, Tuple

logger = get_logger(__name__)

def calculate_clearness_index(ghi: xr.DataArray, 
                              latitude: float,
                              time: xr.DataArray,
                              longitude: Optional[float] = None) -> xr.DataArray:
    """
    Calculate clearness index (ratio of GHI to extraterrestrial radiation).
    Useful for PV system sizing and solar resource assessment.
    
    Args:
        ghi: Global horizontal irradiance in W/m2
        latitude: Location latitude in degrees
        time: Time coordinate
        longitude: Optional longitude for more accurate solar time
        
    Returns:
        Clearness index (0-1)
    """
    # Calculate extraterrestrial radiation
    # Solar constant
    Gsc = 1367  # W/m2
    
    # Day of year
    time_pd = pd.DatetimeIndex(time.values)
    doy = time_pd.dayofyear
    
    # Solar declination (radians)
    decl = np.radians(23.45) * np.sin(np.radians(360 * (284 + doy) / 365))
    
    # Hour angle (radians)
    hour = time_pd.hour + time_pd.minute / 60.0
    
    # Apply longitude correction if available
    if longitude is not None:
        # Solar time correction
        lstm = 15 * round(longitude / 15)  # Local standard time meridian
        eot = equation_of_time(doy)  # Equation of time in minutes
        time_correction = 4 * (longitude - lstm) + eot
        solar_hour = hour + time_correction / 60.0
    else:
        solar_hour = hour
    
    omega = np.radians(15 * (solar_hour - 12))
    
    # Latitude in radians
    lat_rad = np.radians(latitude)
    
    # Extraterrestrial radiation on horizontal surface
    with np.errstate(invalid='ignore'):
        cos_zenith = (np.sin(decl) * np.sin(lat_rad) + 
                     np.cos(decl) * np.cos(lat_rad) * np.cos(omega))
        
        # Earth-sun distance correction
        E0 = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
        
        # Extraterrestrial horizontal radiation
        Gext = Gsc * E0 * np.maximum(cos_zenith, 0)
    
    # Calculate clearness index
    with np.errstate(divide='ignore', invalid='ignore'):
        kt = ghi / (Gext + 1e-10)
        kt = kt.where(Gext > 10, 0)  # Only when sun is up
        kt = kt.clip(0, 1.2)  # Allow slight over-unity due to cloud enhancement
    
    kt.attrs = {
        'units': 'fraction',
        'type': 'state',
        'derived': True,
        'description': 'Clearness index for solar resource assessment',
        'long_name': 'Ratio of GHI to extraterrestrial radiation'
    }
    
    return kt

def calculate_solar_position(time: xr.DataArray, 
                            latitude: float, 
                            longitude: float) -> Tuple[xr.DataArray, xr.DataArray]:
    """
    Calculate solar elevation and azimuth angles.
    
    Args:
        time: Time coordinate
        latitude: Location latitude in degrees
        longitude: Location longitude in degrees
        
    Returns:
        Tuple of (elevation, azimuth) angles in degrees
    """
    time_pd = pd.DatetimeIndex(time.values)
    doy = time_pd.dayofyear
    
    # Solar declination
    decl = np.radians(23.45) * np.sin(np.radians(360 * (284 + doy) / 365))
    
    # Solar time
    hour = time_pd.hour + time_pd.minute / 60.0 + time_pd.second / 3600.0
    lstm = 15 * round(longitude / 15)
    eot = equation_of_time(doy)
    time_correction = 4 * (longitude - lstm) + eot
    solar_hour = hour + time_correction / 60.0
    
    # Hour angle
    omega = np.radians(15 * (solar_hour - 12))
    
    # Convert latitude to radians
    lat_rad = np.radians(latitude)
    
    # Solar elevation angle
    sin_elev = (np.sin(decl) * np.sin(lat_rad) + 
                np.cos(decl) * np.cos(lat_rad) * np.cos(omega))
    elevation = np.degrees(np.arcsin(sin_elev.clip(-1, 1)))
    
    # Solar azimuth angle (from North, clockwise)
    cos_az = (np.sin(decl) * np.cos(lat_rad) - 
              np.cos(decl) * np.sin(lat_rad) * np.cos(omega)) / np.cos(np.radians(elevation))
    sin_az = np.cos(decl) * np.sin(omega) / np.cos(np.radians(elevation))
    
    azimuth = np.degrees(np.arctan2(sin_az, cos_az))
    azimuth = (azimuth + 180) % 360  # Convert to 0-360 from North
    
    # Create DataArrays
    elevation_da = xr.DataArray(
        elevation,
        coords={'time': time},
        dims=['time'],
        attrs={
            'units': 'degrees',
            'description': 'Solar elevation angle above horizon',
            'long_name': 'Solar elevation'
        }
    )
    
    azimuth_da = xr.DataArray(
        azimuth,
        coords={'time': time},
        dims=['time'],
        attrs={
            'units': 'degrees',
            'description': 'Solar azimuth angle from North (clockwise)',
            'long_name': 'Solar azimuth'
        }
    )
    
    return elevation_da, azimuth_da

def calculate_solar_angles(ds: xr.Dataset) -> xr.Dataset:
    """
    Add solar position angles to dataset.
    
    Args:
        ds: Dataset with time coordinate and location attributes
        
    Returns:
        Dataset with solar_elevation and solar_azimuth added
    """
    if 'latitude' not in ds.attrs or 'longitude' not in ds.attrs:
        logger.warning("Cannot calculate solar angles without latitude/longitude")
        return ds
    
    ds_solar = ds.copy()
    
    elevation, azimuth = calculate_solar_position(
        ds.time,
        ds.attrs['latitude'],
        ds.attrs['longitude']
    )
    
    ds_solar['solar_elevation'] = elevation
    ds_solar['solar_azimuth'] = azimuth
    
    # Calculate air mass for solar calculations
    with np.errstate(divide='ignore', invalid='ignore'):
        # Kasten-Young formula for air mass
        zenith_rad = np.radians(90 - elevation)
        am = 1 / (np.cos(zenith_rad) + 0.50572 * (96.07995 - np.degrees(zenith_rad))**(-1.6364))
        am = am.where(elevation > 0, np.nan)  # Only valid when sun is up
        am = am.clip(0, 40)  # Practical limits
    
    ds_solar['air_mass'] = xr.DataArray(
        am,
        coords={'time': ds.time},
        dims=['time'],
        attrs={
            'units': 'dimensionless',
            'description': 'Relative optical air mass',
            'long_name': 'Air mass'
        }
    )
    
    logger.info("Added solar position angles and air mass")
    
    return ds_solar

def equation_of_time(day_of_year):
    """
    Calculate equation of time in minutes.
    
    Args:
        day_of_year: Day of year (1-365/366)
        
    Returns:
        Equation of time in minutes
    """
    B = 2 * np.pi * (day_of_year - 81) / 365
    E = 9.87 * np.sin(2 * B) - 7.53 * np.cos(B) - 1.5 * np.sin(B)
    return E

def calculate_dni_from_ghi_dhi(ghi: xr.DataArray, 
                               dhi: xr.DataArray,
                               solar_elevation: xr.DataArray) -> xr.DataArray:
    """
    Calculate DNI from GHI and DHI using solar geometry.
    More accurate than the simplified version in preprocessing.
    
    Args:
        ghi: Global horizontal irradiance in W/m2
        dhi: Diffuse horizontal irradiance in W/m2
        solar_elevation: Solar elevation angle in degrees
        
    Returns:
        Direct normal irradiance in W/m2
    """
    # Calculate DNI using solar geometry
    # GHI = DNI * sin(elevation) + DHI
    # Therefore: DNI = (GHI - DHI) / sin(elevation)
    
    with np.errstate(divide='ignore', invalid='ignore'):
        sin_elev = np.sin(np.radians(solar_elevation))
        dni = (ghi - dhi) / sin_elev
        
        # Physical constraints
        dni = dni.where(solar_elevation > 5, 0)  # Only valid when sun is above 5deg
        dni = dni.where(ghi > dhi, 0)  # GHI must be greater than DHI
        dni = dni.clip(0, 1500)  # Reasonable physical limits
    
    dni.attrs = {
        'units': 'W/m2',
        'type': 'flux',
        'derived': True,
        'description': 'Direct normal irradiance calculated from GHI and DHI',
        'method': 'Solar geometry calculation'
    }
    
    return dni