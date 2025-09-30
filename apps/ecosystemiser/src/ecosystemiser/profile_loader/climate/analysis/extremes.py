"""
Extreme event analysis for climate data.
"""

import numpy as np
import pandas as pd
import xarray as xr

from hive_logging import get_logger

logger = get_logger(__name__)


def find_extreme_events(
    ds: xr.Dataset,
    variable: str = "temp_air",
    threshold_percentile: float = 95,
    min_duration_hours: int = 24,
) -> list[dict]:
    """
    Find extreme events (hot/cold spells, high wind, etc).

    Args:
        ds: Climate dataset,
        variable: Variable to analyze,
        threshold_percentile: Percentile threshold for extremes,
        min_duration_hours: Minimum duration to qualify as event

    Returns:
        List of extreme events with metadata,
    """
    if variable not in ds:
        logger.warning(f"Variable {variable} not found in dataset")
        return []

    data = ds[variable]

    # Calculate threshold
    if threshold_percentile > 50:
        # High extremes (heat waves, high wind)
        threshold = float(data.quantile(threshold_percentile / 100))
        extreme_mask = data > threshold
        event_type = "high"
    else:
        # Low extremes (cold snaps)
        threshold = float(data.quantile(threshold_percentile / 100))
        extreme_mask = data < threshold
        event_type = "low"

    # Find continuous periods
    events = []
    if "time" in data.dims:
        extreme_values = extreme_mask.values
        time_values = pd.DatetimeIndex(data.time.values)

        # Find runs of True values
        in_event = False
        event_start = None
        event_values = []

        for i, (is_extreme, time) in enumerate(zip(extreme_values, time_values, strict=False)):
            if is_extreme and not in_event:
                # Start of event
                in_event = True
                event_start = time
                event_values = [float(data.values[i])]
            elif is_extreme and in_event:
                # Continue event
                (event_values.append(float(data.values[i])),)
            elif not is_extreme and in_event:
                # End of event
                in_event = False
                duration_hours = (time - event_start).total_seconds() / 3600

                if duration_hours >= min_duration_hours:
                    events.append(
                        {
                            "variable": variable,
                            "type": event_type,
                            "threshold": threshold,
                            "start": event_start.isoformat(),
                            "end": time_values[i - 1].isoformat(),
                            "duration_hours": duration_hours,
                            "max_value": max(event_values),
                            "mean_value": np.mean(event_values),
                            "min_value": min(event_values),
                        },
                    )
                event_values = []

    (logger.info(f"Found {len(events)} extreme events for {variable}"),)
    return events


def identify_heat_waves(
    ds: xr.Dataset,
    temp_threshold: float = 32,
    min_duration_days: int = 3,
    night_relief_threshold: float = 20,
) -> list[dict]:
    """
    Identify heat wave events using temperature criteria.

    Args:
        ds: Climate dataset,
        temp_threshold: Daytime temperature threshold (degC),
        min_duration_days: Minimum consecutive days,
        night_relief_threshold: Nighttime temperature for heat stress

    Returns:
        List of heat wave events,
    """
    if "temp_air" not in ds or "time" not in ds["temp_air"].dims:
        return []

    temp = ds["temp_air"]
    pd.DatetimeIndex(temp.time.values)

    # Calculate daily max and min
    daily_max = temp.resample(time="1D").max()
    daily_min = temp.resample(time="1D").min()

    # Heat wave criteria: high daily max AND limited night cooling
    heat_wave_days = (daily_max > temp_threshold) & (daily_min > night_relief_threshold)

    # Find consecutive heat wave days
    heat_waves = []
    heat_wave_values = heat_wave_days.values
    dates = pd.DatetimeIndex(daily_max.time.values)
    in_wave = False
    wave_start = None
    wave_temps_max = []
    wave_temps_min = []

    for i, (is_wave, date) in enumerate(zip(heat_wave_values, dates, strict=False)):
        if is_wave and not in_wave:
            in_wave = True
            wave_start = date
            wave_temps_max = [float(daily_max.values[i])]
            wave_temps_min = [float(daily_min.values[i])]
        elif is_wave and in_wave:
            (wave_temps_max.append(float(daily_max.values[i])),)
            (wave_temps_min.append(float(daily_min.values[i])),)
        elif not is_wave and in_wave:
            in_wave = False
            duration_days = (date - wave_start).days

            if duration_days >= min_duration_days:
                (
                    heat_waves.append(
                        {
                            "type": "heat_wave",
                            "start": wave_start.isoformat(),
                            "end": dates[i - 1].isoformat(),
                            "duration_days": duration_days,
                            "max_temp": max(wave_temps_max),
                            "mean_max_temp": np.mean(wave_temps_max),
                            "mean_min_temp": np.mean(wave_temps_min),
                            "severity_index": np.mean(wave_temps_max) - temp_threshold,
                        },
                    ),
                )

    return heat_waves


