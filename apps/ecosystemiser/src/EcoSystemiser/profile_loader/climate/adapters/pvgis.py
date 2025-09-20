"""PVGIS (Photovoltaic Geographical Information System) adapter for solar radiation data"""

import xarray as xr
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple, Any
import logging

from .base import BaseAdapter
from .capabilities import (
    AdapterCapabilities, TemporalCoverage, SpatialCoverage,
    DataFrequency, AuthType, RateLimits, QualityFeatures
)

logger = logging.getLogger(__name__)

class PVGISAdapter(BaseAdapter):
    """Adapter for PVGIS solar radiation data API"""
    
    ADAPTER_NAME = "pvgis"
    ADAPTER_VERSION = "0.1.0"
    BASE_URL = "https://re.jrc.ec.europa.eu/api/v5_2"
    
    # Mapping from canonical names to PVGIS parameter codes  
    # Based on PVGIS 5.3 API documentation and research findings
    VARIABLE_MAPPING = {
        # Solar radiation parameters (W/m2)
        'ghi': 'G(h)',                      # Global horizontal irradiance
        'dni': 'Gb(n)',                     # Direct normal irradiance (beam)
        'dhi': 'Gd(h)',                     # Diffuse horizontal irradiance
        'poa_global': 'G(i)',               # Global irradiance on inclined plane
        'poa_direct': 'Gb(i)',              # Beam irradiance on inclined plane  
        'poa_sky_diffuse': 'Gd(i)',         # Diffuse irradiance on inclined plane
        'poa_ground_diffuse': 'Gr(i)',      # Reflected irradiance on inclined plane
        
        # Meteorological parameters
        'temp_air': 'T2m',                  # Air temperature at 2 meters (degC)
        'wind_speed': 'WS10m',              # Wind speed at 10 meters (m/s)  
        'wind_dir': 'WD10m',                # Wind direction at 10 meters (degrees)
        'rel_humidity': 'RH',               # Relative humidity (%)
        'pressure': 'SP',                   # Surface pressure (Pa)
        
        # Solar position parameters
        'solar_elevation': 'H_sun',         # Solar elevation angle (degrees)
        'solar_azimuth': 'A_sun',           # Solar azimuth angle (degrees)
        
        # Clear sky parameters
        'ghi_clearsky': 'Gc(h)',            # Clear sky global horizontal irradiance
        'dni_clearsky': 'Gbc(n)',           # Clear sky direct normal irradiance
        'dhi_clearsky': 'Gdc(h)',           # Clear sky diffuse horizontal irradiance
    }
    
    # Variables available in different PVGIS endpoints
    SERIESCALC_VARIABLES = {
        # Variables available in seriescalc endpoint (hourly time series)
        'G(h)', 'T2m', 'WS10m', 'H_sun'  # Limited set for time series
    }
    
    HOURLY_VARIABLES = {
        # Variables available in hourly radiation endpoint
        'G(h)', 'Gb(n)', 'Gd(h)', 'T2m', 'WS10m', 'WD10m', 'RH', 'SP', 'H_sun'
    }
    
    TMY_VARIABLES = {
        # Variables available in TMY (Typical Meteorological Year) endpoint
        'G(h)', 'Gb(n)', 'Gd(h)', 'T2m', 'WS10m', 'WD10m', 'RH', 'SP', 'H_sun', 'A_sun'
    }
    
    # Variables that can be derived from other parameters
    DERIVED_VARIABLES = {
        'dewpoint': ['T2m', 'RH'],  # Can derive from temperature and humidity
    }
    
    # Database selection based on location
    DATABASES = {
        'PVGIS-SARAH2': {
            'regions': ['Europe', 'Africa', 'Asia'],
            'years': '2005-2020'
        },
        'PVGIS-ERA5': {
            'regions': ['Global'],
            'years': '2005-2020'
        },
        'PVGIS-NSRDB': {
            'regions': ['Americas'],
            'years': '2005-2015'
        }
    }
    
    def __init__(self):
        """Initialize PVGIS adapter"""
        from .base import RateLimitConfig, CacheConfig, HTTPConfig
        
        # Configure rate limiting (PVGIS is free but be reasonable)
        rate_config = RateLimitConfig(
            requests_per_minute=60,  # Conservative for public API
            burst_size=10
        )
        
        # Configure caching (solar data is static)
        cache_config = CacheConfig(
            memory_ttl=3600,   # 1 hour
            disk_ttl=86400,    # 24 hours
        )
        
        super().__init__(
            name=self.ADAPTER_NAME,
            rate_limit_config=rate_config,
            cache_config=cache_config
        )
    
    # Variables not supported by PVGIS seriescalc endpoint
    UNSUPPORTED_VARIABLES = {
        # PVGIS focuses on solar radiation, many met variables not available
        'precip', 'snow', 'cloud_cover', 'visibility', 'soil_temp', 'soil_moisture'
    }
    
    async def _fetch_raw(
        self,
        location: Tuple[float, float],
        variables: List[str],
        period: Dict,
        **kwargs
    ) -> Optional[Any]:
        """Fetch raw data from PVGIS API"""
        lat, lon = location
        
        # Filter out unsupported variables and warn
        supported_vars = []
        for var in variables:
            if var in self.UNSUPPORTED_VARIABLES:
                self.logger.warning(f"Variable '{var}' is not supported by PVGIS seriescalc endpoint")
            else:
                supported_vars.append(var)
        
        if not supported_vars:
            raise ValueError(f"No supported variables requested. PVGIS supports: {list(self.VARIABLE_MAPPING.keys())}")
        
        # Validate request
        self._validate_request(lat, lon, supported_vars, period)
        
        # Select appropriate database
        database = self._select_database(lat, lon)
        
        # Parse period
        start_date, end_date = self._parse_period(period)
        
        resolution = kwargs.get('resolution', '1H')
        
        # PVGIS has different endpoints for different data types
        if resolution == "1H":
            return await self._fetch_hourly_series(lat, lon, supported_vars, start_date, end_date, database)
        elif resolution == "1D":
            return await self._fetch_daily_series(lat, lon, supported_vars, start_date, end_date, database)
        elif resolution == "TMY":
            return await self._fetch_tmy(lat, lon, supported_vars, database)
        else:
            raise ValueError(f"Unsupported resolution for PVGIS: {resolution}")
    
    async def _transform_data(
        self,
        raw_data: Any,
        location: Tuple[float, float],
        variables: List[str]
    ) -> xr.Dataset:
        """Transform raw PVGIS data to xarray Dataset"""
        lat, lon = location
        
        # Raw data is already the processed dataset from _fetch_raw
        ds = raw_data
        
        # Add metadata
        ds.attrs.update({
            'source': 'PVGIS',
            'adapter_version': self.ADAPTER_VERSION,
            'latitude': lat,
            'longitude': lon,
        })
        
        return ds
    
    def _validate_request(self, lat: float, lon: float, variables: List[str], period: Dict):
        """Validate request parameters"""
        if not (-90 <= lat <= 90):
            raise ValueError(f"Invalid latitude: {lat}")
        if not (-180 <= lon <= 180):
            raise ValueError(f"Invalid longitude: {lon}")
        if not variables:
            raise ValueError("Variables list cannot be empty")
    
    async def fetch(
        self, 
        *, 
        lat: float, 
        lon: float, 
        variables: List[str],
        period: Dict, 
        resolution: str = '1H'
    ) -> xr.Dataset:
        """Fetch solar radiation data from PVGIS API"""
        
        # Filter out unsupported variables and warn
        supported_vars = []
        for var in variables:
            if var in self.UNSUPPORTED_VARIABLES:
                self.logger.warning(f"Variable '{var}' is not supported by PVGIS seriescalc endpoint")
            else:
                supported_vars.append(var)
        
        if not supported_vars:
            raise ValueError(f"No supported variables requested. PVGIS supports: {list(self.VARIABLE_MAPPING.keys())}")
        
        # Use base class fetch method
        return await super().fetch(
            location=(lat, lon),
            variables=supported_vars,
            period=period,
            resolution=resolution
        )
    
    def _select_database(self, lat: float, lon: float) -> str:
        """Select the best PVGIS database based on location"""
        
        # Simple region detection
        if -35 <= lat <= 75 and -25 <= lon <= 65:  # Europe/Africa
            return "PVGIS-SARAH2"
        elif -60 <= lat <= 75 and -180 <= lon <= -30:  # Americas
            return "PVGIS-NSRDB"
        else:
            return "PVGIS-ERA5"  # Global fallback
    
    def _parse_period(self, period: Dict) -> tuple:
        """Parse period dict to start and end dates"""
        
        if "year" in period:
            year = period["year"]
            
            # PVGIS has limited year ranges
            if year < 2005:
                raise ValueError("PVGIS data only available from 2005 onwards")
            if year > 2020:
                logger.warning("PVGIS data may not be available after 2020")
            
            if "month" in period:
                month = int(period["month"]) if isinstance(period["month"], str) else period["month"]
                start_date = datetime(year, month, 1)
                if month == 12:
                    end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = datetime(year, month + 1, 1) - timedelta(days=1)
            else:
                start_date = datetime(year, 1, 1)
                end_date = datetime(year, 12, 31)
        else:
            raise ValueError(f"Invalid period specification for PVGIS: {period}")
        
        return start_date, end_date
    
    async def _fetch_hourly_series(
        self, 
        lat: float, 
        lon: float,
        variables: List[str],
        start_date: datetime,
        end_date: datetime,
        database: str
    ) -> xr.Dataset:
        """Fetch hourly time series data from PVGIS"""
        
        # Build API URL for series data
        url = f"{self.BASE_URL}/seriescalc"
        
        # Validate year constraints for different databases
        if database == "PVGIS-NSRDB" and (start_date.year < 2005 or start_date.year > 2015):
            raise ValueError(f"PVGIS-NSRDB only supports years 2005-2015, requested: {start_date.year}")
        elif database in ["PVGIS-SARAH2", "PVGIS-ERA5"] and start_date.year < 2005:
            raise ValueError(f"{database} only supports years from 2005 onwards, requested: {start_date.year}")
        
        # Prepare parameters
        params = {
            'lat': lat,
            'lon': lon,
            'startyear': start_date.year,
            'endyear': end_date.year,
            'pvcalculation': 0,  # We want meteo data, not PV calculation
            'peakpower': 1,  # Required even if pvcalculation=0
            'loss': 0,
            'outputformat': 'json',
            'browser': 0
        }
        
        # Add database selection
        if database == "PVGIS-SARAH2":
            params['raddatabase'] = 'PVGIS-SARAH2'
        elif database == "PVGIS-NSRDB":
            params['raddatabase'] = 'PVGIS-NSRDB'
        else:
            params['raddatabase'] = 'PVGIS-ERA5'
        
        logger.info(f"Fetching PVGIS hourly data for {lat},{lon} using {database}")
        
        try:
            response = await self.http_client.get(url, params=params)
            data = response.json()
        except Exception as e:
            self.logger.error(f"Error fetching PVGIS data: {e}")
            raise
        
        # Parse response to xarray
        ds = self._parse_hourly_response(data, variables, lat, lon, start_date, end_date)
        
        return ds
    
    async def _fetch_daily_series(
        self, 
        lat: float, 
        lon: float,
        variables: List[str],
        start_date: datetime,
        end_date: datetime,
        database: str
    ) -> xr.Dataset:
        """Fetch daily aggregated data from PVGIS"""
        
        # PVGIS daily endpoint
        url = f"{self.BASE_URL}/DRcalc"
        
        params = {
            'lat': lat,
            'lon': lon,
            'month': start_date.month if start_date.month == end_date.month else 0,  # 0 for full year
            'year': start_date.year,
            'raddatabase': database,
            'outputformat': 'json',
            'browser': 0
        }
        
        logger.info(f"Fetching PVGIS daily data for {lat},{lon} using {database}")
        
        try:
            response = await self.http_client.get(url, params=params)
            data = response.json()
        except Exception as e:
            self.logger.error(f"Error fetching PVGIS daily data: {e}")
            raise
        
        # Parse response
        ds = self._parse_daily_response(data, variables, lat, lon, start_date, end_date)
        
        return ds
    
    async def _fetch_tmy(
        self, 
        lat: float, 
        lon: float,
        variables: List[str],
        database: str
    ) -> xr.Dataset:
        """Fetch Typical Meteorological Year data from PVGIS"""
        
        url = f"{self.BASE_URL}/tmy"
        
        params = {
            'lat': lat,
            'lon': lon,
            'outputformat': 'json'
        }
        
        logger.info(f"Fetching PVGIS TMY data for {lat},{lon}")
        
        try:
            response = await self.http_client.get(url, params=params)
            data = response.json()
        except Exception as e:
            self.logger.error(f"Error fetching PVGIS TMY data: {e}")
            raise
        
        # Parse TMY response
        ds = self._parse_tmy_response(data, variables, lat, lon)
        
        return ds
    
    def _parse_hourly_response(
        self, 
        data: Dict,
        variables: List[str],
        lat: float,
        lon: float,
        start_date: datetime,
        end_date: datetime
    ) -> xr.Dataset:
        """Parse PVGIS hourly response to xarray Dataset"""
        
        # Extract hourly data
        if 'outputs' not in data or 'hourly' not in data['outputs']:
            raise ValueError("Invalid PVGIS response structure")
        
        hourly_data = data['outputs']['hourly']
        
        # Convert to DataFrame
        df = pd.DataFrame(hourly_data)
        
        # Parse time column
        df['time'] = pd.to_datetime(df['time'], format='%Y%m%d:%H%M')
        df.set_index('time', inplace=True)
        
        # Filter to requested period
        mask = (df.index >= start_date) & (df.index <= end_date)
        df = df.loc[mask]
        
        # Create Dataset
        ds = xr.Dataset(coords={'time': df.index})
        ds.attrs['latitude'] = lat
        ds.attrs['longitude'] = lon
        ds.attrs['source'] = 'PVGIS'
        
        # Map variables with improved fallback logic
        for canonical_name in variables:
            added = False
            
            # Try primary mapping first
            if canonical_name in self.VARIABLE_MAPPING:
                pvgis_name = self.VARIABLE_MAPPING[canonical_name]
                
                if pvgis_name in df.columns:
                    # Handle unit conversions if needed
                    data = self._convert_units(df[pvgis_name].values, canonical_name)
                    
                    ds[canonical_name] = xr.DataArray(
                        data,
                        coords={'time': df.index},
                        attrs=self._get_variable_attrs(canonical_name)
                    )
                    added = True
            
            # If not added, try fallback mappings for solar variables
            if not added and canonical_name in ['ghi', 'dni', 'dhi']:
                # Check available solar-related columns in actual response
                fallback_mappings = {
                    'ghi': ['G(i)', 'G(h)', 'GHI'],  # Try inclined, then horizontal
                    'dni': ['DNI', 'Gb(n)', 'BNI'],
                    'dhi': ['DHI', 'Gd(h)', 'DIF']
                }
                
                if canonical_name in fallback_mappings:
                    for fallback_col in fallback_mappings[canonical_name]:
                        if fallback_col in df.columns:
                            ds[canonical_name] = xr.DataArray(
                                df[fallback_col].values,
                                coords={'time': df.index},
                                attrs=self._get_variable_attrs(canonical_name)
                            )
                            added = True
                            break
            
            # Try to derive variables if not directly available
            if not added and canonical_name in self.DERIVED_VARIABLES:
                required_vars = self.DERIVED_VARIABLES[canonical_name]
                if canonical_name == 'dewpoint' and all(v in df.columns for v in ['T2m', 'RH']):
                    # Calculate dewpoint from temperature and humidity
                    dewpoint_data = self._calculate_dewpoint(df['T2m'].values, df['RH'].values)
                    ds[canonical_name] = xr.DataArray(
                        dewpoint_data,
                        coords={'time': df.index},
                        attrs=self._get_variable_attrs(canonical_name)
                    )
                    added = True
                    logger.info(f"Derived dewpoint from temperature and humidity")
            
            if not added:
                logger.warning(f"Variable '{canonical_name}' not found in PVGIS response. Available columns: {list(df.columns)}")
        
        return ds
    
    def _parse_daily_response(
        self, 
        data: Dict,
        variables: List[str],
        lat: float,
        lon: float,
        start_date: datetime,
        end_date: datetime
    ) -> xr.Dataset:
        """Parse PVGIS daily response to xarray Dataset"""
        
        if 'outputs' not in data or 'daily_profile' not in data['outputs']:
            raise ValueError("Invalid PVGIS daily response")
        
        daily_data = data['outputs']['daily_profile']
        
        # Create time index
        num_days = (end_date - start_date).days + 1
        time_index = pd.date_range(start_date, periods=num_days, freq='D')
        
        # Create Dataset
        ds = xr.Dataset(coords={'time': time_index})
        ds.attrs['latitude'] = lat
        ds.attrs['longitude'] = lon
        ds.attrs['source'] = 'PVGIS'
        
        # Parse available variables
        for canonical_name in variables:
            if canonical_name == 'ghi' and len(daily_data) > 0:
                # Extract daily GHI values (limit to available data)
                available_days = min(len(daily_data), num_days)
                values = [d.get('G(d)', np.nan) for d in daily_data[:available_days]]
                # Pad with NaN if needed
                if len(values) < num_days:
                    values.extend([np.nan] * (num_days - len(values)))
                ds[canonical_name] = xr.DataArray(
                    values,
                    coords={'time': time_index},
                    attrs=self._get_variable_attrs(canonical_name)
                )
        
        return ds
    
    def _parse_tmy_response(
        self, 
        data: Dict,
        variables: List[str],
        lat: float,
        lon: float
    ) -> xr.Dataset:
        """Parse PVGIS TMY response to xarray Dataset"""
        
        if 'outputs' not in data or 'tmy_hourly' not in data['outputs']:
            raise ValueError("Invalid PVGIS TMY response")
        
        tmy_data = data['outputs']['tmy_hourly']
        
        # Convert to DataFrame
        df = pd.DataFrame(tmy_data)
        
        # Create typical year time index
        # TMY uses a representative year (usually current year for time index)
        current_year = datetime.now().year
        df['time'] = pd.to_datetime(
            df['time(UTC)'], 
            format='%m%d:%H%M'
        ).apply(lambda x: x.replace(year=current_year))
        df.set_index('time', inplace=True)
        
        # Create Dataset
        ds = xr.Dataset(coords={'time': df.index})
        ds.attrs['latitude'] = lat
        ds.attrs['longitude'] = lon
        ds.attrs['source'] = 'PVGIS-TMY'
        ds.attrs['tmy'] = True
        
        # Map variables
        for canonical_name in variables:
            pvgis_cols = {
                'ghi': 'G(h)',
                'dni': 'Gb(n)',
                'dhi': 'Gd(h)',
                'temp_air': 'T2m',
                'wind_speed': 'WS10m',
                'rel_humidity': 'RH'
            }
            
            if canonical_name in pvgis_cols and pvgis_cols[canonical_name] in df.columns:
                ds[canonical_name] = xr.DataArray(
                    df[pvgis_cols[canonical_name]].values,
                    coords={'time': df.index},
                    attrs=self._get_variable_attrs(canonical_name)
                )
        
        return ds
    
    def _calculate_dewpoint(self, temperature: np.ndarray, rel_humidity: np.ndarray) -> np.ndarray:
        """
        Calculate dewpoint temperature from air temperature and relative humidity.
        
        Uses Magnus-Tetens formula for dewpoint calculation.
        
        Args:
            temperature: Air temperature in degC
            rel_humidity: Relative humidity in %
            
        Returns:
            Dewpoint temperature in degC
        """
        # Magnus-Tetens formula constants
        a = 17.27
        b = 237.7
        
        # Calculate dewpoint
        # First calculate the vapor pressure term
        alpha = (a * temperature) / (b + temperature) + np.log(rel_humidity / 100.0)
        
        # Then solve for dewpoint temperature
        dewpoint = (b * alpha) / (a - alpha)
        
        return dewpoint
    
    def _convert_units(self, data: np.ndarray, canonical_name: str) -> np.ndarray:
        """Convert PVGIS units to canonical units if needed"""
        
        # PVGIS generally uses standard units, minimal conversion needed
        conversions = {
            # Solar elevation to zenith angle
            'solar_zenith': lambda x: 90 - x,
        }
        
        if canonical_name in conversions:
            return conversions[canonical_name](data)
        
        return data
    
    def _get_variable_attrs(self, canonical_name: str) -> Dict:
        """Get variable attributes including units"""
        
        units_map = {
            'ghi': 'W/m2',
            'dni': 'W/m2',
            'dhi': 'W/m2',
            'dewpoint': 'degC',
            'temp_air': 'degC',
            'wind_speed': 'm/s',
            'pressure': 'Pa',
            'rel_humidity': '%',
            'solar_zenith': 'degrees'
        }
        
        return {
            "units": units_map.get(canonical_name, "unknown"),
            "long_name": canonical_name.replace("_", " ").title()
        }
    
    def get_capabilities(self) -> AdapterCapabilities:
        """Return PVGIS adapter capabilities"""
        return AdapterCapabilities(
            name="PVGIS",
            version=self.ADAPTER_VERSION,
            description="European Commission's solar radiation and PV performance database",
            
            temporal=TemporalCoverage(
                start_date=date(2005, 1, 1),
                end_date=date(2020, 12, 31),
                historical_years=16,
                forecast_days=0,
                real_time=False,
                delay_hours=None  # Historical data only
            ),
            
            spatial=SpatialCoverage(
                global_coverage=True,  # Through ERA5 database
                regions=["Europe", "Africa", "Asia", "Americas"],
                resolution_km=5,  # SARAH2: 5km, ERA5: 30km
                station_based=False,
                grid_based=True,
                custom_locations=True
            ),
            
            supported_variables=list(self.VARIABLE_MAPPING.keys()),
            
            primary_variables=[
                "ghi",  # Primary strength: solar irradiance (on inclined plane)
                "temp_air",  # Temperature
                "solar_elevation"  # Solar position
            ],
            
            derived_variables=["pv_power"],  # Can calculate PV output
            
            supported_frequencies=[
                DataFrequency.HOURLY,
                DataFrequency.DAILY,
                DataFrequency.MONTHLY,
                DataFrequency.TMY
            ],
            
            native_frequency=DataFrequency.HOURLY,
            
            auth_type=AuthType.NONE,
            requires_subscription=False,
            free_tier_limits=None,  # No limits
            
            quality=QualityFeatures(
                gap_filling=True,
                quality_flags=True,
                uncertainty_estimates=True,  # Provides uncertainty for PV calculations
                ensemble_members=False,
                bias_correction=True
            ),
            
            max_request_days=366,  # 1 year at a time
            max_variables_per_request=None,
            batch_requests_supported=False,
            async_requests_required=False,
            
            special_features=[
                "Optimized for solar energy applications",
                "Multiple satellite databases (SARAH2, ERA5, NSRDB)",
                "Typical Meteorological Year (TMY) data",
                "PV system performance calculations",
                "Horizon profile integration",
                "High-resolution solar data for Europe/Africa"
            ],
            
            data_products=["Hourly", "Daily", "Monthly", "TMY", "PV Performance"]
        )