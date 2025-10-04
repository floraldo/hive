"""
Knowledge Archivist service for archiving agent experiences and web searches.

Archives thinking sessions, web search results, and other agent experiences
into the RAG vector store for future retrieval and context augmentation.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from hive_ai.rag.embeddings import EmbeddingGenerator
from hive_ai.rag.models import ChunkType, CodeChunk
from hive_ai.rag.vector_store import VectorStore
from hive_logging import get_logger

logger = get_logger(__name__)


class KnowledgeArchivist:
    """
    Archives agent experiences into RAG for future retrieval.

    Stores:
    - Thinking session logs
    - Web search results
    - Task solutions and approaches
    - Failed attempts (for retry prevention across sessions)

    Example:
        ```python
        archivist = KnowledgeArchivist(vector_store, embedding_gen)

        # Archive a thinking session
        await archivist.archive_thinking_session_async(
            task_id="task-123",
            thoughts_log=[...],
            web_searches=[...]
        )

        # Archive web search results
        await archivist.archive_web_search_async(
            query="Python async best practices",
            results=[...]
        )
        ```
    """

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
        storage_path: Path | None = None,
    ):
        """Initialize knowledge archivist.

        Args:
            vector_store: Vector store for RAG. If None, creates new one.
            embedding_generator: Embedding generator. If None, creates new one.
            storage_path: Path for vector store persistence. If None, uses default.
        """
        self.storage_path = storage_path or Path("data/knowledge_archive")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize vector store
        self.vector_store = vector_store or VectorStore(embedding_dim=384)

        # Initialize embedding generator
        self.embedding_generator = embedding_generator or EmbeddingGenerator()

        # Load existing index if available
        index_path = self.storage_path / "knowledge.faiss"
        if index_path.exists():
            try:
                self.vector_store.load(str(index_path))
                logger.info(f"Loaded knowledge archive with {self.vector_store.index.ntotal} entries")
            except Exception as e:
                logger.warning(f"Failed to load existing index: {e}")

        logger.info("Initialized KnowledgeArchivist")

    async def archive_thinking_session_async(
        self,
        task_id: str,
        task_description: str,
        thoughts_log: list[dict],
        web_searches: list[dict] | None = None,
        final_solution: Any | None = None,
        success: bool = False,
    ) -> None:
        """
        Archive a complete thinking session to RAG.

        Args:
            task_id: Unique task identifier.
            task_description: Description of the task.
            thoughts_log: List of thought entries from the thinking loop.
            web_searches: Optional list of web search results used.
            final_solution: Final solution if task was completed.
            success: Whether the task was completed successfully.
        """
        logger.info(f"Archiving thinking session for task {task_id}")

        chunks_to_add: list[CodeChunk] = []

        # Archive the complete thinking session as one chunk
        session_content = self._format_thinking_session(
            task_id=task_id,
            task_description=task_description,
            thoughts_log=thoughts_log,
            final_solution=final_solution,
            success=success,
        )

        session_chunk = CodeChunk(
            code=session_content,
            chunk_type=ChunkType.DOCSTRING,
            file_path=f"knowledge_archive/thinking_sessions/{task_id}.md",
            signature=f"thinking_session_{task_id}",
            docstring=task_description,
            purpose=f"Thinking session for task: {task_description}",
            usage_context="Agent Experience",
            execution_type="thinking_session",
            created_at=datetime.now(),
        )

        # Generate embedding
        session_chunk.embedding = await self.embedding_generator.generate_async(session_content)
        chunks_to_add.append(session_chunk)

        # Archive web searches if provided
        if web_searches:
            for search in web_searches:
                search_chunks = await self._archive_web_search_results(
                    task_id=task_id,
                    query=search.get("query", ""),
                    results=search.get("results", []),
                )
                chunks_to_add.extend(search_chunks)

        # Add all chunks to vector store
        if chunks_to_add:
            self.vector_store.add_chunks(chunks_to_add)
            logger.info(f"Archived {len(chunks_to_add)} chunks from thinking session {task_id}")

            # Persist to disk
            await self._persist_async()

    async def archive_web_search_async(
        self,
        query: str,
        results: list[dict],
        task_id: str | None = None,
    ) -> None:
        """
        Archive web search results to RAG.

        Args:
            query: The search query.
            results: List of search result dictionaries.
            task_id: Optional task ID for linking to thinking session.
        """
        logger.info(f"Archiving web search: '{query}' ({len(results)} results)")

        chunks = await self._archive_web_search_results(task_id or "standalone", query, results)

        if chunks:
            self.vector_store.add_chunks(chunks)
            logger.info(f"Archived {len(chunks)} web search results")

            # Persist to disk
            await self._persist_async()

    async def _archive_web_search_results(
        self,
        task_id: str,
        query: str,
        results: list[dict],
    ) -> list[CodeChunk]:
        """
        Convert web search results to CodeChunks for archival.

        Args:
            task_id: Task ID for linking.
            query: Search query.
            results: Search result dictionaries.

        Returns:
            List of CodeChunk objects ready for archival.
        """
        chunks: list[CodeChunk] = []

        for idx, result in enumerate(results):
            # Extract result data
            title = result.get("title", "")
            url = result.get("url", "")
            text = result.get("text", "")
            result.get("score")

            if not text:
                continue  # Skip results without text content

            # Format content for archival
            content = f"# {title}\n\nSource: {url}\n\nQuery: {query}\n\n{text}"

            # Create chunk
            chunk = CodeChunk(
                code=content,
                chunk_type=ChunkType.DOCSTRING,
                file_path=f"knowledge_archive/web_searches/{task_id}_search_{idx}.md",
                signature=f"web_search_{task_id}_{idx}",
                docstring=f"Web search result: {title}",
                purpose=f"Web search result for query: {query}",
                usage_context="Web Search",
                execution_type="web_search_result",
                dependencies=[url],
                created_at=datetime.now(),
            )

            # Generate embedding
            chunk.embedding = await self.embedding_generator.generate_async(content)
            chunks.append(chunk)

        return chunks

    def _format_thinking_session(
        self,
        task_id: str,
        task_description: str,
        thoughts_log: list[dict],
        final_solution: Any | None,
        success: bool,
    ) -> str:
        """
        Format a thinking session into markdown for archival.

        Args:
            task_id: Task identifier.
            task_description: Task description.
            thoughts_log: List of thought entries.
            final_solution: Final solution if available.
            success: Whether task succeeded.

        Returns:
            Formatted markdown string.
        """
        lines = [
            f"# Thinking Session: {task_id}",
            f"\n## Task\n{task_description}",
            f"\n## Outcome\n{'SUCCESS' if success else 'INCOMPLETE'}",
        ]

        if final_solution:
            lines.append(f"\n## Solution\n```\n{final_solution}\n```")

        lines.append(f"\n## Thinking Process ({len(thoughts_log)} thoughts)\n")

        for thought in thoughts_log:
            thought_num = thought.get("thought_number", 0)
            timestamp = thought.get("timestamp", "")
            result = thought.get("result", {})
            reasoning = result.get("reasoning", "No reasoning available")

            lines.append(f"\n### Thought {thought_num}\n*{timestamp}*\n\n{reasoning}\n")

        return "\n".join(lines)

    async def _persist_async(self) -> None:
        """Persist vector store to disk."""
        try:
            index_path = self.storage_path / "knowledge.faiss"
            self.vector_store.save(str(index_path))
            logger.debug(f"Persisted knowledge archive to {index_path}")
        except Exception as e:
            logger.error(f"Failed to persist knowledge archive: {e}")

    async def close_async(self) -> None:
        """Clean up resources and persist final state."""
        await self._persist_async()
        logger.info("Closed KnowledgeArchivist")
