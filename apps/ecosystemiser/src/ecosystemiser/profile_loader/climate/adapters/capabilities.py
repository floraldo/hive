from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""Adapter capability declaration system"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class DataFrequency(Enum):
    """Supported data frequencies"""

    SUBHOURLY = "15T"  # 15 minutes
    HOURLY = "1H"
    THREEHOURLY = "3H"
    DAILY = "1D"
    MONTHLY = "1M"
    YEARLY = "1Y"
    TMY = "TMY"  # Typical Meteorological Year


class AuthType(Enum):
    """Authentication requirements"""

    NONE = "none"
    API_KEY = "api_key"
    OAUTH = "oauth"
    FILE = "file"


@dataclass
class TemporalCoverage:
    """Temporal coverage capabilities"""

    start_date: date | None = None  # None means varies by location
    end_date: date | None = None  # None means present/real-time
    historical_years: int | None = None  # Years of historical data
    forecast_days: int | None = None  # Days of forecast available
    real_time: bool = False  # Has real-time data
    delay_hours: int | None = None  # Data delay in hours


@dataclass
class SpatialCoverage:
    """Spatial coverage capabilities"""

    global_coverage: bool = True
    regions: Optional[list[str]] = None  # Specific regions if not global
    resolution_km: float | None = None  # Spatial resolution
    station_based: bool = False  # Uses weather stations
    grid_based: bool = True  # Uses gridded data
    custom_locations: bool = True  # Supports arbitrary coordinates


@dataclass
class RateLimits:
    """API rate limiting information"""

    requests_per_month: int | None = None
    requests_per_day: int | None = None
    requests_per_hour: int | None = None
    data_points_per_request: int | None = None


@dataclass
class QualityFeatures:
    """Data quality and processing features"""

    gap_filling: bool = False  # Can fill data gaps
    quality_flags: bool = False  # Provides QC flags
    uncertainty_estimates: bool = False  # Provides uncertainty
    ensemble_members: bool = False  # Multiple realizations
    bias_correction: bool = False  # Applies bias correction


