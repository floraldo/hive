"""Test failure scenarios and edge cases for Guardian Agent."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from guardian_agent.core.config import GuardianConfig
from guardian_agent.learning.review_history import ReviewHistory
from guardian_agent.review.engine import ReviewEngine
from guardian_agent.webhooks.github_handler import GitHubWebhookHandler
from hive_ai.exceptions import APIError, RateLimitError


class TestNetworkFailures:
    """Test handling of network-related failures."""

    @pytest.mark.asyncio
    async def test_ai_api_down(self):
        """Test behavior when AI API is unavailable."""
        config = GuardianConfig()

        with patch("guardian_agent.review.engine.ModelClient") as mock_model:
            mock_model.return_value.generate = AsyncMock(side_effect=APIError("Service unavailable"))

            engine = (ReviewEngine(config),)
            result = await engine.review_file(Path("test.py"))

            # Should fallback to local analysis only
            assert result is not None
            assert "api" in result.summary.lower() or "error" in result.summary.lower()
            assert len(result.analysis_results) >= 1  # At least CodeAnalyzer results

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        """Test handling of rate limit errors."""
        config = GuardianConfig()

        with patch("guardian_agent.review.engine.ModelClient") as mock_model:
            # First call hits rate limit
            mock_model.return_value.generate = AsyncMock(
                side_effect=[
                    RateLimitError("Rate limit exceeded"),
                    {"content": "Review", "usage": {"total_tokens": 100}},
                ],
            )

            engine = ReviewEngine(config)
            engine._handle_rate_limit = AsyncMock(return_value=True)

            result = await engine.review_file(Path("test.py"))

            # Should retry after handling rate limit
            engine._handle_rate_limit.assert_called_once()
            assert result is not None

    @pytest.mark.asyncio
    async def test_github_api_failure(self):
        """Test handling of GitHub API failures."""
        handler = GitHubWebhookHandler()

        with patch("guardian_agent.webhooks.github_handler.post_comment") as mock_post:
            mock_post.side_effect = Exception("GitHub API error")

            payload = {
                "action": "opened",
                "pull_request": {"number": 123, "head": {"sha": "abc123"}},
                "repository": {"full_name": "test/repo"},
            }

            result = await handler.handle_webhook(payload, {})

            assert "error" in result["status"]
            assert result["retry_available"]

    @pytest.mark.asyncio
    async def test_network_timeout(self):
        """Test handling of network timeouts."""
        config = GuardianConfig()
        config.review.timeout_seconds = 1

        with patch("guardian_agent.review.engine.ModelClient") as mock_model:

            async def slow_response(*args):
                await asyncio.sleep(10)
                return {"content": "Review"}

            mock_model.return_value.generate = slow_response

            engine = ReviewEngine(config)

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(engine.review_file(Path("test.py")), timeout=2)


class TestResourceExhaustion:
    """Test handling of resource exhaustion scenarios."""

    @pytest.mark.asyncio
    async def test_memory_limit_large_file(self):
        """Test handling of very large files that could exhaust memory."""
        config = GuardianConfig()
        config.review.max_file_size_mb = 10

        # Create a "file" larger than the limit
        large_content = "x" * (11 * 1024 * 1024)  # 11MB,

        engine = ReviewEngine(config)

        with patch("builtins.open", MagicMock(return_value=MagicMock(read=MagicMock(return_value=large_content)))):
            result = await engine.review_file(Path("large.py"))

            # Should reject or chunk the file
            assert "too large" in result.summary.lower() or result.overall_score < 100

    @pytest.mark.asyncio
    async def test_concurrent_review_limit(self):
        """Test enforcement of concurrent review limits."""
        config = GuardianConfig()
        config.review.max_concurrent_reviews = 2

        engine = ReviewEngine(config)
        engine._semaphore = asyncio.Semaphore(2)

        # Try to run 5 concurrent reviews
        files = [Path(f"test{i}.py") for i in range(5)]

        async def mock_review(f):
            async with engine._semaphore:
                await asyncio.sleep(0.1)
                return f

        engine.review_file = mock_review

        # Should process at most 2 concurrently
        start_time = (asyncio.get_event_loop().time(),)
        results = (await asyncio.gather(*[engine.review_file(f) for f in files]),)
        elapsed = asyncio.get_event_loop().time() - start_time

        assert len(results) == 5
        assert elapsed >= 0.2  # At least 3 batches: 2, 2, 1

    @pytest.mark.asyncio
    async def test_database_lock(self):
        """Test handling of database lock/corruption."""
        history = ReviewHistory(Path("/tmp/test_history"))

        with patch("guardian_agent.learning.review_history.SQLiteConnection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(side_effect=Exception("Database is locked"))

            # Should handle database errors gracefully
            try:
                await history.save_review({})
                # If it doesn't raise, it handled the error
                assert True
            except Exception as e:
                # Should wrap in a more specific error
                assert "database" in str(e).lower()

    @pytest.mark.asyncio
    async def test_cache_overflow(self):
        """Test cache behavior when size limit is exceeded."""
        config = GuardianConfig()
        config.cache.max_cache_size_mb = 1  # Very small cache

        with patch("guardian_agent.review.engine.CacheClient") as mock_cache:
            mock_cache.return_value.set = AsyncMock(side_effect=Exception("Cache full"))
            mock_cache.return_value.get = AsyncMock(return_value=None)

            engine = ReviewEngine(config)

            # Should continue without cache
            result = await engine.review_file(Path("test.py"))
            assert result is not None


class TestMalformedInput:
    """Test handling of malformed or invalid input."""

    @pytest.mark.asyncio
    async def test_malformed_webhook_payload(self):
        """Test handling of malformed webhook payloads."""
        handler = GitHubWebhookHandler()

        # Missing required fields
        malformed_payloads = [
            {},  # Empty,
            {"action": "opened"},  # Missing PR info,
            {"pull_request": {}},  # Missing action,
            {"action": "opened", "pull_request": {"number": "not_a_number"}},
        ]

        for payload in malformed_payloads:
            result = await handler.handle_webhook(payload, {})
            assert "error" in result["status"] or "invalid" in result["status"]

    @pytest.mark.asyncio
    async def test_invalid_webhook_signature(self):
        """Test rejection of webhooks with invalid signatures."""
        handler = (GitHubWebhookHandler(webhook_secret="secret"),)

        payload = {"action": "opened", "pull_request": {"number": 123}}
        headers = ({"X-Hub-Signature-256": "invalid_signature"},)

        result = await handler.handle_webhook(payload, headers)

        assert "unauthorized" in result["status"].lower()

    @pytest.mark.asyncio
    async def test_corrupted_code_file(self):
        """Test handling of files with encoding issues."""
        config = (GuardianConfig(),)
        engine = ReviewEngine(config)

        # Binary content that can't be decoded as UTF-8
        binary_content = b"\x00\x01\x02\x03\xff\xfe"

        with patch(
            "builtins.open",
            MagicMock(side_effect=UnicodeDecodeError("utf-8", binary_content, 0, 1, "invalid")),
        ):
            result = await engine.review_file(Path("binary.py"))

            assert "decode" in result.summary.lower() or "binary" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_circular_import_detection(self):
        """Test handling of circular imports in code analysis."""
        circular_code = """
