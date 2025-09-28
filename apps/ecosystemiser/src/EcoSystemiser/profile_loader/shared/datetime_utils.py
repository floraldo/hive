"""
Enhanced date/time utilities with pandas optimizations.

This module provides comprehensive date/time handling capabilities,
building on the existing timezone and timeseries modules with modern
pandas best practices and performance optimizations.
"""

import warnings
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from EcoSystemiser.hive_logging_adapter import get_logger
import numpy as np
import pandas as pd
import xarray as xr

from EcoSystemiser.profile_loader.shared.timezone import TimezoneHandler, to_utc, ensure_utc

logger = get_logger(__name__)

class DateTimeProcessor:
    """
    Enhanced date/time processing with pandas optimizations.

    Provides high-level operations for profile data time handling,
    including frequency inference, gap detection, resampling, and
    period management.
    """

    # Standard frequency mappings
    FREQ_ALIASES = {
        # Input variations -> pandas frequency
        "minutely": "1T",
        "5min": "5T",
        "15min": "15T",
        "30min": "30T",
        "half_hourly": "30T",
        "hourly": "1H",
        "daily": "1D",
        "weekly": "1W",
        "monthly": "1M",
        "yearly": "1Y",
        "annual": "1Y"
    }

    @classmethod
    def normalize_period(cls, period: Dict[str, Any]) -> Dict[str, pd.Timestamp]:
        """
        Normalize period specification to pandas Timestamps.

        Args:
            period: Period specification with various formats

        Returns:
            Normalized period with 'start' and 'end' Timestamps

        Examples:
            {"year": 2023} -> {"start": "2023-01-01", "end": "2023-12-31"}
            {"start": "2023-01-01", "end": "2023-12-31"} -> normalized
            {"months": ["06", "07", "08"], "year": 2023} -> summer 2023
        """
        normalized = {}

        if "start" in period and "end" in period:
            # Direct start/end specification
            normalized["start"] = pd.to_datetime(period["start"], utc=True)
            normalized["end"] = pd.to_datetime(period["end"], utc=True)

        elif "year" in period:
            year = int(period["year"])

            if "months" in period:
                # Specific months within year
                months = period["months"]
                if isinstance(months, (list, tuple)):
                    start_month = int(months[0])
                    end_month = int(months[-1])
                else:
                    start_month = end_month = int(months)

                normalized["start"] = pd.Timestamp(year, start_month, 1, tz="UTC")

                # End of last month
                if end_month == 12:
                    normalized["end"] = pd.Timestamp(year + 1, 1, 1, tz="UTC") - pd.Timedelta(seconds=1)
                else:
                    normalized["end"] = pd.Timestamp(year, end_month + 1, 1, tz="UTC") - pd.Timedelta(seconds=1)

            elif "month" in period:
                # Single month
                month = int(period["month"])
                normalized["start"] = pd.Timestamp(year, month, 1, tz="UTC")
                if month == 12:
                    normalized["end"] = pd.Timestamp(year + 1, 1, 1, tz="UTC") - pd.Timedelta(seconds=1)
                else:
                    normalized["end"] = pd.Timestamp(year, month + 1, 1, tz="UTC") - pd.Timedelta(seconds=1)

            else:
                # Full year
                normalized["start"] = pd.Timestamp(year, 1, 1, tz="UTC")
                normalized["end"] = pd.Timestamp(year + 1, 1, 1, tz="UTC") - pd.Timedelta(seconds=1)

        elif "duration" in period:
            # Duration-based period
            end_time = pd.to_datetime(period.get("end", "now"), utc=True)
            duration = pd.Timedelta(period["duration"])
            normalized["start"] = end_time - duration
            normalized["end"] = end_time

        else:
            # Default to current year
            current_year = datetime.now().year
            normalized["start"] = pd.Timestamp(current_year, 1, 1, tz="UTC")
            normalized["end"] = pd.Timestamp(current_year + 1, 1, 1, tz="UTC") - pd.Timedelta(seconds=1)

        return normalized

    @classmethod
    def normalize_frequency(cls, frequency: Union[str, None]) -> str:
        """
        Normalize frequency specification to pandas frequency string.

        Args:
            frequency: Input frequency specification

        Returns:
            Pandas-compatible frequency string
        """
        if frequency is None:
            return "1H"  # Default to hourly

        # Handle aliases
        freq_lower = frequency.lower()
        if freq_lower in cls.FREQ_ALIASES:
            return cls.FREQ_ALIASES[freq_lower]

        # Pass through pandas frequency strings
        return frequency

    @classmethod
    def create_time_index(
        cls,
        start: Union[str, datetime, pd.Timestamp],
        end: Union[str, datetime, pd.Timestamp],
        freq: str = "1H",
        timezone: str = "UTC"
    ) -> pd.DatetimeIndex:
        """
        Create optimized pandas DatetimeIndex.

        Args:
            start: Start time
            end: End time
            freq: Frequency string
            timezone: Timezone name

        Returns:
            DatetimeIndex with proper timezone handling
        """
        # Normalize inputs
        start_ts = pd.to_datetime(start, utc=(timezone == "UTC"))
        end_ts = pd.to_datetime(end, utc=(timezone == "UTC"))
        freq_norm = cls.normalize_frequency(freq)

        # Create index
        if timezone == "UTC":
            index = pd.date_range(start=start_ts, end=end_ts, freq=freq_norm, tz="UTC")
        else:
            # Use timezone handler for complex timezones
            index = pd.date_range(start=start_ts, end=end_ts, freq=freq_norm)
            index = TimezoneHandler.handle_dst_transition(index, timezone)

        return index

    @classmethod
    def infer_frequency_robust(cls, time_index: pd.DatetimeIndex) -> Optional[str]:
        """
        Robustly infer frequency from DatetimeIndex.

        Handles irregular timestamps and provides fallback strategies.

        Args:
            time_index: DatetimeIndex to analyze

        Returns:
            Inferred frequency string or None
        """
        if len(time_index) < 2:
            return None

        try:
            # Try pandas built-in inference first
            inferred = pd.infer_freq(time_index)
            if inferred:
                return inferred
        except Exception as e:
            pass

        # Manual inference for common cases
        time_diffs = time_index[1:] - time_index[:-1]

        # Get most common time difference
        diff_counts = pd.Series(time_diffs).value_counts()
        most_common_diff = diff_counts.index[0]

        # Convert to frequency string
        total_seconds = most_common_diff.total_seconds()

        if total_seconds == 60:
            return "1T"  # 1 minute
        elif total_seconds == 300:
            return "5T"  # 5 minutes
        elif total_seconds == 900:
            return "15T"  # 15 minutes
        elif total_seconds == 1800:
            return "30T"  # 30 minutes
        elif total_seconds == 3600:
            return "1H"  # 1 hour
        elif total_seconds == 10800:
            return "3H"  # 3 hours
        elif total_seconds == 86400:
            return "1D"  # 1 day
        elif total_seconds == 604800:
            return "1W"  # 1 week
        else:
            # Custom frequency
            if total_seconds < 3600:
                minutes = int(total_seconds / 60)
                return f"{minutes}T"
            elif total_seconds < 86400:
                hours = int(total_seconds / 3600)
                return f"{hours}H"
            else:
                days = int(total_seconds / 86400)
                return f"{days}D"

    @classmethod
    def detect_gaps(
        cls,
        time_index: pd.DatetimeIndex,
        expected_freq: Optional[str] = None,
        tolerance_factor: float = 1.5
    ) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
        """
        Detect gaps in time series.

        Args:
            time_index: DatetimeIndex to check
            expected_freq: Expected frequency (inferred if None)
            tolerance_factor: Gap tolerance as multiple of expected interval

        Returns:
            List of (gap_start, gap_end) tuples
        """
        if len(time_index) < 2:
            return []

        # Infer frequency if not provided
        if expected_freq is None:
            expected_freq = cls.infer_frequency_robust(time_index)
            if expected_freq is None:
                return []

        # Calculate expected interval
        expected_delta = pd.Timedelta(expected_freq)
        tolerance_delta = expected_delta * tolerance_factor

        # Find gaps
        gaps = []
        time_diffs = time_index[1:] - time_index[:-1]

        for i, diff in enumerate(time_diffs):
            if diff > tolerance_delta:
                gap_start = time_index[i]
                gap_end = time_index[i + 1]
                gaps.append((gap_start, gap_end))

        return gaps

    @classmethod
    def resample_with_metadata(
        cls,
        data: Union[pd.DataFrame, pd.Series, xr.Dataset],
        target_freq: str,
        method: str = "mean",
        preserve_attrs: bool = True
    ) -> Union[pd.DataFrame, pd.Series, xr.Dataset]:
        """
        Resample data with metadata preservation.

        Args:
            data: Input data
            target_freq: Target frequency
            method: Resampling method
            preserve_attrs: Whether to preserve xarray attributes

        Returns:
            Resampled data with preserved metadata
        """
        target_freq_norm = cls.normalize_frequency(target_freq)

        if isinstance(data, (pd.DataFrame, pd.Series)):
            # Pandas resampling
            resampler = data.resample(target_freq_norm)

            if method == "mean":
                result = resampler.mean()
            elif method == "sum":
                result = resampler.sum()
            elif method == "max":
                result = resampler.max()
            elif method == "min":
                result = resampler.min()
            elif method == "median":
                result = resampler.median()
            elif method == "first":
                result = resampler.first()
            elif method == "last":
                result = resampler.last()
            else:
                result = resampler.mean()

            return result

        elif isinstance(data, xr.Dataset):
            # XArray resampling
            resampler = data.resample(time=target_freq_norm)

            if method == "mean":
                result = resampler.mean()
            elif method == "sum":
                result = resampler.sum()
            elif method == "max":
                result = resampler.max()
            elif method == "min":
                result = resampler.min()
            elif method == "median":
                result = resampler.median()
            else:
                result = resampler.mean()

            # Preserve attributes
            if preserve_attrs:
                result.attrs = data.attrs.copy()
                for var in result.data_vars:
                    if var in data.data_vars:
                        result[var].attrs = data[var].attrs.copy()

            return result

        else:
            raise TypeError(f"Unsupported data type: {type(data)}")

    @classmethod
    def align_time_series(
        cls,
        *datasets: Union[pd.DataFrame, pd.Series, xr.Dataset],
        method: str = "outer",
        fill_value: Optional[Any] = None
    ) -> List[Union[pd.DataFrame, pd.Series, xr.Dataset]]:
        """
        Align multiple time series to common time index.

        Args:
            *datasets: Multiple datasets to align
            method: Alignment method ('inner', 'outer', 'left', 'right')
            fill_value: Value for missing data

        Returns:
            List of aligned datasets
        """
        if len(datasets) < 2:
            return list(datasets)

        # Separate pandas and xarray datasets
        pandas_data = []
        xarray_data = []

        for i, data in enumerate(datasets):
            if isinstance(data, (pd.DataFrame, pd.Series)):
                pandas_data.append((i, data))
            elif isinstance(data, xr.Dataset):
                xarray_data.append((i, data))
            else:
                raise TypeError(f"Unsupported data type at index {i}: {type(data)}")

        aligned = [None] * len(datasets)

        # Align pandas data
        if pandas_data:
            pandas_datasets = [data for _, data in pandas_data]
            pandas_indices = [data.index for data in pandas_datasets]

            # Find common time index
            if method == "inner":
                common_index = pandas_indices[0]
                for idx in pandas_indices[1:]:
                    common_index = common_index.intersection(idx)
            elif method == "outer":
                common_index = pandas_indices[0]
                for idx in pandas_indices[1:]:
                    common_index = common_index.union(idx)
            else:
                common_index = pandas_indices[0]  # Use first as reference

            # Reindex all pandas datasets
            for orig_idx, data in pandas_data:
                aligned_data = data.reindex(common_index, fill_value=fill_value)
                aligned[orig_idx] = aligned_data

        # Align xarray data
        if xarray_data:
            xarray_datasets = [data for _, data in xarray_data]

            # Use xarray's built-in alignment
            aligned_xr = xr.align(*xarray_datasets, join=method, fill_value=fill_value)

            for i, (orig_idx, _) in enumerate(xarray_data):
                aligned[orig_idx] = aligned_xr[i]

        return aligned

    @classmethod
    def validate_temporal_consistency(
        cls,
        data: Union[pd.DataFrame, pd.Series, xr.Dataset],
        expected_freq: Optional[str] = None,
        timezone: str = "UTC"
    ) -> Dict[str, Any]:
        """
        Validate temporal consistency of dataset.

        Args:
            data: Dataset to validate
            expected_freq: Expected frequency
            timezone: Expected timezone

        Returns:
            Validation report with issues and metrics
        """
        report = {
            "valid": True,
            "issues": [],
            "metrics": {},
            "recommendations": []
        }

        # Get time index
        if isinstance(data, (pd.DataFrame, pd.Series)):
            time_index = data.index
        elif isinstance(data, xr.Dataset):
            if "time" not in data.dims:
                report["valid"] = False
                report["issues"].append("No time dimension found")
                return report
            time_index = pd.DatetimeIndex(data.time.values)
        else:
            report["valid"] = False
            report["issues"].append(f"Unsupported data type: {type(data)}")
            return report

        # Check if time index is sorted
        if not time_index.is_monotonic_increasing:
            report["valid"] = False
            report["issues"].append("Time index is not sorted")
            report["recommendations"].append("Sort by time index")

        # Check for duplicates
        if time_index.has_duplicates:
            report["valid"] = False
            duplicates = time_index.duplicated().sum()
            report["issues"].append(f"Found {duplicates} duplicate timestamps")
            report["recommendations"].append("Remove duplicate timestamps")

        # Infer frequency
        inferred_freq = cls.infer_frequency_robust(time_index)
        report["metrics"]["inferred_frequency"] = inferred_freq

        if expected_freq:
            expected_freq_norm = cls.normalize_frequency(expected_freq)
            if inferred_freq != expected_freq_norm:
                report["issues"].append(
                    f"Frequency mismatch: expected {expected_freq_norm}, got {inferred_freq}"
                )

        # Check for gaps
        gaps = cls.detect_gaps(time_index, expected_freq or inferred_freq)
        report["metrics"]["gap_count"] = len(gaps)
        if gaps:
            report["issues"].append(f"Found {len(gaps)} temporal gaps")
            report["recommendations"].append("Consider gap filling or resampling")

        # Timezone validation
        if isinstance(data, xr.Dataset):
            tz_issues = TimezoneHandler.validate_timezone_consistency(data, timezone)
            if tz_issues:
                report["issues"].extend(tz_issues)
                report["recommendations"].append("Normalize timezone handling")

        # Coverage metrics
        if len(time_index) > 0:
            report["metrics"]["start_time"] = time_index[0]
            report["metrics"]["end_time"] = time_index[-1]
            report["metrics"]["duration"] = time_index[-1] - time_index[0]
            report["metrics"]["data_points"] = len(time_index)

        # Set overall validity
        report["valid"] = len(report["issues"]) == 0

        return report

    @classmethod
    def optimize_time_index(
        cls,
        time_index: pd.DatetimeIndex,
        target_memory_mb: float = 100.0
    ) -> pd.DatetimeIndex:
        """
        Optimize DatetimeIndex for memory efficiency.

        Args:
            time_index: Input DatetimeIndex
            target_memory_mb: Target memory usage in MB

        Returns:
            Optimized DatetimeIndex
        """
        # Current memory usage
        current_memory = time_index.memory_usage(deep=True) / (1024 * 1024)  # MB

        if current_memory <= target_memory_mb:
            return time_index

        # Try to optimize by reducing frequency resolution
        current_freq = cls.infer_frequency_robust(time_index)
        if current_freq is None:
            return time_index

        # Estimate how much we need to reduce resolution
        reduction_factor = current_memory / target_memory_mb

        # Suggest coarser frequency
        if "T" in current_freq:  # Minutes
            minutes = int(current_freq.replace("T", ""))
            new_minutes = int(minutes * reduction_factor)
            suggested_freq = f"{new_minutes}T"
        elif "H" in current_freq:  # Hours
            hours = int(current_freq.replace("H", ""))
            new_hours = int(hours * reduction_factor)
            suggested_freq = f"{new_hours}H"
        else:
            # For other frequencies, suggest hourly
            suggested_freq = "1H"

        logger.info(
            f"Time index memory usage {current_memory:.1f}MB exceeds target {target_memory_mb}MB. "
            f"Consider resampling from {current_freq} to {suggested_freq}"
        )

        return time_index

