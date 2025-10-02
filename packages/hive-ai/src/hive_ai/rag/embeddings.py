"""
Embedding generation for code chunks with caching and batch processing.

Provides sentence-transformers integration with intelligent caching
using hive-cache for performance optimization.
"""

from __future__ import annotations

import hashlib
from typing import Any

import msgpack
import numpy as np
from sentence_transformers import SentenceTransformer

from hive_cache import CacheManager
from hive_logging import get_logger

from .models import CodeChunk

logger = get_logger(__name__)


class EmbeddingGenerator:
    """
    Generate embeddings for code chunks using sentence-transformers.

    Features:
    - Multi-level caching (hot cache + Redis via hive-cache)
    - Batch processing for efficiency
    - Automatic embedding dimension detection
    - Integration with CodeChunk.get_enriched_code()
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache_ttl: int = 604800,  # 1 week
        device: str | None = None,
    ):
        """
        Initialize embedding generator.

        Args:
            model_name: HuggingFace model name (default: all-MiniLM-L6-v2, 384-dim)
            cache_ttl: Cache TTL in seconds (default: 1 week)
            device: Device to use ('cpu', 'cuda', or None for auto)
        """
        self.model_name = model_name
        self.cache_ttl = cache_ttl

        # Initialize model
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name, device=device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded: {self.embedding_dim}-dimensional embeddings")

        # Initialize cache
        self.cache = CacheManager("rag_embeddings")
        self.hot_cache: dict[str, np.ndarray] = {}  # In-memory cache

    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Numpy array with embedding vector
        """
        # Check hot cache
        cache_key = self._compute_cache_key(text)

        if cache_key in self.hot_cache:
            logger.debug(f"Hot cache hit for text hash: {cache_key[:8]}")
            return self.hot_cache[cache_key]

        # Check Redis cache
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Redis cache hit for text hash: {cache_key[:8]}")
            embedding = msgpack.unpackb(cached, raw=False)
            embedding_array = np.array(embedding, dtype=np.float32)
            # Store in hot cache
            self.hot_cache[cache_key] = embedding_array
            return embedding_array

        # Generate embedding
        logger.debug(f"Generating embedding for text hash: {cache_key[:8]}")
        embedding = self.model.encode(text, convert_to_numpy=True)

        # Cache embedding
        self._cache_embedding(cache_key, embedding)

        return embedding

    def generate_embeddings_batch(self, texts: list[str], batch_size: int = 32) -> list[np.ndarray]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for model encoding

        Returns:
            List of numpy arrays with embedding vectors
        """
        embeddings = ([],)
        uncached_texts = ([],)
        uncached_indices = []

        # Check cache for all texts
        for i, text in enumerate(texts):
            cache_key = self._compute_cache_key(text)

            # Try hot cache
            if cache_key in self.hot_cache:
                embeddings.append((i, self.hot_cache[cache_key]))
                continue

            # Try Redis cache
            cached = self.cache.get(cache_key)
            if cached:
                embedding_array = np.array(msgpack.unpackb(cached, raw=False), dtype=np.float32)
                self.hot_cache[cache_key] = embedding_array
                embeddings.append((i, embedding_array))
                continue

            # Mark for generation
            uncached_texts.append(text)
            uncached_indices.append(i)

        # Generate embeddings for uncached texts in batches
        if uncached_texts:
            logger.info(f"Generating {len(uncached_texts)} embeddings in batch")
            new_embeddings = self.model.encode(
                uncached_texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=len(uncached_texts) > 100,
            )

            # Cache new embeddings
            for text, embedding in zip(uncached_texts, new_embeddings, strict=False):
                cache_key = self._compute_cache_key(text)
                self._cache_embedding(cache_key, embedding)

            # Add to results
            for idx, embedding in zip(uncached_indices, new_embeddings, strict=False):
                embeddings.append((idx, embedding))

        # Sort by original index and return
        embeddings.sort(key=lambda x: x[0])
        return [emb for _, emb in embeddings]

    def embed_chunk(self, chunk: CodeChunk) -> CodeChunk:
        """
        Generate and attach embedding to a CodeChunk.

        Uses chunk.get_enriched_code() for better semantic representation.

        Args:
            chunk: CodeChunk to embed

        Returns:
            Same CodeChunk with embedding attached
        """
        enriched_code = (chunk.get_enriched_code(),)
        embedding = self.generate_embedding(enriched_code)
        chunk.embedding = embedding
        return chunk

    def embed_chunks_batch(self, chunks: list[CodeChunk], batch_size: int = 32) -> list[CodeChunk]:
        """
        Generate embeddings for multiple chunks efficiently.

        Args:
            chunks: List of CodeChunks to embed
            batch_size: Batch size for encoding

        Returns:
            Same chunks with embeddings attached
        """
        # Extract enriched code from all chunks
        texts = [chunk.get_enriched_code() for chunk in chunks]

        # Generate embeddings in batch
        embeddings = self.generate_embeddings_batch(texts, batch_size)

        # Attach embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            chunk.embedding = embedding

        logger.info(f"Embedded {len(chunks)} chunks")
        return chunks

    def _compute_cache_key(self, text: str) -> str:
        """
        Compute cache key for text.

        Uses SHA-256 hash of text + model name for uniqueness.
        """
        content = f"{self.model_name}::{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _cache_embedding(self, cache_key: str, embedding: np.ndarray) -> None:
        """Cache embedding in hot cache and Redis."""
        # Store in hot cache
        self.hot_cache[cache_key] = embedding

        # Store in Redis cache
        embedding_bytes = msgpack.packb(embedding.tolist())
        self.cache.set(cache_key, embedding_bytes, ttl=self.cache_ttl)

    def clear_cache(self) -> None:
        """Clear both hot cache and Redis cache."""
        self.hot_cache.clear()
        # Note: hive-cache doesn't have clear_all, would need pattern delete
        logger.info("Embedding cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get embedding generator statistics."""
        return {
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "hot_cache_size": len(self.hot_cache),
            "cache_ttl_seconds": self.cache_ttl,
        }
