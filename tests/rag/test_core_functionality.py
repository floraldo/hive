"""
Core RAG functionality tests - validates the RAG system without Guardian dependencies.
"""

import json
from pathlib import Path

import faiss
import numpy as np
import pytest
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestRAGCoreFunctionality:
    """Test core RAG system functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.rag_index_path = PROJECT_ROOT / "data" / "rag_index"

        if not self.rag_index_path.exists():
            pytest.skip("RAG index not found - run indexing first")

        # Load index components
        self.index = faiss.read_index(str(self.rag_index_path / "faiss.index"))

        with open(self.rag_index_path / "chunks.json", 'r', encoding='utf-8') as f:
            self.chunks = json.load(f)

        with open(self.rag_index_path / "metadata.json", 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)

        self.model = SentenceTransformer(self.metadata['embedding_model'])

    def test_index_loaded(self):
        """Test that index loaded successfully."""
        assert self.index.ntotal > 10000, "Index should have >10K vectors"
        assert self.index.d == 384, "Should be 384-dimensional embeddings"
        assert len(self.chunks) == self.index.ntotal, "Chunks should match index size"

    def test_query_database_patterns(self):
        """Test query for database patterns."""
        query = "How to implement async database operations?"
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        distances, indices = self.index.search(query_embedding.astype('float32'), k=5)

        # Check we got results
        assert len(indices[0]) == 5, "Should return 5 results"

        # Check relevance (distance should be reasonable)
        top_distance = distances[0][0]
        assert top_distance < 2.0, f"Top result should be relevant (distance={top_distance})"

        # Check result content
        top_chunk = self.chunks[indices[0][0]]
        assert 'database' in top_chunk['text'].lower() or 'db' in top_chunk['text'].lower(), \
            "Top result should mention database"

    def test_query_logging_patterns(self):
        """Test query for logging patterns."""
        query = "What are the Golden Rules for logging?"
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        distances, indices = self.index.search(query_embedding.astype('float32'), k=5)

        top_chunk = self.chunks[indices[0][0]]
        assert 'log' in top_chunk['text'].lower(), "Should find logging-related content"

    def test_query_configuration_patterns(self):
        """Test query for configuration patterns."""
        query = "Show me configuration dependency injection pattern"
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        distances, indices = self.index.search(query_embedding.astype('float32'), k=5)

        top_chunk = self.chunks[indices[0][0]]
        # Should find config-related content
        text_lower = top_chunk['text'].lower()
        assert 'config' in text_lower or 'dependency' in text_lower or 'inject' in text_lower

    def test_query_performance(self):
        """Test query performance is within acceptable limits."""
        import time

        query = "How to use the event bus system?"

        # Measure query time
        start = time.time()
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        distances, indices = self.index.search(query_embedding.astype('float32'), k=10)
        elapsed = time.time() - start

        # Should be fast (<200ms for bi-encoder)
        assert elapsed < 0.2, f"Query should complete in <200ms, took {elapsed*1000:.1f}ms"

    def test_multiformat_coverage(self):
        """Test that index covers multiple file formats."""
        types_found = set()
        for chunk in self.chunks[:1000]:  # Sample first 1000
            types_found.add(chunk.get('type', 'unknown'))

        # Should have Python, Markdown, YAML, TOML
        assert 'python' in types_found, "Should index Python files"
        assert 'markdown' in types_found, "Should index Markdown files"
        assert 'yaml' in types_found, "Should index YAML files"
        assert 'toml' in types_found, "Should index TOML files"

    def test_chunk_quality(self):
        """Test that chunks have reasonable quality."""
        # Sample chunks
        sample_chunks = self.chunks[:100]

        for chunk in sample_chunks:
            # Should have required fields
            assert 'text' in chunk, "Chunk should have text"
            assert 'file' in chunk, "Chunk should have file path"
            assert 'type' in chunk, "Chunk should have type"

            # Text should not be empty
            assert len(chunk['text']) > 0, "Chunk text should not be empty"

            # Text should be reasonable length (not too short or long)
            assert 10 < len(chunk['text']) < 10000, "Chunk should be reasonable size"

    def test_graceful_degradation(self):
        """Test system handles edge cases gracefully."""
        # Empty query
        query_embedding = self.model.encode([""], convert_to_numpy=True)
        distances, indices = self.index.search(query_embedding.astype('float32'), k=5)
        assert len(indices[0]) == 5, "Should still return results for empty query"

        # Very long query
        long_query = "database " * 100
        query_embedding = self.model.encode([long_query], convert_to_numpy=True)
        distances, indices = self.index.search(query_embedding.astype('float32'), k=5)
        assert len(indices[0]) == 5, "Should handle long queries"

    def test_storage_efficiency(self):
        """Test that index storage is reasonable."""
        import os

        index_size = os.path.getsize(self.rag_index_path / "faiss.index")
        chunks_size = os.path.getsize(self.rag_index_path / "chunks.json")

        # Should be compact
        total_mb = (index_size + chunks_size) / 1024 / 1024
        assert total_mb < 50, f"Total storage should be <50MB, is {total_mb:.1f}MB"

        # Per-chunk efficiency
        bytes_per_chunk = (index_size + chunks_size) / len(self.chunks)
        assert bytes_per_chunk < 5000, f"Should be <5KB per chunk, is {bytes_per_chunk:.0f} bytes"
