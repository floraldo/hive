"""
Fleet Orchestrator - Coordinating Task Queue, Worker Pool, and QA Workers

Central orchestrator that:
- Manages task queue and worker pool
- Auto-scales workers based on queue depth
- Monitors worker health and restarts failed workers
- Routes tasks to available workers
- Tracks performance metrics
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from hive_config.paths import PROJECT_ROOT
from hive_logging import get_logger
from hive_orchestration.events import get_async_event_bus
from hive_orchestration.models.task import Task
from hive_orchestrator.task_queue import TaskPriority, TaskQueueManager
from hive_orchestrator.worker_pool import WorkerPoolManager

logger = get_logger(__name__)


class FleetOrchestrator:
    """
    Central orchestrator for autonomous QA worker fleet.

    Coordinates:
    - Task queue management
    - Worker pool scaling
    - Worker health monitoring
    - Task routing and assignment
    - Performance metrics
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        min_workers: int = 1,
        max_workers: int = 10,
        target_queue_per_worker: int = 5,
        health_check_interval: float = 10.0,
        scaling_check_interval: float = 30.0,
        cleanup_interval: float = 3600.0,
    ):
        """
        Initialize fleet orchestrator.

        Args:
            db_path: Database path for persistence
            min_workers: Minimum workers to maintain
            max_workers: Maximum workers allowed
            target_queue_per_worker: Target tasks per worker
            health_check_interval: Worker health check interval (seconds)
            scaling_check_interval: Scaling decision interval (seconds)
            cleanup_interval: Old task cleanup interval (seconds)
        """
        self.db_path = db_path or (PROJECT_ROOT / "hive.db")

        # Core components
        self.task_queue = TaskQueueManager(db_path=self.db_path)
        self.worker_pool = WorkerPoolManager(
            min_workers=min_workers,
            max_workers=max_workers,
            target_queue_per_worker=target_queue_per_worker,
        )

        # Configuration
        self.health_check_interval = health_check_interval
        self.scaling_check_interval = scaling_check_interval
        self.cleanup_interval = cleanup_interval

        # Event bus
        self.event_bus = get_async_event_bus()

        # Background tasks
        self._background_tasks: list[asyncio.Task] = []
        self._running = False

        logger.info("FleetOrchestrator initialized")
        logger.info(f"  Database: {self.db_path}")
        logger.info(f"  Worker pool: {min_workers}-{max_workers} workers")
        logger.info(f"  Target queue per worker: {target_queue_per_worker}")

    async def submit_task(
        self,
        task: Task,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_seconds: int = 60,
    ) -> str:
        """
        Submit task to queue for processing.

        Args:
            task: Task to submit
            priority: Task priority level
            timeout_seconds: Task execution timeout

        Returns:
            Task ID
        """
        task_id = await self.task_queue.enqueue(
            task=task, priority=priority, timeout_seconds=timeout_seconds
        )

        logger.info(
            f"Task {task_id} submitted with {priority} priority "
            f"(queue depth: {self.task_queue.queue_depth})"
        )

        return task_id

    async def assign_task_to_worker(self, worker_id: str) -> dict[str, Any] | None:
        """
        Assign next task from queue to worker.

        Args:
            worker_id: Worker requesting task

        Returns:
            Task data or None if queue is empty
        """
        # Dequeue task
        queued_task = await self.task_queue.dequeue(worker_id)

        if queued_task is None:
            return None

        # Mark as in progress
        await self.task_queue.mark_in_progress(queued_task.task.id)

        # Update worker status
        await self.worker_pool.update_heartbeat(
            worker_id=worker_id,
            status="working",
            tasks_completed=0,  # Will be updated on completion
            violations_fixed=0,
            escalations=0,
            current_task=queued_task.task.id,
        )

        logger.info(f"Task {queued_task.task.id} assigned to worker {worker_id}")

        return {
            "task_id": queued_task.task.id,
            "task": queued_task.task,
            "priority": queued_task.priority,
            "timeout_seconds": queued_task.timeout_seconds,
        }

    async def complete_task(
        self, task_id: str, worker_id: str, result: dict[str, Any]
    ) -> bool:
        """
        Mark task as completed by worker.

        Args:
            task_id: Task ID
            worker_id: Worker that completed task
            result: Task execution result

        Returns:
            True if task marked completed, False otherwise
        """
        success = await self.task_queue.mark_completed(task_id, result)

        if success:
            # Update worker metrics
            status = result.get("status", "success")
            violations_fixed = result.get("violations_fixed", 0)

            # Get current worker info to increment metrics
            metrics = await self.worker_pool.get_metrics()
            worker_details = metrics.get("worker_details", {}).get(worker_id, {})

            await self.worker_pool.update_heartbeat(
                worker_id=worker_id,
                status="idle",
                tasks_completed=worker_details.get("tasks_completed", 0) + 1,
                violations_fixed=worker_details.get("violations_fixed", 0)
                + violations_fixed,
                escalations=worker_details.get("escalations", 0)
                + (1 if status == "escalated" else 0),
                current_task=None,
            )

            logger.info(f"Task {task_id} completed by worker {worker_id}")

        return success

    async def fail_task(
        self, task_id: str, worker_id: str, error: str, retry: bool = True
    ) -> bool:
        """
        Mark task as failed and optionally retry.

        Args:
            task_id: Task ID
            worker_id: Worker that failed task
            error: Error message
            retry: Whether to retry the task

        Returns:
            True if task marked failed, False otherwise
        """
        success = await self.task_queue.mark_failed(task_id, error, retry)

        if success:
            # Update worker status
            await self.worker_pool.update_heartbeat(
                worker_id=worker_id,
                status="idle",
                tasks_completed=0,  # Don't increment on failure
                violations_fixed=0,
                escalations=0,
                current_task=None,
            )

            logger.warning(f"Task {task_id} failed by worker {worker_id}: {error}")

        return success

    async def _health_check_loop(self) -> None:
        """Background loop for worker health monitoring."""
        logger.info("Health check loop started")

        try:
            while self._running:
                # Check worker health
                offline_workers = await self.worker_pool.check_worker_health()

                # Attempt to restart offline workers
                for worker_id in offline_workers:
                    logger.warning(f"Worker {worker_id} offline, attempting restart...")
                    await self.worker_pool.restart_worker(worker_id)

                # Check for timed out tasks
                timed_out_tasks = await self.task_queue.check_timeouts()

                if timed_out_tasks:
                    logger.warning(f"{len(timed_out_tasks)} tasks timed out")

                await asyncio.sleep(self.health_check_interval)

        except asyncio.CancelledError:
            logger.info("Health check loop stopped")
        except Exception as e:
            logger.error(f"Health check loop error: {e}")

    async def _scaling_loop(self) -> None:
        """Background loop for worker pool auto-scaling."""
        logger.info("Scaling loop started")

        try:
            while self._running:
                # Get current queue depth
                queue_depth = self.task_queue.queue_depth

                # Calculate scaling decision
                action, count = await self.worker_pool.calculate_scaling_decision(
                    queue_depth
                )

                # Apply scaling decision
                if action != "no_change":
                    scaled = await self.worker_pool.apply_scaling_decision(
                        action, count, worker_type="qa"
                    )

                    logger.info(
                        f"Auto-scaling: {action} {scaled} workers "
                        f"(queue depth: {queue_depth}, "
                        f"pool size: {self.worker_pool.pool_size})"
                    )

                await asyncio.sleep(self.scaling_check_interval)

        except asyncio.CancelledError:
            logger.info("Scaling loop stopped")
        except Exception as e:
            logger.error(f"Scaling loop error: {e}")

    async def _cleanup_loop(self) -> None:
        """Background loop for old task cleanup."""
        logger.info("Cleanup loop started")

        try:
            while self._running:
                # Clean up old tasks (>24h)
                cleaned = await self.task_queue.cleanup_old_tasks(max_age_hours=24)

                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} old tasks")

                await asyncio.sleep(self.cleanup_interval)

        except asyncio.CancelledError:
            logger.info("Cleanup loop stopped")
        except Exception as e:
            logger.error(f"Cleanup loop error: {e}")

    async def start(self) -> None:
        """Start orchestrator and background loops."""
        if self._running:
            logger.warning("Orchestrator already running")
            return

        self._running = True

        # Start background loops
        self._background_tasks = [
            asyncio.create_task(self._health_check_loop()),
            asyncio.create_task(self._scaling_loop()),
            asyncio.create_task(self._cleanup_loop()),
        ]

        logger.info("FleetOrchestrator started")
        logger.info("  Background tasks:")
        logger.info(f"    - Health check (every {self.health_check_interval}s)")
        logger.info(f"    - Auto-scaling (every {self.scaling_check_interval}s)")
        logger.info(f"    - Cleanup (every {self.cleanup_interval}s)")

    async def stop(self) -> None:
        """Stop orchestrator and background loops."""
        if not self._running:
            return

        self._running = False

        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks = []

        logger.info("FleetOrchestrator stopped")

    async def get_status(self) -> dict[str, Any]:
        """
        Get orchestrator status and metrics.

        Returns:
            Status dictionary with queue and pool metrics
        """
        queue_metrics = await self.task_queue.get_metrics()
        pool_metrics = await self.worker_pool.get_metrics()

        return {
            "running": self._running,
            "queue": queue_metrics,
            "pool": pool_metrics,
            "config": {
                "min_workers": self.worker_pool.min_workers,
                "max_workers": self.worker_pool.max_workers,
                "target_queue_per_worker": self.worker_pool.target_queue_per_worker,
                "health_check_interval": self.health_check_interval,
                "scaling_check_interval": self.scaling_check_interval,
            },
        }


