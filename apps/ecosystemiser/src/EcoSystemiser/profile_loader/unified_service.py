"""
Unified profile service factory and interface.

This module provides a single entry point for all profile services
(climate, demand, etc.) using the unified interface.
"""

from typing import Dict, Type, Optional, Any, List
from ecosystemiser.hive_logging_adapter import get_logger
from ecosystemiser.profile_loader.shared.service import BaseProfileService
from ecosystemiser.profile_loader.shared.models import BaseProfileRequest, BaseProfileResponse
from ecosystemiser.profile_loader.climate.service import ClimateService
from ecosystemiser.profile_loader.climate.data_models import ClimateRequest
from ecosystemiser.profile_loader.demand.service import DemandService
from ecosystemiser.profile_loader.demand.models import DemandRequest

logger = get_logger(__name__)

class UnifiedProfileService:
    """
    Unified profile service providing a single interface for all profile types.

    This service acts as a factory and router, directing requests to the
    appropriate specialized service based on the request type.
    """

    def __init__(self):
        """Initialize unified service with all profile services."""
        self.services: Dict[str, BaseProfileService] = {}
        self.request_mappings: Dict[Type, str] = {}

        # Initialize available services
        self._init_services()
        logger.info(f"UnifiedProfileService initialized with {len(self.services)} services")

    def _init_services(self):
        """Initialize and register all available profile services."""
        try:
            # Climate service
            self.services["climate"] = ClimateService()
            self.request_mappings[ClimateRequest] = "climate"
            logger.info("Climate service registered")
        except Exception as e:
            logger.warning(f"Failed to initialize climate service: {e}")

        try:
            # Demand service
            self.services["demand"] = DemandService()
            self.request_mappings[DemandRequest] = "demand"
            logger.info("Demand service registered")
        except Exception as e:
            logger.warning(f"Failed to initialize demand service: {e}")

    def get_service(self, service_type: str) -> Optional[BaseProfileService]:
        """
        Get a specific profile service by type.

        Args:
            service_type: Type of service ("climate", "demand", etc.)

        Returns:
            Profile service instance or None if not available
        """
        return self.services.get(service_type)

    def get_service_for_request(self, request: BaseProfileRequest) -> Optional[BaseProfileService]:
        """
        Get the appropriate service for a given request.

        Args:
            request: Profile request

        Returns:
            Appropriate service instance or None
        """
        request_type = type(request)
        service_type = self.request_mappings.get(request_type)

        if service_type:
            return self.services.get(service_type)

        # Try to infer from request attributes
        if hasattr(request, 'demand_type'):
            return self.services.get("demand")
        elif hasattr(request, 'source') and request.source in ["nasa_power", "meteostat", "pvgis", "era5", "file_epw"]:
            return self.services.get("climate")

        return None

    async def process_request_async(self, request: BaseProfileRequest) -> BaseProfileResponse:
        """
        Process any profile request asynchronously.

        Args:
            request: Profile request

        Returns:
            Profile response

        Raises:
            ValueError: If no appropriate service found
        """
        service = self.get_service_for_request(request)
        if not service:
            raise ValueError(f"No service available for request type: {type(request)}")

        dataset, response = await service.process_request_async(request)
        return response

    def process_request(self, request: BaseProfileRequest) -> BaseProfileResponse:
        """
        Process any profile request synchronously.

        Args:
            request: Profile request

        Returns:
            Profile response

        Raises:
            ValueError: If no appropriate service found
        """
        service = self.get_service_for_request(request)
        if not service:
            raise ValueError(f"No service available for request type: {type(request)}")

        dataset, response = service.process_request(request)
        return response

    def validate_request(self, request: BaseProfileRequest) -> List[str]:
        """
        Validate any profile request.

        Args:
            request: Profile request to validate

        Returns:
            List of validation errors (empty if valid)
        """
        service = self.get_service_for_request(request)
        if not service:
            return [f"No service available for request type: {type(request)}"]

        return service.validate_request(request)

    def get_available_services(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all available services.

        Returns:
            Dictionary mapping service types to their information
        """
        service_info = {}
        for service_type, service in self.services.items():
            service_info[service_type] = service.get_service_info()

        return service_info

    def get_all_sources(self) -> Dict[str, List[str]]:
        """
        Get all available sources across all services.

        Returns:
            Dictionary mapping service types to their available sources
        """
        all_sources = {}
        for service_type, service in self.services.items():
            all_sources[service_type] = service.get_available_sources()

        return all_sources

    async def shutdown(self):
        """Shutdown all services."""
        logger.info("Shutting down UnifiedProfileService")
        for service_type, service in self.services.items():
            try:
                if hasattr(service, 'shutdown'):
                    await service.shutdown()
                logger.info(f"Shutdown {service_type} service")
            except Exception as e:
                logger.warning(f"Error shutting down {service_type} service: {e}")

# Global unified service instance
_unified_service: Optional[UnifiedProfileService] = None

def get_unified_profile_service() -> UnifiedProfileService:
    """Get the global unified profile service instance."""
    global _unified_service

    if _unified_service is None:
        _unified_service = UnifiedProfileService()

    return _unified_service

# Convenience functions for direct access
async def process_climate_request(request: ClimateRequest):
    """Process climate request directly."""
    service = get_unified_profile_service()
    return await service.get_service("climate").process_request_async(request)

async def process_demand_request(request: DemandRequest):
    """Process demand request directly."""
    service = get_unified_profile_service()
    return await service.get_service("demand").process_request_async(request)

def get_climate_service() -> ClimateService:
    """Get climate service directly."""
    service = get_unified_profile_service()
    return service.get_service("climate")

def get_demand_service() -> DemandService:
    """Get demand service directly."""
    service = get_unified_profile_service()
    return service.get_service("demand")