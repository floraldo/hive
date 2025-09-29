#!/usr/bin/env python3
"""
Real-time Event Dashboard for Hive V4.0 Event-Driven Architecture

This dashboard provides live visualization of events flowing through the Hive system,
enabling monitoring of workflow patterns, agent activity, and system health.
"""

import asyncio
import sys
from datetime import datetime, timedelta

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

try:
    from hive_orchestrator.core.bus import EventSubscriber, get_event_bus

    from hive_logging import get_logger
except ImportError as e:
    logger.error(f"Failed to import Hive packages: {e}")
    sys.exit(1)

console = Console()
logger = get_logger(__name__)


class EventDashboard:
    """
    Real-time dashboard for monitoring Hive event flow and system activity
    """

    def __init__(self):
        """Initialize the event dashboard"""
        self.console = Console()
        self.event_bus = get_event_bus()
        self.recent_events = []
        self.agent_activity = {}
        self.workflow_states = {}
        self.system_stats = {
            "total_events": 0,
            "events_per_minute": 0,
            "active_workflows": 0,
            "agents_online": set(),
            "last_update": datetime.now(),
        }
        self.running = False

        # Dashboard configuration
        self.max_recent_events = 20
        self.stats_window_minutes = 5

        logger.info("Event Dashboard initialized")

    def _subscribe_to_events(self):
        """Subscribe to all events for dashboard monitoring"""
        try:
            # Subscribe to all events using wildcard pattern
            subscription_id = self.event_bus.subscribe(
                pattern="*", callback=self._handle_event, subscriber_name="event-dashboard"
            )
            logger.info(f"Subscribed to all events: {subscription_id}")
            return subscription_id
        except Exception as e:
            logger.error(f"Failed to subscribe to events: {e}")
            return None

    def _handle_event(self, event):
        """Handle incoming events for dashboard display"""
        try:
            # Add to recent events
            self.recent_events.insert(
                0,
                {
                    "timestamp": datetime.now(),
                    "event_type": event.event_type,
                    "source_agent": event.source_agent,
                    "payload": event.payload,
                    "correlation_id": getattr(event, "correlation_id", None),
                },
            )

            # Limit recent events list
            if len(self.recent_events) > self.max_recent_events:
                self.recent_events = self.recent_events[: self.max_recent_events]

            # Update agent activity
            agent = event.source_agent
            if agent not in self.agent_activity:
                self.agent_activity[agent] = {"last_seen": datetime.now(), "event_count": 0, "event_types": set()}

            self.agent_activity[agent]["last_seen"] = datetime.now()
            self.agent_activity[agent]["event_count"] += 1
            self.agent_activity[agent]["event_types"].add(event.event_type)

            # Update workflow states
            correlation_id = getattr(event, "correlation_id", None)
            if correlation_id:
                if correlation_id not in self.workflow_states:
                    self.workflow_states[correlation_id] = {
                        "start_time": datetime.now(),
                        "last_update": datetime.now(),
                        "events": [],
                        "status": "active",
                    }

                self.workflow_states[correlation_id]["last_update"] = datetime.now()
                self.workflow_states[correlation_id]["events"].append(
                    {"timestamp": datetime.now(), "event_type": event.event_type, "source": event.source_agent}
                )

            # Update system stats
            self.system_stats["total_events"] += 1
            self.system_stats["agents_online"].add(agent)
            self.system_stats["last_update"] = datetime.now()

        except Exception as e:
            logger.error(f"Error handling event: {e}")

    def _create_recent_events_table(self) -> Table:
        """Create table showing recent events"""
        table = Table(title="Recent Events (Live)")
        table.add_column("Time", style="cyan", width=10)
        table.add_column("Event Type", style="yellow", width=25)
        table.add_column("Source", style="green", width=15)
        table.add_column("Details", style="white", width=40)

        for event in self.recent_events:
            time_str = event["timestamp"].strftime("%H:%M:%S")
            event_type = event["event_type"]
            source = event["source_agent"]

            # Extract key details from payload
            payload = event.get("payload", {})
            details = []

            if "task_id" in payload:
                details.append(f"Task: {payload['task_id']}")
            if "plan_name" in payload:
                details.append(f"Plan: {payload['plan_name']}")
            if "review_decision" in payload:
                details.append(f"Decision: {payload['review_decision']}")
            if "failure_reason" in payload:
                details.append(f"Error: {payload['failure_reason'][:30]}...")

            details_str = " | ".join(details) if details else "N/A"

            table.add_row(time_str, event_type, source, details_str)

        return table

    def _create_agent_activity_table(self) -> Table:
        """Create table showing agent activity"""
        table = Table(title="Agent Activity")
        table.add_column("Agent", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Last Seen", style="yellow")
        table.add_column("Events", style="white")
        table.add_column("Event Types", style="magenta")

        now = datetime.now()

        for agent, activity in self.agent_activity.items():
            last_seen = activity["last_seen"]
            time_since = now - last_seen

            if time_since.seconds < 60:
                status = "🟢 Active"
                last_seen_str = f"{time_since.seconds}s ago"
            elif time_since.seconds < 300:  # 5 minutes
                status = "🟡 Idle"
                last_seen_str = f"{time_since.seconds // 60}m ago"
            else:
                status = "🔴 Offline"
                last_seen_str = f"{time_since.seconds // 60}m ago"

            event_count = activity["event_count"]
            event_types = ", ".join(list(activity["event_types"])[:3])
            if len(activity["event_types"]) > 3:
                event_types += "..."

            table.add_row(agent, status, last_seen_str, str(event_count), event_types)

        return table

    def _create_workflow_table(self) -> Table:
        """Create table showing active workflows"""
        table = Table(title="Active Workflows")
        table.add_column("Workflow ID", style="cyan", width=20)
        table.add_column("Duration", style="yellow")
        table.add_column("Events", style="white")
        table.add_column("Last Activity", style="green")
        table.add_column("Status", style="magenta")

        now = datetime.now()

        # Show only recent workflows (last hour)
        cutoff = now - timedelta(hours=1)

        active_workflows = {
            wf_id: wf_data for wf_id, wf_data in self.workflow_states.items() if wf_data["last_update"] > cutoff
        }

        for wf_id, wf_data in list(active_workflows.items())[:10]:  # Show top 10
            start_time = wf_data["start_time"]
            last_update = wf_data["last_update"]
            duration = now - start_time

            duration_str = f"{duration.seconds // 60}m {duration.seconds % 60}s"
            event_count = len(wf_data["events"])
            last_activity = f"{(now - last_update).seconds}s ago"

            # Determine status based on recent activity
            if (now - last_update).seconds < 60:
                status = "🟢 Active"
            elif (now - last_update).seconds < 300:
                status = "🟡 Waiting"
            else:
                status = "🔴 Stalled"

            table.add_row(
                wf_id[:18] + "..." if len(wf_id) > 20 else wf_id, duration_str, str(event_count), last_activity, status
            )

        return table

    def _create_system_stats_panel(self) -> Panel:
        """Create system statistics panel"""
        now = datetime.now()
        uptime = now - self.system_stats["last_update"]

        # Calculate events per minute
        window_start = now - timedelta(minutes=self.stats_window_minutes)
        recent_events = [e for e in self.recent_events if e["timestamp"] > window_start]
        events_per_minute = len(recent_events) / self.stats_window_minutes

        # Active workflows in last hour
        cutoff = now - timedelta(hours=1)
        active_workflows = sum(1 for wf_data in self.workflow_states.values() if wf_data["last_update"] > cutoff)

        stats_text = f"""
🎯 Total Events: {self.system_stats["total_events"]}
📈 Events/min: {events_per_minute:.1f}
🔄 Active Workflows: {active_workflows}
🤖 Agents Online: {len(self.system_stats["agents_online"])}
⏰ Last Update: {self.system_stats["last_update"].strftime("%H:%M:%S")}
        """.strip()

        return Panel(stats_text, title="System Statistics", border_style="green")

    def _create_dashboard_layout(self) -> Layout:
        """Create the complete dashboard layout"""
        # Create layout structure
        layout = Layout()

        layout.split_column(Layout(name="header", size=3), Layout(name="main"), Layout(name="footer", size=3))

        layout["main"].split_row(Layout(name="left"), Layout(name="right"))

        layout["left"].split_column(Layout(name="events"), Layout(name="stats", size=10))

        layout["right"].split_column(Layout(name="agents"), Layout(name="workflows"))

        # Populate layout
        layout["header"].update(
            Panel("🚀 Hive V4.0 Event Dashboard - Real-time Agent Communication", style="bold blue")
        )
        layout["events"].update(self._create_recent_events_table())
        layout["stats"].update(self._create_system_stats_panel())
        layout["agents"].update(self._create_agent_activity_table())
        layout["workflows"].update(self._create_workflow_table())
        layout["footer"].update(Panel("Press Ctrl+C to exit", style="dim"))

        return layout

    async def run_async(self):
        """Run the live dashboard"""
        logger.info("Starting Event Dashboard...")

        # Subscribe to events
        subscription_id = self._subscribe_to_events()
        if not subscription_id:
            console.logger.error("[red]Failed to subscribe to events. Exiting.[/red]")
            return

        self.running = True

        try:
            with Live(self._create_dashboard_layout(), refresh_per_second=2, screen=True) as live:
                console.logger.info("[green]Event Dashboard started. Monitoring event flow...[/green]")

                while self.running:
                    # Update the dashboard layout
                    live.update(self._create_dashboard_layout())
                    await asyncio.sleep(0.5)

        except KeyboardInterrupt:
            console.logger.info("\n[yellow]Dashboard stopped by user[/yellow]")
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            console.logger.error(f"[red]Dashboard error: {e}[/red]")
        finally:
            self.running = False
            logger.info("Event Dashboard stopped")

    def show_workflow_trace(self, correlation_id: str):
        """Show detailed trace for a specific workflow"""
        if correlation_id not in self.workflow_states:
            console.logger.info(f"[red]Workflow {correlation_id} not found[/red]")
            return

        workflow = self.workflow_states[correlation_id]

        table = Table(title=f"Workflow Trace: {correlation_id}")
        table.add_column("Time", style="cyan")
        table.add_column("Event Type", style="yellow")
        table.add_column("Source", style="green")

        for event in workflow["events"]:
            time_str = event["timestamp"].strftime("%H:%M:%S")
            table.add_row(time_str, event["event_type"], event["source"])

        console.logger.info(table)

    def show_agent_details(self, agent_name: str):
        """Show detailed information for a specific agent"""
        if agent_name not in self.agent_activity:
            console.logger.info(f"[red]Agent {agent_name} not found[/red]")
            return

        activity = self.agent_activity[agent_name]

        console.logger.info(f"\n[bold cyan]Agent: {agent_name}[/bold cyan]")
        console.logger.info(f"Last Seen: {activity['last_seen']}")
        console.logger.info(f"Total Events: {activity['event_count']}")
        console.logger.info(f"Event Types: {', '.join(activity['event_types'])}")


def main():
    """Main entry point for the dashboard"""
    dashboard = EventDashboard()

    try:
        asyncio.run_async(dashboard.run_async())
    except KeyboardInterrupt:
        console.logger.info("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.logger.error(f"[red]Error: {e}[/red]")
        logger.error(f"Dashboard startup error: {e}")


if __name__ == "__main__":
    main()
