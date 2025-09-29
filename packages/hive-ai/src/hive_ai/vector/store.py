"""
Vector database store implementation with multi-provider support.

Provides unified interface for vector operations across different
vector database providers with hive-db integration patterns.
"""

from abc import ABC, abstractmethod
from typing import Any

from hive_async import AsyncCircuitBreaker, async_retry
from hive_cache import CacheManager
from hive_logging import get_logger

from ..core.config import VectorConfig
from ..core.exceptions import VectorError
from ..core.interfaces import VectorStoreInterface

logger = get_logger(__name__)


class BaseVectorProvider(ABC):
    """Abstract base for vector database providers."""

    def __init__(self, config: VectorConfig) -> None:
        self.config = config

    @abstractmethod
    async def store_vectors_async(
        self,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]],
        ids: list[str] | None = None,
    ) -> list[str]:
        """Store vectors in the database."""
        pass

    @abstractmethod
    async def search_vectors_async(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors."""
        pass

    @abstractmethod
    async def delete_vectors_async(self, ids: list[str]) -> bool:
        """Delete vectors by IDs."""
        pass

    @abstractmethod
    async def get_collection_info_async(self) -> dict[str, Any]:
        """Get information about the collection."""
        pass

    @abstractmethod
    async def health_check_async(self) -> bool:
        """Check provider health."""
        pass


class ChromaProvider(BaseVectorProvider):
    """ChromaDB vector database provider."""

    def __init__(self, config: VectorConfig) -> None:
        super().__init__(config)
        self._client = None
        self._collection = None

    async def _get_client_async(self) -> None:
        """Get or create ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings

                if self.config.connection_string:
                    # Remote ChromaDB
                    host, port = self.config.connection_string.split(":")
                    self._client = chromadb.HttpClient(
                        host=host,
                        port=int(port),
                        settings=Settings(anonymized_telemetry=False),
                    )
                else:
                    # Local ChromaDB
                    self._client = chromadb.Client()

                # Get or create collection
                self._collection = self._client.get_or_create_collection(
                    name=self.config.collection_name,
                    metadata={"dimension": self.config.dimension},
                )

                logger.info(f"Connected to ChromaDB collection: {self.config.collection_name}")

            except ImportError:
                raise VectorError(
                    "ChromaDB not installed. Install with: pip install chromadb",
                    collection=self.config.collection_name,
                    operation="initialize",
                )
            except Exception as e:
                raise VectorError(
                    f"Failed to connect to ChromaDB: {str(e)}",
                    collection=self.config.collection_name,
                    operation="connect",
                ) from e

        return self._client, self._collection

    async def store_vectors_async(
        self,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]],
        ids: list[str] | None = None,
    ) -> list[str]:
        """Store vectors in ChromaDB."""
        _, collection = await self._get_client_async()

        if ids is None:
            import uuid

            ids = [str(uuid.uuid4()) for _ in vectors]

        try:
            collection.add(embeddings=vectors, metadatas=metadata, ids=ids)
            logger.debug(f"Stored {len(vectors)} vectors in ChromaDB")
            return ids

        except Exception as e:
            raise VectorError(
                f"Failed to store vectors: {str(e)}",
                collection=self.config.collection_name,
                operation="store",
            ) from e

    async def search_vectors_async(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors in ChromaDB."""
        _, collection = await self._get_client_async()

        try:
            results = collection.query(query_embeddings=[query_vector], n_results=top_k, where=filter_metadata)

            # Transform results to standard format
            search_results = []
            for i in range(len(results["ids"][0])):
                search_results.append(
                    {
                        "id": results["ids"][0][i],
                        "distance": results["distances"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "score": 1.0 - results["distances"][0][i],  # Convert distance to similarity,
                    }
                )

            logger.debug(f"Found {len(search_results)} similar vectors")
            return search_results

        except Exception as e:
            raise VectorError(
                f"Failed to search vectors: {str(e)}",
                collection=self.config.collection_name,
                operation="search",
            ) from e

    async def delete_vectors_async(self, ids: list[str]) -> bool:
        """Delete vectors from ChromaDB."""
        _, collection = await self._get_client_async()

        try:
            collection.delete(ids=ids)
            logger.debug(f"Deleted {len(ids)} vectors from ChromaDB")
            return True

        except Exception as e:
            logger.error(f"Failed to delete vectors: {str(e)}")
            return False

    async def get_collection_info_async(self) -> dict[str, Any]:
        """Get ChromaDB collection information."""
        _, collection = await self._get_client_async()

        try:
            count = collection.count()
            return {
                "name": self.config.collection_name,
                "count": count,
                "dimension": self.config.dimension,
                "provider": "chromadb",
            }

        except Exception as e:
            raise VectorError(
                f"Failed to get collection info: {str(e)}",
                collection=self.config.collection_name,
                operation="info",
            ) from e

    async def health_check_async(self) -> bool:
        """Check ChromaDB health."""
        try:
            client, collection = await self._get_client_async()
            # Simple health check - try to count documents
            collection.count()
            return True
        except ConnectionError as e:
            logger.warning(f"Vector store connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Vector store health check failed: {e}")
            return False


class VectorStore(VectorStoreInterface):
    """
    Unified vector store with multi-provider support.

    Provides consistent interface across vector database providers
    with caching, circuit breaker, and hive-db integration.
    """

    def __init__(self, config: VectorConfig) -> None:
        self.config = config
        self._provider = self._create_provider()
        self._circuit_breaker = AsyncCircuitBreaker(failure_threshold=5, recovery_timeout=60)
        self._cache = CacheManager(f"vector_store_{config.collection_name}")

    def _create_provider(self) -> BaseVectorProvider:
        """Create provider instance based on configuration."""
        provider_map = {
            "chroma": ChromaProvider,
            "chromadb": ChromaProvider,
            # Additional providers can be added here
            # "pinecone": PineconeProvider,
            # "weaviate": WeaviateProvider,
            # "faiss": FaissProvider,
        }

        provider_class = provider_map.get(self.config.provider.lower())
        if not provider_class:
            available = list(provider_map.keys())
            raise VectorError(
                f"Unsupported vector provider: {self.config.provider}. Available: {available}",
                operation="initialize",
            )

        return provider_class(self.config)

    @async_retry(max_attempts=3, delay=1.0)
    async def store_async(
        self,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]],
        ids: list[str] | None = None,
    ) -> list[str]:
        """Store vectors with retry and circuit breaker."""
        if len(vectors) != len(metadata):
            raise VectorError(
                f"Vector count ({len(vectors)}) must match metadata count ({len(metadata)})",
                collection=self.config.collection_name,
                operation="store",
            )

        # Validate vector dimensions
        for i, vector in enumerate(vectors):
            if len(vector) != self.config.dimension:
                raise VectorError(
                    f"Vector {i} has dimension {len(vector)}, expected {self.config.dimension}",
                    collection=self.config.collection_name,
                    operation="store",
                )

        return await self._circuit_breaker.call_async(self._provider.store_vectors_async, vectors, metadata, ids)

    @async_retry(max_attempts=3, delay=1.0)
    async def search_async(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search vectors with caching and circuit breaker."""
        if len(query_vector) != self.config.dimension:
            raise VectorError(
                f"Query vector has dimension {len(query_vector)}, expected {self.config.dimension}",
                collection=self.config.collection_name,
                operation="search",
            )

        # Create cache key
        cache_key = f"search_{hash(str(query_vector))}_{top_k}_{hash(str(filter_metadata))}"
        cached_result = self._cache.get(cache_key)

        if cached_result is not None:
            logger.debug("Returning cached search results")
            return cached_result

        # Execute search
        results = await self._circuit_breaker.call_async(
            self._provider.search_vectors_async, query_vector, top_k, filter_metadata
        )

        # Cache results for 5 minutes
        self._cache.set(cache_key, results, ttl=300)
        return results

    async def delete_async(self, ids: list[str]) -> bool:
        """Delete vectors with circuit breaker."""
        if not ids:
            return True

        # Clear relevant caches
        self._cache.clear()

        return await self._circuit_breaker.call_async(self._provider.delete_vectors_async, ids)

    async def get_info_async(self) -> dict[str, Any]:
        """Get collection information."""
        cache_key = "collection_info"
        cached_info = self._cache.get(cache_key)

        if cached_info is not None:
            return cached_info

        info = await self._provider.get_collection_info_async()

        # Cache for 2 minutes
        self._cache.set(cache_key, info, ttl=120)
        return info

    async def health_check_async(self) -> dict[str, Any]:
        """Comprehensive health check."""
        try:
            provider_healthy = await self._provider.health_check_async()
            circuit_stats = self._circuit_breaker.get_stats()

            return {
                "healthy": provider_healthy and circuit_stats.get("state") != "OPEN",
                "provider": self.config.provider,
                "collection": self.config.collection_name,
                "circuit_breaker": circuit_stats,
                "cache_size": self._cache.size() if hasattr(self._cache, "size") else 0,
            }

        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "provider": self.config.provider,
                "collection": self.config.collection_name,
            }

    async def optimize_async(self) -> dict[str, Any]:
        """Optimize vector store performance."""
        # Clear old cache entries
        self._cache.clear()

        # Get collection stats
        info = await self.get_info_async()

        optimization_results = {
            "cache_cleared": True,
            "collection_info": info,
            "recommendations": [],
        }

        # Add optimization recommendations based on collection size
        if info.get("count", 0) > 10000:
            optimization_results["recommendations"].append("Consider using approximate search for large collections")

        if info.get("count", 0) < 100:
            optimization_results["recommendations"].append("Collection is small, exact search is optimal")

        return optimization_results

    async def close_async(self) -> None:
        """Close vector store connections."""
        try:
            if hasattr(self._provider, "close_async"):
                await self._provider.close_async()
        except Exception as e:
            logger.error(f"Error closing vector store: {e}")

        self._cache.clear()
