"""Enhanced Worker Fleet Monitor - Real-time Dashboard with Queue Visualization

Displays real-time status of autonomous QA worker fleet with:
- Worker health and status
- Task queue visualization (priority levels, depth)
- Active tasks and completion metrics
- Recent activity feed
- Escalation notifications
- Auto-scaling metrics
- Performance benchmarks

Phase 2 enhancements over monitor.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from hive_config.paths import PROJECT_ROOT
from hive_logging import get_logger
from hive_orchestration.events import (
    EscalationEvent,
    QATaskEvent,
    WorkerHeartbeat,
    WorkerRegistration,
    get_async_event_bus,
)
from hive_orchestrator.fleet_orchestrator import get_orchestrator

logger = get_logger(__name__)


class EnhancedFleetMonitor:
    """Enhanced real-time monitoring dashboard for worker fleet.

    Phase 2 Features:
    - Task queue visualization by priority
    - Worker pool auto-scaling metrics
    - Performance benchmarks and trends
    - Enhanced escalation tracking
    - System health indicators
    """

    def __init__(self, orchestrator_db_path: Path | None = None):
        self.console = Console()
        self.event_bus = get_async_event_bus()

        # Get orchestrator instance
        self.orchestrator = get_orchestrator(db_path=orchestrator_db_path)

        # Worker state tracking (from events)
        self.workers: dict[str, dict[str, Any]] = {}
        self.recent_activity: list[dict[str, Any]] = []
        self.escalations: list[dict[str, Any]] = []

        # Performance metrics
        self.total_tasks = 0
        self.total_violations_fixed = 0
        self.total_escalations = 0

        # Queue metrics (updated from orchestrator)
        self.queue_metrics: dict[str, Any] = {}
        self.pool_metrics: dict[str, Any] = {}

        self.start_time = datetime.now(UTC)

    async def handle_worker_heartbeat(self, event: WorkerHeartbeat) -> None:
        """Update worker state from heartbeat."""
        worker_id = event.payload.get("worker_id", "unknown")

        self.workers[worker_id] = {
            "status": event.payload.get("status", "unknown"),
            "tasks_completed": event.payload.get("tasks_completed", 0),
            "violations_fixed": event.payload.get("violations_fixed", 0),
            "escalations": event.payload.get("escalations", 0),
            "uptime_seconds": event.payload.get("uptime_seconds", 0),
            "last_seen": datetime.now(UTC),
        }

    async def handle_worker_registration(self, event: WorkerRegistration) -> None:
        """Handle new worker registration."""
        worker_id = event.payload.get("worker_id", "unknown")
        worker_type = event.payload.get("worker_type", "unknown")

        self.workers[worker_id] = {
            "type": worker_type,
            "status": "idle",
            "tasks_completed": 0,
            "violations_fixed": 0,
            "escalations": 0,
            "uptime_seconds": 0,
            "last_seen": datetime.now(UTC),
        }

        self.add_activity(f"Worker {worker_id} ({worker_type}) registered", "info")

    async def handle_qa_task_event(self, event: QATaskEvent) -> None:
        """Handle QA task lifecycle events."""
        task_id = event.payload.get("task_id", "unknown")
        event_type = event.event_type
        worker_id = event.payload.get("worker_id", "unknown")

        if event_type == "queued":
            priority = event.payload.get("priority", "normal")
            self.add_activity(f"Task {task_id} queued with {priority} priority", "info")

        elif event_type == "assigned":
            self.add_activity(f"[{worker_id}] Task {task_id} assigned", "info")

        elif event_type == "started":
            self.add_activity(f"[{worker_id}] Started task {task_id}", "info")

        elif event_type == "completed":
            violations_fixed = event.payload.get("violations_fixed", 0)
            violations_remaining = event.payload.get("violations_remaining", 0)
            exec_time = event.payload.get("execution_time_ms", 0)

            self.total_tasks += 1
            self.total_violations_fixed += violations_fixed

            status = event.payload.get("status", "success")
            if status == "success":
                self.add_activity(
                    f"[{worker_id}] ✅ Fixed {violations_fixed} violations in {exec_time}ms",
                    "success",
                )
            elif status == "escalated":
                self.add_activity(
                    f"[{worker_id}] ⚠️ Escalated: {violations_remaining} violations remain",
                    "warning",
                )

        elif event_type == "failed":
            error = event.payload.get("error", "Unknown error")
            self.add_activity(f"[{worker_id}] ❌ Task {task_id} failed: {error}", "error")

    async def handle_escalation(self, event: EscalationEvent) -> None:
        """Handle escalation events."""
        task_id = event.payload.get("task_id", "unknown")
        worker_id = event.payload.get("worker_id", "unknown")
        reason = event.payload.get("reason", "Unknown reason")

        self.total_escalations += 1

        escalation = {
            "task_id": task_id,
            "worker_id": worker_id,
            "reason": reason,
            "timestamp": datetime.now(UTC),
            "details": event.payload.get("details", {}),
        }

        self.escalations.append(escalation)

        self.add_activity(
            f"[{worker_id}] 🚨 ESCALATION: {task_id} - {reason}", "escalation",
        )

    def add_activity(self, message: str, level: str = "info") -> None:
        """Add activity to recent feed."""
        self.recent_activity.append(
            {
                "timestamp": datetime.now(UTC),
                "message": message,
                "level": level,
            },
        )

        # Keep only last 30 activities
        if len(self.recent_activity) > 30:
            self.recent_activity.pop(0)

    async def update_orchestrator_metrics(self) -> None:
        """Update metrics from orchestrator."""
        try:
            status = await self.orchestrator.get_status()
            self.queue_metrics = status.get("queue", {})
            self.pool_metrics = status.get("pool", {})
        except Exception as e:
            logger.error(f"Failed to update orchestrator metrics: {e}")

    def make_queue_panel(self) -> Panel:
        """Create task queue visualization panel."""
        if not self.queue_metrics:
            return Panel("No queue metrics available", title="Task Queue", border_style="yellow")

        queue_depth = self.queue_metrics.get("queue_depth", 0)
        queue_depths = self.queue_metrics.get("queue_depths_by_priority", {})

        # Create progress bars for each priority level
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )

        # Total capacity (workers * target per worker)
        total_workers = self.pool_metrics.get("active_workers", 1)
        target_per_worker = 5  # From orchestrator config
        capacity = total_workers * target_per_worker

        # Add tasks for each priority
        high_count = queue_depths.get("high", 0)
        normal_count = queue_depths.get("normal", 0)
        low_count = queue_depths.get("low", 0)

        high_task = progress.add_task(
            "🔴 High Priority", total=capacity, completed=high_count,
        )
        normal_task = progress.add_task(
            "🟡 Normal Priority", total=capacity, completed=normal_count,
        )
        low_task = progress.add_task(
            "🟢 Low Priority", total=capacity, completed=low_count,
        )

        queue_text = Text()
        queue_text.append(f"Total Depth: ", style="bold")
        queue_text.append(f"{queue_depth}\n", style="cyan")
        queue_text.append(f"Capacity: ", style="bold")
        queue_text.append(f"{capacity} ({total_workers} workers × {target_per_worker})\n")
        queue_text.append(f"Utilization: ", style="bold")
        utilization = (queue_depth / capacity * 100) if capacity > 0 else 0
        queue_text.append(f"{utilization:.1f}%\n\n")

        # Combine text and progress
        return Panel(
            Text.assemble(queue_text, "\n", progress),
            title="📋 Task Queue",
            border_style="blue",
        )

    def make_worker_table(self) -> Table:
        """Create worker status table."""
        table = Table(title="Worker Fleet Status", show_header=True, header_style="bold")

        table.add_column("Worker ID", style="cyan", no_wrap=True)
        table.add_column("Status", style="green")
        table.add_column("Tasks", justify="right")
        table.add_column("Fixed", justify="right")
        table.add_column("Esc", justify="right")
        table.add_column("Uptime", justify="right")
        table.add_column("Last Seen", style="dim")

        # Check for stale workers
        now = datetime.now(UTC)
        stale_threshold = timedelta(seconds=30)

        for worker_id, data in sorted(self.workers.items()):
            last_seen = data.get("last_seen", now)
            is_stale = (now - last_seen) > stale_threshold

            # Status emoji
            status = data.get("status", "unknown")
            status_emoji = {
                "idle": "✅",
                "working": "🔄",
                "error": "❌",
                "offline": "⚫",
            }.get(status, "❓")

            if is_stale:
                status_emoji = "⚫"
                status = "OFFLINE"

            # Format uptime
            uptime_sec = data.get("uptime_seconds", 0)
            hours = int(uptime_sec // 3600)
            minutes = int((uptime_sec % 3600) // 60)
            uptime_str = f"{hours}h {minutes}m"

            # Format last seen
            time_since = (now - last_seen).total_seconds()
            if time_since < 60:
                last_seen_str = f"{int(time_since)}s ago"
            else:
                last_seen_str = f"{int(time_since // 60)}m ago"

            table.add_row(
                worker_id,
                f"{status_emoji} {status.upper()}",
                str(data.get("tasks_completed", 0)),
                str(data.get("violations_fixed", 0)),
                str(data.get("escalations", 0)),
                uptime_str,
                last_seen_str,
            )

        if not self.workers:
            table.add_row("No workers online", "", "", "", "", "", "")

        return table

    def make_activity_panel(self) -> Panel:
        """Create recent activity panel."""
        if not self.recent_activity:
            return Panel("No recent activity", title="Recent Activity")

        lines = []
        for activity in reversed(self.recent_activity[-10:]):
            timestamp = activity["timestamp"].strftime("%H:%M:%S")
            message = activity["message"]
            level = activity["level"]

            # Color by level
            if level == "success":
                style = "green"
            elif level == "warning":
                style = "yellow"
            elif level == "error":
                style = "red"
            elif level == "escalation":
                style = "bold red"
            else:
                style = "white"

            lines.append(Text(f"{timestamp} {message}", style=style))

        return Panel(
            Text.assemble(*[line + Text("\n") for line in lines]),
            title="📝 Recent Activity (Last 10)",
            border_style="blue",
        )

    def make_metrics_panel(self) -> Panel:
        """Create performance metrics panel."""
        uptime = (datetime.now(UTC) - self.start_time).total_seconds()
        uptime_str = f"{int(uptime // 60)}m {int(uptime % 60)}s"

        metrics_text = Text()

        # Queue metrics
        metrics_text.append("📊 Queue Metrics\n", style="bold underline")
        metrics_text.append(f"  Total Queued: ", style="bold")
        metrics_text.append(f"{self.queue_metrics.get('total_queued', 0)}\n")
        metrics_text.append(f"  Total Completed: ", style="bold green")
        metrics_text.append(f"{self.queue_metrics.get('total_completed', 0)}\n")
        metrics_text.append(f"  Total Failed: ", style="bold red")
        metrics_text.append(f"{self.queue_metrics.get('total_failed', 0)}\n")
        metrics_text.append(f"  Avg Wait Time: ", style="bold")
        avg_wait = self.queue_metrics.get("avg_wait_time_seconds", 0)
        metrics_text.append(f"{avg_wait:.1f}s\n")
        metrics_text.append(f"  Avg Exec Time: ", style="bold")
        avg_exec = self.queue_metrics.get("avg_execution_time_seconds", 0)
        metrics_text.append(f"{avg_exec:.1f}s\n\n")

        # Pool metrics
        metrics_text.append("👥 Pool Metrics\n", style="bold underline")
        metrics_text.append(f"  Pool Size: ", style="bold")
        metrics_text.append(f"{self.pool_metrics.get('pool_size', 0)}\n")
        metrics_text.append(f"  Active Workers: ", style="bold green")
        metrics_text.append(f"{self.pool_metrics.get('active_workers', 0)}\n")
        metrics_text.append(f"  Idle Workers: ", style="bold")
        metrics_text.append(f"{self.pool_metrics.get('idle_workers', 0)}\n")
        metrics_text.append(f"  Scale Ups: ", style="bold cyan")
        metrics_text.append(f"{self.pool_metrics.get('scale_up_count', 0)}\n")
        metrics_text.append(f"  Scale Downs: ", style="bold")
        metrics_text.append(f"{self.pool_metrics.get('scale_down_count', 0)}\n")
        metrics_text.append(f"  Restarts: ", style="bold yellow")
        metrics_text.append(f"{self.pool_metrics.get('restart_count', 0)}\n\n")

        # Overall metrics
        metrics_text.append("📈 Overall\n", style="bold underline")
        metrics_text.append(f"  Monitor Uptime: ", style="bold")
        metrics_text.append(f"{uptime_str}\n")

        # Calculate success rate
        total_completed = self.queue_metrics.get("total_completed", 0)
        total_failed = self.queue_metrics.get("total_failed", 0)
        total_processed = total_completed + total_failed

        if total_processed > 0:
            success_rate = (total_completed / total_processed * 100)
            metrics_text.append(f"  Success Rate: ", style="bold")
            metrics_text.append(f"{success_rate:.1f}%\n")

        return Panel(metrics_text, title="📊 Metrics", border_style="green")

    def make_escalations_panel(self) -> Panel:
        """Create escalations panel."""
        if not self.escalations:
            return Panel("No escalations", title="Escalations", border_style="yellow")

        # Show last 5 escalations
        lines = []
        for esc in reversed(self.escalations[-5:]):
            timestamp = esc["timestamp"].strftime("%H:%M:%S")
            task_id = esc["task_id"]
            worker_id = esc["worker_id"]
            reason = esc["reason"]

            lines.append(
                Text(f"{timestamp} [{worker_id}] {task_id}: {reason}", style="yellow"),
            )

        return Panel(
            Text.assemble(*[line + Text("\n") for line in lines]),
            title=f"🚨 Escalations ({len(self.escalations)} total)",
            border_style="yellow",
        )

    def make_layout(self) -> Layout:
        """Create enhanced dashboard layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=1),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )

        layout["body"].split_row(
            Layout(name="left", ratio=2), Layout(name="right", ratio=1),
        )

        layout["left"].split_column(
            Layout(name="queue", size=12),
            Layout(name="workers"),
            Layout(name="activity", size=15),
        )

        layout["right"].split_column(
            Layout(name="metrics"), Layout(name="escalations", size=12),
        )

        # Header
        header_text = Text(
            "Enhanced Worker Fleet Monitor (Phase 2)", style="bold white on blue", justify="center",
        )
        layout["header"].update(Panel(header_text))

        # Queue visualization
        layout["queue"].update(self.make_queue_panel())

        # Worker table
        layout["workers"].update(self.make_worker_table())

        # Activity feed
        layout["activity"].update(self.make_activity_panel())

        # Metrics
        layout["metrics"].update(self.make_metrics_panel())

        # Escalations
        layout["escalations"].update(self.make_escalations_panel())

        # Footer
        footer_text = Text(
            "Press Ctrl+C to exit | Updates every 500ms | Phase 2: Queue + Auto-Scaling",
            style="dim",
            justify="center",
        )
        layout["footer"].update(Panel(footer_text, style="dim"))

        return layout

    async def subscribe_to_events(self) -> None:
        """Subscribe to worker fleet events."""
        await self.event_bus.subscribe("heartbeat", self.handle_worker_heartbeat)
        await self.event_bus.subscribe("registered", self.handle_worker_registration)
        await self.event_bus.subscribe("queued", self.handle_qa_task_event)
        await self.event_bus.subscribe("assigned", self.handle_qa_task_event)
        await self.event_bus.subscribe("started", self.handle_qa_task_event)
        await self.event_bus.subscribe("completed", self.handle_qa_task_event)
        await self.event_bus.subscribe("failed", self.handle_qa_task_event)
        await self.event_bus.subscribe("escalation_needed", self.handle_escalation)

        logger.info("Subscribed to worker fleet events")

    async def run(self) -> None:
        """Run the enhanced monitoring dashboard."""
        logger.info("Starting enhanced worker fleet monitor (Phase 2)")

        await self.subscribe_to_events()

        # Start orchestrator
        await self.orchestrator.start()

        with Live(self.make_layout(), console=self.console, refresh_per_second=2) as live:
            try:
                while True:
                    # Update orchestrator metrics
                    await self.update_orchestrator_metrics()

                    # Update display
                    await asyncio.sleep(0.5)
                    live.update(self.make_layout())

            except KeyboardInterrupt:
                logger.info("Monitor shutting down...")
                await self.orchestrator.stop()


async def main():
    """CLI entry point for enhanced fleet monitor."""
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Worker Fleet Monitor (Phase 2)")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Orchestrator database path (default: PROJECT_ROOT/hive.db)",
    )

    args = parser.parse_args()

    monitor = EnhancedFleetMonitor(orchestrator_db_path=args.db_path)
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
