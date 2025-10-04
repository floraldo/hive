"""Worker Pool Manager - Auto-Scaling Worker Fleet

Manages worker pool with:
- Dynamic worker scaling based on queue depth
- Worker health monitoring and auto-restart
- Load balancing across workers
- Worker lifecycle management
- Performance tracking
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from hive_logging import get_logger
from hive_orchestration.events import WorkerRegistration, get_async_event_bus

logger = get_logger(__name__)


class WorkerStatus(str, Enum):
    """Worker status states"""

    STARTING = "starting"
    IDLE = "idle"
    WORKING = "working"
    ERROR = "error"
    OFFLINE = "offline"
    STOPPING = "stopping"


@dataclass
class WorkerInfo:
    """Worker information and metrics"""

    worker_id: str
    worker_type: str  # 'qa' | 'golden_rules' | 'test' | 'security'
    status: WorkerStatus = WorkerStatus.STARTING
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(UTC))
    tasks_completed: int = 0
    violations_fixed: int = 0
    escalations: int = 0
    current_task: str | None = None
    restart_count: int = 0
    max_restarts: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def uptime_seconds(self) -> float:
        """Worker uptime in seconds"""
        return (datetime.now(UTC) - self.registered_at).total_seconds()

    @property
    def is_healthy(self) -> bool:
        """Check if worker is healthy (recent heartbeat)"""
        heartbeat_age = (datetime.now(UTC) - self.last_heartbeat).total_seconds()
        return heartbeat_age < 30  # 30s heartbeat timeout

    @property
    def is_available(self) -> bool:
        """Check if worker is available for tasks"""
        return self.status == WorkerStatus.IDLE and self.is_healthy

    @property
    def can_restart(self) -> bool:
        """Check if worker can be restarted"""
        return self.restart_count < self.max_restarts


class WorkerPoolManager:
    """Auto-scaling worker pool with health monitoring.

    Features:
    - Dynamic scaling based on queue depth
    - Health monitoring with 30s heartbeat timeout
    - Automatic worker restart on failure
    - Load balancing across available workers
    - Performance metrics tracking
    """

    def __init__(
        self,
        min_workers: int = 1,
        max_workers: int = 10,
        target_queue_per_worker: int = 5,
        scale_up_threshold: float = 0.8,
        scale_down_threshold: float = 0.2,
    ):
        """Initialize worker pool manager.

        Args:
            min_workers: Minimum number of workers to maintain
            max_workers: Maximum number of workers allowed
            target_queue_per_worker: Target tasks per worker
            scale_up_threshold: Scale up when queue > threshold * capacity
            scale_down_threshold: Scale down when queue < threshold * capacity

        """
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.target_queue_per_worker = target_queue_per_worker
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold

        # Worker tracking
        self._workers: dict[str, WorkerInfo] = {}

        # Scaling metrics
        self._scale_up_count = 0
        self._scale_down_count = 0
        self._restart_count = 0

        # Event bus
        self.event_bus = get_async_event_bus()

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(
            f"WorkerPoolManager initialized (min={min_workers}, max={max_workers}, "
            f"target_queue_per_worker={target_queue_per_worker})",
        )

    async def register_worker(
        self, worker_id: str, worker_type: str, metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Register a new worker.

        Args:
            worker_id: Worker identifier
            worker_type: Type of worker
            metadata: Additional worker metadata

        Returns:
            True if registration successful, False otherwise

        """
        async with self._lock:
            if worker_id in self._workers:
                logger.warning(f"Worker {worker_id} already registered")
                return False

            worker_info = WorkerInfo(
                worker_id=worker_id, worker_type=worker_type, metadata=metadata or {},
            )

            self._workers[worker_id] = worker_info

            logger.info(
                f"Worker {worker_id} ({worker_type}) registered "
                f"(pool size: {len(self._workers)})",
            )

            # Emit registration event
            await self.event_bus.publish(
                WorkerRegistration(
                    worker_id=worker_id,
                    worker_type=worker_type,
                    payload={
                        "pool_size": len(self._workers),
                        "worker_type": worker_type,
                        "metadata": metadata or {},
                    },
                ),
            )

            return True

    async def update_heartbeat(
        self,
        worker_id: str,
        status: str,
        tasks_completed: int,
        violations_fixed: int,
        escalations: int,
        current_task: str | None = None,
    ) -> bool:
        """Update worker heartbeat and status.

        Args:
            worker_id: Worker identifier
            status: Worker status
            tasks_completed: Total tasks completed
            violations_fixed: Total violations fixed
            escalations: Total escalations
            current_task: Current task ID (if working)

        Returns:
            True if update successful, False otherwise

        """
        async with self._lock:
            if worker_id not in self._workers:
                logger.warning(f"Worker {worker_id} not registered")
                return False

            worker_info = self._workers[worker_id]
            worker_info.last_heartbeat = datetime.now(UTC)
            worker_info.status = WorkerStatus(status)
            worker_info.tasks_completed = tasks_completed
            worker_info.violations_fixed = violations_fixed
            worker_info.escalations = escalations
            worker_info.current_task = current_task

            return True

    async def mark_worker_offline(self, worker_id: str) -> bool:
        """Mark worker as offline.

        Args:
            worker_id: Worker identifier

        Returns:
            True if status updated, False otherwise

        """
        async with self._lock:
            if worker_id not in self._workers:
                return False

            self._workers[worker_id].status = WorkerStatus.OFFLINE
            logger.warning(f"Worker {worker_id} marked offline")
            return True

    async def remove_worker(self, worker_id: str) -> bool:
        """Remove worker from pool.

        Args:
            worker_id: Worker identifier

        Returns:
            True if worker removed, False otherwise

        """
        async with self._lock:
            if worker_id not in self._workers:
                return False

            del self._workers[worker_id]
            logger.info(
                f"Worker {worker_id} removed from pool (pool size: {len(self._workers)})",
            )
            return True

    async def get_available_worker(self, worker_type: str | None = None) -> str | None:
        """Get an available worker for task assignment.

        Args:
            worker_type: Optional worker type filter

        Returns:
            Worker ID or None if no workers available

        """
        async with self._lock:
            # Filter workers
            candidates = [
                w
                for w in self._workers.values()
                if w.is_available and (worker_type is None or w.worker_type == worker_type)
            ]

            if not candidates:
                return None

            # Load balance: pick worker with fewest tasks
            worker = min(candidates, key=lambda w: w.tasks_completed)
            worker.status = WorkerStatus.WORKING

            return worker.worker_id

    async def check_worker_health(self) -> list[str]:
        """Check health of all workers and mark unhealthy ones offline.

        Returns:
            List of worker IDs that became offline

        """
        offline_workers = []

        async with self._lock:
            for worker_id, worker_info in self._workers.items():
                if not worker_info.is_healthy and worker_info.status != WorkerStatus.OFFLINE:
                    worker_info.status = WorkerStatus.OFFLINE
                    offline_workers.append(worker_id)

                    logger.warning(
                        f"Worker {worker_id} marked offline due to missing heartbeat "
                        f"(last seen: {worker_info.last_heartbeat.isoformat()})",
                    )

        return offline_workers

    async def restart_worker(self, worker_id: str) -> bool:
        """Restart a failed worker (placeholder for actual restart logic).

        Args:
            worker_id: Worker identifier

        Returns:
            True if restart initiated, False otherwise

        """
        async with self._lock:
            if worker_id not in self._workers:
                return False

            worker_info = self._workers[worker_id]

            if not worker_info.can_restart:
                logger.error(
                    f"Worker {worker_id} cannot be restarted "
                    f"(max restarts {worker_info.max_restarts} reached)",
                )
                return False

            worker_info.restart_count += 1
            worker_info.status = WorkerStatus.STARTING
            self._restart_count += 1

            logger.info(
                f"Worker {worker_id} restart initiated "
                f"(attempt {worker_info.restart_count}/{worker_info.max_restarts})",
            )

            # TODO: Actual worker restart logic (spawn new process)
            # For now, just mark as starting - integration with CLI in Phase 2

            return True

    async def calculate_scaling_decision(self, queue_depth: int) -> tuple[str, int]:
        """Calculate if pool should scale up or down.

        Args:
            queue_depth: Current task queue depth

        Returns:
            Tuple of (action, count) where action is 'scale_up', 'scale_down', or 'no_change'

        """
        async with self._lock:
            current_workers = len([w for w in self._workers.values() if w.status != WorkerStatus.OFFLINE])

            if current_workers == 0:
                return ("scale_up", self.min_workers)

            # Calculate capacity and utilization
            capacity = current_workers * self.target_queue_per_worker
            utilization = queue_depth / capacity if capacity > 0 else 0

            # Scale up decision
            if utilization > self.scale_up_threshold and current_workers < self.max_workers:
                # Calculate how many workers needed
                needed_workers = (queue_depth // self.target_queue_per_worker) + 1
                scale_up_count = min(
                    needed_workers - current_workers, self.max_workers - current_workers,
                )
                return ("scale_up", scale_up_count)

            # Scale down decision
            if utilization < self.scale_down_threshold and current_workers > self.min_workers:
                # Calculate how many workers can be removed
                needed_workers = max(
                    (queue_depth // self.target_queue_per_worker) + 1, self.min_workers,
                )
                scale_down_count = min(current_workers - needed_workers, current_workers - self.min_workers)
                if scale_down_count > 0:
                    return ("scale_down", scale_down_count)

            return ("no_change", 0)

    async def apply_scaling_decision(
        self, action: str, count: int, worker_type: str = "qa",
    ) -> int:
        """Apply scaling decision (placeholder for actual scaling logic).

        Args:
            action: 'scale_up' or 'scale_down'
            count: Number of workers to add/remove
            worker_type: Type of worker to scale

        Returns:
            Number of workers actually scaled

        """
        async with self._lock:
            if action == "scale_up":
                self._scale_up_count += count
                logger.info(f"Scaling up: adding {count} {worker_type} workers")

                # TODO: Actual worker spawning logic (integration with CLI)
                # For now, just log the decision

                return count

            if action == "scale_down":
                # Find idle workers to remove
                idle_workers = [
                    w for w in self._workers.values() if w.status == WorkerStatus.IDLE
                ]

                removed = 0
                for worker in idle_workers[:count]:
                    worker.status = WorkerStatus.STOPPING
                    removed += 1

                    logger.info(f"Scaling down: stopping worker {worker.worker_id}")

                    # TODO: Actual worker shutdown logic
                    # For now, just mark as stopping

                self._scale_down_count += removed
                return removed

            return 0

    @property
    def pool_size(self) -> int:
        """Total number of workers in pool"""
        return len(self._workers)

    @property
    def active_workers(self) -> int:
        """Number of active (non-offline) workers"""
        return len([w for w in self._workers.values() if w.status != WorkerStatus.OFFLINE])

    @property
    def idle_workers(self) -> int:
        """Number of idle workers available for tasks"""
        return len([w for w in self._workers.values() if w.is_available])

    async def get_metrics(self) -> dict[str, Any]:
        """Get worker pool metrics.

        Returns:
            Pool metrics dictionary

        """
        async with self._lock:
            # Worker status distribution
            status_counts = {status.value: 0 for status in WorkerStatus}
            for worker in self._workers.values():
                status_counts[worker.status.value] += 1

            # Worker type distribution
            type_counts = {}
            for worker in self._workers.values():
                type_counts[worker.worker_type] = type_counts.get(worker.worker_type, 0) + 1

            # Performance metrics
            total_tasks = sum(w.tasks_completed for w in self._workers.values())
            total_violations_fixed = sum(w.violations_fixed for w in self._workers.values())
            total_escalations = sum(w.escalations for w in self._workers.values())

            # Calculate average uptime
            uptimes = [w.uptime_seconds for w in self._workers.values()]
            avg_uptime = sum(uptimes) / len(uptimes) if uptimes else 0

            return {
                "pool_size": self.pool_size,
                "active_workers": self.active_workers,
                "idle_workers": self.idle_workers,
                "status_distribution": status_counts,
                "type_distribution": type_counts,
                "total_tasks_completed": total_tasks,
                "total_violations_fixed": total_violations_fixed,
                "total_escalations": total_escalations,
                "scale_up_count": self._scale_up_count,
                "scale_down_count": self._scale_down_count,
                "restart_count": self._restart_count,
                "avg_uptime_seconds": avg_uptime,
                "worker_details": {
                    worker_id: {
                        "status": worker.status.value,
                        "type": worker.worker_type,
                        "tasks_completed": worker.tasks_completed,
                        "violations_fixed": worker.violations_fixed,
                        "escalations": worker.escalations,
                        "uptime_seconds": worker.uptime_seconds,
                        "is_healthy": worker.is_healthy,
                    }
                    for worker_id, worker in self._workers.items()
                },
            }
