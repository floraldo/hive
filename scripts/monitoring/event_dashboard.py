"""Simple event monitoring dashboard.

Provides real-time visualization of event flow for Phase B/C validation.

Usage:
    python scripts/monitoring/event_dashboard.py
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime

from hive_bus import get_global_registry
from hive_config import create_config_from_sources
from hive_logging import get_logger

from .event_monitor import EventMetrics, EventMonitor

logger = get_logger(__name__)


class EventDashboard:
    """Simple terminal-based event dashboard."""

    def __init__(self, history_size: int = 100):
        """Initialize dashboard.

        Args:
            history_size: Number of recent events to track
        """
        self.monitor = EventMonitor(verbose=False)
        self.recent_events = deque(maxlen=history_size)
        self.config = create_config_from_sources()

    def start(self) -> None:
        """Start the dashboard."""
        self.monitor.start()
        logger.info("Event dashboard started")

    def display(self) -> None:
        """Display dashboard (terminal-based)."""
        # Clear screen (works on most terminals)
        print("\033[2J\033[H")

        # Header
        print("=" * 100)
        print(" " * 35 + "HIVE EVENT DASHBOARD")
        print("=" * 100)

        # Configuration status
        print(f"\nConfiguration:")
        print(
            f"  Unified Events:      {'ENABLED' if self.config.features.enable_unified_events else 'DISABLED'}"
        )
        print(
            f"  Dual Write:          {'ENABLED' if self.config.features.enable_dual_write else 'DISABLED'}"
        )
        print(
            f"  Agent Adapters:      {'ENABLED' if self.config.features.enable_agent_adapters else 'DISABLED'}"
        )
        print(
            f"  Event Monitoring:    {'ENABLED' if self.config.features.event_monitoring_enabled else 'DISABLED'}"
        )

        # Agents with unified events
        if self.config.features.unified_events_agents:
            print(
                f"  Active Agents:       {', '.join(self.config.features.unified_events_agents)}"
            )

        # Metrics
        metrics = self.monitor.get_metrics()
        print(f"\nMetrics:")
        print(f"  Total Events:        {metrics['total_events']}")
        print(f"  Events/min:          {metrics['events_per_minute']}")
        print(f"  Avg Latency:         {metrics['average_latency_ms']} ms")
        print(f"  Errors:              {metrics['processing_errors']}")
        print(f"  Runtime:             {metrics['runtime_minutes']} min")

        # Top event types
        print(f"\nTop Event Types:")
        event_types = sorted(
            metrics["events_by_type"].items(), key=lambda x: x[1], reverse=True
        )[:10]

        for event_type, count in event_types:
            bar_length = int(count / max(1, metrics["total_events"]) * 50)
            bar = "█" * bar_length
            print(f"  {event_type:35} {bar} {count}")

        # Recent events
        print(f"\nRecent Events (last {len(self.recent_events)}):")
        print("-" * 100)
        for event in list(self.recent_events)[-10:]:  # Last 10
            timestamp = event.timestamp.strftime("%H:%M:%S")
            print(
                f"  {timestamp} | {event.event_type:30} | "
                f"Correlation: {event.correlation_id[:20]:20} | "
                f"Source: {event.source_agent}"
            )

        print("=" * 100)
        print(
            "\nPress Ctrl+C to stop                                      "
            f"Updated: {datetime.now().strftime('%H:%M:%S')}"
        )

    def run(self, refresh_interval: int = 5) -> None:
        """Run dashboard with auto-refresh.

        Args:
            refresh_interval: Seconds between refreshes
        """
        self.start()

        try:
            while True:
                self.display()
                time.sleep(refresh_interval)
        except KeyboardInterrupt:
            print("\n\nStopping dashboard...")
            self.monitor.print_summary()


def main():
    """Run event dashboard."""
    dashboard = EventDashboard()
    dashboard.run(refresh_interval=5)


if __name__ == "__main__":
    main()
