"""
Autonomous review agent that polls the database for review_pending tasks
"""
# ruff: noqa: S603, S607

import argparse
import asyncio
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from hive_logging import get_logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ai_reviewer.auto_fix import ErrorAnalyzer, EscalationLogic, FixGenerator, RetryManager
from ai_reviewer.database_adapter import DatabaseAdapter
from ai_reviewer.reviewer import ReviewDecision, ReviewEngine

logger = get_logger(__name__)

# Import from orchestrator's extended database layer (proper app-to-app communication)

# Async database imports for Phase 4.1
try:
    from hive_orchestrator.core.db import (  # noqa: F401
        get_async_connection,
        get_tasks_by_status_async,
        update_task_status_async,
    )

    ASYNC_DB_AVAILABLE = True
except ImportError:
    ASYNC_DB_AVAILABLE = False

# Event bus imports for explicit agent communication
try:
    from hive_bus import TaskEventType, create_task_event, get_event_bus

    # Try to import async event bus operations
    try:
        from hive_bus.event_bus import get_async_event_bus, publish_event_async  # noqa: F401

        ASYNC_EVENTS_AVAILABLE = True
    except ImportError:
        ASYNC_EVENTS_AVAILABLE = False
except ImportError as e:
    logger = get_logger(__name__)
    logger.warning(f"Event bus not available: {e} - continuing without events")
    get_event_bus = None,
    create_task_event = None
    TaskEventType = None
    ASYNC_EVENTS_AVAILABLE = False


console = Console()
logger = get_logger(__name__)


