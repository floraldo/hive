"""BM25-based keyword search for exact matching and text retrieval.

Provides traditional text search to complement semantic search in hybrid retrieval.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from hive_logging import get_logger

from .models import CodeChunk, RetrievalResult

logger = get_logger(__name__)


class BM25KeywordSearch:
    """BM25 keyword search for code chunks.

    Features:
    - BM25 ranking algorithm
    - Tokenization optimized for code (preserves underscores, camelCase)
    - Metadata filtering
    - Efficient for exact term matching
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """Initialize BM25 keyword search.

        Args:
            k1: Term frequency saturation parameter (default: 1.5)
            b: Length normalization parameter (default: 0.75)

        """
        self.k1 = k1
        self.b = b

        # Document storage
        self.chunks: list[CodeChunk] = []
        self.tokenized_docs: list[list[str]] = []

        # BM25 precomputed values
        self.doc_freqs: Counter = Counter()
        self.idf: dict[str, float] = {}
        self.avgdl: float = 0.0

        logger.info("Initialized BM25 keyword search")

    def add_chunks(self, chunks: list[CodeChunk]) -> None:
        """Add chunks to the keyword search index.

        Args:
            chunks: List of CodeChunks to index

        """
        if not chunks:
            return

        # Tokenize all chunks
        for chunk in chunks:
            # Use enriched code for better search coverage
            text = chunk.get_enriched_code()
            tokens = self._tokenize(text)

            self.chunks.append(chunk)
            self.tokenized_docs.append(tokens)

        # Recompute BM25 statistics
        self._compute_bm25_stats()

        logger.info(f"Added {len(chunks)} chunks to keyword search index")

    def search(
        self,
        query: str,
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """Search for chunks matching the query.

        Args:
            query: Search query
            k: Number of results to return
            filters: Optional filters

        Returns:
            List of RetrievalResult objects sorted by BM25 score

        """
        if not self.chunks:
            logger.warning("Keyword search index is empty")
            return []

        # Tokenize query
        query_tokens = self._tokenize(query)

        if not query_tokens:
            logger.warning("Query tokenization resulted in no tokens")
            return []

        # Compute BM25 scores for all documents
        scores = []
        for i, (chunk, doc_tokens) in enumerate(zip(self.chunks, self.tokenized_docs, strict=False)):
            # Apply filters
            if filters:
                if filters.get("exclude_archived") and chunk.is_archived:
                    scores.append((i, 0.0))
                    continue

                if filters.get("usage_context") and chunk.usage_context != filters["usage_context"]:
                    scores.append((i, 0.0))
                    continue

                if filters.get("chunk_types") and chunk.chunk_type not in filters["chunk_types"]:
                    scores.append((i, 0.0))
                    continue

            # Compute BM25 score
            score = self._compute_bm25_score(query_tokens, doc_tokens)
            scores.append((i, score))

        # Sort by score (descending)
        scores.sort(key=lambda x: x[1], reverse=True)

        # Build results (top-k)
        results = []
        for rank, (idx, score) in enumerate(scores[:k], 1):
            if score <= 0:  # Skip zero scores
                continue

            results.append(
                RetrievalResult(
                    chunk=self.chunks[idx],
                    score=score,
                    retrieval_method="keyword",
                    rank=rank,
                ),
            )

        logger.debug(f"Keyword search returned {len(results)} results")
        return results

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text for code search.

        Preserves:
        - Underscores (snake_case)
        - CamelCase (split into words)
        - Function/method names
        """
        # Convert to lowercase
        text = text.lower()

        # Split CamelCase: insertHTMLElement -> insert html element
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)

        # Extract alphanumeric tokens and underscores
        tokens = re.findall(r"\b\w+\b", text)

        # Also split on underscores but keep original
        expanded_tokens = []
        for token in tokens:
            expanded_tokens.append(token)
            if "_" in token:
                expanded_tokens.extend(token.split("_"))

        # Remove very short tokens (< 2 chars) and common stop words
        stop_words = {"def", "class", "if", "else", "for", "in", "is", "and", "or", "not", "self"}
        filtered_tokens = [t for t in expanded_tokens if len(t) >= 2 and t not in stop_words]

        return filtered_tokens

    def _compute_bm25_stats(self) -> None:
        """Precompute BM25 statistics (IDF, average document length)."""
        if not self.tokenized_docs:
            return

        N = len(self.tokenized_docs)

        # Compute document frequencies
        self.doc_freqs = Counter()
        for doc_tokens in self.tokenized_docs:
            unique_tokens = set(doc_tokens)
            for token in unique_tokens:
                self.doc_freqs[token] += 1

        # Compute IDF for each term
        self.idf = {}
        for term, df in self.doc_freqs.items():
            # IDF formula: log((N - df + 0.5) / (df + 0.5) + 1)
            self.idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

        # Compute average document length
        self.avgdl = sum(len(doc) for doc in self.tokenized_docs) / N

        logger.debug(f"BM25 stats computed: {len(self.idf)} unique terms, avgdl={self.avgdl:.1f}")

    def _compute_bm25_score(self, query_tokens: list[str], doc_tokens: list[str]) -> float:
        """Compute BM25 score for a query-document pair.

        Args:
            query_tokens: Tokenized query
            doc_tokens: Tokenized document

        Returns:
            BM25 score

        """
        score = 0.0
        doc_len = len(doc_tokens)
        doc_term_freqs = Counter(doc_tokens)

        for term in query_tokens:
            if term not in self.idf:
                continue

            # Term frequency in document
            tf = doc_term_freqs.get(term, 0)

            if tf == 0:
                continue

            # IDF
            idf = self.idf[term]

            # BM25 score component
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avgdl))

            score += idf * (numerator / denominator)

        return score

    def get_stats(self) -> dict[str, Any]:
        """Get keyword search statistics."""
        return {
            "total_chunks": len(self.chunks),
            "unique_terms": len(self.idf),
            "avg_doc_length": self.avgdl,
        }

    def clear(self) -> None:
        """Clear all data from keyword search index."""
        self.chunks = []
        self.tokenized_docs = []
        self.doc_freqs = Counter()
        self.idf = {}
        self.avgdl = 0.0
        logger.info("Keyword search index cleared")
