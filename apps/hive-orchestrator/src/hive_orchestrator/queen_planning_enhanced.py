#!/usr/bin/env python3
"""
Enhanced Queen with Robust AI Planner Integration

Extends QueenLite with improved integration for AI Planner → Queen → Worker pipeline.
Provides reliable task handoff, status synchronization, and error recovery.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Hive logging system
from hive_logging import get_logger

from .core import db as hive_core_db
from .core.db import database_enhanced_optimized as db_enhanced
from .core.db.planning_integration import (
    async_planning_integration,
    planning_integration,
)
from .queen import QueenLite  # Import base QueenLite

logger = get_logger(__name__)


class QueenPlanningEnhanced(QueenLite):
    """
    Enhanced Queen with robust AI Planner integration.

    Extends QueenLite to provide:
    - Reliable planning queue monitoring
    - Enhanced subtask pickup with dependency resolution
    - Bidirectional status synchronization
    - Automatic plan execution triggering
    - Comprehensive error handling and recovery
    """

    def __init__(self, hive_core, live_output: bool = False):
        """Initialize enhanced Queen with planning integration"""
        super().__init__(hive_core, live_output)

        # Planning-specific configuration
        self.planning_poll_interval = 10  # seconds
        self.last_planning_check = 0
        self.planning_stats = {
            "plans_triggered": 0,
            "subtasks_completed": 0,
            "plans_completed": 0,
            "sync_errors": 0,
        }

        # Enhanced event subscriptions for planning workflow
        self._setup_planning_event_subscriptions()

        logger.info("Queen Planning Enhanced initialized")

    def _setup_planning_event_subscriptions(self):
        """Setup additional event subscriptions for planning integration"""
        try:
            # Subscribe to plan generation events from AI Planner
            self.event_bus.subscribe(
                "workflow.plan_generated",
                self._handle_plan_generated_enhanced,
                "queen-planning-enhanced",
            )

            # Subscribe to subtask completion events for plan progress updates
            self.event_bus.subscribe(
                "task.completed",
                self._handle_subtask_completion,
                "queen-planning-tracker",
            )

            # Subscribe to plan execution requests
            self.event_bus.subscribe(
                "workflow.execute_plan",
                self._handle_execute_plan_request,
                "queen-plan-executor",
            )

            logger.info("Enhanced planning event subscriptions established")

        except Exception as e:
            logger.error(f"Failed to setup enhanced planning event subscriptions: {e}")

    def _handle_plan_generated_enhanced(self, event):
        """Enhanced handler for plan generation events"""
        try:
            payload = event.payload
            task_id = payload.get("task_id")
            plan_id = payload.get("plan_id")
            plan_name = payload.get("plan_name")

            if plan_id:
                logger.info(
                    f"🎯 Enhanced: Received plan generation for {plan_id}: {plan_name}"
                )

                # Automatically trigger plan execution if it's approved or auto-approved
                plan_status = planning_integration.get_execution_plan_status(plan_id)
                if plan_status in ["generated", "approved"]:
                    success = planning_integration.trigger_plan_execution(plan_id)
                    if success:
                        self.planning_stats["plans_triggered"] += 1
                        logger.info(f"🚀 Auto-triggered execution for plan {plan_id}")
                    else:
                        logger.error(
                            f"❌ Failed to trigger execution for plan {plan_id}"
                        )

        except Exception as e:
            logger.error(f"Error in enhanced plan generated handler: {e}")

    def _handle_subtask_completion(self, event):
        """Handle subtask completion and sync status to parent plan"""
        try:
            payload = event.payload
            task_id = payload.get("task_id")

            if not task_id:
                return

            # Check if this is a planned subtask
            task = hive_core_db.get_task(task_id)
            if not task or task.get("task_type") != "planned_subtask":
                return

            # Sync status back to execution plan
            success = planning_integration.sync_subtask_status_to_plan(
                task_id, "completed"
            )
            if success:
                self.planning_stats["subtasks_completed"] += 1
                logger.debug(f"✅ Synced subtask completion: {task_id}")

                # Check if parent plan is now complete
                task_payload = task.get("payload", {})
                plan_id = task_payload.get("parent_plan_id")
                if plan_id:
                    completion_status = planning_integration.get_plan_completion_status(
                        plan_id
                    )
                    if completion_status.get("is_complete"):
                        self.planning_stats["plans_completed"] += 1
                        logger.info(
                            f"🎉 Plan {plan_id} completed! ({completion_status['completion_percentage']}%)"
                        )
            else:
                self.planning_stats["sync_errors"] += 1
                logger.warning(f"⚠️ Failed to sync subtask completion: {task_id}")

        except Exception as e:
            logger.error(f"Error handling subtask completion: {e}")
            self.planning_stats["sync_errors"] += 1

    def _handle_execute_plan_request(self, event):
        """Handle explicit plan execution requests"""
        try:
            payload = event.payload
            plan_id = payload.get("plan_id")

            if plan_id:
                logger.info(f"📋 Received execute plan request: {plan_id}")
                success = planning_integration.trigger_plan_execution(plan_id)
                if success:
                    self.planning_stats["plans_triggered"] += 1
                    logger.info(f"🚀 Executed plan {plan_id} on request")
                else:
                    logger.error(f"❌ Failed to execute plan {plan_id} on request")

        except Exception as e:
            logger.error(f"Error handling execute plan request: {e}")

    def process_queued_tasks_enhanced(self):
        """Enhanced task processing that includes robust AI Planner integration"""
        # Calculate available slots for parallel execution
        max_parallel = sum(self.hive.config["max_parallel_per_role"].values())
        slots_free = max_parallel - len(self.active_workers)

        if slots_free <= 0:
            return  # No capacity for new tasks

        # Get enhanced tasks including planned subtasks with dependency resolution
        try:
            # Use enhanced planning integration for better subtask pickup
            planned_subtasks = planning_integration.get_ready_planned_subtasks(
                limit=slots_free
            )

            # Get regular queued tasks
            regular_tasks = hive_core_db.get_queued_tasks(
                limit=max(0, slots_free - len(planned_subtasks))
            )

            # Combine and prioritize
            all_tasks = planned_subtasks + regular_tasks

            if not all_tasks:
                return

            # Log planning-specific information
            if planned_subtasks:
                logger.info(
                    f"[AI-PLANNER] Found {len(planned_subtasks)} ready planned subtasks"
                )
                for task in planned_subtasks[:3]:  # Log first 3 for visibility
                    plan_ctx = task.get("planner_context", {})
                    logger.info(
                        f"  📋 {task['id']}: {task['title']} (phase: {plan_ctx.get('workflow_phase', 'unknown')})"
                    )

            logger.info(
                f"[ENHANCED] Processing {len(all_tasks)} tasks ({len(planned_subtasks)} planned + {len(regular_tasks)} regular)"
            )

            # Process tasks with enhanced planning awareness
            self._process_task_list_enhanced(all_tasks, slots_free)

        except Exception as e:
            logger.error(f"Error in enhanced task processing: {e}")
            # Fall back to regular processing
            super().process_queued_tasks()

    def _process_task_list_enhanced(self, tasks: List[Dict[str, Any]], slots_free: int):
        """Process task list with enhanced planning integration"""
        # Count active workers per role
        active_per_role = {"backend": 0, "frontend": 0, "infra": 0}
        for metadata in self.active_workers.values():
            worker_type = metadata.get("worker_type", "unknown")
            if worker_type in active_per_role:
                active_per_role[worker_type] += 1

        for task in tasks:
            if len(self.active_workers) >= slots_free:
                break

            task_id = task["id"]

            # Enhanced dependency checking for planned subtasks
            if task.get("task_type") == "planned_subtask":
                # Verify dependencies are still met (double-check)
                dependencies_met = task.get("dependencies_met", True)
                if not dependencies_met:
                    logger.debug(f"Skipping {task_id}: dependencies not met")
                    continue

                # Extract enhanced assignee information
                planner_context = task.get("planner_context", {})
                preferred_assignee = planner_context.get("assignee", "worker:backend")

                # Parse assignee for worker type determination
                if preferred_assignee.startswith("worker:"):
                    worker = preferred_assignee.split(":", 1)[1]
                else:
                    worker = "backend"  # Default fallback

                # Log planning context
                logger.info(f"[PLANNED] Processing {task_id}: {task['title']}")
                logger.info(
                    f"  Phase: {planner_context.get('workflow_phase', 'unknown')}"
                )
                logger.info(
                    f"  Duration: {planner_context.get('estimated_duration', 'unknown')}min"
                )
                logger.info(
                    f"  Skills: {', '.join(planner_context.get('required_skills', []))}"
                )

            else:
                # Regular task processing
                worker = task.get("tags", [None])[0] if task.get("tags") else "backend"
                if worker not in ["backend", "frontend", "infra"]:
                    worker = "backend"

            # Check per-role limit
            max_per_role = self.hive.config["max_parallel_per_role"].get(worker, 1)
            if active_per_role[worker] >= max_per_role:
                continue

            # Handle app tasks
            if self.is_app_task(task):
                success = self._process_app_task_enhanced(task)
                if success:
                    active_per_role.setdefault(
                        worker, 0
                    )  # App tasks don't count against worker limits
                continue

            # Process regular worker task
            success = self._process_worker_task_enhanced(task, worker)
            if success:
                active_per_role[worker] += 1

    def _process_app_task_enhanced(self, task: Dict[str, Any]) -> bool:
        """Enhanced app task processing with planning integration"""
        task_id = task["id"]

        try:
            # Set assigned status
            assignee = task.get("assignee", "")
            hive_core_db.update_task_status(
                task_id,
                "assigned",
                {
                    "assignee": assignee,
                    "assigned_at": datetime.now(timezone.utc).isoformat(),
                    "current_phase": "execute",
                },
            )

            # Publish task assignment event
            self._publish_task_event(
                self._get_task_event_type("ASSIGNED"),
                task_id,
                task,
                assignee=assignee,
                phase="execute",
            )

            # Execute app task
            result = self.execute_app_task(task)
            if result:
                process, run_id = result
                self.active_workers[task_id] = {
                    "process": process,
                    "run_id": run_id,
                    "phase": "execute",
                    "worker_type": "app",
                }

                hive_core_db.update_task_status(
                    task_id,
                    "in_progress",
                    {"started_at": datetime.now(timezone.utc).isoformat()},
                )

                # Publish task started event
                self._publish_task_event(
                    self._get_task_event_type("STARTED"),
                    task_id,
                    task,
                    phase="execute",
                    process_id=process.pid,
                )

                logger.info(
                    f"✅ Enhanced: Spawned app task {task_id} (PID: {process.pid})"
                )
                return True
            else:
                # Revert on failure
                hive_core_db.update_task_status(
                    task_id,
                    "queued",
                    {"assignee": None, "assigned_at": None, "current_phase": None},
                )
                return False

        except Exception as e:
            logger.error(f"Error processing enhanced app task {task_id}: {e}")
            return False

    def _process_worker_task_enhanced(self, task: Dict[str, Any], worker: str) -> bool:
        """Enhanced worker task processing with planning integration"""
        task_id = task["id"]

        try:
            # Set assigned status
            hive_core_db.update_task_status(
                task_id,
                "assigned",
                {
                    "assignee": worker,
                    "assigned_at": datetime.now(timezone.utc).isoformat(),
                    "current_phase": "apply",
                },
            )

            # Publish task assignment event
            self._publish_task_event(
                self._get_task_event_type("ASSIGNED"),
                task_id,
                task,
                assignee=worker,
                phase="apply",
            )

            # Spawn worker
            from .queen import Phase

            result = self.spawn_worker(task, worker, Phase.APPLY)
            if result:
                process, run_id = result
                self.active_workers[task_id] = {
                    "process": process,
                    "run_id": run_id,
                    "phase": "apply",
                    "worker_type": worker,
                }

                hive_core_db.update_task_status(
                    task_id,
                    "in_progress",
                    {"started_at": datetime.now(timezone.utc).isoformat()},
                )

                # Publish task started event
                self._publish_task_event(
                    self._get_task_event_type("STARTED"),
                    task_id,
                    task,
                    phase="apply",
                    process_id=process.pid,
                )

                logger.info(
                    f"✅ Enhanced: Spawned {worker} for {task_id} (PID: {process.pid})"
                )
                return True
            else:
                # Revert on failure
                hive_core_db.update_task_status(
                    task_id,
                    "queued",
                    {"assignee": None, "assigned_at": None, "current_phase": None},
                )
                return False

        except Exception as e:
            logger.error(f"Error processing enhanced worker task {task_id}: {e}")
            return False

    def _get_task_event_type(self, event_name: str):
        """Helper to get task event type (compatibility with base class)"""
        # This would normally import the actual TaskEventType enum
        # For now, return the string
        return event_name

    def monitor_planning_queue(self):
        """Monitor planning queue for new tasks that need AI Planner attention"""
        current_time = time.time()
        if current_time - self.last_planning_check < self.planning_poll_interval:
            return  # Too soon to check again

        try:
            new_tasks = planning_integration.monitor_planning_queue_changes()
            if new_tasks:
                logger.info(f"📋 Found {len(new_tasks)} new tasks in planning queue")
                for task in new_tasks:
                    logger.info(
                        f"  🎯 {task['id']}: {task['task_description'][:80]}..."
                    )

            self.last_planning_check = current_time

        except Exception as e:
            logger.error(f"Error monitoring planning queue: {e}")

    def print_status_enhanced(self):
        """Enhanced status display with planning statistics"""
        # Call parent status
        super().print_status()

        # Add planning-specific stats
        stats = self.planning_stats
        logger.info(
            f"[PLANNING] Plans triggered: {stats['plans_triggered']}, "
            f"Subtasks completed: {stats['subtasks_completed']}, "
            f"Plans completed: {stats['plans_completed']}, "
            f"Sync errors: {stats['sync_errors']}"
        )

        # Show active plan progress
        try:
            # Get active execution plans
            with planning_integration._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, status FROM execution_plans
                    WHERE status IN ('executing', 'generated', 'approved')
                    LIMIT 5
                """
                )

                active_plans = cursor.fetchall()
                if active_plans:
                    logger.info("[ACTIVE PLANS]")
                    for plan_id, status in active_plans:
                        completion = planning_integration.get_plan_completion_status(
                            plan_id
                        )
                        logger.info(
                            f"  📋 {plan_id}: {status} ({completion.get('completion_percentage', 0):.1f}% complete)"
                        )

        except Exception as e:
            logger.debug(f"Could not display plan status: {e}")

    def run_forever_enhanced(self):
        """Enhanced main orchestration loop with planning integration"""
        self.log.info("Queen Planning Enhanced starting...")
        logger.info("Enhanced AI Planner integration enabled")
        logger.info("=" * 50)

        # Initialize database
        hive_core_db.init_db()

        try:
            while True:
                # Enhanced task processing with planning integration
                self.process_queued_tasks_enhanced()

                # Monitor planning queue for new tasks
                self.monitor_planning_queue()

                # Process review tasks (inherited)
                self.process_review_tasks()

                # Monitor running processes (inherited)
                self.monitor_workers()

                # Enhanced status display
                self.print_status_enhanced()

                # Check completion (inherited logic)
                stats = self.hive.get_task_stats()
                review_pending = len(hive_core_db.get_tasks_by_status("review_pending"))

                if (
                    len(self.active_workers) == 0
                    and stats["queued"] == 0
                    and stats["assigned"] == 0
                    and stats["in_progress"] == 0
                    and review_pending == 0
                ):

                    if stats["completed"] > 0 or stats["failed"] > 0:
                        self.log.info("All tasks completed. Exiting enhanced mode...")
                        break

                time.sleep(self.hive.config["orchestration"]["status_refresh_seconds"])

        except KeyboardInterrupt:
            self.log.info("\nQueen Planning Enhanced shutting down...")

            # Terminate workers (inherited)
            for task_id, metadata in self.active_workers.items():
                self.log.info(f"Terminating {task_id}")
                process = metadata["process"]
                process.terminate()

            self.log.info("Queen Planning Enhanced stopped")

    # ================================================================================
    # ASYNC VERSION - Phase 4.1 Implementation
    # ================================================================================

    async def run_forever_enhanced_async(self):
        """Async version of enhanced orchestration loop for maximum performance"""
        self.log.info("Queen Planning Enhanced starting (Async Mode)...")
        logger.info("🚀 High-performance async planning integration enabled")
        logger.info("=" * 50)

        # Initialize database
        hive_core_db.init_db()

        try:
            while True:
                # Execute all operations concurrently
                await asyncio.gather(
                    self._process_queued_tasks_enhanced_async(),
                    self._monitor_planning_queue_async(),
                    self._process_review_tasks_async(),
                    self._monitor_workers_async(),
                    return_exceptions=True,
                )

                # Enhanced status display
                self.print_status_enhanced()

                # Check completion
                stats = self.hive.get_task_stats()
                review_pending_tasks = await hive_core_db.get_tasks_by_status_async(
                    "review_pending"
                )
                review_pending = (
                    len(review_pending_tasks) if review_pending_tasks else 0
                )

                if (
                    len(self.active_workers) == 0
                    and stats["queued"] == 0
                    and stats["assigned"] == 0
                    and stats["in_progress"] == 0
                    and review_pending == 0
                ):

                    if stats["completed"] > 0 or stats["failed"] > 0:
                        self.log.info(
                            "All tasks completed. Exiting enhanced async mode..."
                        )
                        break

                await asyncio.sleep(
                    self.hive.config["orchestration"]["status_refresh_seconds"]
                )

        except KeyboardInterrupt:
            self.log.info("\nQueen Planning Enhanced async mode shutting down...")

            # Terminate workers
            for task_id, metadata in self.active_workers.items():
                self.log.info(f"Terminating {task_id}")
                process = metadata["process"]
                process.terminate()

            self.log.info("Queen Planning Enhanced async mode stopped")

    async def _process_queued_tasks_enhanced_async(self):
        """Async version of enhanced task processing"""
        try:
            # Get ready planned subtasks asynchronously
            planned_subtasks = (
                await async_planning_integration.get_ready_planned_subtasks_async(
                    limit=20
                )
            )

            # Process with enhanced planning integration
            if planned_subtasks:
                logger.debug(
                    f"[ASYNC] Processing {len(planned_subtasks)} planned subtasks"
                )

        except Exception as e:
            logger.error(f"Error in async enhanced task processing: {e}")

    async def _monitor_planning_queue_async(self):
        """Async version of planning queue monitoring"""
        try:
            # This would use async database operations when available
            await asyncio.sleep(0.1)  # Prevent tight loop

        except Exception as e:
            logger.error(f"Error in async planning queue monitoring: {e}")

    async def _process_review_tasks_async(self):
        """Async version of review task processing"""
        try:
            # Placeholder for async review processing
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in async review processing: {e}")

    async def _monitor_workers_async(self):
        """Async version of worker monitoring"""
        try:
            # Placeholder for async worker monitoring
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in async worker monitoring: {e}")


def main():
    """Main entry point for enhanced Queen with planning integration"""
    import argparse

    from hive_logging import setup_logging

    from .hive_core import HiveCore

    parser = argparse.ArgumentParser(description="Queen Planning Enhanced")
    parser.add_argument("--live", action="store_true", help="Enable live output")
    parser.add_argument(
        "--async",
        action="store_true",
        dest="async_mode",
        help="Enable async mode for enhanced performance",
    )
    args = parser.parse_args()

    # Initialize database
    hive_core_db.init_db()

    # Configure logging
    setup_logging(
        name="queen-enhanced", log_to_file=True, log_file_path="logs/queen_enhanced.log"
    )

    # Create components
    hive_core = HiveCore()
    queen = QueenPlanningEnhanced(hive_core, live_output=args.live)

    # Run in selected mode
    if args.async_mode:
        logger.info("Starting Queen Planning Enhanced in async mode")
        import asyncio

        asyncio.run(queen.run_forever_enhanced_async())
    else:
        logger.info("Starting Queen Planning Enhanced in standard mode")
        queen.run_forever_enhanced()


if __name__ == "__main__":
    main()