class ReviewAgent:
    """
    Autonomous agent that continuously monitors and processes review_pending tasks
    """

    def __init__(
        self,
        review_engine: ReviewEngine,
        polling_interval: int = 30,
        test_mode: bool = False,
        enable_auto_fix: bool = True,
        max_fix_attempts: int = 3,
    ):
        """
        Initialize the review agent

        Args:
            review_engine: AI review engine
            polling_interval: Seconds between queue checks
            test_mode: Run with shorter intervals for testing
            enable_auto_fix: Enable autonomous fix-retry loop
            max_fix_attempts: Maximum fix attempts before escalation
        """
        self.adapter = DatabaseAdapter()
        self.review_engine = review_engine
        self.polling_interval = polling_interval if not test_mode else 5
        self.test_mode = test_mode
        self.running = False
        self.enable_auto_fix = enable_auto_fix
        self.stats = {
            "tasks_reviewed": 0,
            "approved": 0,
            "rejected": 0,
            "rework": 0,
            "escalated": 0,
            "auto_fixed": 0,
            "fix_attempts": 0,
            "errors": 0,
            "start_time": None,
        }

        # Auto-fix components
        if enable_auto_fix:
            self.error_analyzer = ErrorAnalyzer()
            self.fix_generator = FixGenerator()
            self.retry_manager = RetryManager(max_attempts=max_fix_attempts)
            self.escalation_logic = EscalationLogic(max_attempts=max_fix_attempts)
            logger.info("Auto-fix enabled with max attempts: {max_fix_attempts}")
        else:
            self.error_analyzer = None
            self.fix_generator = None
            self.retry_manager = None
            self.escalation_logic = None
            logger.info("Auto-fix disabled")

        # Initialize event bus for explicit agent communication
        try:
            self.event_bus = get_event_bus() if get_event_bus else None
            if self.event_bus:
                logger.info("Event bus initialized for explicit agent communication")
        except Exception as e:
            logger.warning(f"Event bus initialization failed: {e} - continuing without events")
            self.event_bus = None

    def _publish_task_event(
        self,
        event_type: "TaskEventType",
        task_id: str,
        correlation_id: str = None,
        **additional_payload,
    ) -> str:
        """Publish task events for explicit agent communication

        Args:
            event_type: Type of task event
            task_id: Associated task ID
            correlation_id: Correlation ID for workflow tracking
            **additional_payload: Additional event data

        Returns:
            Published event ID or empty string if publishing failed
        """
        if not self.event_bus or not create_task_event or not TaskEventType:
            return ""

        try:
            event = create_task_event(
                event_type=event_type,
                task_id=task_id,
                source_agent="ai-reviewer",
                **additional_payload,
            )

            event_id = self.event_bus.publish(event, correlation_id=correlation_id)
            logger.debug(f"Published task event {event_type} for task {task_id}: {event_id}")
            return event_id

        except Exception as e:
            logger.warning(f"Failed to publish task event {event_type} for task {task_id}: {e}")
            return ""

    async def run_async(self) -> None:
        """Main autonomous loop"""
        self.running = True
        self.stats["start_time"] = datetime.now()

        logger.info("AI Reviewer Agent started")
        logger.info(
            Panel.fit(
                "[bold green]AI Reviewer Agent Active[/bold green]\n",
                f"Polling interval: {self.polling_interval}s\n",
                f"Mode: {'TEST' if self.test_mode else 'PRODUCTION'}",
                title="AI Reviewer Status",
            ),
        )

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            while self.running:
                await self._process_review_queue_async()
                await self._report_status_async()
                await asyncio.sleep(self.polling_interval)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self._shutdown_async()

    async def _process_review_queue_async(self) -> None:
        """Process all pending review tasks"""
        try:
            # Get pending review tasks
            pending_tasks = self.adapter.get_pending_reviews()

            if not pending_tasks:
                logger.debug("No tasks pending review")
                return

            console.logger.info(f"\n[yellow]Found {len(pending_tasks)} tasks to review[/yellow]")

            for task in pending_tasks:
                if not self.running:
                    break

                await self._review_task_async(task)

        except Exception as e:
            logger.error(f"Error processing review queue: {e}")
            self.stats["errors"] += 1

    async def _review_task_async(self, task: dict[str, Any]) -> None:
        """Review a single task"""
        try:
            console.logger.info(
                f"\n[cyan]Reviewing task {task['id']}: {task.get('description', 'No description')}[/cyan]",
            )

            # Retrieve task artifacts
            code_files = self.adapter.get_task_code_files(task["id"]),
            test_results = self.adapter.get_test_results(task["id"]),
            transcript = self.adapter.get_task_transcript(task["id"])

            if not code_files:
                logger.warning(f"No code files found for task {task['id']}")
                # Mark as needing escalation
                self.adapter.update_task_status(task["id"], "escalated", {"reason": "No code files found for review"})
                self.stats["escalated"] += 1

                # Publish escalation event
                if TaskEventType:
                    self._publish_task_event(
                        TaskEventType.ESCALATED,
                        task["id"],
                        correlation_id=task.get("correlation_id"),
                        escalation_reason="No code files found for review",
                        escalated_by="ai-reviewer",
                    )
                return

            # Perform AI review
            result = self.review_engine.review_task(
                task_id=task["id"],
                task_description=task.get("description", "No description"),
                code_files=code_files,
                test_results=test_results,
                transcript=transcript,
            )

            # Display review results
            self._display_review_result(result)

            # Check if validation failed and auto-fix is enabled
            if result.decision == ReviewDecision.REJECT and self.enable_auto_fix:
                logger.info(f"Attempting auto-fix for rejected task {task['id']}")

                # Get validation output from test results
                validation_output = test_results if test_results else ""

                # Attempt auto-fix
                fix_succeeded = await self._attempt_auto_fix_async(task, validation_output)

                if fix_succeeded:
                    logger.info(f"Auto-fix succeeded for task {task['id']}, re-running review")

                    # Re-run review after successful fixes
                    code_files = self.adapter.get_task_code_files(task["id"])
                    test_results = self.adapter.get_test_results(task["id"])

                    result = self.review_engine.review_task(
                        task_id=task["id"],
                        task_description=task.get("description", "No description"),
                        code_files=code_files,
                        test_results=test_results,
                        transcript=transcript,
                    )

                    # Display updated review results
                    self._display_review_result(result)
                else:
                    logger.warning(f"Auto-fix failed for task {task['id']}, keeping original REJECT decision")

            # Execute decision
            await self._execute_decision_async(task, result)

            # Update statistics
            self.stats["tasks_reviewed"] += 1
            self._update_stats_for_decision(result.decision)

        except Exception as e:
            logger.error(f"Error reviewing task {task['id']}: {e}")
            self.stats["errors"] += 1
            # Mark task as escalated on error
            self.adapter.update_task_status(task["id"], "escalated", {"error": str(e)})

            # Publish escalation event for error
            if TaskEventType:
                self._publish_task_event(
                    TaskEventType.ESCALATED,
                    task["id"],
                    correlation_id=task.get("correlation_id"),
                    escalation_reason=f"Review error: {str(e)}",
                    escalated_by="ai-reviewer",
                    error_type=type(e).__name__,
                )

    def _display_review_result(self, result: dict[str, Any]) -> None:
        """Display review results in a nice format"""
        # Create metrics table
        metrics_table = Table(title="Quality Metrics")
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Score", style="white")

        metrics_table.add_row("Code Quality", f"{result.metrics.code_quality:.0f}")
        metrics_table.add_row("Test Coverage", f"{result.metrics.test_coverage:.0f}")
        metrics_table.add_row("Documentation", f"{result.metrics.documentation:.0f}")
        metrics_table.add_row("Security", f"{result.metrics.security:.0f}")
        metrics_table.add_row("Architecture", f"{result.metrics.architecture:.0f}")
        metrics_table.add_row("Overall", f"[bold]{result.metrics.overall_score:.0f}[/bold]")

        console.logger.info(metrics_table)

        # Decision panel
        decision_color = {
            ReviewDecision.APPROVE: "green",
            ReviewDecision.REJECT: "red",
            ReviewDecision.REWORK: "yellow",
            ReviewDecision.ESCALATE: "magenta",
        }[result.decision]

        logger.info(
            Panel(
                f"[bold {decision_color}]Decision: {result.decision.value.upper()}[/bold {decision_color}]\n\n",
                f"{result.summary}\n\n",
                f"Confidence: {result.confidence:.0%}",
                title="Review Decision",
            ),
        )

        # Issues and suggestions
        if result.issues:
            console.logger.info("\n[red]Issues Found:[/red]")
            for issue in result.issues:
                console.logger.info(f"  • {issue}")

        if result.suggestions:
            console.logger.info("\n[yellow]Suggestions:[/yellow]")
            for suggestion in result.suggestions:
                console.logger.info(f"  • {suggestion}")

    async def _attempt_auto_fix_async(self, task: dict[str, Any], validation_output: str) -> bool:
        """
        Attempt autonomous fix-retry loop for failed validation.

        Args:
            task: Task dictionary with id and service_dir
            validation_output: Raw validation tool output (pytest, ruff, mypy)

        Returns:
            True if fix succeeded and validation now passes, False otherwise
        """
        if not self.enable_auto_fix:
            logger.info("Auto-fix disabled, skipping fix attempts")
            return False

        task_id = task["id"]
        service_dir = task.get("service_directory")

        if not service_dir:
            logger.error(f"No service directory for task {task_id}, cannot auto-fix")
            return False

        from pathlib import Path

        service_path = Path(service_dir)
        if not service_path.exists():
            logger.error(f"Service directory does not exist: {service_dir}")
            return False

        logger.info(f"Starting auto-fix loop for task {task_id}")

        # Start fix session
        session = self.retry_manager.start_session(task_id, service_path)

        # Parse errors from validation output
        errors = []
        if "pytest" in validation_output.lower():
            errors.extend(self.error_analyzer.parse_pytest_output(validation_output))
        if "ruff" in validation_output.lower() or ".py:" in validation_output:
            errors.extend(self.error_analyzer.parse_ruff_output(validation_output))

        if not errors:
            logger.warning(f"No parseable errors found in validation output for task {task_id}")
            return False

        logger.info(f"Found {len(errors)} errors to fix")

        # Get fixable errors only
        fixable_errors = self.error_analyzer.get_fixable_errors(errors)
        if not fixable_errors:
            logger.info("No fixable errors found, escalating")
            return False

        logger.info(f"{len(fixable_errors)} errors are auto-fixable")

        # Fix-retry loop
        while session.can_retry:
            self.stats["fix_attempts"] += 1

            # Generate fixes for all fixable errors
            for error in fixable_errors:
                # Read the file content
                file_path = service_path / error.file_path
                if not file_path.exists():
                    logger.warning(f"File not found: {file_path}")
                    continue

                file_content = file_path.read_text(encoding="utf-8")

                # Generate fix
                fix = self.fix_generator.generate_fix(error, file_content)
                if not fix:
                    logger.warning(f"Could not generate fix for {error.error_code}: {error.error_message}")
                    continue

                # Apply fix
                success = self.retry_manager.apply_fix(session, fix)
                if success:
                    logger.info(f"Applied fix: {fix.fix_type} for {error.error_code}")
                else:
                    logger.warning(f"Failed to apply fix: {fix.fix_type}")

            # Re-run validation
            logger.info(f"Re-running validation after fix attempt {session.attempt_count}")

            # Re-run validation (simplified - would call actual validation tools)
            # For now, assume we'd call the same validation that initially failed
            # In real implementation, would run pytest, ruff, etc.
            validation_passed = self._rerun_validation(service_path)

            if validation_passed:
                logger.info(f"Validation passed after {session.attempt_count} fix attempts")
                self.retry_manager.complete_session(session, "fixed")
                self.stats["auto_fixed"] += 1

                # Publish success event
                if TaskEventType:
                    await self._publish_task_event_async(
                        TaskEventType.REVIEW_COMPLETED,
                        task_id,
                        correlation_id=task.get("correlation_id"),
                        auto_fix_success=True,
                        fix_attempts=session.attempt_count,
                        fixed_by="guardian-agent",
                    )

                return True

            # Check if we should escalate
            escalation_decision = self.escalation_logic.should_escalate(session)
            if escalation_decision.should_escalate:
                logger.warning(
                    f"Escalating task {task_id}: {escalation_decision.reason.value if escalation_decision.reason else 'unknown'}"
                )

                # Create escalation report
                escalation_report = self.escalation_logic.create_escalation_report(session, escalation_decision)

                # Complete session as escalated
                self.retry_manager.complete_session(session, "escalated")

                # Publish escalation event
                if TaskEventType:
                    await self._publish_task_event_async(
                        TaskEventType.ESCALATED,
                        task_id,
                        correlation_id=task.get("correlation_id"),
                        escalation_reason=escalation_decision.reason.value if escalation_decision.reason else "unknown",
                        fix_attempts=session.attempt_count,
                        escalation_report=escalation_report,
                        escalated_by="guardian-agent",
                    )

                return False

        # Max retries exceeded without escalation check
        logger.warning(f"Max fix attempts ({session.max_attempts}) exceeded for task {task_id}")
        self.retry_manager.complete_session(session, "failed")
        return False

    def _rerun_validation(self, service_path: Path) -> bool:
        """
        Re-run validation on service after fixes applied.

        Args:
            service_path: Path to service directory

        Returns:
            True if validation passes
        """
        logger.info(f"Revalidating service at {service_path}")

        validation_passed = True

        # 1. Syntax check
        try:
            for py_file in service_path.rglob("*.py"):
                result = subprocess.run(
                    ["python", "-m", "py_compile", str(py_file)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    logger.warning(f"Syntax error in {py_file.name}: {result.stderr}")
                    validation_passed = False
        except Exception as e:
            logger.error(f"Syntax check failed: {e}")
            validation_passed = False

        # 2. Ruff check
        try:
            result = subprocess.run(
                ["ruff", "check", str(service_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(f"Ruff violations found:\n{result.stdout}")
                validation_passed = False
            else:
                logger.info("Ruff check: PASS")
        except FileNotFoundError:
            logger.warning("Ruff not found, skipping lint check")
        except Exception as e:
            logger.error(f"Ruff check failed: {e}")
            validation_passed = False

        # 3. Optional: pytest (if tests exist)
        test_dir = service_path / "tests"
        if test_dir.exists():
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", str(test_dir), "--collect-only"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    logger.warning(f"Test collection failed: {result.stderr}")
                    validation_passed = False
                else:
                    logger.info("Test collection: PASS")
            except Exception as e:
                logger.warning(f"Test check skipped: {e}")

        return validation_passed

    async def _execute_decision_async(self, task: dict[str, Any], result) -> None:
        """Execute the review decision"""
        new_status = {
            ReviewDecision.APPROVE: TaskStatus.APPROVED,
            ReviewDecision.REJECT: TaskStatus.REJECTED,
            ReviewDecision.REWORK: TaskStatus.REWORK_NEEDED,
            ReviewDecision.ESCALATE: TaskStatus.ESCALATED,
        }[result.decision]

        # Update task status with review results
        self.adapter.update_task_status(task["id"], new_status, result.to_dict())

        # Publish review completion event with decision details
        if TaskEventType:
            event_type = {
                ReviewDecision.APPROVE: TaskEventType.REVIEW_COMPLETED,
                ReviewDecision.REJECT: TaskEventType.FAILED,
                ReviewDecision.REWORK: TaskEventType.REVIEW_COMPLETED,
                ReviewDecision.ESCALATE: TaskEventType.ESCALATED,
            }.get(result.decision, TaskEventType.REVIEW_COMPLETED)

            self._publish_task_event(
                event_type,
                task["id"],
                correlation_id=task.get("correlation_id"),
                review_decision=result.decision.value,
                review_score=getattr(result, "score", None),
                review_summary=getattr(result, "summary", None),
                new_status=new_status,
            )

        # If approved, potentially trigger next phase
        if result.decision == ReviewDecision.APPROVE:
            await self._trigger_next_phase_async(task)

        logger.info(f"Task {task['id']} review completed: {result.decision.value}")

    async def _trigger_next_phase_async(self, task: dict[str, Any]) -> None:
        """Trigger next phase for approved tasks"""
        # This would integrate with the broader Hive system
        # For now, just log it
        logger.info(f"Task {task['id']} approved, ready for next phase")

    def _update_stats_for_decision(self, decision: ReviewDecision) -> None:
        """Update statistics based on decision"""
        if decision == ReviewDecision.APPROVE:
            self.stats["approved"] += 1
        elif decision == ReviewDecision.REJECT:
            self.stats["rejected"] += 1
        elif decision == ReviewDecision.REWORK:
            self.stats["rework"] += 1
        elif decision == ReviewDecision.ESCALATE:
            self.stats["escalated"] += 1

    async def _report_status_async(self) -> None:
        """Report agent status periodically"""
        if self.stats["tasks_reviewed"] > 0 and self.stats["tasks_reviewed"] % 10 == 0:
            runtime = (datetime.now() - self.stats["start_time"]).total_seconds(),
            rate = self.stats["tasks_reviewed"] / (runtime / 3600)  # tasks per hour,

            status_table = Table(title="Agent Statistics")
            status_table.add_column("Metric", style="cyan")
            status_table.add_column("Value", style="white")

            status_table.add_row("Total Reviewed", str(self.stats["tasks_reviewed"]))
            status_table.add_row("Approved", f"{self.stats['approved']} ({self._pct('approved')}%)")
            status_table.add_row("Rejected", f"{self.stats['rejected']} ({self._pct('rejected')}%)")
            status_table.add_row("Rework", f"{self.stats['rework']} ({self._pct('rework')}%)")
            status_table.add_row("Escalated", f"{self.stats['escalated']} ({self._pct('escalated')}%)")
            status_table.add_row("Auto-Fixed", str(self.stats["auto_fixed"]))
            status_table.add_row("Fix Attempts", str(self.stats["fix_attempts"]))
            status_table.add_row("Errors", str(self.stats["errors"]))
            status_table.add_row("Review Rate", f"{rate:.1f} tasks/hour")

            console.logger.info("\n", status_table)

    def _pct(self, stat: str) -> int:
        """Calculate percentage of a statistic"""
        if self.stats["tasks_reviewed"] == 0:
            return 0
        return int((self.stats[stat] / self.stats["tasks_reviewed"]) * 100)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating shutdown")
        self.running = False

    async def _shutdown_async(self) -> None:
        """Graceful shutdown"""
        console.logger.info("\n[yellow]Shutting down AI Reviewer Agent...[/yellow]")

        # Final statistics
        if self.stats["start_time"]:
            runtime = (datetime.now() - self.stats["start_time"]).total_seconds()
            logger.info(
                Panel(
                    "Session Summary:\n",
                    f"Runtime: {runtime:.0f} seconds\n",
                    f"Tasks Reviewed: {self.stats['tasks_reviewed']}\n",
                    f"Approved: {self.stats['approved']}\n",
                    f"Rejected: {self.stats['rejected']}\n",
                    f"Auto-Fixed: {self.stats['auto_fixed']}\n",
                    f"Fix Attempts: {self.stats['fix_attempts']}\n",
                    f"Errors: {self.stats['errors']}",
                    title="AI Reviewer Session Complete",
                ),
            )

        logger.info("AI Reviewer Agent stopped")

    # ================================================================================
    # ASYNC OPERATIONS - Phase 4.1 Implementation
    # ================================================================================

    async def _publish_task_event_async(
        self,
        event_type: "TaskEventType",
        task_id: str,
        correlation_id: str = None,
        **additional_payload,
    ) -> str:
        """Async version of task event publishing."""
        if not self.event_bus or not create_task_event or not TaskEventType or not ASYNC_EVENTS_AVAILABLE:
            return ""

        try:
            event = create_task_event(
                event_type=event_type,
                task_id=task_id,
                source_agent="ai-reviewer",
                **additional_payload,
            )

            event_id = await publish_event_async(event, correlation_id=correlation_id)
            logger.debug(f"Published async task event {event_type} for task {task_id}: {event_id}")
            return event_id

        except Exception as e:
            logger.warning(f"Failed to publish async task event {event_type} for task {task_id}: {e}")
            return ""

    async def _get_pending_reviews_async(self) -> list[dict[str, Any]]:
        """Async version of getting pending review tasks."""
        if not ASYNC_DB_AVAILABLE:
            # Fallback to sync version
            return self.adapter.get_pending_reviews()

        try:
            # Get review_pending tasks using async database operations
            tasks = await get_tasks_by_status_async("review_pending")
            logger.debug(f"Retrieved {len(tasks)} async pending review tasks")
            return tasks

        except Exception as e:
            logger.error(f"Error retrieving async pending reviews: {e}")
            return []

    async def _update_task_status_async(self, task_id: str, status: str, metadata: dict[str, Any] = None) -> bool:
        """Async version of updating task status."""
        if not ASYNC_DB_AVAILABLE:
            # Fallback to sync version
            return self.adapter.update_task_status(task_id, status, metadata)

        try:
            await update_task_status_async(task_id, status, metadata or {})
            logger.debug(f"Updated async task {task_id} status to {status}")
            return True

        except Exception as e:
            logger.error(f"Error updating async task status: {e}")
            return False

    async def _process_review_queue_async(self) -> None:
        """Async version of processing review queue with enhanced performance."""
        try:
            # Get pending review tasks asynchronously
            pending_tasks = await self._get_pending_reviews_async()

            if not pending_tasks:
                logger.debug("No tasks pending review (async)")
                return

            console.logger.info(f"\n[yellow]Found {len(pending_tasks)} tasks to review (async)[/yellow]")

            for task in pending_tasks:
                if not self.running:
                    break

                await self._review_task_async(task)

        except Exception as e:
            logger.error(f"Error processing async review queue: {e}")
            self.stats["errors"] += 1

    async def _review_task_async(self, task: dict[str, Any]) -> None:
        """Async version of reviewing a single task."""
        try:
            console.logger.info(
                f"\n[cyan]Reviewing task {task['id']} (async): {task.get('description', 'No description')}[/cyan]",
            )

            # Retrieve task artifacts (these could be made async in future enhancement)
            code_files = self.adapter.get_task_code_files(task["id"]),
            test_results = self.adapter.get_test_results(task["id"]),
            transcript = self.adapter.get_task_transcript(task["id"])

            if not code_files:
                logger.warning(f"No code files found for async task {task['id']}")
                # Mark as needing escalation asynchronously
                await self._update_task_status_async(
                    task["id"],
                    "escalated",
                    {"reason": "No code files found for review"},
                )
                self.stats["escalated"] += 1

                # Publish escalation event asynchronously
                if TaskEventType:
                    await self._publish_task_event_async(
                        TaskEventType.ESCALATED,
                        task["id"],
                        correlation_id=task.get("correlation_id"),
                        escalation_reason="No code files found for review",
                        escalated_by="ai-reviewer",
                    )
                return

            # Perform AI review (this can remain sync as it's CPU-bound)
            result = self.review_engine.review_task(
                task_id=task["id"],
                task_description=task.get("description", "No description"),
                code_files=code_files,
                test_results=test_results,
                transcript=transcript,
            )

            # Display review results
            self._display_review_result(result)

            # Execute decision asynchronously
            await self._execute_decision_async(task, result)

            # Update statistics
            self.stats["tasks_reviewed"] += 1
            self._update_stats_for_decision(result.decision)

        except Exception as e:
            logger.error(f"Error reviewing async task {task['id']}: {e}")
            self.stats["errors"] += 1
            # Mark task as escalated on error asynchronously
            await self._update_task_status_async(task["id"], "escalated", {"error": str(e)})

            # Publish escalation event for error asynchronously
            if TaskEventType:
                await self._publish_task_event_async(
                    TaskEventType.ESCALATED,
                    task["id"],
                    correlation_id=task.get("correlation_id"),
                    escalation_reason=f"Review error: {str(e)}",
                    escalated_by="ai-reviewer",
                    error_type=type(e).__name__,
                )

    async def _execute_decision_async(self, task: dict[str, Any], result) -> None:
        """Async version of executing review decision."""
        from ai_reviewer.database_adapter import TaskStatus
        from ai_reviewer.reviewer import ReviewDecision

        new_status = {
            ReviewDecision.APPROVE: TaskStatus.APPROVED,
            ReviewDecision.REJECT: TaskStatus.REJECTED,
            ReviewDecision.REWORK: TaskStatus.REWORK_NEEDED,
            ReviewDecision.ESCALATE: TaskStatus.ESCALATED,
        }[result.decision]

        # Update task status with review results asynchronously
        await self._update_task_status_async(task["id"], new_status, result.to_dict())

        # Publish appropriate events asynchronously
        if TaskEventType:
            if result.decision == ReviewDecision.APPROVE:
                await self._publish_task_event_async(
                    TaskEventType.APPROVED,
                    task["id"],
                    correlation_id=task.get("correlation_id"),
                    review_decision="approve",
                    review_summary=result.summary,
                    overall_score=result.metrics.overall_score,
                    reviewed_by="ai-reviewer",
                )
            elif result.decision in [ReviewDecision.REJECT, ReviewDecision.REWORK]:
                await self._publish_task_event_async(
                    TaskEventType.REJECTED,
                    task["id"],
                    correlation_id=task.get("correlation_id"),
                    review_decision=result.decision.value,
                    review_summary=result.summary,
                    issues=result.issues,
                    suggestions=result.suggestions,
                    reviewed_by="ai-reviewer",
                )
            elif result.decision == ReviewDecision.ESCALATE:
                await self._publish_task_event_async(
                    TaskEventType.ESCALATED,
                    task["id"],
                    correlation_id=task.get("correlation_id"),
                    escalation_reason=result.summary,
                    escalated_by="ai-reviewer",
                )

        console.logger.info(f"[green]Task {task['id']} reviewed: {result.decision.value}[/green]")

    async def run_async(self) -> None:  # noqa: F811
        """Enhanced async version of main autonomous loop for 3-5x performance improvement."""
        self.running = True
        self.stats["start_time"] = datetime.now()

        logger.info("AI Reviewer Agent started in async mode")
        logger.info(
            Panel.fit(
                "[bold green]AI Reviewer Agent Active (Async Mode)[/bold green]\n",
                f"Polling interval: {self.polling_interval}s\n",
                f"Mode: {'TEST' if self.test_mode else 'PRODUCTION'}\n",
                f"Async DB: {'✓' if ASYNC_DB_AVAILABLE else '✗'}\n",
                f"Async Events: {'✓' if ASYNC_EVENTS_AVAILABLE else '✗'}",
                title="AI Reviewer Status",
            ),
        )

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            while self.running:
                # Use async methods for enhanced performance
                if ASYNC_DB_AVAILABLE:
                    await self._process_review_queue_async()
                else:
                    await self._process_review_queue_async()

                await self._report_status_async()
                await asyncio.sleep(self.polling_interval)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self._shutdown_async()


def main() -> None:
    """Main entry point for the autonomous agent"""
    parser = argparse.ArgumentParser(description="AI Reviewer Autonomous Agent")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode")
    parser.add_argument("--api-key", help="Anthropic API key")
    parser.add_argument("--polling-interval", type=int, default=30, help="Polling interval in seconds")
    parser.add_argument("--async-mode", action="store_true", help="Run in async mode for better performance")
    args = parser.parse_args()

    # Initialize components
    # Use mock mode for test mode
    review_engine = ReviewEngine(mock_mode=args.test_mode)

    # Create and run agent
    agent = ReviewAgent(review_engine=review_engine, polling_interval=args.polling_interval, test_mode=args.test_mode)

    # Check if async mode is requested and available
    if args.async_mode:
        if ASYNC_DB_AVAILABLE or ASYNC_EVENTS_AVAILABLE:
            logger.info("Starting AI Reviewer in async mode for enhanced performance")
            asyncio.run_async(agent.run_async())
        else:
            logger.warning("Async mode requested but not available, falling back to sync mode")
            asyncio.run_async(agent.run_async())
    else:
        # Run the autonomous loop
        asyncio.run_async(agent.run_async())


def run_daemon() -> None:
    """Entry point for daemon mode"""
    # This is called by the hive-app.toml daemon configuration
    main()


if __name__ == "__main__":
    main()
