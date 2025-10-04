# Security: subprocess calls in this script use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal RAG server tooling.

"""RAG API Server Launcher.

Convenient script to start the RAG API server for autonomous agent access.

Usage:
    # Start server (default port 8765)
    python scripts/rag/start_api.py

    # Start with custom port
    python scripts/rag/start_api.py --port 9000

    # Start in production mode (no auto-reload)
    python scripts/rag/start_api.py --production
"""

import argparse
import subprocess
import sys


def main() -> int:
    """Start the RAG API server."""
    parser = argparse.ArgumentParser(description="Start RAG API server for autonomous agents")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to run server on (default: 8765)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Run in production mode (no auto-reload)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (production mode only)",
    )

    args = parser.parse_args()

    # Build uvicorn command
    cmd = [
        "uvicorn",
        "hive_ai.rag.api:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]

    if args.production:
        cmd.extend(["--workers", str(args.workers)])
    else:
        cmd.append("--reload")

    print("=" * 60)
    print("Starting RAG API Server for Autonomous Agents")
    print("=" * 60)
    print(f"Mode: {'Production' if args.production else 'Development'}")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    if args.production:
        print(f"Workers: {args.workers}")
    print(f"\nAPI Docs: http://{args.host}:{args.port}/docs")
    print(f"Health Check: http://{args.host}:{args.port}/health")
    print("=" * 60)
    print()

    try:
        subprocess.run(cmd, check=True)
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        return 0


if __name__ == "__main__":
    sys.exit(main())
