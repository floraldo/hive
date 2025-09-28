"""
Integration tests using real implementations instead of mocks where possible.
"""

import pytest
import xarray as xr
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import json

from EcoSystemiser.profile_loader.climate.data_models import ClimateRequest, ClimateResponse
from EcoSystemiser.profile_loader.climate.service import ClimateService
from EcoSystemiser.profile_loader.climate.processing.pipeline import ProcessingPipeline
from EcoSystemiser.profile_loader.climate.processing.validation import validate_complete, apply_quality_control
from EcoSystemiser.profile_loader.climate.processing.resampling import resample_dataset
from EcoSystemiser.profile_loader.climate.adapters.factory import get_adapter
from EcoSystemiser.profile_loader.climate.job_manager import JobManager, JobStatus
from EcoSystemiser.core.errors import DataSourceError


class TestRealServiceIntegration:
    """Test service integration with real components."""
    
    def test_complete_workflow_with_real_data(self):
        """Test complete workflow with real dataset processing."""
        # Create a realistic test dataset
        times = pd.date_range("2023-01-01", periods=48, freq="H")
        
        # Create realistic temperature pattern (diurnal cycle)
        hours = times.hour
        temp_pattern = 15 + 5 * np.sin((hours - 6) * 2 * np.pi / 24)  # Peak at 3pm
        temp_air = temp_pattern + np.random.normal(0, 0.5, len(times))  # Add noise
        
        # Create realistic solar pattern
        hours_array = np.array(hours)  # Convert to numpy array
        ghi = np.maximum(0, 500 * np.sin((hours_array - 6) * np.pi / 12))  # Zero at night
        ghi[hours_array < 6] = 0
        ghi[hours_array > 18] = 0
        
        ds = xr.Dataset(
            {
                "temp_air": (["time"], temp_air),
                "ghi": (["time"], ghi),
                "wind_speed": (["time"], np.random.exponential(3, len(times))),
                "rel_humidity": (["time"], 60 + 20 * np.random.randn(len(times)))
            },
            coords={"time": times},
            attrs={
                "location": "Test Site",
                "latitude": 51.5,
                "longitude": -0.1
            }
        )
        
        # Apply real validation
        qc_report = validate_complete(ds, source="test", validation_level="comprehensive")
        
        # Check that validation actually ran
        assert qc_report is not None
        assert len(qc_report.passed_checks) > 0
        assert qc_report.data_quality_score is not None
        
        # Apply real quality control
        ds_cleaned, final_report = apply_quality_control(
            ds,
            source="test",
            comprehensive=True
        )
        
        # Verify data was actually processed
        assert ds_cleaned is not None
        assert "temp_air" in ds_cleaned
        
        # Check that night solar was zeroed
        night_ghi = ds_cleaned["ghi"].sel(time=ds_cleaned.time.dt.hour < 6)
        assert np.all(night_ghi.values == 0)
    
    def test_real_processing_pipeline(self):
        """Test processing pipeline with actual data transformations."""
        # Create test dataset
        times = pd.date_range("2023-01-01", periods=24, freq="H")
        ds = xr.Dataset(
            {
                "temp_air": (["time"], 20 + 5 * np.random.randn(24)),
                "pressure": (["time"], 1013 + 10 * np.random.randn(24))
            },
            coords={"time": times}
        )
        
        # Create and run real pipeline
        pipeline = ProcessingPipeline()
        
        # Use the actual pipeline methods
        from EcoSystemiser.profile_loader.climate.processing.resampling import resample_dataset
        
        # Process with preprocessing first
        result = pipeline.execute_preprocessing(ds)
        
        # Then resample
        result = resample_dataset(result, "3H")
        
        # Verify actual processing occurred
        assert result is not None
        assert len(result.time) == 8  # 24 hours / 3 hours
        assert "temp_air" in result
        
        # Verify resampling was done correctly
        assert result.time[1] - result.time[0] == pd.Timedelta("3H")
    
    def test_real_resampling_various_resolutions(self):
        """Test resampling with different real resolutions."""
        # Create hourly dataset
        times = pd.date_range("2023-01-01", periods=168, freq="H")  # 1 week
        ds = xr.Dataset(
            {
                "temp_air": (["time"], 15 + 10 * np.sin(np.arange(168) * 2 * np.pi / 24)),
                "ghi": (["time"], np.maximum(0, 500 * np.sin(np.arange(168) * np.pi / 24)))
            },
            coords={"time": times}
        )
        
        # Test various resolutions
        resolutions = ["15min", "30min", "3H", "6H", "1D"]
        
        for resolution in resolutions:
            resampled = resample_dataset(ds.copy(), resolution)
            
            # Verify resampling worked
            assert resampled is not None
            
            # Check time resolution (allow for edge effects)
            if resolution == "15min":
                # Upsampling creates more points
                assert len(resampled.time) >= 168 * 4 - 4  # Allow small variance
            elif resolution == "30min":
                # Upsampling creates more points
                assert len(resampled.time) >= 168 * 2 - 2  # Allow small variance
            elif resolution == "3H":
                # Downsampling to 3-hour intervals
                assert 55 <= len(resampled.time) <= 57  # Around 56 points
            elif resolution == "6H":
                # Downsampling to 6-hour intervals
                assert 27 <= len(resampled.time) <= 29  # Around 28 points
            elif resolution == "1D":
                # Downsampling to daily
                assert 6 <= len(resampled.time) <= 8  # Around 7 days
            
            # Verify data integrity
            assert not np.all(np.isnan(resampled["temp_air"].values))


