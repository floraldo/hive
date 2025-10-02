"""
Enhanced RAG retriever with hybrid search and structured context generation.

Combines semantic search, keyword search, and metadata filtering to provide
high-quality code context for LLM agents.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from hive_logging import get_logger

from .embeddings import EmbeddingGenerator
from .keyword_search import BM25KeywordSearch
from .models import (
    CodeChunk,
    PatternContext,
    RetrievalQuery,
    RetrievalResult,
    RuleContext,
    StructuredContext,
)
from .vector_store import VectorStore

logger = get_logger(__name__)


class EnhancedRAGRetriever:
    """
    Hybrid RAG retriever combining semantic and keyword search.

    Features:
    - Semantic search via vector similarity
    - Keyword search via BM25
    - Hybrid merging with configurable weights
    - Metadata-based filtering
    - Structured context generation for LLM prompts
    - Golden Rules integration
    """

    def __init__(
        self,
        embedding_generator: EmbeddingGenerator | None = None,
        vector_store: VectorStore | None = None,
        keyword_search: BM25KeywordSearch | None = None,
    ):
        """
        Initialize enhanced RAG retriever.

        Args:
            embedding_generator: Embedding generator (creates default if None)
            vector_store: Vector store (creates default if None)
            keyword_search: Keyword search (creates default if None)
        """
        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        self.vector_store = vector_store or VectorStore(embedding_dim=self.embedding_generator.embedding_dim)
        self.keyword_search = keyword_search or BM25KeywordSearch()

        # Golden rules cache (loaded lazily)
        self.golden_rules: list[RuleContext] | None = None

        logger.info("Initialized Enhanced RAG Retriever")

    def index_chunks(self, chunks: list[CodeChunk]) -> None:
        """
        Index chunks for retrieval.

        Args:
            chunks: List of CodeChunks to index
        """
        if not chunks:
            logger.warning("No chunks to index")
            return

        logger.info(f"Indexing {len(chunks)} chunks...")

        # Generate embeddings
        chunks_with_embeddings = self.embedding_generator.embed_chunks_batch(chunks)

        # Add to vector store
        self.vector_store.add_chunks(chunks_with_embeddings)

        # Add to keyword search
        self.keyword_search.add_chunks(chunks)

        logger.info(f"Successfully indexed {len(chunks)} chunks")

    def retrieve(self, query: str | RetrievalQuery) -> list[RetrievalResult]:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: Query string or RetrievalQuery object

        Returns:
            List of RetrievalResult objects sorted by relevance
        """
        # Convert string query to RetrievalQuery
        if isinstance(query, str):
            query = RetrievalQuery(query=query)

        start_time = time.time()

        if query.use_hybrid:
            results = self._hybrid_search(query)
        else:
            # Semantic search only
            query_embedding = self.embedding_generator.generate_embedding(query.query)
            results = self.vector_store.search(
                query_embedding,
                k=query.k,
                filters=self._build_filters(query),
            )

        retrieval_time = (time.time() - start_time) * 1000
        logger.info(f"Retrieved {len(results)} results in {retrieval_time:.1f}ms")

        return results

    def retrieve_with_context(
        self,
        query: str | RetrievalQuery,
        include_golden_rules: bool = True,
    ) -> StructuredContext:
        """
        Retrieve chunks and generate structured context for LLM prompts.

        Args:
            query: Query string or RetrievalQuery object
            include_golden_rules: Whether to include relevant golden rules

        Returns:
            StructuredContext ready for prompt generation
        """
        # Convert string query to RetrievalQuery
        if isinstance(query, str):
            query = RetrievalQuery(query=query)

        start_time = time.time()

        # Retrieve chunks
        results = self.retrieve(query)

        # Convert to pattern contexts
        code_patterns = [result.to_pattern_context() for result in results]

        # Get relevant golden rules
        golden_rules = []
        if include_golden_rules:
            golden_rules = self._get_relevant_golden_rules(query.query)

        # Extract deprecation warnings
        deprecation_warnings = [p.deprecation_warning for p in code_patterns if p.deprecation_warning]

        retrieval_time = (time.time() - start_time) * 1000

        context = StructuredContext(
            code_patterns=code_patterns,
            golden_rules=golden_rules,
            deprecation_warnings=deprecation_warnings,
            retrieval_time_ms=retrieval_time,
            total_chunks_searched=self.vector_store.get_stats()["total_chunks"],
            filters_applied=self._build_filters(query),
        )

        logger.info(
            f"Generated structured context: {len(code_patterns)} patterns, "
            f"{len(golden_rules)} rules, {retrieval_time:.1f}ms"
        )

        return context

    def _hybrid_search(self, query: RetrievalQuery) -> list[RetrievalResult]:
        """
        Perform hybrid search combining semantic and keyword search.

        Args:
            query: Retrieval query

        Returns:
            Merged and re-ranked results
        """
        # Generate query embedding
        query_embedding = self.embedding_generator.generate_embedding(query.query)

        # Semantic search
        semantic_results = self.vector_store.search(
            query_embedding,
            k=query.rerank_top_k if query.use_reranking else query.k,
            filters=self._build_filters(query),
        )

        # Keyword search
        keyword_results = self.keyword_search.search(
            query.query,
            k=query.rerank_top_k if query.use_reranking else query.k,
            filters=self._build_filters(query),
        )

        # Merge results
        merged = self._merge_results(
            semantic_results,
            keyword_results,
            semantic_weight=query.semantic_weight,
            keyword_weight=query.keyword_weight,
        )

        # Re-rank if enabled (placeholder for future cross-encoder)
        if query.use_reranking:
            merged = self._rerank_results(merged, query)

        # Return top-k
        return merged[: query.k]

    def _merge_results(
        self,
        semantic_results: list[RetrievalResult],
        keyword_results: list[RetrievalResult],
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> list[RetrievalResult]:
        """
        Merge semantic and keyword search results.

        Uses weighted score combination with de-duplication.

        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            semantic_weight: Weight for semantic scores
            keyword_weight: Weight for keyword scores

        Returns:
            Merged results sorted by combined score
        """
        # Build combined scores
        combined_scores: dict[str, tuple[CodeChunk, float, str]] = {}

        # Add semantic results
        for result in semantic_results:
            chunk_id = id(result.chunk)
            combined_scores[chunk_id] = (
                result.chunk,
                result.score * semantic_weight,
                "semantic",
            )

        # Add/merge keyword results
        for result in keyword_results:
            chunk_id = id(result.chunk)

            if chunk_id in combined_scores:
                # Combine scores
                chunk, existing_score, _ = combined_scores[chunk_id]
                new_score = existing_score + (result.score * keyword_weight)
                combined_scores[chunk_id] = (chunk, new_score, "hybrid")
            else:
                combined_scores[chunk_id] = (
                    result.chunk,
                    result.score * keyword_weight,
                    "keyword",
                )

        # Sort by combined score
        sorted_results = sorted(combined_scores.values(), key=lambda x: x[1], reverse=True)

        # Convert to RetrievalResult
        merged = []
        for rank, (chunk, score, method) in enumerate(sorted_results, 1):
            merged.append(
                RetrievalResult(
                    chunk=chunk,
                    score=score,
                    retrieval_method=method,
                    rank=rank,
                )
            )

        return merged

    def _rerank_results(self, results: list[RetrievalResult], query: RetrievalQuery) -> list[RetrievalResult]:
        """
        Re-rank results using cross-encoder (placeholder for future implementation).

        Args:
            results: Initial retrieval results
            query: Original query

        Returns:
            Re-ranked results
        """
        # Placeholder: In production, use cross-encoder model for re-ranking
        # For now, just return top results unchanged
        logger.debug("Re-ranking placeholder: returning initial results")
        return results

    def _build_filters(self, query: RetrievalQuery) -> dict[str, Any]:
        """Build filter dictionary from query."""
        filters = {}

        if query.exclude_archived:
            filters["exclude_archived"] = True

        if query.usage_context:
            filters["usage_context"] = query.usage_context

        if query.chunk_types:
            filters["chunk_types"] = query.chunk_types

        return filters

    def _get_relevant_golden_rules(self, query: str) -> list[RuleContext]:
        """
        Get relevant golden rules for the query.

        This is a simplified version - in production, would use semantic matching
        against rule descriptions.

        Args:
            query: Query string

        Returns:
            List of relevant RuleContext objects
        """
        # Placeholder: Load golden rules from hive-tests
        if self.golden_rules is None:
            self._load_golden_rules()

        # Simple keyword matching for now
        relevant_rules = []
        query_lower = query.lower()

        for rule in self.golden_rules or []:
            rule_text_lower = rule.rule_text.lower()

            # Match on keywords
            if any(
                keyword in query_lower or keyword in rule_text_lower
                for keyword in ["import", "logging", "print", "async", "config", "test"]
            ):
                relevant_rules.append(rule)

        return relevant_rules[:3]  # Return top 3

    def _load_golden_rules(self) -> None:
        """Load golden rules from hive-tests package."""
        # Simplified golden rules for demonstration
        self.golden_rules = [
            RuleContext(
                rule_number=3,
                rule_text="No sys.path manipulation - Use proper package imports",
                relevance_reason="Ensures clean import structure",
                severity="ERROR",
            ),
            RuleContext(
                rule_number=10,
                rule_text="No print() statements - Use hive_logging.get_logger()",
                relevance_reason="Maintains structured logging standards",
                severity="ERROR",
            ),
            RuleContext(
                rule_number=11,
                rule_text="Use hive packages for infrastructure - Don't reinvent",
                relevance_reason="Promotes code reuse and consistency",
                severity="WARNING",
            ),
        ]

        logger.info(f"Loaded {len(self.golden_rules)} golden rules")

    def save(self, path: Path | str) -> None:
        """
        Save retriever state to disk.

        Args:
            path: Directory to save state
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save vector store
        self.vector_store.save(path / "vector_store")

        logger.info(f"Saved retriever state to {path}")

    def load(self, path: Path | str) -> None:
        """
        Load retriever state from disk.

        Args:
            path: Directory containing saved state
        """
        path = Path(path)

        # Load vector store
        vector_store_path = path / "vector_store"
        if vector_store_path.exists():
            self.vector_store.load(vector_store_path)
        else:
            logger.warning(f"Vector store not found at {vector_store_path}")

        logger.info(f"Loaded retriever state from {path}")

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive retriever statistics."""
        return {
            "vector_store": self.vector_store.get_stats(),
            "keyword_search": self.keyword_search.get_stats(),
            "embedding_generator": self.embedding_generator.get_stats(),
            "golden_rules_loaded": len(self.golden_rules) if self.golden_rules else 0,
        }