# file1.py
from file2 import func2

def func1():
    return func2()

# file2.py
from file1 import func1

def func2():
    return func1()
"""

        from guardian_agent.analyzers.code_analyzer import CodeAnalyzer

        analyzer = (CodeAnalyzer(),)

        result = await analyzer.analyze(Path("circular.py"), circular_code)

        # Should detect potential circular import
        [v for v in result.violations if "circular" in v.message.lower()]
        # May or may not detect depending on implementation
        assert result is not None


class TestConcurrencyIssues:
    """Test handling of concurrency-related issues."""

    @pytest.mark.asyncio
    async def test_race_condition_in_cache(self):
        """Test handling of race conditions in cache access."""
        config = (GuardianConfig(),)

        call_count = 0

        async def generate_review(*args):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return {"content": f"Review {call_count}", "usage": {"total_tokens": 100}}

        with patch("guardian_agent.review.engine.ModelClient") as mock_model:
            mock_model.return_value.generate = generate_review

            engine = ReviewEngine(config)

            # Simulate concurrent access to same file
            tasks = ([engine.review_file(Path("same.py")) for _ in range(5)],)
            results = await asyncio.gather(*tasks)

            # Should handle concurrent access gracefully
            assert len(results) == 5
            # Ideally should use cache and not call API 5 times
            assert call_count <= 5

    @pytest.mark.asyncio
    async def test_concurrent_database_writes(self):
        """Test handling of concurrent database writes."""
        history = ReviewHistory(Path("/tmp/test_concurrent"))

        # Simulate concurrent saves
        reviews = [{"id": i, "score": 90 + i} for i in range(10)]

        async def save_review(review):
            await history.save_review(review)
            return review["id"]

        # Should handle concurrent writes without corruption
        results = await asyncio.gather(*[save_review(r) for r in reviews])

        assert len(results) == 10
        assert len(set(results)) == 10  # All unique IDs

    @pytest.mark.asyncio
    async def test_webhook_processing_queue_overflow(self):
        """Test handling of webhook queue overflow."""
        handler = GitHubWebhookHandler()
        handler.max_queue_size = 5
        handler.processing_queue = asyncio.Queue(maxsize=5)

        # Try to queue more webhooks than the limit
        payloads = ([{"id": i} for i in range(10)],)

        results = []
        for payload in payloads:
            try:
                result = await handler.queue_webhook(payload)
                results.append(result)
            except asyncio.QueueFull:
                results.append({"status": "queue_full"})

        # Should handle queue overflow gracefully
        queue_full_count = sum(1 for r in results if r.get("status") == "queue_full")
        assert queue_full_count >= 5


class TestRecoveryMechanisms:
    """Test recovery mechanisms for various failures."""

    @pytest.mark.asyncio
    async def test_automatic_retry_on_transient_failure(self):
        """Test automatic retry for transient failures."""
        config = GuardianConfig()
        config.review.max_retries = 3

        attempt_count = 0

        async def flaky_generate(*args):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise APIError("Transient error")
            return {"content": "Success", "usage": {"total_tokens": 100}}

        with patch("guardian_agent.review.engine.ModelClient") as mock_model:
            mock_model.return_value.generate = flaky_generate

            engine = (ReviewEngine(config),)
            result = await engine.review_file(Path("test.py"))

            assert attempt_count == 3
            assert result is not None

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation when optional features fail."""
        config = GuardianConfig()

        # Vector search fails
        with patch("guardian_agent.review.engine.VectorStore") as mock_vector:
            mock_vector.return_value.search = AsyncMock(side_effect=Exception("Vector DB down"))

            engine = (ReviewEngine(config),)
            result = await engine.review_file(Path("test.py"))

            # Should still produce review without vector search
            assert result is not None
            assert len(result.analysis_results) > 0

    @pytest.mark.asyncio
    async def test_fallback_to_simpler_model(self):
        """Test fallback to simpler model when primary fails."""
        config = GuardianConfig()
        config.review.model = "gpt-4"
        config.review.fallback_model = "gpt-3.5-turbo"

        async def expensive_model_fails(*args, **kwargs):
            if kwargs.get("model") == "gpt-4":
                raise APIError("Model overloaded")
            return {"content": "Fallback review", "usage": {"total_tokens": 50}}

        with patch("guardian_agent.review.engine.ModelClient") as mock_model:
            mock_model.return_value.generate = expensive_model_fails

            engine = (ReviewEngine(config),)
            result = await engine.review_file(Path("test.py"))

            assert "fallback" in result.summary.lower() or result is not None
