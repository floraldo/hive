from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
Debug service for EcoSystemiser - Targeted debugging without CLI overhead

This script allows direct testing of the climate service layer,
bypassing CLI argument parsing for faster iteration during debugging.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
import json

# Add the src directory to the Python path
src_root = Path(__file__).resolve().parent / "src"
# Now we can import from the EcoSystemiser package
from EcoSystemiser.profile_loader.climate.data_models import ClimateRequest, ClimateResponse
from EcoSystemiser.profile_loader.climate.service import ClimateService
from EcoSystemiser.errors import ClimateError
import xarray as xr
import pandas as pd

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
log = logging.getLogger(__name__)

def debug_single_request():
    """
    Test a single climate request with detailed output.
    Modify the request parameters to test different scenarios.
    """
    log.info("=" * 60)
    log.info("Starting Debug Session")
    log.info("=" * 60)

    try:
        # ===========================================================
        # MODIFY THIS REQUEST TO TEST DIFFERENT SCENARIOS
        # ===========================================================
        
        # Example 1: Meteostat request (requires internet)
        request = ClimateRequest(
            location=(52.5200, 13.4050),  # Berlin
            variables=["temp_air", "wind_speed", "rel_humidity"],
            period={"start": "2023-08-01", "end": "2023-08-07"},
            source="meteostat",
            mode="observed",
        )
        
        # Example 2: Local EPW file (uncomment to use)
        # request = ClimateRequest(
        #     location=(41.9, -87.9),  # Chicago
        #     variables=["temp_air", "ghi", "dhi", "wind_speed"],
        #     period={"file": "tests/test_data/USA_IL_Chicago.epw"},
        #     source="epw",
        #     mode="observed",
        # )
        
        # Example 3: TMY generation (uncomment to use)
        # request = ClimateRequest(
        #     location=(40.7128, -74.0060),  # New York
        #     variables=["temp_air", "ghi"],
        #     period={"start": "2010-01-01", "end": "2020-12-31"},
        #     source="nasa_power",
        #     mode="tmy",
        # )
        
        log.info(f"Request configuration:\n{json.dumps(request.model_dump(), indent=2)}")
        
        # ===========================================================
        # EXECUTE REQUEST
        # ===========================================================
        
        log.info("Creating service instance...")
        service = ClimateService()
        
        log.info("Processing request...")
        start_time = datetime.now()
        
        # Use the synchronous wrapper
        result = service.process_request(request)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        log.info(f"Request completed in {elapsed:.2f} seconds")
        
        # ===========================================================
        # INSPECT RESULTS
        # ===========================================================
        
        if isinstance(result, tuple):
            ds, response = result
        else:
            # Handle if only dataset is returned
            ds = result
            response = None
        
        log.info("=" * 60)
        log.info("RESULTS")
        log.info("=" * 60)
        
        # Dataset information
        log.info("\n--- Dataset Structure ---")
        logger.info(f"Dimensions: {dict(ds.dims)}")
        logger.info(f"Variables: {list(ds.data_vars)}")
        logger.info(f"Coordinates: {list(ds.coords)}")
        logger.info(f"Attributes: {dict(ds.attrs)}")
        
        # Show data sample
        log.info("\n--- Data Sample (first 5 records) ---")
        df = ds.to_dataframe()
        logger.info(df.head())
        
        # Show statistics
        log.info("\n--- Variable Statistics ---")
        for var in ds.data_vars:
            data = ds[var].values
            logger.info(f"{var}:")
            logger.info(f"  Min: {data.min():.2f}")
            logger.info(f"  Max: {data.max():.2f}")
            logger.info(f"  Mean: {data.mean():.2f}")
            logger.info(f"  Std: {data.std():.2f}")
            logger.info(f"  NaN count: {pd.isna(data).sum()}")
        
        # Response information
        if response:
            log.info("\n--- Response Metadata ---")
            if hasattr(response, 'manifest'):
                logger.info(f"Manifest keys: {response.manifest.keys() if isinstance(response.manifest, dict) else 'N/A'}")
            if hasattr(response, 'path_parquet'):
                logger.info(f"Output path: {response.path_parquet}")
            if hasattr(response, 'stats'):
                logger.info(f"Stats: {response.stats}")
        
        # ===========================================================
        # INTERACTIVE DEBUGGING POINT
        # ===========================================================
        
        # Uncomment the following line to drop into an interactive debugger
        # import pdb; pdb.set_trace()
        
        # Or use IPython for a better experience (if installed)
        # from IPython import embed; embed()
        
        log.info("\n" + "=" * 60)
        log.info("Debug session completed successfully!")
        log.info("=" * 60)
        
    except ClimateError as e:
        log.error("=" * 60)
        log.error("CLIMATE ERROR OCCURRED")
        log.error("=" * 60)
        logger.error(f"\nError Type: {e.__class__.__name__}")
        logger.error(f"Error Code: {e.code.value if hasattr(e, 'code') else 'N/A'}")
        logger.info(f"Message: {str(e)}")
        if hasattr(e, 'details') and e.details:
            logger.info(f"Details: {json.dumps(e.details, indent=2)}")
        if hasattr(e, 'suggested_action') and e.suggested_action:
            logger.info(f"Suggested Action: {e.suggested_action}")
        log.error("Full exception:", exc_info=True)
        
    except Exception as e:
        log.error("=" * 60)
        log.error("UNEXPECTED ERROR")
        log.error("=" * 60)
        log.error(f"Error: {str(e)}", exc_info=True)

