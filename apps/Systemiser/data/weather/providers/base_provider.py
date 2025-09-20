"""
Base Weather Data Provider

Abstract base class defining the interface for all weather data providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
import pandas as pd
from datetime import datetime
import logging

# Use Systemiser logger
try:
    from Systemiser.utils.logger import setup_logging
    logger = setup_logging("WeatherProvider", level=logging.INFO)
except ImportError:
    logger = logging.getLogger("WeatherProvider_Fallback")
    logger.warning("Could not import Systemiser logger, using fallback.")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


class BaseWeatherProvider(ABC):
    """
    Abstract base class for weather data providers.
    
    All weather data providers must implement the abstract methods
    to ensure consistent interface across different data sources.
    """
    
    def __init__(self, name: str):
        """
        Initialize the weather provider.
        
        Args:
            name: Human-readable name of the provider
        """
        self.name = name
        self.logger = logger
        self.logger.info(f"Initialized {self.name} weather provider")
    
    @abstractmethod
    def fetch_raw_data(self, latitude: float, longitude: float, 
                      start_date: str, end_date: str, 
                      **kwargs) -> Optional[Dict[str, Any]]:
        """
        Fetch raw weather data from the provider.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate  
            start_date: Start date in provider-specific format
            end_date: End date in provider-specific format
            **kwargs: Provider-specific parameters
            
        Returns:
            Raw data dictionary or None if fetch failed
        """
        pass
    
    @abstractmethod
    def process_raw_data(self, raw_data: Dict[str, Any]) -> pd.DataFrame:
        """
        Process raw data into standardized DataFrame format.
        
        Args:
            raw_data: Raw data from fetch_raw_data
            
        Returns:
            Processed DataFrame with standardized columns
        """
        pass
    
    @abstractmethod
    def get_available_parameters(self) -> Dict[str, str]:
        """
        Get available weather parameters from this provider.
        
        Returns:
            Dictionary mapping provider parameter names to standard names
        """
        pass
    
    @abstractmethod
    def validate_location(self, latitude: float, longitude: float) -> bool:
        """
        Validate if the location is supported by this provider.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            True if location is supported, False otherwise
        """
        pass
    
    @abstractmethod
    def validate_date_range(self, start_date: str, end_date: str) -> bool:
        """
        Validate if the date range is supported by this provider.
        
        Args:
            start_date: Start date string
            end_date: End date string
            
        Returns:
            True if date range is supported, False otherwise
        """
        pass
    
    def get_data(self, latitude: float, longitude: float,
                 start_date: str, end_date: str,
                 **kwargs) -> Optional[pd.DataFrame]:
        """
        Complete data retrieval workflow: fetch and process.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            start_date: Start date string
            end_date: End date string
            **kwargs: Provider-specific parameters
            
        Returns:
            Processed DataFrame or None if failed
        """
        self.logger.info(f"Getting weather data from {self.name} for "
                        f"lat={latitude}, lon={longitude}, "
                        f"dates={start_date} to {end_date}")
        
        # Validate inputs
        if not self.validate_location(latitude, longitude):
            self.logger.error(f"Invalid location for {self.name}: lat={latitude}, lon={longitude}")
            return None
            
        if not self.validate_date_range(start_date, end_date):
            self.logger.error(f"Invalid date range for {self.name}: {start_date} to {end_date}")
            return None
        
        # Fetch raw data
        raw_data = self.fetch_raw_data(latitude, longitude, start_date, end_date, **kwargs)
        if raw_data is None:
            self.logger.error(f"Failed to fetch raw data from {self.name}")
            return None
        
        # Process raw data
        try:
            processed_df = self.process_raw_data(raw_data)
            self.logger.info(f"Successfully processed data from {self.name}: shape {processed_df.shape}")
            return processed_df
        except Exception as e:
            self.logger.error(f"Failed to process raw data from {self.name}: {e}")
            return None
    
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about this provider.
        
        Returns:
            Dictionary with provider metadata
        """
        return {
            'name': self.name,
            'parameters': self.get_available_parameters(),
            'class': self.__class__.__name__
        } 