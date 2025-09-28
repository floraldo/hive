"""
Base Weather Data Processor

Abstract base class for weather data processing and validation.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
from hive_logging import get_logger

# Use Systemiser logger
try:
    from Systemiser.utils.logger import setup_logging
    logger = setup_logging("WeatherProcessor", level=logging.INFO)
except ImportError:
    logger = get_logger("WeatherProcessor_Fallback")
    logger.warning("Could not import Systemiser logger, using fallback.")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


class BaseWeatherProcessor(ABC):
    """
    Abstract base class for weather data processors.
    
    Processors handle validation, cleaning, and transformation of weather data
    to prepare it for use in energy system simulations.
    """
    
    def __init__(self, name: str):
        """
        Initialize the weather processor.
        
        Args:
            name: Human-readable name of the processor
        """
        self.name = name
        self.logger = logger
        self.logger.info(f"Initialized {self.name} weather processor")
    
    @abstractmethod
    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate weather data DataFrame.
        
        Args:
            df: Input DataFrame to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        pass
    
    @abstractmethod
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and correct weather data.
        
        Args:
            df: Input DataFrame to clean
            
        Returns:
            Cleaned DataFrame
        """
        pass
    
    @abstractmethod
    def get_validation_bounds(self) -> Dict[str, Tuple[float, float]]:
        """
        Get validation bounds for each parameter.
        
        Returns:
            Dictionary mapping parameter names to (min_value, max_value) tuples
        """
        pass
    
    def process_data(self, df: pd.DataFrame, 
                    validate: bool = True, 
                    clean: bool = True) -> Optional[pd.DataFrame]:
        """
        Complete data processing workflow: validate and clean.
        
        Args:
            df: Input DataFrame to process
            validate: Whether to perform validation
            clean: Whether to perform cleaning
            
        Returns:
            Processed DataFrame or None if validation fails
        """
        self.logger.info(f"Processing weather data with {self.name}")
        self.logger.info(f"Input DataFrame shape: {df.shape}")
        
        if df.empty:
            self.logger.warning("Empty DataFrame provided for processing")
            return df
        
        processed_df = df.copy()
        
        # Validation step
        if validate:
            is_valid, issues = self.validate_data(processed_df)
            if not is_valid:
                self.logger.error(f"Data validation failed: {issues}")
                return None
            elif issues:
                self.logger.warning(f"Data validation warnings: {issues}")
        
        # Cleaning step
        if clean:
            try:
                processed_df = self.clean_data(processed_df)
                self.logger.info(f"Data cleaned successfully. Output shape: {processed_df.shape}")
            except Exception as e:
                self.logger.error(f"Data cleaning failed: {e}")
                return None
        
        return processed_df
    
    def get_data_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get summary statistics for weather data.
        
        Args:
            df: DataFrame to summarize
            
        Returns:
            Dictionary with summary statistics
        """
        if df.empty:
            return {'status': 'empty', 'shape': (0, 0)}
        
        summary = {
            'status': 'ok',
            'shape': df.shape,
            'date_range': {
                'start': df.index.min(),
                'end': df.index.max(),
                'duration_days': (df.index.max() - df.index.min()).days
            },
            'parameters': list(df.columns),
            'missing_data': {col: df[col].isna().sum() for col in df.columns},
            'basic_stats': df.describe().to_dict()
        }
        
        return summary 