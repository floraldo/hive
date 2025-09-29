"""
Enhanced Climate data service with centralized configuration and processing pipeline.

This is the new service implementation that leverages:
- Simple adapter factory for instance creation
- Centralized configuration management
- ProcessingPipeline for modular data processing
- Improved error handling and fallback mechanisms
"""
from __future__ import annotations


import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, ListTuple

import pandas as pd
import xarray as xr
from ecosystemiser.core.errors import ProfileError as ClimateError
from ecosystemiser.core.errors import ProfileError as LocationError
from ecosystemiser.core.errors import ProfileError as ProcessingError
from ecosystemiser.core.errors import ProfileError as TemporalError
from ecosystemiser.core.errors import ProfileLoadError as AdapterError
from ecosystemiser.core.errors import ProfileValidationError as ValidationError
from ecosystemiser.profile_loader.climate.adapters.factory import (
    get_adapter,
    get_enabled_adapters,
    list_available_adapters
)
from ecosystemiser.profile_loader.climate.analysis.building_science import (
    derive_building_variables
)
from ecosystemiser.profile_loader.climate.analysis.statistics import describe
from ecosystemiser.profile_loader.climate.analysis.synthetic.bootstrap import (
    multivariate_block_bootstrap
)
from ecosystemiser.profile_loader.climate.analysis.synthetic.copula import (
    copula_synthetic_generation
)
from ecosystemiser.profile_loader.climate.analysis.synthetic.tmy import (
    TMYGenerator,
    TMYMethod
)
from ecosystemiser.profile_loader.climate.cache import (
    cache_key_from_request,
    load_from_cache,
    save_parquet_and_manifest
)
from ecosystemiser.profile_loader.climate.data_models import (
    CANONICAL_VARIABLES,
    ClimateRequest,
    ClimateResponse
)
from ecosystemiser.profile_loader.climate.manifest import build_manifest
from ecosystemiser.profile_loader.climate.processing.pipeline import ProcessingPipeline
from ecosystemiser.profile_loader.climate.processing.resampling import resample_dataset
from ecosystemiser.profile_loader.climate.processing.validation import (
    apply_quality_control
)
from ecosystemiser.profile_loader.climate.subsets import apply_subset
from ecosystemiser.profile_loader.shared.models import BaseProfileRequest
from ecosystemiser.profile_loader.shared.service import (
    BaseProfileService,
    ProfileServiceError
    ProfileValidationError
)
from ecosystemiser.profile_loader.shared.timezone import TimezoneHandler
from ecosystemiser.settings import get_settings
from hive_logging import get_logger

# Compatibility aliases
get_config = get_settings

logger = get_logger(__name__)


