"""
Vector Indexer

Stores knowledge fragments in RAG vector database for semantic search.
Supports multi-vector approach where each fragment gets its own embedding.
"""

from __future__ import annotations

from typing import Any

from hive_ai.vector.embedding import EmbeddingManager
from hive_ai.vector.store import VectorStore
from hive_config import AIConfig, VectorConfig, create_config_from_sources
from hive_errors import RetryStrategy, with_retry
from hive_logging import get_logger

from .fragment_parser import KnowledgeFragment

logger = get_logger(__name__)


class VectorIndexer:
    """
    Index knowledge fragments into vector database.

    Implements Decision 2-B: Multi-vector approach where each fragment
    (summary, error, decision, artifact) gets its own embedding and vector ID.
    """

    def __init__(
        self,
        embedding_manager: EmbeddingManager | None = None,
        vector_store: VectorStore | None = None,
        config: AIConfig | None = None
    ):
        """
        Initialize vector indexer.

        Args:
            embedding_manager: Embedding generator (auto-created if None)
            vector_store: Vector database (auto-created if None)
            config: AI configuration (auto-loaded if None)
        """
        self.config = config or create_config_from_sources().ai

        # Initialize embedding manager
        self.embedding_manager = embedding_manager or EmbeddingManager(self.config)

        # Initialize vector store
        if vector_store is None:
            vector_config = VectorConfig(
                provider="chromadb",  # or from config
                collection_name="hive_knowledge",
                dimension=384,  # sentence-transformers/all-MiniLM-L6-v2
                connection_string=None  # local ChromaDB
            )
            self.vector_store = VectorStore(vector_config)
        else:
            self.vector_store = vector_store

        logger.info("VectorIndexer initialized with ChromaDB backend")

    @with_retry(RetryStrategy(max_attempts=3, min_wait=1.0, max_wait=5.0))
    async def index_fragments_async(
        self,
        fragments: list[KnowledgeFragment]
    ) -> list[str]:
        """
        Index knowledge fragments into vector database.

        Args:
            fragments: List of knowledge fragments to index

        Returns:
            List of vector IDs (document IDs in vector store)

        Raises:
            VectorError: If indexing fails after retries
        """
        if not fragments:
            logger.warning("No fragments to index")
            return []

        # Extract texts for embedding
        texts = [fragment.content for fragment in fragments]

        # Generate embeddings in batch (efficient)
        logger.info(f"Generating embeddings for {len(fragments)} fragments")
        embedding_results = await self.embedding_manager.generate_batch_embeddings_async(
            texts=texts,
            batch_size=32,
            use_cache=True
        )

        # Prepare vectors and metadata
        vectors = [result.vector for result in embedding_results]
        metadata_list = []

        for fragment in fragments:
            metadata = {
                "task_id": fragment.task_id,
                "fragment_type": fragment.fragment_type,
                "task_type": fragment.task_type,
                "status": fragment.status,
                "timestamp": fragment.timestamp,
                "is_archived": False,
                "usage_context": fragment.task_type,  # for filtering
                **fragment.metadata  # merge additional metadata
            }
            metadata_list.append(metadata)

        # Store in vector database
        logger.info(f"Storing {len(vectors)} vectors in ChromaDB")
        vector_ids = await self.vector_store.store_async(
            vectors=vectors,
            metadata=metadata_list,
            ids=None  # auto-generate IDs
        )

        logger.info(
            f"Successfully indexed {len(vector_ids)} fragments. "
            f"Cache hits: {sum(1 for r in embedding_results if r.cache_hit)}/{len(embedding_results)}"
        )

        return vector_ids

    async def archive_old_fragments_async(
        self,
        age_threshold_days: int = 90,
        min_retrieval_count: int = 5
    ) -> int:
        """
        Archive cold knowledge fragments (Curator mode).

        Marks fragments as archived if they meet criteria:
        - Older than age_threshold_days
        - Retrieved fewer than min_retrieval_count times

        Args:
            age_threshold_days: Age threshold in days
            min_retrieval_count: Minimum retrieval count to keep active

        Returns:
            Number of fragments archived
        """
        # Phase 2 enhancement - not implemented yet
        logger.info(
            f"Archive operation triggered (threshold: {age_threshold_days} days, "
            f"min retrievals: {min_retrieval_count})"
        )

        # Future: Query vector store for old, low-retrieval fragments
        # Update their metadata: is_archived = True
        # Return count of archived fragments

        return 0

    async def get_indexing_stats_async(self) -> dict[str, Any]:
        """Get vector indexing statistics."""
        collection_info = await self.vector_store.get_info_async()
        embedding_stats = await self.embedding_manager.get_embedding_stats_async()

        return {
            "vector_store": collection_info,
            "embedding_manager": embedding_stats,
            "indexer_health": "operational"
        }


__all__ = ["VectorIndexer"]
