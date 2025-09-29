"""
Autonomous review agent that polls the database for review_pending tasks
"""

import argparse
import asyncio
import signal
from datetime import datetime
from typing import Any, Dict

# Import hive logging
from hive_logging import get_logger

logger = get_logger(__name__)

from hive_logging import get_logger

# Import from orchestrator's extended database layer (proper app-to-app communication)

# Async database imports for Phase 4.1
try:
    from hive_orchestrator.core.db import (
        get_async_connection,
        get_tasks_by_status_async,
        update_task_status_async,
    )

    ASYNC_DB_AVAILABLE = True
except ImportError:
    ASYNC_DB_AVAILABLE = False
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ai_reviewer.database_adapter import DatabaseAdapter
from ai_reviewer.reviewer import ReviewDecision, ReviewEngine

# Event bus imports for explicit agent communication
try:
    from hive_bus import TaskEventType, create_task_event, get_event_bus

    # Try to import async event bus operations
    try:
        from hive_bus.event_bus import get_async_event_bus, publish_event_async

        ASYNC_EVENTS_AVAILABLE = True
    except ImportError:
        ASYNC_EVENTS_AVAILABLE = False
except ImportError as e:
    logger = get_logger(__name__)
    logger.warning(f"Event bus not available: {e} - continuing without events")
    get_event_bus = None
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
    ):
        """
        Initialize the review agent

        Args:
            review_engine: AI review engine
            polling_interval: Seconds between queue checks
            test_mode: Run with shorter intervals for testing
        """
        self.adapter = DatabaseAdapter()
        self.review_engine = review_engine
        self.polling_interval = polling_interval if not test_mode else 5
        self.test_mode = test_mode
        self.running = False
        self.stats = {
            "tasks_reviewed": 0,
            "approved": 0,
            "rejected": 0,
            "rework": 0,
            "escalated": 0,
            "errors": 0,
            "start_time": None,
        }

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
                "[bold green]AI Reviewer Agent Active[/bold green]\n"
                f"Polling interval: {self.polling_interval}s\n"
                f"Mode: {'TEST' if self.test_mode else 'PRODUCTION'}",
                title="AI Reviewer Status",
            )
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

    async def _review_task_async(self, task: Dict[str, Any]) -> None:
        """Review a single task"""
        try:
            console.logger.info(
                f"\n[cyan]Reviewing task {task['id']}: {task.get('description', 'No description')}[/cyan]"
            )

            # Retrieve task artifacts
            code_files = self.adapter.get_task_code_files(task["id"])
            test_results = self.adapter.get_test_results(task["id"])
            transcript = self.adapter.get_task_transcript(task["id"])

            if not code_files:
                logger.warning(f"No code files found for task {task['id']}")
                # Mark as needing escalation
                self.adapter.update_task_status(
                    task["id"],
                    "escalated",
                    {"reason": "No code files found for review"},
                )
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

    def _display_review_result(self, result: Dict[str, Any]) -> None:
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
                f"[bold {decision_color}]Decision: {result.decision.value.upper()}[/bold {decision_color}]\n\n"
                f"{result.summary}\n\n"
                f"Confidence: {result.confidence:.0%}",
                title="Review Decision",
            )
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

    async def _execute_decision_async(self, task: Dict[str, Any], result) -> None:
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

    async def _trigger_next_phase_async(self, task: Dict[str, Any]) -> None:
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
            runtime = (datetime.now() - self.stats["start_time"]).total_seconds()
            rate = self.stats["tasks_reviewed"] / (runtime / 3600)  # tasks per hour

            status_table = Table(title="Agent Statistics")
            status_table.add_column("Metric", style="cyan")
            status_table.add_column("Value", style="white")

            status_table.add_row("Total Reviewed", str(self.stats["tasks_reviewed"]))
            status_table.add_row("Approved", f"{self.stats['approved']} ({self._pct('approved')}%)")
            status_table.add_row("Rejected", f"{self.stats['rejected']} ({self._pct('rejected')}%)")
            status_table.add_row("Rework", f"{self.stats['rework']} ({self._pct('rework')}%)")
            status_table.add_row("Escalated", f"{self.stats['escalated']} ({self._pct('escalated')}%)")
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
                    f"Session Summary:\n"
                    f"Runtime: {runtime:.0f} seconds\n"
                    f"Tasks Reviewed: {self.stats['tasks_reviewed']}\n"
                    f"Approved: {self.stats['approved']}\n"
                    f"Rejected: {self.stats['rejected']}\n"
                    f"Errors: {self.stats['errors']}",
                    title="AI Reviewer Session Complete",
                )
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

    async def _get_pending_reviews_async(self) -> List[Dict[str, Any]]:
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

    async def _update_task_status_async(self, task_id: str, status: str, metadata: Dict[str, Any] = None) -> bool:
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

    async def _review_task_async(self, task: Dict[str, Any]) -> None:
        """Async version of reviewing a single task."""
        try:
            console.logger.info(
                f"\n[cyan]Reviewing task {task['id']} (async): {task.get('description', 'No description')}[/cyan]"
            )

            # Retrieve task artifacts (these could be made async in future enhancement)
            code_files = self.adapter.get_task_code_files(task["id"])
            test_results = self.adapter.get_test_results(task["id"])
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

    async def _execute_decision_async(self, task: Dict[str, Any], result) -> None:
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

    async def run_async(self) -> None:
        """Enhanced async version of main autonomous loop for 3-5x performance improvement."""
        self.running = True
        self.stats["start_time"] = datetime.now()

        logger.info("AI Reviewer Agent started in async mode")
        logger.info(
            Panel.fit(
                "[bold green]AI Reviewer Agent Active (Async Mode)[/bold green]\n"
                f"Polling interval: {self.polling_interval}s\n"
                f"Mode: {'TEST' if self.test_mode else 'PRODUCTION'}\n"
                f"Async DB: {'✓' if ASYNC_DB_AVAILABLE else '✗'}\n"
                f"Async Events: {'✓' if ASYNC_EVENTS_AVAILABLE else '✗'}",
                title="AI Reviewer Status",
            )
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
    parser.add_argument(
        "--async-mode",
        action="store_true",
        help="Run in async mode for better performance",
    )
    args = parser.parse_args()

    # Initialize components
    # Use mock mode for test mode
    review_engine = ReviewEngine(mock_mode=args.test_mode)

    # Create and run agent
    agent = ReviewAgent(
        review_engine=review_engine,
        polling_interval=args.polling_interval,
        test_mode=args.test_mode,
    )

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