class LocationResolver:
    """Centralized location resolution and geocoding service.

    This service handles all location-to-coordinates conversion before
    adapter selection, enabling intelligent adapter choice based on
    geographical coverage.
    """

    def __init__(self) -> None:
        self.location_cache = {}  # Cache for geocoded locations

        # Well-known locations for fast lookup
        self.known_locations = {
            # Major cities
            "london": (51.5074, -0.1278),
            "london, uk": (51.5074, -0.1278),
            "paris": (48.8566, 2.3522),
            "paris, france": (48.8566, 2.3522),
            "berlin": (52.5200, 13.4050),
            "berlin, germany": (52.5200, 13.4050),
            "madrid": (40.4168, -3.7038),
            "madrid, spain": (40.4168, -3.7038),
            "rome": (41.9028, 12.4964),
            "rome, italy": (41.9028, 12.4964),
            "amsterdam": (52.3676, 4.9041),
            "amsterdam, netherlands": (52.3676, 4.9041),
            "lisbon": (38.7223, -9.1393),
            "lisbon, portugal": (38.7223, -9.1393),
            "stockholm": (59.3293, 18.0686),
            "stockholm, sweden": (59.3293, 18.0686),
            "copenhagen": (55.6761, 12.5683),
            "copenhagen, denmark": (55.6761, 12.5683),
            "vienna": (48.2082, 16.3738),
            "vienna, austria": (48.2082, 16.3738),
            "zurich": (47.3769, 8.5417),
            "zurich, switzerland": (47.3769, 8.5417)
            # US cities
            "new york": (40.7128, -74.0060),
            "new york, ny": (40.7128, -74.0060),
            "los angeles": (34.0522, -118.2437),
            "los angeles, ca": (34.0522, -118.2437),
            "chicago": (41.8781, -87.6298),
            "chicago, il": (41.8781, -87.6298),
            "san francisco": (37.7749, -122.4194),
            "san francisco, ca": (37.7749, -122.4194)
            # Other major cities
            "tokyo": (35.6762, 139.6503),
            "tokyo, japan": (35.6762, 139.6503),
            "sydney": (-33.8688, 151.2093),
            "sydney, australia": (-33.8688, 151.2093),
            "toronto": (43.6532, -79.3832),
            "toronto, canada": (43.6532, -79.3832)
        }

    def resolve_location(self, location: Any) -> Tuple[float, float]:
        """Resolve any location input to lat/lon coordinates.

        Args:
            location: Location as tuple, dict, or string

        Returns:
            Tuple of (latitude, longitude)

        Raises:
            LocationError: If location cannot be resolved
        """
        try:
            # Handle coordinate tuples
            if isinstance(location, tuple) and len(location) == 2:
                lat, lon = location
                self._validate_coordinates(lat, lon)
                return lat, lon

            # Handle coordinate dictionaries
            elif isinstance(location, dict):
                lat = location.get("lat") or location.get("latitude")
                lon = location.get("lon") or location.get("longitude")
                if lat is None or lon is None:
                    raise LocationError("Dict location must contain 'lat'/'latitude' and 'lon'/'longitude'")
                self._validate_coordinates(lat, lon)
                return lat, lon

            # Handle string locations (geocoding)
            elif isinstance(location, str):
                return self._geocode_location(location)

            else:
                raise LocationError(
                    f"Invalid location format: {type(location)}"
                    recovery_suggestion="Provide (lat, lon) tuple, dict with lat/lon, or location name"
                )

        except LocationError:
            raise
        except Exception as e:
            raise LocationError(f"Failed to resolve location: {e}")

    def _validate_coordinates(self, lat: float, lon: float) -> None:
        """Validate that coordinates are within valid ranges."""
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise LocationError("Latitude and longitude must be numeric")

        if not (-90 <= lat <= 90):
            raise LocationError(f"Latitude {lat} out of valid range [-90, 90]")

        if not (-180 <= lon <= 180):
            raise LocationError(f"Longitude {lon} out of valid range [-180, 180]")

    def _geocode_location(self, location_str: str) -> Tuple[float, float]:
        """Geocode a location string to coordinates.

        Args:
            location_str: Location name or address

        Returns:
            Tuple of (latitude, longitude)
        """
        # Check cache first
        cache_key = location_str.lower().strip()
        if cache_key in self.location_cache:
            logger.debug(f"Found cached coordinates for {location_str}")
            return self.location_cache[cache_key]

        # Check known locations
        if cache_key in self.known_locations:
            coords = self.known_locations[cache_key]
            self.location_cache[cache_key] = coords
            logger.debug(f"Found known coordinates for {location_str}: {coords}")
            return coords

        # Try pattern matching for common formats
        coords = self._try_pattern_matching(location_str)
        if coords:
            self.location_cache[cache_key] = coords
            logger.debug(f"Pattern matched coordinates for {location_str}: {coords}")
            return coords

        # Try online geocoding as last resort
        coords = self._try_online_geocoding(location_str)
        if coords:
            self.location_cache[cache_key] = coords
            logger.info(f"Geocoded {location_str} to {coords}")
            return coords

        # If all methods fail
        raise LocationError(
            f"Could not geocode location: {location_str}"
            recovery_suggestion="Provide coordinates as (lat, lon) tuple or use a known city name"
        )

    def _try_pattern_matching(self, location_str: str) -> Optional[Tuple[float, float]]:
        """Try to extract coordinates from string patterns."""
        # Pattern for coordinates in string: "lat, lon" or "lat lon"
        coord_pattern = r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)"
        match = re.search(coord_pattern, location_str)

        if match:
            try:
                lat, lon = float(match.group(1)), float(match.group(2))
                self._validate_coordinates(lat, lon)
                return lat, lon
            except (ValueError, LocationError):
                pass

        return None

    def _try_online_geocoding(self, location_str: str) -> Optional[Tuple[float, float]]:
        """Try online geocoding services (fallback only)."""
        try:
            # Try using a simple HTTP geocoding service
            # Note: In production, you'd want to use a proper service like
            # Nominatim (OpenStreetMap), Google Geocoding API, etc.

            # For now, implement a basic mock that could be extended
            logger.warning(f"Online geocoding not implemented for {location_str}")
            logger.info("To enable online geocoding, configure a geocoding service")

            return None

        except Exception as e:
            logger.debug(f"Online geocoding failed for {location_str}: {e}")
            return None

    def get_adapter_coverage_score(self, lat: float, lon: float, adapter_name: str) -> float:
        """Get a coverage score for how well an adapter covers a location.

        This enables intelligent adapter selection based on geographical coverage.

        Args:
            lat: Latitude
            lon: Longitude
            adapter_name: Name of the adapter

        Returns:
            Coverage score between 0 (no coverage) and 1 (excellent coverage)
        """
        # Adapter coverage regions (can be configured or loaded from adapter metadata)
        coverage_regions = {
            "nasa_power": {"global": True, "score": 0.8},  # Good global coverage,
            "era5": {"global": True, "score": 0.9},  # Excellent global coverage,
            "meteostat": {,
                "regions": [
                    {
                        "bounds": (30, -130, 70, 30),
                        "score": 0.9
                    },  # North America/Europe
                    {
                        "bounds": (-60, -180, 60, 180),
                        "score": 0.7
                    },  # Global with lower quality
                ]
            }
            "pvgis": {,
                "regions": [,
                    {"bounds": (30, -25, 75, 75), "score": 0.95},  # Europe/Africa/Asia
                    {"bounds": (-60, -180, 30, -30), "score": 0.8},  # Americas
                ]
            }
        }

        if adapter_name not in coverage_regions:
            return 0.5  # Default score for unknown adapters

        coverage = coverage_regions[adapter_name]

        # Global coverage
        if coverage.get("global"):
            return coverage.get("score", 0.8)

        # Regional coverage
        if "regions" in coverage:
            best_score = 0
            for region in coverage["regions"]:
                bounds = region["bounds"]
                if bounds[0] <= lat <= bounds[2] and bounds[1] <= lon <= bounds[3]:
                    best_score = max(best_score, region["score"])
            return best_score

        return 0.5  # Default if no specific coverage info


