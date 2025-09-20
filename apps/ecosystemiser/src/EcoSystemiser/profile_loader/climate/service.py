"""
Enhanced Climate data service with centralized configuration and processing pipeline.

This is the new service implementation that leverages:
- Simple adapter factory for instance creation
- Centralized configuration management
- ProcessingPipeline for modular data processing
- Improved error handling and fallback mechanisms
"""

import asyncio
import xarray as xr
import logging
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import pandas as pd

from .data_models import ClimateRequest, ClimateResponse, CANONICAL_VARIABLES
from EcoSystemiser.errors import (
    ClimateError, AdapterError, ValidationError, 
    ProcessingError, TemporalError, LocationError
)
from .processing.resampling import resample_dataset
from .processing.validation import apply_quality_control
from EcoSystemiser.profile_loader.shared.timezone import TimezoneHandler
from .analysis.building_science import derive_building_variables
from .analysis.synthetic.bootstrap import multivariate_block_bootstrap
from .analysis.synthetic.copula import copula_synthetic_generation
from .analysis.synthetic.tmy import TMYGenerator, TMYMethod
from .analysis.statistics import describe as describe_stats
from .subsets import apply_subset
from .cache import cache_key_from_request, save_parquet_and_manifest, load_from_cache
from .manifest import build_manifest
from EcoSystemiser.settings import get_settings
from .adapters.factory import get_adapter, list_available_adapters, get_enabled_adapters
from .processing.pipeline import ProcessingPipeline

# Compatibility aliases
get_config = get_settings

logger = logging.getLogger(__name__)


