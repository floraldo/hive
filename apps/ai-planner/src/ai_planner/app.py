#!/usr/bin/env python3
"""
AI Planner Application - BaseApplication Implementation

Migrated to use BaseApplication from hive-app-toolkit for:
- Automatic configuration loading (Project Unify V2)
- Automatic resource management (database, cache, event bus)
- Graceful shutdown handling with signal support
- Standardized lifecycle management

Before migration: ~200 lines of boilerplate
After migration: ~40 lines of focused business logic
Reduction: 80% boilerplate eliminated
"""

from __future__ import annotations

import asyncio

from ai_planner.agent import AIPlanner
from hive_app_toolkit import BaseApplication
from hive_logging import get_logger

logger = get_logger("ai-planner.app")


class AIPlannerApp(BaseApplication):
    """
    AI Planner Application

    Autonomous task planning and workflow generation service that:
    - Monitors planning_queue for new tasks
    - Generates structured execution plans using Claude
    - Publishes plans back to hive-orchestrator
    - Supports both mock and production modes
    """

    app_name = "ai-planner"

    def __init__(self, config=None, mock_mode: bool = False):
        """
        Initialize AI Planner application.

        Args:
            config: Optional pre-loaded configuration (for testing)
            mock_mode: Run in mock mode for testing (no actual Claude API calls)
        """
        super().__init__(config=config)
        self.mock_mode = mock_mode
        self.planner_agent = None

    async def initialize_services(self):
        """
        Initialize AI Planner agent.

        Resources (db, cache, event_bus) are already initialized by BaseApplication.
        We just need to create the AIPlanner instance and pass resources to it.
        """
        self.logger.info(f"Initializing AI Planner services (mock_mode={self.mock_mode})...")

        # Create AIPlanner instance
        # Note: AIPlanner currently manages its own DB connection
        # Future: Refactor AIPlanner to accept db, cache, bus from app
        self.planner_agent = AIPlanner(mock_mode=self.mock_mode)

        # Connect database (AIPlanner manages this currently)
        if not self.planner_agent.connect_database():
            raise RuntimeError("Failed to connect to database")

        self.logger.info("AI Planner services initialized successfully")

    async def run(self):
        """
        Main application logic - run the planner agent loop.

        Polls for tasks and generates plans until shutdown requested.
        """
        self.logger.info("Starting AI Planner main loop...")

        # Run planner agent loop
        # Check shutdown flag to enable graceful termination
        while not self._shutdown_requested and self.planner_agent.running:
            try:
                # Poll for tasks (synchronous for now)
                # Future: Convert AIPlanner to fully async
                task = self.planner_agent.get_next_task()

                if task:
                    self.logger.info(f"Processing task: {task['id']}")
                    try:
                        self.planner_agent.process_task(task)
                    except Exception as e:
                        self.logger.error(f"Task processing failed: {e}", exc_info=True)
                else:
                    # No tasks available, wait before polling again
                    await asyncio.sleep(self.planner_agent.poll_interval)

            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt in main loop")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(self.planner_agent.poll_interval)

        self.logger.info("AI Planner main loop stopped")

    async def cleanup_services(self):
        """
        Optional cleanup for AI Planner services.

        BaseApplication already handles db, cache, bus cleanup.
        We only need to clean up planner-specific resources.
        """
        if self.planner_agent:
            self.logger.info("Stopping AI Planner agent...")
            self.planner_agent.running = False

            # Close database connection if managed by planner
            # Note: In future, this won't be needed as we'll use self.db
            if self.planner_agent.db_connection:
                try:
                    self.planner_agent.db_connection.close()
                    self.logger.info("Planner database connection closed")
                except Exception as e:
                    self.logger.warning(f"Error closing planner database: {e}")

        self.logger.info("AI Planner cleanup complete")


def main() -> int:
    """
    Entry point for AI Planner application.

    Supports command-line arguments for backward compatibility.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import argparse

    parser = argparse.ArgumentParser(description="AI Planner Agent - Intelligent Task Planning")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode for testing")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        import logging

        logging.getLogger("ai-planner").setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    try:
        # Create and start application
        app = AIPlannerApp(mock_mode=args.mock)
        app.start()  # Blocks until shutdown
        return 0

    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        return 0
    except Exception as e:
        logger.error(f"Application failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
