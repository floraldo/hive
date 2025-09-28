"""
Vector Database Integration for Hive AI.

Provides comprehensive vector storage, embedding generation,
and semantic search capabilities with multi-provider support.
"""

from .store import VectorStore, BaseVectorProvider, ChromaProvider
from .embedding import EmbeddingManager, EmbeddingResult
from .search import SemanticSearch, Document, SearchResult
from .metrics import VectorMetrics, VectorOperationRecord, VectorPerformanceStats

__all__ = [
    # Core vector database
    "VectorStore",
    "BaseVectorProvider",
    "ChromaProvider",

    # Embedding management
    "EmbeddingManager",
    "EmbeddingResult",

    # Semantic search
    "SemanticSearch",
    "Document",
    "SearchResult",

    # Metrics and monitoring
    "VectorMetrics",
    "VectorOperationRecord",
    "VectorPerformanceStats",
]