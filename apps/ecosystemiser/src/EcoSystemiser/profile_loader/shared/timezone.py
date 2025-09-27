"""
Timezone handling utilities using modern zoneinfo (PEP 615).

Replaces pytz with standard library zoneinfo for better timezone handling,
fixes DST edge cases, and provides standardized UTC conversion.
"""

import sys
from datetime import datetime, timezone
from typing import Optional, Union, List
from EcoSystemiser.hive_logging_adapter import get_logger
import pandas as pd
import numpy as np
import xarray as xr

# Use zoneinfo from Python 3.9+ or backport
if sys.version_info >= (3, 9):
    from zoneinfo import ZoneInfo
else:
    try:
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        raise ImportError(
            "zoneinfo requires Python 3.9+ or backports.zoneinfo package. "
            "Install with: pip install backports.zoneinfo"
        )

logger = get_logger(__name__)

class TimezoneHandler:
    """
    Centralized timezone handling for climate data.
    
    Ensures all internal data uses UTC while supporting local time
    for input/output when needed.
    """
    
    # Common timezone aliases
    TIMEZONE_ALIASES = {
        'PST': 'America/Los_Angeles',
        'PDT': 'America/Los_Angeles',
        'MST': 'America/Denver', 
        'MDT': 'America/Denver',
        'CST': 'America/Chicago',
        'CDT': 'America/Chicago',
        'EST': 'America/New_York',
        'EDT': 'America/New_York',
        'GMT': 'UTC',
        'BST': 'Europe/London',
        'CET': 'Europe/Paris',
        'CEST': 'Europe/Paris',
    }
    
    @staticmethod
    def normalize_to_utc(
        timestamp: Union[datetime, pd.Timestamp, pd.DatetimeIndex, np.datetime64],
        source_tz: Optional[str] = None
    ) -> Union[datetime, pd.Timestamp, pd.DatetimeIndex]:
        """
        Normalize any timestamp to UTC.
        
        Args:
            timestamp: Input timestamp (naive or aware)
            source_tz: Source timezone if timestamp is naive
            
        Returns:
            UTC timestamp with timezone info
        """
        # Handle different timestamp types
        if isinstance(timestamp, np.datetime64):
            timestamp = pd.Timestamp(timestamp)
        
        if isinstance(timestamp, pd.DatetimeIndex):
            return TimezoneHandler._normalize_index_to_utc(timestamp, source_tz)
        
        if isinstance(timestamp, pd.Timestamp):
            return TimezoneHandler._normalize_timestamp_to_utc(timestamp, source_tz)
        
        if isinstance(timestamp, datetime):
            return TimezoneHandler._normalize_datetime_to_utc(timestamp, source_tz)
        
        raise TypeError(f"Unsupported timestamp type: {type(timestamp)}")
    
    @staticmethod
    def _normalize_datetime_to_utc(
        dt: datetime,
        source_tz: Optional[str] = None
    ) -> datetime:
        """Normalize datetime to UTC"""
        if dt.tzinfo is None:
            # Naive datetime - localize to source timezone
            if source_tz:
                tz = TimezoneHandler._get_timezone(source_tz)
                dt = dt.replace(tzinfo=tz)
            else:
                # Assume UTC if no source timezone specified
                dt = dt.replace(tzinfo=timezone.utc)
        
        # Convert to UTC
        return dt.astimezone(timezone.utc)
    
    @staticmethod
    def _normalize_timestamp_to_utc(
        ts: pd.Timestamp,
        source_tz: Optional[str] = None
    ) -> pd.Timestamp:
        """Normalize pandas Timestamp to UTC"""
        if ts.tz is None:
            # Naive timestamp - localize to source timezone
            if source_tz:
                tz = TimezoneHandler._get_timezone(source_tz)
                ts = ts.tz_localize(tz)
            else:
                # Assume UTC if no source timezone specified
                ts = ts.tz_localize('UTC')
        
        # Convert to UTC
        return ts.tz_convert('UTC')
    
    @staticmethod
    def _normalize_index_to_utc(
        index: pd.DatetimeIndex,
        source_tz: Optional[str] = None
    ) -> pd.DatetimeIndex:
        """Normalize pandas DatetimeIndex to UTC"""
        if index.tz is None:
            # Naive index - localize to source timezone
            if source_tz:
                tz = TimezoneHandler._get_timezone(source_tz)
                index = index.tz_localize(tz)
            else:
                # Assume UTC if no source timezone specified
                index = index.tz_localize('UTC')
        
        # Convert to UTC
        return index.tz_convert('UTC')
    
    @staticmethod
    def localize_from_utc(
        timestamp: Union[datetime, pd.Timestamp, pd.DatetimeIndex],
        target_tz: str
    ) -> Union[datetime, pd.Timestamp, pd.DatetimeIndex]:
        """
        Convert UTC timestamp to local timezone.
        
        Args:
            timestamp: UTC timestamp
            target_tz: Target timezone name
            
        Returns:
            Localized timestamp
        """
        tz = TimezoneHandler._get_timezone(target_tz)
        
        if isinstance(timestamp, pd.DatetimeIndex):
            return timestamp.tz_convert(tz)
        
        if isinstance(timestamp, pd.Timestamp):
            return timestamp.tz_convert(tz)
        
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            return timestamp.astimezone(tz)
        
        raise TypeError(f"Unsupported timestamp type: {type(timestamp)}")
    
    @staticmethod
    def _get_timezone(tz_name: str) -> Union[ZoneInfo, timezone]:
        """
        Get timezone object from name.
        
        Handles aliases and special cases.
        """
        # Handle UTC special case
        if tz_name.upper() in ['UTC', 'Z']:
            return timezone.utc
        
        # Check aliases
        if tz_name in TimezoneHandler.TIMEZONE_ALIASES:
            tz_name = TimezoneHandler.TIMEZONE_ALIASES[tz_name]
        
        try:
            return ZoneInfo(tz_name)
        except Exception as e:
            logger.warning(f"Unknown timezone '{tz_name}', using UTC: {e}")
            return timezone.utc
    
    @staticmethod
    def ensure_utc_dataset(ds: xr.Dataset) -> xr.Dataset:
        """
        Ensure xarray Dataset uses UTC timestamps.
        
        Args:
            ds: Input dataset
            
        Returns:
            Dataset with UTC timestamps
        """
        if 'time' not in ds.dims:
            return ds
        
        # Get time coordinate
        time_coord = ds.time
        
        # Check if it's already UTC (via attributes)
        if 'timezone' in ds.time.attrs and ds.time.attrs['timezone'] == 'UTC':
            return ds
        
        # Convert to pandas for timezone handling
        time_index = pd.to_datetime(time_coord.values)
        
        # Check if the pandas index is timezone-aware
        if time_index.tz is not None:
            # If already timezone-aware, convert to UTC
            time_index_utc = time_index.tz_convert('UTC')
        else:
            # If naive, assume UTC (or use source_tz if provided in attrs)
            source_tz = ds.time.attrs.get('timezone', 'UTC')
            if source_tz != 'UTC':
                # Localize to source timezone first
                tz = TimezoneHandler._get_timezone(source_tz)
                time_index = time_index.tz_localize(tz)
                time_index_utc = time_index.tz_convert('UTC')
            else:
                # Already in UTC, just make it aware
                time_index_utc = time_index.tz_localize('UTC')
        
        # Convert to timezone-naive UTC for xarray compatibility
        # XArray doesn't support timezone-aware datetime64, so we remove timezone
        # info after converting to UTC
        time_index_utc_naive = time_index_utc.tz_localize(None)
        
        # Update dataset
        ds_utc = ds.copy()
        ds_utc['time'] = time_index_utc_naive
        
        # Add timezone info to attributes to track that it's UTC
        ds_utc.time.attrs['timezone'] = 'UTC'
        
        return ds_utc
    
    @staticmethod
    def handle_dst_transition(
        timestamps: pd.DatetimeIndex,
        tz_name: str
    ) -> pd.DatetimeIndex:
        """
        Handle DST transitions properly.
        
        Args:
            timestamps: Timestamps that may cross DST boundaries
            tz_name: Timezone name
            
        Returns:
            Properly handled timestamps
        """
        tz = TimezoneHandler._get_timezone(tz_name)
        
        # For naive timestamps crossing DST
        if timestamps.tz is None:
            try:
                # Try standard localization
                return timestamps.tz_localize(tz)
            except Exception as e:
                # Handle both ambiguous and non-existent times
                # Different pandas versions have different exception names
                error_msg = str(e).lower()
                
                if 'ambiguous' in error_msg:
                    # Handle ambiguous times during DST transition
                    # Use infer to let pandas infer the correct side
                    return timestamps.tz_localize(tz, ambiguous='infer')
                elif 'nonexistent' in error_msg or 'non-existent' in error_msg:
                    # Handle non-existent times during DST transition
                    # Shift forward to the next valid time
                    return timestamps.tz_localize(tz, nonexistent='shift_forward')
                else:
                    # Unknown error, try with both settings
                    try:
                        return timestamps.tz_localize(
                            tz, 
                            ambiguous='infer',
                            nonexistent='shift_forward'
                        )
                    except:
                        # Last resort - force UTC
                        logger.warning(f"DST handling failed for {tz_name}, using UTC")
                        return timestamps.tz_localize('UTC')
        else:
            # Already has timezone, just convert
            return timestamps.tz_convert(tz)
    
    @staticmethod
    def get_timezone_offset(
        tz_name: str,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Get timezone offset from UTC in hours.
        
        Args:
            tz_name: Timezone name
            timestamp: Specific timestamp (for DST-aware offset)
            
        Returns:
            Offset in hours
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        tz = TimezoneHandler._get_timezone(tz_name)
        
        if isinstance(tz, timezone):
            # Fixed offset
            offset = tz.utcoffset(timestamp)
        else:
            # ZoneInfo - need to localize
            localized = timestamp.astimezone(tz)
            offset = localized.utcoffset()
        
        if offset:
            return offset.total_seconds() / 3600
        
        return 0.0
    
    @staticmethod
    def infer_timezone_from_coordinates(
        latitude: float,
        longitude: float
    ) -> str:
        """
        Infer timezone from geographic coordinates.
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            
        Returns:
            Timezone name
        """
        try:
            # Use timezonefinder if available
            from timezonefinder import TimezoneFinder
            tf = TimezoneFinder()
            tz_name = tf.timezone_at(lat=latitude, lng=longitude)
            
            if tz_name:
                return tz_name
        except ImportError:
            logger.debug("timezonefinder not available, using longitude-based estimate")
        except Exception as e:
            logger.warning(f"Failed to infer timezone from coordinates: {e}")
        
        # Fallback: estimate from longitude
        # Each 15 degrees of longitude = 1 hour offset
        offset_hours = round(longitude / 15)
        
        if offset_hours == 0:
            return 'UTC'
        elif offset_hours > 0:
            return f'Etc/GMT-{offset_hours}'  # Note: signs are reversed in Etc/GMT
        else:
            return f'Etc/GMT+{abs(offset_hours)}'
    
    @staticmethod
    def validate_timezone_consistency(
        ds: xr.Dataset,
        expected_tz: str = 'UTC'
    ) -> List[str]:
        """
        Validate timezone consistency in dataset.
        
        Args:
            ds: Dataset to validate
            expected_tz: Expected timezone
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        # Check time coordinate
        if 'time' in ds.dims:
            time_coord = ds.time
            
            # Check if timezone info exists
            if hasattr(time_coord, 'dt'):
                if hasattr(time_coord.dt, 'tz'):
                    current_tz = time_coord.dt.tz
                    if current_tz and str(current_tz) != expected_tz:
                        issues.append(
                            f"Time coordinate has timezone '{current_tz}' "
                            f"but expected '{expected_tz}'"
                        )
                else:
                    # Convert to pandas to check
                    time_index = pd.to_datetime(time_coord.values)
                    if time_index.tz is None:
                        issues.append("Time coordinate is timezone-naive")
                    elif str(time_index.tz) != expected_tz:
                        issues.append(
                            f"Time coordinate has timezone '{time_index.tz}' "
                            f"but expected '{expected_tz}'"
                        )
            
            # Check for DST jumps that might indicate issues
            time_diffs = np.diff(time_coord.values)
            unique_diffs = np.unique(time_diffs)
            
            if len(unique_diffs) > 1:
                # Multiple different time steps might indicate DST issues
                time_diffs_hours = time_diffs / np.timedelta64(1, 'h')
                if np.any(np.abs(time_diffs_hours - np.median(time_diffs_hours)) > 0.5):
                    issues.append(
                        "Irregular time steps detected - possible DST handling issue"
                    )
        
        return issues

# Convenience functions

def to_utc(
    timestamp: Union[datetime, pd.Timestamp, pd.DatetimeIndex],
    source_tz: Optional[str] = None
) -> Union[datetime, pd.Timestamp, pd.DatetimeIndex]:
    """
    Convert timestamp to UTC.
    
    Args:
        timestamp: Input timestamp
        source_tz: Source timezone if naive
        
    Returns:
        UTC timestamp
    """
    return TimezoneHandler.normalize_to_utc(timestamp, source_tz)

def from_utc(
    timestamp: Union[datetime, pd.Timestamp, pd.DatetimeIndex],
    target_tz: str
) -> Union[datetime, pd.Timestamp, pd.DatetimeIndex]:
    """
    Convert UTC timestamp to local timezone.
    
    Args:
        timestamp: UTC timestamp  
        target_tz: Target timezone
        
    Returns:
        Localized timestamp
    """
    return TimezoneHandler.localize_from_utc(timestamp, target_tz)

def ensure_utc(ds: xr.Dataset) -> xr.Dataset:
    """
    Ensure dataset uses UTC timestamps.
    
    Args:
        ds: Input dataset
        
    Returns:
        Dataset with UTC timestamps
    """
    return TimezoneHandler.ensure_utc_dataset(ds)

def get_timezone_for_location(lat: float, lon: float) -> str:
    """
    Get timezone for geographic location.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Timezone name
    """
    return TimezoneHandler.infer_timezone_from_coordinates(lat, lon)