"""Autonomous deployment agent that polls the database for deployment_pending tasks
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from datetime import datetime
from typing import Any

# TODO: Migrate to hive-orchestration async operations when available
# For now, use sync operations from hive-orchestration
# Import from orchestrator's extended database layer (proper app-to-app communication)
# Import hive logging
from hive_logging import get_logger

# Async operations not yet available
ASYNC_DB_AVAILABLE = False

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from .database_adapter import DatabaseAdapter
from .deployer import DeploymentOrchestrator

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
    get_event_bus = None,
    create_task_event = None
    TaskEventType = None
    ASYNC_EVENTS_AVAILABLE = False


console = Console()
logger = get_logger(__name__)


class DeploymentAgent:
    """Autonomous agent that continuously monitors and processes deployment_pending tasks
    """

    def __init__(
        self,
        orchestrator: DeploymentOrchestrator | None = None,
        polling_interval: int = 30,
        test_mode: bool = False,
    ):
        """Initialize the deployment agent

        Args:
            orchestrator: Deployment orchestrator engine
            polling_interval: Seconds between queue checks
            test_mode: Run with shorter intervals for testing

        """
        self.adapter = DatabaseAdapter()
        self.orchestrator = orchestrator or DeploymentOrchestrator()
        self.polling_interval = polling_interval if not test_mode else 5
        self.test_mode = test_mode
        self.running = False
        self.stats = {
            "tasks_deployed": 0,
            "successful": 0,
            "failed": 0,
            "rolled_back": 0,
            "errors": 0,
            "start_time": None,
        }

        # Initialize event bus for explicit agent communication
        try:
            self.event_bus = get_event_bus() if get_event_bus else None
            if self.event_bus:
                logger.info("Event bus initialized for explicit agent communication")
        except Exception as e:
            logger.warning(f"Event bus initialization failed: {e}")
            self.event_bus = None

    async def run_async(self) -> None:
        """Main agent loop - continuously polls for deployment tasks
        """
        self.running = True
        self.stats["start_time"] = datetime.now()

        logger.info(f"Deployment Agent starting (polling every {self.polling_interval}s)")

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        with Live(self._create_status_panel(), refresh_per_second=1) as live:
            try:
                while self.running:
                    # Update live display
                    live.update(self._create_status_panel())

                    # Check for deployment_pending tasks
                    tasks = await self._get_pending_tasks_async()

                    if tasks:
                        logger.info(f"Found {len(tasks)} deployment_pending tasks")

                        for task in tasks:
                            if not self.running:
                                break

                            await self._process_task_async(task)
                            live.update(self._create_status_panel())

                    # Sleep before next poll
                    await asyncio.sleep(self.polling_interval)

            except Exception as e:
                logger.error(f"Agent error: {e}", exc_info=True)
                self.stats["errors"] += 1
            finally:
                self._cleanup()

    async def _get_pending_tasks_async(self) -> list[dict[str, Any]]:
        """Get tasks with deployment_pending status"""
        try:
            if ASYNC_DB_AVAILABLE:
                # Use async database operations if available
                return await get_tasks_by_status_async("deployment_pending")
            # Fallback to sync operations
            return self.adapter.get_deployment_pending_tasks()
        except Exception as e:
            logger.error(f"Error fetching deployment tasks: {e}")
            return []

    async def _process_task_async(self, task: dict[str, Any]) -> None:
        """Process a single deployment task

        Args:
            task: Task dictionary from database

        """
        task_id = task.get("id", "unknown")

        try:
            logger.info(f"Processing deployment task: {task_id}")

            # Update status to deploying
            await self._update_task_status_async(task_id, "deploying")

            # Perform deployment
            result = await self.orchestrator.deploy(task)

            if result.success:
                # Deployment succeeded
                logger.info(f"Task {task_id} deployed successfully")
                await self._update_task_status_async(task_id, "deployed")
                self.stats["successful"] += 1

                # Trigger post-deployment monitoring
                await self._trigger_monitoring_async(task)

                # Publish success event
                if self.event_bus and create_task_event:
                    event = create_task_event(
                        task_id=task_id,
                        event_type=TaskEventType.DEPLOYED,
                        payload={"deployment_result": result.to_dict()},
                    )
                    self.event_bus.publish(event)
            else:
                # Deployment failed
                logger.error(f"Task {task_id} deployment failed: {result.error}")

                if result.rollback_attempted:
                    await self._update_task_status_async(task_id, "rolled_back")
                    self.stats["rolled_back"] += 1
                else:
                    await self._update_task_status_async(task_id, "deployment_failed")
                    self.stats["failed"] += 1

                # Publish failure event
                if self.event_bus and create_task_event:
                    event = create_task_event(
                        task_id=task_id,
                        event_type=TaskEventType.DEPLOYMENT_FAILED,
                        payload={"error": result.error},
                    )
                    self.event_bus.publish(event)

            self.stats["tasks_deployed"] += 1

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
            await self._update_task_status_async(task_id, "deployment_failed")
            self.stats["errors"] += 1

    async def _update_task_status_async(
        self,
        task_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update task status in database"""
        try:
            if ASYNC_DB_AVAILABLE:
                await update_task_status_async(task_id, status, metadata)
            else:
                self.adapter.update_task_status(task_id, status, metadata)
        except Exception as e:
            logger.error(f"Error updating task {task_id} status to {status}: {e}")

    async def _trigger_monitoring_async(self, task: dict[str, Any]) -> None:
        """Trigger post-deployment monitoring and health checks"""
        try:
            # Perform health check
            health_status = await self.orchestrator.check_health(task)

            if not health_status.healthy:
                logger.warning(f"Deployment {task['id']} health check failed: {health_status.message}")
                # Could trigger automatic rollback here if configured

        except Exception as e:
            logger.error(f"Error in post-deployment monitoring: {e}")

    def _create_status_panel(self) -> Panel:
        """Create rich panel showing agent status"""
        status_table = Table(show_header=False, box=None)

        # Calculate uptime
        if self.stats["start_time"]:
            uptime = datetime.now() - self.stats["start_time"],
            uptime_str = str(uptime).split(".")[0]
        else:
            uptime_str = "00:00:00"

        status_table.add_row("Status", "[green]Active[/green]" if self.running else "[red]Stopping[/red]")
        status_table.add_row("Uptime", uptime_str)
        status_table.add_row("Total Deployed", str(self.stats["tasks_deployed"]))

        if self.stats["tasks_deployed"] > 0:
            success_pct = (self.stats["successful"] / self.stats["tasks_deployed"]) * 100
            status_table.add_row("Successful", f"{self.stats['successful']} ({success_pct:.1f}%)")
            status_table.add_row("Failed", str(self.stats["failed"]))
            status_table.add_row("Rolled Back", str(self.stats["rolled_back"]))

        status_table.add_row("Errors", str(self.stats["errors"]))
        status_table.add_row("Mode", "[yellow]TEST[/yellow]" if self.test_mode else "Production")

        return Panel(status_table, title="[bold blue]AI Deployment Agent[/bold blue]", border_style="blue")

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def _cleanup(self) -> None:
        """Cleanup resources on shutdown"""
        logger.info("Agent shutting down...")

        # Log final stats
        logger.info("Final Statistics:")
        logger.info(f"Total Deployments: {self.stats['tasks_deployed']}")
        logger.info(f"Successful: {self.stats['successful']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Rolled Back: {self.stats['rolled_back']}")
        logger.info(f"Errors: {self.stats['errors']}")

        if self.stats["start_time"]:
            uptime = datetime.now() - self.stats["start_time"]
            logger.info(f"Total Runtime: {str(uptime).split('.')[0]}")


def main() -> None:
    """Main entry point for the deployment agent"""
    parser = argparse.ArgumentParser(description="AI Deployment Agent")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode with shorter intervals")
    parser.add_argument("--polling-interval", type=int, default=30, help="Polling interval in seconds (default: 30)")

    args = parser.parse_args()

    # Create and run agent
    agent = DeploymentAgent(polling_interval=args.polling_interval, test_mode=args.test_mode)

    # Run async event loop
    try:
        asyncio.run_async(agent.run_async())
    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")
    except Exception as e:
        logger.error(f"Agent failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
