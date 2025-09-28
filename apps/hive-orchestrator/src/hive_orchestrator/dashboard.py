from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
Hive Real-Time Dashboard
Interactive terminal dashboard for monitoring the entire Hive system.
Uses the rich library for beautiful terminal UI with live updates.
"""

import time
import json
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.columns import Columns
from rich.text import Text
from rich import box

# Import database functions from the orchestrator's core
from hive_orchestrator.core.db import get_connection, close_connection


class HiveDashboard:
    """Real-time dashboard for Hive orchestration monitoring."""

    def __init__(self):
        self.console = Console()
        self.refresh_rate = 2  # seconds

    def get_task_stats(self) -> Dict[str, int]:
        """Get task counts by status."""
        conn = get_connection()
        cursor = conn.cursor()

        stats = {}
        statuses = ['queued', 'assigned', 'in_progress', 'review_pending',
                   'approved', 'rejected', 'rework_needed', 'escalated',
                   'completed', 'failed', 'cancelled']

        for status in statuses:
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", (status,))
            stats[status] = cursor.fetchone()[0]

        return stats

    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent tasks with their details."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, task_type, status, priority,
                   assigned_worker, created_at, updated_at
            FROM tasks
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))

        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'id': row[0],
                'title': row[1],
                'task_type': row[2],
                'status': row[3],
                'priority': row[4],
                'assigned_worker': row[5],
                'created_at': row[6],
                'updated_at': row[7]
            })

        return tasks

    def get_escalated_tasks(self) -> List[Dict[str, Any]]:
        """Get tasks requiring human review."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, priority, created_at, result_data
            FROM tasks
            WHERE status = 'escalated'
            ORDER BY priority DESC, created_at ASC
            LIMIT 5
        """)

        escalated = []
        for row in cursor.fetchall():
            # Parse result data to get AI score
            result_data = json.loads(row[4]) if row[4] else {}
            review = result_data.get('review', {})

            escalated.append({
                'id': row[0],
                'title': row[1],
                'priority': row[2],
                'created_at': row[3],
                'ai_score': review.get('overall_score', 0),
                'reason': result_data.get('escalation_reason', 'Review needed')
            })

        return escalated

    def get_worker_info(self) -> List[Dict[str, Any]]:
        """Get information about active workers."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, role, status, current_task_id,
                   last_heartbeat, registered_at
            FROM workers
            ORDER BY last_heartbeat DESC
        """)

        workers = []
        for row in cursor.fetchall():
            workers.append({
                'id': row[0],
                'role': row[1],
                'status': row[2],
                'current_task_id': row[3],
                'last_heartbeat': row[4],
                'registered_at': row[5]
            })

        return workers

    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent task execution runs."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT r.id, r.task_id, t.title, r.worker_id,
                   r.status, r.phase, r.started_at, r.completed_at
            FROM runs r
            JOIN tasks t ON r.task_id = t.id
            ORDER BY r.started_at DESC
            LIMIT ?
        """, (limit,))

        runs = []
        for row in cursor.fetchall():
            runs.append({
                'id': row[0],
                'task_id': row[1],
                'task_title': row[2],
                'worker_id': row[3],
                'status': row[4],
                'phase': row[5],
                'started_at': row[6],
                'completed_at': row[7]
            })

        return runs

    def create_escalation_panel(self) -> Panel:
        """Create escalation alert panel for human review tasks."""
        escalated = self.get_escalated_tasks()

        if not escalated:
            return None  # Don't show panel if no escalated tasks

        # Create alert content
        alert_lines = []
        alert_lines.append("[bold red blink]🚨 ACTION REQUIRED: HUMAN REVIEW NEEDED 🚨[/bold red blink]\n")

        # Create mini table for escalated tasks
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Title", width=25)
        table.add_column("Priority", justify="center", width=8)
        table.add_column("Age", width=8)
        table.add_column("AI Score", justify="center", width=8)

        for task in escalated:
            # Calculate age
            created = datetime.fromisoformat(task['created_at'])
            age = datetime.now() - created
            if age.days > 0:
                age_str = f"{age.days}d"
                age_color = "red" if age.days > 2 else "yellow"
            else:
                hours = age.seconds // 3600
                age_str = f"{hours}h"
                age_color = "yellow" if hours > 12 else "white"

            table.add_row(
                task['id'][:12],
                task['title'][:25],
                f"P{task['priority']}",
                f"[{age_color}]{age_str}[/{age_color}]",
                f"{task['ai_score']:.0f}" if task['ai_score'] else "N/A"
            )

        # Create panel with alert styling
        panel = Panel(
            table,
            title=f"[bold red]{len(escalated)} Tasks Escalated for Review[/bold red]",
            box=box.DOUBLE,
            border_style="red",
            padding=(0, 1)
        )

        return panel

    def create_status_table(self) -> Table:
        """Create the status overview table."""
        stats = self.get_task_stats()

        table = Table(title="Task Pipeline Status", box=box.ROUNDED)

        # First row - main pipeline
        table.add_column("Queued", style="white", justify="center")
        table.add_column("Assigned", style="cyan", justify="center")
        table.add_column("In Progress", style="yellow", justify="center")
        table.add_column("Review", style="magenta", justify="center")
        table.add_column("Completed", style="green", justify="center")
        table.add_column("Failed", style="red", justify="center")

        table.add_row(
            str(stats.get('queued', 0)),
            str(stats.get('assigned', 0)),
            str(stats.get('in_progress', 0)),
            str(stats.get('review_pending', 0)),
            str(stats.get('completed', 0)),
            str(stats.get('failed', 0))
        )

        # Add review status if there are any
        if any(stats.get(s, 0) > 0 for s in ['approved', 'rejected', 'rework_needed', 'escalated']):
            review_table = Table(title="AI Review Status", box=box.ROUNDED)
            review_table.add_column("Approved", style="green", justify="center")
            review_table.add_column("Rejected", style="red", justify="center")
            review_table.add_column("Rework", style="yellow", justify="center")
            review_table.add_column("Escalated", style="red bold", justify="center")

            review_table.add_row(
                str(stats.get('approved', 0)),
                str(stats.get('rejected', 0)),
                str(stats.get('rework_needed', 0)),
                f"[red bold]{stats.get('escalated', 0)}[/red bold]" if stats.get('escalated', 0) > 0 else "0"
            )

            return Columns([table, review_table])

        return table

    def create_tasks_table(self) -> Table:
        """Create the recent tasks table."""
        tasks = self.get_recent_tasks(8)

        table = Table(title="Recent Tasks", box=box.ROUNDED)
        table.add_column("ID", style="dim", width=8)
        table.add_column("Title", width=30)
        table.add_column("Type", width=12)
        table.add_column("Status", width=12)
        table.add_column("Priority", justify="center", width=8)
        table.add_column("Worker", width=15)

        status_colors = {
            'queued': 'white',
            'assigned': 'cyan',
            'in_progress': 'yellow',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'dim'
        }

        for task in tasks:
            status_color = status_colors.get(task['status'], 'white')
            table.add_row(
                task['id'][:8],
                task['title'][:30],
                task['task_type'],
                f"[{status_color}]{task['status']}[/{status_color}]",
                str(task['priority']),
                task['assigned_worker'] or '-'
            )

        return table

    def create_workers_table(self) -> Table:
        """Create the workers status table."""
        workers = self.get_worker_info()

        table = Table(title="Active Workers", box=box.ROUNDED)
        table.add_column("ID", style="dim", width=8)
        table.add_column("Role", width=12)
        table.add_column("Status", width=10)
        table.add_column("Current Task", width=20)
        table.add_column("Last Heartbeat", width=15)

        status_colors = {
            'active': 'green',
            'idle': 'yellow',
            'offline': 'red',
            'error': 'red bold'
        }

        for worker in workers:
            status_color = status_colors.get(worker['status'], 'white')

            # Calculate time since last heartbeat
            if worker['last_heartbeat']:
                last_hb = datetime.fromisoformat(worker['last_heartbeat'])
                time_diff = datetime.now() - last_hb
                hb_text = f"{int(time_diff.total_seconds())}s ago"
            else:
                hb_text = "Never"

            table.add_row(
                worker['id'][:8],
                worker['role'],
                f"[{status_color}]{worker['status']}[/{status_color}]",
                worker['current_task_id'][:20] if worker['current_task_id'] else '-',
                hb_text
            )

        return table

    def create_runs_table(self) -> Table:
        """Create the recent runs table."""
        runs = self.get_recent_runs(8)

        table = Table(title="Recent Execution Runs", box=box.ROUNDED)
        table.add_column("Run ID", style="dim", width=8)
        table.add_column("Task", width=25)
        table.add_column("Worker", width=8)
        table.add_column("Status", width=10)
        table.add_column("Phase", width=15)
        table.add_column("Duration", width=10)

        status_colors = {
            'pending': 'white',
            'running': 'yellow',
            'success': 'green',
            'failure': 'red',
            'timeout': 'red bold',
            'cancelled': 'dim'
        }

        for run in runs:
            status_color = status_colors.get(run['status'], 'white')

            # Calculate duration
            if run['started_at'] and run['completed_at']:
                start = datetime.fromisoformat(run['started_at'])
                end = datetime.fromisoformat(run['completed_at'])
                duration = end - start
                duration_text = f"{int(duration.total_seconds())}s"
            elif run['started_at']:
                start = datetime.fromisoformat(run['started_at'])
                duration = datetime.now() - start
                duration_text = f"{int(duration.total_seconds())}s"
            else:
                duration_text = "-"

            table.add_row(
                run['id'][:8],
                run['task_title'][:25],
                run['worker_id'][:8],
                f"[{status_color}]{run['status']}[/{status_color}]",
                run['phase'] or '-',
                duration_text
            )

        return table

    def create_dashboard(self) -> Layout:
        """Create the full dashboard layout."""
        layout = Layout()

        # Check for escalated tasks
        escalation_panel = self.create_escalation_panel()

        # Adjust layout based on whether we have escalated tasks
        if escalation_panel:
            # With escalation alert - make it prominent
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="escalation", size=8),  # Prominent alert
                Layout(name="status", size=5),
                Layout(name="main", size=18),
                Layout(name="footer", size=3)
            )
            layout["escalation"].update(escalation_panel)
        else:
            # Normal layout without escalation
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="status", size=5),
                Layout(name="main", size=20),
                Layout(name="footer", size=3)
            )

        # Header
        header_text = Text.from_markup(
            "[bold cyan]HIVE FLEET COMMAND DASHBOARD[/bold cyan]\n" +
            f"[dim]Real-time System Monitor • Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
        )
        layout["header"].update(Panel(header_text, box=box.DOUBLE))

        # Status overview
        layout["status"].update(self.create_status_table())

        # Main area - split into columns
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )

        # Left side - Tasks and Workers
        layout["left"].split_column(
            Layout(self.create_tasks_table(), name="tasks", ratio=2),
            Layout(self.create_workers_table(), name="workers", ratio=1)
        )

        # Right side - Runs
        layout["right"].update(self.create_runs_table())

        # Footer
        footer_text = Text.from_markup(
            "[dim]Press Ctrl+C to exit • Refreshes every 2 seconds • Database: hive/db/hive-internal.db[/dim]"
        )
        layout["footer"].update(Panel(footer_text, box=box.ROUNDED))

        return layout

    def run(self):
        """Run the dashboard with live updates."""
        try:
            with Live(self.create_dashboard(), refresh_per_second=0.5, console=self.console) as live:
                while True:
                    time.sleep(self.refresh_rate)
                    live.update(self.create_dashboard())

        except KeyboardInterrupt:
            self.console.logger.info("\n[yellow]Dashboard stopped by user.[/yellow]")
        finally:
            close_connection()
            self.console.logger.info("[green]Database connection closed.[/green]")


def main():
    """Entry point for the dashboard."""
    dashboard = HiveDashboard()
    dashboard.run()


if __name__ == "__main__":
    main()