# Convenience functions for common operations

def create_time_range(
    start: Union[str, datetime],
    end: Union[str, datetime],
    freq: str = "1H",
    timezone: str = "UTC"
) -> pd.DatetimeIndex:
    """Create optimized time range."""
    return DateTimeProcessor.create_time_index(start, end, freq, timezone)

def resample_data(
    data: Union[pd.DataFrame, pd.Series, xr.Dataset],
    target_freq: str,
    method: str = "mean"
) -> Union[pd.DataFrame, pd.Series, xr.Dataset]:
    """Resample data with metadata preservation."""
    return DateTimeProcessor.resample_with_metadata(data, target_freq, method)

def align_datasets(
    *datasets: Union[pd.DataFrame, pd.Series, xr.Dataset],
    method: str = "outer"
) -> List[Union[pd.DataFrame, pd.Series, xr.Dataset]]:
    """Align multiple datasets to common time index."""
    return DateTimeProcessor.align_time_series(*datasets, method=method)

def validate_time_data(
    data: Union[pd.DataFrame, pd.Series, xr.Dataset],
    expected_freq: Optional[str] = None
) -> Dict[str, Any]:
    """Validate temporal consistency."""
    return DateTimeProcessor.validate_temporal_consistency(data, expected_freq)

def normalize_period_spec(period: Dict[str, Any]) -> Dict[str, pd.Timestamp]:
    """Normalize period specification."""
    return DateTimeProcessor.normalize_period(period)

def detect_time_gaps(
    time_index: pd.DatetimeIndex,
    expected_freq: Optional[str] = None
) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
    """Detect gaps in time series."""
    return DateTimeProcessor.detect_gaps(time_index, expected_freq)