"""
Enhanced Climate API v2 with batch processing, streaming, and async job support.

Key improvements:
- Batch endpoints for multiple locations/periods
- Streaming responses for large datasets
- Async job queue for heavy processing
- Standardized error responses
- OpenAPI documentation
"""

import asyncio
import gzip
import hashlib
import json
import uuid
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional, Union, AsyncIterator, Tuple
import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Header, Response, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, validator
import xarray as xr
import pandas as pd
import numpy as np

from .data_models import ClimateRequest, ClimateResponse, Mode, Resolution
from .job_manager import JobManager, JobStatus as JobStatusEnum, get_job_manager
from EcoSystemiser.errors import (
    ClimateError,
    ValidationError,
    DataFetchError
)
from EcoSystemiser.profile_loader.shared.timezone import TimezoneHandler

logger = logging.getLogger(__name__)

# Create APIRouter
router = APIRouter(
    prefix="",  # No prefix here, will be set in main.py
    tags=["Climate Data"]
)

# Middleware will be handled by main FastAPI app


# Enhanced request/response models

class BatchClimateRequest(BaseModel):
    """Batch request for multiple climate data queries"""
    requests: List[ClimateRequest] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of climate requests to process"
    )
    parallel: bool = Field(
        default=True,
        description="Process requests in parallel"
    )
    partial_success: bool = Field(
        default=True,
        description="Return partial results if some requests fail"
    )


