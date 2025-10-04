"""
Tasks CLI Command

API-first interface for Hive orchestration task management.
Implements Decision 6-C: Dual-Purpose API and UI.

Default output: JSON (machine-readable)
Human output: --pretty flag (rich tables)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

import click

from hive_logging import get_logger
from hive_orchestration.operations import tasks as task_ops

logger = get_logger(__name__)


def parse_relative_time(time_str: str) -> datetime:
    """
    Parse relative time strings into absolute datetime objects.

    Supports formats like:
    - '2d' or '2days' for 2 days ago
    - '1h' or '1hour' for 1 hour ago
    - '30m' or '30min' for 30 minutes ago
    - '1w' or '1week' for 1 week ago

    Args:
        time_str: Relative time string (e.g., '2d', '1h', '30m')

    Returns:
        datetime: Absolute datetime representing the parsed time

    Raises:
        ValueError: If time_str format is invalid
    """
    pattern = r'^(\d+)(d|day|days|h|hour|hours|m|min|minute|minutes|w|week|weeks)$'
    match = re.match(pattern, time_str.lower())

    if not match:
        raise ValueError(
            f"Invalid time format: '{time_str}'. "
            "Expected formats: 2d, 1h, 30m, 1w"
        )

    amount = int(match.group(1))
    unit = match.group(2)

    # Map units to timedelta
    if unit in ('d', 'day', 'days'):
        delta = timedelta(days=amount)
    elif unit in ('h', 'hour', 'hours'):
        delta = timedelta(hours=amount)
    elif unit in ('m', 'min', 'minute', 'minutes'):
        delta = timedelta(minutes=amount)
    elif unit in ('w', 'week', 'weeks'):
        delta = timedelta(weeks=amount)
    else:
        raise ValueError(f"Unsupported time unit: {unit}")

    return datetime.now() - delta


@click.group(name="tasks")
def tasks_group():
    """Manage Hive orchestration tasks."""
    pass


@tasks_group.command(name="list")
@click.option(
    "--status",
    type=click.Choice(['queued', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled']),
    help="Filter by task status"
)
@click.option(
    "--user",
    "--worker",
    "assigned_worker",
    help="Filter by assigned worker/user"
)
@click.option(
    "--limit",
    type=int,
    default=10,
    help="Maximum number of tasks to return"
)
@click.option(
    "--since",
    type=str,
    help="Filter tasks created since relative time (e.g., 2d, 1h, 30m)"
)
@click.option(
    "--pretty",
    is_flag=True,
    help="Display human-readable table (default: JSON)"
)
def list_tasks(
    status: str | None,
    assigned_worker: str | None,
    limit: int,
    since: str | None,
    pretty: bool
):
    """
    List orchestration tasks with optional filters.

    Examples:
        # JSON output (API-first, default)
        hive tasks list

        # Filter by status
        hive tasks list --status completed --limit 5

        # Filter by creation time (relative)
        hive tasks list --since 2d

        # Combined filters with human-readable output
        hive tasks list --since 1h --pretty

        # Filter by time and status
        hive tasks list --since 30m --status completed

        # Human-readable table
        hive tasks list --pretty

        # Filter by worker
        hive tasks list --user worker-1 --pretty
    """
    try:
        # Parse --since filter if provided
        since_timestamp = None
        if since:
            try:
                since_timestamp = parse_relative_time(since)
            except ValueError as e:
                error_msg = str(e)
                if pretty:
                    click.echo(f"Error: {error_msg}", err=True)
                else:
                    click.echo(json.dumps({"error": error_msg}), err=True)
                raise click.Abort() from e

        # Fetch tasks based on filters
        if status:
            task_list = task_ops.get_tasks_by_status(status)
            # Apply limit manually since get_tasks_by_status doesn't support it
            task_list = task_list[:limit]
        else:
            task_list = task_ops.get_queued_tasks(limit=limit)

        # Filter by assigned worker if specified
        if assigned_worker:
            task_list = [
                t for t in task_list
                if t.get('assigned_worker') == assigned_worker
            ]

        # Filter by creation time if --since specified
        if since_timestamp:
            task_list = [
                t for t in task_list
                if t.get('created_at') and
                datetime.fromisoformat(str(t['created_at']).replace('Z', '+00:00')).replace(tzinfo=None) >= since_timestamp
            ]

        # Output format decision: API-first (JSON default)
        if pretty:
            _render_pretty_table(task_list)
        else:
            # JSON output for programmatic usage
            click.echo(json.dumps(task_list, indent=2, default=str))

    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        click.echo(json.dumps({"error": str(e)}), err=True)
        raise click.Abort() from e


@tasks_group.command(name="show")
@click.argument("task_id")
@click.option(
    "--pretty",
    is_flag=True,
    help="Display human-readable format (default: JSON)"
)
def show_task(task_id: str, pretty: bool):
    """
    Show detailed information about a specific task.

    Examples:
        # JSON output (default)
        hive tasks show abc123

        # Human-readable format
        hive tasks show abc123 --pretty
    """
    try:
        task = task_ops.get_task(task_id)

        if not task:
            error_msg = f"Task {task_id} not found"
            if pretty:
                click.echo(f"Error: {error_msg}", err=True)
            else:
                click.echo(json.dumps({"error": error_msg}), err=True)
            raise click.Abort()

        if pretty:
            _render_task_detail(task)
        else:
            click.echo(json.dumps(task, indent=2, default=str))

    except Exception as e:
        logger.error(f"Failed to show task {task_id}: {e}")
        click.echo(json.dumps({"error": str(e)}), err=True)
        raise click.Abort() from e


def _render_pretty_table(task_list: list[dict[str, Any]]) -> None:
    """
    Render tasks as human-readable table using rich.

    Color coding:
    - queued: yellow
    - in_progress: blue
    - completed: green
    - failed: red
    """
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        click.echo("Error: rich library not installed. Use JSON output or install rich.", err=True)
        click.echo(json.dumps(task_list, indent=2, default=str))
        return

    console = Console()
    table = Table(title=f"Hive Tasks ({len(task_list)} results)")

    # Add columns
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Priority", justify="right", style="yellow")
    table.add_column("Worker", style="blue")
    table.add_column("Created", style="dim")

    # Add rows with color-coded status
    status_colors = {
        'queued': 'yellow',
        'assigned': 'cyan',
        'in_progress': 'blue',
        'completed': 'green',
        'failed': 'red',
        'cancelled': 'dim'
    }

    for task in task_list:
        task_id = task.get('id', 'unknown')[:8]
        title = task.get('title', 'Untitled')[:40]
        status = task.get('status', 'unknown')
        priority = str(task.get('priority', 1))
        worker = task.get('assigned_worker', 'unassigned')[:15]
        created = task.get('created_at', '')[:10]  # YYYY-MM-DD

        status_color = status_colors.get(status, 'white')
        status_display = f"[{status_color}]{status}[/{status_color}]"

        table.add_row(
            task_id,
            title,
            status_display,
            priority,
            worker,
            created
        )

    console.print(table)


def _render_task_detail(task: dict[str, Any]) -> None:
    """Render detailed task information in human-readable format."""
    try:
        from rich.console import Console
        from rich.panel import Panel
    except ImportError:
        click.echo("Error: rich library not installed. Use JSON output.", err=True)
        click.echo(json.dumps(task, indent=2, default=str))
        return

    console = Console()

    # Basic info
    task_id = task.get('id', 'unknown')
    title = task.get('title', 'Untitled')
    status = task.get('status', 'unknown')
    description = task.get('description', 'No description')

    # Status color
    status_colors = {
        'queued': 'yellow',
        'in_progress': 'blue',
        'completed': 'green',
        'failed': 'red'
    }
    status_color = status_colors.get(status, 'white')

    # Build detail text
    details = f"""
[bold]Task ID:[/bold] {task_id}
[bold]Title:[/bold] {title}
[bold]Status:[/bold] [{status_color}]{status}[/{status_color}]
[bold]Type:[/bold] {task.get('task_type', 'unknown')}
[bold]Priority:[/bold] {task.get('priority', 1)}
[bold]Worker:[/bold] {task.get('assigned_worker', 'unassigned')}
[bold]Created:[/bold] {task.get('created_at', 'unknown')}
[bold]Updated:[/bold] {task.get('updated_at', 'unknown')}

[bold]Description:[/bold]
{description}
    """.strip()

    # Memory nexus info (if available)
    if task.get('summary'):
        details += f"\n\n[bold cyan]AI Summary:[/bold cyan]\n{task['summary']}"

    if task.get('related_document_ids'):
        doc_ids = json.loads(task['related_document_ids']) if isinstance(task['related_document_ids'], str) else task['related_document_ids']
        details += f"\n\n[bold cyan]Knowledge Fragments:[/bold cyan] {len(doc_ids)} indexed"

    panel = Panel(details, title=f"Task Details: {title[:40]}", border_style="cyan")
    console.print(panel)


# Export for CLI registration
__all__ = ["tasks_group"]