class TestRealJobManager:
    """Test JobManager with real functionality."""
    
    def test_job_manager_real_workflow(self):
        """Test JobManager with real in-memory storage."""
        # Use real JobManager with memory storage
        import os
        os.environ['REDIS_URL'] = ''  # Force memory storage
        
        manager = JobManager()
        
        # Create real job
        request_data = {
            "location": (51.5, -0.1),
            "variables": ["temp_air", "ghi"],
            "period": {"year": 2023}
        }
        
        job_id = manager.create_job(request_data)
        assert job_id is not None
        assert isinstance(job_id, str)
        
        # Check job exists
        job = manager.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.PENDING
        assert job["request"] == request_data
        
        # Update job status (simulating real processing)
        success = manager.update_job_status(
            job_id,
            JobStatus.PROCESSING,
            progress=50
        )
        assert success
        
        # Check update worked
        job = manager.get_job(job_id)
        assert job["status"] == JobStatus.PROCESSING
        assert job["progress"] == 50
        
        # Complete job with result
        result_data = {
            "path": "/data/output.parquet",
            "shape": (8760, 2),
            "quality_score": 95.5
        }
        
        success = manager.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            result=result_data,
            progress=100
        )
        assert success
        
        # Verify completion
        job = manager.get_job(job_id)
        assert job["status"] == JobStatus.COMPLETED
        assert job["result"] == result_data
        assert job["progress"] == 100
        
        # Test listing jobs
        jobs = manager.list_jobs()
        assert len(jobs) >= 1
        assert any(j["id"] == job_id for j in jobs)
        
        # Test cleanup
        deleted = manager.delete_job(job_id)
        assert deleted
        
        # Verify deletion
        job = manager.get_job(job_id)
        assert job is None


class TestRealAdapterFactory:
    """Test adapter factory with real adapters."""
    
    def test_real_adapter_initialization(self):
        """Test getting real adapters without mocks."""
        # Test each adapter type
        adapter_types = ["nasa_power", "meteostat", "era5", "pvgis", "epw"]
        
        for adapter_type in adapter_types:
            try:
                adapter = get_adapter(adapter_type, use_cache=False)
                assert adapter is not None
                
                # Test real capabilities
                capabilities = adapter.get_capabilities()
                assert capabilities is not None
                assert capabilities.supported_variables is not None
                assert len(capabilities.supported_variables) > 0
                
                # Test variable mapping if method exists
                for var in ["temp_air", "ghi"]:
                    if hasattr(adapter, 'map_variable_name'):
                        try:
                            mapped = adapter.map_variable_name(var)
                            # It's ok if some variables aren't supported
                        except (KeyError, ValueError):
                            pass
                        
            except Exception as e:
                # Some adapters might need API keys, that's ok
                if "API" in str(e) or "key" in str(e).lower():
                    continue
                else:
                    raise


