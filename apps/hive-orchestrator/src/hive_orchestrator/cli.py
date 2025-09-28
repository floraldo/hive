from hive_logging import get_logger

logger = get_logger(__name__)
"""
Command-line interface for Hive Orchestrator.

Provides commands to manage the Queen coordinator and Worker agents.
"""

import click
import json
import os
from pathlib import Path
from typing import Optional

from hive_logging import get_logger
from datetime import datetime

logger = get_logger(__name__)

from .queen import main as queen_main
from .worker import main as worker_main


@click.group()
def cli():
    """Hive Orchestrator - Manage Queen and Workers."""
    pass


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True),
              help='Path to configuration file')
@click.option('--debug', is_flag=True, help='Enable debug logging')
def start_queen(config: Optional[str], debug: bool):
    """Start the Queen orchestrator."""
    try:
        args = []
        if config:
            # Validate config file exists and is readable
            config_path = Path(config)
            if not config_path.exists():
                raise click.ClickException(f"Config file not found: {config}")
            if not config_path.is_file():
                raise click.ClickException(f"Config path is not a file: {config}")
            args.extend(['--config', config])
        if debug:
            args.append('--debug')

        # Call the queen main with simulated argv
        import sys
        original_argv = sys.argv
        try:
            sys.argv = ['hive-queen'] + args
            queen_main()
        finally:
            sys.argv = original_argv
    except ImportError as e:
        click.echo(f"Error importing queen module: {e}", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"Error starting queen: {e}", err=True)
        logger.error(f"Queen startup error: {e}")
        raise click.Exit(1)


@cli.command()
@click.option('--mode', '-m', type=click.Choice(['backend', 'frontend', 'infra', 'general']),
              default='general', help='Worker mode')
@click.option('--name', '-n', help='Worker name')
@click.option('--debug', is_flag=True, help='Enable debug logging')
def start_worker(mode: str, name: Optional[str], debug: bool):
    """Start a Worker agent."""
    try:
        args = ['--mode', mode]
        if name:
            # Validate worker name format
            if not name.strip():
                raise click.ClickException("Worker name cannot be empty")
            if len(name) > 50:
                raise click.ClickException("Worker name too long (max 50 characters)")
            args.extend(['--name', name])
        if debug:
            args.append('--debug')

        # Call the worker main with simulated argv
        import sys
        original_argv = sys.argv
        try:
            sys.argv = ['hive-worker'] + args
            worker_main()
        finally:
            sys.argv = original_argv
    except ImportError as e:
        click.echo(f"Error importing worker module: {e}", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"Error starting worker: {e}", err=True)
        logger.error(f"Worker startup error: {e}")
        raise click.Exit(1)


@cli.command()
def status():
    """Show orchestrator status."""
    try:
        # Import here to avoid circular dependencies
        from hive_db_utils import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        # Count tasks by status with error handling
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'queued'")
        result = cursor.fetchone()
        queued = result[0] if result else 0

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('assigned', 'in_progress')")
        result = cursor.fetchone()
        running = result[0] if result else 0

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        result = cursor.fetchone()
        completed = result[0] if result else 0

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'failed'")
        result = cursor.fetchone()
        failed = result[0] if result else 0

        # Count active workers
        cursor.execute("SELECT COUNT(*) FROM workers WHERE status = 'active'")
        result = cursor.fetchone()
        active_workers = result[0] if result else 0

        # Count total runs
        cursor.execute("SELECT COUNT(*) FROM runs")
        result = cursor.fetchone()
        total_runs = result[0] if result else 0

        click.echo("=== Hive Orchestrator Status ===")
        click.echo(f"\nTasks:")
        click.echo(f"  Queued:    {queued}")
        click.echo(f"  Running:   {running}")
        click.echo(f"  Completed: {completed}")
        click.echo(f"  Failed:    {failed}")
        click.echo(f"\nWorkers:")
        click.echo(f"  Active:    {active_workers}")
        click.echo(f"\nRuns:")
        click.echo(f"  Total:     {total_runs}")

    except ImportError as e:
        click.echo(f"Database module not available: {e}", err=True)
        click.echo("Make sure hive-core-db package is installed", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"Error getting status: {e}", err=True)
        logger.error(f"Status command error: {e}")
        raise click.Exit(1)


