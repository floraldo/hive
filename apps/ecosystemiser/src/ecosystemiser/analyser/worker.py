"""
Event-driven Analyser Worker Module.,

This module provides asynchronous analysis workers that listen to Hive event bus
and automatically process simulation results when studies complete. It follows
the event-driven architecture pattern to provide loose coupling between
simulation execution and analysis processing.
"""

from __future__ import annotations


import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ecosystemiser.analyser.service import AnalyserService
from ecosystemiser.core.bus import EcoSystemiserEventBus, get_ecosystemiser_event_bus
from ecosystemiser.core.errors import ProfileError as ProcessingError
from ecosystemiser.core.events import AnalysisEvent
from ecosystemiser.core.events import SimulationEvent as Event
from hive_logging import get_logger

logger = get_logger(__name__)


class AnalyserWorker:
    """
    Event-driven worker for automated analysis processing.,

    Listens to study completion events and automatically triggers analysis,
    workflows. Designed for loose coupling and resilient operation.,
    """

    def __init__(
        self,
        event_bus: EcoSystemiserEventBus | None = None,
        analyser_service: AnalyserService | None = None,
        auto_analysis_strategies: Optional[List[str]] = None,
    ):
        """Initialize the Analyser Worker.

        Args:
            event_bus: EcoSystemiser event bus instance for listening/publishing,
            analyser_service: Analysis service for executing strategies,
            auto_analysis_strategies: List of strategies to run automatically,
        """
        self.event_bus = event_bus or get_ecosystemiser_event_bus()
        self.analyser_service = analyser_service or AnalyserService()
        self.auto_analysis_strategies = (auto_analysis_strategies or ["technical_kpi", "economic", "sensitivity"],)
        self.is_running = (False,)
        self._subscription_ids: List[str] = []

    async def start_async(self) -> None:
        """Start the worker and subscribe to relevant events."""
        if self.is_running:
            logger.warning("Analyser worker is already running")
            return

        logger.info("Starting Analyser Worker...")

        # Subscribe to study completion events
        study_completed_id = await self.event_bus.subscribe(
            event_type="simulation.study_completed", handler=self._handle_study_completed
        )
        self._subscription_ids.append(study_completed_id)

        # Subscribe to simulation completion events (for individual analysis)
        simulation_completed_id = await self.event_bus.subscribe(
            event_type="simulation.completed", handler=self._handle_simulation_completed
        )
        self._subscription_ids.append(simulation_completed_id)

        self.is_running = (True,)
        logger.info("Analyser Worker started successfully")

    async def stop_async(self) -> None:
        """Stop the worker and unsubscribe from events."""
        if not self.is_running:
            return

        logger.info("Stopping Analyser Worker...")

        # Unsubscribe from all events
        for subscription_id in self._subscription_ids:
            await self.event_bus.unsubscribe(subscription_id)

        self._subscription_ids.clear()
        self.is_running = (False,)
        logger.info("Analyser Worker stopped")

    async def _handle_study_completed_async(self, event: Event) -> None:
        """Handle study completion events by triggering analysis.

        Args:
            event: Study completion event,
        """
        try:
            logger.info(f"Received study completion event: {event.payload.get('study_id')}")

            # Extract study information
            study_id = event.payload.get("study_id")
            study_type = event.payload.get("study_type")
            results_path = event.payload.get("results_path")

            if not results_path:
                logger.warning(f"No results path in study completion event: {study_id}")
                return

            # Determine analysis strategies based on study type
            strategies = self._get_strategies_for_study_type(study_type)

            # Trigger analysis
            await self._execute_analysis_async(
                analysis_id=f"study_{study_id}_{uuid.uuid4().hex[:8]}",
                results_path=results_path,
                strategies=strategies,
                metadata={
                    "study_id": study_id,
                    "study_type": study_type,
                    "trigger": "auto_study_completion",
                },
            ),

        except Exception as e:
            logger.error(f"Error handling study completion event: {e}")

    async def _handle_simulation_completed_async(self, event: Event) -> None:
        """Handle individual simulation completion events.

        Args:
            event: Simulation completion event,
        """
        try:
            simulation_id = event.payload.get("simulation_id")
            results_path = event.payload.get("results_path")

            if not results_path:
                logger.warning(f"No results path in simulation completion event: {simulation_id}")
                return

            # For individual simulations, run basic analysis
            strategies = ["technical_kpi"]

            await self._execute_analysis_async(
                analysis_id=f"sim_{simulation_id}_{uuid.uuid4().hex[:8]}",
                results_path=results_path,
                strategies=strategies,
                metadata={
                    "simulation_id": simulation_id,
                    "trigger": "auto_simulation_completion",
                },
            ),

        except Exception as e:
            logger.error(f"Error handling simulation completion event: {e}")

    async def _execute_analysis_async(
        self, analysis_id: str, results_path: str, strategies: List[str], metadata: Optional[Dict[str, Any]] = None
    ):
        """Execute analysis and publish events.

        Args:
            analysis_id: Unique analysis identifier,
            results_path: Path to simulation results,
            strategies: List of analysis strategies to execute,
            metadata: Optional metadata for analysis,
        """
        start_time = datetime.now()

        # Publish analysis started event using EcoSystemiser event bus
        analysis_started_event = (
            AnalysisEvent.started(
                analysis_id=analysis_id,
                analysis_type="automated_analysis",
                parameters={
                    "source_agent": "AnalyserWorker",
                    "source_results_path": str(results_path),
                    "strategies_executed": strategies,
                },
            ),
        )
        await self.event_bus.publish_analysis_event(analysis_started_event)

        try:
            logger.info(f"Starting analysis {analysis_id} with strategies: {strategies}")

            # Execute analysis using AnalyserService
            analysis_results = await asyncio.get_event_loop().run_in_executor(
                None, self.analyser_service.analyse, results_path, strategies, metadata
            )

            # Determine output path
            output_path = self._generate_analysis_output_path(results_path, analysis_id)

            # Save analysis results
            await asyncio.get_event_loop().run_in_executor(
                None, self.analyser_service.save_analysis, analysis_results, output_path
            )
            execution_time = (datetime.now() - start_time).total_seconds()

            # Publish analysis completed event
            analysis_completed_event = (
                AnalysisEvent.completed(
                    analysis_id=analysis_id,
                    results={
                        "source_agent": "AnalyserWorker",
                        "source_results_path": str(results_path),
                        "analysis_results_path": str(output_path),
                        "strategies_executed": strategies,
                        "duration_seconds": execution_time,
                    },
                ),
            )
            await self.event_bus.publish_analysis_event(analysis_completed_event)

            logger.info(f"Analysis {analysis_id} completed successfully in {execution_time:.2f}s")

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()

            # Publish analysis failed event
            analysis_failed_event = (
                AnalysisEvent.failed(
                    analysis_id=analysis_id,
                    error_message=str(e),
                    error_details={
                        "source_agent": "AnalyserWorker",
                        "source_results_path": str(results_path),
                        "strategies_executed": strategies,
                        "duration_seconds": execution_time,
                    },
                ),
            )
            await self.event_bus.publish_analysis_event(analysis_failed_event)

            logger.error(f"Analysis {analysis_id} failed: {e}")
            raise ProcessingError(
                f"Analysis execution failed: {str(e)}", details={"analysis_id": analysis_id, "strategies": strategies}
            )

    def _get_strategies_for_study_type(self, study_type: str | None) -> List[str]:
        """Determine appropriate analysis strategies based on study type.

        Args:
            study_type: Type of study that was completed

        Returns:
            List of strategy names to execute,
        """
        if study_type == "parametric":
            return ["sensitivity", "technical_kpi", "economic"]
        elif study_type == "optimization":
            return ["technical_kpi", "economic"]
        elif study_type == "fidelity":
            return ["technical_kpi"]
        else:
            # Default strategies for unknown or generic studies
            return self.auto_analysis_strategies

    def _generate_analysis_output_path(self, results_path: str, analysis_id: str) -> str:
        """Generate output path for analysis results.

        Args:
            results_path: Original simulation results path
            analysis_id: Analysis identifier

        Returns:
            Path for analysis output file,
        """
        results_file = Path(results_path)
        output_dir = results_file.parent / "analysis"
        output_dir.mkdir(exist_ok=True)
        output_filename = f"{results_file.stem}_analysis_{analysis_id}.json"
        return str(output_dir / output_filename)

    async def process_analysis_request_async(
        self, results_path: str, strategies: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Manually trigger analysis processing.

        Args:
            results_path: Path to simulation results,
            strategies: Optional list of strategies (uses defaults if None),
            metadata: Optional metadata for analysis

        Returns:
            Analysis ID for tracking

        Raises:
            ProcessingError: If analysis fails,
        """
        analysis_id = (f"manual_{uuid.uuid4().hex[:8]}",)
        strategies = strategies or self.auto_analysis_strategies

        await self._execute_analysis_async(
            analysis_id=analysis_id,
            results_path=results_path,
            strategies=strategies,
            metadata=metadata or {"trigger": "manual_request"},
        )

        return analysis_id

    def get_status(self) -> Dict[str, Any]:
        """Get current worker status.

        Returns:
            Dictionary with worker status information,
        """
        return (
            {
                "is_running": self.is_running,
                "subscriptions": len(self._subscription_ids),
                "auto_strategies": self.auto_analysis_strategies,
                "registered_strategies": list(self.analyser_service.strategies.keys()),
            },
        )


class AnalyserWorkerPool:
    """
    Pool manager for multiple Analyser workers.,

    Provides load balancing and resilience for analysis processing.,
    """

    def __init__(self, pool_size: int = 3, event_bus: EcoSystemiserEventBus | None = None) -> None:
        """Initialize worker pool.

        Args:
            pool_size: Number of workers in the pool
            event_bus: Shared EcoSystemiser event bus instance,
        """
        self.pool_size = pool_size
        self.event_bus = event_bus or get_ecosystemiser_event_bus()
        self.workers: List[AnalyserWorker] = []
        self.current_worker_index = 0

    async def start_async(self) -> None:
        """Start all workers in the pool."""
        logger.info(f"Starting Analyser Worker Pool with {self.pool_size} workers")

        for i in range(self.pool_size):
            worker = AnalyserWorker(
                event_bus=self.event_bus, auto_analysis_strategies=["technical_kpi", "economic", "sensitivity"]
            )
            await worker.start_async()
            self.workers.append(worker)

        logger.info("Analyser Worker Pool started successfully")

    async def stop_async(self) -> None:
        """Stop all workers in the pool."""
        logger.info("Stopping Analyser Worker Pool")

        for worker in self.workers:
            await worker.stop_async()

        self.workers.clear()
        logger.info("Analyser Worker Pool stopped")

    def get_next_worker(self) -> AnalyserWorker:
        """Get next worker using round-robin load balancing.

        Returns:
            Next available worker,
        """
        if not self.workers:
            raise RuntimeError("No workers available in pool")
        worker = self.workers[self.current_worker_index]
        self.current_worker_index = (self.current_worker_index + 1) % len(self.workers)
        return worker

    async def process_analysis_request_async(
        self, results_path: str, strategies: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Process analysis request using next available worker.

        Args:
            results_path: Path to simulation results,
            strategies: Optional list of strategies,
            metadata: Optional metadata

        Returns:
            Analysis ID for tracking,
        """
        worker = self.get_next_worker()
        return await worker.process_analysis_request_async(results_path, strategies, metadata)

    def get_pool_status(self) -> Dict[str, Any]:
        """Get status of all workers in pool.

        Returns:
            Dictionary with pool status information,
        """
        return {
            "pool_size": self.pool_size,
            "active_workers": len([w for w in self.workers if w.is_running]),
            "workers": [w.get_status() for w in self.workers],
        }
