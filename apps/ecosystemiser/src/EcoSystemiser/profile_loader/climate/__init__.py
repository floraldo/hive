from hive_logging import get_logger

logger = get_logger(__name__)

"""
EcoSystemiser Climate Profiles Module - Public API
This is the main, user-facing entry point for accessing climate data.
"""

import asyncio
from typing import Any, Dict

from .data_models import ClimateRequest, ClimateResponse
from .service import ClimateService


def create_climate_service(config: Dict[str, Any]) -> ClimateService:
    """Factory function to create a new ClimateService instance with explicit configuration.

    Args:
        config: Configuration dictionary for the climate service

    Returns:
        ClimateService: New climate service instance

    Example:
        # In main application
        config = get_settings()
        climate_service = create_climate_service(config)

        # Pass to functions that need it
        profile = await get_profile_async(request, climate_service)
    """
    return ClimateService(config)


async def get_profile_async(req: ClimateRequest, service: ClimateService) -> None:
    """
    Fetch and process a climate profile using dependency injection.

    Args:
        req: Climate data request specification
        service: ClimateService instance (injected dependency)

    Returns:
        Processed climate profile data

    Example:
        from ecosystemiser.settings import get_settings

        config = get_settings()
        service = create_climate_service(config)
        profile = await get_profile_async(request, service)
    """
    return await service.process_request_async(req)


def get_profile_sync(req: ClimateRequest, service: ClimateService) -> None:
    """
    A synchronous wrapper for the get_profile function for environments
    where async is not available.

    Args:
        req: Climate data request specification
        service: ClimateService instance (injected dependency)

    Returns:
        Processed climate profile data

    Example:
        from ecosystemiser.settings import get_settings

        config = get_settings()
        service = create_climate_service(config)
        profile = get_profile_sync(request, service)
    """
    return asyncio.run(get_profile_async(req, service))


__all__ = ["create_climate_service", "get_profile", "get_profile_sync", "ClimateRequest", "ClimateResponse"]
