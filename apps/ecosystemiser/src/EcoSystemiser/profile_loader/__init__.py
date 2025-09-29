from hive_logging import get_logger

logger = get_logger(__name__)

"""Profile Loader Module - Unified interface for all profile loading (climate, demand, etc.)"""

# Unified interface
# Legacy climate interface for backward compatibility
from .climate import get_profile, get_profile_sync

# Specific profile types
from .climate.data_models import ClimateRequest, ClimateResponse
from .demand.models import DemandRequest, DemandResponse

# Base models for unified interface
from .shared.models import (
    BaseProfileRequest,
    BaseProfileResponse,
    DataFrequency,
    LocationInfo,
    ProfileMode,
)
from .unified_service import (
    get_climate_service,
    get_demand_service,
    get_unified_profile_service,
    process_climate_request,
    process_demand_request,
)

__all__ = [
    # Unified interface
    "get_unified_profile_service",
    "get_climate_service",
    "get_demand_service",
    "process_climate_request",
    "process_demand_request",
    # Base models
    "BaseProfileRequest",
    "BaseProfileResponse",
    "ProfileMode",
    "DataFrequency",
    "LocationInfo",
    # Specific models
    "ClimateRequest",
    "ClimateResponse",
    "DemandRequest",
    "DemandResponse",
    # Legacy compatibility
    "get_profile",
    "get_profile_sync",
]