@cli.command()
@click.argument('task_id')
def review_escalated(task_id: str):
    """Review an escalated task requiring human decision."""
    try:
        from hive_db_utils import get_connection
        from hive_orchestrator.core.db import TaskStatus
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.prompt import Prompt
        from rich import box

        console = Console()
        conn = get_connection()
        cursor = conn.cursor()

        # Fetch the escalated task
        cursor.execute("""
            SELECT id, title, description, status, priority, result_data
            FROM tasks
            WHERE id = ? AND status = ?
        """, (task_id, TaskStatus.ESCALATED.value))

        task = cursor.fetchone()

        if not task:
            click.echo(f"Error: Task {task_id} not found or not escalated", err=True)
            raise click.Exit(1)

        # Parse result data for AI review information
        result_data = json.loads(task['result_data']) if task['result_data'] else {}
        review = result_data.get('review', {})

        # Display task header
        logger.info(Panel.fit(
            f"[bold red]ESCALATED TASK REVIEW[/bold red]\n"
            f"[yellow]Task ID:[/yellow] {task['id']}\n"
            f"[yellow]Title:[/yellow] {task['title']}\n"
            f"[yellow]Priority:[/yellow] {task['priority']}",
            title="Human Review Required",
            box=box.DOUBLE
        ))

        # Display task description
        console.logger.info("\n[bold]Task Description:[/bold]")
        console.logger.info(task['description'])

        # Display AI analysis if available
        if review:
            console.logger.info("\n[bold]AI Review Analysis:[/bold]")

            # Quality metrics table
            metrics_table = Table(title="Quality Metrics", box=box.ROUNDED)
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Score", style="white")

            metrics = review.get('metrics', {})
            metrics_table.add_row("Code Quality", f"{metrics.get('code_quality', 0):.0f}")
            metrics_table.add_row("Test Coverage", f"{metrics.get('test_coverage', 0):.0f}")
            metrics_table.add_row("Documentation", f"{metrics.get('documentation', 0):.0f}")
            metrics_table.add_row("Security", f"{metrics.get('security', 0):.0f}")
            metrics_table.add_row("Architecture", f"{metrics.get('architecture', 0):.0f}")
            metrics_table.add_row("[bold]Overall[/bold]", f"[bold]{review.get('overall_score', 0):.0f}[/bold]")

            console.logger.info(metrics_table)

            # AI reasoning
            console.logger.info("\n[bold]AI Decision:[/bold]", review.get('decision', 'unknown'))
            console.logger.info("[bold]Confidence:[/bold]", f"{review.get('confidence', 0):.0%}")
            console.logger.info("\n[bold]Summary:[/bold]", review.get('summary', 'No summary available'))

            # Issues found
            if review.get('issues'):
                console.logger.info("\n[bold red]Issues Found:[/bold red]")
                for issue in review['issues']:
                    console.logger.info(f"  • {issue}")

            # Suggestions
            if review.get('suggestions'):
                console.logger.info("\n[bold yellow]AI Suggestions:[/bold yellow]")
                for suggestion in review['suggestions']:
                    console.logger.info(f"  • {suggestion}")

            # Escalation reason
            if 'escalation_reason' in result_data:
                console.logger.info("\n[bold magenta]Escalation Reason:[/bold magenta]")
                console.logger.info(result_data['escalation_reason'])

        # Human decision prompt
        console.logger.info("\n" + "="*60 + "\n")
        console.logger.info("[bold cyan]HUMAN REVIEW DECISION REQUIRED[/bold cyan]")
        console.logger.info("\nAvailable actions:")
        console.logger.info("  [green]approve[/green]  - Override AI concerns and approve")
        console.logger.info("  [red]reject[/red]   - Confirm rejection")
        console.logger.info("  [yellow]rework[/yellow]   - Send back for improvements")
        console.logger.info("  [cyan]defer[/cyan]    - Need more information")
        console.logger.info("  [dim]cancel[/dim]   - Cancel review")

        # Get human decision
        decision = Prompt.ask(
            "\nYour decision",
            choices=["approve", "reject", "rework", "defer", "cancel"],
            default="defer"
        )

        if decision == "cancel":
            console.logger.info("[yellow]Review cancelled[/yellow]")
            return

        # Get additional notes
        notes = Prompt.ask("\nAdditional notes (optional)", default="")

        # Update task status based on decision
        new_status = {
            "approve": TaskStatus.APPROVED.value,
            "reject": TaskStatus.REJECTED.value,
            "rework": TaskStatus.REWORK_NEEDED.value,
            "defer": TaskStatus.ESCALATED.value
        }[decision]

        # Store human review
        human_review = {
            "decision": decision,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
            "reviewer": "human"
        }

        if not result_data:
            result_data = {}
        result_data['human_review'] = human_review

        cursor.execute("""
            UPDATE tasks
            SET status = ?, result_data = ?, updated_at = ?
            WHERE id = ?
        """, (new_status, json.dumps(result_data), datetime.now().isoformat(), task_id))

        conn.commit()

        console.logger.info(f"\n[green]✓[/green] Task {task_id} updated to status: [bold]{new_status}[/bold]")

        if notes:
            console.logger.info(f"[dim]Notes recorded: {notes}[/dim]")

    except ImportError as e:
        click.echo(f"Required module not available: {e}", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"Error reviewing task: {e}", err=True)
        logger.error(f"Review escalated error: {e}")
        raise click.Exit(1)


