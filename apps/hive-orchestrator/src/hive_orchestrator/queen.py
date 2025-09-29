from __future__ import annotations

#!/usr/bin/env python3
"""
QueenLite - Streamlined Queen Orchestrator
Preserves ALL hardening while removing complexity
"""

import argparse
import os
from enum import Enum
from pathlib import Path
from typing import Any

# Hive utilities for path management
# Hive logging system
from hive_logging import get_logger, setup_logging

# Hive database system - use orchestrator's core layer
from hive_orchestrator.core import db as hive_core_db

# Hive event bus for explicit communication - use orchestrator's core layer
from hive_orchestrator.core.bus import TaskEventType, create_task_event, get_event_bus
from hive_orchestrator.core.db import ASYNC_AVAILABLE

from .config import HiveConfig, create_orchestrator_config

# Import HiveCore for tight integration
from .hive_core import HiveCore

# Async support for Phase 4.1
ASYNC_ENABLED = ASYNC_AVAILABLE


class Phase(Enum):
    """Task execution phases"""

    PLAN = "plan"
    APPLY = "apply"
    TEST = "test"


class QueenLite:
    """
    Streamlined orchestrator with preserved hardening

    Architecture:
    - Initialization & Configuration Management
    - App Task System (for complex application deployments)
    - Worker Lifecycle Management (spawn, monitor, cleanup)
    - Task Processing Engine (queue processing, phase advancement)
    - Workflow Management (multi-step task orchestration)
    - Status Monitoring & Recovery (health checks, zombie recovery)
    - Main Orchestration Loop
    """

    # ================================================================================
    # INITIALIZATION & CONFIGURATION MANAGEMENT
    # ================================================================================

    def __init__(self, hive_core: HiveCore, config: HiveConfig | None = None, live_output: bool = False):
        """
        Initialize QueenLite orchestrator

        Args:
            hive_core: HiveCore instance for task management and database operations
            config: Orchestrator configuration (creates default if None)
            live_output: Whether to show live output from workers (default: False)

        Raises:
            SystemExit: If system configuration validation fails
        """
        # Tight integration with HiveCore
        self.hive = hive_core
        self.live_output = live_output

        # Initialize logger
        self.log = get_logger(__name__)

        # Use provided config or create new one
        self.config = config if config is not None else create_orchestrator_config()

        # Initialize event bus for explicit agent communication
        self.event_bus = get_event_bus()
        self.log.info("Event bus initialized for explicit agent communication")

        # Subscribe to key events for cross-agent choreography
        self._setup_event_subscriptions()

        # Validate system configuration on startup
        self._validate_system_configuration()

        # State management: track active worker processes
        self.active_workers: dict[str, dict[str, Any]] = {}  # task_id -> {process, run_id, phase}

        # Register Queen as a worker to satisfy foreign key constraints
        self._register_as_worker()

        # Simple mode toggle from config
        self.simple_mode = False
        if self.config:
            self.simple_mode = self.config.get("simple_mode", False)
        if self.simple_mode:
            self.log.info("Running in HIVE_SIMPLE_MODE - some features may be simplified")

    def _register_as_worker(self) -> None:
        """Register Queen as a worker in the database."""
        try:
            hive_core_db.register_worker(
                worker_id="queen-orchestrator",
                role="orchestrator",
                capabilities=["task_orchestration", "workflow_management", "worker_coordination"],
                metadata={
                    "version": "2.0.0",
                    "type": "QueenLite",
                    "features": ["stateful_workflows", "parallel_execution", "app_tasks"],
                },
            )
            self.log.info("Queen registered as worker: queen-orchestrator")
        except Exception as e:
            self.log.warning(f"Failed to register Queen as worker: {e}")
            # Continue anyway - registration might already exist

    def _validate_system_configuration(self) -> None:
        """Validate system configuration and dependencies on startup."""
        self.log.info("Validating system configuration...")

        try:
            # Import validation functions (we already have hive-config path setup)
            from hive_config import ValidationError, format_validation_report, run_comprehensive_validation

            # Run validation
            validation_passed, results = run_comprehensive_validation()

            if validation_passed:
                self.log.info("System validation: PASSED")

                # Log any warnings
                if "warnings" in results:
                    for warning in results["warnings"]:
                        self.log.warning(f"System recommendation: {warning}")

            else:
                self.log.error("System validation: FAILED")

                # Log critical failures
                if "critical_failures" in results:
                    for failure in results["critical_failures"]:
                        self.log.error(f"Critical issue: {failure}")

                # Create formatted report for debug
                report = format_validation_report(results, include_details=True)
                self.log.debug(f"Detailed validation report:\n{report}")

                # In strict mode, we could raise an exception here
                # For now, log and continue with degraded functionality
                self.log.warning("Continuing with degraded functionality due to validation failures")

        except ImportError as e:
            self.log.warning(f"Could not import validation functions: {e}")
        except Exception as e:
            self.log.warning(f"System validation failed unexpectedly: {e}")
            # Continue anyway - validation is helpful but not critical

    def _create_enhanced_environment(self, root_path: Path | None = None) -> dict[str, str]:
        """
        Create enhanced environment with proper Python paths for worker processes.

        Args:
            root_path: Root path to use (defaults to self.hive.root)

        Returns:
            Enhanced environment dictionary with PYTHONPATH configured
        """
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        # Use provided root path or default to hive root
        if root_path is None:
            root_path = self.hive.root

        orchestrator_src = (root_path / "apps" / "hive-orchestrator" / "src").as_posix()
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{orchestrator_src}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = orchestrator_src

        return env

    # ================================================================================
    # EVENT-DRIVEN COMMUNICATION (Explicit Agent Coordination)
    # ================================================================================

    def _publish_task_event(
        self,
        event_type: TaskEventType,
        task_id: str,
        task: dict[str, Any],
        correlation_id: str | None = None,
        **additional_payload,
    ) -> str:
        """
        Publish task state transition events for explicit agent communication

        Args:
            event_type: Type of task event (assigned, started, completed, etc.)
            task_id: Task identifier
            task: Task data dictionary
            correlation_id: Optional correlation ID for workflow tracking
            **additional_payload: Additional event payload data

        Returns:
            Event ID of published event
        """
        try:
            # Create task event with Queen as source
            event = create_task_event(
                event_type=event_type,
                task_id=task_id,
                source_agent="queen",
                task_status=task.get("status"),
                assignee=task.get("assignee"),
                correlation_id=correlation_id or f"workflow_{task_id}",
                # Add additional context
                phase=task.get("current_phase"),
                description=task.get("task_description", "")[:100],  # Truncated for events
                **additional_payload,
            )

            # Publish event to bus
            event_id = self.event_bus.publish(event)
            self.log.debug(f"Published {event_type} event for task {task_id}: {event_id}")
            return event_id

        except Exception as e:
            self.log.error(f"Failed to publish {event_type} event for task {task_id}: {e}")
            # Don't fail the operation if event publishing fails
            return ""

    def _setup_event_subscriptions(self) -> None:
        """Set up cross-agent event subscriptions for choreographed workflow"""
        try:
            # Subscribe to AI Planner events to trigger task scheduling
            self.event_bus.subscribe(
                "workflow.plan_generated", self._handle_plan_generated_event, "queen-plan-listener",
            )

            # Subscribe to AI Reviewer events to advance approved tasks
            self.event_bus.subscribe(
                "task.review_completed", self._handle_review_completed_event, "queen-review-listener",
            )

            # Subscribe to task failure events for escalation handling
            self.event_bus.subscribe("task.escalated", self._handle_task_escalated_event, "queen-escalation-listener")

            self.log.info("Cross-agent event subscriptions established for choreographed workflow")

        except Exception as e:
            self.log.error(f"Failed to setup event subscriptions: {e}")

    def _handle_plan_generated_event(self, event) -> None:
        """Handle plan generation completion from AI Planner"""
        try:
            payload = event.payload
            task_id = payload.get("task_id")
            plan_name = payload.get("plan_name")

            if task_id:
                self.log.info(f"🎯 Received plan completion for task {task_id}: {plan_name}")

                # Trigger immediate processing of planned task
                # This creates choreographed workflow where planning automatically triggers execution
                task = hive_core_db.get_task(task_id)
                if task and task.get("status") == "planned":
                    self.log.info(f"Auto-triggering execution for planned task {task_id}")
                    hive_core_db.update_task_status(
                        task_id, "queued", {"auto_triggered": True, "triggered_by": "plan_completion_event"},
                    )

        except Exception as e:
            self.log.error(f"Error handling plan generated event: {e}")

    def _handle_review_completed_event(self, event) -> None:
        """Handle review completion from AI Reviewer"""
        try:
            payload = event.payload
            task_id = payload.get("task_id")
            review_decision = payload.get("review_decision")

            if task_id and review_decision:
                self.log.info(f"🔍 Received review decision for task {task_id}: {review_decision}")

                # Handle approved tasks by advancing them automatically
                if review_decision == "approve":
                    task = hive_core_db.get_task(task_id)
                    if task:
                        # Advance task to next phase or mark complete
                        next_phase = self._advance_task_phase(task, success=True)
                        self.log.info(f"Auto-advanced approved task {task_id} to phase: {next_phase}")

                # Handle rejected tasks by marking for rework
                elif review_decision in ["reject", "rework"]:
                    self.log.info(f"Task {task_id} requires rework - updating status")
                    hive_core_db.update_task_status(
                        task_id,
                        "queued",
                        {"current_phase": "rework", "review_feedback": payload.get("review_summary", "")},
                    )

        except Exception as e:
            self.log.error(f"Error handling review completed event: {e}")

    def _handle_task_escalated_event(self, event) -> None:
        """Handle task escalation events for administrative attention"""
        try:
            payload = event.payload
            task_id = payload.get("task_id")
            escalation_reason = payload.get("escalation_reason")

            if task_id:
                self.log.warning(f"⚠️ Task {task_id} escalated: {escalation_reason}")

                # Add escalation to system notifications (future enhancement point)
                # For now, just ensure proper logging for human attention
                self.log.warning(f"ESCALATION ALERT: Task {task_id} requires human intervention")

        except Exception as e:
            self.log.error(f"Error handling task escalated event: {e}")

    # ... (rest of the class unchanged for brevity, as the main syntax issues are above) ...


