"""
Standard Weather Data Processor

Standard implementation of BaseWeatherProcessor with validation and cleaning
based on physical bounds and typical meteorological data patterns.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
import logging

from .base_processor import BaseWeatherProcessor


class StandardWeatherProcessor(BaseWeatherProcessor):
    """
    Standard weather data processor with physical validation bounds.
    
    Validates and cleans weather data using reasonable physical limits
    and handles common data quality issues.
    """
    
    def __init__(self):
        """Initialize standard weather processor."""
        super().__init__("Standard Weather Processor")
        
        # Define validation bounds (reasonable physical limits)
        self._validation_bounds = {
            'temperature_celsius': (-50, 60),
            'precipitation_mm_hr': (0, 50),  # Cap at 50 mm/hr
            'solar_radiation_wm2': (0, 1500),
            'wind_speed_m_s': (0, 70),
            'relative_humidity_percent': (0, 100)
        }
        
        # Parameters that must be non-negative
        self._non_negative_params = {
            'precipitation_mm_hr', 
            'solar_radiation_wm2', 
            'wind_speed_m_s',
            'relative_humidity_percent'
        }
        
        # Parameters with specific upper bounds
        self._bounded_params = {
            'relative_humidity_percent': 100,
            'precipitation_mm_hr': 50  # Extreme rainfall cap
        }
    
    def get_validation_bounds(self) -> Dict[str, Tuple[float, float]]:
        """Get validation bounds for each parameter."""
        return self._validation_bounds.copy()
    
    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate weather data DataFrame against physical bounds.
        
        Args:
            df: Input DataFrame to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        is_valid = True
        
        if df.empty:
            issues.append("DataFrame is empty")
            return False, issues
        
        # Check for required columns
        required_columns = list(self._validation_bounds.keys())
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            issues.append(f"Missing required columns: {missing_columns}")
            is_valid = False
        
        # Check datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            issues.append("Index is not a DatetimeIndex")
            is_valid = False
        
        # Validate each parameter
        for col, (min_val, max_val) in self._validation_bounds.items():
            if col not in df.columns:
                continue
                
            # Convert to numeric, count non-numeric values
            original_dtype = df[col].dtype
            numeric_series = pd.to_numeric(df[col], errors='coerce')
            non_numeric_count = numeric_series.isna().sum() - df[col].isna().sum()
            
            if non_numeric_count > 0:
                issues.append(f"Found {non_numeric_count} non-numeric values in {col}")
            
            # Check bounds for valid numeric data
            valid_data = numeric_series.dropna()
            if len(valid_data) == 0:
                issues.append(f"No valid numeric data found in {col}")
                is_valid = False
                continue
            
            # Check minimum bound
            below_min = (valid_data < min_val).sum()
            if below_min > 0:
                issues.append(f"Found {below_min} values below minimum ({min_val}) in {col}")
            
            # Check maximum bound  
            above_max = (valid_data > max_val).sum()
            if above_max > 0:
                issues.append(f"Found {above_max} values above maximum ({max_val}) in {col}")
            
            # Check for excessive missing data
            missing_pct = (df[col].isna().sum() / len(df)) * 100
            if missing_pct > 50:
                issues.append(f"Excessive missing data in {col}: {missing_pct:.1f}%")
                is_valid = False
        
        # Check temporal consistency
        if isinstance(df.index, pd.DatetimeIndex):
            # Check for duplicated timestamps
            duplicated_count = df.index.duplicated().sum()
            if duplicated_count > 0:
                issues.append(f"Found {duplicated_count} duplicated timestamps")
                is_valid = False
            
            # Check for large gaps in time series
            if len(df) > 1:
                time_diffs = df.index.to_series().diff().dropna()
                median_diff = time_diffs.median()
                large_gaps = (time_diffs > median_diff * 5).sum()
                if large_gaps > 0:
                    issues.append(f"Found {large_gaps} large gaps in time series (>5x median interval)")
        
        return is_valid, issues
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and correct weather data.
        
        Args:
            df: Input DataFrame to clean
            
        Returns:
            Cleaned DataFrame
        """
        self.logger.info(f"Starting data cleaning for DataFrame with shape: {df.shape}")
        df_cleaned = df.copy()
        
        # Clean each parameter
        for col, (min_val, max_val) in self._validation_bounds.items():
            if col not in df_cleaned.columns:
                self.logger.warning(f"Cleaning skipped for missing column: {col}")
                continue
            
            initial_shape = df_cleaned.shape
            
            # Convert to numeric, coercing errors to NaN
            df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce')
            initial_nan_count = df_cleaned[col].isna().sum()
            
            # Apply minimum bound
            if min_val is not None:
                below_min_mask = df_cleaned[col] < min_val
                below_min_count = below_min_mask.sum()
                if below_min_count > 0:
                    self.logger.warning(f"Found {below_min_count} values below minimum ({min_val}) "
                                      f"for {col}. Setting to {min_val}")
                    df_cleaned.loc[below_min_mask, col] = min_val
            
            # Apply maximum bound
            if max_val is not None:
                above_max_mask = df_cleaned[col] > max_val
                above_max_count = above_max_mask.sum()
                if above_max_count > 0:
                    self.logger.warning(f"Found {above_max_count} values above maximum ({max_val}) "
                                      f"for {col}. Capping at {max_val}")
                    
                    # Special logging for precipitation capping
                    if col == 'precipitation_mm_hr':
                        original_max = df.loc[above_max_mask, col].max()
                        self.logger.info(f"Original max precipitation before capping: {original_max:.2f} mm/hr")
                    
                    df_cleaned.loc[above_max_mask, col] = max_val
            
            # Check for new NaNs introduced by coercion
            final_nan_count = df_cleaned[col].isna().sum()
            if final_nan_count > initial_nan_count:
                new_nans = final_nan_count - initial_nan_count
                self.logger.warning(f"Introduced {new_nans} NaN(s) in {col} due to non-numeric values")
        
        # Handle duplicated timestamps
        if df_cleaned.index.duplicated().any():
            self.logger.warning("Found duplicated timestamps. Keeping first occurrence")
            df_cleaned = df_cleaned[~df_cleaned.index.duplicated(keep='first')]
        
        # Sort by datetime index
        df_cleaned = df_cleaned.sort_index()
        
        # Optional: Interpolate small gaps in critical parameters
        # (Uncomment if desired)
        # critical_params = ['temperature_celsius', 'solar_radiation_wm2']
        # for param in critical_params:
        #     if param in df_cleaned.columns:
        #         df_cleaned[param] = df_cleaned[param].interpolate(method='time', limit=3)
        
        self.logger.info(f"Data cleaning completed. Output shape: {df_cleaned.shape}")
        return df_cleaned
    
    def process_precipitation_correction(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply precipitation-specific corrections.
        
        NASA POWER precipitation data is often reported as daily totals
        repeated for each hour. This method can correct for that pattern.
        
        Args:
            df: DataFrame with precipitation data
            
        Returns:
            DataFrame with corrected precipitation
        """
        if 'precipitation_mm_hr' not in df.columns:
            return df
        
        df_corrected = df.copy()
        
        # Check if precipitation values repeat within each day (NASA POWER pattern)
        daily_precip = df_corrected['precipitation_mm_hr'].resample('D').first()
        
        # If there's a pattern of repeated daily values, create true hourly distribution
        # This is a sophisticated correction that could be implemented based on your needs
        # For now, we'll just log the pattern detection
        total_daily_sum = daily_precip.sum()
        total_hourly_sum = df_corrected['precipitation_mm_hr'].sum()
        
        if total_hourly_sum > total_daily_sum * 20:  # Heuristic for detecting daily repeats
            self.logger.info("Detected potential daily precipitation repeats in hourly data")
            # Could implement correction here: df_corrected['precipitation_mm_hr'] /= 24
        
        return df_corrected
    
    def get_quality_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate data quality metrics.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            Dictionary with quality metrics
        """
        if df.empty:
            return {'status': 'empty'}
        
        metrics = {}
        
        for col in df.columns:
            if col in self._validation_bounds:
                min_val, max_val = self._validation_bounds[col]
                valid_data = pd.to_numeric(df[col], errors='coerce').dropna()
                
                if len(valid_data) > 0:
                    metrics[col] = {
                        'completeness_pct': ((len(df) - df[col].isna().sum()) / len(df)) * 100,
                        'within_bounds_pct': ((valid_data >= min_val) & (valid_data <= max_val)).mean() * 100,
                        'outliers_count': ((valid_data < min_val) | (valid_data > max_val)).sum(),
                        'mean': valid_data.mean(),
                        'std': valid_data.std(),
                        'min': valid_data.min(),
                        'max': valid_data.max()
                    }
                else:
                    metrics[col] = {'status': 'no_valid_data'}
        
        return metrics


# Example usage for testing
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Create test data
    dates = pd.date_range('2022-01-01', '2022-01-02', freq='H')
    test_data = pd.DataFrame({
        'temperature_celsius': np.random.normal(10, 5, len(dates)),
        'precipitation_mm_hr': np.random.exponential(0.5, len(dates)),
        'solar_radiation_wm2': np.random.uniform(0, 800, len(dates)),
        'wind_speed_m_s': np.random.uniform(0, 15, len(dates)),
        'relative_humidity_percent': np.random.uniform(30, 90, len(dates))
    }, index=dates)
    
    # Add some outliers for testing
    test_data.loc[test_data.index[0], 'temperature_celsius'] = -100  # Too cold
    test_data.loc[test_data.index[1], 'precipitation_mm_hr'] = 100   # Too much rain
    test_data.loc[test_data.index[2], 'solar_radiation_wm2'] = 2000  # Too much solar
    
    processor = StandardWeatherProcessor()
    
    # Test validation
    is_valid, issues = processor.validate_data(test_data)
    print(f"Validation result: {is_valid}")
    print(f"Issues found: {issues}")
    
    # Test cleaning
    cleaned_data = processor.clean_data(test_data)
    print(f"\nCleaned data shape: {cleaned_data.shape}")
    print("\nCleaned data sample:")
    print(cleaned_data.head())
    
    # Test quality metrics
    quality = processor.get_quality_metrics(cleaned_data)
    print(f"\nQuality metrics: {quality}") 