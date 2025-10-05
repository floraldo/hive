"""RAG Engine - Pattern Priming and Retrieval.

Loads QA fix patterns from data/rag_index/ on daemon startup for fast retrieval.
Provides reactive pattern retrieval for Chimera agents and proactive context
injection for CC workers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hive_config import HiveConfig
from hive_logging import get_logger

logger = get_logger(__name__)


class RAGEngine:
    """RAG engine for QA fix pattern priming and retrieval.

    Loads patterns from:
    - data/rag_index/git_commits.json - Historical fix commits
    - data/rag_index/chunks.json - Code pattern chunks
    - data/rag_index/metadata.json - Pattern metadata

    Provides:
    - Reactive retrieval for Chimera agents (query → top_k patterns)
    - Proactive context injection for CC workers (batch patterns → startup script)

    Example:
        engine = RAGEngine(config)
        await engine.initialize()  # Load patterns on startup
        patterns = await engine.retrieve("Ruff E501 fix", top_k=3)
    """

    def __init__(self, config: HiveConfig | None = None) -> None:
        """Initialize RAG engine.

        Args:
            config: Hive configuration for RAG index path
        """
        self.config = config
        self.logger = logger

        # RAG index path
        self.index_path = Path("data/rag_index")
        if config and hasattr(config, "rag"):
            self.index_path = Path(config.rag.index_path)

        # Loaded patterns
        self.git_commits: list[dict[str, Any]] = []
        self.code_chunks: list[dict[str, Any]] = []
        self.metadata: dict[str, Any] = {}

        # Metrics
        self.pattern_count = 0

    async def initialize(self) -> None:
        """Load and prime RAG patterns from index files.

        Loads:
        - git_commits.json: Historical fix commits with diffs
        - chunks.json: Code pattern chunks
        - metadata.json: Index metadata and versioning
        """
        self.logger.info(f"Loading RAG patterns from: {self.index_path}")

        try:
            # Load git commits
            commits_file = self.index_path / "git_commits.json"
            if commits_file.exists():
                with open(commits_file) as f:
                    self.git_commits = json.load(f)
                self.logger.info(f"Loaded {len(self.git_commits)} git commit patterns")
            else:
                self.logger.warning(f"Git commits file not found: {commits_file}")

            # Load code chunks
            chunks_file = self.index_path / "chunks.json"
            if chunks_file.exists():
                with open(chunks_file) as f:
                    self.code_chunks = json.load(f)
                self.logger.info(f"Loaded {len(self.code_chunks)} code chunk patterns")
            else:
                self.logger.warning(f"Code chunks file not found: {chunks_file}")

            # Load metadata
            metadata_file = self.index_path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file) as f:
                    self.metadata = json.load(f)
                self.logger.info(f"Loaded RAG index metadata: version {self.metadata.get('version', 'unknown')}")
            else:
                self.logger.warning(f"Metadata file not found: {metadata_file}")

            # Calculate total pattern count
            self.pattern_count = len(self.git_commits) + len(self.code_chunks)
            self.logger.info(f"RAG engine initialized with {self.pattern_count} total patterns")

        except Exception as e:
            self.logger.error(f"Failed to load RAG patterns: {e}", exc_info=True)
            # Continue with empty patterns (graceful degradation)

    async def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Retrieve similar patterns for a query.

        Simple similarity scoring based on keyword matching.
        Future: Upgrade to vector embeddings for semantic similarity.

        Args:
            query: Natural language query (e.g., "Ruff E501 line length fix")
            top_k: Number of patterns to return

        Returns:
            List of patterns with similarity scores, sorted by relevance
        """
        self.logger.info(f"Retrieving patterns for query: {query} (top_k={top_k})")

        try:
            # Score all patterns
            scored_patterns = []

            # Score git commits
            for commit in self.git_commits:
                score = self._calculate_similarity(query, commit)
                if score > 0.0:
                    scored_patterns.append({
                        "type": "git_commit",
                        "data": commit,
                        "similarity": score,
                    })

            # Score code chunks
            for chunk in self.code_chunks:
                score = self._calculate_similarity(query, chunk)
                if score > 0.0:
                    scored_patterns.append({
                        "type": "code_chunk",
                        "data": chunk,
                        "similarity": score,
                    })

            # Sort by similarity (descending)
            scored_patterns.sort(key=lambda x: x["similarity"], reverse=True)

            # Return top_k
            top_patterns = scored_patterns[:top_k]

            self.logger.info(f"Retrieved {len(top_patterns)} patterns (max similarity: {top_patterns[0]['similarity']:.2f})" if top_patterns else "No patterns found")

            return top_patterns

        except Exception as e:
            self.logger.error(f"Pattern retrieval failed: {e}", exc_info=True)
            return []

    def _calculate_similarity(self, query: str, pattern: dict[str, Any]) -> float:
        """Calculate similarity score between query and pattern.

        Simple keyword-based scoring for MVP.
        Future: Use vector embeddings (sentence-transformers, OpenAI embeddings).

        Args:
            query: Query string
            pattern: Pattern dictionary

        Returns:
            Similarity score (0.0-1.0)
        """
        # Extract searchable text from pattern
        pattern_text = self._extract_pattern_text(pattern)

        if not pattern_text:
            return 0.0

        # Normalize query and pattern text
        query_lower = query.lower()
        pattern_lower = pattern_text.lower()

        # Keyword matching
        query_keywords = set(query_lower.split())
        pattern_keywords = set(pattern_lower.split())

        # Jaccard similarity (intersection / union)
        if not query_keywords or not pattern_keywords:
            return 0.0

        intersection = query_keywords & pattern_keywords
        union = query_keywords | pattern_keywords

        similarity = len(intersection) / len(union)

        return similarity

    def _extract_pattern_text(self, pattern: dict[str, Any]) -> str:
        """Extract searchable text from pattern.

        Args:
            pattern: Pattern dictionary (git commit or code chunk)

        Returns:
            Combined searchable text
        """
        # Git commit pattern
        if "message" in pattern:
            return f"{pattern.get('message', '')} {pattern.get('diff', '')}"

        # Code chunk pattern
        if "content" in pattern:
            return f"{pattern.get('file', '')} {pattern.get('content', '')}"

        # Unknown pattern type
        return str(pattern)

    def get_batch_context(self, patterns: list[dict[str, Any]], max_tokens: int = 2000) -> str:
        """Build batch context for CC worker injection.

        Combines top patterns into a single context string for startup script.

        Args:
            patterns: Retrieved RAG patterns
            max_tokens: Maximum tokens for context (approximate word count)

        Returns:
            Formatted context string for CC worker startup
        """
        if not patterns:
            return "No similar patterns found."

        context_lines = ["# RAG Context: Similar Fix Patterns", ""]

        tokens_used = 0
        for i, pattern in enumerate(patterns):
            pattern_text = self._format_pattern(pattern, index=i + 1)
            pattern_tokens = len(pattern_text.split())

            if tokens_used + pattern_tokens > max_tokens:
                context_lines.append(f"# ... {len(patterns) - i} more patterns (truncated)")
                break

            context_lines.append(pattern_text)
            tokens_used += pattern_tokens

        return "\n".join(context_lines)

    def _format_pattern(self, pattern: dict[str, Any], index: int) -> str:
        """Format pattern for CC worker context.

        Args:
            pattern: RAG pattern
            index: Pattern index (1-based)

        Returns:
            Formatted pattern string
        """
        pattern_type = pattern.get("type", "unknown")
        similarity = pattern.get("similarity", 0.0)
        data = pattern.get("data", {})

        if pattern_type == "git_commit":
            message = data.get("message", "No message")
            commit_sha = data.get("sha", "unknown")[:8]
            return f"## Pattern {index}: Git Commit (sim: {similarity:.2f})\n# Commit: {commit_sha}\n# Message: {message}\n"

        if pattern_type == "code_chunk":
            file_path = data.get("file", "unknown")
            content = data.get("content", "")[:200]  # Truncate
            return f"## Pattern {index}: Code Chunk (sim: {similarity:.2f})\n# File: {file_path}\n# Content: {content}...\n"

        return f"## Pattern {index}: Unknown Type\n"


__all__ = ["RAGEngine"]