class ClimateService(BaseProfileService):
    """
    Enhanced climate data service implementing the unified profile interface.

    Features:
    - Simple adapter factory for resilience
    - Centralized configuration and location resolution
    - Modular ProcessingPipeline for data processing
    - Intelligent fallback mechanisms
    - Comprehensive QC integration
    - Async request handling
    - Unified profile service interface
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize enhanced climate service with centralized location resolution

        Args:
            config: Configuration object (required via dependency injection)
        """
        self.config = config
        self.processing_pipeline = ProcessingPipeline(config)
        self.location_resolver = LocationResolver()  # Centralized geocoding service

        # Track request statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

        # Get available adapters
        available_adapters = get_enabled_adapters()
        logger.info(f"Enhanced ClimateService initialized with {len(available_adapters)} available adapters")
        logger.info("Centralized location resolution enabled")

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
            ds = await self._fetch_data_with_fallback_async(lat, lon, req, preferred_adapters)

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
                future = executor.submit(lambda: asyncio.run(self.process_request_async(req)))
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
                    f"Unknown variables: {unknown_vars}"
                    field="variables"
                    value=list(unknown_vars)
                    recovery_suggestion=f"Available variables: {list(CANONICAL_VARIABLES.keys())}"
                )

        # Validate period
        if not req.period:
            raise TemporalError(
                "Period must be specified"
                recovery_suggestion="Provide either 'year' or 'start'/'end' dates"
            )

        # Validate source if specified
        if req.source:
            available_adapters = list_available_adapters()
            if req.source not in available_adapters:
                raise ValidationError(
                    f"Unknown data source: {req.source}"
                    field="source"
                    value=req.source
                    recovery_suggestion=f"Available sources: {available_adapters}"
                )

    def _resolve_location(self, location: Any) -> Tuple[float, float]:
        """Resolve location to lat/lon coordinates using centralized geocoding service.

        This method now uses the centralized LocationResolver for all location
        handling, enabling intelligent adapter selection based on geographical coverage.
        """
        return self.location_resolver.resolve_location(location)

    def _select_best_adapter(self, lat: float, lon: float, requested_source: str | None = None) -> str:
        """Select the best adapter for a given location based on coverage and availability.

        Args:
            lat: Latitude
            lon: Longitude
            requested_source: User-requested adapter name (if any)

        Returns:
            Name of the best adapter to use
        """
        available_adapters = get_enabled_adapters()

        if not available_adapters:
            raise AdapterError("No adapters available")

        # If user requested a specific source, use it (if available)
        if requested_source and requested_source in available_adapters:
            logger.debug(f"Using user-requested adapter: {requested_source}")
            return requested_source

        # Score all available adapters based on coverage
        adapter_scores = []
        for adapter_name in available_adapters:
            try:
                coverage_score = self.location_resolver.get_adapter_coverage_score(lat, lon, adapter_name)
                adapter_scores.append((adapter_name, coverage_score))
                logger.debug(f"Adapter {adapter_name} coverage score: {coverage_score:.2f}")
            except Exception as e:
                logger.warning(f"Could not score adapter {adapter_name}: {e}")
                adapter_scores.append((adapter_name, 0.1))  # Low fallback score

        # Sort by score (highest first)
        adapter_scores.sort(key=lambda x: x[1], reverse=True)

        if not adapter_scores:
            raise AdapterError("No suitable adapters found for location")

        best_adapter = adapter_scores[0][0]
        best_score = adapter_scores[0][1]

        logger.info(
            f"Selected adapter {best_adapter} for location ({lat:.3f}, {lon:.3f}) "
            f"with coverage score {best_score:.2f}"
        )

        # Log alternatives for debugging
        if len(adapter_scores) > 1:
            alternatives = [f"{name}({score:.2f})" for name, score in adapter_scores[1:3]]
            logger.debug(f"Alternative adapters: {', '.join(alternatives)}")

        return best_adapter

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
                    manifest=manifest
                    path_parquet=str(cache_path)
                    shape=(len(ds.time), len(list(ds.data_vars)))
                    stats=describe_stats(ds) if req.mode == "observed" else None
                    # Required fields from BaseProfileResponse
                    start_time=pd.Timestamp(ds.time.values[0])
                    end_time=pd.Timestamp(ds.time.values[-1])
                    variables=list(ds.data_vars)
                    source=req.source
                )

                return ds, response

            return None

        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
            return None

    async def _fetch_data_with_fallback_async(
        self, lat: float, lon: float, req: ClimateRequest, preferred_adapters: List[str]
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
                "factory"
                "No enabled adapters available"
                recovery_suggestion="Check adapter configuration and availability"
            )

        # Try preferred adapters first
        for adapter_name in preferred_adapters:
            if adapter_name in available_adapters:
                try:
                    logger.info(f"Trying preferred adapter: {adapter_name}")
                    ds = await self._fetch_from_adapter_async(adapter_name, lat, lon, req)
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
                    ds = await self._fetch_from_adapter_async(adapter_name, lat, lon, req)
                    logger.info(f"Successfully fetched data from {adapter_name}")
                    return ds

                except Exception as e:
                    import traceback

                    logger.warning(f"Fallback adapter {adapter_name} failed: {e}")
                    logger.debug(f"Full traceback:\n{traceback.format_exc()}")
                    continue

        # If we get here, all adapters have failed
        raise AdapterError(
            "All available adapters failed to fetch data"
            adapter_name="factory"
            details={
                "available_adapters": available_adapters,
                "preferred_adapters": preferred_adapters
            }
            recovery_suggestion="Check adapter configuration and try again later"
        )

    async def _fetch_from_adapter_async(
        self, adapter_name: str, lat: float, lon: float, req: ClimateRequest
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
        if hasattr(adapter, "fetch"):
            ds = await adapter.fetch(
                lat=lat
                lon=lon
                variables=req.variables
                period=req.period
                resolution=req.resolution
            )
        else:
            raise AdapterError(
                adapter_name
                "Adapter does not have fetch method"
                recovery_suggestion="Check adapter implementation"
            )

        if ds is None or len(ds.data_vars) == 0:
            raise AdapterError(
                adapter_name
                "No data returned from adapter"
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
            if hasattr(req, "timezone") and req.timezone and req.timezone != "UTC":
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
            raise ProcessingError(f"Failed to process data: {str(e)}")

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
            raise ProcessingError(f"Failed to apply {req.mode} mode: {str(e)}")

    def _compute_average_mode(self, ds: xr.Dataset) -> xr.Dataset:
        """Compute average/typical patterns"""
        ds_avg = ds.groupby("time.dayofyear").mean()

        year = pd.Timestamp.now().year
        time_index = pd.date_range(
            start=f"{year}-01-01"
            end=f"{year}-12-31 23:00:00"
            freq=pd.infer_freq(ds.time.values) or "1H"
        )

        doy_values = time_index.dayofyear
        ds_reconstructed = ds_avg.sel(dayofyear=doy_values)
        ds_reconstructed = ds_reconstructed.rename({"dayofyear": "time"})
        ds_reconstructed["time"] = time_index

        return ds_reconstructed

    def _compute_tmy_mode(self, ds: xr.Dataset, req: ClimateRequest) -> xr.Dataset:
        """Generate Typical Meteorological Year"""
        logger.info("Generating Typical Meteorological Year (TMY)")

        tmy_options = getattr(req, "synthetic_options", {})
        method_name = tmy_options.get("method", "tmy3")

        try:
            method = TMYMethod(method_name)
        except ValueError:
            logger.warning(f"Unknown TMY method '{method_name}', using TMY3")
            method = TMYMethod.TMY3

        generator = TMYGenerator(method=method)

        target_year = tmy_options.get("target_year", 2010)
        min_years = tmy_options.get("min_data_years", 10)
        custom_weights = tmy_options.get("weights", None)

        tmy_dataset, selection_metadata = generator.generate(
            historical_data=ds
            target_year=target_year
            weights=custom_weights
            min_data_years=min_years
        )

        tmy_dataset.attrs["tmy_selection"] = selection_metadata
        logger.info(f"TMY generation complete: {len(tmy_dataset.time)} time steps")

        return tmy_dataset

    def _compute_synthetic_mode(self, ds: xr.Dataset, req: ClimateRequest) -> xr.Dataset:
        """Generate synthetic data"""
        synth_options = getattr(req, "synthetic_options", {})
        method = synth_options.get("method", "bootstrap")

        if method == "copula":
            ds = copula_synthetic_generation(
                ds_hist=ds
                seed=getattr(req, "seed", None)
                copula_type=synth_options.get("copula_type", "gaussian")
                target_length=synth_options.get("target_length", "1Y")
                **{k: v for k, v in synth_options.items() if k not in ["method", "copula_type", "target_length"]}
            )
        else:
            ds = multivariate_block_bootstrap(
                ds_hist=ds
                block=synth_options.get("block", "1D")
                season_bins=synth_options.get("season_bins", 12)
                overlap_hours=synth_options.get("overlap_hours", 3)
                seed=getattr(req, "seed", None)
                target_length=synth_options.get("target_length", "1Y")
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
        self, ds: xr.Dataset, req: ClimateRequest, processing_report: Dict[str, Any]
    ) -> ClimateResponse:
        """Cache data and build response"""
        try:
            # Build manifest with processing info
            manifest = build_manifest(
                adapter_name="enhanced_service"
                adapter_version="1.0.0"
                req=req.model_dump()
                qc_report=processing_report
                source_meta=self.get_service_info()
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
                start_time=start_time
                end_time=end_time
                variables=variables
                source=req.source
                shape=(len(ds.time), len(variables))
                # Climate-specific fields
                manifest=manifest
                path_parquet=cache_path
                stats=describe_stats(ds) if req.mode == "observed" else None
                # Optional metadata
                processing_steps=processing_report.get("steps", [])
                cached=cache_path is not None
                cache_key=cache_key if self.config.features.enable_caching else None
                warnings=processing_report.get("warnings", [])
                processing_time_ms=processing_report.get("processing_time_ms")
            )

            return response

        except Exception as e:
            logger.error(f"Failed to build response: {e}")
            raise ProcessingError(f"Failed to build response: {str(e)}")

    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "service_name": "ClimateService",
            "version": "1.0.0",
            "config": {,
                "caching_enabled": hasattr(self.config, "features") and self.config.features.enable_caching,
                "preprocessing_enabled": hasattr(self.config, "profile_loader")
                and self.config.profile_loader.preprocessing_enabled
                "postprocessing_enabled": hasattr(self.config, "profile_loader")
                and self.config.profile_loader.postprocessing_enabled
            }
            "statistics": {,
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "success_rate": (
                    self.successful_requests / self.total_requests * 100 if self.total_requests > 0 else 0
                )
            }
            "processing_pipeline": self.processing_pipeline.list_steps()
        }

    def get_adapter_health(self) -> Dict[str, Any]:
        """Get adapter health status"""
        adapters = list_available_adapters()
        enabled_adapters = get_enabled_adapters()
        return {
            "total_adapters": len(adapters),
            "enabled_adapters": len(enabled_adapters),
            "available_adapters": adapters,
            "enabled_list": enabled_adapters
        }

    def get_available_sources(self) -> List[str]:
        """Get list of available data sources"""
        return get_enabled_adapters()

    def process_request(self, request: BaseProfileRequest) -> Tuple[xr.Dataset, ClimateResponse]:
        """
        Process climate request synchronously (unified interface).

        Args:
            request: Climate profile request

        Returns:
            Tuple of (xarray Dataset, ClimateResponse)
        """
        # Convert to ClimateRequest if needed
        if not isinstance(request, ClimateRequest):
            climate_request = ClimateRequest(**request.dict())
        else:
            climate_request = request

        # Use existing async method in a sync wrapper
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.process_request_async(climate_request))

    def validate_request(self, request: BaseProfileRequest) -> List[str]:
        """Validate climate profile request (unified interface)."""
        errors = []

        # Convert to ClimateRequest for validation
        if not isinstance(request, ClimateRequest):
            try:
                climate_request = ClimateRequest(**request.dict())
            except Exception as e:
                errors.append(f"Invalid climate request format: {e}")
                return errors
        else:
            climate_request = request

        # Use existing validation logic
        try:
            self._validate_request(climate_request)
        except (ValidationError, LocationError, TemporalError) as e:
            errors.append(str(e))

        return errors

    def get_available_variables(self, source: str | None = None) -> Dict[str, Dict[str, str]]:
        """Get available climate variables (unified interface)."""
        return CANONICAL_VARIABLES

    def get_source_coverage(self, source: str) -> Dict[str, Any]:
        """Get geographical and temporal coverage for climate source (unified interface)."""
        from ecosystemiser.profile_loader.climate.adapters.capabilities import (
            get_adapter_capabilities
        )

        try:
            capabilities = get_adapter_capabilities(source)
            return {
                "spatial_coverage": capabilities.get("spatial_coverage", "Global"),
                "temporal_coverage": capabilities.get("temporal_coverage", "Variable"),
                "resolution": capabilities.get("resolutions", ["1H"]),
                "variables": capabilities.get("variables", [])
            }
        except Exception as e:
            return {
                "spatial_coverage": "Unknown",
                "temporal_coverage": "Unknown",
                "resolution": ["1H"],
                "variables": []
            }

    async def shutdown_async(self) -> None:
        """Shutdown service and cleanup resources"""
        logger.info("Shutting down Enhanced ClimateService")
        # Cleanup adapter factory resources
        from ecosystemiser.profile_loader.climate.adapters.factory import cleanup

        cleanup()


# Global service instance
# Singleton pattern removed - use create_climate_service() from __init__.py instead
