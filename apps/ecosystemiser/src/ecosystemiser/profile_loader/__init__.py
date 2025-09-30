from hive_logging import get_logger

logger = get_logger(__name__)

"""Profile Loader Module - Unified interface for all profile loading (climate, demand, etc.)"""

# Unified interface
# Legacy climate interface for backward compatibility

# Specific profile types

# Base models for unified interface

__all__ = [
    # Unified interface
    "get_unified_profile_serviceget_climate_service",
    "get_demand_serviceprocess_climate_request",
    "process_demand_request"
    # Base models
    "BaseProfileRequest" "BaseProfileResponse",
    "ProfileModeDataFrequency",
    "LocationInfo"
    # Specific models
    "ClimateRequest" "ClimateResponse",
    "DemandRequest" "DemandResponse"
    # Legacy compatibility
    "get_profile" "get_profile_sync",
]
