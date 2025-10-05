"""Worker Monitoring - Health Tracking and Escalation.

Monitors both Chimera agents and CC workers, tracks health, and escalates
failures to HITL when needed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class QAWorkerMonitor:
    """Monitor all QA workers (Chimera + CC terminals).

    Responsibilities:
    - Track Chimera agent execution status
    - Monitor CC worker processes and health
    - Detect failures and timeouts
    - Escalate to HITL when workers fail
    - Publish health metrics to event bus

    Example:
        monitor = QAWorkerMonitor(chimera_executor, cc_spawner, db)
        await monitor.start()  # Background monitoring loop
    """

    def __init__(
        self,
        chimera_executor: Any | None = None,
        cc_spawner: Any | None = None,
        client: Any | None = None,
        heartbeat_interval: float = 30.0,
        worker_timeout: float = 300.0,
    ):
        """Initialize worker monitor.

        Args:
            chimera_executor: Chimera executor instance
            cc_spawner: CC worker spawner instance
            client: Orchestration client for worker registry
            heartbeat_interval: Heartbeat publishing interval (seconds)
            worker_timeout: Worker timeout threshold (seconds)
        """
        self.chimera_executor = chimera_executor
        self.cc_spawner = cc_spawner
        self.client = client
        self.heartbeat_interval = heartbeat_interval
        self.worker_timeout = worker_timeout
        self.running = False
        self.logger = logger

        # Event bus for health events (optional - will be initialized if needed)
        self.event_bus = None

        # Metrics
        self.total_escalations = 0
        self.total_failures_detected = 0

    async def start(self) -> None:
        """Start background monitoring loop."""
        self.running = True
        self.logger.info("Worker monitor started")

        try:
            while self.running:
                await self._monitor_cycle()
                await asyncio.sleep(self.heartbeat_interval)

        except Exception as e:
            self.logger.error(f"Monitor loop crashed: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop monitoring loop."""
        self.running = False
        self.logger.info("Worker monitor stopped")

    async def _monitor_cycle(self) -> None:
        """Single monitoring cycle.

        Checks:
        1. Chimera agent executor status
        2. CC worker process health
        3. Worker timeouts
        4. Publishes heartbeat events
        """
        # Monitor Chimera executor
        chimera_status = await self._check_chimera_status()

        # Monitor CC workers
        cc_worker_status = await self._check_cc_workers()

        # Publish heartbeat with combined status
        await self._publish_heartbeat(chimera_status, cc_worker_status)

    async def _check_chimera_status(self) -> dict[str, Any]:
        """Check Chimera executor status.

        Returns:
            Status dictionary with metrics
        """
        if not self.chimera_executor:
            return {"available": False, "reason": "Not initialized (Phase 2 pending)"}

        try:
            # TODO: Phase 2 - Get actual Chimera executor status
            # status = await self.chimera_executor.get_status()
            status = {
                "available": False,
                "active_workflows": 0,
                "completed_workflows": 0,
                "failed_workflows": 0,
            }

            return status

        except Exception as e:
            self.logger.error(f"Failed to check Chimera status: {e}", exc_info=True)
            return {"available": False, "error": str(e)}

    async def _check_cc_workers(self) -> dict[str, Any]:
        """Check CC worker processes health.

        Returns:
            Status dictionary with worker health
        """
        if not self.cc_spawner:
            return {"available": False, "reason": "Not initialized (Phase 3 pending)"}

        if not self.db:
            return {"available": False, "reason": "Database not available"}

        try:
            # Fetch all active CC workers from database
            workers = await self.db.fetch_workers(worker_type="cc-terminal", status="active")

            # Check each worker for timeout
            unhealthy_workers = []
            healthy_count = 0

            for worker in workers:
                if self._is_worker_unhealthy(worker):
                    unhealthy_workers.append(worker)
                    await self._handle_worker_failure(worker)
                else:
                    healthy_count += 1

            return {
                "available": True,
                "total_workers": len(workers),
                "healthy_workers": healthy_count,
                "unhealthy_workers": len(unhealthy_workers),
            }

        except Exception as e:
            self.logger.error(f"Failed to check CC workers: {e}", exc_info=True)
            return {"available": False, "error": str(e)}

    def _is_worker_unhealthy(self, worker: dict[str, Any]) -> bool:
        """Check if worker has exceeded timeout threshold.

        Args:
            worker: Worker dictionary from database

        Returns:
            True if worker is unhealthy (timeout, crashed, etc.)
        """
        # Check last heartbeat timestamp
        last_heartbeat = worker.get("last_heartbeat")
        if not last_heartbeat:
            return True  # No heartbeat ever = unhealthy

        # Parse timestamp
        try:
            if isinstance(last_heartbeat, str):
                last_heartbeat_dt = datetime.fromisoformat(last_heartbeat)
            else:
                last_heartbeat_dt = last_heartbeat

            # Check if timeout exceeded
            timeout_threshold = datetime.now() - timedelta(seconds=self.worker_timeout)

            if last_heartbeat_dt < timeout_threshold:
                self.logger.warning(
                    f"Worker {worker.get('id')} timed out "
                    f"(last heartbeat: {last_heartbeat_dt})"
                )
                return True

        except Exception as e:
            self.logger.error(f"Failed to parse heartbeat timestamp: {e}")
            return True

        return False

    async def _handle_worker_failure(self, worker: dict[str, Any]) -> None:
        """Handle worker failure by escalating to HITL.

        Args:
            worker: Failed worker dictionary
        """
        self.total_failures_detected += 1
        self.total_escalations += 1

        worker_id = worker.get("id", "unknown")
        task_id = worker.get("current_task_id", "unknown")

        self.logger.error(
            f"Worker failure detected: {worker_id} "
            f"(task: {task_id})"
        )

        # Publish escalation event
        escalation = EscalationEvent(
            task_id=task_id,
            worker_id=worker_id,
            payload={
                "reason": "Worker timeout/crash",
                "worker_status": worker.get("status", "unknown"),
                "last_heartbeat": worker.get("last_heartbeat"),
                "timeout_threshold_seconds": self.worker_timeout,
            },
        )

        try:
            await self.event_bus.publish("qa.escalation", escalation)
            self.logger.info(f"Escalation event published for worker: {worker_id}")

        except Exception as e:
            self.logger.error(f"Failed to publish escalation event: {e}", exc_info=True)

        # Mark worker as offline in database
        if self.db:
            try:
                await self.db.update_worker_status(
                    worker_id,
                    status="offline",
                    error_message="Worker timeout/crash detected by monitor",
                )
            except Exception as e:
                self.logger.error(f"Failed to update worker status: {e}", exc_info=True)

        # TODO: Phase 3 - Spawn interactive CC terminal for HITL review
        # if self.cc_spawner:
        #     await self.cc_spawner.spawn_interactive(
        #         task_id=task_id,
        #         escalation_reason=f"Worker {worker_id} failed/timed out"
        #     )

    async def _publish_heartbeat(
        self,
        chimera_status: dict[str, Any],
        cc_worker_status: dict[str, Any],
    ) -> None:
        """Publish worker monitor heartbeat.

        Args:
            chimera_status: Chimera executor status
            cc_worker_status: CC workers status
        """
        heartbeat = WorkerHeartbeat(
            worker_id="qa-agent-monitor",
            payload={
                "status": "active" if self.running else "offline",
                "chimera_executor": chimera_status,
                "cc_workers": cc_worker_status,
                "total_escalations": self.total_escalations,
                "total_failures_detected": self.total_failures_detected,
                "uptime_seconds": (datetime.now() - self._start_time).total_seconds()
                if hasattr(self, "_start_time")
                else 0,
            },
        )

        try:
            await self.event_bus.publish("qa.monitor.heartbeat", heartbeat)

        except Exception as e:
            self.logger.error(f"Failed to publish heartbeat: {e}", exc_info=True)

    def get_metrics(self) -> dict[str, Any]:
        """Get current monitoring metrics.

        Returns:
            Dictionary with monitoring metrics
        """
        return {
            "total_escalations": self.total_escalations,
            "total_failures_detected": self.total_failures_detected,
            "running": self.running,
        }


__all__ = ["QAWorkerMonitor"]
