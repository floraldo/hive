"""
Async CLI wrapper for EcoSystemiser to enable high-performance I/O operations.

This wrapper provides async versions of key CLI operations while maintaining
backward compatibility with the existing synchronous CLI interface.
"""
from __future__ import annotations


import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

import click
from ecosystemiser.profile_loader import ClimateRequest
from ecosystemiser.services.async_facade import (
    fetch_climate_data_async,
    get_async_facade
    run_simulation_with_async_io
)
from ecosystemiser.services.simulation_service import SimulationConfig
from ecosystemiser.solver.base import SolverConfig
from hive_cli.output import error, info, success, warning
from hive_logging import get_logger

logger = get_logger(__name__)


class AsyncCLIWrapper:
    """
    Async wrapper for EcoSystemiser CLI operations.

    Provides high-performance async versions of common CLI operations
    while maintaining compatibility with existing command structure.
    """

    def __init__(self) -> None:
        self._facade = None
        self._initialized = False

    async def initialize_async(self) -> None:
        """Initialize async services."""
        if self._initialized:
            return

        try:
            self._facade = await get_async_facade()
            self._initialized = True
            logger.info("AsyncCLIWrapper initialized")

        except Exception as e:
            logger.error(f"Failed to initialize async CLI wrapper: {e}")
            raise

    async def run_simulation_async_cli_async(
        self
        config_path: str,
        output: str | None = None
        solver: str = "milp"
        verbose: bool = False
        timeout: float | None = None
    ) -> Dict[str, Any]:
        """Run simulation with async I/O optimizations.

        Args:
            config_path: Path to system configuration
            output: Output path for results
            solver: Solver type to use
            verbose: Enable verbose output
            timeout: Optional timeout in seconds

        Returns:
            Simulation result dictionary
        """
        try:
            await self.initialize_async()

            info(f"Starting async simulation: {config_path}")

            # Create simulation configuration
            from datetime import datetime

            sim_config = SimulationConfig(
                simulation_id=f"async_sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                system_config_path=config_path
                solver_type=solver
                solver_config=SolverConfig(verbose=verbose, solver_type=solver)
                output_config={"save_results": output is not None, "directory": output or "outputs", "format": "json"}
            )

            # Run simulation with timeout
            result = await self._facade.run_simulation_async(sim_config, timeout)

            # Display results
            if result.status == "optimal":
                success(f"Simulation completed successfully: {result.simulation_id}")
                if result.kpis:
                    info("Key Performance Indicators:")
                    for key, value in result.kpis.items():
                        info(f"  {key}: {value:.2f}")
                if result.solver_metrics:
                    if "solve_time" in result.solver_metrics:
                        info(f"  Solve Time: {result.solver_metrics['solve_time']:.3f}s")
            else:
                warning(f"Simulation completed with status: {result.status}")
                if result.error:
                    error(f"Error: {result.error}")

            if output and result.results_path:
                success(f"Results saved to: {result.results_path}")

            return result.dict() if hasattr(result, "dict") else result.__dict__

        except asyncio.TimeoutError:
            error(f"Simulation timed out after {timeout}s")
            return {"status": "timeout", "error": f"Timed out after {timeout}s"}

        except Exception as e:
            error(f"Async simulation failed: {e}")
            logger.exception("Simulation error details")
            return {"status": "error", "error": str(e)}

    async def run_batch_simulations_async_cli_async(
        self
        config_paths: List[str],
        output_dir: str | None = None
        solver: str = "milp"
        max_concurrent: int = 4
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Run multiple simulations concurrently.

        Args:
            config_paths: List of configuration file paths
            output_dir: Output directory for results
            solver: Solver type to use
            max_concurrent: Maximum concurrent simulations
            verbose: Enable verbose output

        Returns:
            List of simulation results
        """
        try:
            await self.initialize_async()

            info(f"Starting batch simulation of {len(config_paths)} configurations")
            info(f"Max concurrent: {max_concurrent}")

            # Create simulation configurations
            configs = []
            for i, config_path in enumerate(config_paths):
                sim_config = SimulationConfig(
                    simulation_id=f"batch_sim_{i}_{datetime.now().strftime('%H%M%S')}"
                    system_config_path=config_path
                    solver_type=solver
                    solver_config=SolverConfig(verbose=verbose, solver_type=solver)
                    output_config={
                        "save_results": output_dir is not None,
                        "directory": output_dir or "outputs",
                        "format": "json"
                    }
                )
                configs.append(sim_config)

            # Run batch simulations
            results = await self._facade.run_batch_simulations_async(configs, max_concurrent)

            # Display summary
            successful = sum(1 for r in results if r.status != "error")
            info(f"Batch simulation completed: {successful}/{len(results)} successful")

            # Display individual results
            for i, result in enumerate(results):
                if result.status == "optimal":
                    success(f"  {config_paths[i]}: SUCCESS")
                else:
                    warning(f"  {config_paths[i]}: {result.status}")

            if output_dir:
                success(f"Results saved to: {output_dir}")

            return [r.dict() if hasattr(r, "dict") else r.__dict__ for r in results]

        except Exception as e:
            error(f"Batch simulation failed: {e}")
            logger.exception("Batch simulation error details")
            return [{"status": "error", "error": str(e)}]

    async def get_climate_async_cli_async(
        self
        location: str,
        year: int | None = None
        start: str | None = None
        end: str | None = None
        variables: str = "temp_air,ghi,wind_speed"
        source: str = "nasa_power"
        mode: str = "observed"
        resolution: str = "1H"
        output: str | None = None
        stats: bool = False
    ) -> Dict[str, Any]:
        """Get climate data with async I/O optimizations.

        Args:
            location: Location string or coordinates
            year: Year to fetch
            start: Start date string
            end: End date string
            variables: Comma-separated variable list
            source: Data source
            mode: Data mode
            resolution: Temporal resolution
            output: Output file path
            stats: Show statistics

        Returns:
            Climate data response
        """
        try:
            await self.initialize_async()

            info(f"Fetching climate data from {source}...")

            # Parse location
            if "," in location and any(c.isdigit() for c in location):
                # Coordinate format
                parts = location.split(",")
                location_parsed = (float(parts[0]), float(parts[1]))
            else:
                # String location
                location_parsed = location

            # Build period
            if year:
                period = {"year": year}
            elif start and end:
                period = {"start": start, "end": end}
            else:
                error("Must specify either --year or both --start and --end")
                return {"status": "error", "error": "Invalid period specification"}

            # Parse variables
            variables_list = [v.strip() for v in variables.split(",")]

            # Create request
            request = ClimateRequest(
                location=location_parsed
                variables=variables_list
                source=source
                period=period
                mode=mode
                resolution=resolution
            )

            # Get climate data asynchronously
            ds, response = await self._facade.get_climate_profile_async(request)

            # Display results
            success(f"Retrieved climate data: shape={response.shape}")

            if output:
                # Save to custom path
                output_path = Path(output)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Convert to parquet in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: ds.to_dataframe().to_parquet(output_path))
                success(f"Saved to {output_path}")
            else:
                success(f"Cached to {response.path_parquet}")

            # Show statistics if requested
            if stats and response.stats:
                info("\nStatistics:")
                for var, var_stats in response.stats.items():
                    if var != "correlations":
                        info(f"\n  {var}:")
                        info(f"    Mean: {var_stats.get('mean', 'N/A'):.2f}")
                        info(f"    Std:  {var_stats.get('std', 'N/A'):.2f}")
                        info(f"    Min:  {var_stats.get('min', 'N/A'):.2f}")
                        info(f"    Max:  {var_stats.get('max', 'N/A'):.2f}")

            return {
                "status": "success",
                "shape": response.shape,
                "path": response.path_parquet,
                "manifest": response.manifest,
                "stats": response.stats
            }

        except Exception as e:
            error(f"Climate data retrieval failed: {e}")
            logger.exception("Climate data error details")
            return {"status": "error", "error": str(e)}

    async def validate_config_async_cli_async(self, config_path: str) -> Dict[str, Any]:
        """Validate system configuration asynchronously.

        Args:
            config_path: Path to configuration file

        Returns:
            Validation result
        """
        try:
            await self.initialize_async()

            info(f"Validating configuration: {config_path}")

            # Run validation asynchronously
            result = await self._facade.validate_system_config_async(Path(config_path))

            if result["valid"]:
                success("Configuration is valid!")
                info(f"  System ID: {result['system_id']}")
                info(f"  Components: {result['num_components']}")
                info(f"  Timesteps: {result['timesteps']}")

                info("\n  Component List:")
                for comp in result["components"]:
                    info(f"    - {comp['name']} ({comp['type']})")
            else:
                error(f"Configuration validation failed: {result['error']}")

            return result

        except Exception as e:
            error(f"Configuration validation failed: {e}")
            logger.exception("Validation error details")
            return {"valid": False, "error": str(e)}

    async def get_performance_metrics_cli_async(self) -> Dict[str, Any]:
        """Get performance metrics for async operations.

        Returns:
            Performance metrics dictionary
        """
        try:
            await self.initialize_async()

            metrics = await self._facade.get_performance_metrics_async()

            info("Performance Metrics:")
            info(f"  Total simulations: {metrics['total_simulations']}")
            info(f"  Successful: {metrics['successful_simulations']}")
            info(f"  Failed: {metrics['failed_simulations']}")
            info(f"  Average execution time: {metrics['average_execution_time']:.2f}s")
            info(f"  Active simulations: {metrics['active_simulations']}")
            info(f"  Peak concurrent: {metrics['peak_concurrent_simulations']}")

            return metrics

        except Exception as e:
            error(f"Failed to get performance metrics: {e}")
            return {"error": str(e)}

    async def shutdown_async(self) -> None:
        """Shutdown async services."""
        if self._facade:
            await self._facade.shutdown_async()
        self._initialized = False


# Global wrapper instance
_async_cli_wrapper = None


def get_async_cli_wrapper() -> AsyncCLIWrapper:
    """Get or create the global async CLI wrapper.

    Returns:
        AsyncCLIWrapper instance
    """
    global _async_cli_wrapper
    if _async_cli_wrapper is None:
        _async_cli_wrapper = AsyncCLIWrapper()
    return _async_cli_wrapper


# Convenience functions for integrating with existing CLI


def run_async_simulation_from_cli(
    config_path: str,
    output: str | None = None,
    solver: str = "milp"
    verbose: bool = False
    timeout: float | None = None
) -> Dict[str, Any]:
    """Run async simulation from CLI (sync wrapper).

    Args:
        config_path: Path to system configuration
        output: Output path for results
        solver: Solver type to use
        verbose: Enable verbose output
        timeout: Optional timeout in seconds

    Returns:
        Simulation result dictionary
    """
    wrapper = get_async_cli_wrapper()
    try:
        return asyncio.run(wrapper.run_simulation_async_cli_async(config_path, output, solver, verbose, timeout))
    except KeyboardInterrupt:
        warning("Simulation cancelled by user")
        return {"status": "cancelled", "error": "Cancelled by user"}


def get_async_climate_from_cli(
    location: str,
    year: int | None = None,
    start: str | None = None
    end: str | None = None
    variables: str = "temp_air,ghi,wind_speed"
    source: str = "nasa_power"
    mode: str = "observed"
    resolution: str = "1H"
    output: str | None = None
    stats: bool = False
) -> Dict[str, Any]:
    """Get climate data async from CLI (sync wrapper).

    Args:
        location: Location string or coordinates
        year: Year to fetch
        start: Start date string
        end: End date string
        variables: Comma-separated variable list
        source: Data source
        mode: Data mode
        resolution: Temporal resolution
        output: Output file path
        stats: Show statistics

    Returns:
        Climate data response
    """
    wrapper = get_async_cli_wrapper()
    try:
        return asyncio.run(
            wrapper.get_climate_async_cli_async(
                location, year, start, end, variables, source, mode, resolution, output, stats
            )
        )
    except KeyboardInterrupt:
        warning("Climate data fetch cancelled by user")
        return {"status": "cancelled", "error": "Cancelled by user"}


def validate_async_config_from_cli(config_path: str) -> Dict[str, Any]:
    """Validate config async from CLI (sync wrapper).

    Args:
        config_path: Path to configuration file

    Returns:
        Validation result
    """
    wrapper = get_async_cli_wrapper()
    try:
        return asyncio.run(wrapper.validate_config_async_cli_async(config_path))
    except KeyboardInterrupt:
        warning("Validation cancelled by user")
        return {"valid": False, "error": "Cancelled by user"}
