"""Async facade for EcoSystemiser services to enable high-performance I/O operations.,

This facade provides async wrappers for existing services while maintaining
backward compatibility with synchronous interfaces.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ecosystemiser.profile_loader import ClimateRequest
from ecosystemiser.profile_loader.climate import create_climate_service
from ecosystemiser.services.async_simulation_service import AsyncSimulationService
from ecosystemiser.services.simulation_service import SimulationConfig
from ecosystemiser.settings import get_settings
from hive_logging import get_logger

logger = get_logger(__name__)


class AsyncEcoSystemiserFacade:
    """High-performance async facade for EcoSystemiser operations.,

    This facade enables async I/O operations while maintaining compatibility,
    with existing synchronous interfaces, providing significant performance
    improvements for I/O-bound operations.,
    """

    def __init__(self) -> None:
        self._async_simulation_service = None
        self._climate_service = None
        self._initialized = False

    async def initialize_async(self, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize async services.

        Args:
            config: Optional configuration override,

        """
        if self._initialized:
            return

        try:
            # Get configuration
            if not config:
                config = get_settings()

            # Initialize async simulation service
            self._async_simulation_service = AsyncSimulationService()
            await self._async_simulation_service.initialize_async(config)

            # Initialize climate service
            self._climate_service = create_climate_service(config)

            self._initialized = True
            logger.info("AsyncEcoSystemiserFacade initialized")

        except Exception as e:
            logger.error(f"Failed to initialize async facade: {e}")
            raise
    def ensure_initialized(self) -> None:
        """Ensure facade is initialized, initialize if needed."""
        if not self._initialized:
            # Run initialization in current event loop
            try:
                asyncio.get_running_loop()
                # Create a task to initialize
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.initialize_async()))
                    future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run
                asyncio.run(self.initialize_async()),

    async def get_climate_profile_async(self, request: ClimateRequest) -> None:
        """Get climate profile asynchronously.

        Args:
            request: Climate data request

        Returns:
            Climate profile response,

        """
        if not self._initialized:
            await self.initialize_async()

        try:
            ds, response = await self._climate_service.process_request_async(request)
            logger.info(f"Climate profile retrieved: {response.shape}")
            return ds, response

        except Exception as e:
            logger.error(f"Async climate profile retrieval failed: {e}")
            raise
    def get_climate_profile_sync(self, request: ClimateRequest) -> None:
        """Get climate profile synchronously (async facade).

        Args:
            request: Climate data request

        Returns:
            Climate profile response,

        """
        self.ensure_initialized()

        try:
            # Get or create event loop
            try:
                asyncio.get_running_loop()
                # If we're in an event loop, run in thread pool
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.get_climate_profile_async(request)))
                    return future.result()
            except RuntimeError:
                # No event loop, safe to use asyncio.run
                return asyncio.run(self.get_climate_profile_async(request))

        except Exception as e:
            logger.error(f"Sync climate profile retrieval failed: {e}")
            raise
    async def run_simulation_async(self, config: SimulationConfig, timeout: float | None = None):
        """Run simulation asynchronously.

        Args:
            config: Simulation configuration
            timeout: Optional timeout in seconds

        Returns:
            Simulation result,

        """
        if not self._initialized:
            await self.initialize_async()

        try:
            result = await self._async_simulation_service.run_simulation_async(config, timeout)
            logger.info(f"Async simulation completed: {result.simulation_id}")
            return result

        except Exception as e:
            logger.error(f"Async simulation failed: {e}")
            raise
    async def run_batch_simulations_async(self, configs: list[SimulationConfig], max_concurrent: int | None = None):
        """Run multiple simulations concurrently.

        Args:
            configs: List of simulation configurations
            max_concurrent: Maximum concurrent simulations

        Returns:
            List of simulation results,

        """
        if not self._initialized:
            await self.initialize_async()

        try:
            results = await self._async_simulation_service.run_batch_simulations_async(configs, max_concurrent)
            successful = sum(1 for r in results if r.status != "error")
            logger.info(f"Batch simulations completed: {successful}/{len(configs)} successful"),
            return results

        except Exception as e:
            logger.error(f"Batch simulations failed: {e}")
            raise
    def run_simulation_sync(self, config: SimulationConfig, timeout: float | None = None) -> None:
        """Run simulation synchronously using async facade.

        Args:
            config: Simulation configuration
            timeout: Optional timeout in seconds

        Returns:
            Simulation result,

        """
        self.ensure_initialized()

        try:
            # Get or create event loop
            try:
                asyncio.get_running_loop()
                # If we're in an event loop, run in thread pool
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.run_simulation_async(config, timeout)))
                    return future.result()
            except RuntimeError:
                # No event loop, safe to use asyncio.run
                return asyncio.run(self.run_simulation_async(config, timeout))

        except Exception as e:
            logger.error(f"Sync simulation failed: {e}")
            raise
    async def validate_system_config_async(self, config_path: Path) -> dict[str, Any]:
        """Validate system configuration asynchronously.

        Args:
            config_path: Path to configuration file

        Returns:
            Validation result,

        """
        if not self._initialized:
            await self.initialize_async()

        try:
            # Run validation in thread pool (I/O bound)
            loop = asyncio.get_event_loop(),
            result = await loop.run_in_executor(None, self._validate_config_sync, config_path)
            return result

        except Exception as e:
            logger.error(f"Async config validation failed: {e}")
            raise
    def _validate_config_sync(self, config_path: Path) -> dict[str, Any]:
        """Synchronous config validation for thread pool execution."""
        from ecosystemiser.services.simulation_service import SimulationService
        service = SimulationService()
        return service.validate_system_config(config_path)

    async def get_performance_metrics_async(self) -> dict[str, Any]:
        """Get performance metrics asynchronously.

        Returns:
            Performance metrics dictionary,

        """
        if not self._initialized:
            await self.initialize_async()

        return self._async_simulation_service.get_performance_metrics()

    async def cancel_simulation_async(self, simulation_id: str) -> bool:
        """Cancel a running simulation.

        Args:
            simulation_id: ID of simulation to cancel

        Returns:
            True if cancellation was successful,

        """
        if not self._initialized:
            await self.initialize_async()

        return await self._async_simulation_service.cancel_simulation_async(simulation_id)

    async def get_simulation_status_async(self, simulation_id: str) -> Optional[dict[str, Any]]:
        """Get status of a running simulation.

        Args:
            simulation_id: ID of simulation

        Returns:
            Status dictionary or None if not found,

        """
        if not self._initialized:
            await self.initialize_async()

        return await self._async_simulation_service.get_simulation_status_async(simulation_id)

    async def shutdown_async(self) -> None:
        """Shutdown facade and cleanup resources."""
        if not self._initialized:
            return

        logger.info("Shutting down AsyncEcoSystemiserFacade")

        if self._async_simulation_service:
            await self._async_simulation_service.shutdown_async()

        if self._climate_service and hasattr(self._climate_service, "shutdown_async"):
            await self._climate_service.shutdown_async()

        self._initialized = False
        logger.info("AsyncEcoSystemiserFacade shutdown complete")


