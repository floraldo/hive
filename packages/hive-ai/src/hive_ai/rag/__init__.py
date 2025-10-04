"""RAG (Retrieval-Augmented Generation) infrastructure for Hive platform.

Provides semantic code search, pattern retrieval, and context augmentation
for AI agents with metadata-rich indexing and hybrid retrieval strategies.
"""

from .chunker import HierarchicalChunker
from .context_formatter import (
    ContextFormatter,
    FormatStyle,
    FormattingConfig,
    format_for_code_review,
    format_for_documentation,
    format_for_implementation,
    format_minimal,
)
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
from .query_engine import QueryEngine, QueryEngineConfig, QueryResult
from .retriever import EnhancedRAGRetriever
from .vector_store import VectorStore

# API server (optional import - requires fastapi)
try:
    from .api import AGENT_TOOL_SPEC
    from .api import app as api_app

    _API_AVAILABLE = True
except ImportError:
    api_app = None
    AGENT_TOOL_SPEC = None
    _API_AVAILABLE = False

# Re-ranker (optional import - requires sentence-transformers)
try:
    from .reranker import CrossEncoderReranker, RerankerConfig, create_reranker

    _RERANKER_AVAILABLE = True
except ImportError:
    CrossEncoderReranker = None
    RerankerConfig = None
    create_reranker = None
    _RERANKER_AVAILABLE = False

__all__ = [
    "AGENT_TOOL_SPEC",
    "BM25KeywordSearch",
    # Core models
    "ChunkType",
    "CodeChunk",
    # Context formatting (v0.2.0)
    "ContextFormatter",
    # Cross-encoder re-ranking (v0.4.0)
    "CrossEncoderReranker",
    # Retrieval
    "EmbeddingGenerator",
    "EnhancedRAGRetriever",
    "FormatStyle",
    "FormattingConfig",
    # Processing
    "HierarchicalChunker",
    "MetadataLoader",
    "PatternContext",
    # High-level APIs (v0.2.0)
    "QueryEngine",
    "QueryEngineConfig",
    "QueryResult",
    "RerankerConfig",
    "RetrievalQuery",
    "RetrievalResult",
    "RuleContext",
    "StructuredContext",
    "VectorStore",
    # API server for autonomous agents (v0.3.0)
    "api_app",
    "create_reranker",
    "format_for_code_review",
    "format_for_documentation",
    "format_for_implementation",
    "format_minimal",
]

__version__ = "0.4.0"
