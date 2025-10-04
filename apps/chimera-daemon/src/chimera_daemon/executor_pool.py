"""ExecutorPool - Parallel Workflow Execution Manager.

Manages concurrent execution of multiple Chimera workflows with resource limits.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from hive_logging import get_logger
from hive_orchestration import ChimeraExecutor, ChimeraPhase, Task

from .task_queue import TaskQueue

logger = get_logger(__name__)


class WorkflowMetrics:
    """Metrics for a single workflow execution."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.started_at = datetime.now()
        self.completed_at: datetime | None = None
        self.success: bool = False
        self.error: str | None = None

    @property
    def duration_ms(self) -> float:
        """Get execution duration in milliseconds."""
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds() * 1000


class ExecutorPool:
    """Pool of ChimeraExecutor workers for parallel workflow execution.

    Manages concurrent workflow execution with configurable limits and metrics.

    Example:
        pool = ExecutorPool(max_concurrent=5, agents_registry=agents, task_queue=queue)
        await pool.start()
        await pool.submit_workflow(task)
        await pool.stop()
    """

    def __init__(
        self,
        max_concurrent: int,
        agents_registry: dict[str, Any],
        task_queue: TaskQueue,
    ):
        """Initialize executor pool.

        Args:
            max_concurrent: Maximum number of concurrent workflows
            agents_registry: Registry of Chimera agents
            task_queue: Task queue for state management
        """
        self.max_concurrent = max_concurrent
        self.agents_registry = agents_registry
        self.task_queue = task_queue
        self.logger = logger

        # Concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._running = False

        # Metrics
        self._workflow_metrics: list[WorkflowMetrics] = []
        self.total_workflows_processed = 0
        self.total_workflows_succeeded = 0
        self.total_workflows_failed = 0

    async def start(self) -> None:
        """Start the executor pool."""
        self._running = True
        self.logger.info(f"ExecutorPool started (max_concurrent={self.max_concurrent})")

    async def stop(self) -> None:
        """Stop the executor pool and wait for active workflows to complete."""
        self._running = False
        self.logger.info(f"ExecutorPool stopping ({len(self._active_tasks)} active workflows)...")

        # Wait for all active workflows to complete
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)

        self.logger.info("ExecutorPool stopped")
        self._log_final_metrics()

    async def submit_workflow(self, task: Task) -> None:
        """Submit a task for workflow execution.

        Args:
            task: Chimera task to execute

        Note:
            This method returns immediately after starting the workflow.
            The workflow runs asynchronously in the background.
        """
        if not self._running:
            raise RuntimeError("ExecutorPool is not running")

        # Create background task for workflow execution
        workflow_task = asyncio.create_task(self._execute_workflow_with_semaphore(task))

        # Track active task
        self._active_tasks[task.id] = workflow_task

        # Add cleanup callback
        workflow_task.add_done_callback(lambda t: self._active_tasks.pop(task.id, None))

        self.logger.info(f"Workflow submitted: {task.id} ({self.active_count}/{self.max_concurrent} slots)")

    async def _execute_workflow_with_semaphore(self, task: Task) -> None:
        """Execute workflow with semaphore-based concurrency control.

        Args:
            task: Chimera task to execute
        """
        async with self._semaphore:
            await self._execute_workflow(task)

    async def _execute_workflow(self, task: Task) -> None:
        """Execute Chimera workflow for task.

        Args:
            task: Chimera task to execute
        """
        # Convert task.id to string for TaskQueue compatibility
        task_id_str = str(task.id)

        metrics = WorkflowMetrics(task.id)
        self._workflow_metrics.append(metrics)

        self.logger.info(f"Starting workflow execution: {task.id}")

        try:
            # Create executor instance for this workflow
            executor = ChimeraExecutor(agents_registry=self.agents_registry)

            # Execute workflow
            workflow = await executor.execute_workflow(task, max_iterations=10)

            # Store result
            workflow_state = workflow.model_dump()

            if workflow.current_phase == ChimeraPhase.COMPLETE:
                result = {
                    "status": "success",
                    "phase": workflow.current_phase.value,
                    "test_path": workflow.test_path,
                    "code_pr_id": workflow.code_pr_id,
                    "code_commit_sha": workflow.code_commit_sha,
                    "review_decision": workflow.review_decision,
                    "deployment_url": workflow.deployment_url,
                    "validation_status": workflow.validation_status,
                }

                await self.task_queue.mark_completed(
                    task_id=task_id_str,
                    workflow_state=workflow_state,
                    result=result,
                )

                metrics.success = True
                self.total_workflows_succeeded += 1
                self.total_workflows_processed += 1

                self.logger.info(f"Workflow completed successfully: {task.id}")

            else:
                error = f"Workflow incomplete: {workflow.current_phase.value}"
                metrics.error = error

                await self.task_queue.mark_failed(
                    task_id=task_id_str,
                    workflow_state=workflow_state,
                    error=error,
                )

                self.total_workflows_failed += 1
                self.total_workflows_processed += 1

                self.logger.warning(f"Workflow failed: {task.id} - {error}")

        except Exception as e:
            self.logger.error(f"Workflow execution error: {task.id} - {e}", exc_info=True)

            metrics.error = str(e)

            await self.task_queue.mark_failed(
                task_id=task_id_str,
                workflow_state=None,
                error=str(e),
            )

            self.total_workflows_failed += 1
            self.total_workflows_processed += 1

        finally:
            metrics.completed_at = datetime.now()

    @property
    def active_count(self) -> int:
        """Get number of currently active workflows."""
        return len(self._active_tasks)

    @property
    def available_slots(self) -> int:
        """Get number of available execution slots."""
        return self.max_concurrent - self.active_count

    @property
    def avg_workflow_duration_ms(self) -> float:
        """Get average workflow duration in milliseconds."""
        completed_metrics = [m for m in self._workflow_metrics if m.completed_at is not None]

        if not completed_metrics:
            return 0.0

        total_duration = sum(m.duration_ms for m in completed_metrics)
        return total_duration / len(completed_metrics)

    def get_metrics(self) -> dict[str, Any]:
        """Get pool metrics.

        Returns:
            Dictionary with pool metrics
        """
        return {
            "pool_size": self.max_concurrent,
            "active_workflows": self.active_count,
            "available_slots": self.available_slots,
            "total_workflows_processed": self.total_workflows_processed,
            "total_workflows_succeeded": self.total_workflows_succeeded,
            "total_workflows_failed": self.total_workflows_failed,
            "avg_workflow_duration_ms": self.avg_workflow_duration_ms,
            "success_rate": (
                (self.total_workflows_succeeded / self.total_workflows_processed * 100)
                if self.total_workflows_processed > 0
                else 0.0
            ),
        }

    def _log_final_metrics(self) -> None:
        """Log final metrics on shutdown."""
        metrics = self.get_metrics()

        self.logger.info("=== ExecutorPool Final Metrics ===")
        self.logger.info(f"Pool Size: {metrics['pool_size']}")
        self.logger.info(f"Total Processed: {metrics['total_workflows_processed']}")
        self.logger.info(f"Succeeded: {metrics['total_workflows_succeeded']}")
        self.logger.info(f"Failed: {metrics['total_workflows_failed']}")
        self.logger.info(f"Success Rate: {metrics['success_rate']:.1f}%")
        self.logger.info(f"Avg Duration: {metrics['avg_workflow_duration_ms']:.0f}ms")


__all__ = ["ExecutorPool", "WorkflowMetrics"]
