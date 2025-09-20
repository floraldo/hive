"""
Command-line interface for Hive Orchestrator.

Provides commands to manage the Queen coordinator and Worker agents.
"""

import click
import json
import os
import logging
from pathlib import Path
from typing import Optional

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
        logging.error(f"Queen startup error: {e}")
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
        logging.error(f"Worker startup error: {e}")
        raise click.Exit(1)


@cli.command()
def status():
    """Show orchestrator status."""
    try:
        # Import here to avoid circular dependencies
        from hive_core_db.database import get_connection

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
        logging.error(f"Status command error: {e}")
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
        from hive_core_db import create_task

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
        logging.error(f"Queue task error: {e}")
        raise click.Exit(1)


if __name__ == '__main__':
    cli()