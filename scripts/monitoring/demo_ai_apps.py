#!/usr/bin/env python3
"""Demo script to exercise AI apps and generate dashboard metrics.

Launches all three AI apps with metrics servers and simulates activity
to populate the monitoring dashboard with real data.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "apps" / "ai-reviewer" / "src"))
sys.path.insert(0, str(project_root / "apps" / "ai-planner" / "src"))
sys.path.insert(0, str(project_root / "apps" / "ai-deployer" / "src"))

from hive_logging import get_logger
from hive_performance import start_metrics_server

logger = get_logger(__name__)


async def start_ai_reviewer_with_metrics():
    """Start AI Reviewer with metrics on port 8001."""
    logger.info("Starting AI Reviewer metrics server on port 8001...")

    # Start metrics server
    start_metrics_server(port=8001, app_name="ai-reviewer")

    # Simulate some review activity

    logger.info("AI Reviewer ready - metrics at http://localhost:8001/metrics")

    # Keep running
    while True:
        await asyncio.sleep(10)


async def start_ai_planner_with_metrics():
    """Start AI Planner with metrics on port 8002."""
    logger.info("Starting AI Planner metrics server on port 8002...")

    # Start metrics server
    start_metrics_server(port=8002, app_name="ai-planner")

    logger.info("AI Planner ready - metrics at http://localhost:8002/metrics")

    # Keep running
    while True:
        await asyncio.sleep(10)


async def start_ai_deployer_with_metrics():
    """Start AI Deployer with metrics on port 8003."""
    logger.info("Starting AI Deployer metrics server on port 8003...")

    # Start metrics server
    start_metrics_server(port=8003, app_name="ai-deployer")

    logger.info("AI Deployer ready - metrics at http://localhost:8003/metrics")

    # Keep running
    while True:
        await asyncio.sleep(10)


async def simulate_activity():
    """Simulate AI app activity to generate metrics."""
    logger.info("Starting activity simulation...")

    # Import instrumented functions

    # Wait for apps to start
    await asyncio.sleep(2)

    while True:
        try:
            # Simulate review activity
            logger.info("Simulating review activity...")

            # This will trigger instrumented functions and generate metrics
            # The @track_request decorators will automatically record metrics

            await asyncio.sleep(15)

        except Exception as e:
            logger.error(f"Activity simulation error: {e}")
            await asyncio.sleep(5)


async def main():
    """Main entry point."""
    print("=" * 60)
    print("AI Apps Metrics Demo")
    print("=" * 60)
    print()
    print("Starting all AI apps with metrics enabled...")
    print()
    print("Metrics endpoints:")
    print("  - AI Reviewer:  http://localhost:8001/metrics")
    print("  - AI Planner:   http://localhost:8002/metrics")
    print("  - AI Deployer:  http://localhost:8003/metrics")
    print()
    print("Dashboard:        http://localhost:5000")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    # Start all apps concurrently
    tasks = [
        asyncio.create_task(start_ai_reviewer_with_metrics()),
        asyncio.create_task(start_ai_planner_with_metrics()),
        asyncio.create_task(start_ai_deployer_with_metrics()),
        asyncio.create_task(simulate_activity()),
    ]

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        for task in tasks:
            task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo stopped by user")
