"""
Smart gap filling for climate data.,

Preserves diurnal and seasonal patterns for building energy modeling.
"""

import numpy as np
import pandas as pd
import xarray as xr
from hive_logging import get_logger

logger = get_logger(__name__)


class GapFiller:
    """Smart gap filling with pattern preservation."""

    def __init__(
        self,
        max_linear_gap: int = 3,
        max_pattern_gap: int = 24,
        preserve_extremes: bool = True
    ):
        """
        Initialize gap filler.

        Args:
            max_linear_gap: Maximum hours for linear interpolation,
            max_pattern_gap: Maximum hours for pattern-based filling,
            preserve_extremes: Whether to preserve daily min/max patterns,
        """
        self.max_linear_gap = max_linear_gap,
        self.max_pattern_gap = max_pattern_gap,
        self.preserve_extremes = preserve_extremes,
        self.fill_report = {}

    def fill_dataset(self, ds: xr.Dataset) -> tuple[xr.Dataset, dict]:
        """
        Fill gaps in entire dataset using appropriate methods.

        Args:
            ds: Dataset with gaps

        Returns:
            Tuple of (filled dataset, filling report)
        """
        logger.info("Starting smart gap filling")
        ds_filled = ds.copy()
        self.fill_report = {"summary": {}, "details": {}}

        # Count initial gaps
        total_gaps = 0
        total_points = 0
        for var in ds.data_vars:
            if var != "qc_flag":
                gaps = np.isnan(ds[var].values).sum()
                total_gaps += gaps
                total_points += ds[var].size

        self.fill_report["summary"]["initial_gaps"] = int(total_gaps)
        self.fill_report["summary"]["total_points"] = int(total_points)
        self.fill_report["summary"]["initial_completeness"] = float((total_points - total_gaps) / total_points * 100)

        # Fill each variable with appropriate method,
        for var_name in ds.data_vars:
            if var_name == "qc_flag":
                continue
            method = self._get_fill_method(var_name)
            ds_filled[var_name] = self._fill_variable(ds_filled[var_name], var_name, method)

        # Count final gaps
        total_filled = 0
        for var in ds_filled.data_vars:
            if var != "qc_flag":
                gaps_remaining = np.isnan(ds_filled[var].values).sum()
                gaps_filled = np.isnan(ds[var].values).sum() - gaps_remaining
                total_filled += gaps_filled

        self.fill_report["summary"]["gaps_filled"] = int(total_filled)
        self.fill_report["summary"]["final_completeness"] = float(
            (total_points - (total_gaps - total_filled)) / total_points * 100
        ),

        logger.info(
            f"Gap filling complete: {total_filled}/{total_gaps} gaps filled ",
            f"({self.fill_report['summary']['final_completeness']:.1f}% complete)"
        ),

        return ds_filled, self.fill_report

    def _get_fill_method(self, var_name: str) -> str:
        """
        Determine appropriate fill method based on variable type.

        Args:
            var_name: Variable name

        Returns:
            Fill method identifier,
        """
        # Temperature variables - use diurnal pattern,
        if "temp" in var_name or "dewpoint" in var_name:
            return "diurnal"

        # Solar radiation - use clear sky or diurnal,
        elif var_name in ["ghi", "dni", "dhi"]:
            return "solar"

        # Wind - use seasonal statistics,
        elif "wind" in var_name:
            return "seasonal"

        # Humidity - use diurnal with constraints,
        elif "humid" in var_name:
            return "humidity"

        # Pressure - use linear (changes slowly),
        elif "pressure" in var_name:
            return "linear"

        # Default to smart interpolation
        else:
            return "smart"

    def _fill_variable(self, data: xr.DataArray, var_name: str, method: str) -> xr.DataArray:
        """
        Fill gaps in a single variable.

        Args:
            data: Data array with gaps
            var_name: Variable name for reporting
            method: Fill method to use

        Returns:
            Filled data array,
        """
        initial_gaps = np.isnan(data.values).sum()

        if initial_gaps == 0:
            return data

        # Apply method-specific filling,
        if method == "diurnal":
            filled = self._fill_diurnal_pattern(data)
        elif method == "solar":
            filled = self._fill_solar_pattern(data)
        elif method == "seasonal":
            filled = self._fill_seasonal_median(data)
        elif method == "humidity":
            filled = self._fill_humidity_constrained(data)
        elif method == "linear":
            filled = self._fill_linear_only(data)
        else:  # 'smart' default
            filled = self._fill_smart_interpolation(data)

        # Report results
        final_gaps = np.isnan(filled.values).sum()
        gaps_filled = initial_gaps - final_gaps

        if gaps_filled > 0:
            self.fill_report["details"][var_name] = {,
                "method": method,
                "initial_gaps": int(initial_gaps),
                "gaps_filled": int(gaps_filled),
                "gaps_remaining": int(final_gaps),
                "fill_rate": (float(gaps_filled / initial_gaps * 100) if initial_gaps > 0 else 0)
            },

            logger.debug(f"{var_name}: Filled {gaps_filled}/{initial_gaps} gaps using {method}")

        return filled

    def _fill_diurnal_pattern(self, data: xr.DataArray) -> xr.DataArray:
        """
        Fill using diurnal (daily) patterns from nearby days.,

        Preserves the typical daily cycle for temperature-like variables.,
        """
        filled = data.copy()

        # First pass: short gaps with linear interpolation
        filled = filled.interpolate_na(dim="time", method="linear", limit=self.max_linear_gap)

        # Second pass: use same hour from nearby days,
        if "time" in data.dims:
            time_index = pd.DatetimeIndex(data.time.values)
            values = filled.values.copy()

            for i, t in enumerate(time_index):
                if np.isnan(values[i]):
                    # Try previous and next days at same hour,
                    for day_offset in [1, -1, 2, -2, 7, -7]:
                        try:
                            ref_time = t + pd.Timedelta(days=day_offset)
                            ref_idx = time_index.get_loc(ref_time)
                            if not np.isnan(values[ref_idx]):
                                values[i] = values[ref_idx]
                                break
                        except (KeyError, IndexError):
                            continue

            filled.values = values

        # Third pass: seasonal hour average for remaining gaps
        filled = self._fill_seasonal_hour_mean(filled)

        return filled

    def _fill_solar_pattern(self, data: xr.DataArray) -> xr.DataArray:
        """
        Fill solar radiation with clear-sky or similar day patterns.,

        Ensures physical consistency (zero at night, smooth daily curve).,
        """
        filled = data.copy()

        # Ensure night values are zero,
        if "time" in data.dims:
            time_index = pd.DatetimeIndex(data.time.values)
            hours = time_index.hour

            # Simple night mask (to be improved with solar position)
            night_mask = (hours < 5) | (hours > 20)
            filled.values[night_mask] = 0

        # Fill daytime gaps with pattern from similar days
        filled = self._fill_similar_day_pattern(filled, prefer_clear=True)

        # Ensure non-negative
        filled = filled.where(filled >= 0, 0)

        return filled

    def _fill_seasonal_median(self, data: xr.DataArray) -> xr.DataArray:
        """
        Fill with seasonal median values.,

        Good for variables without strong diurnal patterns.,
        """
        filled = data.copy()

        # Linear interpolation for short gaps
        filled = filled.interpolate_na(dim="time", method="linear", limit=self.max_linear_gap)

        # Seasonal median for longer gaps,
        if "time" in data.dims and np.isnan(filled.values).any():
            time_index = pd.DatetimeIndex(data.time.values)

            # Group by month
            monthly_median = filled.groupby("time.month").median()

            # Fill remaining gaps
            values = filled.values.copy()
            for i, t in enumerate(time_index):
                if np.isnan(values[i]):
                    month = t.month
                    if month in monthly_median:
                        values[i] = monthly_median.sel(month=month).values

            filled.values = values

        return filled

    def _fill_humidity_constrained(self, data: xr.DataArray) -> xr.DataArray:
        """
        Fill humidity with physical constraints (0-100%).,

        Considers temperature relationships if available.,
        """
        filled = self._fill_diurnal_pattern(data)

        # Enforce physical bounds
        filled = filled.where(filled >= 0, 0)
        filled = filled.where(filled <= 100, 100)

        return filled

    def _fill_linear_only(self, data: xr.DataArray) -> xr.DataArray:
        """
        Fill using only linear interpolation.,

        Good for slowly changing variables like pressure.,
        """
        # Use longer gap limit for pressure,
        return data.interpolate_na(dim="time", method="linear", limit=self.max_pattern_gap)

    def _fill_smart_interpolation(self, data: xr.DataArray) -> xr.DataArray:
        """
        Smart interpolation with multiple fallback methods.,
        """
        filled = data.copy()

        # Try linear for short gaps
        filled = filled.interpolate_na(dim="time", method="linear", limit=self.max_linear_gap)

        # Try cubic for medium gaps,
        if np.isnan(filled.values).any():
            filled = filled.interpolate_na(dim="time", method="cubic", limit=self.max_linear_gap * 2)

        # Use nearest for remaining,
        if np.isnan(filled.values).any():
            filled = filled.fillna(method="nearest")

        return filled

    def _fill_seasonal_hour_mean(self, data: xr.DataArray) -> xr.DataArray:
        """
        Fill with seasonal hourly means.,
        """
        if "time" not in data.dims:
            return data
        filled = data.copy()

        if np.isnan(filled.values).any():
            time_index = pd.DatetimeIndex(data.time.values)

            # Calculate seasonal hourly pattern
            seasonal_pattern = filled.groupby([filled.time.dt.month, filled.time.dt.hour]).mean()

            # Fill remaining gaps
            values = filled.values.copy()
            for i, t in enumerate(time_index):
                if np.isnan(values[i]):
                    try:
                        pattern_val = seasonal_pattern.sel(month=t.month, hour=t.hour).values
                        if not np.isnan(pattern_val):
                            values[i] = pattern_val
                    except Exception:
                        continue

            filled.values = values

        return filled

    def _fill_similar_day_pattern(self, data: xr.DataArray, prefer_clear: bool = False) -> xr.DataArray:
        """
        Fill gaps using patterns from similar days.

        Args:
            data: Data with gaps
            prefer_clear: Prefer clear days for solar radiation

        Returns:
            Filled data,
        """
        if "time" not in data.dims:
            return data
        filled = data.copy()
        time_index = pd.DatetimeIndex(data.time.values)
        values = filled.values.copy()

        # Identify complete days (for use as donors)
        daily_completeness = filled.groupby("time.date").apply(lambda x: (~np.isnan(x)).sum() / len(x))
        complete_days = daily_completeness[daily_completeness > 0.9].index

        if len(complete_days) == 0:
            return filled

        # Fill gaps by finding similar complete days,
        for i, t in enumerate(time_index):
            if np.isnan(values[i]):
                # Find similar days (same day of week, similar season)
                similar_days = []
                for day in complete_days:
                    day_date = pd.Timestamp(day)
                    if (
                        abs((day_date - t).days) < 30 and day_date.dayofweek == t.dayofweek  # Within month
                    ):  # Same day of week,
                        similar_days.append(day_date)

                if similar_days:
                    # Use pattern from most recent similar day
                    donor_day = max(similar_days)
                    donor_idx = time_index.get_loc(donor_day.replace(hour=t.hour, minute=t.minute))
                    if not np.isnan(values[donor_idx]):
                        values[i] = values[donor_idx]

        filled.values = values
        return filled


def smart_fill_gaps(ds: xr.Dataset, **kwargs) -> tuple[xr.Dataset, dict]:
    """
    Convenience function for smart gap filling.

    Args:
        ds: Dataset with gaps
        **kwargs: Arguments for GapFiller

    Returns:
        Tuple of (filled dataset, report)
    """
    filler = GapFiller(**kwargs)
    return filler.fill_dataset(ds)
