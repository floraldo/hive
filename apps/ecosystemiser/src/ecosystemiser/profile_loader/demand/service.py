"""
Demand profile service implementing the unified profile interface.,

This service handles loading and processing of energy demand profiles
(electricity, heating, cooling, etc.) from various sources.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from ecosystemiser.profile_loader.demand.file_adapter import DemandFileAdapter
from ecosystemiser.profile_loader.demand.models import DEMAND_VARIABLES, DemandRequest, DemandResponse
from ecosystemiser.profile_loader.shared.models import BaseProfileRequest
from ecosystemiser.profile_loader.shared.service import BaseProfileService, ProfileServiceError, ProfileValidationError
from hive_logging import get_logger

logger = get_logger(__name__)


class DemandService(BaseProfileService):
    """
    Demand profile service with unified interface.,

    Handles loading demand profiles from files, databases, and standard,
    profile libraries using the common profile service interface.,
    """

    def __init__(self) -> None:
        """Initialize demand service with available adapters."""
        self.adapters = {
            "file": DemandFileAdapter(),
            # Future adapters can be added here
            # "database": DemandDatabaseAdapter()
            # "standard_profiles": StandardProfileAdapter()
        }
        self.service_info = {
            "service_type": "DemandService",
            "version": "1.0.0",
            "supported_demand_types": [
                "electricity",
                "heating",
                "cooling",
                "hot_water",
                "process_heat",
            ],
            "supported_building_types": [
                "residential_single",
                "residential_multi",
                "office",
                "retail",
                "industrial",
            ],
        }
        logger.info("DemandService initialized with unified interface")

    async def process_request_async(self, request: BaseProfileRequest) -> tuple[xr.Dataset, DemandResponse]:
        """Process demand request asynchronously."""
        # Run synchronous processing in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.process_request, request)

    def process_request(self, request: BaseProfileRequest) -> tuple[xr.Dataset, DemandResponse]:
        """
        Process demand profile request synchronously.

        Args:
            request: Demand profile request (should be DemandRequest)

        Returns:
            Tuple of (xarray Dataset, DemandResponse)
        """
        # Convert to DemandRequest if needed
        if not isinstance(request, DemandRequest):
            demand_request = DemandRequest(**request.dict())
        else:
            demand_request = request

        logger.info(f"Processing demand request: {demand_request.demand_type} at {demand_request.location}")

        # Validate request
        validation_errors = self.validate_request(demand_request)
        if validation_errors:
            raise ProfileValidationError(f"Request validation failed: {validation_errors}")

        try:
            # Select and configure adapter
            adapter = self._select_adapter(demand_request)
            adapter_config = self._build_adapter_config(demand_request)

            # Fetch profile data
            profiles = adapter.fetch(adapter_config)

            if not profiles:
                raise ProfileServiceError("No demand profiles loaded for request")

            # Convert to xarray Dataset
            dataset = self._create_dataset(profiles, demand_request)

            # Calculate response metrics
            response = self._build_response(dataset, demand_request, profiles)

            logger.info(f"Successfully processed demand request: {dataset.dims}")
            return dataset, response

        except Exception as e:
            logger.error(f"Error processing demand request: {e}")
            raise ProfileServiceError(f"Demand processing failed: {e}") from e

    def validate_request(self, request: BaseProfileRequest) -> list[str]:
        """Validate demand profile request."""
        errors = []

        # Convert to DemandRequest for validation
        if not isinstance(request, DemandRequest):
            try:
                demand_request = DemandRequest(**request.dict())
            except Exception as e:
                errors.append(f"Invalid demand request format: {e}")
                return errors
        else:
            demand_request = request

        # Validate source
        if demand_request.source and demand_request.source not in self.get_available_sources():
            errors.append(f"Unknown demand source: {demand_request.source}")

        # Validate variables
        available_vars = self.get_available_variables()
        for var in demand_request.variables:
            if var not in available_vars:
                errors.append(f"Unknown demand variable: {var}")

        # Validate location for file source
        if demand_request.source == "file" and not isinstance(demand_request.location, str):
            errors.append("File source requires location to be a file path string")

        return errors

    def get_available_sources(self) -> list[str]:
        """Get available demand data sources."""
        return list(self.adapters.keys())

    def get_available_variables(self, source: str | None = None) -> dict[str, dict[str, str]]:
        """Get available demand variables."""
        return DEMAND_VARIABLES

    def get_source_coverage(self, source: str) -> dict[str, Any]:
        """Get coverage information for demand source."""
        if source == "file":
            return {
                "spatial_coverage": "User-defined",
                "temporal_coverage": "User-defined",
                "resolution": "Variable",
                "data_types": ["electricity", "heating", "cooling", "hot_water"],
            }
        else:
            return {"coverage": "Unknown"}

    def _select_adapter(self, request: DemandRequest):
        """Select appropriate adapter for request."""
        if request.source:
            if request.source in self.adapters:
                return self.adapters[request.source]
            else:
                # Map source to adapter
                source_mapping = {
                    "standard_profile": "file",  # For now, map to file adapter
                    "smart_meter": "file",
                    "scada": "file",
                    "simulation": "file",
                    "benchmark": "file",
                }
                adapter_name = source_mapping.get(request.source, "file")
                return self.adapters[adapter_name]
        else:
            # Default to file adapter
            return self.adapters["file"]

    def _build_adapter_config(self, request: DemandRequest) -> dict[str, Any]:
        """Build configuration for selected adapter."""
        config = {
            "demand_type": request.demand_type,
            "building_type": request.building_type,
            "variables": request.variables,
        }

        # Add source-specific configuration
        if request.source == "file" or isinstance(request.location, str):
            config["file_path"] = request.location
            # Create column mapping based on variables
            config["column_mapping"] = {var: var for var in request.variables}

        return config

    def _create_dataset(self, profiles: dict[str, np.ndarray], request: DemandRequest) -> xr.Dataset:
        """Convert profile data to xarray Dataset."""
        if not profiles:
            raise ProfileServiceError("No profile data to convert")

        # Get time dimension
        time_steps = len(next(iter(profiles.values())))

        # Create time index based on request period
        period = request.period
        if "start" in period and "end" in period:
            time_index = pd.date_range(start=period["start"], end=period["end"], freq=request.resolution or "1H")[
                :time_steps
            ]  # Truncate to actual data length
        else:
            # Generate generic time index
            time_index = pd.date_range(start="2023-01-01", periods=time_steps, freq=request.resolution or "1H")

        # Create data variables
        data_vars = {}
        for var_name, values in profiles.items():
            data_vars[var_name] = (["time"], values)

        # Create dataset
        dataset = xr.Dataset(data_vars=data_vars, coords={"time": time_index})

        # Add metadata
        dataset.attrs.update(
            {
                "source": request.source or "file",
                "demand_type": request.demand_type,
                "building_type": request.building_type,
                "location": str(request.location),
                "resolution": request.resolution,
                "variables": list(profiles.keys()),
            },
        )

        return dataset

    def _build_response(
        self,
        dataset: xr.Dataset,
        request: DemandRequest,
        profiles: dict[str, np.ndarray],
    ) -> DemandResponse:
        """Build demand response with metrics."""
        # Calculate basic metrics
        electricity_vars = [var for var in dataset.data_vars if "power" in var.lower() or "electricity" in var.lower()]
        peak_demand = None
        total_energy = None
        load_factor = None

        if electricity_vars and electricity_vars[0] in dataset:
            power_data = dataset[electricity_vars[0]].values
            peak_demand = float(np.max(power_data))
            total_energy = float(np.sum(power_data))  # Simplified calculation
            avg_demand = float(np.mean(power_data))
            load_factor = avg_demand / peak_demand if peak_demand > 0 else None

        # Build response
        response = DemandResponse(
            shape=(len(dataset.time), len(dataset.data_vars)),
            start_time=pd.Timestamp(dataset.time.values[0]),
            end_time=pd.Timestamp(dataset.time.values[-1]),
            variables=list(dataset.data_vars),
            source=request.source or "file",
            peak_demand_kw=peak_demand,
            total_energy_kwh=total_energy,
            load_factor=load_factor,
            processing_steps=["load_profiles", "create_dataset", "calculate_metrics"],
            quality={"completeness": 100.0, "validation_passed": True},
        )

        return response
