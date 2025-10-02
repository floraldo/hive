"""
High-level query engine for RAG system with agent-friendly API.

Provides simplified interface for agents to perform reactive retrieval
with built-in caching, error handling, and structured context generation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hive_logging import get_logger

from .models import RetrievalQuery, StructuredContext
from .retriever import EnhancedRAGRetriever

# Optional re-ranker import
try:
    from .reranker import CrossEncoderReranker, RerankerConfig

    _RERANKER_AVAILABLE = True
except ImportError:
    CrossEncoderReranker = None
    RerankerConfig = None
    _RERANKER_AVAILABLE = False

logger = get_logger(__name__)


@dataclass
class QueryEngineConfig:
    """Configuration for query engine behavior."""

    # Retrieval defaults
    default_k: int = 5
    use_hybrid_search: bool = True
    semantic_weight: float = 0.7
    keyword_weight: float = 0.3

    # Re-ranking (NEW - v0.4.0)
    enable_reranking: bool = False  # Disabled by default (requires cross-encoder model)
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_top_n: int = 20  # Re-rank top N candidates

    # Performance
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600

    # Quality
    include_golden_rules: bool = True
    exclude_archived: bool = True

    # Error handling
    fallback_on_error: bool = True
    max_retries: int = 2


@dataclass
class QueryResult:
    """Result from query engine with metadata and context."""

    # Core result
    context: StructuredContext

    # Performance metrics
    retrieval_time_ms: float
    cache_hit: bool = False

    # Quality metrics
    total_results: int = 0
    top_result_score: float = 0.0

    # Metadata
    query: str = ""
    filters_applied: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class QueryEngine:
    """
    High-level query engine for RAG system.

    Provides simplified API for agents to perform reactive retrieval
    with automatic error handling, caching, and structured context.

    Example:
        ```python
        engine = QueryEngine(),
        result = engine.query(
            "How to implement async database operations?",
            k=5,
            usage_context="database"
        )

        if result.context:
            prompt = result.context.to_prompt_section()
        ```
    """

    def __init__(
        self,
        retriever: EnhancedRAGRetriever | None = None,
        config: QueryEngineConfig | None = None,
    ):
        """
        Initialize query engine.

        Args:
            retriever: RAG retriever instance (creates default if None)
            config: Query engine configuration
        """
        self.retriever = retriever or EnhancedRAGRetriever()
        self.config = config or QueryEngineConfig()

        # Query cache (in-memory for session)
        self.query_cache: dict[str, QueryResult] = {}

        # Initialize re-ranker if enabled
        self.reranker = None
        if self.config.enable_reranking and _RERANKER_AVAILABLE and CrossEncoderReranker:
            try:
                reranker_config = RerankerConfig(
                    enabled=True,
                    model_name=self.config.reranker_model,
                    rerank_count=self.config.rerank_top_n,
                    final_count=self.config.default_k,
                )
                self.reranker = CrossEncoderReranker(config=reranker_config)
                logger.info(f"Re-ranking enabled with {self.config.reranker_model}")
            except Exception as e:
                logger.warning(f"Failed to initialize re-ranker: {e}")
                self.config.enable_reranking = False

        logger.info(
            "QueryEngine initialized",
            extra={
                "hybrid_search": self.config.use_hybrid_search,
                "caching": self.config.enable_caching,
                "reranking": self.config.enable_reranking,
                "include_golden_rules": self.config.include_golden_rules,
            },
        )

    def query(
        self,
        query: str,
        k: int | None = None,
        usage_context: str | None = None,
        include_golden_rules: bool | None = None,
        exclude_archived: bool | None = None,
    ) -> QueryResult:
        """
        Execute query with automatic caching and error handling.

        Args:
            query: Natural language query string
            k: Number of results to return (uses default_k if None)
            usage_context: Filter by usage context ("CI/CD", "database", etc.)
            include_golden_rules: Include relevant golden rules
            exclude_archived: Exclude archived/deprecated code

        Returns:
            QueryResult with structured context and metadata
        """
        # Build cache key
        cache_key = self._build_cache_key(query, k, usage_context)

        # Check cache
        if self.config.enable_caching and cache_key in self.query_cache:
            cached = self.query_cache[cache_key]
            logger.debug(f"Query cache hit: {query[:50]}...")
            return QueryResult(
                context=cached.context,
                retrieval_time_ms=0.0,
                cache_hit=True,
                total_results=cached.total_results,
                top_result_score=cached.top_result_score,
                query=query,
                filters_applied=cached.filters_applied,
            )

        # Execute query with retry
        start_time = time.time(),
        result = self._execute_query_with_retry(
            query=query,
            k=k or self.config.default_k,
            usage_context=usage_context,
            include_golden_rules=(
                include_golden_rules if include_golden_rules is not None else self.config.include_golden_rules
            ),
            exclude_archived=(exclude_archived if exclude_archived is not None else self.config.exclude_archived),
        )

        retrieval_time_ms = (time.time() - start_time) * 1000

        # Cache result
        if self.config.enable_caching and result.context:
            self.query_cache[cache_key] = result

        logger.info(
            "Query executed",
            extra={
                "query_preview": query[:50],
                "retrieval_time_ms": retrieval_time_ms,
                "cache_hit": False,
                "results": result.total_results,
                "top_score": result.top_result_score,
            },
        )

        return result

    def query_multi_stage(
        self,
        queries: list[str],
        k_per_query: int | None = None,
    ) -> list[QueryResult]:
        """
        Execute multiple queries in sequence for reactive retrieval pattern.

        This implements the multi-stage reactive retrieval approach where
        an agent performs several queries as it builds understanding.

        Args:
            queries: List of query strings to execute in order
            k_per_query: Number of results per query

        Returns:
            List of QueryResult objects

        Example:
            ```python
            results = engine.query_multi_stage([
                "Show me the overall file structure",
                "What are the Golden Rules for database access?",
                "Are there any deprecated database patterns?"
            ])
            ```
        """
        results = []

        for i, query in enumerate(queries, 1):
            logger.debug(f"Multi-stage query {i}/{len(queries)}: {query[:50]}...")
            result = self.query(query, k=k_per_query)
            results.append(result)

        return results

    def _execute_query_with_retry(
        self,
        query: str,
        k: int,
        usage_context: str | None,
        include_golden_rules: bool,
        exclude_archived: bool,
    ) -> QueryResult:
        """
        Execute query with retry logic and graceful degradation.

        Implements graceful degradation: Returns empty context on failure
        rather than raising exception.
        """
        retry_count = 0,
        last_error = None

        while retry_count <= self.config.max_retries:
            try:
                # Build retrieval query
                retrieval_query = RetrievalQuery(
                    query=query,
                    k=k,
                    usage_context=usage_context,
                    exclude_archived=exclude_archived,
                    use_hybrid=self.config.use_hybrid_search,
                    semantic_weight=self.config.semantic_weight,
                    keyword_weight=self.config.keyword_weight,
                )

                # Execute retrieval
                context = self.retriever.retrieve_with_context(
                    query=retrieval_query,
                    include_golden_rules=include_golden_rules,
                )

                # Calculate metrics
                total_results = len(context.code_patterns),
                top_score = context.code_patterns[0].relevance_score if context.code_patterns else 0.0

                return QueryResult(
                    context=context,
                    retrieval_time_ms=context.retrieval_time_ms,
                    cache_hit=False,
                    total_results=total_results,
                    top_result_score=top_score,
                    query=query,
                    filters_applied=context.filters_applied,
                )

            except Exception as e:
                last_error = str(e)
                retry_count += 1

                logger.warning(
                    f"Query failed (attempt {retry_count}/{self.config.max_retries + 1}): {e}",
                    extra={"query": query[:50], "error": str(e)},
                )

                if retry_count > self.config.max_retries:
                    break

        # Graceful degradation: Return empty context
        if self.config.fallback_on_error:
            logger.error(
                f"Query failed after {retry_count} attempts - returning empty context",
                extra={"query": query[:50], "last_error": last_error},
            )

            return QueryResult(
                context=StructuredContext(),
                retrieval_time_ms=0.0,
                cache_hit=False,
                error=last_error,
                query=query,
            )
        else:
            # Re-raise if fallback disabled
            raise RuntimeError(f"Query failed: {last_error}")

    def _build_cache_key(
        self,
        query: str,
        k: int | None,
        usage_context: str | None,
    ) -> str:
        """Build cache key from query parameters."""
        parts = [query]

        if k is not None:
            parts.append(f"k={k}")
        if usage_context:
            parts.append(f"ctx={usage_context}")

        return "|".join(parts)

    def clear_cache(self) -> None:
        """Clear query cache."""
        cache_size = len(self.query_cache)
        self.query_cache.clear()
        logger.info(f"Query cache cleared ({cache_size} entries)")

    def get_stats(self) -> dict[str, Any]:
        """Get query engine statistics."""
        return {
            "query_cache_size": len(self.query_cache),
            "config": {
                "default_k": self.config.default_k,
                "use_hybrid_search": self.config.use_hybrid_search,
                "enable_caching": self.config.enable_caching,
            },
            "retriever_stats": self.retriever.get_stats(),
        }

    def load_index(self, path: Path | str) -> None:
        """
        Load RAG index from disk.

        Args:
            path: Directory containing saved index
        """
        self.retriever.load(path)
        logger.info(f"Loaded RAG index from {path}")

    def save_index(self, path: Path | str) -> None:
        """
        Save RAG index to disk.

        Args:
            path: Directory to save index
        """
        self.retriever.save(path)
        logger.info(f"Saved RAG index to {path}")
