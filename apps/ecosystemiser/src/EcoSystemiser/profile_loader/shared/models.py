"""
Shared base models for all profile loaders.

This module defines common data structures that can be inherited
by specific profile types (climate, demand, etc.).
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import pandas as pd


class ProfileMode(Enum):
    """Common profile generation modes"""
    OBSERVED = "observed"      # Historical/measured data
    AVERAGE = "average"        # Average patterns
    TYPICAL = "typical"        # Typical year/period
    SYNTHETIC = "synthetic"    # Synthetic generation
    FORECAST = "forecast"      # Future projections


class DataFrequency(Enum):
    """Standard data frequencies"""
    MINUTELY = "1T"
    FIVE_MINUTELY = "5T"
    TEN_MINUTELY = "10T"
    FIFTEEN_MINUTELY = "15T"
    HALF_HOURLY = "30T"
    HOURLY = "1H"
    DAILY = "1D"
    WEEKLY = "1W"
    MONTHLY = "1M"
    YEARLY = "1Y"


class BaseProfileRequest(BaseModel):
    """
    Base class for all profile data requests.
    
    Common attributes for any time series profile request.
    """
    # Location - can be coordinates, ID, or name
    location: Union[Tuple[float, float], str, Dict[str, Any]]
    
    # Time period specification
    period: Dict[str, Any]
    
    # Variables/parameters to fetch
    variables: List[str]
    
    # Data resolution/frequency
    resolution: Optional[str] = "1H"
    
    # Profile generation mode
    mode: ProfileMode = ProfileMode.OBSERVED
    
    # Data source preference
    source: Optional[str] = None
    
    # Timezone for output
    timezone: str = "UTC"
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Request ID for tracking
    request_id: Optional[str] = None
    
    # Caching preferences
    use_cache: bool = True
    cache_ttl: Optional[int] = None  # seconds
    
    @validator('period')
    def validate_period(cls, v):
        """Validate and normalize period specification."""
        if not isinstance(v, dict):
            raise ValueError("Period must be a dictionary")

        # Import here to avoid circular imports
        from EcoSystemiser.profile_loader.datetime_utils import DateTimeProcessor

        try:
            # Validate by attempting to normalize
            normalized = DateTimeProcessor.normalize_period(v)
            return v  # Return original for now, normalization happens at processing time
        except Exception as e:
            raise ValueError(f"Invalid period specification: {e}")

    @validator('resolution')
    def validate_resolution(cls, v):
        """Validate resolution string."""
        if v is None:
            return v

        # Import here to avoid circular imports
        from EcoSystemiser.profile_loader.datetime_utils import DateTimeProcessor

        try:
            normalized = DateTimeProcessor.normalize_frequency(v)
            return v  # Return original, normalization happens at processing time
        except Exception as e:
            raise ValueError(f"Invalid resolution specification: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "location": self.location,
            "period": self.period,
            "variables": self.variables,
            "resolution": self.resolution,
            "mode": self.mode.value if isinstance(self.mode, ProfileMode) else self.mode,
            "source": self.source,
            "timezone": self.timezone,
            "metadata": self.metadata,
            "request_id": self.request_id,
            "use_cache": self.use_cache,
            "cache_ttl": self.cache_ttl
        }

    def get_normalized_period(self) -> Dict[str, pd.Timestamp]:
        """Get normalized period with pandas Timestamps."""
        from EcoSystemiser.profile_loader.datetime_utils import DateTimeProcessor
        return DateTimeProcessor.normalize_period(self.period)

    def get_normalized_frequency(self) -> str:
        """Get normalized frequency string."""
        from EcoSystemiser.profile_loader.datetime_utils import DateTimeProcessor
        return DateTimeProcessor.normalize_frequency(self.resolution)


class BaseProfileResponse(BaseModel):
    """
    Base class for profile data responses.
    
    Common structure for returning profile data with metadata.
    """
    # Data shape (time_steps, variables)
    shape: Tuple[int, int]
    
    # Time range
    start_time: datetime
    end_time: datetime
    
    # Actual variables returned
    variables: List[str]
    
    # Data source used
    source: str
    
    # Processing applied
    processing_steps: List[str] = Field(default_factory=list)
    
    # Quality metrics
    quality: Dict[str, Any] = Field(default_factory=dict)
    
    # Cache information
    cached: bool = False
    cache_key: Optional[str] = None
    
    # File paths if data is persisted
    path_parquet: Optional[str] = None
    path_csv: Optional[str] = None
    
    # Metadata and manifest
    metadata: Dict[str, Any] = Field(default_factory=dict)
    manifest: Optional[Dict[str, Any]] = None
    
    # Timing information
    processing_time_ms: Optional[int] = None
    
    # Warnings or notes
    warnings: List[str] = Field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "shape": self.shape,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "variables": self.variables,
            "source": self.source,
            "processing_steps": self.processing_steps,
            "quality": self.quality,
            "cached": self.cached,
            "cache_key": self.cache_key,
            "path_parquet": self.path_parquet,
            "path_csv": self.path_csv,
            "metadata": self.metadata,
            "manifest": self.manifest,
            "processing_time_ms": self.processing_time_ms,
            "warnings": self.warnings
        }


class DataQuality(BaseModel):
    """
    Data quality metrics common to all profiles.
    """
    completeness: float  # Percentage of non-null values
    gaps: List[Tuple[datetime, datetime]] = Field(default_factory=list)  # List of gap periods
    outliers: Dict[str, int]  # Count of outliers per variable
    quality_flags: Dict[str, Any] = Field(default_factory=dict)
    validation_passed: bool = True
    validation_notes: List[str] = Field(default_factory=list)


class LocationInfo(BaseModel):
    """
    Standard location information.
    """
    latitude: float
    longitude: float
    elevation: Optional[float] = None
    timezone: Optional[str] = None
    name: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)