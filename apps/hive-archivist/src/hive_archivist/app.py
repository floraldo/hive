#!/usr/bin/env python3
"""Hive Archivist Application - BaseApplication Implementation

Migrated to use BaseApplication from hive-app-toolkit for:
- Automatic configuration loading (Project Unify V2)
- Automatic resource management (database, cache, event bus)
- Graceful shutdown handling with signal support
- Standardized lifecycle management

Migration: hive-archivist (Knowledge Management Service)
Pattern: Dual-mode service (librarian real-time + curator scheduled)
"""

from __future__ import annotations

import asyncio

from hive_app_toolkit import BaseApplication
from hive_archivist.archivist_service import ArchivistService
from hive_logging import get_logger

logger = get_logger("hive-archivist.app")


class HiveArchivistApp(BaseApplication):
    """Hive Archivist Application

    Unified knowledge management service that:
    - Librarian mode: Real-time event-driven indexing
    - Curator mode: Scheduled deep analysis and maintenance
    - Both mode: Run librarian + curator concurrently
    """

    app_name = "hive-archivist"

    def __init__(self, config=None, mode: str = "librarian", maintenance_interval: int = 3600):
        """Initialize Hive Archivist application.

        Args:
            config: Optional pre-loaded configuration (for testing)
            mode: Operating mode ('librarian', 'curator', 'both')
            maintenance_interval: Seconds between curator maintenance runs (curator/both modes)

        """
        super().__init__(config=config)
        self.mode = mode
        self.maintenance_interval = maintenance_interval
        self.archivist_service = None

    async def initialize_services(self):
        """Initialize Hive Archivist service.

        Resources (db, cache, event_bus) are already initialized by BaseApplication.
        """
        self.logger.info(f"Initializing Hive Archivist services (mode={self.mode})...")

        # Create archivist service with injected event bus
        # Note: event_bus is provided by BaseApplication
        self.archivist_service = ArchivistService(
            mode=self.mode,
            bus=self.event_bus,  # Injected from BaseApplication
            # fragment_parser and vector_indexer use defaults
        )

        # Start the service (librarian subscribes to events)
        await self.archivist_service.start_async()

        self.logger.info(f"Hive Archivist services initialized in '{self.mode}' mode")

    async def run(self):
        """Main application logic.

        - Librarian mode: Service is event-driven, just stay alive
        - Curator mode: Run periodic maintenance
        - Both mode: Librarian event-driven + periodic curator maintenance
        """
        self.logger.info(f"Starting Hive Archivist main loop (mode={self.mode})...")

        if self.mode == "librarian":
            # Librarian is event-driven, just wait for shutdown
            self.logger.info("Librarian mode active - waiting for events...")
            while not self._shutdown_requested:
                await asyncio.sleep(10)  # Just keep alive

        elif self.mode == "curator":
            # Curator runs periodic maintenance
            self.logger.info(
                f"Curator mode active - " f"running maintenance every {self.maintenance_interval}s...",
            )
            while not self._shutdown_requested:
                try:
                    # Run maintenance
                    if self.archivist_service.curator:
                        await self.archivist_service.run_maintenance_async()
                        self.logger.info("Curator maintenance complete")

                    # Wait for next cycle
                    await asyncio.sleep(self.maintenance_interval)

                except Exception as e:
                    self.logger.error(f"Curator maintenance failed: {e}", exc_info=True)
                    await asyncio.sleep(60)  # Brief delay before retry

        elif self.mode == "both":
            # Both modes: librarian event-driven + curator periodic
            self.logger.info(
                f"Dual mode active - "
                f"Librarian (events) + Curator (every {self.maintenance_interval}s)...",
            )
            while not self._shutdown_requested:
                try:
                    # Run curator maintenance
                    if self.archivist_service.curator:
                        await self.archivist_service.run_maintenance_async()
                        self.logger.info("Curator maintenance complete")

                    # Wait for next cycle (librarian continues handling events)
                    await asyncio.sleep(self.maintenance_interval)

                except Exception as e:
                    self.logger.error(f"Curator maintenance failed: {e}", exc_info=True)
                    await asyncio.sleep(60)

        self.logger.info("Hive Archivist main loop stopped")

    async def cleanup_services(self):
        """Cleanup Hive Archivist services.

        BaseApplication handles db, cache, bus cleanup.
        We only clean archivist-specific resources.
        """
        if self.archivist_service:
            self.logger.info("Stopping Hive Archivist service...")
            await self.archivist_service.stop_async()

        self.logger.info("Hive Archivist cleanup complete")


def main() -> int:
    """Entry point for Hive Archivist application.

    Returns:
        Exit code (0 for success, 1 for failure)

    """
    import argparse

    parser = argparse.ArgumentParser(description="Hive Archivist - Knowledge Management Service")
    parser.add_argument(
        "--mode",
        choices=["librarian", "curator", "both"],
        default="librarian",
        help="Operating mode: librarian (real-time), curator (scheduled), both (dual)",
    )
    parser.add_argument(
        "--maintenance-interval",
        type=int,
        default=3600,
        help="Curator maintenance interval in seconds (default: 3600 = 1 hour)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        import logging

        # Set debug level for hive-archivist logger
        debug_logger = get_logger("hive-archivist")
        debug_logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    try:
        # Create and start application
        app = HiveArchivistApp(mode=args.mode, maintenance_interval=args.maintenance_interval)
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
