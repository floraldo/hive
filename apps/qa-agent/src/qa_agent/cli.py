"""QA Agent CLI - Command Line Interface.

Provides CLI commands for running the QA agent daemon and related utilities.
"""

from __future__ import annotations

import asyncio
import sys

import click
from hive_logging import get_logger

logger = get_logger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """QA Agent - Hybrid Autonomous Quality Enforcement System."""
    pass


@cli.command()
@click.option(
    "--poll-interval",
    default=5.0,
    help="Queue polling interval in seconds",
    type=float,
)
@click.option(
    "--max-chimera",
    default=3,
    help="Maximum concurrent Chimera agent executions",
    type=int,
)
@click.option(
    "--max-cc-workers",
    default=2,
    help="Maximum concurrent CC worker spawns",
    type=int,
)
def start(poll_interval: float, max_chimera: int, max_cc_workers: int) -> None:
    """Start QA Agent daemon.

    Runs background daemon that polls hive-orchestrator queue and routes
    violations to Chimera agents or CC workers based on complexity.
    """
    from .daemon import QAAgentDaemon

    logger.info("Starting QA Agent daemon...")

    # Create and run daemon
    daemon = QAAgentDaemon(
        poll_interval=poll_interval,
        max_concurrent_chimera=max_chimera,
        max_concurrent_cc_workers=max_cc_workers,
    )

    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Daemon failed: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
def status() -> None:
    """Show QA Agent status and worker health."""
    from .dashboard import display_simple_status

    click.echo("Fetching QA Agent status...")

    # For simple status, we'd need a running daemon reference
    # In production, this would connect to daemon via IPC/socket
    click.echo("\nNote: For real-time status, use 'qa-agent dashboard'")
    click.echo("For daemon logs, use: tail -f logs/qa-agent.log\n")

    display_simple_status(None)  # Pass daemon instance when available


@cli.command()
@click.option("--show-pending", is_flag=True, help="Show only pending escalations")
def escalations(show_pending: bool) -> None:
    """Show escalations requiring HITL review."""
    from .escalation import EscalationManager

    click.echo("Loading escalations...")

    # Create escalation manager (would connect to daemon in production)
    manager = EscalationManager()

    if show_pending:
        pending = manager.get_pending_escalations()
        click.echo(f"\nPending Escalations: {len(pending)}")
        for esc in pending:
            click.echo(f"  - {esc.escalation_id}: {esc.reason}")
    else:
        stats = manager.get_escalation_stats()
        click.echo("\nEscalation Statistics:")
        click.echo(f"  Total: {stats['total_escalations']}")
        click.echo(f"  Pending: {stats['pending']}")
        click.echo(f"  In Review: {stats['in_review']}")
        click.echo(f"  Resolved: {stats['resolved']}")
        click.echo(f"  Cannot Fix: {stats['cannot_fix']}")
        click.echo(f"  Won't Fix: {stats['wont_fix']}")


@cli.command()
def dashboard() -> None:
    """Launch interactive monitoring dashboard."""
    from .dashboard import Dashboard

    click.echo("Launching QA Agent dashboard...")
    click.echo("Press Ctrl+C to exit\n")

    # Create dashboard (would connect to daemon in production)
    dash = Dashboard(daemon=None, monitor=None, escalation_manager=None)

    try:
        asyncio.run(dash.start())
    except KeyboardInterrupt:
        click.echo("\nDashboard closed")


def main() -> None:
    """Main entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
