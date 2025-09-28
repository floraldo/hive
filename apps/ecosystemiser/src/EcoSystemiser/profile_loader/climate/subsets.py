"""Subset extraction for climate data"""

from typing import Dict, Optional

import pandas as pd
import xarray as xr
from hive_logging import get_logger

logger = get_logger(__name__)


def apply_subset(ds: xr.Dataset, subset: Dict[str, str]) -> xr.Dataset:
    """
    Apply subset selection to dataset.

    Args:
        ds: Dataset to subset
        subset: Subset specification
               Examples:
               - {"month": "07"} - July only
               - {"day": "2019-07-14"} - Specific day
               - {"start": "07-10", "end": "07-24"} - Date range
               - {"hour": "12"} - Specific hour
               - {"season": "summer"} - Season

    Returns:
        Subset of dataset
    """
    if not subset:
        return ds

    ds_subset = ds.copy()

    # Month subset
    if "month" in subset:
        month = int(subset["month"])
        time_index = pd.DatetimeIndex(ds_subset.time.values)
        mask = time_index.month == month
        ds_subset = ds_subset.isel(time=mask)
        logger.info(f"Applied month subset: {month}")

    # Day subset
    if "day" in subset:
        day = pd.Timestamp(subset["day"])
        ds_subset = ds_subset.sel(time=slice(day, day + pd.Timedelta(days=1)))
        logger.info(f"Applied day subset: {day}")

    # Date range subset
    if "start" in subset and "end" in subset:
        # Handle different date formats
        start_str = subset["start"]
        end_str = subset["end"]

        # Check if it's month-day format (e.g., "07-10")
        if "-" in start_str and len(start_str.split("-")) == 2:
            # Assume current year from dataset
            year = pd.DatetimeIndex(ds_subset.time.values)[0].year
            start = pd.Timestamp(f"{year}-{start_str}")
            end = pd.Timestamp(f"{year}-{end_str}")
        else:
            start = pd.Timestamp(start_str)
            end = pd.Timestamp(end_str)

        ds_subset = ds_subset.sel(time=slice(start, end))
        logger.info(f"Applied date range subset: {start} to {end}")

    # Hour subset
    if "hour" in subset:
        hour = int(subset["hour"])
        time_index = pd.DatetimeIndex(ds_subset.time.values)
        mask = time_index.hour == hour
        ds_subset = ds_subset.isel(time=mask)
        logger.info(f"Applied hour subset: {hour}")

    # Season subset
    if "season" in subset:
        season = subset["season"].lower()
        ds_subset = extract_season(ds_subset, season)
        logger.info(f"Applied season subset: {season}")

    # Week subset
    if "week" in subset:
        week = int(subset["week"])
        time_index = pd.DatetimeIndex(ds_subset.time.values)
        mask = time_index.isocalendar().week == week
        ds_subset = ds_subset.isel(time=mask)
        logger.info(f"Applied week subset: {week}")

    return ds_subset


def extract_season(ds: xr.Dataset, season: str) -> xr.Dataset:
    """
    Extract seasonal subset from dataset.

    Args:
        ds: Dataset to subset
        season: Season name ('spring', 'summer', 'fall', 'winter')

    Returns:
        Seasonal subset
    """
    season_months = {
        "spring": [3, 4, 5],
        "summer": [6, 7, 8],
        "fall": [9, 10, 11],
        "autumn": [9, 10, 11],  # Alias
        "winter": [12, 1, 2],
    }

    if season not in season_months:
        logger.warning(f"Unknown season '{season}', returning full dataset")
        return ds

    months = season_months[season]
    time_index = pd.DatetimeIndex(ds.time.values)
    mask = time_index.month.isin(months)

    return ds.isel(time=mask)


def extract_typical_periods(ds: xr.Dataset, period_type: str = "typical_week") -> xr.Dataset:
    """
    Extract typical periods from dataset.

    Args:
        ds: Dataset to analyze
        period_type: Type of typical period
                    ('typical_week', 'typical_day', 'peak_week')

    Returns:
        Typical period subset
    """
    if period_type == "typical_week":
        # Find week closest to annual average
        weekly_means = ds.resample(time="1W").mean()
        annual_mean = ds.mean(dim="time")

        # Calculate distance from annual mean for each week
        distances = {}
        for week_start in weekly_means.time.values:
            week_data = ds.sel(time=slice(week_start, week_start + pd.Timedelta(days=7)))
            if len(week_data.time) > 0:
                week_mean = week_data.mean(dim="time")
                # Simple euclidean distance across all variables
                dist = 0
                for var in ds.data_vars:
                    if var in week_mean and var in annual_mean:
                        dist += float((week_mean[var] - annual_mean[var]) ** 2)
                distances[week_start] = dist

        # Select week with minimum distance
        if distances:
            typical_week_start = min(distances, key=distances.get)
            typical_week = ds.sel(time=slice(typical_week_start, typical_week_start + pd.Timedelta(days=7)))
            return typical_week

    elif period_type == "typical_day":
        # Find day closest to annual average
        daily_means = ds.resample(time="1D").mean()
        annual_mean = ds.mean(dim="time")

        distances = {}
        for day in daily_means.time.values:
            day_data = daily_means.sel(time=day)
            dist = 0
            for var in ds.data_vars:
                if var in day_data and var in annual_mean:
                    dist += float((day_data[var] - annual_mean[var]) ** 2)
            distances[day] = dist

        if distances:
            typical_day = min(distances, key=distances.get)
            return ds.sel(time=slice(typical_day, typical_day + pd.Timedelta(days=1)))

    elif period_type == "peak_week":
        # Find week with highest energy demand proxy (high temp or low temp)
        weekly_means = ds.resample(time="1W").mean()

        if "temp_air" in weekly_means:
            # Summer peak (highest temperature)
            peak_week_idx = weekly_means["temp_air"].argmax()
            peak_week_start = weekly_means.time[peak_week_idx].values

            return ds.sel(time=slice(peak_week_start, peak_week_start + pd.Timedelta(days=7)))

    logger.warning(f"Could not extract {period_type}, returning full dataset")
    return ds