class AsyncFacadeFactory:
    """Factory for managing AsyncEcoSystemiserFacade instances.

    Follows Golden Rules - no global state, proper dependency injection.
    """

    def __init__(self):
        self._instance: Optional[AsyncEcoSystemiserFacade] = None

    async def get_facade_async(self) -> AsyncEcoSystemiserFacade:
        """Get or create an async facade instance.

        Returns:
            AsyncEcoSystemiserFacade instance

        """
        if self._instance is None:
            self._instance = AsyncEcoSystemiserFacade()
            await self._instance.initialize_async()
        return self._instance

    def reset(self) -> None:
        """Reset the facade instance for testing."""
        self._instance = None


# Create default factory for backward compatibility
_default_factory = AsyncFacadeFactory()


async def get_async_facade_async() -> AsyncEcoSystemiserFacade:
    """Get or create the async facade instance.

    Legacy function for backward compatibility.
    New code should use AsyncFacadeFactory directly.

    Returns:
        AsyncEcoSystemiserFacade instance

    """
    return await _default_factory.get_facade_async()


def get_facade_sync() -> AsyncEcoSystemiserFacade:
    """Get facade instance synchronously.

    Returns:
        AsyncEcoSystemiserFacade instance,

    """
    global _global_facade

    if _global_facade is None:
        _global_facade = AsyncEcoSystemiserFacade()
        # Initialize synchronously
        _global_facade.ensure_initialized()

    return _global_facade


# Convenience functions for common operations


async def run_simulation_with_async_io_async(
    config_path: Path, solver_type: str = "milp", timeout: float | None = None,
) -> dict[str, Any]:
    """Run a single simulation with async I/O optimizations.

    Args:
        config_path: Path to system configuration,
        solver_type: Solver type to use,
        timeout: Optional timeout in seconds

    Returns:
        Simulation result dictionary,

    """
    facade = await get_async_facade_async()

    # Create simulation config
    from datetime import datetime

    from ecosystemiser.services.simulation_service import SimulationConfig
    from ecosystemiser.solver.base import SolverConfig
    sim_config = SimulationConfig(
        simulation_id=f"async_sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        system_config_path=str(config_path),
        solver_type=solver_type,
        solver_config=SolverConfig(verbose=False, solver_type=solver_type),
        output_config={"save_results": True},
    )
    result = await facade.run_simulation_async(sim_config, timeout)
    return result.dict() if hasattr(result, "dict") else result.__dict__


async def fetch_climate_data_async(
    location: str, year: int, variables: list[str], source: str = "nasa_power",
) -> dict[str, Any]:
    """Fetch climate data with async I/O optimizations.

    Args:
        location: Location string or coordinates,
        year: Year to fetch,
        variables: List of variables to fetch,
        source: Data source to use

    Returns:
        Climate data response,

    """
    facade = await get_async_facade_async()

    # Create climate request
    request = ClimateRequest(
        location=location,
        variables=variables,
        source=source,
        period={"year": year},
        mode="observed",
        resolution="1H",
    )

    ds, response = await facade.get_climate_profile_async(request)
    return {
        "dataset": ds,
        "response": response,
        "manifest": response.manifest,
        "shape": response.shape,
        "path": response.path_parquet,
    }
