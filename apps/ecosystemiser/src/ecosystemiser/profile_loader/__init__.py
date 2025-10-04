"""Profile Loader Module - Unified interface for all profile loading (climate, demand, etc.)"""

from hive_logging import get_logger

# Import from climate module
from .climate import ClimateRequest, ClimateResponse, get_profile_sync

# Import base models from shared.models
from .shared.models import BaseProfileRequest, BaseProfileResponse, ProfileMode

logger = get_logger(__name__)

# Aliases for unified interface
get_climate_service = get_profile_sync
process_climate_request = get_profile_sync

# Legacy compatibility
get_profile = get_profile_sync

__all__ = [
    # Climate service interface
    "get_climate_service",
    "process_climate_request",
    # Base models
    "BaseProfileRequest",
    "BaseProfileResponse",
    "ProfileMode",
    # Climate-specific models
    "ClimateRequest",
    "ClimateResponse",
    # Legacy compatibility
    "get_profile",
    "get_profile_sync",
]
