"""Seasonal block bootstrap for synthetic climate generation"""

import xarray as xr
import numpy as np
import pandas as pd
from typing import Optional, Literal
import logging

logger = logging.getLogger(__name__)

def multivariate_block_bootstrap(
    ds_hist: xr.Dataset,
    block: str = "1D",
    season_bins: int = 12,
    overlap_hours: int = 3,
    seed: Optional[int] = None,
    target_length: Optional[str] = "1Y"
) -> xr.Dataset:
    """
    Generate synthetic climate data using seasonal block bootstrap.
    
    Preserves intra-block correlations between variables.
    
    Args:
        ds_hist: Historical dataset to bootstrap from
        block: Block size (e.g., "1D" for daily blocks, "7D" for weekly)
        season_bins: Number of seasonal bins (12 for monthly)
        overlap_hours: Hours of overlap for smoothing block boundaries
        seed: Random seed for reproducibility
        target_length: Length of synthetic series to generate
        
    Returns:
        Synthetic dataset with same variables as input
    """
    if seed is not None:
        np.random.seed(seed)
    
    logger.info(
        f"Generating synthetic data: block={block}, seasons={season_bins}, "
        f"overlap={overlap_hours}h, seed={seed}"
    )
    
    # Convert block size to timedelta
    block_td = pd.Timedelta(block)
    
    # Partition historical data into blocks
    blocks = partition_into_blocks(ds_hist, block_td, season_bins)
    
    # Determine target length
    if target_length:
        target_td = pd.Timedelta(target_length)
        n_blocks_needed = int(np.ceil(target_td / block_td))
    else:
        n_blocks_needed = len(blocks)
    
    # Sample blocks with replacement
    sampled_blocks = sample_blocks_by_season(
        blocks, 
        n_blocks_needed,
        season_bins
    )
    
    # Concatenate blocks
    synthetic = concatenate_blocks(sampled_blocks, overlap_hours)
    
    # Ensure continuity and proper time index
    synthetic = ensure_continuity(synthetic, ds_hist.time[0].values)
    
    # Copy attributes
    synthetic.attrs = ds_hist.attrs.copy()
    synthetic.attrs['synthetic'] = True
    synthetic.attrs['method'] = 'seasonal_block_bootstrap'
    synthetic.attrs['block_size'] = block
    synthetic.attrs['seed'] = seed
    
    return synthetic

def partition_into_blocks(
    ds: xr.Dataset,
    block_size: pd.Timedelta,
    season_bins: int
) -> list:
    """
    Partition dataset into blocks labeled by season.
    
    Args:
        ds: Dataset to partition
        block_size: Size of each block
        season_bins: Number of seasonal bins
        
    Returns:
        List of (block_data, season_label) tuples
    """
    blocks = []
    
    # Get time range
    time_start = pd.Timestamp(ds.time[0].values)
    time_end = pd.Timestamp(ds.time[-1].values)
    
    # Create block boundaries
    block_starts = pd.date_range(
        start=time_start,
        end=time_end,
        freq=block_size
    )
    
    for i in range(len(block_starts) - 1):
        start = block_starts[i]
        end = block_starts[i + 1]
        
        # Extract block
        block_data = ds.sel(time=slice(start, end))
        
        if len(block_data.time) > 0:
            # Determine season (month-based for simplicity)
            mid_time = start + (end - start) / 2
            if season_bins == 12:
                season = mid_time.month - 1
            elif season_bins == 4:
                season = (mid_time.month - 1) // 3
            else:
                # Generic binning based on day of year
                day_of_year = mid_time.dayofyear
                season = int((day_of_year - 1) / 365 * season_bins)
            
            blocks.append((block_data, season))
    
    logger.info(f"Partitioned into {len(blocks)} blocks across {season_bins} seasons")
    
    return blocks

def sample_blocks_by_season(
    blocks: list,
    n_blocks: int,
    n_seasons: int
) -> list:
    """
    Sample blocks with replacement, respecting seasonal distribution.
    
    Args:
        blocks: List of (block_data, season) tuples
        n_blocks: Number of blocks to sample
        n_seasons: Number of seasons
        
    Returns:
        List of sampled blocks
    """
    # Organize blocks by season
    blocks_by_season = {s: [] for s in range(n_seasons)}
    
    for block_data, season in blocks:
        blocks_by_season[season].append(block_data)
    
    # Sample blocks
    sampled = []
    blocks_per_season = n_blocks // n_seasons
    extra_blocks = n_blocks % n_seasons
    
    for season in range(n_seasons):
        season_blocks = blocks_by_season[season]
        
        if not season_blocks:
            logger.warning(f"No blocks available for season {season}")
            continue
        
        # Determine number of blocks to sample from this season
        n_sample = blocks_per_season
        if extra_blocks > 0:
            n_sample += 1
            extra_blocks -= 1
        
        # Sample with replacement
        for _ in range(n_sample):
            idx = np.random.randint(0, len(season_blocks))
            sampled.append(season_blocks[idx].copy())
    
    # Shuffle to avoid systematic seasonal ordering
    np.random.shuffle(sampled)
    
    logger.info(f"Sampled {len(sampled)} blocks")
    
    return sampled

def concatenate_blocks(
    blocks: list,
    overlap_hours: int
) -> xr.Dataset:
    """
    Concatenate blocks with overlap-save smoothing.
    
    Args:
        blocks: List of block datasets
        overlap_hours: Hours of overlap for smoothing
        
    Returns:
        Concatenated dataset
    """
    if not blocks:
        raise ValueError("No blocks to concatenate")
    
    if overlap_hours == 0:
        # Simple concatenation
        return xr.concat(blocks, dim='time')
    
    # Concatenate with overlap smoothing
    result = blocks[0].copy()
    
    for i in range(1, len(blocks)):
        current_block = blocks[i]
        
        # Find overlap region
        overlap_td = pd.Timedelta(hours=overlap_hours)
        
        # Get overlapping portions
        result_end = result.time[-overlap_hours:]
        block_start = current_block.time[:overlap_hours]
        
        # Blend in overlap region
        if len(result_end) > 0 and len(block_start) > 0:
            # Linear blending weights
            n_overlap = min(len(result_end), len(block_start))
            weights = np.linspace(1, 0, n_overlap)
            
            for var in result.data_vars:
                if var in current_block:
                    # Blend values
                    result[var].values[-n_overlap:] = (
                        weights * result[var].values[-n_overlap:] +
                        (1 - weights) * current_block[var].values[:n_overlap]
                    )
        
        # Append non-overlapping portion
        non_overlap = current_block.isel(time=slice(overlap_hours, None))
        result = xr.concat([result, non_overlap], dim='time')
    
    return result

def ensure_continuity(
    ds: xr.Dataset,
    start_time: np.datetime64
) -> xr.Dataset:
    """
    Ensure continuous time index starting from specified time.
    
    Args:
        ds: Dataset to process
        start_time: Starting time for new index
        
    Returns:
        Dataset with continuous time index
    """
    # Get original frequency
    time_diff = pd.Series(ds.time.values).diff().mode()[0]
    freq = pd.Timedelta(time_diff)
    
    # Create new continuous time index
    n_steps = len(ds.time)
    new_time = pd.date_range(
        start=start_time,
        periods=n_steps,
        freq=freq
    )
    
    # Reassign time coordinate
    ds_continuous = ds.assign_coords(time=new_time)
    
    return ds_continuous