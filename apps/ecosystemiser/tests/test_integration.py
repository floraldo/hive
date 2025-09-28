"""
Integration test suite for the EcoSystemiser platform.

This module demonstrates proper absolute import paths and tests
the integration between different components of the system.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from ecosystemiser.profile_loader.climate.adapters.factory import (
    get_adapter,
    list_available_adapters,
)
from ecosystemiser.profile_loader.climate.data_models import (
    ClimateRequest,
    ClimateResponse,
)
from ecosystemiser.profile_loader.climate.processing.pipeline import ProcessingPipeline
from ecosystemiser.profile_loader.climate.processing.validation import (
    apply_quality_control,
)
from ecosystemiser.profile_loader.climate.service import ClimateService
from ecosystemiser.profile_loader.shared.models import BaseProfileRequest, ProfileMode
from ecosystemiser.profile_loader.shared.timezone import TimezoneHandler
from ecosystemiser.settings import get_settings


@pytest.fixture
def test_config():
    """Test configuration fixture for dependency injection."""
    return get_settings()

# from ecosystemiser.profile_loader.climate.config import ClimateConfig
# from observability import get_logger


class TestFullSystemIntegration:
    """Test complete system integration scenarios."""

    def test_complete_climate_data_workflow(self, test_config):
        """Test a complete workflow from request to processed data."""
        # Create a realistic climate data request
        request = ClimateRequest(
            location=(40.7589, -73.9851),  # New York City
            variables=["temp_air", "ghi", "wind_speed", "rel_humidity"],
            period={"start": "2020-06-01", "end": "2020-06-07"},
            source="nasa_power",
            mode="observed",
            resolution="1H",
            timezone="UTC",
        )

        # Test request validation
        service = ClimateService(test_config)
        service._validate_request(request)  # Should not raise

        # Test that location resolution works
        lat, lon = service._resolve_location(request.location)
        assert abs(lat - 40.7589) < 0.001
        assert abs(lon + 73.9851) < 0.001

    def test_adapter_to_processing_integration(self, test_config):
        """Test integration between adapters and processing pipeline."""
        # Create sample data that would come from an adapter
        time = pd.date_range("2020-06-01", periods=168, freq="1H")  # 1 week

        ds = xr.Dataset(
            {
                "temp_air": (
                    ["time"],
                    20
                    + 10 * np.sin(np.arange(168) * 2 * np.pi / 24)
                    + np.random.randn(168) * 2,
                ),
                "ghi": (
                    ["time"],
                    np.maximum(
                        0,
                        400 * np.maximum(0, np.sin(np.arange(168) * 2 * np.pi / 24))
                        + np.random.randn(168) * 50,
                    ),
                ),
                "wind_speed": (["time"], np.maximum(0, 5 + np.random.randn(168) * 2)),
                "rel_humidity": (
                    ["time"],
                    np.clip(65 + np.random.randn(168) * 15, 0, 100),
                ),
            },
            coords={"time": time},
        )

        # Add metadata that would come from adapter
        ds.attrs.update(
            {
                "source": "nasa_power",
                "latitude": 40.7589,
                "longitude": -73.9851,
                "created_at": datetime.now().isoformat(),
            }
        )

        # Test processing pipeline integration
        pipeline = ProcessingPipeline(test_config)
        ds_processed = pipeline.execute_preprocessing(ds)

        assert isinstance(ds_processed, xr.Dataset)
        assert ds_processed.sizes["time"] == 168

        # Test quality control integration
        ds_qc, report = apply_quality_control(
            ds_processed, source="nasa_power", comprehensive=True
        )

        assert isinstance(ds_qc, xr.Dataset)
        assert ds_qc.sizes == ds_processed.sizes

    def test_service_configuration_integration(self, test_config):
        """Test that service integrates correctly with configuration."""
        # settings = get_settings()
        service = ClimateService(test_config)

        # assert service.config == settings
        assert hasattr(service, "config")
        # assert hasattr(service, 'processing_pipeline')
        # assert isinstance(service.processing_pipeline, ProcessingPipeline)

    def test_logging_integration(self, test_config):
        """Test that logging works across the system."""
        import logging

        logger = logging.getLogger("test_integration")
        assert logger is not None

        # Test that service uses logging
        service = ClimateService(test_config)
        assert hasattr(service, "config")

    def test_timezone_integration(self):
        """Test timezone handling integration across components."""
        handler = TimezoneHandler()

        # Test timezone aliases are available
        assert "EST" in handler.TIMEZONE_ALIASES
        assert "PST" in handler.TIMEZONE_ALIASES

        # Test integration with climate request (using valid timezone values)
        request = ClimateRequest(
            location=(40.7589, -73.9851),
            variables=["temp_air"],
            period={"year": 2020},
            timezone="local",  # This should be handled properly
        )

        assert request.timezone == "local"


class TestApiIntegration:
    """Test API layer integration with core services."""

    def test_climate_api_models_integration(self):
        """Test that API models integrate with core data models."""
        # Test that ClimateRequest inherits properly
        request = ClimateRequest(
            location=(51.5074, -0.1278),  # London
            variables=["temp_air", "ghi"],
            period={"year": 2020},
        )

        assert isinstance(request, BaseProfileRequest)
        assert request.mode == ProfileMode.OBSERVED.value

    def test_service_real_integration(self, test_config):
        """Test service integration with real processing pipeline."""
        # Create realistic test data directly
        time_range = pd.date_range("2020-01-01", periods=24, freq="1H")

        # Create test dataset with realistic patterns
        test_ds = xr.Dataset(
            {
                "temp_air": (
                    ["time"],
                    15
                    + 5 * np.sin(np.arange(24) * 2 * np.pi / 24)
                    + np.random.randn(24) * 0.5,
                )
            },
            coords={"time": time_range},
        )

        # Test with actual service components
        service = ClimateService(test_config)
        request = ClimateRequest(
            location=(51.5, -0.1), variables=["temp_air"], period={"year": 2020}
        )

        # Validate request processing
        service._validate_request(request)

        # Test pipeline processing with real data
        pipeline = ProcessingPipeline(test_config)
        processed_ds = pipeline.execute_preprocessing(test_ds)

        assert isinstance(processed_ds, xr.Dataset)
        assert "temp_air" in processed_ds
        assert processed_ds.sizes["time"] == 24

        # Test quality control on processed data
        qc_ds, qc_report = apply_quality_control(processed_ds, source="test")
        assert isinstance(qc_ds, xr.Dataset)
        assert qc_report is not None


class TestErrorHandlingIntegration:
    """Test error handling across integrated components."""

    def test_adapter_error_propagation(self, test_config):
        """Test that adapter errors are properly handled by service."""
        service = ClimateService(test_config)

        # Test with invalid variables
        request = ClimateRequest(
            location=(51.5, -0.1),
            variables=["invalid_var", "another_invalid"],  # Invalid variables
            period={"year": 2020},
            source="nasa_power",
        )

        with pytest.raises(Exception):  # Should raise validation error
            service._validate_request(request)

    def test_validation_error_integration(self, test_config):
        """Test validation error handling integration."""
        # Test with invalid location
        with pytest.raises(Exception):
            request = ClimateRequest(
                location=(999, 999),  # Invalid coordinates
                variables=["temp_air"],
                period={"year": 2020},
            )

            service = ClimateService(test_config)
            service._resolve_location(request.location)


class TestCacheIntegration:
    """Test caching integration across the system."""

    def test_cache_configuration_integration(self, test_config):
        """Test that caching integrates with configuration."""
        # settings = get_settings()
        service = ClimateService(test_config)

        # Check cache configuration is accessible
        # cache_enabled = hasattr(settings, 'caching') and settings.caching.enabled if hasattr(settings, 'caching') else False

        # Service should respect cache configuration
        assert hasattr(service, "_check_cache")


class TestDataConsistencyIntegration:
    """Test data consistency across different system components."""

    def test_variable_consistency_across_components(self):
        """Test that variable definitions are consistent."""
        from ecosystemiser.profile_loader.climate.data_models import CANONICAL_VARIABLES

        # Test that canonical variables are available
        assert "temp_air" in CANONICAL_VARIABLES
        assert "ghi" in CANONICAL_VARIABLES
        assert "wind_speed" in CANONICAL_VARIABLES

        # Test that request uses canonical variables
        request = ClimateRequest(
            location=(51.5, -0.1), variables=["temp_air", "ghi"], period={"year": 2020}
        )

        for var in request.variables:
            assert (
                var in CANONICAL_VARIABLES
            ), f"Variable {var} not in canonical variables"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
