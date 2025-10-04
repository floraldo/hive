"""RAG-Enhanced PR Comment Engine - Read-Only Guardian Integration.

This is the SAFE first integration of RAG with Guardian Agent. Instead of
automatically fixing code, the Guardian posts intelligent comments on PRs
based on RAG-retrieved context.

Design Philosophy:
- Read-only operation (zero code modifications)
- High visibility (comments are visible to all reviewers)
- Low risk (can be ignored or disabled without impact)
- High value (provides contextual guidance to developers)

Integration Pattern:
1. Guardian detects patterns in PR diff
2. QueryEngine retrieves relevant context (patterns, rules, deprecations)
3. ContextFormatter generates instructional guidance
4. Guardian posts comment with retrieved context and suggestions

Example Output:
    "Guardian Suggestion: In packages/hive-db/pool.py, similar database
     connections use async context managers with try/except for error handling.
     Consider adding similar error handling here for resilience.

     Relevant Pattern (from hive-db/pool.py:45):
     ```python
     async with self.pool.get_connection() as conn:
         try:
             result = await conn.execute(query)
         except sqlite3.Error as e:
             logger.error(f'Database error: {e}')
             raise
     ```

     Golden Rule #12: All database operations must have proper error handling."
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hive_ai.rag import QueryEngine
from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class PRComment:
    """Structured PR comment with RAG context."""

    # Comment metadata
    file_path: str
    line_number: int
    comment_type: str  # "suggestion", "golden_rule_violation", "deprecation_warning"

    # Content
    title: str
    message: str
    code_example: str | None = None

    # RAG traceability
    rag_patterns_used: list[str] = field(default_factory=list)
    golden_rules_applied: list[int] = field(default_factory=list)
    deprecation_warnings: list[str] = field(default_factory=list)
    retrieval_time_ms: float = 0.0
    confidence_score: float = 0.0

    def to_github_comment(self) -> str:
        """Format as GitHub PR comment markdown.

        Returns:
            GitHub-flavored markdown comment

        """
        lines = [f"**{self.title}**", ""]

        # Main message
        lines.append(self.message)
        lines.append("")

        # Code example if available
        if self.code_example:
            lines.append("**Example Pattern:**")
            lines.append(f"```python\n{self.code_example}\n```")
            lines.append("")

        # Golden rules if applicable
        if self.golden_rules_applied:
            lines.append("**Applicable Golden Rules:**")
            for rule_num in self.golden_rules_applied:
                lines.append(f"- Golden Rule #{rule_num}")
            lines.append("")

        # Deprecation warnings if any
        if self.deprecation_warnings:
            lines.append("**Deprecation Warnings:**")
            for warning in self.deprecation_warnings:
                lines.append(f"- {warning}")
            lines.append("")

        # Footer with metadata
        lines.append("---")
        lines.append(
            f"*Guardian Agent with RAG • Confidence: {self.confidence_score:.0%} • "
            f"Retrieved: {len(self.rag_patterns_used)} patterns in {self.retrieval_time_ms:.0f}ms*",
        )

        return "\n".join(lines)


@dataclass
class PRCommentBatch:
    """Batch of comments for a PR."""

    pr_number: int
    comments: list[PRComment] = field(default_factory=list)
    total_retrieval_time_ms: float = 0.0
    files_analyzed: int = 0

    def add_comment(self, comment: PRComment) -> None:
        """Add comment to batch."""
        self.comments.append(comment)
        self.total_retrieval_time_ms += comment.retrieval_time_ms

    def to_summary(self) -> str:
        """Generate summary of comment batch."""
        return (
            f"Guardian RAG Review Summary:\n"
            f"- Files Analyzed: {self.files_analyzed}\n"
            f"- Suggestions: {len([c for c in self.comments if c.comment_type == 'suggestion'])}\n"
            f"- Golden Rule Violations: {len([c for c in self.comments if c.comment_type == 'golden_rule_violation'])}\n"
            f"- Deprecation Warnings: {len([c for c in self.comments if c.comment_type == 'deprecation_warning'])}\n"
            f"- Total RAG Retrieval Time: {self.total_retrieval_time_ms:.0f}ms"
        )


class RAGEnhancedCommentEngine:
    """RAG-Enhanced PR comment engine for Guardian Agent.

    This is the SAFE read-only integration that posts intelligent comments
    on PRs without modifying code.

    Features:
    - Pattern-aware suggestions
    - Golden Rule violation detection
    - Deprecation warnings
    - Contextual code examples
    - Full RAG traceability
    """

    def __init__(self, rag_index_path: Path | None = None):
        """Initialize RAG-enhanced comment engine.

        Args:
            rag_index_path: Path to RAG index (defaults to data/rag_index)

        """
        # Initialize RAG query engine
        self.query_engine = QueryEngine()

        # Load index if available
        if rag_index_path is None:
            rag_index_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "rag_index"

        try:
            if rag_index_path.exists():
                self.query_engine.load_index(rag_index_path)
                self.rag_available = True
                logger.info(f"RAG index loaded from {rag_index_path}")
            else:
                self.rag_available = False
                logger.warning(
                    f"RAG index not found at {rag_index_path} - comment engine will use basic patterns only",
                    extra={"operating_mode": "basic", "reason": "index_not_found"},
                )
        except Exception as e:
            self.rag_available = False
            logger.error(
                f"Failed to load RAG index: {e} - comment engine will use basic patterns only",
                extra={"operating_mode": "basic", "error": str(e)},
            )

        logger.info(
            "RAGEnhancedCommentEngine initialized",
            extra={"rag_available": self.rag_available, "mode": "read_only_comments"},
        )

    async def analyze_pr_for_comments(
        self,
        pr_files: list[tuple[str, str]],
        pr_number: int,
    ) -> PRCommentBatch:
        """Analyze PR files and generate intelligent comments.

        This is the main entry point for read-only PR review.

        Args:
            pr_files: List of (file_path, diff) tuples
            pr_number: PR number for tracking

        Returns:
            PRCommentBatch with all generated comments

        """
        start_time = time.time()
        comment_batch = PRCommentBatch(pr_number=pr_number, files_analyzed=len(pr_files))

        for file_path, diff in pr_files:
            logger.info(
                f"Analyzing {file_path} for RAG-enhanced comments",
                extra={"pr_number": pr_number, "file": file_path},
            )

            # Detect patterns in diff
            detected_patterns = self._detect_patterns_in_diff(diff)

            # Generate comments for each detected pattern
            for pattern_type, line_number, context in detected_patterns:
                comment = await self._generate_pattern_comment(
                    file_path=file_path,
                    line_number=line_number,
                    pattern_type=pattern_type,
                    context=context,
                )

                if comment:
                    comment_batch.add_comment(comment)

            # Check for deprecated patterns
            deprecation_comments = await self._check_for_deprecations(file_path, diff)
            for comment in deprecation_comments:
                comment_batch.add_comment(comment)

        execution_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"PR analysis complete for PR #{pr_number}",
            extra={
                "pr_number": pr_number,
                "files_analyzed": len(pr_files),
                "comments_generated": len(comment_batch.comments),
                "execution_time_ms": execution_time_ms,
                "rag_retrieval_time_ms": comment_batch.total_retrieval_time_ms,
            },
        )

        return comment_batch

    async def _generate_pattern_comment(
        self,
        file_path: str,
        line_number: int,
        pattern_type: str,
        context: str,
    ) -> PRComment | None:
        """Generate comment for detected pattern using RAG context.

        Args:
            file_path: File being reviewed
            line_number: Line number for comment
            pattern_type: Type of pattern detected
            context: Code context around pattern

        Returns:
            PRComment if relevant context found, None otherwise

        """
        if not self.rag_available:
            return None

        # Build query based on pattern type
        query = self._build_query_for_pattern(pattern_type, context)

        # Retrieve context
        result = self.query_engine.query(query, k=3, include_golden_rules=True)

        if not result.context or not result.context.code_patterns:
            return None

        # Generate comment from context
        comment_type = self._determine_comment_type(result.context)
        title, message = self._generate_comment_text(pattern_type, result.context)

        # Extract best code example
        code_example = None
        if result.context.code_patterns:
            code_example = result.context.code_patterns[0].code[:300]  # Truncate

        return PRComment(
            file_path=file_path,
            line_number=line_number,
            comment_type=comment_type,
            title=title,
            message=message,
            code_example=code_example,
            rag_patterns_used=[p.source for p in result.context.code_patterns],
            golden_rules_applied=[r.rule_number for r in result.context.golden_rules],
            retrieval_time_ms=result.retrieval_time_ms,
            confidence_score=result.top_result_score if result.top_result_score > 0 else 0.7,
        )

    async def _check_for_deprecations(
        self,
        file_path: str,
        diff: str,
    ) -> list[PRComment]:
        """Check for deprecated patterns in diff.

        Args:
            file_path: File being reviewed
            diff: Diff content

        Returns:
            List of deprecation warning comments

        """
        if not self.rag_available:
            return []

        comments = []

        # Query for deprecated patterns (include archived content)
        result = self.query_engine.query(
            diff[:500],  # First 500 chars
            k=5,
            exclude_archived=False,  # INCLUDE archived for deprecation detection
        )

        # Extract deprecation warnings from context
        if result.context and result.context.deprecation_warnings:
            for warning in result.context.deprecation_warnings:
                comments.append(
                    PRComment(
                        file_path=file_path,
                        line_number=1,  # Top of file
                        comment_type="deprecation_warning",
                        title="Deprecated Pattern Detected",
                        message=f"This code appears to use a deprecated pattern:\n\n{warning}",
                        deprecation_warnings=[warning],
                        retrieval_time_ms=result.retrieval_time_ms,
                        confidence_score=0.8,
                    ),
                )

        return comments

    def _detect_patterns_in_diff(self, diff: str) -> list[tuple[str, int, str]]:
        """Detect code patterns in diff that warrant RAG-enhanced comments.

        Returns:
            List of (pattern_type, line_number, context) tuples

        """
        patterns = []
        lines = diff.split("\n")

        for i, line in enumerate(lines, 1):
            line_lower = line.lower()

            # Database patterns
            if "database" in line_lower or "connection" in line_lower or "sqlite" in line_lower:
                patterns.append(("database_operation", i, line))

            # Async patterns
            elif "async def" in line or "await " in line:
                patterns.append(("async_operation", i, line))

            # Config patterns
            elif "get_config" in line or "config" in line_lower:
                patterns.append(("configuration", i, line))

            # Logging patterns
            elif "print(" in line:
                patterns.append(("logging_violation", i, line))

        return patterns

    def _build_query_for_pattern(self, pattern_type: str, context: str) -> str:
        """Build RAG query for pattern type."""
        queries = {
            "database_operation": "Best practices for async database operations with error handling",
            "async_operation": "Async patterns with retry and circuit breaker",
            "configuration": "Configuration management with dependency injection pattern",
            "logging_violation": "Proper logging patterns using hive_logging",
        }

        return queries.get(pattern_type, f"Best practices for {pattern_type}")

    def _determine_comment_type(self, context: Any) -> str:
        """Determine comment type from RAG context."""
        if context.golden_rules:
            return "golden_rule_violation"
        if context.deprecation_warnings:
            return "deprecation_warning"
        return "suggestion"

    def _generate_comment_text(self, pattern_type: str, context: Any) -> tuple[str, str]:
        """Generate comment title and message from pattern and context."""
        titles = {
            "database_operation": "Database Operation Suggestion",
            "async_operation": "Async Pattern Suggestion",
            "configuration": "Configuration Pattern Suggestion",
            "logging_violation": "Logging Best Practice",
        }

        messages = {
            "database_operation": (
                "Similar database operations in the codebase use async context managers "
                "with proper error handling. Consider adding similar error handling here for resilience."
            ),
            "async_operation": (
                "Similar async operations in the codebase use retry logic and circuit breakers "
                "for fault tolerance. Consider adding similar resilience patterns here."
            ),
            "configuration": (
                "The codebase follows a dependency injection pattern for configuration. "
                "Consider using `create_config_from_sources()` instead of `get_config()` "
                "to avoid global state."
            ),
            "logging_violation": (
                "The codebase uses `hive_logging.get_logger(__name__)` for all logging. "
                "Avoid using `print()` statements. Use structured logging instead."
            ),
        }

        title = titles.get(pattern_type, "Code Pattern Suggestion")
        message = messages.get(pattern_type, "Consider following established patterns in the codebase.")

        return title, message
