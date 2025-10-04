"""Archivist Service

Unified service that combines Librarian (real-time) and Curator (scheduled) modes.
Provides single entry point for all knowledge management operations.

Implements Decision 4-C: Proactive Knowledge Curator with dual-mode architecture.
"""

from __future__ import annotations

from typing import Any, Literal

from hive_bus import BaseBus
from hive_errors import HiveError
from hive_logging import get_logger

from .indexing.fragment_parser import FragmentParser
from .indexing.vector_indexer import VectorIndexer
from .services.curator import CuratorService
from .services.librarian import LibrarianService

logger = get_logger(__name__)


class ArchivistService:
    """Unified knowledge management service.

    Modes:
    - 'librarian': Real-time event-driven indexing
    - 'curator': Scheduled deep analysis and maintenance
    - 'both': Run both modes concurrently
    """

    def __init__(
        self,
        mode: Literal["librarian", "curator", "both"] = "librarian",
        bus: BaseBus | None = None,
        fragment_parser: FragmentParser | None = None,
        vector_indexer: VectorIndexer | None = None,
    ):
        """Initialize archivist service.

        Args:
            mode: Operating mode ('librarian', 'curator', or 'both')
            bus: Event bus (required for librarian mode)
            fragment_parser: Fragment extraction logic
            vector_indexer: Vector storage logic

        """
        self.mode = mode
        self.fragment_parser = fragment_parser or FragmentParser()
        self.vector_indexer = vector_indexer or VectorIndexer()

        # Initialize mode-specific services
        self.librarian: LibrarianService | None = None
        self.curator: CuratorService | None = None

        if mode in ("librarian", "both"):
            self.librarian = LibrarianService(
                bus=bus,
                fragment_parser=self.fragment_parser,
                vector_indexer=self.vector_indexer,
            )

        if mode in ("curator", "both"):
            self.curator = CuratorService(
                vector_indexer=self.vector_indexer,
            )

        logger.info(f"ArchivistService initialized in '{mode}' mode")

    async def start_async(self) -> None:
        """Start the archivist service.

        For 'librarian' mode: Subscribes to event bus
        For 'curator' mode: No-op (runs on schedule)
        For 'both': Starts librarian only (curator runs on demand)
        """
        if self.mode == "librarian" and self.librarian:
            await self.librarian.start()
            logger.info("Librarian service started (real-time indexing active)")

        elif self.mode == "both" and self.librarian:
            await self.librarian.start()
            logger.info(
                "Archivist started in dual mode: "
                "Librarian active (real-time), Curator available (on-demand)",
            )

        elif self.mode == "curator":
            logger.info(
                "Curator mode - service ready. "
                "Call run_maintenance_async() to execute scheduled maintenance",
            )

    async def stop_async(self) -> None:
        """Stop the archivist service."""
        if self.librarian:
            await self.librarian.stop()

        logger.info("Archivist service stopped")

    async def index_task_async(self, task_id: str) -> list[str]:
        """Manually index a task (useful for backfilling).

        Args:
            task_id: Task ID to index

        Returns:
            List of vector IDs created

        Raises:
            HiveError: If librarian not available or task not found

        """
        if not self.librarian:
            raise HiveError(
                "Manual indexing requires librarian mode. "
                "Initialize with mode='librarian' or mode='both'",
            )

        return await self.librarian.index_task_async(task_id)

    async def run_maintenance_async(self) -> dict[str, Any]:
        """Run curator maintenance cycle.

        Returns:
            Maintenance results and statistics

        Raises:
            HiveError: If curator not available

        """
        if not self.curator:
            raise HiveError(
                "Maintenance requires curator mode. "
                "Initialize with mode='curator' or mode='both'",
            )

        return await self.curator.run_maintenance_async()

    async def get_stats_async(self) -> dict[str, Any]:
        """Get comprehensive service statistics."""
        stats = {
            "mode": self.mode,
            "services": {},
        }

        if self.librarian:
            stats["services"]["librarian"] = await self.librarian.get_stats_async()

        if self.curator:
            stats["services"]["curator"] = await self.curator.get_curator_stats_async()

        # Vector store stats
        stats["vector_store"] = await self.vector_indexer.get_indexing_stats_async()

        return stats


__all__ = ["ArchivistService"]
