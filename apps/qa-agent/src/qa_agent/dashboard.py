"""Dashboard - Terminal UI for QA Agent Monitoring.

Provides real-time monitoring dashboard for QA agent operations,
worker status, escalations, and performance metrics.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class Dashboard:
    """Terminal UI dashboard for QA agent monitoring.

    Features:
    - Real-time worker status (Chimera + CC workers)
    - Task queue depth and throughput
    - Escalation alerts and HITL status
    - Performance metrics (fix rate, latency, success rate)
    - Event stream from hive-bus

    For MVP, provides text-based output.
    Future: Upgrade to rich/textual for interactive TUI.

    Example:
        dashboard = Dashboard(daemon, monitor, escalation_manager)
        await dashboard.start()  # Runs until Ctrl+C
    """

    def __init__(
        self,
        daemon: Any | None = None,
        monitor: Any | None = None,
        escalation_manager: Any | None = None,
        refresh_interval: float = 2.0,
    ):
        """Initialize dashboard.

        Args:
            daemon: QA agent daemon instance
            monitor: Worker monitor instance
            escalation_manager: Escalation manager instance
            refresh_interval: Display refresh interval (seconds)
        """
        self.daemon = daemon
        self.monitor = monitor
        self.escalation_manager = escalation_manager
        self.refresh_interval = refresh_interval
        self.running = False
        self.logger = logger

    async def start(self) -> None:
        """Start dashboard display loop."""
        self.running = True
        self.logger.info("Dashboard started")

        try:
            while self.running:
                # Clear screen and display dashboard
                self._display_dashboard()

                # Wait for refresh interval
                await asyncio.sleep(self.refresh_interval)

        except KeyboardInterrupt:
            self.logger.info("Dashboard interrupted by user")

        finally:
            self.running = False
            self.logger.info("Dashboard stopped")

    def stop(self) -> None:
        """Stop dashboard."""
        self.running = False

    def _display_dashboard(self) -> None:
        """Display dashboard content."""
        # For MVP, simple text output
        # Future: Use rich or textual for interactive TUI

        # Clear screen (ANSI escape code)
        print("\033[2J\033[H", end="")

        # Header
        print("=" * 80)
        print("QA AGENT DASHBOARD - Real-time Monitoring".center(80))
        print("=" * 80)
        print(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()

        # Daemon status
        self._display_daemon_status()
        print()

        # Worker status
        self._display_worker_status()
        print()

        # Escalation status
        self._display_escalation_status()
        print()

        # Performance metrics
        self._display_performance_metrics()
        print()

        # Footer
        print("=" * 80)
        print("Press Ctrl+C to exit".center(80))
        print("=" * 80)

    def _display_daemon_status(self) -> None:
        """Display daemon status section."""
        print("DAEMON STATUS")
        print("-" * 80)

        if not self.daemon:
            print("  Daemon: Not available")
            return

        # Daemon metrics
        uptime = 0
        if hasattr(self.daemon, "started_at") and self.daemon.started_at:
            uptime = (datetime.now() - self.daemon.started_at).total_seconds()

        print(f"  Status: {'RUNNING' if self.daemon.running else 'STOPPED'}")
        print(f"  Uptime: {self._format_duration(uptime)}")
        print(f"  Poll Interval: {self.daemon.poll_interval}s")
        print(f"  Tasks Processed: {self.daemon.tasks_processed}")
        print(f"    - Chimera: {self.daemon.tasks_chimera}")
        print(f"    - CC Workers: {self.daemon.tasks_cc_worker}")
        print(f"    - Escalated: {self.daemon.tasks_escalated}")
        print(f"    - Failed: {self.daemon.tasks_failed}")

        # Calculate rates
        if self.daemon.tasks_processed > 0:
            chimera_rate = (self.daemon.tasks_chimera / self.daemon.tasks_processed) * 100
            escalation_rate = (self.daemon.tasks_escalated / self.daemon.tasks_processed) * 100
            print(f"  Chimera Rate: {chimera_rate:.1f}%")
            print(f"  Escalation Rate: {escalation_rate:.1f}%")

    def _display_worker_status(self) -> None:
        """Display worker status section."""
        print("WORKER STATUS")
        print("-" * 80)

        # Chimera executor status
        print("  Chimera Agents:")
        if self.daemon and self.daemon.chimera_executor:
            print("    Status: ACTIVE")
            print(f"    Max Concurrent: {self.daemon.max_concurrent_chimera}")
            # TODO: Get actual active workflows count
        else:
            print("    Status: NOT INITIALIZED (Phase 2 integration pending)")

        print()

        # CC worker status
        print("  CC Workers:")
        if self.daemon and self.daemon.cc_spawner:
            worker_count = self.daemon.cc_spawner.get_worker_count()
            print(f"    Active Workers: {worker_count}")
            print(f"    Max Concurrent: {self.daemon.max_concurrent_cc_workers}")

            # List active workers
            if worker_count > 0:
                active_workers = self.daemon.cc_spawner.get_active_workers()
                for worker_id, info in list(active_workers.items())[:5]:  # Show first 5
                    elapsed = (datetime.now() - info["started_at"]).total_seconds()
                    print(f"      - {worker_id}: {info['task_id']} ({self._format_duration(elapsed)})")

                if worker_count > 5:
                    print(f"      ... and {worker_count - 5} more")
        else:
            print("    Status: NOT INITIALIZED (Phase 3 integration pending)")

        print()

        # Monitor status
        print("  Health Monitor:")
        if self.monitor:
            metrics = self.monitor.get_metrics()
            print(f"    Status: {'ACTIVE' if metrics['running'] else 'STOPPED'}")
            print(f"    Total Escalations: {metrics['total_escalations']}")
            print(f"    Failures Detected: {metrics['total_failures_detected']}")
        else:
            print("    Status: NOT INITIALIZED")

    def _display_escalation_status(self) -> None:
        """Display escalation status section."""
        print("ESCALATION STATUS")
        print("-" * 80)

        if not self.escalation_manager:
            print("  Escalation Manager: Not initialized")
            return

        stats = self.escalation_manager.get_escalation_stats()

        print(f"  Total Escalations: {stats['total_escalations']}")
        print(f"  Pending Review: {stats['pending']}")
        print(f"  In Review: {stats['in_review']}")
        print(f"  Resolved: {stats['resolved']}")
        print(f"  Cannot Fix: {stats['cannot_fix']}")
        print(f"  Won't Fix: {stats['wont_fix']}")

        if stats['avg_resolution_time_seconds'] > 0:
            avg_time = self._format_duration(stats['avg_resolution_time_seconds'])
            print(f"  Avg Resolution Time: {avg_time}")

        # Show pending escalations
        pending = self.escalation_manager.get_pending_escalations()
        if pending:
            print()
            print("  Pending Escalations:")
            for esc in pending[:3]:  # Show first 3
                print(f"    - {esc.escalation_id}: {esc.reason[:50]}...")

            if len(pending) > 3:
                print(f"    ... and {len(pending) - 3} more")

    def _display_performance_metrics(self) -> None:
        """Display performance metrics section."""
        print("PERFORMANCE METRICS")
        print("-" * 80)

        if not self.daemon:
            print("  Metrics: Not available")
            return

        # Calculate throughput
        uptime = 0
        if hasattr(self.daemon, "started_at") and self.daemon.started_at:
            uptime = (datetime.now() - self.daemon.started_at).total_seconds()

        if uptime > 0:
            throughput = (self.daemon.tasks_processed / uptime) * 60  # Tasks per minute
            print(f"  Throughput: {throughput:.2f} tasks/min")

        # Success rate
        if self.daemon.tasks_processed > 0:
            success_count = (
                self.daemon.tasks_chimera
                + self.daemon.tasks_cc_worker
                + self.daemon.tasks_escalated
            )
            success_rate = (success_count / self.daemon.tasks_processed) * 100
            failure_rate = (self.daemon.tasks_failed / self.daemon.tasks_processed) * 100

            print(f"  Success Rate: {success_rate:.1f}%")
            print(f"  Failure Rate: {failure_rate:.1f}%")
        else:
            print("  Success Rate: N/A (no tasks processed)")

        # RAG engine metrics
        if self.daemon.rag_engine:
            pattern_count = self.daemon.rag_engine.pattern_count
            print(f"  RAG Patterns Loaded: {pattern_count}")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    def get_status_summary(self) -> dict[str, Any]:
        """Get status summary as dictionary.

        Returns:
            Status summary dictionary
        """
        summary = {
            "timestamp": datetime.now().isoformat(),
            "daemon": {
                "running": self.daemon.running if self.daemon else False,
                "tasks_processed": self.daemon.tasks_processed if self.daemon else 0,
            },
        }

        if self.monitor:
            summary["monitor"] = self.monitor.get_metrics()

        if self.escalation_manager:
            summary["escalations"] = self.escalation_manager.get_escalation_stats()

        return summary


def display_simple_status(daemon: Any) -> None:
    """Display simple status output (non-interactive).

    Args:
        daemon: QA agent daemon instance
    """
    print("\n" + "=" * 80)
    print("QA AGENT STATUS")
    print("=" * 80)

    if daemon:
        print(f"Status: {'RUNNING' if daemon.running else 'STOPPED'}")
        print(f"Tasks Processed: {daemon.tasks_processed}")
        print(f"  - Chimera: {daemon.tasks_chimera}")
        print(f"  - CC Workers: {daemon.tasks_cc_worker}")
        print(f"  - Escalated: {daemon.tasks_escalated}")
        print(f"  - Failed: {daemon.tasks_failed}")
    else:
        print("Status: Daemon not available")

    print("=" * 80 + "\n")


__all__ = ["Dashboard", "display_simple_status"]
