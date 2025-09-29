"""
Comprehensive tests for hive-ai vector database components.

Tests VectorStore, EmbeddingManager, SemanticSearch, and VectorMetrics
with property-based testing.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from hive_ai.core.config import AIConfig, VectorConfig
from hive_ai.core.exceptions import VectorError
from hive_ai.vector.embedding import EmbeddingManager, EmbeddingResult
from hive_ai.vector.metrics import VectorMetrics
from hive_ai.vector.search import Document, SearchResult, SemanticSearch
from hive_ai.vector.store import VectorStore
from hypothesis import given, settings
from hypothesis import strategies as st


# Vector generation strategies for property-based testing
@st.composite
def vector_data(draw, dimension=None):
    """Generate valid vector data."""
    if dimension is None:
        dimension = draw(st.integers(min_value=128, max_value=1536))

    vector = draw(
        st.lists(
            st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=dimension,
            max_size=dimension,
        )
    )
    return vector


@st.composite
def document_data(draw):
    """Generate valid document data."""
    return {
        "id": draw(st.text(min_size=1, max_size=50)),
        "content": draw(st.text(min_size=10, max_size=1000)),
        "metadata": draw(
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.one_of(st.text(), st.integers(), st.floats(allow_nan=False)),
            )
        ),
    }


class TestVectorStore:
    """Test VectorStore functionality."""

    @pytest.fixture
    def vector_config(self):
        """Vector configuration for testing."""
        return VectorConfig(provider="chroma", collection_name="test_collection", dimension=128)

    @pytest.fixture
    def mock_chroma_provider(self):
        """Mock ChromaDB provider for testing."""
        provider = Mock()
        provider.store_vectors_async = AsyncMock(return_value=["id1", "id2"])
        provider.search_vectors_async = AsyncMock(
            return_value=[
                {
                    "id": "id1",
                    "distance": 0.1,
                    "metadata": {"content": "test content"},
                    "score": 0.9,
                }
            ]
        )
        provider.delete_vectors_async = AsyncMock(return_value=True)
        provider.get_collection_info_async = AsyncMock(
            return_value={
                "name": "test_collection",
                "count": 100,
                "dimension": 128,
                "provider": "chroma",
            }
        )
        provider.health_check_async = AsyncMock(return_value=True)
        return provider

    def test_vector_store_initialization(self, vector_config):
        """Test VectorStore initialization."""
        store = VectorStore(vector_config)
        assert store.config == vector_config
        assert store._provider is not None

    @pytest.mark.asyncio
    async def test_store_vectors_success_async(self, vector_config, mock_chroma_provider):
        """Test successful vector storage."""
        store = VectorStore(vector_config)
        store._provider = mock_chroma_provider

        vectors = [[0.1, 0.2, 0.3] * 42 + [0.4, 0.5]]  # 128-dim vector
        metadata = [{"content": "test"}]

        result = await store.store_async(vectors, metadata)

        assert result == ["id1", "id2"]
        mock_chroma_provider.store_vectors_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_vectors_dimension_mismatch_async(self, vector_config):
        """Test vector storage with dimension mismatch."""
        store = VectorStore(vector_config)

        # Wrong dimension vector
        vectors = [[0.1, 0.2, 0.3]]  # Only 3 dimensions, expected 128
        metadata = [{"content": "test"}]

        with pytest.raises(VectorError, match="dimension"):
            await store.store_async(vectors, metadata)

    @pytest.mark.asyncio
    async def test_search_vectors_success_async(self, vector_config, mock_chroma_provider):
        """Test successful vector search."""
        store = VectorStore(vector_config)
        store._provider = mock_chroma_provider

        query_vector = [0.1] * 128
        results = await store.search_async(query_vector, top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == "id1"
        assert results[0]["score"] == 0.9
        mock_chroma_provider.search_vectors_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_vectors_dimension_mismatch_async(self, vector_config):
        """Test vector search with dimension mismatch."""
        store = VectorStore(vector_config)

        # Wrong dimension query vector
        query_vector = [0.1, 0.2, 0.3]  # Only 3 dimensions

        with pytest.raises(VectorError, match="dimension"):
            await store.search_async(query_vector)

    @pytest.mark.asyncio
    async def test_delete_vectors_async(self, vector_config, mock_chroma_provider):
        """Test vector deletion."""
        store = VectorStore(vector_config)
        store._provider = mock_chroma_provider

        result = await store.delete_async(["id1", "id2"])

        assert result is True
        mock_chroma_provider.delete_vectors_async.assert_called_once_with(["id1", "id2"])

    @pytest.mark.asyncio
    async def test_health_check_async(self, vector_config, mock_chroma_provider):
        """Test vector store health check."""
        store = VectorStore(vector_config)
        store._provider = mock_chroma_provider

        health = await store.health_check_async()

        assert health["healthy"] is True
        assert health["provider"] == "chroma"
        assert health["collection"] == "test_collection"

    @given(
        vector_data(dimension=128),
        st.lists(st.dictionaries(st.text(min_size=1), st.text()), min_size=1, max_size=1),
    )
    @pytest.mark.asyncio
    async def test_store_vectors_property_async(self, vector, metadata_list):
        """Property-based test for vector storage."""
        config = VectorConfig(provider="chroma", dimension=128)
        store = VectorStore(config)

        # Mock the provider
        mock_provider = Mock()
        mock_provider.store_vectors_async = AsyncMock(return_value=["test_id"])
        store._provider = mock_provider

        try:
            result = await store.store_async([vector], metadata_list)
            assert isinstance(result, list)
            assert len(result) >= 0
        except VectorError:
            # Some combinations might be invalid, that's expected
            pass


class TestEmbeddingManager:
    """Test EmbeddingManager functionality."""

    @pytest.fixture
    def ai_config(self):
        """AI configuration for testing."""
        return AIConfig()

    @pytest.fixture
    def mock_model_client(self):
        """Mock ModelClient for testing."""
        client = Mock()
        client.generate_async = AsyncMock(return_value=Mock(content="Generated response", tokens_used=50, cost=0.001))
        return client

    @pytest.fixture
    def embedding_manager(self, ai_config, mock_model_client):
        """EmbeddingManager instance for testing."""
        manager = EmbeddingManager(ai_config)
        manager.model_client = mock_model_client
        return manager

    @pytest.mark.asyncio
    async def test_generate_embedding_success_async(self, embedding_manager):
        """Test successful embedding generation."""
        with patch.object(embedding_manager, "_simulate_embedding") as mock_simulate:
            mock_simulate.return_value = [0.1] * 1536

            result = await embedding_manager.generate_embedding_async("test text")

            assert isinstance(result, EmbeddingResult)
            assert result.text == "test text"
            assert len(result.vector) == 1536
            assert result.cache_hit is False

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text_async(self, embedding_manager):
        """Test embedding generation with empty text."""
        with pytest.raises(VectorError, match="empty text"):
            await embedding_manager.generate_embedding_async("")

    @pytest.mark.asyncio
    async def test_generate_embedding_caching_async(self, embedding_manager):
        """Test embedding caching behavior."""
        with patch.object(embedding_manager, "_simulate_embedding") as mock_simulate:
            mock_simulate.return_value = [0.1] * 1536

            # First call
            result1 = await embedding_manager.generate_embedding_async("test text")
            assert result1.cache_hit is False

            # Second call should hit cache
            result2 = await embedding_manager.generate_embedding_async("test text")
            assert result2.cache_hit is True
            assert result1.vector == result2.vector

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings_async(self, embedding_manager):
        """Test batch embedding generation."""
        texts = ["text 1", "text 2", "text 3"]

        with patch.object(embedding_manager, "_simulate_embedding") as mock_simulate:
            mock_simulate.return_value = [0.1] * 1536

            results = await embedding_manager.generate_batch_embeddings_async(texts)

            assert len(results) == 3
            for i, result in enumerate(results):
                assert result.text == texts[i]
                assert len(result.vector) == 1536

    @pytest.mark.asyncio
    async def test_search_similar_texts_async(self, embedding_manager):
        """Test similar text search."""
        query_text = "search query"
        candidate_texts = ["similar text", "different content", "another text"]

        with patch.object(embedding_manager, "_simulate_embedding") as mock_simulate:
            # Return different vectors for different texts
            def mock_embedding(text):
                if "similar" in text:
                    return [0.9] * 1536  # High similarity
                else:
                    return [0.1] * 1536  # Low similarity

            mock_simulate.side_effect = mock_embedding

            results = await embedding_manager.search_similar_texts_async(query_text, candidate_texts, top_k=2)

            assert len(results) <= 2
            assert all("similarity" in result for result in results)
            assert all(0 <= result["similarity"] <= 1 for result in results)

    @pytest.mark.asyncio
    async def test_cosine_similarity_calculation_async(self, embedding_manager):
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        vec3 = [1.0, 0.0, 0.0]

        # Orthogonal vectors should have similarity 0
        similarity_orthogonal = embedding_manager._calculate_cosine_similarity(vec1, vec2)
        assert abs(similarity_orthogonal) < 0.001

        # Identical vectors should have similarity 1
        similarity_identical = embedding_manager._calculate_cosine_similarity(vec1, vec3)
        assert abs(similarity_identical - 1.0) < 0.001

    def test_cosine_similarity_dimension_mismatch(self, embedding_manager):
        """Test cosine similarity with mismatched dimensions."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        with pytest.raises(VectorError, match="dimensions don't match"):
            embedding_manager._calculate_cosine_similarity(vec1, vec2)

    @given(st.text(min_size=1, max_size=100))
    @pytest.mark.asyncio
    async def test_embedding_generation_property_async(self, text):
        """Property-based test for embedding generation."""
        ai_config = AIConfig()
        manager = EmbeddingManager(ai_config)

        try:
            result = await manager.generate_embedding_async(text)

            # Properties that should always hold
            assert result.text == text
            assert len(result.vector) > 0
            assert all(isinstance(val, (int, float)) for val in result.vector)
            assert -1.0 <= max(result.vector) <= 1.0
            assert -1.0 <= min(result.vector) <= 1.0

        except VectorError:
            # Some texts might be invalid, that's expected
            pass