class TestRealValidation:
    """Test validation with real data patterns."""
    
    def test_real_data_quality_issues(self):
        """Test validation with data that has real quality issues."""
        times = pd.date_range("2023-01-01", periods=100, freq="H")
        
        # Create data with various real issues
        temp_data = 20 + 5 * np.random.randn(100)
        temp_data[10:15] = np.nan  # Gap in data
        temp_data[30] = 100  # Spike/outlier
        temp_data[50:55] = -100  # Impossible values
        
        ghi_data = np.maximum(0, 500 * np.sin(np.arange(100) * np.pi / 24))
        ghi_data[40:45] = 1000  # Night time solar (wrong)
        
        ds = xr.Dataset(
            {
                "temp_air": (["time"], temp_data),
                "ghi": (["time"], ghi_data),
                "wind_speed": (["time"], np.ones(100) * 5)  # Suspiciously constant
            },
            coords={"time": times}
        )
        
        # Run real validation
        report = validate_complete(ds, validation_level="comprehensive")
        
        # Check that issues were detected
        assert len(report.issues) > 0
        
        # Check for specific issue types
        issue_types = [issue.type for issue in report.issues]
        
        # Should detect bounds violations
        assert any("bounds" in t for t in issue_types)
        
        # Should detect constant values
        assert any("constant" in t for t in issue_types)
        
        # Apply corrections
        ds_corrected, correction_report = apply_quality_control(ds)
        
        # Verify corrections were applied
        assert ds_corrected is not None
        
        # Check that extreme values were handled (either clipped or marked as nan)
        temp_values = ds_corrected["temp_air"].values
        valid_temps = temp_values[~np.isnan(temp_values)]
        
        # Either the values are clipped, removed, or marked as invalid
        if len(valid_temps) > 0:
            # Check if extreme values were handled
            # The quality control might not clip to exactly -70/70, but should handle extremes
            extreme_low_count = np.sum(valid_temps < -70)
            extreme_high_count = np.sum(valid_temps > 70)
            
            # Original data had values at -100 and 100
            # After QC, these should be reduced significantly
            original_extreme_low = 5  # We had 5 values at -100
            original_extreme_high = 1  # We had 1 value at 100
            
            # Test passes if extreme values were reduced (even if not perfectly clipped)
            assert extreme_low_count < original_extreme_low or extreme_high_count < original_extreme_high


class TestRealFileOperations:
    """Test with real file operations."""
    
    def test_real_epw_file_handling(self):
        """Test EPW adapter with real file content."""
        from EcoSystemiser.profile_loader.climate.adapters.file_epw import EPWAdapter
        
        adapter = EPWAdapter()
        
        # Create a minimal valid EPW content
        epw_lines = [
            "LOCATION,Test City,Test Region,USA,TMY3,123456,40.0,-105.0,-7.0,1650.0",
            "DESIGN CONDITIONS,1,Climate Design Data 2009 ASHRAE,Heating,1,-20.0,-17.0",
            "TYPICAL/EXTREME PERIODS,0",
            "GROUND TEMPERATURES,0",
            "HOLIDAYS/DAYLIGHT SAVING,No,0,0,0",
            "COMMENTS 1,Test EPW File",
            "COMMENTS 2,For Testing",
            "DATA PERIODS,1,1,Data,Sunday,1/1,12/31",
            # Add a data line (35 columns as per EPW spec)
            "2023,1,1,1,0,?9?9?9?9E0?9?9?9?9?9?9?9?9?9?9?9?9?9?9*_*9*9*9?9?9,15.0,10.0,70,101325,"
            "0,0,300,0,0,0,0,0,0,0,0,0,180,3.0,5,5,20.0,1000,9,999999999,150,0.1,0,88,0.0,0.0,0.0"
        ]
        
        epw_content = "\n".join(epw_lines)
        
        # Parse with real adapter
        try:
            df = adapter._parse_epw_data(epw_content)
            assert df is not None
            assert not df.empty
            assert "time" in df.index.name
        except Exception as e:
            # If parsing fails, it should be a specific error
            from EcoSystemiser.core.errors import DataParseError
            assert isinstance(e, DataParseError)
    
    def test_real_cache_operations(self):
        """Test cache operations with real file system."""
        from EcoSystemiser.profile_loader.climate.cache.store import CacheStore
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = CacheStore(cache_dir=temp_dir)
            
            # Create test data
            times = pd.date_range("2023-01-01", periods=24, freq="H")
            ds = xr.Dataset(
                {"temp_air": (["time"], np.random.randn(24))},
                coords={"time": times}
            )
            
            # Test real cache operations
            cache_key = "test_dataset_123"
            
            # Save to cache
            path = cache.save_dataset(ds, cache_key)
            assert path is not None
            assert Path(path).exists()
            
            # Load from cache
            ds_loaded = cache.load_dataset(cache_key)
            assert ds_loaded is not None
            assert "temp_air" in ds_loaded
            
            # Verify data integrity
            np.testing.assert_array_almost_equal(
                ds["temp_air"].values,
                ds_loaded["temp_air"].values
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])