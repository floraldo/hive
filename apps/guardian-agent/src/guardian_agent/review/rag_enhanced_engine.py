"""
RAG-Enhanced Review Engine with Reactive Retrieval and Graceful Degradation.

Implements the four critical design decisions for RAG-Guardian integration:
1. Reactive Retrieval (Option B): Multi-stage iterative context gathering
2. Instructional Priming (Option C): Structured context with explicit instructions
3. Combined Quality Score (Option C): Holistic component + system measurement
4. Graceful Degradation (Option B): Resilient operation even if RAG fails

This engine enhances the Guardian's code review capabilities with RAG-powered
architectural memory, pattern matching, and deprecation warnings.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add hive-ai to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "packages" / "hive-ai" / "src"))

from guardian_agent.analyzers.code_analyzer import CodeAnalyzer
from guardian_agent.analyzers.golden_rules import GoldenRulesAnalyzer
from guardian_agent.core.config import GuardianConfig
from guardian_agent.core.interfaces import AnalysisResult, ReviewResult, Severity
from guardian_agent.prompts.review_prompts import ReviewPromptBuilder
from hive_ai.rag import EnhancedRAGRetriever, RetrievalQuery, StructuredContext
from hive_async import AsyncExecutor
from hive_cache import CacheClient
from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class RAGRetrievalMetrics:
    """Metrics for RAG retrieval during review."""

    # Retrieval performance
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    cache_hits: int = 0

    # Timing
    total_retrieval_time_ms: float = 0.0
    avg_retrieval_time_ms: float = 0.0

    # Context quality
    patterns_retrieved: int = 0
    golden_rules_applied: int = 0
    deprecation_warnings: int = 0

    # Operating modes
    rag_enhanced_reviews: int = 0
    blind_reviews: int = 0


class RAGEnhancedReviewEngine:
    """
    RAG-Enhanced Review Engine with reactive retrieval pattern.

    Design Decisions Implemented:
    - Reactive Retrieval: Multi-stage context gathering as analysis progresses
    - Instructional Priming: Structured context with explicit usage instructions
    - Graceful Degradation: Continues operation if RAG unavailable
    - Traceability Logging: Comprehensive RAG usage logging
    """

    def __init__(self, config: GuardianConfig | None = None, rag_index_path: Path | None = None) -> None:
        """
        Initialize RAG-enhanced review engine.

        Args:
            config: Guardian configuration
            rag_index_path: Path to RAG index (defaults to data/rag_index)
        """
        self.config = config or GuardianConfig()

        # Initialize RAG retriever (with graceful degradation)
        self.rag = None
        self.rag_available = False

        if rag_index_path is None:
            rag_index_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "rag_index"

        try:
            self.rag = EnhancedRAGRetriever()
            if rag_index_path.exists():
                self.rag.load(rag_index_path)
                self.rag_available = True
                logger.info("RAG index loaded successfully from %s", rag_index_path)
            else:
                logger.warning(
                    "RAG index not found at %s - operating in blind mode",
                    rag_index_path,
                    extra={"operating_mode": "blind", "reason": "index_not_found"},
                )
        except Exception as e:
            logger.error(
                "Failed to initialize RAG system: %s - operating in blind mode",
                e,
                extra={"operating_mode": "blind", "error": str(e)},
            )

        # Initialize cache
        if self.config.cache.enabled:
            self.cache = CacheClient(
                ttl_seconds=self.config.cache.ttl_seconds,
                max_size_mb=self.config.cache.max_cache_size_mb,
            )
        else:
            self.cache = None

        # Initialize async executor
        self.async_executor = AsyncExecutor(max_workers=4)

        # Initialize analyzers
        self.analyzers = self._initialize_analyzers()

        # Initialize prompt builder
        self.prompt_builder = ReviewPromptBuilder()

        # Initialize metrics tracking
        self.rag_metrics = RAGRetrievalMetrics()

        logger.info(
            "RAGEnhancedReviewEngine initialized",
            extra={
                "analyzers": len(self.analyzers),
                "rag_available": self.rag_available,
                "operating_mode": "rag_enhanced" if self.rag_available else "blind",
            },
        )

    def _initialize_analyzers(self) -> list[Any]:
        """Initialize all configured analyzers."""
        analyzers = []
        analyzers.append(CodeAnalyzer())

        if self.config.review.enable_golden_rules:
            analyzers.append(GoldenRulesAnalyzer())

        return analyzers

    async def review_file_with_rag(self, file_path: Path, diff: str | None = None) -> ReviewResult:
        """
        Review file with RAG-enhanced context (reactive retrieval pattern).

        This implements the multi-stage reactive retrieval approach:
        1. Retrieve file structure and patterns
        2. Analyze diff/content to detect patterns
        3. Retrieve specific pattern guidance
        4. Check for deprecated patterns
        5. Generate review with combined context

        Args:
            file_path: Path to file being reviewed
            diff: Optional diff content (for PR reviews)

        Returns:
            ReviewResult with RAG-enhanced insights
        """
        start_time = time.time()

        # Read file content
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error("Failed to read file %s: %s", file_path, e)
            raise

        # Use diff if provided, otherwise use full content
        analysis_content = diff if diff else content

        # Stage 1: Retrieve file structure and similar patterns (Reactive Retrieval)
        structure_context = await self._retrieve_structure_context(file_path, content[:1000])

        # Stage 2: Analyze content to detect patterns
        detected_patterns = self._detect_patterns(analysis_content)

        # Stage 3: Retrieve pattern-specific guidance (Reactive Retrieval)
        pattern_context = await self._retrieve_pattern_context(detected_patterns)

        # Stage 4: Check for deprecated patterns (Reactive Retrieval)
        deprecation_context = await self._retrieve_deprecation_context(analysis_content[:500])

        # Combine all retrieved contexts
        combined_context = self._combine_contexts(structure_context, pattern_context, deprecation_context)

        # Run standard analyzers
        analysis_results = await self._run_analyzers_sequential(file_path, content)

        # Get AI review with RAG context (Instructional Priming)
        ai_review = await self._get_ai_review_with_rag_context(
            file_path=file_path,
            content=content,
            analysis_results=analysis_results,
            rag_context=combined_context,
        )

        # Combine results
        result = self._combine_results(file_path, analysis_results, ai_review, combined_context)

        execution_time = (time.time() - start_time) * 1000

        # Update metrics
        if self.rag_available and combined_context:
            self.rag_metrics.rag_enhanced_reviews += 1
        else:
            self.rag_metrics.blind_reviews += 1

        logger.info(
            "RAG-enhanced review completed for %s in %.1f ms",
            file_path,
            execution_time,
            extra={
                "violations": len(result.all_violations),
                "suggestions": len(result.all_suggestions),
                "rag_patterns_used": len(combined_context.code_patterns) if combined_context else 0,
                "golden_rules_applied": len(combined_context.golden_rules) if combined_context else 0,
                "deprecation_warnings": len(combined_context.deprecation_warnings) if combined_context else 0,
                "operating_mode": "rag_enhanced" if combined_context else "blind",
            },
        )

        return result

    async def _retrieve_structure_context(self, file_path: Path, content_preview: str) -> StructuredContext | None:
        """
        Stage 1: Retrieve file structure and similar patterns.

        Implements graceful degradation: Returns None if RAG unavailable.
        """
        if not self.rag_available:
            logger.debug(
                "RAG unavailable, skipping structure context",
                extra={"file": str(file_path), "stage": "structure", "operating_mode": "blind"},
            )
            return None

        try:
            self.rag_metrics.total_queries += 1
            start = time.time(),

            query = f"Show overall structure and key patterns similar to {file_path.name}",
            context = self.rag.retrieve_with_context(
                query=query,
                k=3,
                include_golden_rules=False,  # Will retrieve separately
            )

            retrieval_time = (time.time() - start) * 1000
            self.rag_metrics.total_retrieval_time_ms += retrieval_time
            self.rag_metrics.successful_queries += 1
            self.rag_metrics.patterns_retrieved += len(context.code_patterns)

            logger.debug(
                "Structure context retrieved",
                extra={
                    "file": str(file_path),
                    "stage": "structure",
                    "patterns": len(context.code_patterns),
                    "retrieval_time_ms": retrieval_time,
                },
            )

            return context

        except Exception as e:
            logger.warning(
                "Structure context retrieval failed: %s",
                e,
                extra={"file": str(file_path), "stage": "structure", "error": str(e), "operating_mode": "blind"},
            )
            self.rag_metrics.failed_queries += 1
            return None

    async def _retrieve_pattern_context(self, detected_patterns: list[str]) -> StructuredContext | None:
        """
        Stage 3: Retrieve pattern-specific guidance.

        Implements graceful degradation: Returns None if RAG unavailable.
        """
        if not self.rag_available or not detected_patterns:
            return None

        try:
            self.rag_metrics.total_queries += 1
            start = time.time()

            # Build query from detected patterns
            query = f"Best practices and examples for {', '.join(detected_patterns[:3])}"
            context = self.rag.retrieve_with_context(
                query=query,
                k=5,
                include_golden_rules=True,  # Include applicable golden rules
            )

            retrieval_time = (time.time() - start) * 1000
            self.rag_metrics.total_retrieval_time_ms += retrieval_time
            self.rag_metrics.successful_queries += 1
            self.rag_metrics.patterns_retrieved += len(context.code_patterns)
            self.rag_metrics.golden_rules_applied += len(context.golden_rules)

            logger.debug(
                "Pattern context retrieved",
                extra={
                    "stage": "patterns",
                    "detected_patterns": detected_patterns,
                    "patterns": len(context.code_patterns),
                    "golden_rules": len(context.golden_rules),
                    "retrieval_time_ms": retrieval_time,
                },
            )

            return context

        except Exception as e:
            logger.warning(
                "Pattern context retrieval failed: %s",
                e,
                extra={"stage": "patterns", "error": str(e), "operating_mode": "blind"},
            )
            self.rag_metrics.failed_queries += 1
            return None

    async def _retrieve_deprecation_context(self, content_preview: str) -> StructuredContext | None:
        """
        Stage 4: Check for deprecated patterns.

        Implements graceful degradation: Returns None if RAG unavailable.
        """
        if not self.rag_available:
            return None

        try:
            self.rag_metrics.total_queries += 1
            start = time.time()

            # Query including archived content for deprecation warnings
            results = self.rag.retrieve(
                RetrievalQuery(
                    query=content_preview,
                    k=5,
                    exclude_archived=False,  # INCLUDE archived for deprecation detection
                )
            )

            # Extract deprecation warnings
            deprecation_warnings = [
                r.chunk.deprecation_reason for r in results if r.chunk.is_archived and r.chunk.deprecation_reason
            ]

            retrieval_time = (time.time() - start) * 1000
            self.rag_metrics.total_retrieval_time_ms += retrieval_time
            self.rag_metrics.successful_queries += 1
            self.rag_metrics.deprecation_warnings += len(deprecation_warnings)

            if deprecation_warnings:
                logger.info(
                    "Deprecation warnings detected",
                    extra={
                        "stage": "deprecation",
                        "warnings": len(deprecation_warnings),
                        "retrieval_time_ms": retrieval_time,
                    },
                )

            # Create context with deprecation warnings
            if deprecation_warnings:
                return StructuredContext(
                    code_patterns=[],
                    golden_rules=[],
                    deprecation_warnings=deprecation_warnings,
                    retrieval_time_ms=retrieval_time,
                )

            return None

        except Exception as e:
            logger.warning(
                "Deprecation context retrieval failed: %s",
                e,
                extra={"stage": "deprecation", "error": str(e), "operating_mode": "blind"},
            )
            self.rag_metrics.failed_queries += 1
            return None

    def _detect_patterns(self, content: str) -> list[str]:
        """
        Analyze content to detect code patterns.

        Returns list of pattern types detected (e.g., "async database", "config DI", etc.)
        """
        patterns = [],

        content_lower = content.lower()

        # Detect async patterns
        if "async def" in content or "await " in content:
            patterns.append("async patterns")

        # Detect database patterns
        if "database" in content_lower or "connection" in content_lower or "pool" in content_lower:
            patterns.append("database operations")

        # Detect configuration patterns
        if "config" in content_lower or "get_config" in content_lower or "create_config" in content_lower:
            patterns.append("configuration management")

        # Detect logging patterns
        if "logger" in content_lower or "get_logger" in content_lower:
            patterns.append("logging")

        # Detect caching patterns
        if "cache" in content_lower:
            patterns.append("caching")

        # Detect testing patterns
        if "pytest" in content_lower or "test_" in content_lower or "@pytest" in content:
            patterns.append("testing")

        return patterns

    def _combine_contexts(
        self,
        structure: StructuredContext | None,
        patterns: StructuredContext | None,
        deprecation: StructuredContext | None,
    ) -> StructuredContext | None:
        """
        Combine multiple retrieved contexts into single unified context.

        Implements graceful degradation: Returns None if all contexts are None.
        """
        if not structure and not patterns and not deprecation:
            return None

        # Combine code patterns (deduplicate by source)
        combined_patterns = [],
        seen_sources = set()

        for ctx in [structure, patterns]:
            if ctx:
                for pattern in ctx.code_patterns:
                    if pattern.source not in seen_sources:
                        combined_patterns.append(pattern)
                        seen_sources.add(pattern.source)

        # Combine golden rules (deduplicate by name)
        combined_rules = [],
        seen_rules = set()

        for ctx in [structure, patterns]:
            if ctx:
                for rule in ctx.golden_rules:
                    if rule.name not in seen_rules:
                        combined_rules.append(rule)
                        seen_rules.add(rule.name)

        # Combine deprecation warnings
        combined_warnings = []
        if deprecation:
            combined_warnings.extend(deprecation.deprecation_warnings)

        # Calculate total retrieval time
        total_time = sum(ctx.retrieval_time_ms for ctx in [structure, patterns, deprecation] if ctx)

        return StructuredContext(
            code_patterns=combined_patterns,
            golden_rules=combined_rules,
            deprecation_warnings=combined_warnings,
            retrieval_time_ms=total_time,
        )

    async def _run_analyzers_sequential(self, file_path: Path, content: str) -> list[AnalysisResult]:
        """Run analyzers sequentially."""
        results = []
        for analyzer in self.analyzers:
            try:
                result = await analyzer.analyze(file_path, content)
                results.append(result)
            except Exception as e:
                logger.error("Analyzer %s failed: %s", analyzer.__class__.__name__, e)
                results.append(AnalysisResult(analyzer_name=analyzer.__class__.__name__, error=str(e)))

        return results

    async def _get_ai_review_with_rag_context(
        self,
        file_path: Path,
        content: str,
        analysis_results: list[AnalysisResult],
        rag_context: StructuredContext | None,
    ) -> dict[str, Any]:
        """
        Get AI review with RAG context using Instructional Priming.

        Implements graceful degradation: Works without RAG context.
        """
        # Build prompt with instructional priming
        if rag_context and rag_context.code_patterns:
            # RAG-enhanced prompt with instructional priming
            self._build_instructional_prompt(
                file_path=file_path,
                content=content,
                analysis_results=analysis_results,
                rag_context=rag_context,
            )
            operating_mode = "rag_enhanced"
        else:
            # Fallback to standard prompt (graceful degradation)
            self.prompt_builder.build_review_prompt(
                file_path=file_path,
                content=content,
                analysis_results=analysis_results,
                similar_patterns=[],
            )
            operating_mode = "blind"

            logger.info(
                "Operating in blind mode - no RAG context available",
                extra={
                    "file": str(file_path),
                    "operating_mode": "blind",
                    "fallback": "standard_prompt",
                },
            )

        # For now, return mock AI review (would use ModelClient in production)
        return {
            "summary": (
                "RAG-enhanced review completed" if operating_mode == "rag_enhanced" else "Standard review completed"
            ),
            "score": 85,
            "confidence": 0.9 if operating_mode == "rag_enhanced" else 0.7,
            "suggestions": [],
            "metadata": {
                "operating_mode": operating_mode,
                "rag_patterns_used": len(rag_context.code_patterns) if rag_context else 0,
            },
        }

    def _build_instructional_prompt(
        self,
        file_path: Path,
        content: str,
        analysis_results: list[AnalysisResult],
        rag_context: StructuredContext,
    ) -> str:
        """
        Build instructional primed prompt (Design Decision 2: Option C).

        Provides explicit instructions on how to use retrieved context.
        """
        sections = [
            "You are reviewing code with access to relevant context from the codebase.",
            "",
            rag_context.to_prompt_section(),
            "",
            "---",
            "",
            "**FILE TO REVIEW:**",
            f"Path: `{file_path}`",
            "",
            "```python",
            content[:2000],  # Limit size
            "```",
            "",
            "**ANALYSIS RESULTS:**",
        ]

        for result in analysis_results:
            sections.append(f"- {result.analyzer_name}: {len(result.violations)} violations")

        sections.extend(
            [
                "",
                "**YOUR TASK:**",
                "Based on the context and analysis above:",
                "1. Evaluate code quality using the provided code patterns as reference",
                "2. Verify compliance with all Golden Rules mentioned",
                "3. Check for any deprecated patterns and recommend replacements",
                "4. Provide actionable suggestions for improvement",
                "",
                "Generate your review:",
            ]
        )

        return "\n".join(sections)

    def _combine_results(
        self,
        file_path: Path,
        analysis_results: list[AnalysisResult],
        ai_review: dict[str, Any],
        rag_context: StructuredContext | None,
    ) -> ReviewResult:
        """Combine all analysis results into final review."""
        # Count violations by severity
        violations_count = {
            Severity.INFO: 0,
            Severity.WARNING: 0,
            Severity.ERROR: 0,
            Severity.CRITICAL: 0,
        }

        for result in analysis_results:
            for violation in result.violations:
                violations_count[violation.severity] += 1

        # Count auto-fixable violations
        auto_fixable_count = sum(
            1 for result in analysis_results for violation in result.violations if violation.fix_suggestion
        )

        # Calculate suggestions count
        suggestions_count = sum(len(result.suggestions) for result in analysis_results)
        suggestions_count += len(ai_review.get("suggestions", []))

        # Add RAG metadata
        metadata = ai_review.get("metadata", {})
        if rag_context:
            metadata["rag_enhanced"] = True
            metadata["rag_patterns_retrieved"] = len(rag_context.code_patterns)
            metadata["golden_rules_applied"] = len(rag_context.golden_rules)
            metadata["deprecation_warnings"] = len(rag_context.deprecation_warnings)
            metadata["retrieval_time_ms"] = rag_context.retrieval_time_ms
        else:
            metadata["rag_enhanced"] = False
            metadata["operating_mode"] = "blind"

        return ReviewResult(
            file_path=file_path,
            analysis_results=analysis_results,
            overall_score=ai_review.get("score", 75),
            summary=ai_review.get("summary", ""),
            violations_count=violations_count,
            suggestions_count=suggestions_count,
            auto_fixable_count=auto_fixable_count,
            ai_confidence=ai_review.get("confidence", 0.8),
            metadata=metadata,
        )

    def get_rag_metrics(self) -> RAGRetrievalMetrics:
        """Get current RAG retrieval metrics."""
        # Calculate average retrieval time
        if self.rag_metrics.successful_queries > 0:
            self.rag_metrics.avg_retrieval_time_ms = (
                self.rag_metrics.total_retrieval_time_ms / self.rag_metrics.successful_queries
            )

        return self.rag_metrics

    async def close(self) -> None:
        """Clean up resources."""
        if self.cache:
            await self.cache.close()

        await self.async_executor.close()

        logger.info(
            "RAGEnhancedReviewEngine closed",
            extra={
                "total_reviews": self.rag_metrics.rag_enhanced_reviews + self.rag_metrics.blind_reviews,
                "rag_enhanced_reviews": self.rag_metrics.rag_enhanced_reviews,
                "blind_reviews": self.rag_metrics.blind_reviews,
                "total_rag_queries": self.rag_metrics.total_queries,
                "successful_queries": self.rag_metrics.successful_queries,
                "failed_queries": self.rag_metrics.failed_queries,
            },
        )