class JobStatus(str, Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobRequest(BaseModel):
    """Async job request"""
    request: Union[ClimateRequest, BatchClimateRequest]
    priority: int = Field(default=5, ge=1, le=10)
    callback_url: Optional[str] = None
    notification_email: Optional[str] = None


class JobResponse(BaseModel):
    """Job status response"""
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress: Optional[float] = Field(None, ge=0, le=100)
    result_url: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    eta: Optional[datetime] = None


class StreamFormat(str, Enum):
    """Streaming response formats"""
    NDJSON = "ndjson"
    CSV = "csv"
    PARQUET = "parquet"
    NETCDF = "netcdf"


# Job management now properly uses Redis-backed JobManager for production
# All endpoints interact with the distributed job manager


# API Endpoints

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@router.post("/single", response_model=ClimateResponse)
async def get_climate_single(
    request: ClimateRequest,
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    accept_encoding: Optional[str] = Header(None, alias="Accept-Encoding")
):
    """
    Get climate data for a single location and period.
    
    Enhanced with correlation ID tracking and compression support.
    """
    # Get or create correlation ID
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    context = dict(
        correlation_id=correlation_id,
        location=request.location if isinstance(request.location, tuple) else None,
        variables=request.variables,
        period=request.period
    )
    
    try:
        # Process request (placeholder - integrate with actual service)
        result = await process_climate_request(request, context)
        
        # Check if client accepts gzip
        if accept_encoding and 'gzip' in accept_encoding:
            # Response will be gzipped by middleware
            pass
        
        return result
        
    except ClimateError as e:
        # Already structured error
        error_response = {"error": str(e), "status_code": 400}
        return JSONResponse(
            content=error_response,
            status_code=error_response['status_code'],
            headers={"X-Correlation-ID": correlation_id}
        )
    except Exception as e:
        # Unexpected error
        climate_error = ClimateError(f"Internal error: {str(e)}")
        error_response = {"error": str(climate_error), "status_code": 500}
        return JSONResponse(
            content=error_response,
            status_code=500,
            headers={"X-Correlation-ID": correlation_id}
        )


@router.post("/batch")
async def get_climate_batch(
    batch_request: BatchClimateRequest,
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID")
):
    """
    Process multiple climate requests in batch.
    
    Supports parallel processing and partial success.
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    results = []
    errors = []
    
    if batch_request.parallel:
        # Process in parallel
        tasks = [
            process_climate_request(req, dict(correlation_id=f"{correlation_id}_{i}"))
            for i, req in enumerate(batch_request.requests)
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                errors.append({
                    "index": i,
                    "error": str(response)
                })
                if not batch_request.partial_success:
                    # Fail fast if partial success not allowed
                    raise HTTPException(
                        status_code=400,
                        detail=f"Request {i} failed: {response}"
                    )
            else:
                results.append({
                    "index": i,
                    "data": response
                })
    else:
        # Process sequentially
        for i, req in enumerate(batch_request.requests):
            try:
                result = await process_climate_request(
                    req,
                    dict(correlation_id=f"{correlation_id}_{i}")
                )
                results.append({
                    "index": i,
                    "data": result
                })
            except Exception as e:
                errors.append({
                    "index": i,
                    "error": str(e)
                })
                if not batch_request.partial_success:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Request {i} failed: {e}"
                    )
    
    return {
        "correlation_id": correlation_id,
        "total_requests": len(batch_request.requests),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors if errors else None
    }


@router.post("/stream")
async def stream_climate_data(
    request: ClimateRequest,
    format: StreamFormat = Query(StreamFormat.NDJSON),
    chunk_size: int = Query(1000, ge=100, le=10000),
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID")
):
    """
    Stream climate data for large requests.
    
    Supports NDJSON, CSV, Parquet, and NetCDF formats.
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    context = dict(correlation_id=correlation_id)
    
    async def generate_stream():
        """Generate streaming response"""
        try:
            # Get data (placeholder - integrate with actual service)
            ds = await fetch_climate_data(request, context)
            
            if format == StreamFormat.NDJSON:
                # Stream as NDJSON (newline-delimited JSON)
                async for chunk in stream_as_ndjson(ds, chunk_size):
                    yield chunk
                    
            elif format == StreamFormat.CSV:
                # Stream as CSV
                async for chunk in stream_as_csv(ds, chunk_size):
                    yield chunk
                    
            elif format == StreamFormat.PARQUET:
                # Stream as Parquet
                yield stream_as_parquet(ds)
                
            elif format == StreamFormat.NETCDF:
                # Stream as NetCDF
                yield stream_as_netcdf(ds)
                
        except Exception as e:
            # Stream error as final chunk
            error_data = json.dumps({
                "error": str(e),
                "correlation_id": correlation_id
            })
            yield error_data.encode()
    
    # Set appropriate content type
    content_type_map = {
        StreamFormat.NDJSON: "application/x-ndjson",
        StreamFormat.CSV: "text/csv",
        StreamFormat.PARQUET: "application/octet-stream",
        StreamFormat.NETCDF: "application/x-netcdf"
    }
    
    return StreamingResponse(
        generate_stream(),
        media_type=content_type_map[format],
        headers={
            "X-Correlation-ID": correlation_id,
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post("/jobs", response_model=JobResponse)
async def create_climate_job(
    job_request: JobRequest,
    background_tasks: BackgroundTasks,
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    Create async job for heavy climate data processing.

    Returns job ID for status polling.
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    # Store the job request data for the worker
    request_data = {
        "type": "climate_request",
        "request": job_request.model_dump(),
        "correlation_id": correlation_id,
        "priority": job_request.priority
    }

    # Create job using the distributed job manager
    job_id = job_manager.create_job(request_data)

    # Queue background processing
    background_tasks.add_task(
        process_job_async,
        job_id,
        job_request,
        correlation_id,
        job_manager
    )

    # Get the created job data
    job_data = job_manager.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=500, detail="Failed to create job")

    # Convert to API response format
    return JobResponse(
        job_id=job_data["id"],
        status=JobStatus(job_data["status"]),
        created_at=datetime.fromisoformat(job_data["created_at"]),
        updated_at=datetime.fromisoformat(job_data["updated_at"]),
        progress=job_data.get("progress", 0)
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: str,
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    job_manager: JobManager = Depends(get_job_manager)
):
    """Get status of async job from distributed job manager"""
    job_data = job_manager.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    # Convert to API response format
    return JobResponse(
        job_id=job_data["id"],
        status=JobStatus(job_data["status"]),
        created_at=datetime.fromisoformat(job_data["created_at"]),
        updated_at=datetime.fromisoformat(job_data["updated_at"]),
        progress=job_data.get("progress", 0),
        result_url=f"/api/v2/climate/jobs/{job_id}/result" if job_data["status"] == "completed" else None,
        error=job_data.get("error"),
        eta=datetime.fromisoformat(job_data["eta"]) if job_data.get("eta") else None
    )


@router.get("/jobs/{job_id}/result")
async def get_job_result(
    job_id: str,
    format: StreamFormat = Query(StreamFormat.NDJSON),
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    Get result of completed job from distributed storage.

    Supports multiple output formats.
    """
    job_data = job_manager.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_data["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job status is {job_data['status']}, not completed"
        )

    if not job_data.get("result"):
        raise HTTPException(status_code=404, detail="Job result not found")

    result = job_data["result"]

    # Format and return result based on requested format
    if format == StreamFormat.NDJSON:
        # Convert result to proper format for streaming
        if isinstance(result, dict) and "data" in result:
            async def generate_result_stream():
                # Stream the result data as NDJSON
                yield json.dumps(result).encode() + b"\n"

            return StreamingResponse(
                generate_result_stream(),
                media_type="application/x-ndjson",
                headers={"X-Correlation-ID": correlation_id or ""}
            )

    # Return raw result for other formats
    return result


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: str,
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    job_manager: JobManager = Depends(get_job_manager)
):
    """Cancel a queued or running job using distributed job manager"""
    job_data = job_manager.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_data["status"] in ["completed", "failed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status {job_data['status']}"
        )

    # Update job status to cancelled
    success = job_manager.update_job_status(
        job_id,
        "cancelled",
        error="Job cancelled by user request"
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to cancel job")

    return {"message": f"Job {job_id} cancelled"}


@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by job status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of jobs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    List jobs with optional filtering and pagination.

    Supports filtering by status and pagination for production job monitoring.
    """
    try:
        # Get jobs from distributed job manager
        jobs_data = job_manager.list_jobs(status=status, limit=limit, offset=offset)

        # Convert to API response format
        jobs = []
        for job_data in jobs_data:
            job_response = JobResponse(
                job_id=job_data["id"],
                status=JobStatus(job_data["status"]),
                created_at=datetime.fromisoformat(job_data["created_at"]),
                updated_at=datetime.fromisoformat(job_data["updated_at"]),
                progress=job_data.get("progress", 0),
                result_url=f"/api/v2/climate/jobs/{job_data['id']}/result" if job_data["status"] == "completed" else None,
                error=job_data.get("error"),
                eta=datetime.fromisoformat(job_data["eta"]) if job_data.get("eta") else None
            )
            jobs.append(job_response)

        return {
            "jobs": jobs,
            "total": len(jobs),
            "limit": limit,
            "offset": offset,
            "filter": {"status": status} if status else None
        }

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs")


@router.delete("/jobs/cleanup")
async def cleanup_old_jobs(
    days: int = Query(7, ge=1, le=365, description="Delete jobs older than this many days"),
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    Clean up old jobs for maintenance.

    This endpoint helps maintain the job storage by removing old completed/failed jobs.
    """
    try:
        deleted_count = job_manager.cleanup_old_jobs(days=days)

        return {
            "message": f"Cleaned up {deleted_count} old jobs",
            "deleted_count": deleted_count,
            "cutoff_days": days
        }

    except Exception as e:
        logger.error(f"Failed to cleanup jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup old jobs")


# Helper functions

async def process_climate_request(
    request: ClimateRequest,
    context: dict
) -> ClimateResponse:
    """
    Process single climate request using the actual climate service.
    """
    # Get the enhanced climate service
    from .service import get_enhanced_climate_service
    
    service = get_enhanced_climate_service()
    
    # Process the request through the full pipeline
    response = service.get_climate(request)
    
    return response


async def fetch_climate_data(
    request: ClimateRequest,
    context: dict
) -> xr.Dataset:
    """
    Fetch climate data as xarray Dataset.
    
    Placeholder - integrate with actual adapters.
    """
    # This would use the async adapters
    # For now, create mock dataset
    
    time = pd.date_range('2020-01-01', periods=8760, freq='h')
    
    ds = xr.Dataset({
        'temp_air': (['time'], np.random.randn(8760) * 10 + 15),
        'ghi': (['time'], np.maximum(0, np.random.randn(8760) * 200 + 300))
    }, coords={'time': time})
    
    return ds


async def stream_as_ndjson(
    ds: xr.Dataset,
    chunk_size: int
) -> AsyncIterator[bytes]:
    """Stream dataset as NDJSON with memory-efficient chunking"""
    # Process time dimension in chunks to avoid loading entire dataset
    time_dim = 'time' if 'time' in ds.dims else list(ds.dims)[0]
    total_size = len(ds[time_dim])
    
    for i in range(0, total_size, chunk_size):
        # Select chunk using xarray's isel for memory efficiency
        end_idx = min(i + chunk_size, total_size)
        chunk_ds = ds.isel({time_dim: slice(i, end_idx)})
        
        # Convert only this chunk to DataFrame
        chunk_df = chunk_ds.to_dataframe()
        
        # Stream each row as JSON
        for _, row in chunk_df.iterrows():
            json_line = row.to_json() + "\n"
            yield json_line.encode()


async def stream_as_csv(
    ds: xr.Dataset,
    chunk_size: int
) -> AsyncIterator[bytes]:
    """Stream dataset as CSV with memory-efficient chunking"""
    # Process time dimension in chunks
    time_dim = 'time' if 'time' in ds.dims else list(ds.dims)[0]
    total_size = len(ds[time_dim])
    
    # Yield header from first small chunk
    first_chunk = ds.isel({time_dim: slice(0, 1)}).to_dataframe()
    header = ",".join(first_chunk.columns) + "\n"
    yield header.encode()
    
    # Yield data chunks without loading entire dataset
    for i in range(0, total_size, chunk_size):
        end_idx = min(i + chunk_size, total_size)
        chunk_ds = ds.isel({time_dim: slice(i, end_idx)})
        
        # Convert only this chunk to DataFrame and CSV
        chunk_df = chunk_ds.to_dataframe()
        csv_chunk = chunk_df.to_csv(index=False, header=False)
        yield csv_chunk.encode()


def stream_as_parquet(ds: xr.Dataset) -> bytes:
    """Convert dataset to Parquet bytes"""
    df = ds.to_dataframe()
    buffer = BytesIO()
    df.to_parquet(buffer, engine='pyarrow', compression='snappy')
    return buffer.getvalue()


def stream_as_netcdf(ds: xr.Dataset) -> bytes:
    """Convert dataset to NetCDF bytes"""
    buffer = BytesIO()
    ds.to_netcdf(buffer, engine='h5netcdf')
    return buffer.getvalue()


async def process_job_async(
    job_id: str,
    job_request: JobRequest,
    correlation_id: str,
    job_manager: JobManager
):
    """
    Process job asynchronously using distributed job manager.

    This integrates with Redis-backed job storage for production scalability.
    """
    try:
        # Update status to processing
        job_manager.update_job_status(job_id, "processing", progress=0)

        # Process request based on type
        if isinstance(job_request.request, ClimateRequest):
            # Update progress
            job_manager.update_job_status(job_id, "processing", progress=25)

            result = await process_climate_request(
                job_request.request,
                dict(correlation_id=correlation_id)
            )

            # Convert result to serializable format
            serializable_result = {
                "type": "climate_response",
                "data": result.model_dump() if hasattr(result, 'model_dump') else result,
                "correlation_id": correlation_id,
                "processed_at": datetime.utcnow().isoformat()
            }
        else:
            # Batch request processing
            job_manager.update_job_status(job_id, "processing", progress=25)

            # Process batch (simplified for now)
            serializable_result = {
                "type": "batch_response",
                "data": {"batch": "result", "processed": "placeholder"},
                "correlation_id": correlation_id,
                "processed_at": datetime.utcnow().isoformat()
            }

        # Update job as completed with result
        job_manager.update_job_status(
            job_id,
            "completed",
            result=serializable_result,
            progress=100
        )

        # Send notifications if configured
        if job_request.callback_url:
            # TODO: Implement callback notification
            logger.info(f"Job {job_id} completed - callback URL configured: {job_request.callback_url}")

        if job_request.notification_email:
            # TODO: Implement email notification
            logger.info(f"Job {job_id} completed - email notification configured: {job_request.notification_email}")

    except Exception as e:
        # Handle failure using distributed job manager
        error_message = str(e)
        job_manager.update_job_status(
            job_id,
            "failed",
            error=error_message
        )

        logger.error(f"Job {job_id} failed: {e}", exc_info=True)


# ============================================================================
# Analytics Endpoints (Postprocessing)
# ============================================================================

class AnalyticsRequest(BaseModel):
    """Request for analytics/postprocessing only"""
    location: Union[Tuple[float, float], str]
    period: Dict[str, Union[int, str]]
    source: str = "nasa_power"
    resolution: Optional[str] = "1H"
    analytics_options: Dict[str, Any] = Field(default_factory=dict)
    

class ProcessingOptions(BaseModel):
    """Processing options for climate requests"""
    # Preprocessing options
    fill_gaps: bool = True
    derive_basic_vars: bool = True
    qc_strict: bool = False
    
    # Postprocessing options  
    include_analytics: bool = False
    derive_building_params: bool = False
    calculate_degree_days: bool = False
    calculate_statistics: bool = False
    calculate_extremes: bool = False
    

class ExtendedClimateRequest(ClimateRequest):
    """Extended climate request with processing options"""
    processing_options: ProcessingOptions = Field(default_factory=ProcessingOptions)


@router.post("/analyze")
async def analyze_climate_data(
    request: AnalyticsRequest,
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID")
):
    """
    Run analytics on existing climate data (postprocessing only).
    
    This endpoint assumes data is already available and just runs
    postprocessing analytics without fetching or preprocessing.
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    try:
        # Import processing modules
        from .analysis.statistics import calculate_statistics
        from .analysis.extremes import analyze_extremes
        from .analysis.building_science import derive_building_variables, calculate_design_conditions
        from .service import get_enhanced_climate_service
        
        # Get data using climate service (will be preprocessed)
        service = get_enhanced_climate_service()
        climate_req = ClimateRequest(
            location=request.location,
            period=request.period,
            source=request.source,
            resolution=request.resolution or "1H",
            mode="observed"
        )
        
        # Fetch and preprocess data
        response = service.get_climate(climate_req)
        
        # Load dataset from parquet
        import xarray as xr
        ds = xr.open_dataset(response.path_parquet, engine='pyarrow')
        
        # Run analytics based on options
        analytics_results = {}
        options = request.analytics_options
        
        # Statistics
        if options.get('statistics', True):
            stats = calculate_statistics(
                ds, 
                percentiles=options.get('percentiles', [1, 5, 25, 50, 75, 95, 99])
            )
            analytics_results['statistics'] = stats
        
        # Extremes analysis
        if options.get('extremes', True):
            extremes = analyze_extremes(ds, config=options)
            analytics_results['extremes'] = extremes
        
        # Design conditions
        if options.get('design_conditions', False):
            design = calculate_design_conditions(ds)
            analytics_results['design_conditions'] = design
        
        # Building variables
        if options.get('building_metrics', False):
            building_config = {
                'calculate_degree_days': True,
                'calculate_wet_bulb': True,
                'calculate_heat_index': True,
                'hdd_base_temp': options.get('hdd_base', 18.0),
                'cdd_base_temp': options.get('cdd_base', 24.0)
            }
            ds_building = derive_building_variables(ds, config=building_config)
            
            # Extract degree day totals if calculated
            if 'hdd' in ds_building:
                analytics_results['heating_degree_days'] = float(ds_building.hdd.sum().values)
            if 'cdd' in ds_building:
                analytics_results['cooling_degree_days'] = float(ds_building.cdd.sum().values)
        
        return {
            "correlation_id": correlation_id,
            "location": request.location,
            "period": request.period,
            "analytics": analytics_results,
            "data_shape": response.shape,
            "data_path": response.path_parquet
        }
        
    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analytics processing failed: {str(e)}"
        )


@router.post("/profile")
async def get_climate_profile(
    request: ExtendedClimateRequest,
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID")
):
    """
    Get climate data with optional preprocessing and postprocessing.
    
    This is the main endpoint that supports the full pipeline with
    configurable processing options.
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    try:
        from .service import get_enhanced_climate_service
        
        # Configure service with processing options
        service = get_enhanced_climate_service()
        
        # Add processing options to request (will be used by _process_data)
        request.processing_options = request.processing_options or ProcessingOptions()
        
        # Process request with full pipeline
        response = service.get_climate(request)
        
        # Add processing report if available
        if hasattr(service, '_pipeline_report'):
            response.manifest['processing_report'] = service._pipeline_report
        
        return response
        
    except Exception as e:
        logger.error(f"Profile request failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Climate profile processing failed: {str(e)}"
        )


@router.get("/processing/options")
async def get_processing_options():
    """
    Get available processing options and their defaults.
    
    This helps clients understand what processing capabilities are available.
    """
    from settings import get_settings
    get_config = get_settings
    
    config = get_config()
    
    return {
        "preprocessing": {
            "resampling": {
                "enabled": config.preprocessing.auto_resample,
                "default_resolution": config.preprocessing.default_resolution,
                "available_resolutions": ["15min", "30min", "1H", "3H", "1D"]
            },
            "quality_control": {
                "enabled": config.preprocessing.apply_qc,
                "bounds_check": config.preprocessing.qc_bounds_check,
                "consistency_check": config.preprocessing.qc_consistency_check
            },
            "gap_filling": {
                "enabled": config.preprocessing.fill_gaps,
                "method": config.preprocessing.gap_fill_method,
                "available_methods": ["smart", "linear", "pattern", "seasonal"],
                "max_gap_hours": config.preprocessing.max_pattern_gap_hours
            },
            "derivations": {
                "basic_vars": config.preprocessing.derive_basic_vars,
                "variables": ["dewpoint", "rel_humidity", "pressure"]
            }
        },
        "postprocessing": {
            "building_metrics": {
                "degree_days": {
                    "enabled": config.postprocessing.calculate_degree_days,
                    "hdd_base": config.postprocessing.hdd_base_temp,
                    "cdd_base": config.postprocessing.cdd_base_temp
                },
                "comfort": {
                    "wet_bulb": config.postprocessing.calculate_wet_bulb,
                    "heat_index": config.postprocessing.calculate_heat_index
                }
            },
            "solar": {
                "clearness_index": config.postprocessing.calculate_clearness_index,
                "solar_angles": config.postprocessing.calculate_solar_angles
            },
            "statistics": {
                "enabled": config.postprocessing.include_statistics,
                "percentiles": config.postprocessing.stats_percentiles
            },
            "extremes": {
                "enabled": config.postprocessing.analyze_extremes,
                "percentile": config.postprocessing.extreme_percentile
            },
            "design_conditions": {
                "enabled": config.postprocessing.calculate_design_conditions,
                "percentiles": config.postprocessing.design_percentiles
            }
        }
    }


# This router is now included in the main FastAPI app in main.py