#!/usr/bin/env python3
"""
AI Reviewer Application - BaseApplication Implementation

Migrated to use BaseApplication from hive-app-toolkit for:
- Automatic configuration loading (Project Unify V2)
- Automatic resource management (database, cache, event bus)
- Graceful shutdown handling with signal support
- Standardized lifecycle management

Migration: ai-reviewer (Worker App #2)
Pattern: Long-running review agent with polling
"""

from __future__ import annotations

import asyncio

from ai_reviewer.agent import ReviewAgent
from ai_reviewer.reviewer import ReviewEngine
from hive_app_toolkit import BaseApplication
from hive_logging import get_logger

logger = get_logger("ai-reviewer.app")


class AIReviewerApp(BaseApplication):
    """
    AI Reviewer Application

    Autonomous code review service that:
    - Monitors review_pending tasks in database
    - Performs AI-powered code reviews
    - Publishes review results back to orchestrator
    - Supports both test and production modes
    """

    app_name = "ai-reviewer"

    def __init__(self, config=None, test_mode: bool = False, polling_interval: int = 30):
        """
        Initialize AI Reviewer application.

        Args:
            config: Optional pre-loaded configuration (for testing)
            test_mode: Run in test/mock mode (no actual API calls)
            polling_interval: Seconds between queue polls
        """
        super().__init__(config=config)
        self.test_mode = test_mode
        self.polling_interval = polling_interval
        self.review_agent = None
        self.review_engine = None

    async def initialize_services(self):
        """
        Initialize AI Reviewer services.

        Resources (db, cache, event_bus) are already initialized by BaseApplication.
        """
        self.logger.info(
            f"Initializing AI Reviewer services "
            f"(test_mode={self.test_mode}, poll_interval={self.polling_interval}s)..."
        )

        # Create review engine
        # Future: Pass self.cache for result caching
        self.review_engine = ReviewEngine(mock_mode=self.test_mode)

        # Create review agent
        # Future: Pass self.db instead of DatabaseAdapter
        self.review_agent = ReviewAgent(
            review_engine=self.review_engine,
            polling_interval=self.polling_interval,
            test_mode=self.test_mode,
        )

        self.logger.info("AI Reviewer services initialized successfully")

    async def run(self):
        """
        Main application logic - run the review agent loop.

        Polls for review tasks and processes them until shutdown.
        """
        self.logger.info("Starting AI Reviewer main loop...")

        # Start agent
        self.review_agent.running = True
        self.review_agent.stats["start_time"] = __import__("datetime").datetime.now()

        # Main review loop
        while not self._shutdown_requested and self.review_agent.running:
            try:
                # Process review queue (synchronous for now)
                # Future: Use async version when available
                await self.review_agent._process_review_queue_async()

                # Report status
                await self.review_agent._report_status_async()

                # Sleep before next poll
                await asyncio.sleep(self.polling_interval)

            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt in main loop")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(self.polling_interval)

        self.logger.info("AI Reviewer main loop stopped")

    async def cleanup_services(self):
        """
        Cleanup AI Reviewer services.

        BaseApplication handles db, cache, bus cleanup.
        We only clean reviewer-specific resources.
        """
        if self.review_agent:
            self.logger.info("Stopping AI Reviewer agent...")
            self.review_agent.running = False

            # Future: Call shutdown method if available
            if hasattr(self.review_agent, "_shutdown_async"):
                try:
                    await self.review_agent._shutdown_async()
                except Exception as e:
                    self.logger.warning(f"Error during agent shutdown: {e}")

        self.logger.info("AI Reviewer cleanup complete")


def main() -> int:
    """
    Entry point for AI Reviewer application.

    Supports command-line arguments for backward compatibility.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import argparse

    parser = argparse.ArgumentParser(description="AI Reviewer Autonomous Agent")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode")
    parser.add_argument("--polling-interval", type=int, default=30, help="Polling interval in seconds")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        import logging

        logging.getLogger("ai-reviewer").setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    try:
        # Create and start application
        app = AIReviewerApp(test_mode=args.test_mode, polling_interval=args.polling_interval)
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
