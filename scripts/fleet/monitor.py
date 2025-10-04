"""Worker Fleet Monitor - Real-time Dashboard

Displays real-time status of autonomous QA worker fleet with:
- Worker health and status
- Active tasks and completion metrics
- Recent activity feed
- Escalation notifications

Uses rich library for terminal UI.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from hive_orchestration.events import (
    EscalationEvent,
    QATaskEvent,
    WorkerHeartbeat,
    WorkerRegistration,
    get_async_event_bus,
)
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from hive_logging import get_logger

logger = get_logger(__name__)


class WorkerFleetMonitor:
    """Real-time monitoring dashboard for worker fleet.

    Features:
    - Live worker status table
    - Recent activity feed (last 20 events)
    - Escalation notifications
    - Performance metrics
    - Auto-refresh every 500ms
    """

    def __init__(self):
        self.console = Console()
        self.event_bus = get_async_event_bus()

        # Worker state tracking
        self.workers: dict[str, dict[str, Any]] = {}
        self.recent_activity: list[dict[str, Any]] = []
        self.escalations: list[dict[str, Any]] = []

        # Performance metrics
        self.total_tasks = 0
        self.total_violations_fixed = 0
        self.total_escalations = 0

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

        if event_type == "started":
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

        # Keep only last 20 activities
        if len(self.recent_activity) > 20:
            self.recent_activity.pop(0)

    def make_worker_table(self) -> Table:
        """Create worker status table."""
        table = Table(title="Worker Fleet Status", show_header=True, header_style="bold")

        table.add_column("Worker ID", style="cyan", no_wrap=True)
        table.add_column("Status", style="green")
        table.add_column("Tasks", justify="right")
        table.add_column("Fixed", justify="right")
        table.add_column("Escalations", justify="right")
        table.add_column("Uptime", justify="right")
        table.add_column("Last Seen", style="dim")

        # Check for stale workers (no heartbeat in 30s)
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
            title="Recent Activity (Last 10)",
            border_style="blue",
        )

    def make_metrics_panel(self) -> Panel:
        """Create performance metrics panel."""
        uptime = (datetime.now(UTC) - self.start_time).total_seconds()
        uptime_str = f"{int(uptime // 60)}m {int(uptime % 60)}s"

        metrics_text = Text()
        metrics_text.append("📊 Total Tasks: ", style="bold")
        metrics_text.append(f"{self.total_tasks}\n")
        metrics_text.append("✅ Violations Fixed: ", style="bold green")
        metrics_text.append(f"{self.total_violations_fixed}\n")
        metrics_text.append("🚨 Escalations: ", style="bold yellow")
        metrics_text.append(f"{self.total_escalations}\n")
        metrics_text.append("⏱️  Monitor Uptime: ", style="bold")
        metrics_text.append(f"{uptime_str}\n")

        # Calculate success rate
        if self.total_tasks > 0:
            success_rate = (
                (self.total_tasks - self.total_escalations) / self.total_tasks * 100
            )
            metrics_text.append("📈 Auto-Fix Rate: ", style="bold")
            metrics_text.append(f"{success_rate:.1f}%\n")

        return Panel(metrics_text, title="Fleet Metrics", border_style="green")

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
            title=f"Recent Escalations ({len(self.escalations)} total)",
            border_style="yellow",
        )

    def make_layout(self) -> Layout:
        """Create dashboard layout."""
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
            Layout(name="workers"), Layout(name="activity", size=15),
        )

        layout["right"].split_column(
            Layout(name="metrics", size=10), Layout(name="escalations"),
        )

        # Header
        header_text = Text("Worker Fleet Monitor", style="bold white on blue", justify="center")
        layout["header"].update(Panel(header_text))

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
            "Press Ctrl+C to exit | Updates every 500ms", style="dim", justify="center",
        )
        layout["footer"].update(Panel(footer_text, style="dim"))

        return layout

    async def subscribe_to_events(self) -> None:
        """Subscribe to worker fleet events."""
        await self.event_bus.subscribe("heartbeat", self.handle_worker_heartbeat)
        await self.event_bus.subscribe("registered", self.handle_worker_registration)
        await self.event_bus.subscribe("started", self.handle_qa_task_event)
        await self.event_bus.subscribe("completed", self.handle_qa_task_event)
        await self.event_bus.subscribe("failed", self.handle_qa_task_event)
        await self.event_bus.subscribe(
            "escalation_needed", self.handle_escalation,
        )

        logger.info("Subscribed to worker fleet events")

    async def run(self) -> None:
        """Run the monitoring dashboard."""
        logger.info("Starting worker fleet monitor")

        await self.subscribe_to_events()

        with Live(self.make_layout(), console=self.console, refresh_per_second=2) as live:
            try:
                while True:
                    await asyncio.sleep(0.5)
                    live.update(self.make_layout())

            except KeyboardInterrupt:
                logger.info("Monitor shutting down...")


async def main():
    """CLI entry point for fleet monitor."""
    monitor = WorkerFleetMonitor()
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