# Global orchestrator instance
_orchestrator_instance: FleetOrchestrator | None = None


def get_orchestrator(
    db_path: Path | str | None = None,
    min_workers: int = 1,
    max_workers: int = 10,
) -> FleetOrchestrator:
    """
    Get or create global orchestrator instance.

    Args:
        db_path: Database path
        min_workers: Minimum workers
        max_workers: Maximum workers

    Returns:
        FleetOrchestrator instance
    """
    global _orchestrator_instance

    if _orchestrator_instance is None:
        _orchestrator_instance = FleetOrchestrator(
            db_path=db_path, min_workers=min_workers, max_workers=max_workers
        )

    return _orchestrator_instance


async def main():
    """CLI entry point for orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(description="Fleet Orchestrator")
    parser.add_argument(
        "--db-path", type=Path, default=None, help="Database path (default: PROJECT_ROOT/hive.db)"
    )
    parser.add_argument("--min-workers", type=int, default=1, help="Minimum workers")
    parser.add_argument("--max-workers", type=int, default=10, help="Maximum workers")

    args = parser.parse_args()

    # Create and start orchestrator
    orchestrator = FleetOrchestrator(
        db_path=args.db_path, min_workers=args.min_workers, max_workers=args.max_workers
    )

    await orchestrator.start()

    try:
        # Run until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
