"""Worker Fleet CLI - Fleet Management Commands

CLI for managing autonomous QA worker fleet:
- hive fleet spawn - Spawn worker fleet in tmux
- hive fleet status - Check worker fleet status
- hive fleet worker <id> - Get specific worker details
- hive fleet monitor - Launch monitoring dashboard
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from hive_config.paths import PROJECT_ROOT
from hive_logging import get_logger, setup_logging

logger = get_logger(__name__)


def spawn_worker_fleet(
    workers: list[str], workspace: Path | None = None, poll_interval: float = 2.0,
) -> bool:
    """Spawn worker fleet in tmux panes.

    Args:
        workers: List of worker types to spawn ('qa', 'golden_rules', 'test', 'security')
        workspace: Workspace directory (defaults to PROJECT_ROOT)
        poll_interval: Task queue poll interval in seconds

    Returns:
        True if fleet spawned successfully, False otherwise

    """
    workspace = workspace or PROJECT_ROOT

    logger.info(f"Spawning {len(workers)} workers in tmux...")

    try:
        # Check if tmux is available
        result = subprocess.run(
            ["tmux", "list-sessions"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Create new tmux session if needed
        session_name = "hive-qa-fleet"

        if result.returncode != 0:
            # No tmux session exists
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name],
                check=True,
            )
            logger.info(f"Created tmux session: {session_name}")

        # Spawn monitor in pane 0 (HITL terminal shows this)
        monitor_cmd = f"python {PROJECT_ROOT}/scripts/fleet/monitor.py"
        subprocess.run(
            ["tmux", "send-keys", "-t", f"{session_name}:0", monitor_cmd, "Enter"],
            check=True,
        )
        logger.info("Monitor dashboard spawned in pane 0")

        # Spawn workers in panes 1-N
        for idx, worker_type in enumerate(workers, start=1):
            # Create new pane
            subprocess.run(
                ["tmux", "split-window", "-t", session_name, "-h"],
                check=True,
            )

            # Run worker
            worker_id = f"{worker_type}-worker-{idx}"
            worker_cmd = (
                f"python {PROJECT_ROOT}/apps/hive-orchestrator/src/hive_orchestrator/qa_worker.py "
                f"--worker-id {worker_id} "
                f"--workspace {workspace} "
                f"--poll-interval {poll_interval}"
            )

            subprocess.run(
                ["tmux", "send-keys", "-t", f"{session_name}:{idx}", worker_cmd, "Enter"],
                check=True,
            )

            logger.info(f"Worker {worker_id} spawned in pane {idx}")

        # Attach to session to show monitor
        logger.info("\nFleet spawned successfully!")
        logger.info(f"  Session: {session_name}")
        logger.info(f"  Workers: {len(workers)}")
        logger.info(f"  Attach with: tmux attach -t {session_name}")

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to spawn worker fleet: {e}")
        return False
    except FileNotFoundError:
        logger.error("tmux not found - install with: sudo apt install tmux")
        return False


def show_fleet_status() -> None:
    """Show worker fleet status summary."""
    logger.info("Worker fleet status:")
    logger.info("  Implementation: Basic status check")
    logger.info("  Use 'hive fleet monitor' for real-time dashboard")


def show_worker_details(worker_id: str) -> None:
    """Show specific worker details."""
    logger.info(f"Worker {worker_id} details:")
    logger.info("  Implementation: Worker detail query")


def launch_monitor() -> None:
    """Launch worker fleet monitoring dashboard."""
    logger.info("Launching worker fleet monitor...")

    try:
        monitor_script = PROJECT_ROOT / "scripts" / "fleet" / "monitor.py"
        subprocess.run(["python", str(monitor_script)], check=True)

    except KeyboardInterrupt:
        logger.info("\nMonitor stopped")
    except subprocess.CalledProcessError as e:
        logger.error(f"Monitor failed: {e}")


def main() -> int:
    """CLI entry point."""
    setup_logging(name="fleet-cli", log_to_file=False)

    parser = argparse.ArgumentParser(
        description="Worker Fleet CLI - Autonomous QA Worker Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Spawn QA and Golden Rules workers
  hive fleet spawn --workers qa,golden_rules

  # Spawn full fleet (4 worker types)
  hive fleet spawn --workers qa,golden_rules,test,security

  # Check fleet status
  hive fleet status

  # Launch monitoring dashboard
  hive fleet monitor

  # Get specific worker details
  hive fleet worker qa-worker-1
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Fleet management commands")

    # Spawn command
    spawn_parser = subparsers.add_parser("spawn", help="Spawn worker fleet in tmux")
    spawn_parser.add_argument(
        "--workers",
        required=True,
        help="Comma-separated list of worker types (qa,golden_rules,test,security)",
    )
    spawn_parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (default: PROJECT_ROOT)",
    )
    spawn_parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Task queue poll interval in seconds (default: 2.0)",
    )

    # Status command
    subparsers.add_parser("status", help="Show worker fleet status")

    # Monitor command
    subparsers.add_parser("monitor", help="Launch monitoring dashboard")

    # Worker command
    worker_parser = subparsers.add_parser("worker", help="Show specific worker details")
    worker_parser.add_argument("worker_id", help="Worker ID to query")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "spawn":
        workers = [w.strip() for w in args.workers.split(",")]
        valid_workers = {"qa", "golden_rules", "test", "security"}

        invalid = set(workers) - valid_workers
        if invalid:
            logger.error(f"Invalid worker types: {invalid}")
            logger.error(f"Valid types: {valid_workers}")
            return 1

        success = spawn_worker_fleet(
            workers=workers,
            workspace=args.workspace,
            poll_interval=args.poll_interval,
        )
        return 0 if success else 1

    if args.command == "status":
        show_fleet_status()
        return 0

    if args.command == "monitor":
        launch_monitor()
        return 0

    if args.command == "worker":
        show_worker_details(args.worker_id)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