def debug_multiple_sources():
    """
    Test fallback behavior by trying multiple sources.
    """
    log.info("Testing multi-source fallback...")
    
    sources = ["nasa_power", "meteostat", "era5"]
    location = (52.5200, 13.4050)  # Berlin
    
    for source in sources:
        log.info(f"\nTrying source: {source}")
        try:
            request = ClimateRequest(
                location=location,
                variables=["temp_air"],
                period={"start": "2023-06-01", "end": "2023-06-07"},
                source=source,
                mode="observed",
            )
            
            service = ClimateService()
            ds, _ = service.process_request(request)
            
            log.info(f"✓ {source} succeeded - got {len(ds.time)} records")
            
        except Exception as e:
            log.warning(f"✗ {source} failed: {str(e)}")

def debug_processing_pipeline():
    """
    Test the processing pipeline with synthetic data.
    """
    log.info("Testing processing pipeline...")
    
    # Create synthetic dataset
    import numpy as np
    import pandas as pd
    
    times = pd.date_range("2023-01-01", "2023-01-31", freq="H")
    temp = 20 + 10 * np.sin(np.arange(len(times)) * 2 * np.pi / 24) + np.random.randn(len(times)) * 2
    
    # Add some gaps and outliers
    temp[100:150] = np.nan  # Gap
    temp[200] = 100  # Outlier
    temp[300] = -50  # Outlier
    
    ds = xr.Dataset(
        {
            "temp_air": (["time"], temp),
            "ghi": (["time"], np.maximum(0, 500 * np.sin(np.arange(len(times)) * 2 * np.pi / 24))),
        },
        coords={"time": times}
    )
    
    log.info(f"Created synthetic dataset with {len(ds.time)} hourly records")
    log.info(f"  - Gaps: {np.isnan(temp).sum()}")
    log.info(f"  - Outliers: 2")
    
    # Apply processing
    from profile_loader.climate.processing.validation import apply_quality_control
    
    ds_processed, qc_report = apply_quality_control(
        ds, 
        spike_filter=True,
        gap_fill=True,
        comprehensive=True
    )
    
    log.info("\nQC Report:")
    log.info(f"  - Issues found: {len(qc_report.issues)}")
    for issue in qc_report.issues[:5]:  # Show first 5 issues
        log.info(f"    • {issue.severity.value}: {issue.message}")
    
    log.info(f"\nProcessed data:")
    log.info(f"  - Remaining gaps: {np.isnan(ds_processed['temp_air'].values).sum()}")

if __name__ == "__main__":
    # Choose which debug function to run
    # Modify this to test different aspects
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "multi":
            debug_multiple_sources()
        elif mode == "pipeline":
            debug_processing_pipeline()
        else:
            log.error(f"Unknown mode: {mode}")
            logger.debug("Usage: python debug_service.py [multi|pipeline]")
    else:
        # Default: single request debug
        debug_single_request()