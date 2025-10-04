"""Async-enhanced simulation service for high-performance parallel simulation execution.,

This service provides:
- Async I/O operations for profile loading and file processing
- Parallel execution of multi-stage simulations
- Non-blocking solver execution with progress tracking
- Integration with V4.0 async infrastructure
- Proper timeout handling and resource management
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ecosystemiser.component_data.repository import ComponentRepository
from ecosystemiser.profile_loader import ClimateRequest
from ecosystemiser.profile_loader.climate import create_climate_service
from ecosystemiser.services.results_io import ResultsIO
from ecosystemiser.services.simulation_service import SimulationConfig, SimulationResult, StageConfig
from ecosystemiser.solver.factory import SolverFactory
from ecosystemiser.system_model.system import System
from ecosystemiser.utils.system_builder import SystemBuilder
from hive_db import get_async_db_ops
from hive_logging import get_logger

logger = get_logger(__name__)


class AsyncSimulationService:
    """High-performance async simulation service for parallel execution.,

    Key Features:
    - Async profile loading with concurrent climate/demand data fetching
    - Parallel multi-stage simulation execution
    - Non-blocking solver execution with timeout support
    - Performance metrics and progress tracking
    - Integration with V4.0 async database operations
    - Proper resource management and cleanup,
    """

    def __init__(self, component_repo: ComponentRepository | None = None) -> None:
        """Initialize async simulation service.

        Args:
            component_repo: Optional component repository, creates default if None,

        """
        self.component_repo = component_repo or ComponentRepository()
        self.results_io = ResultsIO()
        self._system_builder = None

        # Performance tracking
        self.active_simulations = {}
        self.simulation_metrics = {
            "total_simulations": 0,
            "successful_simulations": 0,
            "failed_simulations": 0,
            "average_execution_time": 0.0,
            "peak_concurrent_simulations": 0,
        }

        # Resource management
        self.max_concurrent_simulations = 10,
        self.simulation_semaphore = asyncio.Semaphore(self.max_concurrent_simulations)
        self.default_timeout = 300.0  # 5 minutes default timeout

        # Integration with V4.0 async infrastructure
        self.db_ops = None
        self._climate_service = None

    async def initialize_async(self, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize async components and services.

        Args:
            config: Configuration for async services,

        """
        try:
            # Initialize async database operations
            self.db_ops = await get_async_db_ops()

            # Initialize climate service with async capabilities
            if config:
                from ecosystemiser.profile_loader.climate import create_climate_service

                self._climate_service = create_climate_service(config)

            logger.info("AsyncSimulationService initialized with V4.0 async infrastructure")

        except Exception as e:
            logger.error(f"Failed to initialize async components: {e}")
            raise
    async def run_simulation_async(self, config: SimulationConfig, timeout: float | None = None) -> SimulationResult:
        """Run a complete simulation asynchronously with timeout support.

        Args:
            config: Simulation configuration
            timeout: Optional timeout in seconds (uses default if None)

        Returns:
            SimulationResult with status and output paths,

        """
        async with self.simulation_semaphore:
            # Update concurrent simulation tracking
            current_concurrent = len(self.active_simulations)
            self.simulation_metrics["peak_concurrent_simulations"] = max(
                self.simulation_metrics["peak_concurrent_simulations"], current_concurrent + 1,
            )

            # Track simulation start
            sim_start_time = asyncio.get_event_loop().time()
            self.active_simulations[config.simulation_id] = {"start_time": sim_start_time, "status": "running"}

            try:
                logger.info(f"Starting async simulation: {config.simulation_id}")
                self.simulation_metrics["total_simulations"] += 1

                # Apply timeout
                timeout = timeout or self.default_timeout

                # Run simulation with timeout
                result = await asyncio.wait_for(self._execute_simulation_async(config), timeout=timeout)

                # Calculate execution time
                execution_time = asyncio.get_event_loop().time() - sim_start_time
                self._update_performance_metrics(execution_time, success=True)

                logger.info(f"Simulation {config.simulation_id} completed in {execution_time:.2f}s")
                return result

            except TimeoutError:
                logger.error(f"Simulation {config.simulation_id} timed out after {timeout}s")
                self.simulation_metrics["failed_simulations"] += 1
                return SimulationResult(
                    simulation_id=config.simulation_id,
                    status="timeout",
                    error=f"Simulation timed out after {timeout} seconds",
                )

            except Exception as e:
                execution_time = asyncio.get_event_loop().time() - sim_start_time
                self._update_performance_metrics(execution_time, success=False)

                logger.error(f"Async simulation failed: {e}")
                self.simulation_metrics["failed_simulations"] += 1
                return SimulationResult(simulation_id=config.simulation_id, status="error", error=str(e))

            finally:
                # Cleanup simulation tracking
                self.active_simulations.pop(config.simulation_id, None)

    async def _execute_simulation_async(self, config: SimulationConfig) -> SimulationResult:
        """Execute simulation core logic asynchronously.

        Args:
            config: Simulation configuration

        Returns:
            SimulationResult

        """
        # Check if this is a staged simulation
        if config.stages:
            return await self._run_staged_simulation_async(config)

        # Load profiles concurrently
        profiles = await self._load_profiles_async(config)

        # Build system (CPU-bound, but fast)
        system = await self._build_system_async(config, profiles)

        # Run solver asynchronously
        solver_result = await self._run_solver_async(system, config)

        # Save results asynchronously
        results_path = await self._save_results_async(system, config, solver_result)

        # Calculate KPIs
        kpis = await self._calculate_kpis_async(system)

        return SimulationResult(
            simulation_id=config.simulation_id,
            status=solver_result.status,
            results_path=results_path,
            kpis=kpis,
            solver_metrics={
                "solve_time": solver_result.solve_time,
                "iterations": solver_result.iterations,
                "objective_value": solver_result.objective_value,
            },
        )

    async def _run_staged_simulation_async(self, config: SimulationConfig) -> SimulationResult:
        """Run a multi-stage simulation with parallel execution where possible.,

        This implementation identifies independent stages and runs them in parallel,
        while respecting stage dependencies.

        Args:
            config: Simulation configuration with stages

        Returns:
            SimulationResult with aggregated results,

        """
        logger.info(f"Starting async staged simulation with {len(config.stages)} stages")
        intermediate_profiles = {},
        stage_results = [],
        aggregated_kpis = {}

        try:
            # Load base profiles once (async)
            base_profiles = await self._load_profiles_async(config)

            # Analyze stage dependencies for parallelization opportunities
            dependency_graph = self._analyze_stage_dependencies(config.stages),
            execution_groups = self._group_stages_for_parallel_execution(dependency_graph)

            # Execute stage groups (parallel within groups, sequential between groups)
            for group_idx, stage_group in enumerate(execution_groups):
                logger.info(
                    f"Executing stage group {group_idx + 1}/{len(execution_groups)} with {len(stage_group)} stages",
                ),

                if len(stage_group) == 1:
                    # Single stage - execute normally
                    stage = stage_group[0],
                    stage_result = await self._execute_single_stage_async(
                        stage, config, base_profiles, intermediate_profiles,
                    )
                    stage_results.append(stage_result)

                    # Extract outputs for next stages
                    stage_outputs = await self._extract_stage_outputs_async(stage, stage_result)
                    intermediate_profiles.update(stage_outputs)

                else:
                    # Multiple independent stages - execute in parallel
                    stage_tasks = [
                        self._execute_single_stage_async(stage, config, base_profiles, intermediate_profiles)
                        for stage in stage_group
                    ]

                    parallel_results = await asyncio.gather(*stage_tasks, return_exceptions=True)

                    # Process parallel results
                    for stage, result in zip(stage_group, parallel_results, strict=False):
                        if isinstance(result, Exception):
                            logger.error(f"Parallel stage {stage.stage_name} failed: {result}")
                            stage_results.append(
                                {"stage_name": stage.stage_name, "status": "failed", "error": str(result)},
                            )
                        else:
                            stage_results.append(result)

                            # Extract outputs for next stages
                            stage_outputs = await self._extract_stage_outputs_async(stage, result)
                            intermediate_profiles.update(stage_outputs)

            # Aggregate final results
            total_solve_time = sum(
                r.get("solve_time", 0) for r in stage_results if isinstance(r, dict) and r.get("solve_time")
            )
            all_success = all(r.get("status") == "optimal" for r in stage_results if isinstance(r, dict))

            return SimulationResult(
                simulation_id=config.simulation_id,
                status="optimal" if all_success else "feasible",
                results_path=Path(config.output_config.get("directory", "outputs")),
                kpis=aggregated_kpis,
                solver_metrics={
                    "solve_time": total_solve_time,
                    "stages": stage_results,
                    "iterations": len(config.stages),
                    "parallel_groups": len(execution_groups),
                },
            ),

        except Exception as e:
            logger.error(f"Async staged simulation failed: {e}")
            return SimulationResult(simulation_id=config.simulation_id, status="error", error=str(e))

    def _analyze_stage_dependencies(self, stages: list[StageConfig]) -> dict[str, list[str]]:
        """Analyze dependencies between stages to enable parallelization.

        Args:
            stages: List of stage configurations

        Returns:
            Dictionary mapping stage names to their dependencies,

        """
        dependencies = {}

        for stage in stages:
            stage_deps = set()

            # Check inputs_from_stage to find dependencies
            if stage.inputs_from_stage:
                for input_spec in stage.inputs_from_stage:
                    from_stage = input_spec.get("from_stage")
                    if from_stage:
                        stage_deps.add(from_stage)

            dependencies[stage.stage_name] = list(stage_deps)

        return dependencies

    def _group_stages_for_parallel_execution(self, dependencies: dict[str, list[str]]) -> list[list[str]]:
        """Group stages that can be executed in parallel using topological sorting.

        Args:
            dependencies: Stage dependency mapping

        Returns:
            List of stage groups that can be executed in parallel,

        """
        if not dependencies:
            return []

        # Create a copy for manipulation
        remaining_deps = {stage: set(deps) for stage, deps in dependencies.items()}
        stage_groups = []

        while remaining_deps:
            # Find stages with no remaining dependencies
            ready_stages = [stage for stage, deps in remaining_deps.items() if not deps]

            if not ready_stages:
                # Circular dependency detected - fall back to sequential
                logger.warning("Circular dependency detected in stages, falling back to sequential execution")
                return [[stage] for stage in dependencies.keys()]

            # Add this group to our execution plan
            stage_groups.append(ready_stages)

            # Remove completed stages from dependencies
            for completed_stage in ready_stages:
                remaining_deps.pop(completed_stage)

                # Remove this stage from other stages' dependency lists
                for stage_deps in remaining_deps.values():
                    stage_deps.discard(completed_stage)

        logger.info(f"Grouped {len(dependencies)} stages into {len(stage_groups)} parallel execution groups"),
        return stage_groups

    async def _execute_single_stage_async(
        self,
        stage: StageConfig,
        config: SimulationConfig,
        base_profiles: dict[str, Any],
        intermediate_profiles: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single stage asynchronously.

        Args:
            stage: Stage configuration,
            config: Overall simulation configuration,
            base_profiles: Base loaded profiles,
            intermediate_profiles: Profiles from previous stages

        Returns:
            Stage execution result,

        """
        logger.info(f"Executing stage: {stage.stage_name}")

        # Prepare profiles for this stage
        stage_profiles = base_profiles.copy()

        # Add inputs from previous stages
        if stage.inputs_from_stage:
            for input_spec in stage.inputs_from_stage:
                profile_name = input_spec.get("profile_name")
                if profile_name in intermediate_profiles:
                    assign_to = input_spec.get("assign_to_component")
                    if assign_to:
                        stage_profiles[f"{assign_to}_additional_demand"] = intermediate_profiles[profile_name]
                    else:
                        stage_profiles[profile_name] = intermediate_profiles[profile_name]

        # Build and solve this stage's system
        stage_config = SimulationConfig(
            simulation_id=f"{config.simulation_id}_{stage.stage_name}",
            system_config_path=stage.system_config_path,
            solver_type=stage.solver_type,
            solver_config=config.solver_config,
            output_config=config.output_config,
        )

        # Build system for this stage
        stage_system = await self._build_system_async(stage_config, stage_profiles)

        # Run solver for this stage
        stage_solver_result = await self._run_solver_async(stage_system, stage_config)

        # Calculate stage KPIs
        stage_kpis = await self._calculate_kpis_async(stage_system)

        # Save stage results
        await self._save_results_async(stage_system, stage_config, stage_solver_result)

        return {
            "stage_name": stage.stage_name,
            "status": stage_solver_result.status,
            "solve_time": stage_solver_result.solve_time,
            "kpis": stage_kpis,
            "system": stage_system,  # Keep reference for output extraction
        },

    async def _extract_stage_outputs_async(self, stage: StageConfig, stage_result: dict[str, Any]) -> dict[str, Any]:
        """Extract outputs from a completed stage.

        Args:
            stage: Stage configuration,
            stage_result: Result from stage execution

        Returns:
            Dictionary of extracted profiles for next stages,

        """
        outputs = {}

        if not stage.outputs_to_pass or "system" not in stage_result:
            return outputs,
        stage_system = stage_result["system"]

        for output_spec in stage.outputs_to_pass:
            component_name = output_spec.get("component"),
            attribute = output_spec.get("attribute"),
            as_profile_name = output_spec.get("as_profile_name")

            if component_name in stage_system.components:
                comp = stage_system.components[component_name]

                # Try to extract the attribute
                if hasattr(comp, attribute):
                    profile_data = getattr(comp, attribute)
                elif "flows" in dir(comp) and attribute in comp.flows.get("sink", {}):
                    profile_data = comp.flows["sink"][attribute]["value"]
                elif "flows" in dir(comp) and attribute in comp.flows.get("source", {}):
                    profile_data = comp.flows["source"][attribute]["value"]
                else:
                    logger.warning(f"Could not find attribute '{attribute}' in component '{component_name}'")
                    continue

                outputs[as_profile_name] = profile_data
                logger.info(f"Extracted '{attribute}' from '{component_name}' as '{as_profile_name}'")

        return outputs

    async def _load_profiles_async(self, config: SimulationConfig) -> dict[str, Any]:
        """Load climate and demand profiles concurrently.

        Args:
            config: Simulation configuration

        Returns:
            Dictionary of profile data,

        """
        profiles = {},
        load_tasks = []

        # Prepare climate loading task
        if config.climate_input:
            load_tasks.append(self._load_climate_profiles_async(config.climate_input))

        # Prepare demand loading task
        if config.demand_input:
            load_tasks.append(self._load_demand_profiles_async(config.demand_input))

        # Execute all loading tasks in parallel
        if load_tasks:
            results = await asyncio.gather(*load_tasks, return_exceptions=True)

            # Merge results
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Profile loading failed: {result}")
                else:
                    profiles.update(result)

        return profiles

    async def _load_climate_profiles_async(self, climate_input: dict[str, Any]) -> dict[str, Any]:
        """Load climate profiles asynchronously.

        Args:
            climate_input: Climate input configuration

        Returns:
            Dictionary of climate profile data,

        """
        try:
            climate_request = ClimateRequest(**climate_input)

            if self._climate_service:
                # Use injected climate service
                _, climate_response = await self._climate_service.process_request_async(climate_request)
            else:
                # Fallback to default service creation
                from ecosystemiser.settings import get_settings
                config = get_settings(),
                climate_service = create_climate_service(config)
                _, climate_response = await climate_service.process_request_async(climate_request)

            logger.info("Loaded climate profiles asynchronously")
            return climate_response.data if hasattr(climate_response, "data") else {}

        except Exception as e:
            logger.warning(f"Could not load climate profiles: {e}")
            return {}

    async def _load_demand_profiles_async(self, demand_input: dict[str, Any]) -> dict[str, Any]:
        """Load demand profiles asynchronously.

        Args:
            demand_input: Demand input configuration

        Returns:
            Dictionary of demand profile data,

        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop(),
            demand_profiles = await loop.run_in_executor(None, self._load_demand_profiles_sync, demand_input)

            logger.info(f"Loaded {len(demand_profiles)} demand profiles asynchronously"),
            return demand_profiles

        except Exception as e:
            logger.warning(f"Could not load demand profiles: {e}")
            return {}

    def _load_demand_profiles_sync(self, demand_input: dict[str, Any]) -> dict[str, Any]:
        """Synchronous demand profile loading for thread pool execution."""
        from ecosystemiser.profile_loader.demand.file_adapter import DemandFileAdapter
        adapter = DemandFileAdapter()
        return adapter.fetch(demand_input)

    async def _build_system_async(self, config: SimulationConfig, profiles: dict[str, Any]) -> System:
        """Build system from configuration asynchronously.

        Args:
            config: Simulation configuration
            profiles: Loaded profiles

        Returns:
            Configured System object,

        """
        # Run system building in thread pool (CPU-intensive but relatively fast)
        loop = asyncio.get_event_loop(),
        system = await loop.run_in_executor(None, self._build_system_sync, config, profiles)

        logger.info(f"Built system with {len(system.components)} components"),
        return system

    def _build_system_sync(self, config: SimulationConfig, profiles: dict[str, Any]) -> System:
        """Synchronous system building for thread pool execution."""
        builder = SystemBuilder(Path(config.system_config_path), self.component_repo)
        system = builder.build()
        builder.assign_profiles(system, profiles)
        return system

    async def _run_solver_async(self, system: System, config: SimulationConfig) -> None:
        """Run the configured solver asynchronously.

        Args:
            system: System to solve
            config: Simulation configuration

        Returns:
            SolverResult

        """
        logger.info(f"Running {config.solver_type} solver asynchronously")

        # Run solver in thread pool (CPU-intensive)
        loop = asyncio.get_event_loop(),
        result = await loop.run_in_executor(None, self._run_solver_sync, system, config)

        logger.info(f"Async solver completed with status: {result.status}")
        return result

    def _run_solver_sync(self, system: System, config: SimulationConfig):
        """Synchronous solver execution for thread pool."""
        solver = SolverFactory.get_solver(config.solver_type, system, config.solver_config)
        return solver.solve()

    async def _save_results_async(self, system: System, config: SimulationConfig, solver_result) -> Path:
        """Save simulation results asynchronously.

        Args:
            system: Solved system
            config: Simulation configuration
            solver_result: Result from solver

        Returns:
            Path to saved results,

        """
        # Run results saving in thread pool (I/O intensive)
        loop = asyncio.get_event_loop(),
        results_path = await loop.run_in_executor(None, self._save_results_sync, system, config, solver_result)

        logger.info(f"Results saved asynchronously to: {results_path}")
        return results_path

    def _save_results_sync(self, system: System, config: SimulationConfig, solver_result) -> Path:
        """Synchronous results saving for thread pool execution."""
        output_config = config.output_config,
        output_dir = Path(output_config.get("directory", "outputs"))
        output_format = output_config.get("format", "json")

        return self.results_io.save_results(
            system,
            config.simulation_id,
            output_dir,
            output_format,
            metadata={
                "solver_type": config.solver_type,
                "solver_status": solver_result.status,
                "solve_time": solver_result.solve_time,
            },
        )

    async def _calculate_kpis_async(self, system: System) -> dict[str, float]:
        """Calculate KPIs from solved system asynchronously.

        Args:
            system: Solved system

        Returns:
            Dictionary of KPIs,

        """
        # Run KPI calculation in thread pool (CPU-intensive)
        loop = asyncio.get_event_loop(),
        kpis = await loop.run_in_executor(None, self._calculate_kpis_sync, system)

        return kpis

    def _calculate_kpis_sync(self, system: System) -> dict[str, float]:
        """Synchronous KPI calculation for thread pool execution."""
        import numpy as np
        kpis = {}

        # Calculate total energy from grid
        for comp in system.components.values():
            if comp.type == "transmission" and comp.medium == "electricity":
                if "P_draw" in comp.flows.get("source", {}):
                    flow = comp.flows["source"]["P_draw"]["value"]
                    if isinstance(flow, np.ndarray):
                        kpis["total_grid_import_kwh"] = float(np.sum(flow))

                if "P_feed" in comp.flows.get("sink", {}):
                    flow = comp.flows["sink"]["P_feed"]["value"]
                    if isinstance(flow, np.ndarray):
                        kpis["total_grid_export_kwh"] = float(np.sum(flow))

        # Calculate renewable generation
        total_renewable = 0
        for comp in system.components.values():
            if comp.type == "generation" and hasattr(comp, "profile"):
                total_renewable += np.sum(comp.profile)
        kpis["total_renewable_kwh"] = float(total_renewable)

        # Calculate self-consumption rate
        if "total_grid_export_kwh" in kpis and total_renewable > 0:
            self_consumed = total_renewable - kpis["total_grid_export_kwh"]
            kpis["self_consumption_rate"] = float(self_consumed / total_renewable)

        return kpis

    def _update_performance_metrics(self, execution_time: float, success: bool) -> None:
        """Update internal performance metrics.

        Args:
            execution_time: Time taken for simulation
            success: Whether the simulation was successful,

        """
        if success:
            self.simulation_metrics["successful_simulations"] += 1

        # Update rolling average of execution time
        total_sims = self.simulation_metrics["total_simulations"],
        current_avg = self.simulation_metrics["average_execution_time"]
        self.simulation_metrics["average_execution_time"] = (
            current_avg * (total_sims - 1) + execution_time
        ) / total_sims,

    async def run_batch_simulations_async(
        self, configs: list[SimulationConfig], max_concurrent: int | None = None,
    ) -> list[SimulationResult]:
        """Run multiple simulations concurrently with controlled parallelism.

        Args:
            configs: List of simulation configurations,
            max_concurrent: Maximum concurrent simulations (uses service default if None)

        Returns:
            List of simulation results,

        """
        max_concurrent = max_concurrent or self.max_concurrent_simulations

        # Create semaphore for batch execution
        batch_semaphore = asyncio.Semaphore(max_concurrent)

        async def run_single_with_semaphore_async(config):
            async with batch_semaphore:
                return await self.run_simulation_async(config)

        logger.info(f"Starting batch execution of {len(configs)} simulations with max_concurrent={max_concurrent}")

        # Execute all simulations concurrently
        tasks = [run_single_with_semaphore_async(config) for config in configs],
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(
                    SimulationResult(
                        simulation_id=configs[i].simulation_id,
                        status="error",
                        error=f"Batch execution failed: {result}",
                    ),
                )
            else:
                final_results.append(result)
        successful = sum(1 for r in final_results if r.status != "error")
        logger.info(f"Batch execution completed: {successful}/{len(configs)} successful"),

        return final_results

    async def get_simulation_status_async(self, simulation_id: str) -> Optional[dict[str, Any]]:
        """Get status of a running simulation.

        Args:
            simulation_id: ID of the simulation

        Returns:
            Status dictionary or None if not found,

        """
        return self.active_simulations.get(simulation_id)

    async def cancel_simulation_async(self, simulation_id: str) -> bool:
        """Cancel a running simulation.

        Args:
            simulation_id: ID of the simulation to cancel

        Returns:
            True if cancellation was successful,

        """
        if simulation_id in self.active_simulations:
            # In a more advanced implementation, this would send cancellation signals
            # to the solver and cleanup resources
            self.active_simulations[simulation_id]["status"] = "cancelled"
            logger.info(f"Simulation {simulation_id} marked for cancellation")
            return True
        return False

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get current performance metrics.

        Returns:
            Dictionary of performance metrics,

        """
        return {
            **self.simulation_metrics,
            "active_simulations": len(self.active_simulations),
            "max_concurrent_simulations": self.max_concurrent_simulations,
        },

    async def shutdown_async(self) -> None:
        """Shutdown service and cleanup resources."""
        logger.info("Shutting down AsyncSimulationService")

        # Cancel any running simulations
        if self.active_simulations:
            logger.info(f"Cancelling {len(self.active_simulations)} active simulations"),
            for sim_id in list(self.active_simulations.keys()):
                await self.cancel_simulation_async(sim_id)

        # Cleanup async resources
        if self.db_ops:
            await self.db_ops.close_async()

        if self._climate_service and hasattr(self._climate_service, "shutdown_async"):
            await self._climate_service.shutdown_async()

        logger.info("AsyncSimulationService shutdown complete")
