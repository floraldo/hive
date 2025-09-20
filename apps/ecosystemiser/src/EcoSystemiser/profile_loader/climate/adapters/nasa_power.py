"""NASA POWER API adapter for climate data"""

import xarray as xr
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
import logging
from ..utils.chunking import split_date_range, concatenate_chunked_results, estimate_memory_usage

from .base import BaseAdapter
from .capabilities import (
    AdapterCapabilities, TemporalCoverage, SpatialCoverage,
    DataFrequency, AuthType, RateLimits, QualityFeatures
)
from ..data_models import CANONICAL_VARIABLES
from EcoSystemiser.errors import DataFetchError, DataParseError, ValidationError

logger = logging.getLogger(__name__)

class NASAPowerAdapter(BaseAdapter):
    """Adapter for NASA POWER climate data API"""
    
    ADAPTER_NAME = "nasa_power"
    ADAPTER_VERSION = "0.1.0"
    BASE_URL = 'https://power.larc.nasa.gov/api/temporal/hourly/point'
    
    # Mapping from canonical names to NASA POWER parameter codes
    VARIABLE_MAPPING = {
        # Temperature parameters
        'temp_air': 'T2M',                    # Air temperature at 2 meters (degC)
        'temp_air_max': 'T2M_MAX',            # Maximum air temperature at 2 meters (degC)  
        'temp_air_min': 'T2M_MIN',            # Minimum air temperature at 2 meters (degC)
        'dewpoint': 'T2MDEW',                 # Dew point temperature at 2 meters (degC)
        'temp_air_range': 'T2M_RANGE',        # Temperature range at 2 meters (degC)
        'earth_skin_temp': 'TS',              # Earth skin temperature (degC)
        
        # Humidity parameters  
        'rel_humidity': 'RH2M',               # Relative humidity at 2 meters (%)
        'specific_humidity': 'QV2M',          # Specific humidity at 2 meters (g/kg)
        
        # Wind parameters
        'wind_speed': 'WS10M',                # Wind speed at 10 meters (m/s)
        'wind_speed_max': 'WS10M_MAX',        # Maximum wind speed at 10 meters (m/s)
        'wind_speed_min': 'WS10M_MIN',        # Minimum wind speed at 10 meters (m/s)
        'wind_speed_50m': 'WS50M',            # Wind speed at 50 meters (m/s)
        'wind_speed_50m_max': 'WS50M_MAX',    # Maximum wind speed at 50 meters (m/s)
        'wind_speed_50m_min': 'WS50M_MIN',    # Minimum wind speed at 50 meters (m/s)
        'wind_dir': 'WD10M',                  # Wind direction at 10 meters (degrees)
        'wind_dir_50m': 'WD50M',              # Wind direction at 50 meters (degrees)
        
        # Solar radiation parameters (W/m2)
        'ghi': 'ALLSKY_SFC_SW_DWN',           # Global horizontal irradiance
        'dni': 'DNI',                         # Direct normal irradiance
        'dhi': 'DIFF',                        # Diffuse horizontal irradiance
        'ghi_clearsky': 'CLRSKY_SFC_SW_DWN',  # Clear sky global horizontal irradiance
        'dni_clearsky': 'CLRSKY_DNI',         # Clear sky direct normal irradiance
        'dhi_clearsky': 'CLRSKY_DIFF',        # Clear sky diffuse horizontal irradiance
        'par': 'ALLSKY_SFC_PAR_TOT',          # Photosynthetically active radiation
        'par_clearsky': 'CLRSKY_SFC_PAR_TOT', # Clear sky PAR
        'uv': 'ALLSKY_SFC_UVA',               # UV-A irradiance
        'uvb': 'ALLSKY_SFC_UVB',              # UV-B irradiance
        
        # Longwave radiation parameters
        'lw_down': 'ALLSKY_SFC_LW_DWN',       # Longwave radiation downward
        'lw_up': 'ALLSKY_SFC_LW_UP',          # Longwave radiation upward (estimated)
        'lw_net': 'ALLSKY_SFC_LW_NET',        # Net longwave radiation
        
        # Precipitation parameters  
        'precip': 'PRECTOTCORR',              # Corrected precipitation (mm/hour)
        'precip_land': 'PRECTOTLAND',         # Precipitation over land (mm/hour)
        'snow': 'SNOW',                       # Snowfall (mm water equivalent)
        
        # Pressure parameters
        'pressure': 'PS',                     # Surface pressure (kPa)
        
        # Cloud parameters
        'cloud_cover': 'CLOUD_AMT',           # Cloud amount (%)
        'cloud_cover_low': 'CLDTT',           # Cloud transmittance (%)
        
        # Atmospheric parameters
        'wind_shear': 'WS_SHEAR',             # Wind shear between 10m and 50m
        'atmospheric_water': 'TQV',           # Total column water vapor (g/cm2)
        'ozone': 'TO3',                       # Total ozone (Dobson Units)
        'aerosol_optical_depth': 'AOD',       # Aerosol optical depth
        
        # Evapotranspiration and soil parameters
        'evapotranspiration': 'EVPTRNS',      # Evapotranspiration energy flux (MJ/m2/day)
        'evaporation': 'EVAP',                # Evaporation from wet soil (mm/day)
        'soil_temp_0_10cm': 'T0_10CM',        # Soil temperature 0-10cm depth (degC)
        'soil_temp_10_40cm': 'T10_40CM',      # Soil temperature 10-40cm depth (degC)
        'soil_temp_40_100cm': 'T40_100CM',    # Soil temperature 40-100cm depth (degC)
        'soil_temp_100_200cm': 'T100_200CM',  # Soil temperature 100-200cm depth (degC)
        
        # Additional meteorological parameters
        'frost_days': 'FROST_DAYS',           # Number of frost days
        'wet_bulb_temp': 'T2MWET',            # Wet bulb temperature at 2m (degC)
        'heating_degree_days': 'T2M_HDD',     # Heating degree days base 18.3degC
        'cooling_degree_days': 'T2M_CDD',     # Cooling degree days base 18.3degC
        'growing_degree_days': 'T2M_GDD',     # Growing degree days base 10degC
    }
    
    # Reverse mapping
    REVERSE_MAPPING = {v: k for k, v in VARIABLE_MAPPING.items()}
    
    async def _fetch_raw(
        self,
        location: Tuple[float, float],
        variables: List[str],
        period: Dict[str, Any],
        **kwargs
    ) -> Optional[Any]:
        """Fetch raw data from NASA POWER API"""
        lat, lon = location
        
        # Validate request
        self._validate_request(lat, lon, variables, period)
        
        # Build request parameters
        params = self.build_request_params(lat, lon, variables, period, 'hourly')
        
        # Make HTTP request using base class client
        response = await self.http_client.get(self.BASE_URL, params=params)
        
        # Parse JSON response
        data = response.json()
        
        # Validate response structure
        if 'properties' not in data:
            raise DataParseError(
                self.ADAPTER_NAME,
                "Invalid NASA POWER response structure",
                field='properties'
            )
        
        return data
    
    async def _transform_data(
        self,
        raw_data: Any,
        location: Tuple[float, float],
        variables: List[str]
    ) -> xr.Dataset:
        """Transform raw NASA POWER data to xarray Dataset"""
        lat, lon = location
        
        # Convert to xarray Dataset
        ds = self._json_to_xarray(raw_data, variables)
        
        # Optimize memory usage
        ds = self._optimize_dataset_memory(ds)
        
        # Add metadata
        ds.attrs.update({
            'source': 'NASA POWER',
            'adapter_version': self.ADAPTER_VERSION,
            'latitude': lat,
            'longitude': lon,
            'license': 'NASA Open Data Policy'
        })
        
        return ds
    
    async def fetch(
        self, 
        *, 
        lat: float, 
        lon: float, 
        variables: List[str],
        period: Dict[str, Any], 
        resolution: str,
        chunk_years: int = 1,  # Maximum years per request
        use_batch: bool = False  # Enable batch processing
    ) -> xr.Dataset:
        """
        Fetch climate data from NASA POWER API.
        
        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            variables: List of canonical variable names
            period: Time period (e.g., {"year": 2019})
            resolution: Time resolution (NASA POWER provides hourly)
            
        Returns:
            xarray.Dataset with UTC time index and canonical variable names
            
        Raises:
            DataFetchError: If API request fails
            DataParseError: If response cannot be parsed
            ValidationError: If parameters are invalid
        """
        try:
            # Check if we need to chunk the request
            start_date, end_date = self._parse_period(period)
            days_diff = (end_date - start_date).days
            
            # If request is large, process in chunks
            if days_diff > (chunk_years * 365):
                logger.info(f"Large date range detected ({days_diff} days), processing in chunks")
                return await self._fetch_chunked(lat, lon, variables, period, resolution, chunk_years)
            
            # Use batch processing if enabled and beneficial
            if use_batch and len(variables) > 5:
                return await self._fetch_batched(lat, lon, variables, period, resolution)
            
            # Use base class fetch method
            return await super().fetch(
                location=(lat, lon),
                variables=variables,
                period=period,
                resolution=resolution
            )
            
        except Exception as e:
            # Wrap unexpected errors
            error = DataFetchError(
                self.ADAPTER_NAME,
                f"Unexpected error fetching NASA POWER data: {str(e)}",
                details={'lat': lat, 'lon': lon, 'variables': variables}
            )
            raise error
    
    def build_request_params(
        self,
        lat: float,
        lon: float,
        variables: List[str],
        period: Dict[str, Any],
        resolution: str
    ) -> Dict[str, Any]:
        """
        Build request parameters for NASA POWER API.
        
        Args:
            lat: Latitude
            lon: Longitude
            variables: List of variables to fetch
            period: Time period specification
            resolution: Time resolution
            
        Returns:
            Dictionary of request parameters
        """
        # Parse period
        start_date, end_date = self._parse_period(period)
        
        # Map canonical variables to NASA POWER parameters
        nasa_params = []
        for var in variables:
            if var in self.VARIABLE_MAPPING:
                nasa_params.append(self.VARIABLE_MAPPING[var])
            else:
                logger.warning(f"Variable '{var}' not available in NASA POWER")
        
        if not nasa_params:
            raise ValidationError(
                f"No valid variables for NASA POWER from: {variables}",
                field='variables',
                value=variables,
                recovery_suggestion=f"Available variables: {list(self.VARIABLE_MAPPING.keys())}"
            )
        
        return {
            'start': start_date.strftime('%Y%m%d'),
            'end': end_date.strftime('%Y%m%d'),
            'latitude': f"{float(lat):.4f}",
            'longitude': f"{float(lon):.4f}",
            'parameters': ','.join(nasa_params),
            'community': 'RE',
            'format': 'JSON',
            'time_standard': 'UTC'
        }
    
    def parse_response_to_dataset(
        self,
        response_data: Dict[str, Any],
        variables: List[str],
        lat: float,
        lon: float
    ) -> xr.Dataset:
        """
        Parse NASA POWER API response into xarray Dataset.
        
        Args:
            response_data: Parsed API response
            variables: Requested variables
            lat: Latitude
            lon: Longitude
            
        Returns:
            xarray Dataset with canonical variable names
        """
        return self._json_to_xarray(response_data, variables)
    
    def _parse_period(self, period: Dict[str, Any]) -> Tuple[datetime, datetime]:
        """Parse period specification to start and end dates"""
        if 'year' in period:
            year = int(period['year'])
            start = datetime(year, 1, 1)
            end = datetime(year, 12, 31, 23, 0, 0)
        elif 'start' in period and 'end' in period:
            start = pd.to_datetime(period['start'])
            end = pd.to_datetime(period['end'])
        else:
            raise ValueError("Period must specify 'year' or both 'start' and 'end'")
        
        return start, end
    
    def _json_to_xarray(self, data: Dict[str, Any], requested_vars: List[str]) -> xr.Dataset:
        """Convert NASA POWER JSON response to xarray Dataset"""
        
        try:
            properties = data.get('properties', {})
            parameters = properties.get('parameter', {})
            
            if not parameters:
                raise DataParseError(
                    self.ADAPTER_NAME,
                    "No parameter data in NASA POWER response",
                    field='properties.parameter'
                )
            
            # Get timestamps from first parameter
            first_param = list(parameters.keys())[0]
            timestamps_str = sorted(parameters[first_param].keys())
            
            # Convert timestamps to datetime
            timestamps = [datetime.strptime(ts, '%Y%m%d%H') for ts in timestamps_str]
            
            # Create data arrays
            data_vars = {}
            
            for nasa_param, values in parameters.items():
                if nasa_param in self.REVERSE_MAPPING:
                    canonical_name = self.REVERSE_MAPPING[nasa_param]
                    
                    if canonical_name in requested_vars:
                        # Extract values in timestamp order
                        data_array = np.array([values.get(ts, np.nan) for ts in timestamps_str])
                        
                        # Create DataArray with proper metadata
                        da = xr.DataArray(
                            data_array,
                            dims=['time'],
                            coords={'time': timestamps},
                            name=canonical_name
                        )
                        
                        # Add units
                        if canonical_name in CANONICAL_VARIABLES:
                            da.attrs['units'] = CANONICAL_VARIABLES[canonical_name]['unit']
                            da.attrs['type'] = CANONICAL_VARIABLES[canonical_name]['type']
                        
                        # Convert units if needed
                        da = self._convert_units(da, canonical_name, nasa_param)
                        
                        data_vars[canonical_name] = da
            
            if not data_vars:
                raise DataParseError(
                    self.ADAPTER_NAME,
                    f"No matching variables found in response for: {requested_vars}",
                    details={'available_params': list(parameters.keys())}
                )
            
            # Create Dataset
            ds = xr.Dataset(data_vars)
            
            # Ensure time is in UTC
            ds = ds.assign_coords(time=pd.DatetimeIndex(ds.time, tz='UTC'))
            
            return ds
            
        except DataParseError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Wrap unexpected parsing errors
            raise DataParseError(
                self.ADAPTER_NAME,
                f"Failed to parse NASA POWER response: {str(e)}",
                details={'variables': requested_vars}
            )
    
    def _convert_units(self, da: xr.DataArray, canonical_name: str, nasa_param: str) -> xr.DataArray:
        """Convert units from NASA POWER to canonical units if needed"""
        
        # NASA POWER specific unit conversions
        conversions = {
            'PS': lambda x: x * 1000,  # kPa to Pa
        }
        
        if nasa_param in conversions:
            da.data = conversions[nasa_param](da.data)
        
        return da
    
    def _validate_request(self, lat: float, lon: float, variables: List[str], period: Dict[str, Any]):
        """Validate request parameters"""
        if not (-90 <= lat <= 90):
            raise ValidationError(f"Invalid latitude: {lat}", field='lat', value=lat)
        if not (-180 <= lon <= 180):
            raise ValidationError(f"Invalid longitude: {lon}", field='lon', value=lon)
        if not variables:
            raise ValidationError("Variables list cannot be empty", field='variables', value=variables)
    
    def _optimize_dataset_memory(self, ds: xr.Dataset) -> xr.Dataset:
        """Optimize dataset memory usage by converting to appropriate dtypes"""
        import numpy as np
        
        # Convert data variables to float32 for memory efficiency
        for var in ds.data_vars:
            if ds[var].dtype == np.float64:
                ds[var] = ds[var].astype(np.float32)
        
        return ds
    
    def __init__(self):
        """Initialize NASA POWER adapter"""
        from .base import RateLimitConfig, CacheConfig, HTTPConfig
        
        # Configure rate limiting (NASA POWER has no strict limits)
        rate_config = RateLimitConfig(
            requests_per_minute=120,  # Conservative limit
            burst_size=20
        )
        
        # Configure caching
        cache_config = CacheConfig(
            memory_ttl=900,  # 15 minutes
            disk_ttl=7200,   # 2 hours
        )
        
        super().__init__(
            name=self.ADAPTER_NAME,
            rate_limit_config=rate_config,
            cache_config=cache_config
        )
    
    def get_capabilities(self) -> AdapterCapabilities:
        """Return NASA POWER adapter capabilities"""
        return AdapterCapabilities(
            name="NASA POWER",
            version=self.ADAPTER_VERSION,
            description="NASA's Prediction Of Worldwide Energy Resources - global meteorological and solar data",
            
            temporal=TemporalCoverage(
                start_date=date(1981, 1, 1),
                end_date=None,  # Present
                historical_years=43,
                forecast_days=0,
                real_time=False,
                delay_hours=24  # Typically 1 day delay
            ),
            
            spatial=SpatialCoverage(
                global_coverage=True,
                regions=None,
                resolution_km=50,  # 0.5deg x 0.5deg
                station_based=False,
                grid_based=True,
                custom_locations=True
            ),
            
            supported_variables=list(self.VARIABLE_MAPPING.keys()),
            
            primary_variables=[
                "ghi", "dni", "dhi",  # Solar radiation - primary strength
                "temp_air", "wind_speed"  # Also good for these
            ],
            
            derived_variables=[],
            
            supported_frequencies=[
                DataFrequency.HOURLY,
                DataFrequency.DAILY,
                DataFrequency.MONTHLY
            ],
            
            native_frequency=DataFrequency.HOURLY,
            
            auth_type=AuthType.NONE,
            requires_subscription=False,
            free_tier_limits=None,  # No rate limits
            
            quality=QualityFeatures(
                gap_filling=True,  # Uses MERRA-2 reanalysis
                quality_flags=False,
                uncertainty_estimates=False,
                ensemble_members=False,
                bias_correction=True  # Satellite bias corrected
            ),
            
            max_request_days=366,  # Max 1 year per request
            max_variables_per_request=20,
            batch_requests_supported=False,
            async_requests_required=False,
            
            special_features=[
                "Global coverage since 1981",
                "No authentication required",
                "Satellite-derived with reanalysis",
                "Optimized for renewable energy",
                "MERRA-2 reanalysis based"
            ],
            
            data_products=["Hourly", "Daily", "Monthly", "Climatology"]
        )
    
    async def _fetch_chunked(
        self,
        lat: float,
        lon: float,
        variables: List[str],
        period: Dict,
        resolution: str,
        chunk_years: int = 1
    ) -> xr.Dataset:
        """
        Fetch data in chunks for large date ranges.
        
        Args:
            lat: Latitude
            lon: Longitude  
            variables: Variables to fetch
            period: Time period
            resolution: Time resolution
            chunk_years: Years per chunk
            
        Returns:
            Combined dataset from all chunks
        """
        start_date, end_date = self._parse_period(period)
        chunks = split_date_range(start_date, end_date, chunk_years * 365)
        
        datasets = []
        for i, (chunk_start, chunk_end) in enumerate(chunks):
            logger.info(f"Fetching chunk {i+1}/{len(chunks)}: {chunk_start} to {chunk_end}")
            
            # Create period dict for this chunk
            chunk_period = {
                'start': chunk_start.strftime('%Y%m%d'),
                'end': chunk_end.strftime('%Y%m%d')
            }
            
            # Fetch chunk (recursive call without chunking)
            chunk_ds = await self.fetch(
                lat=lat,
                lon=lon,
                variables=variables,
                period=chunk_period,
                resolution=resolution,
                chunk_years=999  # Prevent infinite recursion
            )
            
            datasets.append(chunk_ds)
            
            # Log memory usage
            mem_usage = estimate_memory_usage(chunk_ds)
            logger.debug(f"Chunk {i+1} memory usage: {mem_usage:.2f} MB")
        
        # Combine all chunks
        combined = concatenate_chunked_results(datasets, dim='time')
        logger.info(f"Successfully combined {len(chunks)} chunks")
        
        return combined
    
    async def _fetch_batched(
        self,
        lat: float,
        lon: float,
        variables: List[str],
        period: Dict[str, Any],
        resolution: str
    ) -> xr.Dataset:
        """
        Fetch data using smart batching to reduce API calls.
        
        Args:
            lat: Latitude
            lon: Longitude
            variables: Variables to fetch
            period: Time period
            resolution: Time resolution
            
        Returns:
            Combined dataset from batched requests
        """
        # Group variables into optimal batches
        # NASA POWER can handle multiple variables per request
        batch_size = 10  # NASA POWER limit
        batches = [variables[i:i + batch_size] for i in range(0, len(variables), batch_size)]
        
        datasets = []
        for i, batch_vars in enumerate(batches):
            logger.info(f"Fetching batch {i+1}/{len(batches)}: {batch_vars}")
            
            # Fetch batch without batching enabled to prevent recursion
            batch_ds = await self.fetch(
                lat=lat,
                lon=lon,
                variables=batch_vars,
                period=period,
                resolution=resolution,
                use_batch=False
            )
            
            datasets.append(batch_ds)
        
        # Merge all datasets
        if len(datasets) == 1:
            return datasets[0]
        
        # Combine along variable dimension
        combined = xr.merge(datasets)
        logger.info(f"Successfully combined {len(batches)} batches")
        
        return combined