class ClimateService:
    """
    Enhanced climate data service with configuration management and processing pipeline.
    
    Features:
    - Simple adapter factory for resilience
    - Centralized configuration
    - Modular ProcessingPipeline for data processing
    - Intelligent fallback mechanisms
    - Comprehensive QC integration
    - Async request handling
    """
    
    def __init__(self):
        """Initialize enhanced climate service"""
        self.config = get_config()
        self.processing_pipeline = ProcessingPipeline()
        
        # Track request statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        
        # Get available adapters
        available_adapters = get_enabled_adapters()
        logger.info(f"Enhanced ClimateService initialized with {len(available_adapters)} available adapters")
    
    async def process_request_async(self, req: ClimateRequest) -> Tuple[xr.Dataset, ClimateResponse]:
        """
        Async version of process_request with adapter factory integration.
        
        Args:
            req: Climate data request
            
        Returns:
            Tuple of (xarray Dataset, ClimateResponse)
        """
        self.total_requests += 1
        logger.info(f"Processing climate request: source={req.source}, mode={req.mode}")
        
        try:
            # Validate request
            self._validate_request(req)
            
            # Resolve location
            lat, lon = self._resolve_location(req.location)
            
            # Check cache first
            cache_result = self._check_cache(req)
            if cache_result:
                self.successful_requests += 1
                return cache_result
            
            # Determine adapter strategy
            preferred_adapters = [req.source] if req.source else []
            
            # Fetch data with fallback
            ds = await self._fetch_data_with_fallback(
                lat, lon, req, preferred_adapters
            )
            
            # Process data
            ds, processing_report = await self._process_data_async(ds, req)
            
            # Apply mode and subset
            ds = self._apply_mode(ds, req)
            ds = self._apply_subset(ds, req)
            
            # Cache and build response
            response = self._cache_and_respond(ds, req, processing_report)
            
            self.successful_requests += 1
            return ds, response
            
        except Exception as e:
            self.failed_requests += 1
            logger.error(f"Request failed: {e}")
            raise
    
    def process_request(self, req: ClimateRequest) -> Tuple[xr.Dataset, ClimateResponse]:
        """
        Synchronous wrapper for async process_request.
        
        Args:
            req: Climate data request
            
        Returns:
            Tuple of (xarray Dataset, ClimateResponse)
        """
        # Run async method in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # If we're already in an event loop, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(self.process_request_async(req))
                )
                return future.result()
        else:
            # Run in the current loop
            return loop.run_until_complete(self.process_request_async(req))
    
    def _validate_request(self, req: ClimateRequest) -> None:
        """Validate request parameters"""
        # Validate variables
        if req.variables:
            unknown_vars = set(req.variables) - set(CANONICAL_VARIABLES.keys())
            if unknown_vars:
                raise ValidationError(
                    f"Unknown variables: {unknown_vars}",
                    field='variables',
                    value=list(unknown_vars),
                    recovery_suggestion=f"Available variables: {list(CANONICAL_VARIABLES.keys())}"
                )
        
        # Validate period
        if not req.period:
            raise TemporalError(
                "Period must be specified",
                recovery_suggestion="Provide either 'year' or 'start'/'end' dates"
            )
        
        # Validate source if specified
        if req.source:
            available_adapters = list_available_adapters()
            if req.source not in available_adapters:
                raise ValidationError(
                    f"Unknown data source: {req.source}",
                    field='source',
                    value=req.source,
                    recovery_suggestion=f"Available sources: {available_adapters}"
                )
    
    def _resolve_location(self, location: Any) -> Tuple[float, float]:
        """Resolve location to lat/lon coordinates"""
        try:
            if isinstance(location, tuple) and len(location) == 2:
                lat, lon = location
            elif isinstance(location, dict):
                lat = location.get('lat') or location.get('latitude')
                lon = location.get('lon') or location.get('longitude')
            elif isinstance(location, str):
                # Handle city names - for now just pass through to adapter
                # which should handle geocoding
                logger.info(f"Using location string: {location}")
                lat, lon = None, None  # Let adapter handle geocoding
            else:
                raise LocationError(
                    f"Invalid location format: {type(location)}",
                    recovery_suggestion="Provide (lat, lon) tuple, dict with lat/lon, or location name"
                )
            
            # Validate coordinates
            if not (-90 <= lat <= 90):
                raise LocationError(f"Invalid latitude: {lat}")
            if not (-180 <= lon <= 180):
                raise LocationError(f"Invalid longitude: {lon}")
            
            return float(lat), float(lon)
            
        except (TypeError, ValueError) as e:
            raise LocationError(f"Failed to parse location: {e}")
    
    def _check_cache(self, req: ClimateRequest) -> Optional[Tuple[xr.Dataset, ClimateResponse]]:
        """Check cache for existing data"""
        if not self.config.features.enable_caching:
            return None
        
        try:
            # Generate cache key based on request
            cache_key = cache_key_from_request(req, "enhanced_v1")
            cached = load_from_cache(cache_key)
            
            if cached is not None:
                ds, manifest = cached
                logger.info("Returning cached data")
                
                cache_path = Path(self.config.cache.cache_dir) / "climate" / "data" / f"{cache_key}.parquet"
                response = ClimateResponse(
                    manifest=manifest,
                    path_parquet=str(cache_path),
                    shape=(len(ds.time), len(list(ds.data_vars))),
                    stats=describe_stats(ds) if req.mode == "observed" else None,
                    # Required fields from BaseProfileResponse
                    start_time=pd.Timestamp(ds.time.values[0]),
                    end_time=pd.Timestamp(ds.time.values[-1]),
                    variables=list(ds.data_vars),
                    source=req.source
                )
                
                return ds, response
            
            return None
            
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
            return None
    
    async def _fetch_data_with_fallback(
        self,
        lat: float,
        lon: float,
        req: ClimateRequest,
        preferred_adapters: List[str]
    ) -> xr.Dataset:
        """
        Fetch data with intelligent fallback using simple adapter factory.
        
        Args:
            lat: Latitude
            lon: Longitude  
            req: Climate request
            preferred_adapters: List of preferred adapters to try first
            
        Returns:
            xarray Dataset
            
        Raises:
            AdapterError: If all adapters fail
        """
        logger.info(f"Fetching data with fallback strategy")
        
        # Get available adapters
        available_adapters = get_enabled_adapters()
        
        if not available_adapters:
            raise AdapterError(
                "factory",
                "No enabled adapters available",
                recovery_suggestion="Check adapter configuration and availability"
            )
        
        # Try preferred adapters first
        for adapter_name in preferred_adapters:
            if adapter_name in available_adapters:
                try:
                    logger.info(f"Trying preferred adapter: {adapter_name}")
                    ds = await self._fetch_from_adapter(adapter_name, lat, lon, req)
                    logger.info(f"Successfully fetched data from {adapter_name}")
                    return ds
                    
                except Exception as e:
                    import traceback
                    logger.warning(f"Preferred adapter {adapter_name} failed: {e}")
                    logger.debug(f"Full traceback:\n{traceback.format_exc()}")
                    continue
        
        # Try other available adapters
        for adapter_name in available_adapters:
            if adapter_name not in preferred_adapters:
                try:
                    logger.info(f"Trying fallback adapter: {adapter_name}")
                    ds = await self._fetch_from_adapter(adapter_name, lat, lon, req)
                    logger.info(f"Successfully fetched data from {adapter_name}")
                    return ds
                    
                except Exception as e:
                    import traceback
                    logger.warning(f"Fallback adapter {adapter_name} failed: {e}")
                    logger.debug(f"Full traceback:\n{traceback.format_exc()}")
                    continue
        
        # If we get here, all adapters have failed
        from ...errors import ErrorCode
        raise AdapterError(
            code=ErrorCode.ADAPTER_ERROR,
            message="All available adapters failed to fetch data",
            adapter_name="factory",
            details={
                'available_adapters': available_adapters,
                'preferred_adapters': preferred_adapters
            },
            suggested_action="Check adapter configuration and try again later"
        )
    
    async def _fetch_from_adapter(
        self,
        adapter_name: str,
        lat: float,
        lon: float,
        req: ClimateRequest
    ) -> xr.Dataset:
        """
        Fetch data from specific adapter using adapter factory.
        
        Args:
            adapter_name: Name of adapter
            lat: Latitude
            lon: Longitude
            req: Climate request
            
        Returns:
            xarray Dataset
        """
        # Get adapter instance from factory
        adapter = get_adapter(adapter_name)
        
        # Call fetch method directly (all adapters have async fetch)
        if hasattr(adapter, 'fetch'):
            ds = await adapter.fetch(
                lat=lat,
                lon=lon,
                variables=req.variables,
                period=req.period,
                resolution=req.resolution
            )
        else:
            raise AdapterError(
                adapter_name,
                "Adapter does not have fetch method",
                recovery_suggestion="Check adapter implementation"
            )
        
        if ds is None or len(ds.data_vars) == 0:
            raise AdapterError(
                adapter_name,
                "No data returned from adapter",
                recovery_suggestion="Try different parameters or another data source"
            )
        
        return ds
    
    async def _process_data_async(self, ds: xr.Dataset, req: ClimateRequest) -> Tuple[xr.Dataset, Dict[str, Any]]:
        """Apply processing pipeline asynchronously.
        
        Returns:
            Tuple of (processed dataset, processing report)
        """
        try:
            # Configure pipeline based on request
            pipeline = self.processing_pipeline
            
            # Update pipeline configuration based on request
            if req.resolution:
                # Enable resampling if resolution is specified
                for step in pipeline.preprocessing_steps:
                    if step.name == "resample":
                        step.enabled = True
                        step.config["resolution"] = req.resolution
            
            # Handle timezone configuration
            if hasattr(req, 'timezone') and req.timezone and req.timezone != "UTC":
                for step in pipeline.preprocessing_steps:
                    if step.name == "timezone_conversion":
                        step.enabled = True
                        step.config["target_tz"] = req.timezone
            
            # Execute preprocessing pipeline
            ds_processed = pipeline.execute_preprocessing(ds)
            
            # Get execution report for manifest (thread-safe)
            processing_report = pipeline.get_execution_report()
            
            return ds_processed, processing_report

        except Exception as e:
            logger.error(f"Data processing failed: {e}", exc_info=True)
            from EcoSystemiser.errors import ProcessingError, ErrorCode
            raise ProcessingError(
                code=ErrorCode.PROCESSING_FAILED,
                message=f"Failed to process data: {str(e)}"
            )
    
    def _apply_mode(self, ds: xr.Dataset, req: ClimateRequest) -> xr.Dataset:
        """Apply mode-specific transformations"""
        try:
            if req.mode == "average":
                ds = self._compute_average_mode(ds)
            elif req.mode == "tmy":
                ds = self._compute_tmy_mode(ds, req)
            elif req.mode == "synthetic":
                ds = self._compute_synthetic_mode(ds, req)
            # "observed" mode returns data as-is
            
            return ds
            
        except Exception as e:
            logger.error(f"Mode application failed: {e}")
            raise ProcessingError(
                code=ErrorCode.PROCESSING_FAILED,
                message=f"Failed to apply {req.mode} mode: {str(e)}"
            )
    
    def _compute_average_mode(self, ds: xr.Dataset) -> xr.Dataset:
        """Compute average/typical patterns"""
        ds_avg = ds.groupby('time.dayofyear').mean()
        
        year = pd.Timestamp.now().year
        time_index = pd.date_range(
            start=f'{year}-01-01',
            end=f'{year}-12-31 23:00:00',
            freq=pd.infer_freq(ds.time.values) or '1H'
        )
        
        doy_values = time_index.dayofyear
        ds_reconstructed = ds_avg.sel(dayofyear=doy_values)
        ds_reconstructed = ds_reconstructed.rename({'dayofyear': 'time'})
        ds_reconstructed['time'] = time_index
        
        return ds_reconstructed
    
    def _compute_tmy_mode(self, ds: xr.Dataset, req: ClimateRequest) -> xr.Dataset:
        """Generate Typical Meteorological Year"""
        logger.info("Generating Typical Meteorological Year (TMY)")
        
        tmy_options = getattr(req, 'synthetic_options', {})
        method_name = tmy_options.get('method', 'tmy3')
        
        try:
            method = TMYMethod(method_name)
        except ValueError:
            logger.warning(f"Unknown TMY method '{method_name}', using TMY3")
            method = TMYMethod.TMY3
        
        generator = TMYGenerator(method=method)
        
        target_year = tmy_options.get('target_year', 2010)
        min_years = tmy_options.get('min_data_years', 10)
        custom_weights = tmy_options.get('weights', None)
        
        tmy_dataset, selection_metadata = generator.generate(
            historical_data=ds,
            target_year=target_year,
            weights=custom_weights,
            min_data_years=min_years
        )
        
        tmy_dataset.attrs['tmy_selection'] = selection_metadata
        logger.info(f"TMY generation complete: {len(tmy_dataset.time)} time steps")
        
        return tmy_dataset
    
    def _compute_synthetic_mode(self, ds: xr.Dataset, req: ClimateRequest) -> xr.Dataset:
        """Generate synthetic data"""
        synth_options = getattr(req, 'synthetic_options', {})
        method = synth_options.get('method', 'bootstrap')
        
        if method == 'copula':
            ds = copula_synthetic_generation(
                ds_hist=ds,
                seed=getattr(req, "seed", None),
                copula_type=synth_options.get('copula_type', 'gaussian'),
                target_length=synth_options.get('target_length', '1Y'),
                **{k: v for k, v in synth_options.items() 
                   if k not in ['method', 'copula_type', 'target_length']}
            )
        else:
            ds = multivariate_block_bootstrap(
                ds_hist=ds,
                block=synth_options.get('block', "1D"),
                season_bins=synth_options.get('season_bins', 12),
                overlap_hours=synth_options.get('overlap_hours', 3),
                seed=getattr(req, "seed", None),
                target_length=synth_options.get('target_length', "1Y")
            )
        
        return ds
    
    def _apply_subset(self, ds: xr.Dataset, req: ClimateRequest) -> xr.Dataset:
        """Apply subset if requested"""
        if req.subset:
            try:
                return apply_subset(ds, req.subset)
            except Exception as e:
                logger.warning(f"Subset application failed: {e}")
                return ds
        return ds
    
    def _cache_and_respond(
        self,
        ds: xr.Dataset,
        req: ClimateRequest,
        processing_report: Dict[str, Any]
    ) -> ClimateResponse:
        """Cache data and build response"""
        try:
            # Build manifest with processing info
            manifest = build_manifest(
                adapter_name="enhanced_service",
                adapter_version="1.0.0",
                req=req.model_dump(),
                qc_report=processing_report,
                source_meta=self.get_service_info(),
                ds=ds
            )
            
            # Cache if enabled
            cache_key = None
            cache_path = None
            if self.config.features.enable_caching:
                try:
                    cache_key = cache_key_from_request(req, "enhanced_v1")
                    save_parquet_and_manifest(ds, manifest, cache_key)
                    logger.info(f"Data cached with key: {cache_key}")
                    cache_path = str(Path(self.config.cache.cache_dir) / "climate" / "data" / f"{cache_key}.parquet")
                except Exception as e:
                    logger.warning(f"Failed to cache data: {e}")
                    cache_path = None
                    cache_key = None
            
            # Extract temporal bounds safely
            time_values = pd.to_datetime(ds.time.values)
            start_time = time_values[0] if len(time_values) > 0 else pd.Timestamp.now()
            end_time = time_values[-1] if len(time_values) > 0 else pd.Timestamp.now()
            
            # Get actual variables from dataset
            variables = list(ds.data_vars)
            
            # Build response with ALL required fields
            response = ClimateResponse(
                # Required base fields (MUST be provided)
                start_time=start_time,
                end_time=end_time,
                variables=variables,
                source=req.source,
                shape=(len(ds.time), len(variables)),
                
                # Climate-specific fields
                manifest=manifest,
                path_parquet=cache_path,
                stats=describe_stats(ds) if req.mode == "observed" else None,
                
                # Optional metadata
                processing_steps=processing_report.get('steps', []),
                cached=cache_path is not None,
                cache_key=cache_key if self.config.features.enable_caching else None,
                warnings=processing_report.get('warnings', []),
                processing_time_ms=processing_report.get('processing_time_ms')
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to build response: {e}")
            raise ProcessingError(
                code=ErrorCode.PROCESSING_FAILED,
                message=f"Failed to build response: {str(e)}"
            )
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            'service_name': 'ClimateService',
            'version': '1.0.0',
            'config': {
                'caching_enabled': hasattr(self.config, 'features') and self.config.features.enable_caching,
                'preprocessing_enabled': hasattr(self.config, 'profile_loader') and self.config.profile_loader.preprocessing_enabled,
                'postprocessing_enabled': hasattr(self.config, 'profile_loader') and self.config.profile_loader.postprocessing_enabled
            },
            'statistics': {
                'total_requests': self.total_requests,
                'successful_requests': self.successful_requests,
                'failed_requests': self.failed_requests,
                'success_rate': (
                    self.successful_requests / self.total_requests * 100 
                    if self.total_requests > 0 else 0
                )
            },
            'processing_pipeline': self.processing_pipeline.list_steps()
        }
    
    def get_adapter_health(self) -> Dict[str, Any]:
        """Get adapter health status"""
        adapters = list_available_adapters()
        enabled_adapters = get_enabled_adapters()
        return {
            'total_adapters': len(adapters),
            'enabled_adapters': len(enabled_adapters),
            'available_adapters': adapters,
            'enabled_list': enabled_adapters
        }
    
    def get_available_sources(self) -> List[str]:
        """Get list of available data sources"""
        return get_enabled_adapters()
    
    async def shutdown(self):
        """Shutdown service and cleanup resources"""
        logger.info("Shutting down Enhanced ClimateService")
        # Cleanup adapter factory resources
        from .adapters.factory import cleanup
        cleanup()


# Global service instance
_global_service: Optional[ClimateService] = None


def get_enhanced_climate_service() -> ClimateService:
    """Get the global enhanced climate service instance"""
    global _global_service
    
    if _global_service is None:
        _global_service = ClimateService()
    
    return _global_service