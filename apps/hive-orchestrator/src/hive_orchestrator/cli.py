"""
Command-line interface for Hive Orchestrator.

Provides commands to manage the Queen coordinator and Worker agents.
"""

import click
import json
import os
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
    args = []
    if config:
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


@cli.command()
@click.option('--mode', '-m', type=click.Choice(['backend', 'frontend', 'infra', 'general']),
              default='general', help='Worker mode')
@click.option('--name', '-n', help='Worker name')
@click.option('--debug', is_flag=True, help='Enable debug logging')
def start_worker(mode: str, name: Optional[str], debug: bool):
    """Start a Worker agent."""
    args = ['--mode', mode]
    if name:
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


@cli.command()
def status():
    """Show orchestrator status."""
    try:
        # Import here to avoid circular dependencies
        from hive_core_db import session_scope, Task, Workflow, Worker

        with session_scope() as session:
            # Count tasks by status
            queued = session.query(Task).filter_by(status='queued').count()
            running = session.query(Task).filter_by(status='running').count()
            completed = session.query(Task).filter_by(status='completed').count()
            failed = session.query(Task).filter_by(status='failed').count()

            # Count active workers
            active_workers = session.query(Worker).filter_by(status='active').count()

            # Count workflows
            active_workflows = session.query(Workflow).filter_by(status='active').count()

            click.echo("=== Hive Orchestrator Status ===")
            click.echo(f"\nTasks:")
            click.echo(f"  Queued:    {queued}")
            click.echo(f"  Running:   {running}")
            click.echo(f"  Completed: {completed}")
            click.echo(f"  Failed:    {failed}")
            click.echo(f"\nWorkers:")
            click.echo(f"  Active:    {active_workers}")
            click.echo(f"\nWorkflows:")
            click.echo(f"  Active:    {active_workflows}")

    except Exception as e:
        click.echo(f"Error getting status: {e}", err=True)
        raise click.Exit(1)


@cli.command()
@click.argument('task_description')
@click.option('--role', '-r', help='Target worker role')
@click.option('--priority', '-p', type=int, default=1, help='Task priority')
def queue_task(task_description: str, role: Optional[str], priority: int):
    """Queue a new task for processing."""
    try:
        # Import here to avoid circular dependencies
        from hive_core_db import create_task

        task = create_task(
            description=task_description,
            worker_role=role or 'general',
            priority=priority
        )

        click.echo(f"Task queued with ID: {task.id}")

    except Exception as e:
        click.echo(f"Error queuing task: {e}", err=True)
        raise click.Exit(1)


if __name__ == '__main__':
    cli()