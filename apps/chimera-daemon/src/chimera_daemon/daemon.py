"""Chimera Daemon - Autonomous Workflow Execution Service.

Background service that continuously processes Chimera workflow tasks from the queue.
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime
from typing import Any

from hive_config import HiveConfig, create_config_from_sources
from hive_logging import get_logger
from hive_orchestration import (
    Task,
    create_chimera_task,
)
from hive_orchestration import (
    TaskStatus as OrchestratorTaskStatus,
)
from hive_orchestration.workflows.chimera_agents import create_chimera_agents_registry

from .executor_pool import ExecutorPool
from .task_queue import TaskQueue

logger = get_logger(__name__)


class ChimeraDaemon:
    """Background daemon for autonomous Chimera workflow execution.

    Continuously polls task queue and executes workflows autonomously.

    Example:
        daemon = ChimeraDaemon()
        await daemon.start()  # Runs until stopped (Ctrl+C or signal)
    """

    def __init__(
        self,
        config: HiveConfig | None = None,
        poll_interval: float = 1.0,
        max_concurrent: int = 5,
    ):
        """Initialize Chimera daemon.

        Args:
            config: Hive configuration (uses default if not provided)
            poll_interval: Queue polling interval in seconds
            max_concurrent: Maximum number of concurrent workflows
        """
        self._config = config or create_config_from_sources()
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self.running = False
        self.logger = logger

        # Task queue
        db_path = self._config.database.path.parent / "chimera_tasks.db"
        self.task_queue = TaskQueue(db_path=db_path)

        # Executor pool
        self.agents_registry = create_chimera_agents_registry()
        self.executor_pool = ExecutorPool(
            max_concurrent=max_concurrent,
            agents_registry=self.agents_registry,
            task_queue=self.task_queue,
        )

        # Metrics
        self.started_at: datetime | None = None

        # Signal handlers
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Set up graceful shutdown on SIGINT/SIGTERM."""

        def handle_signal(signum: int, frame: Any) -> None:  # noqa: ARG001
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    async def start(self) -> None:
        """Start daemon processing loop.

        Runs continuously until stopped via signal (SIGINT/SIGTERM).
        """
        await self.task_queue.initialize()
        await self.executor_pool.start()

        self.running = True
        self.started_at = datetime.now()
        self.logger.info("Chimera daemon started (Layer 2 - Parallel Execution)")
        self.logger.info(f"Polling interval: {self.poll_interval}s")
        self.logger.info(f"Max concurrent workflows: {self.max_concurrent}")

        try:
            while self.running:
                await self._process_next_task()
                await asyncio.sleep(self.poll_interval)

        except Exception as e:
            self.logger.error(f"Daemon crashed: {e}", exc_info=True)
            raise

        finally:
            self.logger.info("Chimera daemon stopping...")
            await self.executor_pool.stop()
            self.logger.info("Chimera daemon stopped")
            self._log_final_metrics()

    async def _process_next_task(self) -> None:
        """Process next task from queue."""
        # Check if pool has available capacity
        if self.executor_pool.available_slots == 0:
            return  # Pool full, wait for next polling interval

        # Get next task from queue
        queued_task = await self.task_queue.get_next_task()

        if not queued_task:
            return  # Queue empty, continue polling

        self.logger.info(
            f"Claiming task: {queued_task.task_id} "
            f"(pool: {self.executor_pool.active_count + 1}/{self.max_concurrent})"
        )

        try:
            # Mark as running immediately to prevent race conditions
            await self.task_queue.mark_running(queued_task.task_id)

            # Create Chimera task
            task_data = create_chimera_task(
                feature_description=queued_task.feature_description,
                target_url=queued_task.target_url,
                staging_url=queued_task.staging_url or queued_task.target_url,
                priority=queued_task.priority,
            )

            # Create Task object
            task = Task(
                id=queued_task.task_id,
                title=task_data["title"],
                description=task_data["description"],
                task_type=task_data["task_type"],
                priority=task_data["priority"],
                workflow=task_data["workflow"],
                payload=task_data["payload"],
                status=OrchestratorTaskStatus.QUEUED,
            )

            # Submit to executor pool (non-blocking)
            await self.executor_pool.submit_workflow(task)

        except Exception as e:
            self.logger.error(f"Task submission failed: {queued_task.task_id} - {e}", exc_info=True)
            await self.task_queue.mark_failed(
                task_id=queued_task.task_id,
                workflow_state=None,
                error=str(e),
            )

    def _log_final_metrics(self) -> None:
        """Log final metrics on shutdown."""
        uptime = (datetime.now() - self.started_at).total_seconds() if self.started_at else 0

        self.logger.info("=== Chimera Daemon Metrics ===")
        self.logger.info(f"Uptime: {uptime:.0f}s")

        # Pool metrics (delegated to ExecutorPool)
        pool_metrics = self.executor_pool.get_metrics()
        self.logger.info(f"Pool Size: {pool_metrics['pool_size']}")
        self.logger.info(f"Tasks Processed: {pool_metrics['total_workflows_processed']}")
        self.logger.info(f"Tasks Succeeded: {pool_metrics['total_workflows_succeeded']}")
        self.logger.info(f"Tasks Failed: {pool_metrics['total_workflows_failed']}")
        self.logger.info(f"Success Rate: {pool_metrics['success_rate']:.1f}%")
        self.logger.info(f"Avg Duration: {pool_metrics['avg_workflow_duration_ms']:.0f}ms")


__all__ = ["ChimeraDaemon"]
