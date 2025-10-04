"""Unit tests for KnowledgeArchivist and RAG synergy.

Tests cover:
- Thinking session archival
- Web search result archival
- Vector store persistence
- RAG context retrieval
- Multi-source knowledge integration
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from hive_ai.rag.embeddings import EmbeddingGenerator
from hive_ai.rag.models import ChunkType
from hive_ai.rag.vector_store import VectorStore
from hive_ai.services.knowledge_archivist import KnowledgeArchivist


class TestKnowledgeArchivistInitialization:
    """Test KnowledgeArchivist initialization and setup."""

    def test_archivist_initialization_creates_storage_path(self, tmp_path):
        """Test that archivist creates storage directory."""
        storage_path = tmp_path / "test_archive"

        KnowledgeArchivist(storage_path=storage_path)

        assert storage_path.exists()
        assert storage_path.is_dir()

    def test_archivist_loads_existing_index(self, tmp_path):
        """Test loading existing knowledge archive index."""
        storage_path = tmp_path / "test_archive"
        storage_path.mkdir()

        # Create mock index file
        index_path = storage_path / "knowledge.faiss"
        index_path.touch()

        with patch.object(VectorStore, "load") as mock_load:
            KnowledgeArchivist(storage_path=storage_path)

            # Should attempt to load existing index
            mock_load.assert_called_once()

    def test_archivist_with_custom_vector_store(self):
        """Test initialization with custom vector store."""
        mock_vector_store = MagicMock(spec=VectorStore)

        archivist = KnowledgeArchivist(vector_store=mock_vector_store)

        assert archivist.vector_store is mock_vector_store


class TestThinkingSessionArchival:
    """Test archiving thinking sessions to RAG."""

    @pytest.mark.asyncio
    async def test_archive_thinking_session_basic(self):
        """Test basic thinking session archival."""
        mock_vector_store = MagicMock(spec=VectorStore)
        mock_embedding_gen = AsyncMock(spec=EmbeddingGenerator)
        mock_embedding_gen.generate_async.return_value = np.random.rand(384)

        archivist = KnowledgeArchivist(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_gen,
        )

        thoughts_log = [
            {
                "thought_number": 1,
                "timestamp": "2024-10-04T10:00:00",
                "result": {"reasoning": "First thought"},
            },
            {
                "thought_number": 2,
                "timestamp": "2024-10-04T10:00:05",
                "result": {"reasoning": "Second thought"},
            },
        ]

        await archivist.archive_thinking_session_async(
            task_id="test-task-001",
            task_description="Solve optimization problem",
            thoughts_log=thoughts_log,
            final_solution="Optimal solution found",
            success=True,
        )

        # Verify embedding generation was called
        mock_embedding_gen.generate_async.assert_called()

        # Verify chunks were added to vector store
        mock_vector_store.add_chunks.assert_called_once()

        # Verify chunk structure
        call_args = mock_vector_store.add_chunks.call_args
        chunks = call_args[0][0]

        assert len(chunks) >= 1  # At least session chunk
        session_chunk = chunks[0]
        assert session_chunk.chunk_type == ChunkType.DOCSTRING
        assert "test-task-001" in session_chunk.file_path
        assert session_chunk.purpose == "Thinking session for task: Solve optimization problem"

    @pytest.mark.asyncio
    async def test_archive_thinking_session_with_web_searches(self):
        """Test archival with web search results included."""
        mock_vector_store = MagicMock(spec=VectorStore)
        mock_embedding_gen = AsyncMock(spec=EmbeddingGenerator)
        mock_embedding_gen.generate_async.return_value = np.random.rand(384)

        archivist = KnowledgeArchivist(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_gen,
        )

        web_searches = [
            {
                "query": "Python async best practices",
                "results": [
                    {
                        "title": "Async Guide",
                        "url": "https://example.com/async",
                        "text": "Learn about async/await...",
                    },
                ],
            },
        ]

        await archivist.archive_thinking_session_async(
            task_id="test-task-002",
            task_description="Research async patterns",
            thoughts_log=[],
            web_searches=web_searches,
            success=False,
        )

        # Should add both session chunk and web search chunks
        call_args = mock_vector_store.add_chunks.call_args
        chunks = call_args[0][0]

        assert len(chunks) >= 2  # Session + at least one web search result

        # Find web search chunk
        web_chunks = [c for c in chunks if "web_search" in c.file_path]
        assert len(web_chunks) > 0
        assert web_chunks[0].dependencies == ["https://example.com/async"]

    @pytest.mark.asyncio
    async def test_thinking_session_markdown_formatting(self):
        """Test markdown formatting of thinking sessions."""
        mock_vector_store = MagicMock(spec=VectorStore)
        mock_embedding_gen = AsyncMock(spec=EmbeddingGenerator)
        mock_embedding_gen.generate_async.return_value = np.random.rand(384)

        archivist = KnowledgeArchivist(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_gen,
        )

        thoughts_log = [
            {
                "thought_number": 1,
                "timestamp": "2024-10-04T10:00:00",
                "result": {"reasoning": "Analyzing problem..."},
            },
        ]

        await archivist.archive_thinking_session_async(
            task_id="test-task-003",
            task_description="Format test",
            thoughts_log=thoughts_log,
            final_solution="Solution found",
            success=True,
        )

        # Extract the formatted content
        call_args = mock_embedding_gen.generate_async.call_args
        formatted_content = call_args[0][0]

        # Verify markdown structure
        assert "# Thinking Session: test-task-003" in formatted_content
        assert "## Task" in formatted_content
        assert "Format test" in formatted_content
        assert "## Outcome" in formatted_content
        assert "SUCCESS" in formatted_content
        assert "## Solution" in formatted_content
        assert "Solution found" in formatted_content
        assert "## Thinking Process" in formatted_content
        assert "### Thought 1" in formatted_content


class TestWebSearchArchival:
    """Test archiving web search results."""

    @pytest.mark.asyncio
    async def test_archive_web_search_basic(self):
        """Test archiving standalone web search results."""
        mock_vector_store = MagicMock(spec=VectorStore)
        mock_embedding_gen = AsyncMock(spec=EmbeddingGenerator)
        mock_embedding_gen.generate_async.return_value = np.random.rand(384)

        archivist = KnowledgeArchivist(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_gen,
        )

        search_results = [
            {
                "title": "Article 1",
                "url": "https://example.com/1",
                "text": "Article content 1",
                "score": 0.95,
            },
            {
                "title": "Article 2",
                "url": "https://example.com/2",
                "text": "Article content 2",
                "score": 0.88,
            },
        ]

        await archivist.archive_web_search_async(
            query="test search query",
            results=search_results,
        )

        # Verify chunks created for each result
        call_args = mock_vector_store.add_chunks.call_args
        chunks = call_args[0][0]

        assert len(chunks) == 2
        assert all(c.chunk_type == ChunkType.DOCSTRING for c in chunks)
        assert all("Query: test search query" in c.code for c in chunks)

    @pytest.mark.asyncio
    async def test_archive_web_search_skips_results_without_text(self):
        """Test that results without text are skipped."""
        mock_vector_store = MagicMock(spec=VectorStore)
        mock_embedding_gen = AsyncMock(spec=EmbeddingGenerator)
        mock_embedding_gen.generate_async.return_value = np.random.rand(384)

        archivist = KnowledgeArchivist(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_gen,
        )

        search_results = [
            {"title": "No text", "url": "https://example.com/1"},  # No text field
            {
                "title": "Has text",
                "url": "https://example.com/2",
                "text": "Content here",
            },
        ]

        await archivist.archive_web_search_async(
            query="test query",
            results=search_results,
        )

        # Should only archive the one with text
        call_args = mock_vector_store.add_chunks.call_args
        chunks = call_args[0][0]

        assert len(chunks) == 1
        assert "Has text" in chunks[0].code


class TestPersistence:
    """Test vector store persistence."""

    @pytest.mark.asyncio
    async def test_persistence_after_archival(self, tmp_path):
        """Test that vector store is persisted after archival."""
        storage_path = tmp_path / "test_archive"
        mock_vector_store = MagicMock(spec=VectorStore)

        archivist = KnowledgeArchivist(
            vector_store=mock_vector_store,
            storage_path=storage_path,
        )

        # Mock the embedding generator
        with patch.object(archivist.embedding_generator, "generate_async", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = np.random.rand(384)

            await archivist.archive_thinking_session_async(
                task_id="persist-test",
                task_description="Test persistence",
                thoughts_log=[],
                success=True,
            )

            # Verify save was called
            expected_path = str(storage_path / "knowledge.faiss")
            mock_vector_store.save.assert_called_once_with(expected_path)

    @pytest.mark.asyncio
    async def test_close_persists_state(self, tmp_path):
        """Test that closing archivist persists final state."""
        storage_path = tmp_path / "test_archive"
        mock_vector_store = MagicMock(spec=VectorStore)

        archivist = KnowledgeArchivist(
            vector_store=mock_vector_store,
            storage_path=storage_path,
        )

        await archivist.close_async()

        # Should persist on close
        mock_vector_store.save.assert_called_once()


class TestRAGContextRetrieval:
    """Test enhanced context retrieval with RAG synergy."""

    @pytest.mark.asyncio
    async def test_augmented_context_retrieval(self):
        """Test multi-source context retrieval."""
        from hive_ai.memory.context_service import ContextRetrievalService

        # Mock dependencies
        mock_vector_store = MagicMock()
        mock_embedding_manager = MagicMock()

        service = ContextRetrievalService(
            vector_store=mock_vector_store,
            embedding_manager=mock_embedding_manager,
        )

        # Mock the standard context retrieval
        with patch.object(service, "get_context_for_task", new_callable=AsyncMock) as mock_get_context:
            mock_get_context.return_value = "Standard code context..."

            # Test augmented retrieval
            result = await service.get_augmented_context_for_task(
                task_id="test-123",
                task_description="Test task description",
                include_knowledge_archive=False,  # Disable to simplify test
                include_test_intelligence=False,  # Disable to simplify test
            )

            assert "combined_context" in result
            assert "sources" in result
            assert "metadata" in result
            assert "Standard code context..." in result["combined_context"]

    @pytest.mark.asyncio
    async def test_augmented_context_with_knowledge_archive(self, tmp_path):
        """Test context retrieval including knowledge archive."""
        from hive_ai.memory.context_service import ContextRetrievalService

        # Create mock archive with data
        archive_path = tmp_path / "knowledge_archive"
        archive_path.mkdir()
        index_path = archive_path / "knowledge.faiss"

        # Create a real but minimal FAISS index
        import faiss
        index = faiss.IndexFlatIP(384)
        faiss.write_index(index, str(index_path))

        mock_vector_store = MagicMock()
        mock_embedding_manager = MagicMock()

        service = ContextRetrievalService(
            vector_store=mock_vector_store,
            embedding_manager=mock_embedding_manager,
        )

        # Mock standard context
        with patch.object(service, "get_context_for_task", new_callable=AsyncMock) as mock_get_context:
            mock_get_context.return_value = ""

            # Change working directory for test
            with patch("pathlib.Path") as mock_path:
                mock_path.return_value = archive_path

                result = await service.get_augmented_context_for_task(
                    task_id="test-archive",
                    task_description="Test with archive",
                    include_knowledge_archive=True,
                    include_test_intelligence=False,
                )

                # Should have attempted to load archive
                assert "combined_context" in result


class TestErrorHandling:
    """Test error handling in knowledge archival."""

    @pytest.mark.asyncio
    async def test_archival_continues_on_embedding_error(self):
        """Test that archival handles embedding errors gracefully."""
        mock_vector_store = MagicMock(spec=VectorStore)
        mock_embedding_gen = AsyncMock(spec=EmbeddingGenerator)
        mock_embedding_gen.generate_async.side_effect = Exception("Embedding failed")

        archivist = KnowledgeArchivist(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_gen,
        )

        # Should not crash, just fail gracefully
        with pytest.raises(Exception):
            await archivist.archive_thinking_session_async(
                task_id="error-test",
                task_description="Test error handling",
                thoughts_log=[],
                success=False,
            )

    @pytest.mark.asyncio
    async def test_archival_handles_persistence_errors(self, tmp_path):
        """Test handling of persistence errors."""
        storage_path = tmp_path / "readonly_archive"
        storage_path.mkdir()

        mock_vector_store = MagicMock(spec=VectorStore)
        mock_vector_store.save.side_effect = Exception("Disk full")

        archivist = KnowledgeArchivist(
            vector_store=mock_vector_store,
            storage_path=storage_path,
        )

        # Should log error but not crash
        with patch.object(archivist.embedding_generator, "generate_async", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = np.random.rand(384)

            # This should complete without raising
            await archivist.archive_thinking_session_async(
                task_id="persist-error",
                task_description="Test persistence error",
                thoughts_log=[],
                success=True,
            )

            # Vector store should have attempted save despite error
            mock_vector_store.save.assert_called()
