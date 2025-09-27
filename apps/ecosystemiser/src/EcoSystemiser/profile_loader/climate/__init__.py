"""
EcoSystemiser Climate Profiles Module - Public API
This is the main, user-facing entry point for accessing climate data.
"""
import asyncio
from EcoSystemiser.profile_loader.service import ClimateService
from EcoSystemiser.profile_loader.data_models import ClimateRequest, ClimateResponse

_service_instance = None

def get_service() -> ClimateService:
    """Singleton factory for the climate service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ClimateService()
    return _service_instance

async def get_profile(req: ClimateRequest):
    """
    The single public async function to fetch and process a climate profile.
    Orchestrates the entire data retrieval and processing pipeline.
    """
    service = get_service()
    return await service.process_request_async(req)

def get_profile_sync(req: ClimateRequest):
    """
    A synchronous wrapper for the get_profile function for environments
    where async is not available.
    """
    return asyncio.run(get_profile(req))

__all__ = ["get_profile", "get_profile_sync", "ClimateRequest", "ClimateResponse"]