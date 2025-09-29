"""Main review engine orchestrating the code review process."""

import time
from pathlib import Path
from typing import Any

from guardian_agent.analyzers.code_analyzer import CodeAnalyzer
from guardian_agent.analyzers.golden_rules import GoldenRulesAnalyzer
from guardian_agent.core.config import GuardianConfig
from guardian_agent.core.interfaces import AnalysisResult, ReviewResult, Severity
from guardian_agent.prompts.review_prompts import ReviewPromptBuilder
from hive_ai import ModelClient, VectorStore
from hive_async import AsyncExecutor
from hive_cache import CacheClient
from hive_logging import get_logger

logger = get_logger(__name__)


class ReviewEngine:
    """
    Main engine for orchestrating code reviews.

    Leverages hive-ai for model management, vector search for context,
    and coordinates multiple analyzers for comprehensive review.
    """

    def __init__(self, config: GuardianConfig | None = None) -> None:
        """Initialize the review engine."""
        self.config = config or GuardianConfig()

        # Initialize hive-ai components
        self.model_client = ModelClient(
            model_name=self.config.review.model,
            api_key=self.config.openai_api_key,
            temperature=self.config.review.temperature,
            max_tokens=self.config.review.max_tokens,
        )

        # Initialize vector store for pattern matching
        if self.config.vector_search.enabled:
            self.vector_store = VectorStore(
                index_path=str(self.config.vector_search.index_path), model_name=self.config.vector_search.model_name,
            )
        else:
            self.vector_store = None

        # Initialize cache
        if self.config.cache.enabled:
            self.cache = CacheClient(
                ttl_seconds=self.config.cache.ttl_seconds, max_size_mb=self.config.cache.max_cache_size_mb,
            )
        else:
            self.cache = None

        # Initialize async executor for parallel analysis
        self.async_executor = AsyncExecutor(max_workers=4)

        # Initialize analyzers
        self.analyzers = self._initialize_analyzers()

        # Initialize prompt builder
        self.prompt_builder = ReviewPromptBuilder()

        logger.info("ReviewEngine initialized with %d analyzers", len(self.analyzers))

    def _initialize_analyzers(self) -> list[Any]:
        """Initialize all configured analyzers."""
        analyzers = []

        # Always include code analyzer for AST analysis
        analyzers.append(CodeAnalyzer())

        # Add Golden Rules analyzer if enabled
        if self.config.review.enable_golden_rules:
            analyzers.append(GoldenRulesAnalyzer())

        # Additional analyzers can be added here
        # if self.config.review.enable_security_scan:
        #     analyzers.append(SecurityAnalyzer())

        return analyzers

    async def review_file(self, file_path: Path) -> ReviewResult:
        """
        Review a single file.

        Args:
            file_path: Path to the file to review

        Returns:
            ReviewResult containing all findings
        """
        start_time = time.time()

        # Check cache first
        cache_key = f"review:{file_path}:{file_path.stat().st_mtime}"
        if self.cache:
            cached_result = await self.cache.get_async(cache_key)
            if cached_result:
                logger.info("Using cached review for %s", file_path)
                return cached_result

        # Read file content
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error("Failed to read file %s: %s", file_path, e)
            raise

        # Check file size limit
        file_size_kb = len(content) / 1024
        if file_size_kb > self.config.review.max_file_size_kb:
            logger.warning("File %s exceeds size limit (%.1f KB)", file_path, file_size_kb)
            # Could return partial review or skip

        # Run analyzers
        if self.config.review.parallel_analysis:
            analysis_results = await self._run_analyzers_parallel(file_path, content)
        else:
            analysis_results = await self._run_analyzers_sequential(file_path, content)

        # Get AI-powered review
        ai_review = await self._get_ai_review(file_path, content, analysis_results)

        # Combine results
        result = self._combine_results(file_path, analysis_results, ai_review)

        # Cache result
        if self.cache:
            await self.cache.set_async(cache_key, result)

        execution_time = (time.time() - start_time) * 1000
        logger.info(
            "Review completed for %s in %.1f ms (%d violations, %d suggestions)",
            file_path,
            execution_time,
            len(result.all_violations),
            len(result.all_suggestions),
        )

        return result

    async def _run_analyzers_parallel(self, file_path: Path, content: str) -> list[AnalysisResult]:
        """Run all analyzers in parallel."""
        tasks = []
        for analyzer in self.analyzers:
            task = self.async_executor.submit(analyzer.analyze, file_path, content)
            tasks.append(task)

        results = await self.async_executor.gather(*tasks)
        return results

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

    async def _get_ai_review(
        self, file_path: Path, content: str, analysis_results: list[AnalysisResult],
    ) -> dict[str, Any]:
        """Get AI-powered review using hive-ai."""
        # Find similar code patterns if vector search is enabled
        similar_patterns = []
        if self.vector_store:
            try:
                similar_patterns = await self.vector_store.search(
                    query=content[:1000],  # Use first 1000 chars as query,
                    k=self.config.vector_search.max_results,
                    threshold=self.config.vector_search.similarity_threshold,
                )
            except Exception as e:
                logger.warning("Vector search failed: %s", e)

        # Build prompt
        prompt = self.prompt_builder.build_review_prompt(
            file_path=file_path, content=content, analysis_results=analysis_results, similar_patterns=similar_patterns,
        )

        # Get AI review
        try:
            response = await self.model_client.complete(prompt)

            # Parse AI response (assumes structured output)
            ai_review = {
                "summary": response.get("summary", ""),
                "score": response.get("score", 75),
                "confidence": response.get("confidence", 0.8),
                "suggestions": response.get("suggestions", []),
                "metadata": response.get("metadata", {}),
            }

        except Exception as e:
            logger.error("AI review failed: %s", e)
            ai_review = {
                "summary": "AI review unavailable",
                "score": 0,
                "confidence": 0,
                "suggestions": [],
                "metadata": {"error": str(e)},
            }

        return ai_review

    def _combine_results(
        self, file_path: Path, analysis_results: list[AnalysisResult], ai_review: dict[str, Any],
    ) -> ReviewResult:
        """Combine all analysis results into final review."""
        # Count violations by severity
        violations_count = {Severity.INFO: 0, Severity.WARNING: 0, Severity.ERROR: 0, Severity.CRITICAL: 0}

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

        return ReviewResult(
            file_path=file_path,
            analysis_results=analysis_results,
            overall_score=ai_review.get("score", 75),
            summary=ai_review.get("summary", ""),
            violations_count=violations_count,
            suggestions_count=suggestions_count,
            auto_fixable_count=auto_fixable_count,
            ai_confidence=ai_review.get("confidence", 0.8),
            metadata=ai_review.get("metadata", {}),
        )

    async def review_directory(self, directory: Path, recursive: bool = True) -> list[ReviewResult]:
        """
        Review all files in a directory.

        Args:
            directory: Directory to review
            recursive: Whether to review subdirectories

        Returns:
            List of review results
        """
        pattern = "**/*" if recursive else "*"
        files = []

        for include_pattern in self.config.include_patterns:
            files.extend(directory.glob(f"{pattern}{include_pattern}"))

        # Filter excluded patterns
        filtered_files = []
        for file_path in files:
            excluded = False
            for exclude_pattern in self.config.exclude_patterns:
                if file_path.match(exclude_pattern):
                    excluded = True
                    break

            if not excluded and file_path.is_file():
                filtered_files.append(file_path)

        logger.info("Reviewing %d files in %s", len(filtered_files), directory)

        # Review files in parallel
        tasks = [self.review_file(file_path) for file_path in filtered_files]
        results = await self.async_executor.gather(*tasks)

        return results

    async def close(self) -> None:
        """Clean up resources."""
        if self.cache:
            await self.cache.close()

        if self.vector_store:
            await self.vector_store.close()

        await self.async_executor.close()

        logger.info("ReviewEngine closed")
