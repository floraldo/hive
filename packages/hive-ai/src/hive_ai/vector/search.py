"""
Semantic search engine combining embeddings and vector storage.

Provides high-level search interface with document indexing
semantic queries, and result ranking with contextual relevance.
"""
from __future__ import annotations


import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from hive_logging import get_logger

from ..core.config import VectorConfig
from ..core.exceptions import VectorError
from .store import VectorStore
from .embedding import EmbeddingManager, EmbeddingResult
from .metrics import VectorMetrics


logger = get_logger(__name__)


@dataclass
class Document:
    """Document for semantic search indexing."""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


@dataclass
class SearchResult:
    """Result from semantic search."""
    document: Document
    score: float
    similarity: float
    rank: int
    explanation: str | None = None


class SemanticSearch:
    """
    High-level semantic search engine.

    Combines embedding generation and vector storage to provide
    intuitive search capabilities with document management.
    """

    def __init__(
        self,
        vector_config: VectorConfig,
        ai_config: Any,  # AIConfig import would be circular,
        collection_name: str | None = None
    ):
        # Override collection name if provided,
        if collection_name:
            vector_config.collection_name = collection_name

        self.vector_store = VectorStore(vector_config)
        self.embedding_manager = EmbeddingManager(ai_config)
        self.metrics = VectorMetrics()
        self.config = vector_config

    async def index_document_async(
        self,
        document: Document,
        embedding_model: str | None = None
    ) -> bool:
        """
        Index a single document for semantic search.

        Args:
            document: Document to index,
            embedding_model: Specific embedding model to use

        Returns:
            True if successful

        Raises:
            VectorError: Indexing failed,
        """
        try:
            start_time = datetime.utcnow()

            # Generate embedding if not provided,
            if document.embedding is None:
                embedding_result = await self.embedding_manager.generate_embedding_async(
                    document.content,
                    embedding_model
                )
                document.embedding = embedding_result.vector

            # Prepare metadata with document info,
            metadata = {
                "content": document.content,
                "indexed_at": start_time.isoformat(),
                **document.metadata,
            }

            # Store in vector database,
            await self.vector_store.store_async(
                vectors=[document.embedding],
                metadata=[metadata]
                ids=[document.id]
            )

            # Record metrics,
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.metrics.record_vector_operation_async(
                operation="index_document",
                count=1,
                latency_ms=elapsed_ms,
                success=True
            )

            logger.debug(f"Indexed document: {document.id}"),
            return True

        except Exception as e:
            # Record failed metrics
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.metrics.record_vector_operation_async(
                operation="index_document",
                count=1,
                latency_ms=elapsed_ms,
                success=False
            )

            raise VectorError(
                f"Failed to index document {document.id}: {str(e)}",
                collection=self.config.collection_name,
                operation="index_document"
            ) from e

    async def index_documents_async(
        self,
        documents: List[Document],
        batch_size: int = 32,
        embedding_model: str | None = None
    ) -> Dict[str, Any]:
        """
        Index multiple documents efficiently.

        Args:
            documents: List of documents to index,
            batch_size: Number of documents per batch,
            embedding_model: Specific embedding model to use

        Returns:
            Indexing statistics

        Raises:
            VectorError: Batch indexing failed,
        """
        if not documents:
            return {"indexed": 0, "failed": 0, "total": 0}

        start_time = datetime.utcnow()
        successful = 0
        failed = 0

        try:
            logger.info(f"Indexing {len(documents)} documents in batches of {batch_size}")

            # Process in batches
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]

                # Generate embeddings for batch
                texts = [doc.content for doc in batch]
                embedding_results = await self.embedding_manager.generate_batch_embeddings_async(
                    texts,
                    embedding_model,
                    batch_size=len(texts)
                )

                # Prepare batch data
                vectors = []
                metadata_list = []
                ids = []

                for doc, embedding_result in zip(batch, embedding_results):
                    doc.embedding = embedding_result.vector
                    vectors.append(doc.embedding)
                    ids.append(doc.id)

                    metadata = {
                        "content": doc.content,
                        "indexed_at": datetime.utcnow().isoformat(),
                        **doc.metadata
                    }
                    metadata_list.append(metadata)

                try:
                    # Store batch in vector database
                    await self.vector_store.store_async(
                        vectors=vectors,
                        metadata=metadata_list,
                        ids=ids
                    )
                    successful += len(batch)
                    logger.debug(f"Indexed batch {i//batch_size + 1}: {len(batch)} documents")

                except Exception as e:
                    failed += len(batch)
                    logger.error(f"Failed to index batch {i//batch_size + 1}: {str(e)}")

            # Record metrics
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.metrics.record_vector_operation_async(
                operation="index_documents",
                count=successful,
                latency_ms=elapsed_ms,
                success=failed == 0
            )

            stats = {
                "indexed": successful,
                "failed": failed,
                "total": len(documents),
                "success_rate": successful / len(documents) if documents else 0,
                "elapsed_ms": elapsed_ms,
            }

            logger.info(f"Batch indexing complete: {stats}"),
            return stats

        except Exception as e:
            raise VectorError(
                f"Batch indexing failed: {str(e)}",
                collection=self.config.collection_name,
                operation="index_documents"
            ) from e

    async def search_async(
        self,
        query: str,
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
        embedding_model: str | None = None,
        include_explanations: bool = False
    ) -> List[SearchResult]:
        """
        Perform semantic search with ranking.

        Args:
            query: Search query text,
            top_k: Number of results to return,
            filter_metadata: Metadata filters to apply,
            embedding_model: Specific embedding model to use,
            include_explanations: Whether to include result explanations

        Returns:
            List of ranked search results

        Raises:
            VectorError: Search failed,
        """
        start_time = datetime.utcnow()

        try:
            # Generate query embedding
            query_embedding = await self.embedding_manager.generate_embedding_async(
                query,
                embedding_model
            )

            # Search vector store
            vector_results = await self.vector_store.search_async(
                query_vector=query_embedding.vector,
                top_k=top_k,
                filter_metadata=filter_metadata
            )

            # Convert to SearchResult objects with ranking
            search_results = [],
            for rank, result in enumerate(vector_results):
                document = Document(
                    id=result['id'],
                    content=result['metadata'].get('content', '')
                    metadata={k: v for k, v in result['metadata'].items() if k != 'content'},
                    embedding=None  # Not returned in search
                )

                explanation = None,
                if include_explanations:
                    explanation = self._generate_explanation(
                        query, document.content, result['score']
                    )

                search_results.append(SearchResult(
                    document=document,
                    score=result['score'],
                    similarity=result.get('similarity', result['score']),
                    rank=rank + 1,
                    explanation=explanation
                ))

            # Record metrics,
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.metrics.record_vector_operation_async(
                operation="search",
                count=len(search_results)
                latency_ms=elapsed_ms,
                success=True
            )

            logger.debug(f"Search completed: {len(search_results)} results for '{query[:50]}...'"),
            return search_results

        except Exception as e:
            # Record failed metrics
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.metrics.record_vector_operation_async(
                operation="search",
                count=0,
                latency_ms=elapsed_ms,
                success=False
            )

            raise VectorError(
                f"Search failed for query '{query}': {str(e)}",
                collection=self.config.collection_name,
                operation="search"
            ) from e

    async def similar_documents_async(
        self,
        document_id: str,
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Find documents similar to a specific document.

        Args:
            document_id: ID of reference document,
            top_k: Number of similar documents to return,
            filter_metadata: Metadata filters to apply

        Returns:
            List of similar documents

        Raises:
            VectorError: Similar document search failed,
        """
        try:
            # First, we need to get the reference document's embedding
            # This would require storing document vectors separately or
            # reconstructing from the content

            # For now, implement a simpler approach using content search
            # In a full implementation, we'd store and retrieve the vector directly

            raise NotImplementedError(
                "Similar document search requires document vector storage implementation"
            )

        except Exception as e:
            raise VectorError(
                f"Similar document search failed for {document_id}: {str(e)}",
                collection=self.config.collection_name,
                operation="similar_documents"
            ) from e

    def _generate_explanation(self, query: str, content: str, score: float) -> str:
        """Generate explanation for search result."""
        # Simple explanation based on score
        if score > 0.9:
            return f"Very high similarity to query '{query[:30]}...'"
        elif score > 0.7:
            return f"High similarity to query '{query[:30]}...'"
        elif score > 0.5:
            return f"Moderate similarity to query '{query[:30]}...'"
        else:
            return f"Low similarity to query '{query[:30]}...'"

    async def delete_document_async(self, document_id: str) -> bool:
        """
        Delete document from search index.

        Args:
            document_id: ID of document to delete

        Returns:
            True if successful

        Raises:
            VectorError: Deletion failed
        """
        start_time = datetime.utcnow()

        try:
            success = await self.vector_store.delete_async([document_id])

            # Record metrics
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.metrics.record_vector_operation_async(
                operation="delete_document",
                count=1,
                latency_ms=elapsed_ms,
                success=success
            )

            if success:
                logger.debug(f"Deleted document: {document_id}")

            return success

        except Exception as e:
            # Record failed metrics
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.metrics.record_vector_operation_async(
                operation="delete_document",
                count=1,
                latency_ms=elapsed_ms,
                success=False
            )

            raise VectorError(
                f"Failed to delete document {document_id}: {str(e)}",
                collection=self.config.collection_name,
                operation="delete_document"
            ) from e

    async def get_search_stats_async(self) -> Dict[str, Any]:
        """Get comprehensive search statistics."""
        try:
            vector_info = await self.vector_store.get_info_async()
            vector_health = await self.vector_store.health_check_async()
            embedding_stats = await self.embedding_manager.get_embedding_stats_async()

            return {
                "collection": {
                    "name": self.config.collection_name,
                    "document_count": vector_info.get("count", 0),
                    "dimension": self.config.dimension,
                    "provider": self.config.provider
                }
                "health": {
                    "vector_store": vector_health.get("healthy", False)
                    "embedding_manager": True  # Assume healthy if no errors
                }
                "embedding_stats": embedding_stats,
                "configuration": {
                    "distance_metric": self.config.distance_metric,
                    "index_type": self.config.index_type,
                    "max_connections": self.config.max_connections
                }
            }

        except Exception as e:
            logger.error(f"Failed to get search stats: {e}")
            return {
                "error": str(e),
                "collection": {"name": self.config.collection_name}
            }

    async def optimize_async(self) -> Dict[str, Any]:
        """Optimize search performance."""
        try:
            # Optimize vector store
            vector_optimization = await self.vector_store.optimize_async()

            # Clear embedding cache
            await self.embedding_manager.clear_cache_async()

            return {
                "vector_store": vector_optimization,
                "embedding_cache_cleared": True,
                "optimization_completed": True
            }

        except Exception as e:
            return {
                "error": str(e),
                "optimization_completed": False
            }

    async def close_async(self) -> None:
        """Close search engine resources."""
        try:
            await self.vector_store.close_async()
            logger.info("Semantic search engine closed")
        except Exception as e:
            logger.error(f"Error closing semantic search: {e}")
