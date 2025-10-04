"""
Librarian Service

Real-time knowledge indexing service that listens to task.completed events
and automatically indexes knowledge fragments into the RAG system.

Implements Decision 4-C: Proactive Knowledge Curator (Librarian mode).
"""

from __future__ import annotations

import json
from typing import Any

from hive_bus import BaseBus
from hive_errors import HiveError
from hive_logging import get_logger
from hive_orchestration.operations import tasks

from ..indexing.fragment_parser import FragmentParser
from ..indexing.vector_indexer import VectorIndexer

logger = get_logger(__name__)


class LibrarianService:
    """
    Real-time knowledge indexing service.

    Listens for task.completed events and automatically:
    1. Parses task into knowledge fragments
    2. Generates embeddings for each fragment
    3. Stores vectors in RAG database
    4. Updates task DB with related_document_ids
    """

    def __init__(
        self,
        bus: BaseBus | None = None,
        fragment_parser: FragmentParser | None = None,
        vector_indexer: VectorIndexer | None = None
    ):
        """
        Initialize librarian service.

        Args:
            bus: Event bus for listening to task completions
            fragment_parser: Fragment extraction logic
            vector_indexer: Vector storage logic
        """
        self.bus = bus  # Will be injected by orchestrator
        self.fragment_parser = fragment_parser or FragmentParser()
        self.vector_indexer = vector_indexer or VectorIndexer()

        self.running = False
        self.tasks_indexed = 0

        logger.info("LibrarianService initialized")

    async def start(self) -> None:
        """
        Start the librarian service.

        Subscribes to task.completed events and begins real-time indexing.
        """
        if self.running:
            logger.warning("LibrarianService already running")
            return

        if not self.bus:
            raise HiveError(
                "LibrarianService requires event bus. "
                "Pass bus instance or use LibrarianService.start_with_bus()"
            )

        # Subscribe to task completion events
        await self.bus.subscribe_async("task.completed", self._handle_task_completed)

        self.running = True
        logger.info("LibrarianService started - listening for task.completed events")

    async def stop(self) -> None:
        """Stop the librarian service."""
        if not self.running:
            return

        if self.bus:
            await self.bus.unsubscribe_async("task.completed", self._handle_task_completed)

        self.running = False
        logger.info(f"LibrarianService stopped. Total tasks indexed: {self.tasks_indexed}")

    async def _handle_task_completed(self, event: dict[str, Any]) -> None:
        """
        Handle task.completed event.

        Args:
            event: Event payload containing task_id and metadata
        """
        task_id = event.get('task_id')
        if not task_id:
            logger.error("task.completed event missing task_id")
            return

        try:
            await self.index_task_async(task_id)
        except Exception as e:
            logger.error(f"Failed to index task {task_id}: {e}", exc_info=True)

    async def index_task_async(self, task_id: str) -> list[str]:
        """
        Index a completed task into the knowledge base.

        Args:
            task_id: ID of the task to index

        Returns:
            List of vector IDs created in the RAG system

        Raises:
            HiveError: If task not found or indexing fails
        """
        logger.info(f"Indexing task {task_id[:8]}...")

        # 1. Fetch task from orchestration DB
        task = tasks.get_task(task_id)
        if not task:
            raise HiveError(f"Task {task_id} not found in orchestration DB")

        # 2. Parse into knowledge fragments
        fragments = self.fragment_parser.parse_task(task)
        if not fragments:
            logger.warning(f"No knowledge fragments extracted from task {task_id[:8]}")
            return []

        # 3. Generate embeddings and store in vector DB
        vector_ids = await self.vector_indexer.index_fragments_async(fragments)

        # 4. Update task with related_document_ids
        await self._update_task_with_vectors(task_id, fragments, vector_ids)

        self.tasks_indexed += 1
        logger.info(
            f"Successfully indexed task {task_id[:8]} → {len(vector_ids)} vectors created"
        )

        return vector_ids

    async def _update_task_with_vectors(
        self,
        task_id: str,
        fragments: list,
        vector_ids: list[str]
    ) -> None:
        """
        Update task DB with knowledge fragment metadata.

        Stores:
        - related_document_ids: Vector IDs for retrieval
        - knowledge_fragments: Structured fragment metadata
        - summary: First summary fragment (for quick reference)
        """
        # Build knowledge_fragments JSON
        knowledge_data = {
            'summaries': [],
            'errors': [],
            'decisions': [],
            'artifacts': []
        }

        for fragment in fragments:
            fragment_entry = {
                'content': fragment.content[:200],  # truncate for storage
                'timestamp': fragment.timestamp,
                'metadata': fragment.metadata
            }

            if fragment.fragment_type == 'summary':
                knowledge_data['summaries'].append(fragment_entry)
            elif fragment.fragment_type == 'error':
                knowledge_data['errors'].append(fragment_entry)
            elif fragment.fragment_type == 'decision':
                knowledge_data['decisions'].append(fragment_entry)
            elif fragment.fragment_type == 'artifact':
                knowledge_data['artifacts'].append(fragment_entry)

        # Extract summary for quick reference
        summary = None
        for fragment in fragments:
            if fragment.fragment_type == 'summary':
                summary = fragment.content
                break

        # Update task in DB
        update_data = {
            'related_document_ids': json.dumps(vector_ids),
            'knowledge_fragments': json.dumps(knowledge_data),
            'summary': summary
        }

        success = tasks.update_task_status(
            task_id=task_id,
            status=tasks.get_task(task_id)['status'],  # keep existing status
            metadata=update_data
        )

        if success:
            logger.debug(f"Updated task {task_id[:8]} with {len(vector_ids)} vector IDs")
        else:
            logger.error(f"Failed to update task {task_id[:8]} with vector metadata")

    async def get_stats_async(self) -> dict[str, Any]:
        """Get librarian service statistics."""
        indexer_stats = await self.vector_indexer.get_indexing_stats_async()

        return {
            "service": "librarian",
            "status": "running" if self.running else "stopped",
            "tasks_indexed": self.tasks_indexed,
            **indexer_stats
        }


__all__ = ["LibrarianService"]
