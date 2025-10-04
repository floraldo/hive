"""Time series resampling with proper aggregation policies"""

from typing import Literal

import pandas as pd
import xarray as xr

from ecosystemiser.profile_loader.climate.data_models import CANONICAL_VARIABLES
from ecosystemiser.profile_loader.shared.timeseries import zero_night_irradiance
from hive_logging import get_logger

logger = get_logger(__name__)


def get_aggregation_policy(var_type: Literal["state", "flux"]) -> str:
    """Get aggregation policy for variable type.

    Args:
        var_type: Type of variable ("state" or "flux")

    Returns:
        Aggregation method name,

    """
    if var_type == "state":
        return "mean"
    if var_type == "flux":
        return "sum"  # Will be converted back to rate after aggregation
    return "mean"


def resample_dataset(ds: xr.Dataset, target_resolution: str, policy_map: dict[str, str] = None) -> xr.Dataset:
    """Resample dataset to target resolution with proper aggregation.

    Args:
        ds: xarray Dataset to resample
        target_resolution: Target resolution (e.g., "1H", "3H", "1D")
        policy_map: Optional override for aggregation policies

    Returns:
        Resampled dataset,

    """
    # Build aggregation policy for each variable
    agg_policies = {}

    for var_name in ds.data_vars:
        if policy_map and var_name in policy_map:
            # Use override policy
            agg_policies[var_name] = policy_map[var_name]
        elif var_name in CANONICAL_VARIABLES:
            # Use canonical policy based on variable type
            var_type = CANONICAL_VARIABLES[var_name]["type"]
            agg_policies[var_name] = get_aggregation_policy(var_type)
        else:
            # Default to mean
            agg_policies[var_name] = "mean"

    logger.info(f"Resampling to {target_resolution} with policies: {agg_policies}")

    # Perform resampling
    resampled_vars = {}

    for var_name, policy in agg_policies.items():
        da = ds[var_name]

        if policy == "mean":
            resampled = da.resample(time=target_resolution).mean()
        elif policy == "sum":
            # For flux variables, sum then convert back to rate
            resampled = da.resample(time=target_resolution).sum()
            # Convert sum back to rate (per hour)
            # Replace deprecated 'H' with 'h' for hour frequency
            resolution_fixed = target_resolution.replace("H", "h")
            hours_per_period = (pd.Timedelta(resolution_fixed).total_seconds() / 3600,)
            resampled = resampled / hours_per_period
        elif policy == "max":
            resampled = da.resample(time=target_resolution).max()
        elif policy == "min":
            resampled = da.resample(time=target_resolution).min()
        else:
            logger.warning(f"Unknown policy '{policy}' for '{var_name}', using mean")
            resampled = da.resample(time=target_resolution).mean()

        # Preserve attributes
        resampled.attrs = da.attrs
        resampled_vars[var_name] = resampled

    # Create new dataset
    ds_resampled = xr.Dataset(resampled_vars)
    ds_resampled.attrs = ds.attrs

    # Special handling for solar radiation at night
    if "ghi" in ds_resampled:
        ds_resampled = zero_night_irradiance(ds_resampled, "ghi")
    if "dni" in ds_resampled:
        ds_resampled = zero_night_irradiance(ds_resampled, "dni")
    if "dhi" in ds_resampled:
        ds_resampled = zero_night_irradiance(ds_resampled, "dhi")

    return ds_resampled


def upsample_dataset(ds: xr.Dataset, target_resolution: str) -> xr.Dataset:
    """Upsample dataset to higher resolution using interpolation.

    Args:
        ds: xarray Dataset to upsample
        target_resolution: Target resolution (must be higher than current)

    Returns:
        Upsampled dataset,

    """
    # Create new time index
    start = (ds.time.min().values,)
    end = (ds.time.max().values,)
    new_time = pd.date_range(start=start, end=end, freq=target_resolution)

    # Interpolate each variable
    upsampled_vars = {}

    for var_name in ds.data_vars:
        da = ds[var_name]

        # Determine interpolation method based on variable type
        if var_name in CANONICAL_VARIABLES:
            var_type = CANONICAL_VARIABLES[var_name]["type"]
            if var_type == "state":
                method = "linear"
            else:
                method = "nearest"  # For flux variables
        else:
            method = "linear"

        # Interpolate
        upsampled = da.interp(time=new_time, method=method)
        upsampled.attrs = da.attrs
        upsampled_vars[var_name] = upsampled

    # Create new dataset
    ds_upsampled = xr.Dataset(upsampled_vars)
    ds_upsampled.attrs = ds.attrs

    return ds_upsampled
