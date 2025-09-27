"""
Autonomous review agent that polls the database for review_pending tasks
"""

import asyncio
import argparse
import json
import signal
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

# Add paths for Hive packages
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "packages" / "hive-logging" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "packages" / "hive-bus" / "src"))

import hive_core_db
from hive_logging import get_logger
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel

from ai_reviewer.reviewer import ReviewEngine, ReviewDecision
from ai_reviewer.database_adapter import DatabaseAdapter

# Event bus imports for explicit agent communication
try:
    from hive_bus import get_event_bus, create_task_event, TaskEventType
except ImportError as e:
    logger.warning(f"Event bus not available: {e} - continuing without events")
    get_event_bus = None
    create_task_event = None
    TaskEventType = None


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
        test_mode: bool = False
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
            "start_time": None
        }

        # Initialize event bus for explicit agent communication
        try:
            self.event_bus = get_event_bus() if get_event_bus else None
            if self.event_bus:
                logger.info("Event bus initialized for explicit agent communication")
        except Exception as e:
            logger.warning(f"Event bus initialization failed: {e} - continuing without events")
            self.event_bus = None

    def _publish_task_event(self, event_type: 'TaskEventType', task_id: str,
                           correlation_id: str = None, **additional_payload) -> str:
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
                **additional_payload
            )

            event_id = self.event_bus.publish(event, correlation_id=correlation_id)
            logger.debug(f"Published task event {event_type} for task {task_id}: {event_id}")
            return event_id

        except Exception as e:
            logger.warning(f"Failed to publish task event {event_type} for task {task_id}: {e}")
            return ""

    async def run(self):
        """Main autonomous loop"""
        self.running = True
        self.stats["start_time"] = datetime.now()

        logger.info("AI Reviewer Agent started")
        console.print(
            Panel.fit(
                "[bold green]AI Reviewer Agent Active[/bold green]\n"
                f"Polling interval: {self.polling_interval}s\n"
                f"Mode: {'TEST' if self.test_mode else 'PRODUCTION'}",
                title="AI Reviewer Status"
            )
        )

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            while self.running:
                await self._process_review_queue()
                await self._report_status()
                await asyncio.sleep(self.polling_interval)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self._shutdown()

    async def _process_review_queue(self):
        """Process all pending review tasks"""
        try:
            # Get pending review tasks
            pending_tasks = self.adapter.get_pending_reviews()

            if not pending_tasks:
                logger.debug("No tasks pending review")
                return

            console.print(f"\n[yellow]Found {len(pending_tasks)} tasks to review[/yellow]")

            for task in pending_tasks:
                if not self.running:
                    break

                await self._review_task(task)

        except Exception as e:
            logger.error(f"Error processing review queue: {e}")
            self.stats["errors"] += 1

    async def _review_task(self, task: Dict[str, Any]):
        """Review a single task"""
        try:
            console.print(f"\n[cyan]Reviewing task {task['id']}: {task.get('description', 'No description')}[/cyan]")

            # Retrieve task artifacts
            code_files = self.adapter.get_task_code_files(task['id'])
            test_results = self.adapter.get_test_results(task['id'])
            transcript = self.adapter.get_task_transcript(task['id'])

            if not code_files:
                logger.warning(f"No code files found for task {task['id']}")
                # Mark as needing escalation
                self.adapter.update_task_status(
                    task['id'],
                    "escalated",
                    {"reason": "No code files found for review"}
                )
                self.stats["escalated"] += 1

                # Publish escalation event
                if TaskEventType:
                    self._publish_task_event(
                        TaskEventType.ESCALATED,
                        task['id'],
                        correlation_id=task.get('correlation_id'),
                        escalation_reason="No code files found for review",
                        escalated_by="ai-reviewer"
                    )
                return

            # Perform AI review
            result = self.review_engine.review_task(
                task_id=task['id'],
                task_description=task.get('description', 'No description'),
                code_files=code_files,
                test_results=test_results,
                transcript=transcript
            )

            # Display review results
            self._display_review_result(result)

            # Execute decision
            await self._execute_decision(task, result)

            # Update statistics
            self.stats["tasks_reviewed"] += 1
            self._update_stats_for_decision(result.decision)

        except Exception as e:
            logger.error(f"Error reviewing task {task['id']}: {e}")
            self.stats["errors"] += 1
            # Mark task as escalated on error
            self.adapter.update_task_status(
                task['id'],
                "escalated",
                {"error": str(e)}
            )

            # Publish escalation event for error
            if TaskEventType:
                self._publish_task_event(
                    TaskEventType.ESCALATED,
                    task['id'],
                    correlation_id=task.get('correlation_id'),
                    escalation_reason=f"Review error: {str(e)}",
                    escalated_by="ai-reviewer",
                    error_type=type(e).__name__
                )

    def _display_review_result(self, result):
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

        console.print(metrics_table)

        # Decision panel
        decision_color = {
            ReviewDecision.APPROVE: "green",
            ReviewDecision.REJECT: "red",
            ReviewDecision.REWORK: "yellow",
            ReviewDecision.ESCALATE: "magenta"
        }[result.decision]

        console.print(
            Panel(
                f"[bold {decision_color}]Decision: {result.decision.value.upper()}[/bold {decision_color}]\n\n"
                f"{result.summary}\n\n"
                f"Confidence: {result.confidence:.0%}",
                title="Review Decision"
            )
        )

        # Issues and suggestions
        if result.issues:
            console.print("\n[red]Issues Found:[/red]")
            for issue in result.issues:
                console.print(f"  • {issue}")

        if result.suggestions:
            console.print("\n[yellow]Suggestions:[/yellow]")
            for suggestion in result.suggestions:
                console.print(f"  • {suggestion}")

    async def _execute_decision(self, task: Dict[str, Any], result):
        """Execute the review decision"""
        new_status = {
            ReviewDecision.APPROVE: TaskStatus.APPROVED,
            ReviewDecision.REJECT: TaskStatus.REJECTED,
            ReviewDecision.REWORK: TaskStatus.REWORK_NEEDED,
            ReviewDecision.ESCALATE: TaskStatus.ESCALATED
        }[result.decision]

        # Update task status with review results
        self.adapter.update_task_status(
            task['id'],
            new_status,
            result.to_dict()
        )

        # Publish review completion event with decision details
        if TaskEventType:
            event_type = {
                ReviewDecision.APPROVE: TaskEventType.REVIEW_COMPLETED,
                ReviewDecision.REJECT: TaskEventType.FAILED,
                ReviewDecision.REWORK: TaskEventType.REVIEW_COMPLETED,
                ReviewDecision.ESCALATE: TaskEventType.ESCALATED
            }.get(result.decision, TaskEventType.REVIEW_COMPLETED)

            self._publish_task_event(
                event_type,
                task['id'],
                correlation_id=task.get('correlation_id'),
                review_decision=result.decision.value,
                review_score=getattr(result, 'score', None),
                review_summary=getattr(result, 'summary', None),
                new_status=new_status
            )

        # If approved, potentially trigger next phase
        if result.decision == ReviewDecision.APPROVE:
            await self._trigger_next_phase(task)

        logger.info(f"Task {task['id']} review completed: {result.decision.value}")

    async def _trigger_next_phase(self, task: Dict[str, Any]):
        """Trigger next phase for approved tasks"""
        # This would integrate with the broader Hive system
        # For now, just log it
        logger.info(f"Task {task['id']} approved, ready for next phase")

    def _update_stats_for_decision(self, decision: ReviewDecision):
        """Update statistics based on decision"""
        if decision == ReviewDecision.APPROVE:
            self.stats["approved"] += 1
        elif decision == ReviewDecision.REJECT:
            self.stats["rejected"] += 1
        elif decision == ReviewDecision.REWORK:
            self.stats["rework"] += 1
        elif decision == ReviewDecision.ESCALATE:
            self.stats["escalated"] += 1

    async def _report_status(self):
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

            console.print("\n", status_table)

    def _pct(self, stat: str) -> int:
        """Calculate percentage of a statistic"""
        if self.stats["tasks_reviewed"] == 0:
            return 0
        return int((self.stats[stat] / self.stats["tasks_reviewed"]) * 100)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating shutdown")
        self.running = False

    async def _shutdown(self):
        """Graceful shutdown"""
        console.print("\n[yellow]Shutting down AI Reviewer Agent...[/yellow]")

        # Final statistics
        if self.stats["start_time"]:
            runtime = (datetime.now() - self.stats["start_time"]).total_seconds()
            console.print(
                Panel(
                    f"Session Summary:\n"
                    f"Runtime: {runtime:.0f} seconds\n"
                    f"Tasks Reviewed: {self.stats['tasks_reviewed']}\n"
                    f"Approved: {self.stats['approved']}\n"
                    f"Rejected: {self.stats['rejected']}\n"
                    f"Errors: {self.stats['errors']}",
                    title="AI Reviewer Session Complete"
                )
            )

        logger.info("AI Reviewer Agent stopped")


def main():
    """Main entry point for the autonomous agent"""
    parser = argparse.ArgumentParser(description="AI Reviewer Autonomous Agent")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode")
    parser.add_argument("--api-key", help="Anthropic API key")
    parser.add_argument("--polling-interval", type=int, default=30, help="Polling interval in seconds")
    args = parser.parse_args()

    # Initialize components
    # Use mock mode for test mode
    review_engine = ReviewEngine(mock_mode=args.test_mode)

    # Create and run agent
    agent = ReviewAgent(
        review_engine=review_engine,
        polling_interval=args.polling_interval,
        test_mode=args.test_mode
    )

    # Run the autonomous loop
    asyncio.run(agent.run())


def run_daemon():
    """Entry point for daemon mode"""
    # This is called by the hive-app.toml daemon configuration
    main()


if __name__ == "__main__":
    main()