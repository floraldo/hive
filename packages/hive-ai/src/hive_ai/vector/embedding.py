"""
Embedding generation and management with multi-provider support.

Handles text-to-vector conversion with caching, batching,
and integration with the model management system.
"""

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from hive_async import gather_with_concurrency
from hive_cache import CacheManager
from hive_logging import get_logger

from ..core.config import AIConfig
from ..core.exceptions import ModelError, VectorError
from ..models.client import ModelClient
from ..models.registry import ModelRegistry

logger = get_logger(__name__)


@dataclass
class EmbeddingResult:
    """Result from embedding generation."""

    text: str
    vector: List[float]
    model: str
    tokens_used: int
    cache_hit: bool


class EmbeddingManager:
    """
    Manages text embedding generation across providers.

    Provides efficient embedding generation with caching,
    batching, and automatic model selection.
    """

    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self.model_client = ModelClient(config)
        self.registry = ModelRegistry(config)
        self.cache = CacheManager("embeddings")

        # Default embedding models by provider
        self._default_models = {
            "openai": "text-embedding-ada-002",
            "anthropic": "claude-3-sonnet",  # Fallback, Anthropic doesn't have embedding models
            "local": "sentence-transformers/all-MiniLM-L6-v2",
        }

    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key for text and model combination."""
        # Create hash of text and model for consistent caching
        content = f"{text}|{model}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _get_embedding_model(self, model: Optional[str] = None) -> str:
        """Get appropriate embedding model."""
        if model:
            return model

        # Find the best available embedding model
        embedding_models = self.registry.get_models_by_type("embedding")

        if embedding_models:
            # Use the cheapest healthy embedding model
            cheapest = self.registry.get_cheapest_model("embedding")
            if cheapest:
                return cheapest

            # Fallback to first available
            for model_name in embedding_models:
                if self.registry.validate_model_available(model_name):
                    return model_name

        # No embedding models configured, try completion models
        completion_models = self.registry.get_models_by_type("completion") + self.registry.get_models_by_type("chat")

        if completion_models:
            logger.warning("No embedding models available, using completion model")
            return completion_models[0]

        raise VectorError("No embedding or completion models available", operation="get_embedding_model")

    async def generate_embedding_async(
        self, text: str, model: Optional[str] = None, use_cache: bool = True
    ) -> EmbeddingResult:
        """
        Generate embedding for single text.

        Args:
            text: Text to embed
            model: Specific model to use (auto-select if None)
            use_cache: Whether to use cached embeddings

        Returns:
            EmbeddingResult with vector and metadata

        Raises:
            VectorError: Embedding generation failed
        """
        if not text.strip():
            raise VectorError("Cannot generate embedding for empty text", operation="generate_embedding")

        embedding_model = self._get_embedding_model(model)
        cache_key = self._get_cache_key(text, embedding_model)

        # Check cache first
        if use_cache:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for embedding: {text[:50]}...")
                return EmbeddingResult(
                    text=text,
                    vector=cached_result["vector"],
                    model=embedding_model,
                    tokens_used=cached_result["tokens_used"],
                    cache_hit=True,
                )

        try:
            # Check if this is a true embedding model or completion model
            model_config = self.registry.get_model_config(embedding_model)

            if model_config.model_type == "embedding":
                # Use dedicated embedding API
                vector = await self._generate_embedding_vector_async(text, embedding_model)
                tokens_used = len(text.split())  # Rough estimate for embeddings
            else:
                # Use completion model to generate embedding-like representation
                # This is a fallback for when no embedding models are available
                vector = await self._generate_completion_embedding_async(text, embedding_model)
                tokens_used = len(text.split()) * 2  # Higher token usage for completion

            result = EmbeddingResult(
                text=text, vector=vector, model=embedding_model, tokens_used=tokens_used, cache_hit=False
            )

            # Cache the result
            if use_cache:
                self.cache.set(cache_key, {"vector": vector, "tokens_used": tokens_used}, ttl=3600)  # Cache for 1 hour

            logger.debug(f"Generated embedding for text: {text[:50]}... (dim: {len(vector)})")
            return result

        except Exception as e:
            raise VectorError(f"Failed to generate embedding: {str(e)}", operation="generate_embedding") from e

    async def _generate_embedding_vector_async(self, text: str, model: str) -> List[float]:
        """Generate embedding using dedicated embedding model."""
        # This would integrate with the actual embedding API
        # For now, this is a placeholder that would need provider-specific implementation

        model_config = self.registry.get_model_config(model)
        provider = self.registry.get_provider(model_config.provider)

        if hasattr(provider, "generate_embedding_async"):
            return await provider.generate_embedding_async(text, model)
        else:
            # Fallback to simulated embedding
            return await self._simulate_embedding_async(text)

    async def _generate_completion_embedding_async(self, text: str, model: str) -> List[float]:
        """Generate embedding-like vector using completion model."""
        # This is a fallback approach - not recommended for production
        logger.warning(f"Using completion model {model} for embedding generation")

        # Use a simple approach to generate embeddings from text
        return await self._simulate_embedding_async(text)

    async def _simulate_embedding_async(self, text: str, dimension: int = 1536) -> List[float]:
        """Simulate embedding generation for testing/fallback."""
        # Create a simple hash-based embedding for testing
        # In production, this should be replaced with real embedding models

        import hashlib
        import struct

        # Create deterministic embedding based on text hash
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()

        # Convert hash to float vector
        vector = []
        for i in range(0, min(len(hash_bytes) - 3, dimension * 4), 4):
            float_val = struct.unpack("f", hash_bytes[i : i + 4])[0]
            # Normalize to [-1, 1] range
            vector.append(max(-1.0, min(1.0, float_val)))

        # Pad or truncate to desired dimension
        while len(vector) < dimension:
            vector.append(0.0)

        return vector[:dimension]

    async def generate_batch_embeddings_async(
        self,
        texts: List[str],
        model: Optional[str] = None,
        batch_size: int = 32,
        use_cache: bool = True,
        max_concurrency: int = 5,
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            model: Specific model to use
            batch_size: Number of texts to process per batch
            use_cache: Whether to use cached embeddings
            max_concurrency: Maximum concurrent operations

        Returns:
            List of EmbeddingResults

        Raises:
            VectorError: Batch embedding generation failed
        """
        if not texts:
            return []

        logger.info(f"Generating embeddings for {len(texts)} texts")

        # Split into batches
        batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]

        async def process_batch_async(batch: List[str]) -> List[EmbeddingResult]:
            tasks = [self.generate_embedding_async(text, model, use_cache) for text in batch]
            return await gather_with_concurrency(tasks, max_concurrency)

        try:
            # Process all batches
            batch_tasks = [process_batch_async(batch) for batch in batches]
            batch_results = await gather_with_concurrency(batch_tasks, max_concurrency=3)

            # Flatten results
            all_results = []
            for batch_result in batch_results:
                all_results.extend(batch_result)

            # Calculate statistics
            cache_hits = sum(1 for r in all_results if r.cache_hit)
            total_tokens = sum(r.tokens_used for r in all_results)

            logger.info(
                f"Batch embedding complete: {len(all_results)} embeddings, "
                f"{cache_hits} cache hits, {total_tokens} tokens used"
            )

            return all_results

        except Exception as e:
            raise VectorError(
                f"Batch embedding generation failed: {str(e)}", operation="generate_batch_embeddings"
            ) from e

    async def search_similar_texts_async(
        self, query_text: str, candidate_texts: List[str], top_k: int = 5, model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find most similar texts using embedding similarity.

        Args:
            query_text: Text to find similarities for
            candidate_texts: List of texts to compare against
            top_k: Number of top results to return
            model: Embedding model to use

        Returns:
            List of similarity results with scores

        Raises:
            VectorError: Similarity search failed
        """
        if not candidate_texts:
            return []

        try:
            # Generate embedding for query
            query_result = await self.generate_embedding_async(query_text, model)

            # Generate embeddings for candidates
            candidate_results = await self.generate_batch_embeddings_async(candidate_texts, model)

            # Calculate similarities
            similarities = []
            for i, candidate_result in enumerate(candidate_results):
                similarity = self._calculate_cosine_similarity(query_result.vector, candidate_result.vector)
                similarities.append(
                    {
                        "index": i,
                        "text": candidate_result.text,
                        "similarity": similarity,
                        "model": candidate_result.model,
                    }
                )

            # Sort by similarity and return top k
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            return similarities[:top_k]

        except Exception as e:
            raise VectorError(f"Similar text search failed: {str(e)}", operation="search_similar_texts") from e

    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            raise VectorError(
                f"Vector dimensions don't match: {len(vec1)} vs {len(vec2)}", operation="cosine_similarity"
            )

        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Calculate magnitudes
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    async def get_embedding_stats_async(self) -> Dict[str, Any]:
        """Get embedding generation statistics."""
        cache_stats = {
            "cache_size": self.cache.size() if hasattr(self.cache, "size") else 0,
            "cache_hit_rate": "N/A",  # Would need tracking to calculate
        }

        available_models = self.registry.get_models_by_type("embedding")

        return {
            "available_embedding_models": available_models,
            "default_model": self._get_embedding_model(),
            "cache_stats": cache_stats,
            "supported_providers": list(self._default_models.keys()),
        }

    async def clear_cache_async(self) -> bool:
        """Clear embedding cache."""
        try:
            self.cache.clear()
            logger.info("Embedding cache cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear embedding cache: {e}")
            return False
