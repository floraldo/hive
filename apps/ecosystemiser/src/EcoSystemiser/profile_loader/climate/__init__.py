"""
EcoSystemiser Climate Profiles Module - Public API
This is the main, user-facing entry point for accessing climate data.
"""

import asyncio
from typing import Dict, Any

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
        profile = await get_profile(request, climate_service)
    """
    return ClimateService(config)


async def get_profile(req: ClimateRequest, service: ClimateService):
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
        profile = await get_profile(request, service)
    """
    return await service.process_request_async(req)


def get_profile_sync(req: ClimateRequest, service: ClimateService):
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
    return asyncio.run(get_profile(req, service))


__all__ = ["create_climate_service", "get_profile", "get_profile_sync", "ClimateRequest", "ClimateResponse"]