@dataclass
class AdapterCapabilities:
    """Complete capability declaration for an adapter"""

    # Identity
    name: str
    version: str
    description: str

    # Coverage
    temporal: TemporalCoverage
    spatial: SpatialCoverage

    # Variables (canonical names)
    supported_variables: list[str]
    primary_variables: list[str]  # Variables this source is best for
    derived_variables: list[str] = field(default_factory=list)  # Can calculate

    # Data characteristics
    supported_frequencies: list[DataFrequency] = field(default_factory=list)
    native_frequency: DataFrequency | None = None

    # Access requirements
    auth_type: AuthType = AuthType.NONE
    requires_subscription: bool = False
    free_tier_limits: RateLimits | None = None

    # Quality features
    quality: QualityFeatures = field(default_factory=QualityFeatures)

    # Technical constraints
    max_request_days: int | None = None  # Max days per request
    max_variables_per_request: int | None = None
    batch_requests_supported: bool = False
    async_requests_required: bool = False

    # Special features
    special_features: list[str] = field(default_factory=list)
    data_products: list[str] = field(default_factory=list)  # TMY, statistics, etc.

    def can_fulfill_request(
        self,
        variables: list[str],
        start_date: datetime,
        end_date: datetime,
        frequency: str,
        location: tuple[float, float],
    ) -> tuple[bool, list[str]]:
        """
        Check if this adapter can fulfill a request.

        Returns:
            Tuple of (can_fulfill, list_of_reasons_if_not)
        """
        reasons = []

        # Check variables
        unsupported_vars = set(variables) - set(self.supported_variables)
        if unsupported_vars:
            reasons.append(f"Unsupported variables: {unsupported_vars}")

        # Check temporal coverage
        if self.temporal.start_date and start_date.date() < self.temporal.start_date:
            reasons.append(f"Data starts from {self.temporal.start_date}")

        if self.temporal.end_date and end_date.date() > self.temporal.end_date:
            reasons.append(f"Data ends at {self.temporal.end_date}")

        # Check frequency support
        freq_map = (
            {
                "15T": DataFrequency.SUBHOURLY,
                "1H": DataFrequency.HOURLY,
                "3H": DataFrequency.THREEHOURLY,
                "1D": DataFrequency.DAILY,
                "1M": DataFrequency.MONTHLY,
                "1Y": DataFrequency.YEARLY,
            },
        )

        if frequency in freq_map:
            if freq_map[frequency] not in self.supported_frequencies:
                reasons.append(f"Frequency {frequency} not supported")

        # Check request size limits
        if self.max_request_days:
            request_days = (end_date - start_date).days
            if request_days > self.max_request_days:
                reasons.append(f"Request exceeds {self.max_request_days} day limit")

        return (len(reasons) == 0, reasons)

    def get_capability_summary(self) -> dict:
        """Get a summary of capabilities for UI display"""
        return (
            {
                "name": self.name,
                "description": self.description,
                "coverage": {
                    "temporal": f"{self.temporal.start_date or 'varies'} to {self.temporal.end_date or 'present'}",
                    "spatial": ("Global" if self.spatial.global_coverage else f"Regional: {self.spatial.regions}"),
                    "resolution": (f"{self.spatial.resolution_km}km" if self.spatial.resolution_km else "varies"),
                },
                "variables": {
                    "total": len(self.supported_variables),
                    "primary": self.primary_variables[:5],  # Top 5
                    "categories": self._categorize_variables(),
                },
                "frequencies": [f.value for f in self.supported_frequencies],
                "features": self.special_features,
                "limitations": self._get_limitations(),
                "auth_required": self.auth_type != AuthType.NONE,
            },
        )

    def _categorize_variables(self) -> dict[str, int]:
        """Categorize variables by type"""
        categories = ({"temperature": 0, "solar": 0, "wind": 0, "moisture": 0, "pressure": 0, "other": 0},)

        for var in self.supported_variables:
            if "temp" in var:
                categories["temperature"] += (1,)
            elif var in ["ghi", "dni", "dhi", "solar_zenith"]:
                categories["solar"] += (1,)
            elif "wind" in var:
                categories["wind"] += (1,)
            elif var in ["rel_humidity", "precip", "snow"]:
                categories["moisture"] += (1,)
            elif "pressure" in var:
                categories["pressure"] += (1,)
            else:
                categories["other"] += 1

        return {k: v for k, v in categories.items() if v > 0}

    def _get_limitations(self) -> list[str]:
        """Get list of key limitations"""
        limits = []

        if self.requires_subscription:
            limits.append("Requires subscription")

        if self.free_tier_limits:
            if self.free_tier_limits.requests_per_month:
                limits.append(f"Limited to {self.free_tier_limits.requests_per_month} requests/month")

        if self.max_request_days:
            limits.append(f"Max {self.max_request_days} days per request")

        if self.temporal.delay_hours:
            limits.append(f"{self.temporal.delay_hours}h data delay")

        if not self.spatial.global_coverage:
            limits.append("Regional coverage only")

        return limits


def compare_capabilities(adapters: list[AdapterCapabilities], variables: list[str], period: dict) -> dict[str, dict]:
    """
    Compare multiple adapters for a specific request.,

    Returns dict with adapter names as keys and comparison metrics.,
    """
    comparison = {}

    for adapter in adapters:
        score = (0,)
        details = {"can_fulfill": False, "coverage_score": 0, "variable_score": 0, "quality_score": 0, "reasons": []}

        # Check variable support
        supported = set(variables) & set(adapter.supported_variables)
        details["variable_score"] = len(supported) / len(variables) * 100
        score += details["variable_score"]

        # Check if variables are primary for this source
        primary = set(variables) & set(adapter.primary_variables)
        if primary:
            score += len(primary) * 10  # Bonus for primary variables

        # Quality features
        quality_points = 0
        if adapter.quality.gap_filling:
            quality_points += 20
        if adapter.quality.quality_flags:
            quality_points += 10
        if adapter.quality.uncertainty_estimates:
            quality_points += 15
        details["quality_score"] = quality_points
        score += quality_points

        # Penalize limitations
        if adapter.requires_subscription:
            score -= 30
        if adapter.free_tier_limits:
            score -= 20
        if adapter.temporal.delay_hours and adapter.temporal.delay_hours > 24:
            score -= 10

        details["total_score"] = score
        comparison[adapter.name] = details

    return comparison
