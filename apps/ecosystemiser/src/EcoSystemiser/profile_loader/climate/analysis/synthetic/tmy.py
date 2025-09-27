"""
Comprehensive Typical Meteorological Year (TMY) module.

Implements complete TMY3 methodology for selecting representative months
from historical weather data for building energy modeling. Consolidates
generation, metrics, and selection algorithms into a single module.

This module combines functionality from:
- TMY generation and orchestration
- Statistical metrics and analysis
- Advanced month selection with quality assessment
"""

import xarray as xr
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Literal
from EcoSystemiser.hive_logging_adapter import get_logger
from enum import Enum
from dataclasses import dataclass
from scipy import stats

logger = get_logger(__name__)

class TMYMethod(Enum):
    """TMY generation methods"""
    TMY3 = "tmy3"           # Standard TMY3 methodology (NREL)
    SIMPLIFIED = "simplified" # Simplified selection based on temperature only
    CUSTOM = "custom"        # Custom weighting factors

@dataclass
class MonthQuality:
    """Quality assessment for a selected month"""
    completeness: float  # Data completeness (0-1)
    representativeness: float  # How well it represents long-term (0-1)
    extremes_score: float  # Score for extreme events handling
    continuity_score: float  # Month boundary continuity
    overall_score: float  # Combined quality score