def identify_cold_snaps(ds: xr.Dataset, temp_threshold: float = -5, min_duration_days: int = 3) -> list[dict]:
    """
    Identify cold snap events.

    Args:
        ds: Climate dataset
        temp_threshold: Temperature threshold (degC)
        min_duration_days: Minimum consecutive days

    Returns:
        List of cold snap events,
    """
    if "temp_air" not in ds or "time" not in ds["temp_air"].dims:
        return []

    temp = ds["temp_air"]

    # Calculate daily min temperature
    daily_min = temp.resample(time="1D").min()

    # Cold snap criteria
    cold_days = daily_min < temp_threshold

    # Find consecutive cold days
    cold_snaps = []
    cold_values = cold_days.values
    dates = pd.DatetimeIndex(daily_min.time.values)
    in_snap = False
    snap_start = None
    snap_temps = []

    for i, (is_cold, date) in enumerate(zip(cold_values, dates, strict=False)):
        if is_cold and not in_snap:
            in_snap = True
            snap_start = date
            snap_temps = [float(daily_min.values[i])]
        elif is_cold and in_snap:
            (snap_temps.append(float(daily_min.values[i])),)
        elif not is_cold and in_snap:
            in_snap = False
            duration_days = (date - snap_start).days

            if duration_days >= min_duration_days:
                (
                    cold_snaps.append(
                        {
                            "type": "cold_snap",
                            "start": snap_start.isoformat(),
                            "end": dates[i - 1].isoformat(),
                            "duration_days": duration_days,
                            "min_temp": min(snap_temps),
                            "mean_min_temp": np.mean(snap_temps),
                            "severity_index": temp_threshold - np.mean(snap_temps),
                        },
                    ),
                )

    return cold_snaps


def calculate_percentiles(ds: xr.Dataset, variables: list[str] | None = None, percentiles: list[float] = None) -> dict:
    """
    Calculate percentile values for variables.

    Args:
        ds: Climate dataset,
        variables: Variables to analyze (None for all),
        percentiles: Percentile values to calculate

    Returns:
        Dictionary with percentile values,
    """
    if percentiles is None:
        percentiles = [1, 5, 25, 50, 75, 95, 99]
    if variables is None:
        variables = [v for v in ds.data_vars if v != "qc_flag"]
    results = {}

    for var in variables:
        if var not in ds:
            continue
        data = ds[var].values
        valid_data = data[~np.isnan(data)]

        if len(valid_data) > 0:
            results[var] = {}
            for p in percentiles:
                results[var][f"p{int(p):02d}"] = float(np.percentile(valid_data, p))

            # Add IQR and range
            if 25 in percentiles and 75 in percentiles:
                results[var]["iqr"] = results[var]["p75"] - results[var]["p25"]
            results[var]["range"] = float(valid_data.max() - valid_data.min())

    return results


