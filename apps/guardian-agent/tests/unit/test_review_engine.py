"""Comprehensive unit tests for the ReviewEngine."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from guardian_agent.core.config import GuardianConfig
from guardian_agent.core.interfaces import AnalysisResult, ReviewResult, Severity, Violation, ViolationType
from guardian_agent.review.engine import ReviewEngine
from hive_ai import ModelClient, VectorStore
from hive_cache import HiveCacheClient as CacheClient


class TestReviewEngine:
    """Test suite for ReviewEngine."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = GuardianConfig()
        config.review.model = "gpt-3.5-turbo"
        config.review.temperature = 0.3
        config.review.max_tokens = 1000
        config.vector_search.enabled = True
        config.cache.enabled = True
        return config

    @pytest.fixture
    def mock_model_client(self):
        """Create mock ModelClient."""
        mock = MagicMock(spec=ModelClient)
        mock.generate.return_value = AsyncMock(return_value={"content": "Test review", "usage": {"total_tokens": 100}})
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create mock VectorStore."""
        mock = MagicMock(spec=VectorStore)
        mock.search = AsyncMock(
            return_value=[{"text": "similar_code", "score": 0.95}, {"text": "pattern_match", "score": 0.88}],
        )
        return mock

    @pytest.fixture
    def mock_cache(self):
        """Create mock CacheClient."""
        mock = MagicMock(spec=CacheClient)
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_review_engine_initialization(self, config):
        """Test ReviewEngine initialization with all components."""
        with patch("guardian_agent.review.engine.ModelClient"):
            with patch("guardian_agent.review.engine.VectorStore"):
                with patch("guardian_agent.review.engine.CacheClient"):
                    engine = ReviewEngine(config)

                    assert engine.config == config
                    assert engine.model_client is not None
                    assert engine.vector_store is not None
                    assert engine.cache is not None
                    assert len(engine.analyzers) >= 2  # CodeAnalyzer + GoldenRulesAnalyzer

    @pytest.mark.asyncio
    async def test_review_file_with_cache_hit(self, config, mock_model_client, mock_cache):
        """Test file review with cache hit."""
        # Setup cache hit
        cached_result = ReviewResult(
            file_path=Path("test.py"),
            analysis_results=[],
            overall_score=95.0,
            summary="Cached review",
        )
        mock_cache.get = AsyncMock(return_value=cached_result)

        with patch("guardian_agent.review.engine.ModelClient", return_value=mock_model_client):
            with patch("guardian_agent.review.engine.CacheClient", return_value=mock_cache):
                engine = ReviewEngine(config),
                result = await engine.review_file(Path("test.py"))

                assert result == cached_result
                mock_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_file_with_analyzers(self, config, mock_model_client):
        """Test file review runs all analyzers."""
        test_file = Path("test.py"),
        test_code = "def test(): pass"

        with patch("guardian_agent.review.engine.ModelClient", return_value=mock_model_client):
            with patch("builtins.open", MagicMock(return_value=MagicMock(read=MagicMock(return_value=test_code)))):
                engine = ReviewEngine(config)

                # Mock analyzer responses
                for analyzer in engine.analyzers:
                    analyzer.analyze = AsyncMock(
                        return_value=AnalysisResult(
                            analyzer_name=analyzer.__class__.__name__,
                            violations=[],
                            suggestions=[],
                        ),
                    )

                result = await engine.review_file(test_file)

                assert result.file_path == test_file
                assert len(result.analysis_results) == len(engine.analyzers)
                for analyzer in engine.analyzers:
                    analyzer.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_multiple_files_parallel(self, config, mock_model_client):
        """Test parallel review of multiple files."""
        files = [Path(f"test{i}.py") for i in range(5)]

        with patch("guardian_agent.review.engine.ModelClient", return_value=mock_model_client):
            engine = ReviewEngine(config)
            engine.review_file = AsyncMock(
                side_effect=[
                    ReviewResult(file_path=f, analysis_results=[], overall_score=90.0, summary=f"Review for {f}")
                    for f in files
                ],
            )

            results = await engine.review_multiple_files(files)

            assert len(results) == len(files)
            assert all(r.file_path in files for r in results)

    @pytest.mark.asyncio
    async def test_review_with_ai_enhancement(self, config, mock_model_client, mock_vector_store):
        """Test review with AI-powered enhancement."""
        with patch("guardian_agent.review.engine.ModelClient", return_value=mock_model_client):
            with patch("guardian_agent.review.engine.VectorStore", return_value=mock_vector_store):
                engine = ReviewEngine(config)

                # Mock the AI enhancement
                engine._enhance_with_ai = AsyncMock(
                    return_value={
                        "additional_insights": ["Consider using type hints"],
                        "similar_patterns": ["Found similar code in utils.py"],
                    },
                )

                await engine.review_file(Path("test.py"))

                engine._enhance_with_ai.assert_called_once()
                mock_vector_store.search.assert_called()

    @pytest.mark.asyncio
    async def test_review_error_handling(self, config):
        """Test error handling in review process."""
        with patch("guardian_agent.review.engine.ModelClient") as mock_model:
            mock_model.side_effect = Exception("API Error")

            engine = ReviewEngine(config)
            engine.analyzers[0].analyze = AsyncMock(side_effect=Exception("Analyzer failed"))

            # Should handle analyzer failure gracefully
            result = await engine.review_file(Path("test.py"))

            assert result.file_path == Path("test.py")
            assert "error" in result.summary.lower() or len(result.analysis_results) == 0

    @pytest.mark.asyncio
    async def test_review_with_token_limit(self, config, mock_model_client):
        """Test review respects token limits."""
        config.review.max_tokens = 100
        large_code = "x = 1\n" * 10000  # Very large file

        with patch("guardian_agent.review.engine.ModelClient", return_value=mock_model_client):
            with patch("builtins.open", MagicMock(return_value=MagicMock(read=MagicMock(return_value=large_code)))):
                engine = ReviewEngine(config)

                # Should chunk the file or limit analysis
                result = await engine.review_file(Path("large.py"))

                assert result is not None
                # Verify token counting was performed
                assert mock_model_client.generate.called

    @pytest.mark.asyncio
    async def test_review_priority_sorting(self, config):
        """Test violations are sorted by severity."""
        engine = ReviewEngine(config),

        violations = [
            Violation(
                type=ViolationType.CODE_SMELL,
                severity=Severity.INFO,
                rule="test1",
                message="Info message",
                file_path=Path("test.py"),
            ),
            Violation(
                type=ViolationType.BUG,
                severity=Severity.CRITICAL,
                rule="test2",
                message="Critical bug",
                file_path=Path("test.py"),
            ),
            Violation(
                type=ViolationType.CODE_SMELL,
                severity=Severity.WARNING,
                rule="test3",
                message="Warning message",
                file_path=Path("test.py"),
            ),
        ]

        sorted_violations = engine._sort_violations_by_priority(violations)

        assert sorted_violations[0].severity == Severity.CRITICAL
        assert sorted_violations[1].severity == Severity.WARNING
        assert sorted_violations[2].severity == Severity.INFO

    @pytest.mark.asyncio
    async def test_review_cancellation(self, config):
        """Test review can be cancelled mid-process."""
        engine = ReviewEngine(config)

        # Create a slow analyzer
        slow_analyzer = MagicMock()
        slow_analyzer.analyze = AsyncMock(side_effect=lambda *args: asyncio.sleep(10))
        engine.analyzers = [slow_analyzer]

        # Start review and cancel
        review_task = asyncio.create_task(engine.review_file(Path("test.py")))
        await asyncio.sleep(0.1)
        review_task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await review_task

    @pytest.mark.asyncio
    async def test_review_metrics_collection(self, config):
        """Test that review metrics are collected."""
        with patch("guardian_agent.review.engine.ModelClient"):
            engine = ReviewEngine(config)
            engine._collect_metrics = MagicMock()

            await engine.review_file(Path("test.py"))

            engine._collect_metrics.assert_called()


class TestReviewEngineIntegration:
    """Integration tests for ReviewEngine with real components."""

    @pytest.mark.asyncio
    async def test_end_to_end_review_flow(self):
        """Test complete review flow from file to result."""
        config = GuardianConfig()
        config.vector_search.enabled = False
        config.cache.enabled = False

        test_code = '''
def complex_function(x, y, z):
    """Function with high complexity."""
    if x > 0:
        if y > 0:
            if z > 0:
                for i in range(10):
                    print(i)
    return x + y + z
'''

        with patch("builtins.open", MagicMock(return_value=MagicMock(read=MagicMock(return_value=test_code)))):
            with patch("guardian_agent.review.engine.ModelClient") as mock_model:
                mock_model.return_value.generate = AsyncMock(
                    return_value={"content": "Code has high complexity", "usage": {"total_tokens": 50}},
                )

                engine = ReviewEngine(config),
                result = await engine.review_file(Path("test.py"))

                assert result.file_path == Path("test.py")
                assert len(result.analysis_results) > 0
                assert result.overall_score is not None
                assert result.summary is not None
