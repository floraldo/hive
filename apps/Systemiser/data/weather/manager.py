from hive_logging import get_logger

logger = get_logger(__name__)
"""
Weather Data Manager

Main interface for weather data operations in Systemiser.
Coordinates data providers, processors, and caching.
"""

import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
import logging
from pathlib import Path

from .providers import BaseWeatherProvider, NasaPowerProvider
from .processors import BaseWeatherProcessor, StandardWeatherProcessor

# Use Systemiser logger
try:
    from Systemiser.utils.logger import setup_logging
    logger = setup_logging("WeatherDataManager", level=logging.INFO)
except ImportError:
    logger = logging.getLogger("WeatherDataManager_Fallback")
    logger.warning("Could not import Systemiser logger, using fallback.")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


class WeatherDataManager:
    """
    Main weather data management interface for Systemiser.
    
    Provides a unified interface for fetching, processing, caching,
    and accessing weather data from various providers.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the weather data manager.
        
        Args:
            cache_dir: Directory for caching weather data. 
                      If None, uses 'Systemiser/data/weather/cache'
        """
        self.logger = logger
        
        # Set up cache directory
        if cache_dir is None:
            # Default to cache directory relative to this file
            current_dir = Path(__file__).parent
            cache_dir = current_dir / "cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize providers and processors
        self.providers: Dict[str, BaseWeatherProvider] = {}
        self.processors: Dict[str, BaseWeatherProcessor] = {}
        
        # Register default providers and processors
        self._register_defaults()
        
        # Default settings
        self.default_provider = "nasa_power"
        self.default_processor = "standard"
        
        self.logger.info(f"Initialized WeatherDataManager with cache dir: {self.cache_dir}")
    
    def _register_defaults(self):
        """Register default providers and processors."""
        # Register providers
        self.register_provider("nasa_power", NasaPowerProvider())
        
        # Register processors  
        self.register_processor("standard", StandardWeatherProcessor())
    
    def register_provider(self, name: str, provider: BaseWeatherProvider):
        """
        Register a weather data provider.
        
        Args:
            name: Unique name for the provider
            provider: Provider instance
        """
        self.providers[name] = provider
        self.logger.info(f"Registered weather provider: {name}")
    
    def register_processor(self, name: str, processor: BaseWeatherProcessor):
        """
        Register a weather data processor.
        
        Args:
            name: Unique name for the processor
            processor: Processor instance
        """
        self.processors[name] = processor
        self.logger.info(f"Registered weather processor: {name}")
    
    def list_providers(self) -> List[str]:
        """Get list of available provider names."""
        return list(self.providers.keys())
    
    def list_processors(self) -> List[str]:
        """Get list of available processor names."""
        return list(self.processors.keys())
    
    def get_data(self, 
                 latitude: float, 
                 longitude: float,
                 start_date: Union[str, datetime],
                 end_date: Union[str, datetime],
                 provider: Optional[str] = None,
                 processor: Optional[str] = None,
                 use_cache: bool = True,
                 validate: bool = True,
                 clean: bool = True,
                 **kwargs) -> Optional[pd.DataFrame]:
        """
        Get weather data with full processing pipeline.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            start_date: Start date (string in YYYYMMDD format or datetime)
            end_date: End date (string in YYYYMMDD format or datetime)
            provider: Provider name (default: self.default_provider)
            processor: Processor name (default: self.default_processor)
            use_cache: Whether to use cached data if available
            validate: Whether to validate the data
            clean: Whether to clean the data
            **kwargs: Additional arguments passed to provider
            
        Returns:
            Processed weather DataFrame or None if failed
        """
        # Use defaults if not specified
        provider = provider or self.default_provider
        processor = processor or self.default_processor
        
        # Validate inputs
        if provider not in self.providers:
            self.logger.error(f"Unknown provider: {provider}. Available: {list(self.providers.keys())}")
            return None
            
        if processor not in self.processors:
            self.logger.error(f"Unknown processor: {processor}. Available: {list(self.processors.keys())}")
            return None
        
        # Convert dates to strings if needed
        if isinstance(start_date, datetime):
            start_date = start_date.strftime("%Y%m%d")
        if isinstance(end_date, datetime):
            end_date = end_date.strftime("%Y%m%d")
        
        self.logger.info(f"Getting weather data: lat={latitude}, lon={longitude}, "
                        f"dates={start_date} to {end_date}, provider={provider}, processor={processor}")
        
        # Check cache first
        if use_cache:
            cached_data = self._load_from_cache(latitude, longitude, start_date, end_date, provider, processor)
            if cached_data is not None:
                self.logger.info("Loaded data from cache")
                return cached_data
        
        # Fetch raw data from provider
        provider_instance = self.providers[provider]
        raw_df = provider_instance.get_data(latitude, longitude, start_date, end_date, **kwargs)
        
        if raw_df is None or raw_df.empty:
            self.logger.error("Failed to fetch data from provider")
            return None
        
        # Process data
        processor_instance = self.processors[processor]
        processed_df = processor_instance.process_data(raw_df, validate=validate, clean=clean)
        
        if processed_df is None or processed_df.empty:
            self.logger.error("Failed to process data")
            return None
        
        # Cache the processed data
        if use_cache:
            self._save_to_cache(processed_df, latitude, longitude, start_date, end_date, provider, processor)
        
        self.logger.info(f"Successfully retrieved and processed weather data: shape {processed_df.shape}")
        return processed_df
    
    def get_data_for_year(self,
                         latitude: float,
                         longitude: float, 
                         year: int,
                         provider: Optional[str] = None,
                         processor: Optional[str] = None,
                         **kwargs) -> Optional[pd.DataFrame]:
        """
        Convenience method to get weather data for a full year.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            year: Year to fetch data for
            provider: Provider name (default: self.default_provider)
            processor: Processor name (default: self.default_processor)
            **kwargs: Additional arguments passed to get_data
            
        Returns:
            Processed weather DataFrame or None if failed
        """
        start_date = f"{year}0101"
        end_date = f"{year}1231"
        
        return self.get_data(latitude, longitude, start_date, end_date, 
                           provider=provider, processor=processor, **kwargs)
    
    def get_data_for_years(self,
                          latitude: float,
                          longitude: float,
                          start_year: int,
                          end_year: int,
                          provider: Optional[str] = None,
                          processor: Optional[str] = None,
                          **kwargs) -> Optional[pd.DataFrame]:
        """
        Get weather data for multiple years and concatenate.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            start_year: Starting year (inclusive)
            end_year: Ending year (inclusive)
            provider: Provider name (default: self.default_provider)
            processor: Processor name (default: self.default_processor)
            **kwargs: Additional arguments passed to get_data
            
        Returns:
            Concatenated weather DataFrame or None if failed
        """
        year_dataframes = []
        failed_years = []
        
        for year in range(start_year, end_year + 1):
            self.logger.info(f"Fetching data for year {year}")
            year_df = self.get_data_for_year(latitude, longitude, year, 
                                           provider=provider, processor=processor, **kwargs)
            
            if year_df is not None and not year_df.empty:
                year_dataframes.append(year_df)
            else:
                failed_years.append(year)
                self.logger.warning(f"Failed to get data for year {year}")
        
        if not year_dataframes:
            self.logger.error("No data retrieved for any year")
            return None
        
        # Concatenate all years
        combined_df = pd.concat(year_dataframes, ignore_index=False)
        combined_df = combined_df.sort_index()
        
        if failed_years:
            self.logger.warning(f"Failed to retrieve data for years: {failed_years}")
        
        self.logger.info(f"Successfully combined data for {len(year_dataframes)} years. "
                        f"Total shape: {combined_df.shape}")
        
        return combined_df
    
    def _get_cache_filename(self, latitude: float, longitude: float, 
                           start_date: str, end_date: str,
                           provider: str, processor: str) -> str:
        """Generate cache filename for the given parameters."""
        # Create a unique filename based on parameters
        lat_str = f"{latitude:.4f}".replace(".", "p").replace("-", "n")
        lon_str = f"{longitude:.4f}".replace(".", "p").replace("-", "n")
        
        filename = f"weather_{provider}_{processor}_lat{lat_str}_lon{lon_str}_{start_date}_{end_date}.parquet"
        return str(self.cache_dir / filename)
    
    def _save_to_cache(self, df: pd.DataFrame, latitude: float, longitude: float,
                      start_date: str, end_date: str, provider: str, processor: str):
        """Save DataFrame to cache."""
        try:
            cache_file = self._get_cache_filename(latitude, longitude, start_date, end_date, provider, processor)
            
            # Save as parquet for efficient storage
            df.to_parquet(cache_file)
            
            # Also save metadata
            metadata = {
                'latitude': latitude,
                'longitude': longitude,
                'start_date': start_date,
                'end_date': end_date,
                'provider': provider,
                'processor': processor,
                'created_at': datetime.now().isoformat(),
                'shape': df.shape,
                'columns': list(df.columns)
            }
            
            metadata_file = cache_file.replace('.parquet', '.json')
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"Saved data to cache: {cache_file}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save data to cache: {e}")
    
    def _load_from_cache(self, latitude: float, longitude: float,
                        start_date: str, end_date: str, provider: str, processor: str) -> Optional[pd.DataFrame]:
        """Load DataFrame from cache if available."""
        try:
            cache_file = self._get_cache_filename(latitude, longitude, start_date, end_date, provider, processor)
            
            if not os.path.exists(cache_file):
                return None
            
            # Load DataFrame
            df = pd.read_parquet(cache_file)
            
            # Validate metadata if available
            metadata_file = cache_file.replace('.parquet', '.json')
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Basic validation
                if (metadata.get('latitude') != latitude or 
                    metadata.get('longitude') != longitude or
                    metadata.get('provider') != provider or
                    metadata.get('processor') != processor):
                    self.logger.warning("Cache metadata mismatch, ignoring cached data")
                    return None
            
            self.logger.info(f"Loaded data from cache: {cache_file}")
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to load data from cache: {e}")
            return None
    
    def clear_cache(self, pattern: Optional[str] = None):
        """
        Clear cached weather data.
        
        Args:
            pattern: Optional pattern to match filenames (e.g., 'nasa_power_*')
                    If None, clears all cache files
        """
        try:
            cache_files = list(self.cache_dir.glob(pattern or "weather_*.parquet"))
            metadata_files = list(self.cache_dir.glob(pattern or "weather_*.json"))
            
            for file in cache_files + metadata_files:
                file.unlink()
            
            self.logger.info(f"Cleared {len(cache_files)} cache files")
            
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cached data."""
        cache_files = list(self.cache_dir.glob("weather_*.parquet"))
        
        cache_info = {
            'cache_dir': str(self.cache_dir),
            'total_files': len(cache_files),
            'total_size_mb': sum(f.stat().st_size for f in cache_files) / (1024 * 1024),
            'files': []
        }
        
        for cache_file in cache_files:
            metadata_file = cache_file.with_suffix('.json')
            file_info = {
                'filename': cache_file.name,
                'size_mb': cache_file.stat().st_size / (1024 * 1024),
                'modified': datetime.fromtimestamp(cache_file.stat().st_mtime).isoformat()
            }
            
            # Add metadata if available
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    file_info['metadata'] = metadata
                except Exception as e:
                    pass
            
            cache_info['files'].append(file_info)
        
        return cache_info


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Initialize manager
    manager = WeatherDataManager()
    
    # Test with Wageningen, NL coordinates
    lat = 51.97
    lon = 5.66
    
    # Get data for a small date range
    df = manager.get_data(lat, lon, "20220101", "20220107")
    
    if df is not None:
        logger.info(f"Retrieved weather data: {df.shape}")
        logger.info(f"Columns: {df.columns.tolist()}")
        logger.info("\nFirst few rows:")
        logger.info(df.head())
        
        # Test cache info
        cache_info = manager.get_cache_info()
        logger.info(f"\nCache info: {cache_info['total_files']} files, {cache_info['total_size_mb']:.2f} MB")
    else:
        logger.error("Failed to retrieve weather data") 