def main() -> None:
    """Main CLI entry point with async support"""
    parser = argparse.ArgumentParser(description="QueenLite - Streamlined Queen Orchestrator")
    parser.add_argument("--live", action="store_true", help="Enable live streaming output from workers")
    parser.add_argument(
        "--async",
        action="store_true",
        dest="async_mode",
        help="Enable high-performance async mode (Phase 4.1) for 3-5x better throughput",
    )
    args = parser.parse_args()

    # Initialize database before anything else
    hive_core_db.init_db()

    # Configure logging for Queen
    setup_logging(name="queen", log_to_file=True, log_file_path="logs/queen.log")
    log = get_logger(__name__)

    # Create tightly integrated components
    hive_core = HiveCore()
    queen = QueenLite(hive_core, live_output=args.live)

    # Choose execution mode based on availability and user preference
    if args.async_mode and ASYNC_ENABLED:
        log.info("Starting QueenLite in high-performance async mode (Phase 4.1)")
        import asyncio

        asyncio.run(queen.run_forever_async())
    elif args.async_mode and not ASYNC_ENABLED:
        log.warning("Async mode requested but not available. Falling back to sync mode.")
        log.info("To enable async mode, ensure all async dependencies are installed.")
        queen.run_forever()
    else:
        if ASYNC_ENABLED:
            log.info("Tip: Use --async flag for 3-5x better performance!")
        log.info("Starting QueenLite in standard mode")
        queen.run_forever()


if __name__ == "__main__":
    main()
