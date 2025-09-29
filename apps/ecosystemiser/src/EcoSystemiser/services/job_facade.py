"""Job Facade Service for decoupling service dependencies.

This service acts as an intermediary between high-level services (like StudyService)
and execution services (like SimulationService), preparing for future event-driven architecture.
"""
from __future__ import annotations


import json
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

from ecosystemiser.core.bus import get_ecosystemiser_event_bus
from ecosystemiser.core.events import SimulationEvent, StudyEvent
from hive_logging import get_logger
from pydantic import BaseModel, Field

logger = get_logger(__name__)


class JobStatus(Enum):
    """Status of a submitted job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class JobType(Enum):
    """Types of jobs that can be submitted."""

    SIMULATION = "simulation"
    ANALYSIS = "analysis"
    OPTIMIZATION = "optimization"
    MONTE_CARLO = "monte_carlo"


class JobRequest(BaseModel):
    """Request to submit a job for processing."""

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_type: JobType
    config: Dict[str, Any]
    correlation_id: str | None = None
    priority: int = 0  # Higher numbers = higher priority
    timeout_seconds: int | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JobResult(BaseModel):
    """Result from a completed job."""

    job_id: str
    job_type: JobType
    status: JobStatus
    result: Optional[Dict[str, Any]] = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_time_seconds: float | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JobFacade:
    """Facade service for managing job submission and execution.

    This service provides a synchronous interface for now, but is designed
    to easily transition to an asynchronous, event-driven model in the future.
    """

    def __init__(self, max_workers: int = 4) -> None:
        """Initialize the job facade service.

        Args:
            max_workers: Maximum number of concurrent workers for job execution
        """
        self.event_bus = get_ecosystemiser_event_bus()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: Dict[str, JobResult] = {}

        # Lazy imports to avoid circular dependencies
        self._simulation_service = None
        self._analyser_service = None

        logger.info(f"JobFacade initialized with {max_workers} workers")

    def submit_simulation_job(
        self
        config: Dict[str, Any]
        correlation_id: str | None = None
        timeout: int | None = None
        blocking: bool = True
    ) -> JobResult:
        """Submit a simulation job for execution.

        Args:
            config: Simulation configuration
            correlation_id: Optional correlation ID for tracking
            timeout: Optional timeout in seconds
            blocking: If True, wait for completion; if False, return immediately

        Returns:
            JobResult with simulation results or status
        """
        # Create job request
        request = JobRequest(
            job_type=JobType.SIMULATION, config=config, correlation_id=correlation_id, timeout_seconds=timeout
        )

        logger.info(f"Submitting simulation job {request.job_id}")

        # Publish job submitted event
        self.event_bus.publish(
            SimulationEvent(
                event_type="simulation_requested"
                data={"job_id": request.job_id, "correlation_id": correlation_id, "config": config}
            )
        )

        if blocking:
            # Execute synchronously (current implementation)
            return self._execute_simulation_sync(request)
        else:
            # Submit for async execution (future enhancement)
            future = self.executor.submit(self._execute_simulation_sync, request)

            # Return pending status immediately
            result = JobResult(
                job_id=request.job_id
                job_type=JobType.SIMULATION
                status=JobStatus.PENDING
                metadata={"future": future}
            )
            self._jobs[request.job_id] = result
            return result

    def _execute_simulation_sync(self, request: JobRequest) -> JobResult:
        """Execute a simulation job synchronously.

        Args:
            request: Job request to execute

        Returns:
            JobResult with simulation results
        """
        # Lazy import to avoid circular dependency
        if self._simulation_service is None:
            from ecosystemiser.services.simulation_service import (
                SimulationConfig
                SimulationResult
                SimulationService
            )

            self._simulation_service = SimulationService()

        started_at = datetime.now()

        try:
            # Update job status
            self._jobs[request.job_id] = JobResult(
                job_id=request.job_id, job_type=JobType.SIMULATION, status=JobStatus.RUNNING, started_at=started_at
            )

            # Execute simulation
            sim_config = SimulationConfig(**request.config)
            sim_result = self._simulation_service.run_simulation(sim_config)

            completed_at = datetime.now()
            execution_time = (completed_at - started_at).total_seconds()

            # Create success result
            result = JobResult(
                job_id=request.job_id
                job_type=JobType.SIMULATION
                status=JobStatus.COMPLETED
                result=sim_result.dict() if hasattr(sim_result, "dict") else sim_result
                started_at=started_at
                completed_at=completed_at
                execution_time_seconds=execution_time
            )

            # Publish completion event
            self.event_bus.publish(
                SimulationEvent(
                    event_type="simulation_completed"
                    data={
                        "job_id": request.job_id
                        "correlation_id": request.correlation_id
                        "status": "success"
                        "execution_time": execution_time
                    }
                )
            )

        except TimeoutError:
            result = JobResult(
                job_id=request.job_id
                job_type=JobType.SIMULATION
                status=JobStatus.TIMEOUT
                error="Job execution timed out"
                started_at=started_at
                completed_at=datetime.now()
            )

            # Publish timeout event
            self.event_bus.publish(
                SimulationEvent(
                    event_type="simulation_failed"
                    data={"job_id": request.job_id, "correlation_id": request.correlation_id, "error": "timeout"}
                )
            )

        except Exception as e:
            logger.exception(f"Job {request.job_id} failed with error")
            result = JobResult(
                job_id=request.job_id
                job_type=JobType.SIMULATION
                status=JobStatus.FAILED
                error=str(e)
                started_at=started_at
                completed_at=datetime.now()
            )

            # Publish failure event
            self.event_bus.publish(
                SimulationEvent(
                    event_type="simulation_failed"
                    data={"job_id": request.job_id, "correlation_id": request.correlation_id, "error": str(e)}
                )
            )

        # Store result
        self._jobs[request.job_id] = result
        return result

    def submit_analysis_job(
        self
        config: Dict[str, Any]
        correlation_id: str | None = None
        timeout: int | None = None
        blocking: bool = True
    ) -> JobResult:
        """Submit an analysis job for execution.

        Args:
            config: Analysis configuration
            correlation_id: Optional correlation ID for tracking
            timeout: Optional timeout in seconds
            blocking: If True, wait for completion; if False, return immediately

        Returns:
            JobResult with analysis results or status
        """
        # Create job request
        request = JobRequest(
            job_type=JobType.ANALYSIS, config=config, correlation_id=correlation_id, timeout_seconds=timeout
        )

        logger.info(f"Submitting analysis job {request.job_id}")

        if blocking:
            return self._execute_analysis_sync(request)
        else:
            # Future: Submit for async execution
            future = self.executor.submit(self._execute_analysis_sync, request)
            result = JobResult(
                job_id=request.job_id, job_type=JobType.ANALYSIS, status=JobStatus.PENDING, metadata={"future": future}
            )
            self._jobs[request.job_id] = result
            return result

    def _execute_analysis_sync(self, request: JobRequest) -> JobResult:
        """Execute an analysis job synchronously.

        Args:
            request: Job request to execute

        Returns:
            JobResult with analysis results
        """
        # Lazy import to avoid circular dependency
        if self._analyser_service is None:
            from ecosystemiser.analyser import AnalyserService

            self._analyser_service = AnalyserService()

        started_at = datetime.now()

        try:
            # Execute analysis
            analysis_result = self._analyser_service.analyze(**request.config)

            completed_at = datetime.now()
            execution_time = (completed_at - started_at).total_seconds()

            result = JobResult(
                job_id=request.job_id
                job_type=JobType.ANALYSIS
                status=JobStatus.COMPLETED
                result=analysis_result
                started_at=started_at
                completed_at=completed_at
                execution_time_seconds=execution_time
            )

        except Exception as e:
            logger.exception(f"Analysis job {request.job_id} failed")
            result = JobResult(
                job_id=request.job_id
                job_type=JobType.ANALYSIS
                status=JobStatus.FAILED
                error=str(e)
                started_at=started_at
                completed_at=datetime.now()
            )

        self._jobs[request.job_id] = result
        return result

    def get_job_status(self, job_id: str) -> JobResult | None:
        """Get the status of a submitted job.

        Args:
            job_id: ID of the job to check

        Returns:
            JobResult if found, None otherwise
        """
        return self._jobs.get(job_id)

    def wait_for_job(self, job_id: str, timeout: int | None = None) -> JobResult:
        """Wait for a job to complete.

        Args:
            job_id: ID of the job to wait for
            timeout: Optional timeout in seconds

        Returns:
            JobResult when job completes

        Raises:
            TimeoutError: If timeout is exceeded
            KeyError: If job ID not found
        """
        if job_id not in self._jobs:
            raise KeyError(f"Job {job_id} not found")

        job = self._jobs[job_id]

        # If job has a future (async execution), wait for it
        if "future" in job.metadata:
            future = job.metadata["future"]
            try:
                result = future.result(timeout=timeout)
                return result
            except TimeoutError:
                job.status = JobStatus.TIMEOUT
                job.error = "Job execution timed out"
                raise

        # Otherwise, job is already complete
        return job

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job.

        Args:
            job_id: ID of the job to cancel

        Returns:
            True if cancelled, False if not found or already complete
        """
        if job_id not in self._jobs:
            return False

        job = self._jobs[job_id]

        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            return False

        # Cancel future if exists
        if "future" in job.metadata:
            future = job.metadata["future"]
            cancelled = future.cancel()
            if cancelled:
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now()
                return True

        return False

    def submit_job(self, config: Dict[str, Any], job_type: JobType = JobType.SIMULATION) -> JobResult:
        """General job submission method.

        Args:
            config: Job configuration
            job_type: Type of job to submit

        Returns:
            JobResult with job results or status
        """
        if job_type == JobType.SIMULATION:
            return self.submit_simulation_job(config)
        elif job_type == JobType.ANALYSIS:
            return self.submit_analysis_job(config)
        else:
            raise ValueError(f"Unsupported job type: {job_type}")

    def get_job_result(self, job_id: str) -> JobResult | None:
        """Get the result of a completed job.

        Args:
            job_id: ID of the job

        Returns:
            JobResult if found and complete, None otherwise
        """
        job = self.get_job_status(job_id)
        if job and job.status == JobStatus.COMPLETED:
            return job
        return None

    def run_simulation(self, config) -> None:
        """Direct simulation execution for backward compatibility.

        Args:
            config: SimulationConfig object or dict

        Returns:
            SimulationResult
        """
        # Convert config to dict if needed
        if hasattr(config, "dict"):
            config_dict = config.dict()
        else:
            config_dict = config

        # Run simulation synchronously
        result = self.submit_simulation_job(config_dict, blocking=True)

        # Extract the actual simulation result
        if result.status == JobStatus.COMPLETED and result.result:
            # If result.result is a dict representation of SimulationResult, return it
            # For backward compatibility with StudyService
            from ecosystemiser.services.simulation_service import SimulationResult

            if isinstance(result.result, dict):
                # The dict should be compatible with SimulationResult
                return SimulationResult(**result.result)
            return result.result
        elif result.status == JobStatus.FAILED:
            raise RuntimeError(f"Simulation failed: {result.error}")
        else:
            raise RuntimeError(f"Unexpected job status: {result.status}")

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the job facade service.

        Args:
            wait: If True, wait for pending jobs to complete
        """
        logger.info("Shutting down JobFacade")
        self.executor.shutdown(wait=wait)
