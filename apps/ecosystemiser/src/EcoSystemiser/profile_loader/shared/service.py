"""
Unified profile service interface for all profile types.

This module defines the common service interface that all profile loaders
(climate, demand, etc.) should implement for consistency.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
import xarray as xr
from ecosystemiser.profile_loader.shared.models import BaseProfileRequest, BaseProfileResponse


class BaseProfileService(ABC):
    """
    Abstract base class for all profile services.

    This defines the unified interface that all profile loaders should implement,
    ensuring consistency between climate, demand, and future profile types.
    """

    @abstractmethod
    async def process_request_async(self, request: BaseProfileRequest) -> Tuple[xr.Dataset, BaseProfileResponse]:
        """
        Process a profile data request asynchronously.

        Args:
            request: Profile data request following the unified interface

        Returns:
            Tuple of (xarray Dataset, Response metadata)

        Raises:
            ProfileServiceError: If request processing fails
        """
        pass

    @abstractmethod
    def process_request(self, request: BaseProfileRequest) -> Tuple[xr.Dataset, BaseProfileResponse]:
        """
        Process a profile data request synchronously.

        Args:
            request: Profile data request following the unified interface

        Returns:
            Tuple of (xarray Dataset, Response metadata)

        Raises:
            ProfileServiceError: If request processing fails
        """
        pass

    @abstractmethod
    def validate_request(self, request: BaseProfileRequest) -> List[str]:
        """
        Validate a profile request and return any validation errors.

        Args:
            request: Profile data request to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        pass

    @abstractmethod
    def get_available_sources(self) -> List[str]:
        """
        Get list of available data sources for this profile type.

        Returns:
            List of source identifiers
        """
        pass

    @abstractmethod
    def get_available_variables(self, source: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        """
        Get available variables for this profile type.

        Args:
            source: Optional source filter

        Returns:
            Dictionary mapping variable names to metadata
        """
        pass

    @abstractmethod
    def get_source_coverage(self, source: str) -> Dict[str, Any]:
        """
        Get geographical and temporal coverage for a data source.

        Args:
            source: Source identifier

        Returns:
            Coverage information including spatial/temporal bounds
        """
        pass

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about this service.

        Returns:
            Service metadata including capabilities and version
        """
        return {
            "service_type": self.__class__.__name__,
            "version": "1.0.0",
            "available_sources": self.get_available_sources(),
            "capabilities": {
                "async_processing": True,
                "caching": True,
                "validation": True
            }
        }


class ProfileServiceError(Exception):
    """Base exception for profile service errors."""

    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class ProfileValidationError(ProfileServiceError):
    """Exception for profile request validation errors."""
    pass


class ProfileDataError(ProfileServiceError):
    """Exception for profile data processing errors."""
    pass


class ProfileSourceError(ProfileServiceError):
    """Exception for profile data source errors."""
    pass