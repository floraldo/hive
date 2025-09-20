"""
Test suite for climate data processing functionality.

This module demonstrates proper absolute import paths for processing modules.
All imports use the ecosystemiser package root.
"""

import pytest
import xarray as xr
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


from EcoSystemiser.profile_loader.climate.processing.validation import (
    validate_complete, apply_quality_control, apply_corrections, 
    QCReport, QCSeverity, QCIssue
)
from EcoSystemiser.profile_loader.climate.processing.pipeline import ProcessingPipeline
from EcoSystemiser.profile_loader.climate.processing.resampling import resample_dataset
from EcoSystemiser.profile_loader.climate.processing.gap_filling import GapFiller
from EcoSystemiser.profile_loader.shared.timezone import TimezoneHandler
from EcoSystemiser.profile_loader.climate.data_models import ClimateRequest


class TestValidation:
    """Test cases for data validation functionality."""
    
    def create_sample_dataset(self) -> xr.Dataset:
        """Create a sample climate dataset for testing."""
        time = pd.date_range('2020-01-01', periods=100, freq='1H')
        
        # Create realistic climate data
        temp_air = 15 + 10 * np.sin(np.arange(100) * 2 * np.pi / 24) + np.random.randn(100) * 2
        ghi = np.maximum(0, 300 + 200 * np.sin(np.arange(100) * 2 * np.pi / 24) + np.random.randn(100) * 50)
        wind_speed = np.maximum(0, 5 + np.random.randn(100) * 2)
        rel_humidity = np.clip(60 + np.random.randn(100) * 15, 0, 100)
        
        ds = xr.Dataset({
            'temp_air': (['time'], temp_air),
            'ghi': (['time'], ghi),
            'wind_speed': (['time'], wind_speed),
            'rel_humidity': (['time'], rel_humidity)
        }, coords={'time': time})
        
        # Add some metadata
        ds.attrs['latitude'] = 51.5
        ds.attrs['longitude'] = -0.1
        ds.attrs['source'] = 'test_data'
        
        return ds
        
    def test_validate_complete_function(self):
        """Test the validate_complete module-level function."""
        ds = self.create_sample_dataset()
        
        report = validate_complete(
            ds, 
            source="test_data",
            validation_level="comprehensive",
            strict_mode=False,
            enable_profiling=True
        )
        
        assert isinstance(report, QCReport)
        assert hasattr(report, 'issues')
        assert hasattr(report, 'summary')
        
    def test_apply_quality_control(self):
        """Test the main QC entry point."""
        ds = self.create_sample_dataset()
        
        ds_qc, report = apply_quality_control(
            ds,
            source="test_data",
            comprehensive=True
        )
        
        assert isinstance(ds_qc, xr.Dataset)
        assert isinstance(report, QCReport)
        assert ds_qc.sizes == ds.sizes  # Should maintain same structure
        
    def test_apply_corrections(self):
        """Test applying corrections based on QC report."""
        ds = self.create_sample_dataset()
        
        # First run validation to get a report
        report = validate_complete(ds, source="test_data")
        
        # Apply corrections
        ds_corrected = apply_corrections(
            ds, 
            report,
            spike_filter=True,
            gap_fill=True
        )
        
        assert isinstance(ds_corrected, xr.Dataset)
        assert ds_corrected.sizes == ds.sizes
        
    def test_qc_report_functionality(self):
        """Test QC report creation and methods."""
        report = QCReport(
            dataset_id="test_dataset",
            timestamp=datetime.now().isoformat()
        )
        
        # Add a test issue
        issue = QCIssue(
            type="test",
            message="Test issue",
            severity=QCSeverity.LOW,
            affected_variables=["temp_air"]
        )
        
        report.add_issue(issue)
        
        assert len(report.issues) == 1
        assert len(report.get_issues_by_severity(QCSeverity.LOW)) == 1
        assert not report.has_critical_issues()
        
        # Test quality score calculation
        score = report.calculate_quality_score()
        assert 0 <= score <= 100


class TestProcessingPipeline:
    """Test cases for the processing pipeline."""
    
    def test_pipeline_initialization(self):
        """Test pipeline initializes correctly."""
        pipeline = ProcessingPipeline()
        assert pipeline is not None
        assert hasattr(pipeline, 'execute_preprocessing')
        
    def test_pipeline_execution(self):
        """Test pipeline execution with sample data."""
        pipeline = ProcessingPipeline()
        
        # Create sample dataset
        time = pd.date_range('2020-01-01', periods=24, freq='1H')
        ds = xr.Dataset({
            'temp_air': (['time'], np.random.randn(24) + 15)
        }, coords={'time': time})
        
        # Execute pipeline
        ds_processed = pipeline.execute_preprocessing(ds)
        
        assert isinstance(ds_processed, xr.Dataset)
        assert 'temp_air' in ds_processed.data_vars


class TestResampling:
    """Test cases for data resampling functionality."""
    
    def test_resample_dataset(self):
        """Test dataset resampling functionality."""
        # Create hourly data
        time = pd.date_range('2020-01-01', periods=24, freq='1H')
        ds = xr.Dataset({
            'temp_air': (['time'], np.random.randn(24) + 15)
        }, coords={'time': time})
        
        # Resample to 3-hourly
        ds_resampled = resample_dataset(ds, target_resolution='3H')
        
        assert isinstance(ds_resampled, xr.Dataset)
        assert len(ds_resampled.time) == 8  # 24 hours / 3 = 8 points
        
    def test_resample_invalid_resolution(self):
        """Test resampling with invalid resolution."""
        time = pd.date_range('2020-01-01', periods=24, freq='1H')
        ds = xr.Dataset({
            'temp_air': (['time'], np.random.randn(24) + 15)
        }, coords={'time': time})
        
        with pytest.raises(ValueError):
            resample_dataset(ds, target_resolution='invalid')


class TestTimezoneProcessing:
    """Test cases for timezone processing utilities."""
    
    def test_timezone_handler_integration(self):
        """Test timezone handler works with datasets."""
        handler = TimezoneHandler()
        
        # Create UTC dataset
        time_utc = pd.date_range('2020-01-01', periods=24, freq='1H', tz='UTC')
        ds = xr.Dataset({
            'temp_air': (['time'], np.random.randn(24) + 15)
        }, coords={'time': time_utc})
        
        # Test handler can process dataset
        assert handler is not None
        # More specific timezone tests would go here


class TestDataIntegrity:
    """Test cases for data integrity and consistency."""
    
    def test_no_data_corruption_through_pipeline(self):
        """Test that data maintains integrity through processing."""
        # Create dataset with known values
        time = pd.date_range('2020-01-01', periods=10, freq='1H')
        original_values = np.array([10, 15, 20, 25, 30, 25, 20, 15, 10, 5])
        
        ds = xr.Dataset({
            'temp_air': (['time'], original_values)
        }, coords={'time': time})
        
        # Run through QC
        ds_qc, report = apply_quality_control(ds, comprehensive=False)
        
        # Check that reasonable values are preserved
        qc_values = ds_qc['temp_air'].values
        
        # Should maintain general pattern (allowing for minor corrections)
        assert len(qc_values) == len(original_values)
        assert np.corrcoef(original_values, qc_values)[0, 1] > 0.9  # High correlation


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__])