class TMYMetrics:
    """Statistical metrics for TMY generation"""
    
    def calculate_monthly_statistics(
        self, 
        data: xr.Dataset, 
        month: int
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate long-term monthly statistics for TMY selection.
        
        Args:
            data: Multi-year climate dataset
            month: Month number (1-12)
            
        Returns:
            Dictionary of statistics by variable
        """
        # Filter to specified month across all years
        time_values = pd.to_datetime(data.time.values)
        month_mask = time_values.month == month
        month_data = data.isel(time=month_mask)
        
        if len(month_data.time) == 0:
            raise ValueError(f"No data found for month {month}")
        
        stats_dict = {}
        
        for var_name in month_data.data_vars:
            var_data = month_data[var_name].values.flatten()
            
            # Remove NaN values
            valid_data = var_data[~np.isnan(var_data)]
            
            if len(valid_data) < 10:  # Insufficient data
                logger.warning(f"Insufficient data for {var_name} in month {month}")
                continue
            
            # Calculate comprehensive statistics
            stats_dict[var_name] = {
                'mean': float(np.mean(valid_data)),
                'std': float(np.std(valid_data)),
                'min': float(np.min(valid_data)),
                'max': float(np.max(valid_data)),
                'median': float(np.median(valid_data)),
                'p25': float(np.percentile(valid_data, 25)),
                'p75': float(np.percentile(valid_data, 75)),
                'p05': float(np.percentile(valid_data, 5)),
                'p95': float(np.percentile(valid_data, 95)),
                'skewness': float(stats.skew(valid_data)),
                'kurtosis': float(stats.kurtosis(valid_data)),
                'count': len(valid_data)
            }
            
            # Add percentile array for CDF comparison
            stats_dict[var_name]['percentiles'] = np.percentile(
                valid_data, np.linspace(0, 100, 101)
            )
        
        return stats_dict
    
    def calculate_fs_statistic(
        self, 
        candidate_data: np.ndarray, 
        long_term_stats: Dict[str, float]
    ) -> float:
        """
        Calculate Finkelstein-Schafer (FS) statistic for TMY selection.
        
        The FS statistic compares the cumulative distribution functions
        of candidate year data with long-term statistics.
        
        Args:
            candidate_data: Data values for candidate year
            long_term_stats: Long-term statistics dictionary
            
        Returns:
            FS statistic (lower is better)
        """
        # Remove NaN values
        valid_data = candidate_data[~np.isnan(candidate_data)]
        
        if len(valid_data) < 5:
            return 999.0  # Very poor score for insufficient data
        
        # Get long-term percentiles
        if 'percentiles' not in long_term_stats:
            # Fallback: create approximate percentiles from basic stats
            lt_mean = long_term_stats['mean']
            lt_std = long_term_stats['std']
            
            # Approximate percentiles assuming normal distribution
            percentiles = []
            for p in np.linspace(0, 100, 101):
                z_score = stats.norm.ppf(p / 100.0)
                value = lt_mean + z_score * lt_std
                percentiles.append(value)
            
            long_term_percentiles = np.array(percentiles)
        else:
            long_term_percentiles = long_term_stats['percentiles']
        
        # Calculate candidate percentiles
        candidate_percentiles = np.percentile(valid_data, np.linspace(0, 100, 101))
        
        # Calculate FS statistic as mean absolute difference
        fs_statistic = np.mean(np.abs(
            candidate_percentiles - long_term_percentiles
        ))
        
        # Normalize by standard deviation to make comparable across variables
        if long_term_stats['std'] > 0:
            fs_statistic = fs_statistic / long_term_stats['std']
        
        return float(fs_statistic)
    
    def calculate_persistence_metrics(
        self, 
        data: np.ndarray,
        threshold_percentiles: List[float] = [10, 90]
    ) -> Dict[str, float]:
        """
        Calculate persistence metrics for extreme conditions.
        
        Important for building energy modeling - measures how long
        extreme conditions persist.
        
        Args:
            data: Time series data
            threshold_percentiles: Percentiles to use for extreme thresholds
            
        Returns:
            Dictionary of persistence metrics
        """
        valid_data = data[~np.isnan(data)]
        
        if len(valid_data) < 24:
            return {'max_hot_hours': 0, 'max_cold_hours': 0}
        
        # Calculate thresholds
        thresholds = np.percentile(valid_data, threshold_percentiles)
        low_threshold, high_threshold = thresholds[0], thresholds[1]
        
        # Find extreme periods
        cold_mask = valid_data <= low_threshold
        hot_mask = valid_data >= high_threshold
        
        # Calculate maximum consecutive periods
        max_cold_hours = self._max_consecutive(cold_mask)
        max_hot_hours = self._max_consecutive(hot_mask)
        
        return {
            'max_cold_hours': max_cold_hours,
            'max_hot_hours': max_hot_hours,
            'cold_threshold': float(low_threshold),
            'hot_threshold': float(high_threshold),
            'cold_frequency': float(np.sum(cold_mask) / len(valid_data)),
            'hot_frequency': float(np.sum(hot_mask) / len(valid_data))
        }
    
    def _max_consecutive(self, boolean_array: np.ndarray) -> int:
        """Find maximum consecutive True values in boolean array"""
        if len(boolean_array) == 0:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for value in boolean_array:
            if value:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def calculate_diurnal_patterns(
        self, 
        data: xr.Dataset, 
        variable: str
    ) -> Dict[str, np.ndarray]:
        """
        Calculate average diurnal patterns for a variable.
        
        Important for understanding daily cycles in TMY data.
        
        Args:
            data: Climate dataset with hourly data
            variable: Variable name to analyze
            
        Returns:
            Dictionary with hourly averages and statistics
        """
        if variable not in data.data_vars:
            raise ValueError(f"Variable {variable} not found in dataset")
        
        var_data = data[variable]
        time_values = pd.to_datetime(data.time.values)
        
        # Group by hour of day
        hourly_data = {}
        for hour in range(24):
            hour_mask = time_values.hour == hour
            if np.any(hour_mask):
                hour_values = var_data.isel(time=hour_mask).values
                hour_values = hour_values[~np.isnan(hour_values)]
                hourly_data[hour] = hour_values
        
        # Calculate statistics for each hour
        hourly_means = np.full(24, np.nan)
        hourly_stds = np.full(24, np.nan)
        hourly_mins = np.full(24, np.nan)
        hourly_maxs = np.full(24, np.nan)
        
        for hour in range(24):
            if hour in hourly_data and len(hourly_data[hour]) > 0:
                values = hourly_data[hour]
                hourly_means[hour] = np.mean(values)
                hourly_stds[hour] = np.std(values)
                hourly_mins[hour] = np.min(values)
                hourly_maxs[hour] = np.max(values)
        
        return {
            'mean': hourly_means,
            'std': hourly_stds,
            'min': hourly_mins,
            'max': hourly_maxs,
            'hours': np.arange(24)
        }
    
    def calculate_variable_correlations(
        self, 
        data: xr.Dataset,
        variables: Optional[List[str]] = None
    ) -> np.ndarray:
        """
        Calculate correlation matrix between variables.
        
        Important for understanding relationships preserved in TMY.
        
        Args:
            data: Climate dataset
            variables: Variables to include (default: all)
            
        Returns:
            Correlation matrix as numpy array
        """
        if variables is None:
            variables = list(data.data_vars)
        
        # Create data matrix
        data_matrix = []
        valid_vars = []
        
        for var in variables:
            if var in data.data_vars:
                var_data = data[var].values.flatten()
                if not np.all(np.isnan(var_data)):
                    data_matrix.append(var_data)
                    valid_vars.append(var)
        
        if len(data_matrix) < 2:
            return np.array([[1.0]])
        
        data_matrix = np.array(data_matrix)
        
        # Calculate correlation matrix (handling NaN values)
        correlation_matrix = np.corrcoef(data_matrix)
        
        # Replace NaN with 0 (no correlation)
        correlation_matrix = np.nan_to_num(correlation_matrix, nan=0.0)
        
        return correlation_matrix

class TMYSelector:
    """Advanced TMY month selection with quality assessment"""
    
    def __init__(self):
        """Initialize TMY selector"""
        self.quality_weights = {
            'completeness': 0.3,
            'representativeness': 0.4,
            'extremes': 0.2,
            'continuity': 0.1
        }
    
    def select_optimal_months(
        self,
        data: xr.Dataset,
        selection_criteria: Dict,
        building_type: Optional[Literal['residential', 'commercial', 'industrial']] = None
    ) -> Dict[int, Tuple[int, MonthQuality]]:
        """
        Select optimal months for TMY with quality assessment.
        
        Args:
            data: Multi-year historical dataset
            selection_criteria: Criteria for month selection
            building_type: Building type for optimization (optional)
            
        Returns:
            Dictionary mapping month -> (selected_year, quality)
        """
        logger.info("Selecting optimal months with quality assessment")
        
        selected_months = {}
        
        for month in range(1, 13):
            year, quality = self._select_month_with_quality(
                data, month, selection_criteria, building_type
            )
            selected_months[month] = (year, quality)
            
            logger.debug(f"Month {month}: Year {year}, Quality {quality.overall_score:.3f}")
        
        # Post-process for continuity optimization
        selected_months = self._optimize_continuity(data, selected_months)
        
        return selected_months
    
    def _select_month_with_quality(
        self,
        data: xr.Dataset,
        month: int,
        criteria: Dict,
        building_type: Optional[str]
    ) -> Tuple[int, MonthQuality]:
        """Select month with comprehensive quality assessment"""
        
        # Get candidate years for this month
        time_values = pd.to_datetime(data.time.values)
        month_mask = time_values.month == month
        month_data = data.isel(time=month_mask)
        
        years = pd.to_datetime(month_data.time.values).year.unique()
        
        if len(years) == 0:
            raise ValueError(f"No data found for month {month}")
        
        if len(years) == 1:
            # Only one year available
            quality = self._assess_month_quality(
                month_data, data, month, criteria
            )
            return years[0], quality
        
        # Evaluate each candidate year
        best_year = None
        best_quality = None
        best_score = -1
        
        for year in years:
            year_mask = pd.to_datetime(month_data.time.values).year == year
            year_data = month_data.isel(time=year_mask)
            
            if len(year_data.time) < 24 * 28:  # Less than 28 days
                continue
            
            # Assess quality
            quality = self._assess_month_quality(
                year_data, data, month, criteria
            )
            
            # Apply building-type specific weighting
            adjusted_score = self._apply_building_weights(
                quality, building_type
            )
            
            if adjusted_score > best_score:
                best_year = year
                best_quality = quality
                best_score = adjusted_score
        
        if best_year is None:
            # Fallback to first available year
            best_year = years[0]
            year_mask = pd.to_datetime(month_data.time.values).year == best_year
            year_data = month_data.isel(time=year_mask)
            best_quality = self._assess_month_quality(
                year_data, data, month, criteria
            )
        
        return best_year, best_quality
    
    def _assess_month_quality(
        self,
        month_data: xr.Dataset,
        full_data: xr.Dataset,
        month: int,
        criteria: Dict
    ) -> MonthQuality:
        """Comprehensive quality assessment for a month's data"""
        
        # 1. Data completeness
        completeness = self._calculate_completeness(month_data)
        
        # 2. Representativeness (how well it matches long-term patterns)
        representativeness = self._calculate_representativeness(
            month_data, full_data, month
        )
        
        # 3. Extreme events handling
        extremes_score = self._calculate_extremes_score(
            month_data, full_data, month
        )
        
        # 4. Boundary continuity (for smooth transitions)
        continuity_score = self._calculate_continuity_score(month_data)
        
        # Calculate overall quality score
        overall_score = (
            self.quality_weights['completeness'] * completeness +
            self.quality_weights['representativeness'] * representativeness +
            self.quality_weights['extremes'] * extremes_score +
            self.quality_weights['continuity'] * continuity_score
        )
        
        return MonthQuality(
            completeness=completeness,
            representativeness=representativeness,
            extremes_score=extremes_score,
            continuity_score=continuity_score,
            overall_score=overall_score
        )
    
    def _calculate_completeness(self, data: xr.Dataset) -> float:
        """Calculate data completeness score"""
        total_points = 0
        valid_points = 0
        
        for var in data.data_vars:
            var_data = data[var].values.flatten()
            total_points += len(var_data)
            valid_points += np.sum(~np.isnan(var_data))
        
        if total_points == 0:
            return 0.0
        
        return valid_points / total_points
    
    def _calculate_representativeness(
        self, 
        month_data: xr.Dataset, 
        full_data: xr.Dataset, 
        month: int
    ) -> float:
        """Calculate how representative the month is of long-term patterns"""
        
        # Get long-term monthly statistics
        time_values = pd.to_datetime(full_data.time.values)
        month_mask = time_values.month == month
        long_term_month = full_data.isel(time=month_mask)
        
        representativeness_scores = []
        
        for var in month_data.data_vars:
            if var not in long_term_month.data_vars:
                continue
            
            # Compare distributions using KS test
            month_values = month_data[var].values.flatten()
            month_values = month_values[~np.isnan(month_values)]
            
            lt_values = long_term_month[var].values.flatten()
            lt_values = lt_values[~np.isnan(lt_values)]
            
            if len(month_values) < 10 or len(lt_values) < 10:
                continue
            
            # Simple comparison of key statistics
            month_mean = np.mean(month_values)
            lt_mean = np.mean(lt_values)
            lt_std = np.std(lt_values)
            
            if lt_std > 0:
                # Normalized difference in means
                mean_diff = abs(month_mean - lt_mean) / lt_std
                # Convert to score (1 = perfect, 0 = very different)
                score = np.exp(-mean_diff)
                representativeness_scores.append(score)
        
        if not representativeness_scores:
            return 0.5  # Neutral score
        
        return np.mean(representativeness_scores)
    
    def _calculate_extremes_score(
        self,
        month_data: xr.Dataset,
        full_data: xr.Dataset,
        month: int
    ) -> float:
        """Score based on appropriate handling of extreme events"""
        
        # Focus on temperature extremes as most critical for buildings
        if 'temp_air' not in month_data.data_vars:
            return 0.5  # Neutral score
        
        month_temps = month_data['temp_air'].values.flatten()
        month_temps = month_temps[~np.isnan(month_temps)]
        
        if len(month_temps) < 24:
            return 0.0
        
        # Get long-term temperature statistics for this month
        time_values = pd.to_datetime(full_data.time.values)
        month_mask = time_values.month == month
        lt_month_temps = full_data['temp_air'].isel(time=month_mask).values.flatten()
        lt_month_temps = lt_month_temps[~np.isnan(lt_month_temps)]
        
        if len(lt_month_temps) < 100:
            return 0.5
        
        # Calculate percentiles
        lt_p05 = np.percentile(lt_month_temps, 5)
        lt_p95 = np.percentile(lt_month_temps, 95)
        
        month_p05 = np.percentile(month_temps, 5)
        month_p95 = np.percentile(month_temps, 95)
        
        # Score based on how well extremes are represented
        lt_range = lt_p95 - lt_p05
        if lt_range == 0:
            return 1.0
        
        # Normalized differences in extreme percentiles
        low_diff = abs(month_p05 - lt_p05) / lt_range
        high_diff = abs(month_p95 - lt_p95) / lt_range
        
        # Convert to score
        extreme_score = np.exp(-(low_diff + high_diff))
        
        return extreme_score
    
    def _calculate_continuity_score(self, data: xr.Dataset) -> float:
        """Score based on smooth transitions at month boundaries"""
        
        if 'temp_air' not in data.data_vars:
            return 0.5
        
        temps = data['temp_air'].values.flatten()
        temps = temps[~np.isnan(temps)]
        
        if len(temps) < 48:  # Less than 2 days
            return 0.0
        
        # Calculate temperature gradients
        gradients = np.diff(temps)
        
        # Score based on smoothness (lower gradients = better)
        mean_gradient = np.mean(np.abs(gradients))
        
        # Normalize by typical daily temperature variation (~10degC)
        normalized_gradient = mean_gradient / 10.0
        
        # Convert to score (smoother = better)
        continuity_score = np.exp(-normalized_gradient)
        
        return continuity_score
    
    def _apply_building_weights(
        self, 
        quality: MonthQuality, 
        building_type: Optional[str]
    ) -> float:
        """Apply building-type specific weighting to quality scores"""
        
        if building_type is None:
            return quality.overall_score
        
        # Building-specific quality weights
        if building_type == 'residential':
            # Residential buildings care more about extremes
            weights = {
                'completeness': 0.2,
                'representativeness': 0.3,
                'extremes': 0.4,
                'continuity': 0.1
            }
        elif building_type == 'commercial':
            # Commercial buildings need consistent patterns
            weights = {
                'completeness': 0.3,
                'representativeness': 0.5,
                'extremes': 0.1,
                'continuity': 0.1
            }
        elif building_type == 'industrial':
            # Industrial needs complete, reliable data
            weights = {
                'completeness': 0.5,
                'representativeness': 0.3,
                'extremes': 0.1,
                'continuity': 0.1
            }
        else:
            weights = self.quality_weights
        
        # Recalculate score with building-specific weights
        adjusted_score = (
            weights['completeness'] * quality.completeness +
            weights['representativeness'] * quality.representativeness +
            weights['extremes'] * quality.extremes_score +
            weights['continuity'] * quality.continuity_score
        )
        
        return adjusted_score
    
    def _optimize_continuity(
        self,
        data: xr.Dataset,
        selected_months: Dict[int, Tuple[int, MonthQuality]]
    ) -> Dict[int, Tuple[int, MonthQuality]]:
        """Optimize month selections for better year-to-year continuity"""
        
        # For now, return as-is
        # Future enhancement: consider temperature/weather pattern continuity
        # between adjacent months from different years
        
        logger.debug("Continuity optimization not yet implemented")
        return selected_months

class TMYGenerator:
    """
    Generate Typical Meteorological Year datasets from historical data.
    
    Follows TMY3 methodology for selecting representative months based on
    long-term statistics and building energy modeling requirements.
    
    This consolidated class integrates:
    - TMY generation orchestration and methodology
    - Statistical metrics and analysis functions
    - Advanced month selection with quality assessment
    """
    
    def __init__(self, method: TMYMethod = TMYMethod.TMY3):
        """
        Initialize TMY generator.
        
        Args:
            method: TMY generation method to use
        """
        self.method = method
        self.metrics = TMYMetrics()
        self.selector = TMYSelector()
        
        # Standard TMY3 variable weights (NREL methodology)
        self.tmy3_weights = {
            'temp_air': 2.0,        # Primary variable
            'dewpoint': 1.0,
            'wind_speed': 1.0,
            'ghi': 2.0,             # Primary solar variable
            'dni': 1.0,
            'rel_humidity': 0.5,
            'pressure': 0.5,
            'precip': 0.5
        }
        
        # Critical months for building energy analysis
        self.critical_months = {
            'heating': [1, 2, 12],    # Winter months
            'cooling': [6, 7, 8],     # Summer months
            'shoulder': [3, 4, 5, 9, 10, 11]  # Spring/fall months
        }
    
    def generate(
        self,
        historical_data: xr.Dataset,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        target_year: int = 2010,
        weights: Optional[Dict[str, float]] = None,
        min_data_years: int = 10,
        building_type: Optional[Literal['residential', 'commercial', 'industrial']] = None,
        use_advanced_selection: bool = False
    ) -> Tuple[xr.Dataset, Dict]:
        """
        Generate TMY dataset from historical weather data.
        
        Args:
            historical_data: Multi-year historical climate dataset
            start_year: Start year for analysis period (default: data start)
            end_year: End year for analysis period (default: data end)
            target_year: Target year for TMY timestamps (default: 2010)
            weights: Custom variable weights (default: TMY3 standard)
            min_data_years: Minimum years of data required
            building_type: Building type for optimization (optional)
            use_advanced_selection: Use advanced selection with quality assessment
            
        Returns:
            Tuple of (TMY dataset, selection metadata)
            
        Raises:
            ValueError: If insufficient data or invalid parameters
        """
        logger.info(f"Generating TMY using {self.method.value} methodology")
        
        # Validate input data
        self._validate_input(historical_data, min_data_years)
        
        # Set analysis period
        if start_year is None:
            start_year = pd.to_datetime(historical_data.time.values[0]).year
        if end_year is None:
            end_year = pd.to_datetime(historical_data.time.values[-1]).year
            
        logger.info(f"Analysis period: {start_year}-{end_year}")
        
        # Filter to analysis period
        time_mask = (
            (pd.to_datetime(historical_data.time.values).year >= start_year) &
            (pd.to_datetime(historical_data.time.values).year <= end_year)
        )
        analysis_data = historical_data.isel(time=time_mask)
        
        # Use provided weights or defaults based on method
        if weights is None:
            weights = self._get_default_weights()
        
        # Generate TMY by month
        tmy_months = {}
        selection_metadata = {
            'method': self.method.value,
            'analysis_period': (start_year, end_year),
            'target_year': target_year,
            'weights': weights,
            'building_type': building_type,
            'use_advanced_selection': use_advanced_selection,
            'selected_months': {}
        }
        
        if use_advanced_selection:
            # Use advanced selection with quality assessment
            selection_criteria = {'weights': weights}
            selected_months = self.selector.select_optimal_months(
                analysis_data, selection_criteria, building_type
            )
            
            for month in range(1, 13):
                selected_year, quality = selected_months[month]
                
                # Extract month data
                month_data = self._extract_month_data(
                    analysis_data, selected_year, month, target_year
                )
                
                tmy_months[month] = month_data
                selection_metadata['selected_months'][month] = {
                    'selected_year': selected_year,
                    'quality': {
                        'completeness': quality.completeness,
                        'representativeness': quality.representativeness,
                        'extremes_score': quality.extremes_score,
                        'continuity_score': quality.continuity_score,
                        'overall_score': quality.overall_score
                    },
                    'data_points': len(month_data.time)
                }
                
                logger.info(f"Month {month}: Selected year {selected_year} (quality: {quality.overall_score:.3f})")
        else:
            # Use standard TMY3 methodology
            for month in range(1, 13):
                logger.info(f"Selecting representative data for month {month}")
                
                # Select best month
                selected_year, scores = self._select_month(
                    analysis_data, month, weights
                )
                
                # Extract month data
                month_data = self._extract_month_data(
                    analysis_data, selected_year, month, target_year
                )
                
                tmy_months[month] = month_data
                selection_metadata['selected_months'][month] = {
                    'selected_year': selected_year,
                    'scores': scores,
                    'data_points': len(month_data.time)
                }
                
                logger.info(f"Month {month}: Selected year {selected_year} (score: {scores.get('total', 0):.3f})")
        
        # Combine months into full TMY
        tmy_dataset = self._combine_months(tmy_months, target_year)
        
        # Add TMY metadata
        tmy_dataset.attrs.update({
            'title': f'Typical Meteorological Year {target_year}',
            'method': self.method.value,
            'analysis_period': f'{start_year}-{end_year}',
            'generated_on': datetime.now().isoformat(),
            'source': 'EcoSystemiser TMY Generator',
            'building_type': building_type or 'general',
            'advanced_selection': use_advanced_selection
        })
        
        logger.info(f"TMY generation complete: {len(tmy_dataset.time)} time steps")
        
        return tmy_dataset, selection_metadata
    
    def _validate_input(self, data: xr.Dataset, min_years: int):
        """Validate input dataset"""
        if 'time' not in data.dims:
            raise ValueError("Dataset must have 'time' dimension")
        
        if len(data.time) < 8760:  # Less than 1 year
            raise ValueError("Dataset must contain at least 1 year of data")
        
        # Check data span
        time_values = pd.to_datetime(data.time.values)
        years = time_values.year.unique()
        
        if len(years) < min_years:
            raise ValueError(f"Dataset must contain at least {min_years} years of data. Found {len(years)} years.")
        
        # Check for required variables
        required_vars = ['temp_air']
        missing_vars = [var for var in required_vars if var not in data.data_vars]
        if missing_vars:
            raise ValueError(f"Dataset missing required variables: {missing_vars}")
    
    def _get_default_weights(self) -> Dict[str, float]:
        """Get default variable weights based on method"""
        if self.method == TMYMethod.TMY3:
            return self.tmy3_weights.copy()
        elif self.method == TMYMethod.SIMPLIFIED:
            return {'temp_air': 1.0}  # Temperature only
        else:
            return {'temp_air': 1.0}  # Default fallback
    
    def _select_month(
        self, 
        data: xr.Dataset, 
        month: int, 
        weights: Dict[str, float]
    ) -> Tuple[int, Dict[str, float]]:
        """
        Select the most representative year for a given month.
        
        Uses TMY3 methodology with cumulative distribution function (CDF)
        comparison and weighted scoring.
        """
        # Get all available years for this month
        time_values = pd.to_datetime(data.time.values)
        month_mask = time_values.month == month
        month_data = data.isel(time=month_mask)
        
        if len(month_data.time) == 0:
            raise ValueError(f"No data found for month {month}")
        
        # Group by year
        years = pd.to_datetime(month_data.time.values).year.unique()
        
        if len(years) < 2:
            return years[0], {'total': 0.0}
        
        # Calculate long-term statistics for the month
        long_term_stats = self.metrics.calculate_monthly_statistics(
            data, month
        )
        
        # Score each year
        year_scores = {}
        
        for year in years:
            year_mask = pd.to_datetime(month_data.time.values).year == year
            year_data = month_data.isel(time=year_mask)
            
            if len(year_data.time) < 24:  # Skip years with insufficient data
                continue
            
            # Calculate composite score
            score = self._calculate_year_score(
                year_data, long_term_stats, weights
            )
            
            year_scores[year] = score
        
        if not year_scores:
            raise ValueError(f"No valid years found for month {month}")
        
        # Select year with best (lowest) score
        best_year = min(year_scores.keys(), key=lambda y: year_scores[y]['total'])
        
        return best_year, year_scores[best_year]
    
    def _calculate_year_score(
        self,
        year_data: xr.Dataset,
        long_term_stats: Dict,
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate composite score for a year's data
        
        Fixed to penalize years with missing variables rather than
        giving them an unfair advantage.
        """
        scores = {}
        weighted_sum = 0
        missing_penalty = 10.0  # High penalty score for missing variables
        
        # Use full weight sum for normalization (not just available variables)
        total_weight = sum(weights.values())
        
        for var_name, weight in weights.items():
            if var_name not in year_data.data_vars:
                # Penalize missing variables instead of skipping
                scores[var_name] = missing_penalty
                weighted_sum += missing_penalty * weight
                logger.debug(f"Variable {var_name} missing in year data - applying penalty")
                continue
            
            if var_name not in long_term_stats:
                # Also penalize if no long-term stats available
                scores[var_name] = missing_penalty
                weighted_sum += missing_penalty * weight
                logger.debug(f"Variable {var_name} missing in long-term stats - applying penalty")
                continue
            
            # Calculate CDF-based score using Finkelstein-Schafer statistics
            score = self.metrics.calculate_fs_statistic(
                year_data[var_name].values.flatten(),
                long_term_stats[var_name]
            )
            
            scores[var_name] = score
            weighted_sum += score * weight
        
        # Calculate composite score (now properly normalized)
        scores['total'] = weighted_sum / total_weight if total_weight > 0 else missing_penalty
        
        return scores
    
    def _extract_month_data(
        self,
        data: xr.Dataset,
        year: int,
        month: int,
        target_year: int
    ) -> xr.Dataset:
        """Extract and re-timestamp month data"""
        # Filter to specific year and month
        time_values = pd.to_datetime(data.time.values)
        month_mask = (time_values.year == year) & (time_values.month == month)
        month_data = data.isel(time=month_mask)
        
        if len(month_data.time) == 0:
            raise ValueError(f"No data found for {year}-{month:02d}")
        
        # Create new timestamps for target year
        original_times = pd.to_datetime(month_data.time.values)
        new_times = []
        
        for orig_time in original_times:
            try:
                new_time = orig_time.replace(year=target_year)
            except ValueError:
                # Handle leap year issues (Feb 29)
                if orig_time.month == 2 and orig_time.day == 29:
                    # Use Feb 28 in non-leap years
                    new_time = orig_time.replace(year=target_year, day=28)
                else:
                    raise
            new_times.append(new_time)
        
        # Update time coordinate
        month_data = month_data.assign_coords(time=new_times)
        
        return month_data
    
    def _combine_months(
        self, 
        month_datasets: Dict[int, xr.Dataset], 
        target_year: int
    ) -> xr.Dataset:
        """Combine monthly datasets into complete TMY"""
        # Sort months and concatenate
        sorted_months = [month_datasets[i] for i in range(1, 13)]
        
        # Concatenate along time dimension
        tmy_dataset = xr.concat(sorted_months, dim='time')
        
        # Ensure time is properly sorted
        tmy_dataset = tmy_dataset.sortby('time')
        
        # Handle potential time gaps/overlaps at month boundaries
        tmy_dataset = self._fix_time_continuity(tmy_dataset)
        
        return tmy_dataset
    
    def _fix_time_continuity(self, dataset: xr.Dataset) -> xr.Dataset:
        """Fix any time continuity issues in the TMY"""
        # Check for duplicate timestamps
        time_values = pd.to_datetime(dataset.time.values)
        
        if len(time_values) != len(set(time_values)):
            logger.warning("Duplicate timestamps detected, removing duplicates")
            # Keep first occurrence of each timestamp
            _, unique_indices = np.unique(time_values, return_index=True)
            dataset = dataset.isel(time=sorted(unique_indices))
        
        return dataset

# Convenience functions for backward compatibility and ease of use

def generate_tmy(
    historical_data: xr.Dataset,
    method: str = "tmy3",
    **kwargs
) -> Tuple[xr.Dataset, Dict]:
    """
    Convenience function for generating TMY datasets.
    
    Args:
        historical_data: Multi-year historical climate dataset
        method: TMY generation method ('tmy3', 'simplified', 'custom')
        **kwargs: Additional arguments passed to TMYGenerator.generate()
        
    Returns:
        Tuple of (TMY dataset, selection metadata)
    """
    method_enum = TMYMethod(method.lower())
    generator = TMYGenerator(method=method_enum)
    return generator.generate(historical_data, **kwargs)

def calculate_tmy_metrics(
    data: xr.Dataset,
    variables: Optional[List[str]] = None
) -> Dict:
    """
    Convenience function for calculating TMY quality metrics.
    
    Args:
        data: Climate dataset
        variables: Variables to analyze (default: all)
        
    Returns:
        Dictionary of comprehensive metrics
    """
    metrics = TMYMetrics()
    
    if variables is None:
        variables = list(data.data_vars)
    
    results = {
        'monthly_statistics': {},
        'diurnal_patterns': {},
        'correlations': metrics.calculate_variable_correlations(data, variables)
    }
    
    # Calculate monthly statistics for each month
    for month in range(1, 13):
        try:
            results['monthly_statistics'][month] = metrics.calculate_monthly_statistics(data, month)
        except ValueError as e:
            logger.warning(f"Could not calculate statistics for month {month}: {e}")
    
    # Calculate diurnal patterns for key variables
    key_vars = ['temp_air', 'ghi', 'wind_speed']
    for var in key_vars:
        if var in variables and var in data.data_vars:
            try:
                results['diurnal_patterns'][var] = metrics.calculate_diurnal_patterns(data, var)
            except ValueError as e:
                logger.warning(f"Could not calculate diurnal patterns for {var}: {e}")
    
    return results