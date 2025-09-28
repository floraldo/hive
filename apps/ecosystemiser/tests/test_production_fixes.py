"""
Test suite for production-critical fixes.

These tests verify that the critical production issues have been resolved.
"""

import pytest
import xarray as xr
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from EcoSystemiser.profile_loader.climate.data_models import ClimateRequest, ClimateResponse
from EcoSystemiser.profile_loader.climate.service import ClimateService
from EcoSystemiser.profile_loader.climate.job_manager import JobManager, JobStatus
from EcoSystemiser.core.errors import DataParseError


class TestClimateResponseValidation:
    """Test that ClimateResponse includes all required base fields."""
    
    def test_response_has_all_required_fields(self):
        """Test that _cache_and_respond creates valid ClimateResponse."""
        # Create a mock dataset
        times = pd.date_range("2023-01-01", periods=24, freq="H")
        ds = xr.Dataset(
            {
                "temp_air": (["time"], np.random.randn(24) + 20),
                "ghi": (["time"], np.random.randn(24) * 100 + 500)
            },
            coords={"time": times}
        )
        
        # Create request
        request = ClimateRequest(
            location=(40.7, -74.0),
            variables=["temp_air", "ghi"],
            period={"year": 2023},
            source="nasa_power"
        )
        
        # Create service and build response
        service = ClimateService()
        processing_report = {"steps": ["validation", "resampling"], "warnings": []}
        
        # This should NOT raise a validation error anymore
        response = service._cache_and_respond(ds, request, processing_report)
        
        # Verify all required fields are present
        assert response.start_time is not None
        assert response.end_time is not None
        assert response.variables == ["temp_air", "ghi"]
        assert response.source == "nasa_power"
        assert response.shape == (24, 2)
        
        # Verify timestamps are correct
        assert response.start_time == pd.Timestamp(times[0])
        assert response.end_time == pd.Timestamp(times[-1])


class TestJobManagerRedis:
    """Test the production-ready job manager."""
    
    def test_job_manager_fallback_without_redis(self):
        """Test that JobManager works without Redis (development mode)."""
        # Create manager without Redis
        with patch('EcoSystemiser.profile_loader.climate.job_manager.REDIS_AVAILABLE', False):
            manager = JobManager()
            
            # Should fall back to memory store
            assert manager.redis is None
            assert manager._memory_store is not None
            
            # Test basic operations
            job_id = manager.create_job({"test": "data"})
            assert job_id is not None
            
            job = manager.get_job(job_id)
            assert job is not None
            assert job["status"] == JobStatus.PENDING
            assert job["request"] == {"test": "data"}
            
            # Update status
            success = manager.update_job_status(
                job_id,
                JobStatus.COMPLETED,
                result={"output": "result"}
            )
            assert success is True
            
            # Check updated job
            job = manager.get_job(job_id)
            assert job["status"] == JobStatus.COMPLETED
            assert job["result"] == {"output": "result"}
    
    @patch('EcoSystemiser.profile_loader.climate.job_manager.Redis')
    def test_job_manager_with_redis_mock(self, mock_redis_class):
        """Test JobManager with mocked Redis."""
        # Setup mock Redis
        mock_redis = MagicMock()
        mock_redis_class.from_url.return_value = mock_redis
        mock_redis.ping.return_value = True
        
        # Create manager
        manager = JobManager(redis_url="redis://localhost:6379")
        
        # Verify Redis was connected
        assert manager.redis is not None
        mock_redis.ping.assert_called_once()
        
        # Test job creation
        job_id = manager.create_job({"request": "data"})
        
        # Verify Redis calls
        assert mock_redis.setex.called
        assert mock_redis.zadd.called
        
        # The first call to setex should have the job data
        call_args = mock_redis.setex.call_args
        assert "job:" in call_args[0][0]  # Key contains "job:"
        assert call_args[0][1] > 0  # TTL is positive
    
    def test_job_manager_handles_missing_jobs(self):
        """Test that job manager handles missing jobs gracefully."""
        with patch('EcoSystemiser.profile_loader.climate.job_manager.REDIS_AVAILABLE', False):
            manager = JobManager()
            
            # Try to get non-existent job
            job = manager.get_job("non-existent-id")
            assert job is None
            
            # Try to update non-existent job
            success = manager.update_job_status("non-existent-id", JobStatus.COMPLETED)
            assert success is False


class TestEPWErrorHandling:
    """Test EPW file parser error handling."""
    
    def test_epw_parser_handles_malformed_file(self):
        """Test that EPW parser raises specific errors for malformed files."""
        from EcoSystemiser.profile_loader.climate.adapters.file_epw import EPWAdapter
        
        adapter = EPWAdapter()
        
        # Test with too short file
        short_content = "LOCATION,Test\nDATA"
        with pytest.raises(DataParseError) as exc_info:
            adapter._parse_epw_data(short_content)
        assert "too short" in str(exc_info.value).lower()
        
        # Test with invalid CSV data
        invalid_content = "\n" * 10 + "not,valid,csv,data\n,,,\n"
        with pytest.raises(DataParseError) as exc_info:
            adapter._parse_epw_data(invalid_content)
        # The error should be about the file being too short or parsing issues
        error_msg = str(exc_info.value).lower()
        assert "too short" in error_msg or "parse" in error_msg


class TestTimeGapDetection:
    """Test improved time gap detection with explicit frequency."""
    
    def test_time_gaps_with_explicit_frequency(self):
        """Test that time gap detection uses provided frequency."""
        from EcoSystemiser.profile_loader.climate.processing.validation import ValidationProcessor
        
        processor = ValidationProcessor()
        
        # Create dataset with a gap
        times = pd.date_range("2023-01-01", periods=10, freq="H").tolist()
        times.pop(5)  # Remove one timestamp to create a gap
        
        ds = xr.Dataset(
            {"temp": (["time"], np.ones(9))},
            coords={"time": times}
        )
        
        # Check gaps with explicit frequency
        issues = processor._check_time_gaps(ds, expected_freq="1H")
        
        # Should detect the missing timestamp
        assert len(issues) > 0
        assert any("missing" in issue.message.lower() for issue in issues)
        
        # Verify the expected frequency was used
        gap_issue = next((i for i in issues if "missing" in i.message.lower() or "gap" in i.message.lower()), None)
        assert gap_issue is not None
        # QCIssue uses 'metadata' not 'details'
        assert gap_issue.metadata["expected_freq"] == "1H"


class TestFactoryCleanup:
    """Test that sys.path hacks have been removed."""
    
    def test_no_sys_path_manipulation(self):
        """Test that factory doesn't manipulate sys.path."""
        import sys
        original_path = sys.path.copy()
        
        # Import should not modify sys.path
        from EcoSystemiser.profile_loader.climate.adapters.factory import _auto_register_adapters
        
        # Check path wasn't modified
        assert sys.path == original_path
        
        # Run auto-register
        _auto_register_adapters()
        
        # Path should still be unchanged
        assert sys.path == original_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])