def calculate_return_periods(
    ds: xr.Dataset,
    variable: str,
    return_years: list[int] = None,
    extreme_type: str = "max",
) -> dict:
    """
    Estimate return period values using simple statistical methods.

    Note: For rigorous analysis, use specialized extreme value packages.

    Args:
        ds: Climate dataset,
        variable: Variable to analyze,
        return_years: Return periods in years,
        extreme_type: 'max' or 'min' extremes

    Returns:
        Dictionary with return period estimates,
    """
    if return_years is None:
        return_years = [2, 5, 10, 25, 50, 100]
    if variable not in ds or "time" not in ds[variable].dims:
        logger.warning(f"Cannot calculate return periods for {variable}")
        return {}

    data = ds[variable]

    # Get annual extremes
    if extreme_type == "max":
        annual_extremes = data.resample(time="1Y").max()
    else:
        annual_extremes = data.resample(time="1Y").min()
    extremes = annual_extremes.values[~np.isnan(annual_extremes.values)]

    if len(extremes) < 5:
        logger.warning("Insufficient data for return period calculation")
        return {}

    # Simple Gumbel distribution approximation
    # For proper analysis, use scipy.stats.gumbel_r or genextreme
    mean_extreme = np.mean(extremes)
    std_extreme = np.std(extremes)
    results = {
        "variable": variable,
        "type": extreme_type,
        "n_years": len(extremes),
        "mean_annual_extreme": float(mean_extreme),
        "std_annual_extreme": float(std_extreme),
        "return_values": {},
    }

    # Gumbel reduced variate
    for T in return_years:
        if T <= len(extremes) * 2:  # Only extrapolate to 2x data length
            y_T = -np.log(-np.log(1 - 1 / T))  # Gumbel reduced variate

            # Simplified estimation (Gumbel method of moments)
            alpha = np.pi / (std_extreme * np.sqrt(6))
            u = mean_extreme - 0.5772 / alpha  # Euler's constant

            if extreme_type == "max":
                x_T = u + y_T / alpha
            else:
                x_T = u - y_T / alpha

            results["return_values"][f"{T}_year"] = float(x_T)

    # Add observed percentiles for reference
    results["observed_percentiles"] = (
        {
            "p90": float(np.percentile(extremes, 90)),
            "p95": float(np.percentile(extremes, 95)),
            "p99": float(np.percentile(extremes, 99)) if len(extremes) > 100 else None,
        },
    )

    return results


def summarize_extremes(ds: xr.Dataset) -> dict:
    """
    Comprehensive summary of extreme events in the dataset.

    Args:
        ds: Climate dataset

    Returns:
        Dictionary with extreme event summary,
    """
    summary = {"temperature": {}, "precipitation": {}, "wind": {}, "solar": {}}

    # Temperature extremes
    if "temp_air" in ds:
        heat_waves = identify_heat_waves(ds)
        cold_snaps = identify_cold_snaps(ds)

        summary["temperature"] = {
            "n_heat_waves": len(heat_waves),
            "n_cold_snaps": len(cold_snaps),
            "longest_heat_wave_days": (max([h["duration_days"] for h in heat_waves]) if heat_waves else 0),
            "longest_cold_snap_days": (max([c["duration_days"] for c in cold_snaps]) if cold_snaps else 0),
            "return_periods": calculate_return_periods(ds, "temp_air", extreme_type="max"),
        }

    # Wind extremes
    if "wind_speed" in ds:
        wind_extremes = find_extreme_events(ds, "wind_speed", threshold_percentile=99, min_duration_hours=6)
        summary["wind"] = {
            "n_high_wind_events": len(wind_extremes),
            "max_wind_speed": float(ds["wind_speed"].max()),
            "return_periods": calculate_return_periods(ds, "wind_speed", extreme_type="max"),
        }

    # Precipitation extremes
    if "precip" in ds:
        heavy_rain = find_extreme_events(ds, "precip", threshold_percentile=95, min_duration_hours=1)
        summary["precipitation"] = (
            {
                "n_heavy_rain_events": len(heavy_rain),
                "max_hourly_precip": float(ds["precip"].max()) if "precip" in ds else None,
            },
        )

    return summary
