"""
RAG (Retrieval-Augmented Generation) infrastructure for Hive platform.

Provides semantic code search, pattern retrieval, and context augmentation
for AI agents with metadata-rich indexing and hybrid retrieval strategies.
"""

from .chunker import HierarchicalChunker
from .embeddings import EmbeddingGenerator
from .keyword_search import BM25KeywordSearch
from .metadata_loader import MetadataLoader
from .models import (
    ChunkType,
    CodeChunk,
    PatternContext,
    RetrievalQuery,
    RetrievalResult,
    RuleContext,
    StructuredContext,
)
from .context_formatter import (
    ContextFormatter,
    FormatStyle,
    FormattingConfig,
    format_for_code_review,
    format_for_documentation,
    format_for_implementation,
    format_minimal,
)
from .query_engine import QueryEngine, QueryEngineConfig, QueryResult
from .retriever import EnhancedRAGRetriever
from .vector_store import VectorStore

__all__ = [
    # Core models
    "ChunkType",
    "CodeChunk",
    "PatternContext",
    "RetrievalQuery",
    "RetrievalResult",
    "RuleContext",
    "StructuredContext",
    # Processing
    "HierarchicalChunker",
    "MetadataLoader",
    # Retrieval
    "EmbeddingGenerator",
    "VectorStore",
    "BM25KeywordSearch",
    "EnhancedRAGRetriever",
    # High-level APIs (NEW in v0.2.0)
    "QueryEngine",
    "QueryEngineConfig",
    "QueryResult",
    # Context formatting (NEW in v0.2.0)
    "ContextFormatter",
    "FormatStyle",
    "FormattingConfig",
    "format_for_code_review",
    "format_for_implementation",
    "format_for_documentation",
    "format_minimal",
]

__version__ = "0.2.0"
