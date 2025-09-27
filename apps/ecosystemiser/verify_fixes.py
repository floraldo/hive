#!/usr/bin/env python3
"""
Verify that all production fixes have been implemented correctly.
"""

import sys
import os

def test_climate_response_validation():
    """Test that ClimateResponse includes all required base fields."""
    print("Testing ClimateResponse validation...")
    
    import xarray as xr
    import pandas as pd
    import numpy as np
    from EcoSystemiser.profile_loader.climate.data_models import ClimateRequest, ClimateResponse
    from EcoSystemiser.profile_loader.climate.service import ClimateService
    
    # Create a mock dataset
    times = pd.date_range("2023-01-01", periods=24, freq="h")
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
    try:
        response = service._cache_and_respond(ds, request, processing_report)
        
        # Verify all required fields are present
        assert response.start_time is not None, "start_time is missing"
        assert response.end_time is not None, "end_time is missing"
        assert response.variables == ["temp_air", "ghi"], "variables mismatch"
        assert response.source == "nasa_power", "source mismatch"
        assert response.shape == (24, 2), "shape mismatch"
        
        print("[PASS] ClimateResponse validation test PASSED")
        return True
    except Exception as e:
        print(f"[FAIL] ClimateResponse validation test FAILED: {e}")
        return False

def test_job_manager():
    """Test the production-ready job manager."""
    print("\nTesting JobManager...")
    
    from EcoSystemiser.profile_loader.climate.job_manager import JobManager, JobStatus
    
    # Create manager without Redis (fallback to memory)
    os.environ['REDIS_URL'] = ''  # Ensure we use memory fallback
    manager = JobManager()
    
    # Should fall back to memory store
    assert manager.redis is None, "Should use memory store"
    assert manager._memory_store is not None, "Memory store not initialized"
    
    # Test basic operations
    job_id = manager.create_job({"test": "data"})
    assert job_id is not None, "Job ID not created"
    
    job = manager.get_job(job_id)
    assert job is not None, "Job not found"
    assert job["status"] == JobStatus.PENDING, "Wrong initial status"
    assert job["request"] == {"test": "data"}, "Request data mismatch"
    
    # Update status
    success = manager.update_job_status(
        job_id,
        JobStatus.COMPLETED,
        result={"output": "result"}
    )
    assert success is True, "Job update failed"
    
    # Check updated job
    job = manager.get_job(job_id)
    assert job["status"] == JobStatus.COMPLETED, "Status not updated"
    assert job["result"] == {"output": "result"}, "Result not stored"
    
    print("[PASS] JobManager test PASSED")
    return True

def test_epw_error_handling():
    """Test EPW file parser error handling."""
    print("\nTesting EPW error handling...")
    
    from EcoSystemiser.profile_loader.climate.adapters.file_epw import EPWAdapter
    from EcoSystemiser.errors import DataParseError
    
    adapter = EPWAdapter()
    
    # Test with too short file
    short_content = "LOCATION,Test\\nDATA"
    try:
        adapter._parse_epw_data(short_content)
        print("[FAIL] EPW error handling test FAILED: Should have raised DataParseError for short file")
        return False
    except DataParseError as e:
        if "too short" not in str(e).lower():
            print(f"[FAIL] EPW error handling test FAILED: Wrong error message: {e}")
            return False
    
    # Test with invalid CSV data
    invalid_content = "\\n" * 10 + "not,valid,csv,data\\n,,,\\n"
    try:
        adapter._parse_epw_data(invalid_content)
        print("[FAIL] EPW error handling test FAILED: Should have raised DataParseError for invalid CSV")
        return False
    except DataParseError as e:
        if "parse" not in str(e).lower() and "short" not in str(e).lower():
            print(f"[FAIL] EPW error handling test FAILED: Wrong error message: {e}")
            return False
    
    print("[PASS] EPW error handling test PASSED")
    return True

def test_time_gap_detection():
    """Test improved time gap detection with explicit frequency."""
    print("\nTesting time gap detection...")
    
    import xarray as xr
    import pandas as pd
    import numpy as np
    from EcoSystemiser.profile_loader.climate.processing.validation import ValidationProcessor
    
    processor = ValidationProcessor()
    
    # Create dataset with a gap
    times = pd.date_range("2023-01-01", periods=10, freq="h").tolist()
    times.pop(5)  # Remove one timestamp to create a gap
    
    ds = xr.Dataset(
        {"temp": (["time"], np.ones(9))},
        coords={"time": times}
    )
    
    # Check gaps with explicit frequency
    issues = processor._check_time_gaps(ds, expected_freq="1H")
    
    # Should detect the missing timestamp
    assert len(issues) > 0, "No issues detected"
    assert any("missing" in issue.message.lower() or "gap" in issue.message.lower() 
               for issue in issues), "Missing timestamp not detected"
    
    # Verify the expected frequency was used
    gap_issue = next((i for i in issues if "missing" in i.message.lower() or "gap" in i.message.lower()), None)
    assert gap_issue is not None, "No gap issue found"
    
    # Check that frequency information is in metadata
    metadata = gap_issue.metadata or {}
    if 'expected_freq' in metadata:
        assert "1H" in str(metadata['expected_freq']), "Expected frequency not used"
    
    print("[PASS] Time gap detection test PASSED")
    return True

def test_factory_no_sys_path():
    """Test that factory doesn't manipulate sys.path."""
    print("\nTesting factory sys.path cleanup...")
    
    import sys
    original_path = sys.path.copy()
    
    # Import should not modify sys.path
    from EcoSystemiser.profile_loader.climate.adapters.factory import _auto_register_adapters
    
    # Check path wasn't modified
    assert sys.path == original_path, "sys.path was modified on import"
    
    # Run auto-register
    _auto_register_adapters()
    
    # Path should still be unchanged
    assert sys.path == original_path, "sys.path was modified by _auto_register_adapters"
    
    print("[PASS] Factory sys.path test PASSED")
    return True

def main():
    """Run all verification tests."""
    print("=" * 60)
    print("PRODUCTION FIXES VERIFICATION")
    print("=" * 60)
    
    results = []
    
    # Run each test
    results.append(("ClimateResponse validation", test_climate_response_validation()))
    results.append(("JobManager", test_job_manager()))
    results.append(("EPW error handling", test_epw_error_handling()))
    results.append(("Time gap detection", test_time_gap_detection()))
    results.append(("Factory sys.path cleanup", test_factory_no_sys_path()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS] PASSED" if result else "[FAIL] FAILED"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nSUCCESS: ALL PRODUCTION FIXES VERIFIED SUCCESSFULLY!")
        return 0
    else:
        print(f"\nWARNING:  {total - passed} tests failed. Please review the failures above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())