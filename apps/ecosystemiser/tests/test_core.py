"""
Core tests for EcoSystemiser components.

This module tests adapters, data models, and basic service functionality.
"""

import pytest
import xarray as xr
import numpy as np
import pandas as pd
from datetime import datetime

from ecosystemiser.profile_loader.climate.data_models import ClimateRequest, ClimateResponse, CANONICAL_VARIABLES
from ecosystemiser.profile_loader.climate.service import ClimateService
from ecosystemiser.profile_loader.climate.adapters.factory import get_adapter, list_available_adapters
from ecosystemiser.profile_loader.climate.adapters.base import BaseAdapter
from ecosystemiser.profile_loader.climate.adapters.nasa_power import NASAPowerAdapter
from ecosystemiser.profile_loader.shared.models import BaseProfileRequest, ProfileMode
from ecosystemiser.profile_loader.shared.timezone import TimezoneHandler
from ecosystemiser.core.errors import AdapterError, ValidationError


class TestAdapterFactory:
    """Test cases for the adapter factory system."""
    
    def test_list_available_adapters(self):
        """Test that adapter listing works correctly."""
        adapters = list_available_adapters()
        assert isinstance(adapters, list)
        assert len(adapters) > 0
        
    def test_get_adapter_success(self):
        """Test successful adapter retrieval."""
        adapters = list_available_adapters()
        if adapters:
            adapter = get_adapter(adapters[0])
            assert isinstance(adapter, BaseAdapter)
            
    def test_get_adapter_invalid_name(self):
        """Test adapter retrieval with invalid name."""
        with pytest.raises((AdapterError, ValueError)):
            get_adapter("nonexistent_adapter")


class TestNASAPowerAdapter:
    """Test cases for NASA POWER adapter."""
    
    def test_adapter_initialization(self):
        """Test adapter can be initialized."""
        adapter = NASAPowerAdapter()
        assert isinstance(adapter, BaseAdapter)
        
    def test_capabilities_method(self):
        """Test adapter capabilities method exists."""
        adapter = NASAPowerAdapter()
        assert hasattr(adapter, 'get_capabilities')
        capabilities = adapter.get_capabilities()
        assert capabilities is not None
        assert capabilities.supported_variables is not None


class TestClimateService:
    """Test cases for the climate service."""
    
    def test_service_initialization(self):
        """Test service initializes correctly."""
        service = ClimateService()
        assert service is not None
        assert hasattr(service, 'process_request')
        assert hasattr(service, 'config')
        assert hasattr(service, '_validate_request')
        assert hasattr(service, '_check_cache')
        
    def test_validate_request(self):
        """Test request validation."""
        service = ClimateService()
        
        # Valid request
        valid_request = ClimateRequest(
            location=(51.5, -0.1),  # London
            variables=["temp_air", "ghi"],
            period={"year": 2020},
            source="nasa_power"
        )
        
        # Should not raise exception
        service._validate_request(valid_request)
        
    def test_location_resolution(self):
        """Test location resolution works."""
        service = ClimateService()
        request = ClimateRequest(
            location=(40.7589, -73.9851),  # New York City
            variables=["temp_air"],
            period={"year": 2020}
        )
        
        lat, lon = service._resolve_location(request.location)
        assert abs(lat - 40.7589) < 0.001
        assert abs(lon + 73.9851) < 0.001


class TestDataModels:
    """Test cases for data model validation."""
    
    def test_climate_request_creation(self):
        """Test ClimateRequest model creation."""
        request = ClimateRequest(
            location=(40.7, -74.0),  # NYC
            variables=["temp_air", "wind_speed"],
            period={"start": "2020-01-01", "end": "2020-12-31"},
            mode="observed",
            resolution="1H"
        )
        assert request.location == (40.7, -74.0)
        assert "temp_air" in request.variables
        assert request.mode.value == "observed"
        
    def test_base_profile_request_inheritance(self):
        """Test that ClimateRequest properly inherits from BaseProfileRequest."""
        request = ClimateRequest(
            location=(40.7, -74.0),
            variables=["temp_air"],
            period={"year": 2020}
        )
        assert isinstance(request, BaseProfileRequest)
        assert request.mode.value == ProfileMode.OBSERVED.value
        
    def test_canonical_variables(self):
        """Test that canonical variables are defined."""
        assert 'temp_air' in CANONICAL_VARIABLES
        assert 'ghi' in CANONICAL_VARIABLES
        assert 'wind_speed' in CANONICAL_VARIABLES
        assert 'rel_humidity' in CANONICAL_VARIABLES
        
    def test_variable_consistency(self):
        """Test that request uses canonical variables."""
        request = ClimateRequest(
            location=(51.5, -0.1),
            variables=["temp_air", "ghi"],
            period={"year": 2020}
        )
        
        for var in request.variables:
            assert var in CANONICAL_VARIABLES, f"Variable {var} not in canonical variables"


class TestTimezoneHandler:
    """Test cases for timezone handling utilities."""
    
    def test_timezone_handler_initialization(self):
        """Test timezone handler initializes correctly."""
        handler = TimezoneHandler()
        assert handler is not None
        
    def test_timezone_aliases(self):
        """Test timezone aliases are available."""
        handler = TimezoneHandler()
        assert hasattr(TimezoneHandler, 'TIMEZONE_ALIASES')
        assert isinstance(TimezoneHandler.TIMEZONE_ALIASES, dict)
        assert 'EST' in handler.TIMEZONE_ALIASES
        assert 'PST' in handler.TIMEZONE_ALIASES
        
    def test_timezone_integration(self):
        """Test timezone handling with climate request."""
        request = ClimateRequest(
            location=(40.7589, -73.9851),
            variables=["temp_air"],
            period={"year": 2020},
            timezone="local"
        )
        assert request.timezone == "local"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])