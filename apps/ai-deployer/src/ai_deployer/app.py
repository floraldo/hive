#!/usr/bin/env python3
"""
AI Deployer Application - BaseApplication Implementation

Migrated to use BaseApplication from hive-app-toolkit for:
- Automatic configuration loading (Project Unify V2)
- Automatic resource management (database, cache, event bus)
- Graceful shutdown handling with signal support
- Standardized lifecycle management

Migration: ai-deployer (Worker App #3)
Pattern: Long-running deployment agent with polling
"""

from __future__ import annotations

import asyncio

from ai_deployer.agent import DeploymentAgent
from ai_deployer.deployer import DeploymentOrchestrator
from hive_app_toolkit import BaseApplication
from hive_logging import get_logger

logger = get_logger("ai-deployer.app")


class AIDeployerApp(BaseApplication):
    """
    AI Deployer Application

    Autonomous deployment service that:
    - Monitors deployment_pending tasks in database
    - Orchestrates automated deployments
    - Publishes deployment results back to orchestrator
    - Supports both test and production modes
    """

    app_name = "ai-deployer"

    def __init__(self, config=None, test_mode: bool = False, polling_interval: int = 30):
        """
        Initialize AI Deployer application.

        Args:
            config: Optional pre-loaded configuration (for testing)
            test_mode: Run in test/mock mode
            polling_interval: Seconds between queue polls
        """
        super().__init__(config=config)
        self.test_mode = test_mode
        self.polling_interval = polling_interval
        self.deployment_agent = None
        self.orchestrator = None

    async def initialize_services(self):
        """
        Initialize AI Deployer services.

        Resources (db, cache, event_bus) are already initialized by BaseApplication.
        """
        self.logger.info(
            f"Initializing AI Deployer services "
            f"(test_mode={self.test_mode}, poll_interval={self.polling_interval}s)..."
        )

        # Create deployment orchestrator
        self.orchestrator = DeploymentOrchestrator()

        # Create deployment agent
        # Future: Pass self.db instead of DatabaseAdapter
        self.deployment_agent = DeploymentAgent(
            orchestrator=self.orchestrator, polling_interval=self.polling_interval, test_mode=self.test_mode
        )

        self.logger.info("AI Deployer services initialized successfully")

    async def run(self):
        """
        Main application logic - run the deployment agent loop.

        Polls for deployment tasks and processes them until shutdown.
        """
        self.logger.info("Starting AI Deployer main loop...")

        # Start agent
        self.deployment_agent.running = True
        self.deployment_agent.stats["start_time"] = __import__("datetime").datetime.now()

        # Main deployment loop
        while not self._shutdown_requested and self.deployment_agent.running:
            try:
                # Process deployment queue
                # Future: Use async version when available
                task = await self._get_next_task()

                if task:
                    self.logger.info(f"Processing deployment task: {task['id']}")
                    try:
                        await self._process_deployment(task)
                    except Exception as e:
                        self.logger.error(f"Deployment failed: {e}", exc_info=True)
                else:
                    # No tasks available, wait before polling again
                    await asyncio.sleep(self.polling_interval)

            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt in main loop")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(self.polling_interval)

        self.logger.info("AI Deployer main loop stopped")

    async def _get_next_task(self):
        """Get next deployment task (temporary wrapper)"""
        # This is a temporary wrapper around synchronous method
        # Future: Use async database operations
        return self.deployment_agent.adapter.get_next_pending_task()

    async def _process_deployment(self, task):
        """Process deployment task (temporary wrapper)"""
        # This is a temporary wrapper around synchronous method
        # Future: Make orchestrator fully async
        result = self.orchestrator.deploy(task)
        self.deployment_agent.adapter.update_task_status(task["id"], "deployed" if result else "failed")
        return result

    async def cleanup_services(self):
        """
        Cleanup AI Deployer services.

        BaseApplication handles db, cache, bus cleanup.
        We only clean deployer-specific resources.
        """
        if self.deployment_agent:
            self.logger.info("Stopping AI Deployer agent...")
            self.deployment_agent.running = False

        self.logger.info("AI Deployer cleanup complete")


def main() -> int:
    """
    Entry point for AI Deployer application.

    Supports command-line arguments for backward compatibility.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import argparse

    parser = argparse.ArgumentParser(description="AI Deployer Autonomous Agent")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode")
    parser.add_argument("--polling-interval", type=int, default=30, help="Polling interval in seconds")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        import logging

        # Set debug level for ai-deployer logger
        debug_logger = get_logger("ai-deployer")
        debug_logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    try:
        # Create and start application
        app = AIDeployerApp(test_mode=args.test_mode, polling_interval=args.polling_interval)
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
