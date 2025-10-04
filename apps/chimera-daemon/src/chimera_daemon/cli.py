"""CLI - Command-line interface for Chimera daemon."""

from __future__ import annotations

import asyncio
import sys

import uvicorn
from hive_logging import get_logger

from .api import create_app
from .daemon import ChimeraDaemon

logger = get_logger(__name__)


def start_daemon() -> None:
    """Start Chimera daemon (background task processor)."""
    print("Starting Chimera Daemon...")
    print("Press Ctrl+C to stop")

    daemon = ChimeraDaemon(poll_interval=1.0)

    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")


def start_api(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start REST API server.

    Args:
        host: API host (default: 0.0.0.0)
        port: API port (default: 8000)
    """
    print(f"Starting Chimera API on {host}:{port}")
    print("Press Ctrl+C to stop")

    app = create_app()

    uvicorn.run(app, host=host, port=port, log_level="info")


def start_all(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start both daemon and API (development mode).

    Args:
        host: API host
        port: API port
    """
    print("Starting Chimera Daemon + API (development mode)")
    print(f"API: http://{host}:{port}")
    print("Press Ctrl+C to stop")

    # Start API in separate process
    import multiprocessing

    api_process = multiprocessing.Process(target=start_api, args=(host, port))
    api_process.start()

    # Start daemon in main process
    try:
        start_daemon()
    finally:
        api_process.terminate()
        api_process.join()


def main() -> None:
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  chimera-daemon start        # Start daemon only")
        print("  chimera-daemon api          # Start API only")
        print("  chimera-daemon start-all    # Start daemon + API")
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        start_daemon()
    elif command == "api":
        start_api()
    elif command == "start-all":
        start_all()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
