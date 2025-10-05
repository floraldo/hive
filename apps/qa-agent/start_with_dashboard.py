#!/usr/bin/env python3
"""Start QA Agent with Live Dashboard.

This script starts the QA Agent daemon and displays a live dashboard showing:
- Tasks processed
- Worker routing decisions
- Real-time status updates

Run: python start_with_dashboard.py
"""

import asyncio
import sys
from datetime import datetime

# Add all required packages to path
for pkg in [  # noqa: E501
    'hive-logging', 'hive-config', 'hive-errors', 'hive-db',
    'hive-bus', 'hive-models', 'hive-async', 'hive-orchestration'
]:
    sys.path.insert(0, f'C:/git/hive/packages/{pkg}/src')
sys.path.insert(0, 'C:/git/hive/apps/qa-agent/src')

from qa_agent.daemon import QAAgentDaemon  # noqa: E402


class DashboardWrapper:
    """Wrapper that adds live dashboard output to daemon."""

    def __init__(self, daemon: QAAgentDaemon):
        self.daemon = daemon
        self.start_time = datetime.now()

    async def start(self):
        """Start daemon with dashboard."""
        print("\033[2J\033[H")  # Clear screen
        self.print_header()

        # Start daemon in background
        daemon_task = asyncio.create_task(self.daemon.start())

        # Wait for daemon to initialize
        await asyncio.sleep(0.5)

        # Run dashboard updates
        try:
            while not daemon_task.done():
                await asyncio.sleep(2.0)
                self.update_dashboard()
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            self.daemon.running = False
            await daemon_task

    def print_header(self):
        """Print dashboard header."""
        print("=" * 80)
        print("QA AGENT LIVE DASHBOARD")
        print("=" * 80)
        print()
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Polling: {self.daemon.poll_interval}s")
        print(f"Max Chimera: {self.daemon.max_concurrent_chimera}")
        print(f"Max CC Workers: {self.daemon.max_concurrent_cc_workers}")
        print()
        print("=" * 80)
        print()
        print("Press Ctrl+C to stop")
        print()

    def update_dashboard(self):
        """Update dashboard with current metrics."""
        uptime = (datetime.now() - self.start_time).total_seconds()

        # Move cursor to metrics section (line 15)
        print("\033[15;1H")
        print("METRICS" + " " * 73)
        print("-" * 80)

        print(f"Uptime: {int(uptime)}s" + " " * 60)
        print(f"Tasks Processed: {self.daemon.tasks_processed}" + " " * 50)
        print(f"  - Chimera Agents: {self.daemon.tasks_chimera}" + " " * 45)
        print(f"  - CC Workers: {self.daemon.tasks_cc_worker}" + " " * 48)
        print(f"  - Escalated (HITL): {self.daemon.tasks_escalated}" + " " * 42)
        print(f"  - Failed: {self.daemon.tasks_failed}" + " " * 52)
        print()

        if self.daemon.tasks_processed > 0:
            chimera_pct = (self.daemon.tasks_chimera / self.daemon.tasks_processed) * 100
            cc_pct = (self.daemon.tasks_cc_worker / self.daemon.tasks_processed) * 100
            escalation_pct = (self.daemon.tasks_escalated / self.daemon.tasks_processed) * 100

            print("ROUTING DISTRIBUTION" + " " * 59)
            print(f"  Chimera: {chimera_pct:.1f}% {'█' * int(chimera_pct / 5)}" + " " * 30)
            print(f"  CC Workers: {cc_pct:.1f}% {'█' * int(cc_pct / 5)}" + " " * 30)
            print(f"  HITL: {escalation_pct:.1f}% {'█' * int(escalation_pct / 5)}" + " " * 30)
        else:
            print("Waiting for tasks..." + " " * 58)

        print()
        print("-" * 80)
        print("Watching orchestrator queue...")
        print(" " * 80)


async def main():
    """Start QA Agent with dashboard."""
    print("Initializing QA Agent...")

    daemon = QAAgentDaemon(
        poll_interval=5.0,
        max_concurrent_chimera=3,
        max_concurrent_cc_workers=2
    )

    dashboard = DashboardWrapper(daemon)
    await dashboard.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDashboard closed")
        sys.exit(0)