@cli.command()
def list_escalated():
    """List all tasks requiring human review."""
    try:
        from hive_db_utils import get_connection
        from hive_orchestrator.core.db import TaskStatus
        from rich.console import Console
        from rich.table import Table
        from rich import box
        import json

        console = Console()
        conn = get_connection()
        cursor = conn.cursor()

        # Fetch all escalated tasks
        cursor.execute("""
            SELECT id, title, description, priority, created_at, result_data
            FROM tasks
            WHERE status = ?
            ORDER BY priority DESC, created_at ASC
        """, (TaskStatus.ESCALATED.value,))

        tasks = cursor.fetchall()

        if not tasks:
            console.logger.info("[green]✓[/green] No escalated tasks requiring review")
            return

        # Create table
        table = Table(
            title=f"[bold red]🚨 {len(tasks)} Tasks Requiring Human Review[/bold red]",
            box=box.ROUNDED
        )

        table.add_column("ID", style="cyan", width=12)
        table.add_column("Title", width=30)
        table.add_column("Priority", justify="center", width=8)
        table.add_column("Age", width=10)
        table.add_column("AI Score", justify="center", width=10)
        table.add_column("Reason", width=30)

        for task in tasks:
            # Calculate age
            created = datetime.fromisoformat(task['created_at'])
            age = datetime.now() - created
            age_str = f"{age.days}d {age.seconds//3600}h" if age.days > 0 else f"{age.seconds//3600}h {(age.seconds%3600)//60}m"

            # Get AI score and reason
            result_data = json.loads(task['result_data']) if task['result_data'] else {}
            review = result_data.get('review', {})
            score = review.get('overall_score', 0)

            # Determine escalation reason
            if review:
                if score < 40:
                    reason = "Very low quality score"
                elif len(review.get('issues', [])) > 5:
                    reason = f"{len(review['issues'])} issues found"
                elif review.get('confidence', 1) < 0.5:
                    reason = "Low AI confidence"
                else:
                    reason = result_data.get('escalation_reason', 'Complex decision required')
            else:
                reason = result_data.get('reason', 'No AI analysis available')

            # Color code by age
            if age.days > 2:
                age_color = "red"
            elif age.days > 0:
                age_color = "yellow"
            else:
                age_color = "white"

            table.add_row(
                task['id'][:12],
                task['title'][:30],
                str(task['priority']),
                f"[{age_color}]{age_str}[/{age_color}]",
                f"{score:.0f}" if score else "N/A",
                reason[:30]
            )

        console.logger.info(table)
        console.logger.info(f"\n[yellow]Use 'hive review-escalated <task_id>' to review a specific task[/yellow]")

    except ImportError as e:
        click.echo(f"Required module not available: {e}", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"Error listing escalated tasks: {e}", err=True)
        logger.error(f"List escalated error: {e}")
        raise click.Exit(1)


@cli.command()
@click.argument('task_description')
@click.option('--role', '-r', help='Target worker role')
@click.option('--priority', '-p', type=int, default=1, help='Task priority')
def queue_task(task_description: str, role: Optional[str], priority: int):
    """Queue a new task for processing."""
    try:
        # Validate inputs
        if not task_description.strip():
            raise click.ClickException("Task description cannot be empty")
        if len(task_description) > 5000:
            raise click.ClickException("Task description too long (max 5000 characters)")
        if priority < 1 or priority > 10:
            raise click.ClickException("Priority must be between 1 and 10")
        if role and len(role) > 50:
            raise click.ClickException("Role name too long (max 50 characters)")

        # Import here to avoid circular dependencies
        from hive_orchestrator.core.db import create_task

        task_id = create_task(
            title=task_description[:50],  # Truncate title
            task_type=role or 'general',
            description=task_description,
            priority=priority
        )

        click.echo(f"Task queued with ID: {task_id}")

    except ImportError as e:
        click.echo(f"Database module not available: {e}", err=True)
        click.echo("Make sure hive-core-db package is installed", err=True)
        raise click.Exit(1)
    except click.ClickException:
        raise  # Re-raise click exceptions as-is
    except Exception as e:
        click.echo(f"Error queuing task: {e}", err=True)
        logger.error(f"Queue task error: {e}")
        raise click.Exit(1)


if __name__ == '__main__':
    cli()