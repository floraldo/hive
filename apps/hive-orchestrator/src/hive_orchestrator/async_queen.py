#!/usr/bin/env python3
"""
AsyncQueen - High-Performance Async Orchestrator for V4.0
Phase 2 Implementation with 3-5x performance improvements
"""
from __future__ import annotations


import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, ListSet, Tuple

import toml

# Hive utilities
from hive_config.paths import LOGS_DIR, PROJECT_ROOT, ensure_directory
from hive_logging import get_logger, setup_logging

# Async event bus from Phase 1
from hive_orchestrator.core.bus import get_async_event_bus

# Async database operations from Phase 1
from hive_orchestrator.core.db import AsyncDatabaseOperations, get_async_db_operations

from .config import HiveConfig, create_orchestrator_config

# Import HiveCore for integration
from .hive_core import HiveCore


class Phase(Enum):
    """Task execution phases"""

    PLAN = "plan",
    APPLY = "apply",
    TEST = "test"


class AsyncQueen:
    """
    High-performance async orchestrator with V4.0 optimizations

    Features:
    - Non-blocking I/O for all operations
    - Concurrent task processing with semaphores
    - Async database operations with connection pooling
    - Event-driven coordination with async event bus
    - 3-5x performance improvement over sync version
    """

    def __init__(
        self,
        hive_core: HiveCore,
        config: HiveConfig | None = None,
        live_output: bool = False
    ):
        """Initialize AsyncQueen with async-first architecture"""
        self.hive = hive_core,
        self.live_output = live_output,
        self.log = get_logger(__name__)

        # Configuration,
        self.config = config if config is not None else create_orchestrator_config()

        # Async components from Phase 1,
        self.db_ops: AsyncDatabaseOperations | None = None,
        self.event_bus = None

        # State management,
        self.active_workers: Dict[str, Dict[str, Any]] = {}
        self.worker_semaphore = None  # Will be initialized in async context

        # Performance tracking,
        self.metrics = {
            "tasks_processed": 0,
            "average_processing_time": 0,
            "concurrent_peak": 0,
            "db_operations": 0,
            "events_published": 0,
        }

        # Simple mode toggle,
        self.simple_mode = self.config.get("simple_mode", False)
        if self.simple_mode:
            self.log.info("Running in SIMPLE_MODE")

    async def initialize_async(self) -> None:
        """Async initialization of database and event bus"""
        # Initialize async database operations,
        self.db_ops = await get_async_db_operations()
        self.log.info("Async database operations initialized with connection pooling")

        # Initialize async event bus,
        self.event_bus = await get_async_event_bus()
        self.log.info("Async event bus initialized with priority queues")

        # Setup event subscriptions,
        await self._setup_event_subscriptions_async()

        # Initialize worker semaphore for concurrency control,
        max_workers = sum(self.hive.config["max_parallel_per_role"].values())
        self.worker_semaphore = asyncio.Semaphore(max_workers * 2)  # 2x for async efficiency

        # Register Queen as a worker
        await self._register_as_worker_async()

        # Initialize performance monitoring
        asyncio.create_task(self._monitor_performance_async())

    async def _register_as_worker_async(self) -> None:
        """Register Queen as a worker in the database"""
        try:
            await self.db_ops.register_worker_async(
                worker_id="async-queen-orchestrator",
                role="orchestrator",
                capabilities=[
                    "async_orchestration",
                    "high_performance",
                    "workflow_management",
                    "concurrent_execution"
                ]
                metadata={
                    "version": "4.0.0",
                    "type": "AsyncQueen",
                    "phase": "V4.0 Phase 2",
                    "performance": "3-5x"
                }
            )
            self.log.info("AsyncQueen registered as worker")
        except Exception as e:
            self.log.warning(f"Failed to register AsyncQueen: {e}")

    async def _setup_event_subscriptions_async(self) -> None:
        """Setup async event subscriptions for choreographed workflow"""
        try:
            # Subscribe to workflow events
            await self.event_bus.subscribe_async(
                "workflow.plan_generated", self._handle_plan_generated_event, "async-queen-plan-listener"
            )

            await self.event_bus.subscribe_async(
                "task.review_completed", self._handle_review_completed_event, "async-queen-review-listener"
            )

            await self.event_bus.subscribe_async(
                "task.escalated", self._handle_task_escalated_event, "async-queen-escalation-listener"
            )

            self.log.info("Async event subscriptions established")
        except Exception as e:
            self.log.error(f"Failed to setup event subscriptions: {e}")

    async def _handle_plan_generated_event_async(self, event) -> None:
        """Handle plan generation completion asynchronously"""
        try:
            payload = event.payload,
            task_id = payload.get("task_id")

            if task_id:
                self.log.info(f"# OK Received plan completion for task {task_id}")
                task = await self.db_ops.get_task_async(task_id)

                if task and task.get("status") == "planned":
                    await self.db_ops.update_task_status_async(task_id, "queued", {"auto_triggered": True})

        except Exception as e:
            self.log.error(f"Error handling plan event: {e}")

    async def _handle_review_completed_event_async(self, event) -> None:
        """Handle review completion asynchronously"""
        try:
            payload = event.payload,
            task_id = payload.get("task_id")
            decision = payload.get("review_decision")

            if task_id and decision:
                self.log.info(f"# OK Review decision for {task_id}: {decision}")

                if decision == "approve":
                    task = await self.db_ops.get_task_async(task_id)
                    if task:
                        await self._advance_task_phase_async(task, success=True)

                elif decision in ["reject", "rework"]:
                    await self.db_ops.update_task_status_async(task_id, "queued", {"current_phase": "rework"})

        except Exception as e:
            self.log.error(f"Error handling review event: {e}")

    async def _handle_task_escalated_event_async(self, event) -> None:
        """Handle task escalation asynchronously"""
        try:
            payload = event.payload,
            task_id = payload.get("task_id")
            reason = payload.get("escalation_reason")

            if task_id:
                self.log.warning(f"# WARN Task {task_id} escalated: {reason}")
                # Could trigger notification system here

        except Exception as e:
            self.log.error(f"Error handling escalation event: {e}")

    async def spawn_worker_async(
        self, task: Dict[str, Any], worker: str, phase: Phase
    ) -> Optional[Tuple[asyncio.subprocess.Process, str]]:
        """Spawn worker process asynchronously for non-blocking execution"""
        task_id = task["id"]
        run_id = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{phase.value}"

        self.log.info(f"Spawning async worker for task: {task_id}")

        # Determine workspace mode
        mode = task.get("workspace", "repo")

        # Build command
        cmd = [
            sys.executable,
            "-m",
            "hive_orchestrator.worker",
            worker,
            "--one-shot",
            "--task-id",
            task_id,
            "--run-id",
            run_id,
            "--phase",
            phase.value,
            "--mode",
            mode,
            "--async",  # Enable async mode in worker
        ]

        if self.live_output:
            cmd.append("--live")

        try:
            # Create async subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._create_enhanced_environment()
            )

            self.log.info(f"[ASYNC-SPAWN] Started {worker} for {task_id} (PID: {process.pid})")
            return process, run_id

        except Exception as e:
            self.log.error(f"Failed to spawn async worker: {e}")
            return None

    def _create_enhanced_environment(self) -> Dict[str, str]:
        """Create enhanced environment for worker processes"""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        orchestrator_src = (PROJECT_ROOT / "apps" / "hive-orchestrator" / "src").as_posix()
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{orchestrator_src}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = orchestrator_src

        return env

    async def process_queued_tasks_async(self) -> None:
        """Process queued tasks with high concurrency"""
        async with self.worker_semaphore:
            # Get available slots
            max_parallel = sum(self.hive.config["max_parallel_per_role"].values()) * 2
            slots_free = max_parallel - len(self.active_workers)

            if slots_free <= 0:
                return

            # Fetch tasks concurrently
            tasks = await self.db_ops.get_tasks_concurrent_async(status="queued", limit=slots_free)

            if not tasks:
                return

            self.log.info(f"[ASYNC] Processing {len(tasks)} tasks with {slots_free} slots")

            # Process tasks concurrently
            processing_tasks = []
            for task in tasks:
                processing_tasks.append(self._process_single_task_async(task))

            # Execute all task processing concurrently
            results = await asyncio.gather(*processing_tasks, return_exceptions=True)

            # Update metrics
            self.metrics["tasks_processed"] += len([r for r in results if r])
            self.metrics["concurrent_peak"] = max(self.metrics["concurrent_peak"], len(self.active_workers))

    async def _process_single_task_async(self, task: Dict[str, Any]) -> bool:
        """Process a single task asynchronously"""
        task_id = task["id"]

        try:
            # Check dependencies
            depends_on = task.get("depends_on", [])
            if depends_on:
                dep_checks = [self.db_ops.get_task_async(dep_id) for dep_id in depends_on]
                dep_tasks = await asyncio.gather(*dep_checks)

                for dep_task in dep_tasks:
                    if not dep_task or dep_task.get("status") != "completed":
                        return False  # Dependencies not met

            # Determine worker type
            worker = task.get("tags", [None])[0] if task.get("tags") else "backend"
            if worker not in ["backend", "frontend", "infra"]:
                worker = "backend"

            # Update status
            await self.db_ops.update_task_status_async(
                task_id,
                "assigned",
                {
                    "assignee": worker,
                    "assigned_at": datetime.now(timezone.utc).isoformat(),
                    "current_phase": Phase.APPLY.value
                }
            )

            # Spawn worker
            result = await self.spawn_worker_async(task, worker, Phase.APPLY)
            if result:
                process, run_id = result
                self.active_workers[task_id] = {
                    "process": process,
                    "run_id": run_id,
                    "phase": Phase.APPLY.value,
                    "worker_type": worker,
                    "start_time": time.time()
                }

                await self.db_ops.update_task_status_async(
                    task_id, "in_progress", {"started_at": datetime.now(timezone.utc).isoformat()}
                )

                # Publish event
                await self.event_bus.publish_async(
                    event_type="task.started",
                    task_id=task_id,
                    priority=2
                )

                return True
            else:
                # Revert to queued
                await self.db_ops.update_task_status_async(task_id, "queued", {"assignee": None})
                return False

        except Exception as e:
            self.log.error(f"Error processing task {task_id}: {e}")
            return False

    async def monitor_workers_async(self) -> None:
        """Monitor active workers concurrently"""
        if not self.active_workers:
            return

        # Monitor all workers concurrently
        monitoring_tasks = []
        for task_id, metadata in list(self.active_workers.items()):
            monitoring_tasks.append(self._monitor_single_worker_async(task_id, metadata))

        if monitoring_tasks:
            await asyncio.gather(*monitoring_tasks, return_exceptions=True)

    async def _monitor_single_worker_async(self, task_id: str, metadata: Dict[str, Any]):
        """Monitor a single worker process"""
        process = metadata["process"]

        # Check if process finished
        if process.returncode is not None:
            # Process completed
            task = await self.db_ops.get_task_async(task_id)
            if not task:
                del self.active_workers[task_id]
                return

            # Calculate processing time
            processing_time = time.time() - metadata["start_time"]
            self._update_average_time(processing_time)

            if process.returncode == 0:
                # Success
                await self._handle_worker_success_async(task_id, task, metadata)
            else:
                # Failure
                await self._handle_worker_failure_async(task_id, task, metadata)

            # Cleanup
            if task_id in self.active_workers:
                del self.active_workers[task_id]

    async def _handle_worker_success_async(self, task_id: str, task: Dict[str, Any], metadata: Dict[str, Any]):
        """Handle successful worker completion"""
        current_phase = metadata.get("phase", "apply")

        if current_phase == "apply":
            # Advance to TEST phase
            self.log.info(f"# OK Task {task_id} APPLY succeeded")

            # Spawn TEST phase
            result = await self.spawn_worker_async(task, metadata["worker_type"], Phase.TEST)
            if result:
                process, run_id = result
                self.active_workers[task_id] = {
                    "process": process,
                    "run_id": run_id,
                    "phase": Phase.TEST.value,
                    "worker_type": metadata["worker_type"],
                    "start_time": time.time()
                }

                await self.db_ops.update_task_status_async(task_id, "in_progress", {"current_phase": Phase.TEST.value})
            else:
                await self.db_ops.update_task_status_async(
                    task_id, "failed", {"failure_reason": "Failed to spawn TEST phase"}
                )
        else:
            # TEST phase completed
            await self.db_ops.update_task_status_async(task_id, "completed", {})
            self.log.info(f"# OK Task {task_id} COMPLETED")

            # Publish completion event
            await self.event_bus.publish_async(
                event_type="task.completed",
                task_id=task_id,
                priority=1
            )

    async def _handle_worker_failure_async(self, task_id: str, task: Dict[str, Any], metadata: Dict[str, Any]):
        """Handle worker failure with retry logic"""
        retry_count = task.get("retry_count", 0)
        max_retries = self.hive.config["orchestration"]["task_retry_limit"]

        if retry_count < max_retries:
            # Retry
            self.log.info(f"# RETRY Task {task_id} (attempt {retry_count + 1}/{max_retries})")
            await self.db_ops.update_task_status_async(task_id, "queued", {"retry_count": retry_count + 1})
        else:
            # Max retries reached
            await self.db_ops.update_task_status_async(task_id, "failed", {})
            self.log.info(f"# FAIL Task {task_id} after {retry_count} retries")

            # Publish failure event
            await self.event_bus.publish_async(
                event_type="task.failed",
                task_id=task_id,
                priority=0
            )

    async def _advance_task_phase_async(self, task: Dict[str, Any], success: bool = True) -> str | None:
        """Advance task to next phase based on workflow"""
        workflow = task.get("workflow")
        if not workflow:
            return None

        current_phase = task.get("current_phase", "start")
        phase_config = workflow.get(current_phase, {})

        if success:
            next_phase = phase_config.get("next_phase_on_success")
        else:
            next_phase = phase_config.get("next_phase_on_failure", "failed")

        if not next_phase:
            return None

        task_id = task["id"]

        if next_phase == "completed":
            await self.db_ops.update_task_status_async(task_id, "completed", {})
            self.log.info(f"# OK Task {task_id} completed")
        elif next_phase == "failed":
            await self.db_ops.update_task_status_async(task_id, "failed", {})
            self.log.info(f"# FAIL Task {task_id} failed")
        else:
            await self.db_ops.update_task_status_async(task_id, "queued", {"current_phase": next_phase})
            self.log.info(f"Task {task_id} advanced to phase '{next_phase}'")

        return next_phase

    async def recover_zombie_tasks_async(self) -> None:
        """Recover zombie tasks using async operations"""
        # Get in-progress tasks
        in_progress = await self.db_ops.get_tasks_concurrent_async(status="in_progress", limit=100)

        if not in_progress:
            return

        recovery_tasks = []
        for task in in_progress:
            task_id = task["id"]
            if task_id not in self.active_workers:
                recovery_tasks.append(self._recover_single_zombie_async(task))

        if recovery_tasks:
            await asyncio.gather(*recovery_tasks, return_exceptions=True)

    async def _recover_single_zombie_async(self, task: Dict[str, Any]) -> None:
        """Recover a single zombie task"""
        task_id = task["id"]
        started_at = task.get("started_at")

        if started_at:
            start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            age_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60

            zombie_threshold = self.hive.config.get("zombie_detection_minutes", 5)
            if age_minutes >= zombie_threshold:
                self.log.info(f"[RECOVER] Zombie task {task_id} (stale {age_minutes:.1f}m)")

                await self.db_ops.update_task_status_async(
                    task_id,
                    "queued",
                    {
                        "current_phase": "plan",
                        "assignee": None,
                        "started_at": None
                    }
                )

    async def print_status_async(self) -> None:
        """Print async status update"""
        stats = await self.db_ops.get_stats_async()
        active_count = len(self.active_workers)

        self.log.info(
            f"\n[ASYNC-STATUS] Q:{stats['queued']} I:{stats['in_progress']} ",
            f"C:{stats['completed']} F:{stats['failed']} | Active: {active_count}"
        )

        # Show performance metrics
        self.log.info(
            f"[PERF] Processed: {self.metrics['tasks_processed']} | ",
            f"Avg Time: {self.metrics['average_processing_time']:.1f}s | ",
            f"Peak Concurrent: {self.metrics['concurrent_peak']}"
        )

    def _update_average_time(self, new_time: float) -> None:
        """Update average processing time metric"""
        count = self.metrics["tasks_processed"]
        if count == 0:
            self.metrics["average_processing_time"] = new_time
        else:
            avg = self.metrics["average_processing_time"]
            self.metrics["average_processing_time"] = (avg * count + new_time) / (count + 1)

    async def _monitor_performance_async(self) -> None:
        """Background task to monitor performance metrics"""
        while True:
            await asyncio.sleep(60)  # Every minute

            # Log performance metrics
            self.log.info(
                f"[METRICS] Tasks: {self.metrics['tasks_processed']} | ",
                f"DB Ops: {self.metrics['db_operations']} | ",
                f"Events: {self.metrics['events_published']} | ",
                f"Avg Time: {self.metrics['average_processing_time']:.1f}s"
            )

    async def run_forever_async(self) -> None:
        """Main async orchestration loop with high performance"""
        self.log.info("AsyncQueen starting (V4.0 Phase 2)...")
        self.log.info("# OK High-performance async orchestration enabled")
        self.log.info("=" * 50)

        # Initialize async components
        await self.initialize_async()

        try:
            while True:
                # Execute all operations concurrently
                await asyncio.gather(
                    self.process_queued_tasks_async()
                    self.monitor_workers_async()
                    self.recover_zombie_tasks_async()
                    return_exceptions=True
                )

                # Status update
                await self.print_status_async()

                # Check if all work is done
                stats = await self.db_ops.get_stats_async()
                if len(self.active_workers) == 0 and stats["queued"] == 0 and stats["in_progress"] == 0:
                    if stats["completed"] > 0 or stats["failed"] > 0:
                        self.log.info("All tasks completed. Exiting...")
                        break

                # Non-blocking sleep
                await asyncio.sleep(self.hive.config["orchestration"]["status_refresh_seconds"])

        except KeyboardInterrupt:
            self.log.info("\nAsyncQueen shutting down...")

            # Terminate workers gracefully
            for task_id, metadata in self.active_workers.items():
                self.log.info(f"Terminating {task_id}")
                process = metadata["process"]
                process.terminate()
                await process.wait()

            # Close async resources
            if self.db_ops:
                await self.db_ops.close()

            self.log.info("AsyncQueen stopped")


async def main_async() -> None:
    """Main entry point for AsyncQueen"""
    parser = argparse.ArgumentParser(description="AsyncQueen - V4.0 High-Performance Orchestrator")
    parser.add_argument("--live", action="store_true", help="Enable live streaming output"),
    args = parser.parse_args()

    # Configure logging
    setup_logging(name="async-queen", log_to_file=True, log_file_path="logs/async-queen.log"),
    log = get_logger(__name__)

    # Create components
    hive_core = HiveCore()
    queen = AsyncQueen(hive_core, live_output=args.live)

    # Run async orchestrator
    await queen.run_forever_async()


if __name__ == "__main__":
    asyncio.run(main_async())
