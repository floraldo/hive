from hive_logging import get_logger

logger = get_logger(__name__)

"""
Vector Database Integration for Hive AI.

Provides comprehensive vector storage, embedding generation,
and semantic search capabilities with multi-provider support.
"""

from .embedding import EmbeddingManager, EmbeddingResult
from .metrics import VectorMetrics, VectorOperationRecord, VectorPerformanceStats
from .search import Document, SearchResult, SemanticSearch
from .store import BaseVectorProvider, ChromaProvider, VectorStore

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
