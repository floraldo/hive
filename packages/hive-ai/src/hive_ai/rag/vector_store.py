"""
Vector store for semantic search using FAISS.

Provides efficient similarity search with persistence and metadata filtering.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from hive_logging import get_logger

from .models import CodeChunk, RetrievalResult

logger = get_logger(__name__)


class VectorStore:
    """
    FAISS-based vector store for semantic code search.

    Features:
    - Efficient similarity search (cosine similarity)
    - Metadata filtering
    - Persistence (save/load index)
    - Incremental indexing
    """

    def __init__(self, embedding_dim: int = 384):
        """
        Initialize vector store.

        Args:
            embedding_dim: Dimension of embeddings (default: 384 for all-MiniLM-L6-v2)
        """
        self.embedding_dim = embedding_dim

        # FAISS index (using cosine similarity via inner product with normalized vectors)
        self.index = faiss.IndexFlatIP(embedding_dim)

        # Metadata storage (chunk objects indexed by position)
        self.chunks: list[CodeChunk] = []

        logger.info(f"Initialized vector store with {embedding_dim}-dim embeddings")

    def add_chunks(self, chunks: list[CodeChunk]) -> None:
        """
        Add chunks to the vector store.

        Args:
            chunks: List of CodeChunks with embeddings attached
        """
        if not chunks:
            return

        # Filter chunks that have embeddings
        chunks_with_embeddings = [c for c in chunks if c.embedding is not None]

        if not chunks_with_embeddings:
            logger.warning("No chunks with embeddings to add")
            return

        # Extract and normalize embeddings
        embeddings = np.array([c.embedding for c in chunks_with_embeddings], dtype=np.float32)

        # Normalize for cosine similarity (FAISS uses inner product)
        faiss.normalize_L2(embeddings)

        # Add to index
        self.index.add(embeddings)

        # Store chunks
        self.chunks.extend(chunks_with_embeddings)

        logger.info(f"Added {len(chunks_with_embeddings)} chunks to vector store")

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """
        Search for similar chunks.

        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            filters: Optional filters (e.g., {"exclude_archived": True})

        Returns:
            List of RetrievalResult objects sorted by score
        """
        if self.index.ntotal == 0:
            logger.warning("Vector store is empty")
            return []

        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query_embedding)

        # Search
        # Retrieve more than k to account for filtering
        search_k = min(k * 3, self.index.ntotal)
        scores, indices = self.index.search(query_embedding, search_k)

        # Build results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= len(self.chunks):  # Safety check
                continue

            chunk = self.chunks[idx]

            # Apply filters
            if filters:
                if filters.get("exclude_archived") and chunk.is_archived:
                    continue

                if filters.get("usage_context") and chunk.usage_context != filters["usage_context"]:
                    continue

                if filters.get("chunk_types") and chunk.chunk_type not in filters["chunk_types"]:
                    continue

            results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=float(score),
                    retrieval_method="semantic",
                )
            )

            # Stop once we have enough results
            if len(results) >= k:
                break

        # Rank results
        for i, result in enumerate(results):
            result.rank = i + 1

        logger.debug(f"Vector search returned {len(results)} results")
        return results

    def save(self, path: Path | str) -> None:
        """
        Save vector store to disk.

        Args:
            path: Directory path to save index and metadata
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        index_path = path / "faiss.index"
        faiss.write_index(self.index, str(index_path))

        # Save chunks metadata
        chunks_path = path / "chunks.pkl"
        with open(chunks_path, "wb") as f:
            pickle.dump(self.chunks, f)

        logger.info(f"Saved vector store to {path}")

    def load(self, path: Path | str) -> None:
        """
        Load vector store from disk.

        Args:
            path: Directory path containing saved index and metadata
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Vector store not found at {path}")

        # Load FAISS index
        index_path = path / "faiss.index"
        if index_path.exists():
            self.index = faiss.read_index(str(index_path))
        else:
            raise FileNotFoundError(f"FAISS index not found at {index_path}")

        # Load chunks metadata
        chunks_path = path / "chunks.pkl"
        if chunks_path.exists():
            with open(chunks_path, "rb") as f:
                self.chunks = pickle.load(f)
        else:
            raise FileNotFoundError(f"Chunks metadata not found at {chunks_path}")

        logger.info(f"Loaded vector store from {path}: {len(self.chunks)} chunks")

    def get_stats(self) -> dict[str, Any]:
        """Get vector store statistics."""
        return {
            "total_chunks": len(self.chunks),
            "embedding_dim": self.embedding_dim,
            "indexed_vectors": self.index.ntotal,
        }

    def clear(self) -> None:
        """Clear all data from vector store."""
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.chunks = []
        logger.info("Vector store cleared")