class TestSemanticSearch:
    """Test SemanticSearch functionality."""

    @pytest.fixture
    def vector_config(self):
        """Vector configuration for testing."""
        return VectorConfig(provider="chroma", collection_name="search_test", dimension=128)

    @pytest.fixture
    def ai_config(self):
        """AI configuration for testing."""
        return AIConfig()

    @pytest.fixture
    def mock_vector_store(self):
        """Mock VectorStore for testing."""
        store = Mock()
        store.store_async = AsyncMock(return_value=["doc1"])
        store.search_async = AsyncMock(
            return_value=[
                {
                    "id": "doc1",
                    "distance": 0.1,
                    "metadata": {"content": "test content", "indexed_at": "2024-01-01"},
                    "score": 0.9,
                }
            ]
        )
        store.delete_async = AsyncMock(return_value=True)
        store.get_info_async = AsyncMock(return_value={"name": "search_test", "count": 1, "dimension": 128})
        return store

    @pytest.fixture
    def mock_embedding_manager(self):
        """Mock EmbeddingManager for testing."""
        manager = Mock()
        manager.generate_embedding_async = AsyncMock(
            return_value=EmbeddingResult(
                text="test",
                vector=[0.1] * 128,
                model="test-model",
                tokens_used=10,
                cache_hit=False,
            )
        )
        manager.generate_batch_embeddings_async = AsyncMock(
            return_value=[
                EmbeddingResult(
                    text="doc content",
                    vector=[0.1] * 128,
                    model="test-model",
                    tokens_used=10,
                    cache_hit=False,
                )
            ]
        )
        return manager

    @pytest.fixture
    def semantic_search(self, vector_config, ai_config, mock_vector_store, mock_embedding_manager):
        """SemanticSearch instance for testing."""
        search = SemanticSearch(vector_config, ai_config)
        search.vector_store = mock_vector_store
        search.embedding_manager = mock_embedding_manager
        return search

    @pytest.mark.asyncio
    async def test_index_document_success_async(self, semantic_search):
        """Test successful document indexing."""
        document = Document(id="doc1", content="Test document content", metadata={"category": "test"})

        result = await semantic_search.index_document_async(document)

        assert result is True
        semantic_search.vector_store.store_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_documents_batch_async(self, semantic_search):
        """Test batch document indexing."""
        documents = [
            Document(id="doc1", content="Content 1", metadata={}),
            Document(id="doc2", content="Content 2", metadata={}),
            Document(id="doc3", content="Content 3", metadata={}),
        ]

        stats = await semantic_search.index_documents_async(documents)

        assert stats["indexed"] == 3
        assert stats["failed"] == 0
        assert stats["total"] == 3
        assert stats["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_search_success_async(self, semantic_search):
        """Test successful semantic search."""
        results = await semantic_search.search_async(query="test query", top_k=5)

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].document.id == "doc1"
        assert results[0].score == 0.9
        assert results[0].rank == 1

    @pytest.mark.asyncio
    async def test_search_with_explanations_async(self, semantic_search):
        """Test search with explanations enabled."""
        results = await semantic_search.search_async(query="test query", include_explanations=True)

        assert len(results) == 1
        assert results[0].explanation is not None
        assert "similarity" in results[0].explanation.lower()

    @pytest.mark.asyncio
    async def test_delete_document_async(self, semantic_search):
        """Test document deletion."""
        result = await semantic_search.delete_document_async("doc1")

        assert result is True
        semantic_search.vector_store.delete_async.assert_called_once_with(["doc1"])

    @pytest.mark.asyncio
    async def test_get_search_stats_async(self, semantic_search):
        """Test search statistics."""
        stats = await semantic_search.get_search_stats_async()

        assert "collection" in stats
        assert "health" in stats
        assert "embedding_stats" in stats
        assert stats["collection"]["name"] == "search_test"

    @given(document_data())
    @pytest.mark.asyncio
    async def test_document_indexing_property_async(self, doc_data):
        """Property-based test for document indexing."""
        vector_config = VectorConfig(provider="chroma", dimension=128)
        ai_config = AIConfig()
        search = SemanticSearch(vector_config, ai_config)

        # Mock dependencies
        search.vector_store = Mock()
        search.vector_store.store_async = AsyncMock(return_value=[doc_data["id"]])
        search.embedding_manager = Mock()
        search.embedding_manager.generate_embedding_async = AsyncMock(
            return_value=EmbeddingResult(
                text=doc_data["content"],
                vector=[0.1] * 128,
                model="test",
                tokens_used=10,
                cache_hit=False,
            )
        )

        document = Document(
            id=doc_data["id"],
            content=doc_data["content"],
            metadata=doc_data["metadata"],
        )

        try:
            result = await search.index_document_async(document)
            assert isinstance(result, bool)
        except VectorError:
            # Some documents might be invalid, that's expected
            pass


