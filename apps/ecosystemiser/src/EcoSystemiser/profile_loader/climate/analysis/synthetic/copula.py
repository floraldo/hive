"""Copula-based synthetic generation for climate data"""

import xarray as xr
import numpy as np
import pandas as pd
from typing import Optional, Literal, Dict, Tuple, List
from scipy import stats
from scipy.stats import norm
from hive_logging import get_logger
from dataclasses import dataclass
from enum import Enum

logger = get_logger(__name__)

class CopulaType(Enum):
    """Supported copula types"""
    GAUSSIAN = "gaussian"
    T_COPULA = "t_copula"
    EMPIRICAL = "empirical"
    VINE = "vine"  # Advanced - for future

@dataclass
class CopulaConfig:
    """Configuration for copula-based generation"""
    copula_type: CopulaType = CopulaType.GAUSSIAN
    preserve_seasonality: bool = True
    preserve_diurnal: bool = True
    n_samples: int = 8760  # Default to 1 year
    seasonal_bins: int = 12  # Monthly
    diurnal_bins: int = 24  # Hourly
    min_correlation: float = 0.05  # Minimum correlation to model
    bootstrap_samples: int = 1000
    
class CopulaSyntheticGenerator:
    """
    Advanced synthetic climate data generation using copula methods.
    
    Preserves both marginal distributions and dependence structure
    while allowing for temporal pattern preservation.
    """
    
    def __init__(self, config: Optional[CopulaConfig] = None):
        """Initialize copula generator"""
        self.config = config or CopulaConfig()
        self._fitted_copula = None
        self._marginal_models = {}
        self._seasonal_patterns = {}
        
    def generate(
        self, 
        ds_hist: xr.Dataset, 
        seed: Optional[int] = None,
        target_length: str = "1Y"
    ) -> xr.Dataset:
        """
        Generate synthetic climate data preserving correlations and distributions.
        
        Args:
            ds_hist: Historical dataset to learn from
            seed: Random seed for reproducibility
            target_length: Target length (e.g., "1Y", "2Y")
            
        Returns:
            Synthetic dataset with same structure as input
        """
        if seed is not None:
            np.random.seed(seed)
            
        logger.info(f"Generating synthetic data using {self.config.copula_type.value} copula")
        
        # Extract and prepare data
        data_matrix, variables, time_info = self._prepare_data(ds_hist)
        
        # Parse target length with frequency awareness
        n_samples = self._parse_target_length(target_length, time_info.get('freq', 'h'))
        
        if data_matrix.shape[1] < 2:
            raise ValueError("Need at least 2 variables for copula modeling")
            
        # Fit marginal distributions
        self._fit_marginals(data_matrix, variables, time_info)
        
        # Fit copula
        self._fit_copula(data_matrix)
        
        # Generate synthetic data
        synthetic_data = self._generate_synthetic(n_samples, variables, time_info)
        
        # Create output dataset
        synthetic_ds = self._create_synthetic_dataset(
            synthetic_data, variables, ds_hist, target_length, time_info
        )
        
        logger.info(f"Generated {len(synthetic_ds.time)} synthetic time steps")
        
        return synthetic_ds
    
    def _parse_target_length(self, target_length: str, freq: str = 'h') -> int:
        """Parse target length string to number of samples based on frequency"""
        # Convert frequency to samples per day
        freq_lower = freq.lower()
        if freq_lower in ['h', 'hour', 'hourly']:
            samples_per_day = 24
        elif freq_lower in ['d', 'day', 'daily']:
            samples_per_day = 1
        elif freq_lower in ['3h', '3hour']:
            samples_per_day = 8
        elif freq_lower in ['6h', '6hour']:
            samples_per_day = 4
        elif freq_lower in ['12h', '12hour']:
            samples_per_day = 2
        else:
            # Try to extract number from frequency string (e.g., '2H' -> 2 hours)
            import re
            match = re.match(r'(\d+)([A-Za-z])', freq)
            if match:
                num, unit = match.groups()
                if unit.lower() in ['h']:
                    samples_per_day = 24 // int(num)
                else:
                    samples_per_day = 24  # Default to hourly
            else:
                samples_per_day = 24  # Default to hourly
        
        if target_length.endswith('Y'):
            years = int(target_length[:-1]) if target_length[:-1] else 1
            return years * 365 * samples_per_day
        elif target_length.endswith('M'):
            months = int(target_length[:-1]) if target_length[:-1] else 1
            return months * 30 * samples_per_day  # Approximate
        elif target_length.endswith('D'):
            days = int(target_length[:-1]) if target_length[:-1] else 1
            return days * samples_per_day
        else:
            return int(target_length)  # Assume number of samples
    
    def _prepare_data(self, ds: xr.Dataset) -> Tuple[np.ndarray, List[str], Dict]:
        """Prepare data matrix for copula fitting"""
        
        # Select numerical variables only
        variables = []
        data_arrays = []
        
        for var in ds.data_vars:
            data = ds[var].values.flatten()
            # Remove NaN values and check if enough data
            valid_mask = ~np.isnan(data)
            if np.sum(valid_mask) > 100:  # Need sufficient data
                variables.append(var)
                data_arrays.append(data[valid_mask])
        
        if len(variables) == 0:
            raise ValueError("No valid variables found for synthetic generation")
        
        # Create aligned data matrix (handle different lengths due to NaN removal)
        min_length = min(len(arr) for arr in data_arrays)
        data_matrix = np.column_stack([arr[:min_length] for arr in data_arrays])
        
        # Extract temporal information
        time_info = {
            'original_times': pd.to_datetime(ds.time.values),
            'start_time': pd.to_datetime(ds.time.values[0]),
            'freq': pd.infer_freq(ds.time.values) or 'H'
        }
        
        logger.info(f"Prepared data matrix: {data_matrix.shape} for variables {variables}")
        
        return data_matrix, variables, time_info
    
    def _fit_marginals(
        self, 
        data_matrix: np.ndarray, 
        variables: List[str], 
        time_info: Dict
    ):
        """Fit marginal distributions for each variable"""
        
        logger.info("Fitting marginal distributions")
        
        for i, var in enumerate(variables):
            data = data_matrix[:, i]
            
            # Try different distributions and select best
            distributions = [stats.norm, stats.gamma, stats.lognorm, stats.beta]
            best_dist = None
            best_params = None
            best_score = -np.inf
            
            for dist in distributions:
                try:
                    # Fit distribution
                    params = dist.fit(data)
                    
                    # Calculate goodness of fit (negative log-likelihood)
                    log_likelihood = np.sum(dist.logpdf(data, *params))
                    
                    # Use AIC for model selection
                    aic = -2 * log_likelihood + 2 * len(params)
                    score = -aic  # Higher is better
                    
                    if score > best_score:
                        best_dist = dist
                        best_params = params
                        best_score = score
                        
                except Exception as e:
                    continue
            
            # Fallback to normal distribution
            if best_dist is None:
                best_dist = stats.norm
                best_params = stats.norm.fit(data)
            
            self._marginal_models[var] = {
                'distribution': best_dist,
                'parameters': best_params,
                'data_range': (np.min(data), np.max(data))
            }
            
            logger.debug(f"Variable {var}: fitted {best_dist.name} distribution")
    
    def _fit_copula(self, data_matrix: np.ndarray):
        """Fit copula to the dependence structure"""
        
        logger.info(f"Fitting {self.config.copula_type.value} copula")
        
        # Transform to uniform margins using empirical CDF
        n_obs, n_vars = data_matrix.shape
        uniform_data = np.zeros_like(data_matrix)
        
        for i in range(n_vars):
            # Empirical CDF transformation
            sorted_data = np.sort(data_matrix[:, i])
            uniform_data[:, i] = np.searchsorted(sorted_data, data_matrix[:, i]) / n_obs
            # Avoid 0 and 1 values
            uniform_data[:, i] = np.clip(uniform_data[:, i], 1/(2*n_obs), 1-1/(2*n_obs))
        
        if self.config.copula_type == CopulaType.GAUSSIAN:
            # Gaussian copula - estimate correlation matrix
            # Transform uniform to normal
            normal_data = norm.ppf(uniform_data)
            
            # Estimate correlation matrix
            correlation_matrix = np.corrcoef(normal_data.T)
            
            # Ensure positive definite
            correlation_matrix = self._ensure_positive_definite(correlation_matrix)
            
            self._fitted_copula = {
                'type': 'gaussian',
                'correlation_matrix': correlation_matrix,
                'uniform_data': uniform_data  # Store for empirical margins
            }
            
        elif self.config.copula_type == CopulaType.EMPIRICAL:
            # Empirical copula - store the transformed data
            self._fitted_copula = {
                'type': 'empirical',
                'uniform_data': uniform_data,
                'n_samples': n_obs
            }
            
        else:
            raise NotImplementedError(f"Copula type {self.config.copula_type.value} not implemented")
            
        logger.info("Copula fitting complete")
    
    def _ensure_positive_definite(self, matrix: np.ndarray) -> np.ndarray:
        """Ensure correlation matrix is positive definite"""
        eigenvals, eigenvecs = np.linalg.eigh(matrix)
        
        # Set negative eigenvalues to small positive value
        eigenvals = np.maximum(eigenvals, 1e-8)
        
        # Reconstruct matrix
        matrix_pd = eigenvecs @ np.diag(eigenvals) @ eigenvecs.T
        
        # Normalize to ensure diagonal elements are 1
        diag_sqrt = np.sqrt(np.diag(matrix_pd))
        matrix_pd = matrix_pd / np.outer(diag_sqrt, diag_sqrt)
        
        return matrix_pd
    
    def _generate_synthetic(
        self, 
        n_samples: int, 
        variables: List[str], 
        time_info: Dict
    ) -> np.ndarray:
        """Generate synthetic samples from fitted copula"""
        
        logger.info(f"Generating {n_samples} synthetic samples")
        
        if self._fitted_copula['type'] == 'gaussian':
            # Generate from multivariate normal copula
            corr_matrix = self._fitted_copula['correlation_matrix']
            n_vars = len(variables)
            
            # Generate correlated normal variables
            normal_samples = np.random.multivariate_normal(
                mean=np.zeros(n_vars),
                cov=corr_matrix,
                size=n_samples
            )
            
            # Transform to uniform
            uniform_samples = norm.cdf(normal_samples)
            
        elif self._fitted_copula['type'] == 'empirical':
            # Bootstrap from empirical copula
            uniform_data = self._fitted_copula['uniform_data']
            n_obs = self._fitted_copula['n_samples']
            
            # Bootstrap sample indices
            bootstrap_indices = np.random.choice(n_obs, size=n_samples, replace=True)
            uniform_samples = uniform_data[bootstrap_indices]
            
        else:
            raise NotImplementedError(f"Generation for {self._fitted_copula['type']} not implemented")
        
        # Transform uniform samples back to original margins
        synthetic_data = np.zeros_like(uniform_samples)
        
        for i, var in enumerate(variables):
            marginal_info = self._marginal_models[var]
            dist = marginal_info['distribution']
            params = marginal_info['parameters']
            
            # Transform uniform to original distribution
            synthetic_data[:, i] = dist.ppf(uniform_samples[:, i], *params)
            
            # Ensure values are within reasonable bounds
            data_min, data_max = marginal_info['data_range']
            buffer = (data_max - data_min) * 0.1  # Allow 10% extension
            synthetic_data[:, i] = np.clip(
                synthetic_data[:, i], 
                data_min - buffer, 
                data_max + buffer
            )
        
        return synthetic_data
    
    def _create_synthetic_dataset(
        self,
        synthetic_data: np.ndarray,
        variables: List[str],
        original_ds: xr.Dataset,
        target_length: str,
        time_info: Dict
    ) -> xr.Dataset:
        """Create xarray dataset from synthetic data"""
        
        # Create time index
        n_samples = synthetic_data.shape[0]
        
        # Start from a reference year
        start_time = pd.Timestamp('2010-01-01')
        inferred_freq = time_info.get('freq', 'h')  # Use inferred frequency
        time_index = pd.date_range(
            start=start_time,
            periods=n_samples,
            freq=inferred_freq  # Use original data frequency
        )
        
        # Create dataset
        data_vars = {}
        for i, var in enumerate(variables):
            # Get original attributes if available
            attrs = original_ds[var].attrs.copy() if var in original_ds.data_vars else {}
            
            data_vars[var] = xr.DataArray(
                synthetic_data[:, i],
                dims=['time'],
                coords={'time': time_index},
                attrs=attrs
            )
        
        synthetic_ds = xr.Dataset(data_vars)
        
        # Add metadata
        synthetic_ds.attrs.update({
            'title': 'Synthetic Climate Data (Copula-based)',
            'method': f'{self.config.copula_type.value}_copula',
            'generated_on': pd.Timestamp.now().isoformat(),
            'target_length': target_length,
            'source': 'EcoSystemiser Copula Generator'
        })
        
        return synthetic_ds

def copula_synthetic_generation(
    ds_hist: xr.Dataset,
    seed: Optional[int] = None,
    copula_type: str = "gaussian",
    target_length: str = "1Y",
    **kwargs
) -> xr.Dataset:
    """
    Generate synthetic climate data using copula methods.
    
    Args:
        ds_hist: Historical dataset to learn from
        seed: Random seed for reproducibility  
        copula_type: Type of copula ('gaussian', 'empirical')
        target_length: Target length of synthetic data
        **kwargs: Additional configuration options
        
    Returns:
        Synthetic dataset preserving correlations and marginal distributions
    """
    # Create configuration
    try:
        copula_enum = CopulaType(copula_type.lower())
    except ValueError:
        logger.warning(f"Unknown copula type '{copula_type}', using gaussian")
        copula_enum = CopulaType.GAUSSIAN
    
    config = CopulaConfig(copula_type=copula_enum, **kwargs)
    
    # Generate synthetic data
    generator = CopulaSyntheticGenerator(config)
    return generator.generate(ds_hist, seed=seed, target_length=target_length)