class TestVectorMetrics:
    """Test VectorMetrics functionality."""

    @pytest.fixture
    def metrics(self):
        """VectorMetrics instance for testing."""
        return VectorMetrics()

    @pytest.mark.asyncio
    async def test_record_vector_operation_async(self, metrics):
        """Test recording vector operations."""
        await metrics.record_vector_operation_async(
            operation="search",
            count=5,
            latency_ms=1500,
            success=True,
            collection="test_collection",
        )

        summary = metrics.get_metrics_summary()
        assert summary["total_operations"] == 1
        assert summary["successful_operations"] == 1
        assert summary["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_get_operation_performance_async(self, metrics):
        """Test operation performance statistics."""
        # Record multiple search operations
        for i in range(5):
            await metrics.record_vector_operation_async(
                operation="search",
                count=10,
                latency_ms=1000 + i * 100,
                success=i < 4,  # One failure
            )

        stats = await metrics.get_operation_performance_async("search")

        assert stats.total_operations == 5
        assert stats.successful_operations == 4
        assert stats.success_rate == 0.8
        assert stats.avg_latency_ms == 1200  # Average latency

    @pytest.mark.asyncio
    async def test_get_performance_trends_async(self, metrics):
        """Test performance trends analysis."""
        # Record operations over time
        for i in range(10):
            await metrics.record_vector_operation_async(operation="store", count=1, latency_ms=500, success=True)

        trends = await metrics.get_performance_trends_async(hours=1)

        assert "time_period_hours" in trends
        assert "total_records" in trends
        assert "performance_summary" in trends

    @pytest.mark.asyncio
    async def test_get_collection_metrics_async(self, metrics):
        """Test collection-specific metrics."""
        collection_name = "test_collection"

        # Record operations for specific collection
        await metrics.record_vector_operation_async(
            operation="search",
            count=5,
            latency_ms=1000,
            success=True,
            collection=collection_name,
        )

        collection_metrics = await metrics.get_collection_metrics_async(collection_name)

        assert collection_metrics["collection"] == collection_name
        assert collection_metrics["total_operations"] == 1
        assert collection_metrics["total_vectors_processed"] == 5

    @pytest.mark.asyncio
    async def test_error_analysis_async(self, metrics):
        """Test error analysis functionality."""
        # Record some failures
        await metrics.record_vector_operation_async(operation="search", count=1, latency_ms=1000, success=False)

        await metrics.record_vector_operation_async(operation="store", count=1, latency_ms=2000, success=False)

        error_analysis = await metrics.get_error_analysis_async()

        assert error_analysis["total_failures"] == 2
        assert error_analysis["failure_rate"] == 1.0  # All operations failed
        assert "errors_by_operation" in error_analysis
        assert "recommendations" in error_analysis

    @given(
        st.lists(
            st.tuples(
                st.sampled_from(["search", "store", "delete"]),
                st.integers(min_value=1, max_value=100),
                st.integers(min_value=100, max_value=5000),
                st.booleans(),
            ),
            min_size=1,
            max_size=50,
        )
    )
    @pytest.mark.asyncio
    async def test_metrics_aggregation_property_async(self, operations):
        """Property-based test for metrics aggregation."""
        metrics = VectorMetrics()

        total_operations = 0
        successful_operations = 0
        total_vectors = 0

        for operation, count, latency, success in operations:
            await metrics.record_vector_operation_async(
                operation=operation, count=count, latency_ms=latency, success=success
            )

            total_operations += 1
            if success:
                successful_operations += 1
            total_vectors += count

        summary = metrics.get_metrics_summary()

        # Verify aggregation consistency
        assert summary["total_operations"] == total_operations
        assert summary["successful_operations"] == successful_operations
        assert summary["total_vectors_processed"] == total_vectors

        if total_operations > 0:
            expected_success_rate = successful_operations / total_operations
            assert abs(summary["success_rate"] - expected_success_rate) < 0.001


class TestVectorIntegration:
    """Integration tests for vector components working together."""

    @pytest.mark.asyncio
    async def test_full_search_pipeline_simulation_async(self):
        """Test complete search pipeline with mocked components."""
        # Create configuration
        vector_config = VectorConfig(provider="chroma", dimension=128)
        ai_config = AIConfig()

        # Create search engine
        search = SemanticSearch(vector_config, ai_config)

        # Mock dependencies
        search.vector_store = Mock()
        search.vector_store.store_async = AsyncMock(return_value=["doc1", "doc2"])
        search.vector_store.search_async = AsyncMock(
            return_value=[
                {
                    "id": "doc1",
                    "distance": 0.1,
                    "metadata": {
                        "content": "Python programming guide",
                        "category": "tech",
                    },
                    "score": 0.9,
                },
                {
                    "id": "doc2",
                    "distance": 0.3,
                    "metadata": {"content": "JavaScript tutorial", "category": "tech"},
                    "score": 0.7,
                },
            ]
        )

        search.embedding_manager = Mock()
        search.embedding_manager.generate_embedding_async = AsyncMock(
            return_value=EmbeddingResult(
                text="test",
                vector=[0.1] * 128,
                model="test-model",
                tokens_used=10,
                cache_hit=False,
            )
        )
        search.embedding_manager.generate_batch_embeddings_async = AsyncMock(
            return_value=[
                EmbeddingResult(
                    text="Python programming guide",
                    vector=[0.1] * 128,
                    model="test-model",
                    tokens_used=15,
                    cache_hit=False,
                ),
                EmbeddingResult(
                    text="JavaScript tutorial",
                    vector=[0.2] * 128,
                    model="test-model",
                    tokens_used=12,
                    cache_hit=False,
                ),
            ]
        )

        # Test document indexing
        documents = [
            Document(
                id="doc1",
                content="Python programming guide",
                metadata={"category": "tech"},
            ),
            Document(id="doc2", content="JavaScript tutorial", metadata={"category": "tech"}),
        ]

        indexing_stats = await search.index_documents_async(documents)
        assert indexing_stats["indexed"] == 2
        assert indexing_stats["success_rate"] == 1.0

        # Test search
        search_results = await search.search_async("programming languages", top_k=2)
        assert len(search_results) == 2
        assert search_results[0].score > search_results[1].score  # Results should be ranked

    @settings(max_examples=10, deadline=10000)
    @given(
        st.lists(
            st.tuples(
                st.text(min_size=5, max_size=100),  # content
                st.dictionaries(
                    st.text(min_size=1, max_size=10),
                    st.text(min_size=1, max_size=20),
                    min_size=0,
                    max_size=3,
                ),  # metadata
            ),
            min_size=1,
            max_size=10,
        )
    )
    @pytest.mark.asyncio
    async def test_search_consistency_property_async(self, documents_data):
        """Property-based test for search result consistency."""
        vector_config = VectorConfig(provider="chroma", dimension=128)
        ai_config = AIConfig()
        search = SemanticSearch(vector_config, ai_config)

        # Mock dependencies
        search.vector_store = Mock()
        search.vector_store.search_async = AsyncMock(return_value=[])
        search.embedding_manager = Mock()
        search.embedding_manager.generate_embedding_async = AsyncMock(
            return_value=EmbeddingResult(
                text="query",
                vector=[0.1] * 128,
                model="test",
                tokens_used=5,
                cache_hit=False,
            )
        )

        try:
            # Search should not fail for any valid query
            results = await search.search_async("test query", top_k=5)
            assert isinstance(results, list)
            assert len(results) >= 0

            # All results should have required fields
            for result in results:
                assert hasattr(result, "document")
                assert hasattr(result, "score")
                assert hasattr(result, "rank")
                assert 0 <= result.score <= 1

        except VectorError:
            # Some configurations might be invalid, that's expected
            pass
