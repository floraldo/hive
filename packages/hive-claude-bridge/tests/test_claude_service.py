"""
Unit tests for ClaudeService
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from hive_claude_bridge.claude_service import (
    ClaudeService,
    ClaudeMetrics,
    RateLimitConfig,
    RateLimiter,
    CacheEntry,
    get_claude_service,
    reset_claude_service
)
from hive_claude_bridge.bridge import ClaudeBridgeConfig
from hive_claude_bridge.exceptions import ClaudeRateLimitError, ClaudeServiceError


class TestClaudeMetrics:
    """Test ClaudeMetrics dataclass"""

    def test_metrics_initialization(self):
        """Test metrics are initialized to zero"""
        metrics = ClaudeMetrics()
        assert metrics.total_calls == 0
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 0
        assert metrics.cached_responses == 0
        assert metrics.total_tokens == 0
        assert metrics.total_latency_ms == 0.0
        assert metrics.rate_limited == 0

    def test_average_latency_no_calls(self):
        """Test average latency when no successful calls"""
        metrics = ClaudeMetrics()
        assert metrics.average_latency_ms == 0.0

    def test_average_latency_with_calls(self):
        """Test average latency calculation"""
        metrics = ClaudeMetrics(
            successful_calls=3,
            total_latency_ms=300.0
        )
        assert metrics.average_latency_ms == 100.0

    def test_success_rate_no_calls(self):
        """Test success rate when no calls made"""
        metrics = ClaudeMetrics()
        assert metrics.success_rate == 0.0

    def test_success_rate_with_calls(self):
        """Test success rate calculation"""
        metrics = ClaudeMetrics(
            total_calls=10,
            successful_calls=8
        )
        assert metrics.success_rate == 80.0

    def test_to_dict(self):
        """Test metrics conversion to dictionary"""
        metrics = ClaudeMetrics(
            total_calls=10,
            successful_calls=8,
            failed_calls=2,
            cached_responses=3,
            total_tokens=1000,
            total_latency_ms=800.0,
            rate_limited=1
        )

        result = metrics.to_dict()

        assert result["total_calls"] == 10
        assert result["successful_calls"] == 8
        assert result["failed_calls"] == 2
        assert result["cached_responses"] == 3
        assert result["total_tokens"] == 1000
        assert result["average_latency_ms"] == 100.0
        assert result["success_rate"] == 80.0
        assert result["rate_limited"] == 1


class TestCacheEntry:
    """Test CacheEntry functionality"""

    def test_cache_entry_creation(self):
        """Test cache entry creation"""
        response = {"result": "test"}
        entry = CacheEntry(response=response, timestamp=datetime.now())

        assert entry.response == response
        assert entry.hit_count == 0
        assert isinstance(entry.timestamp, datetime)

    def test_cache_not_expired(self):
        """Test cache entry not expired"""
        entry = CacheEntry(
            response={"test": "data"},
            timestamp=datetime.now()
        )

        assert not entry.is_expired(300)  # 5 minutes TTL

    def test_cache_expired(self):
        """Test cache entry expired"""
        old_time = datetime.now() - timedelta(minutes=10)
        entry = CacheEntry(
            response={"test": "data"},
            timestamp=old_time
        )

        assert entry.is_expired(300)  # 5 minutes TTL


class TestRateLimiter:
    """Test RateLimiter functionality"""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization"""
        config = RateLimitConfig(max_calls_per_minute=60, max_calls_per_hour=1000)
        limiter = RateLimiter(config)

        assert limiter.config.max_calls_per_minute == 60
        assert limiter.config.max_calls_per_hour == 1000

    def test_rate_limiter_allows_requests(self):
        """Test rate limiter allows requests within limits"""
        config = RateLimitConfig(max_calls_per_minute=10, max_calls_per_hour=100)
        limiter = RateLimiter(config)

        # Should allow first request
        assert limiter.can_make_request()
        limiter.record_request()

    def test_rate_limiter_blocks_excess_requests(self):
        """Test rate limiter blocks excessive requests"""
        config = RateLimitConfig(max_calls_per_minute=2, max_calls_per_hour=10)
        limiter = RateLimiter(config)

        # Make 2 requests (at limit)
        assert limiter.can_make_request()
        limiter.record_request()
        assert limiter.can_make_request()
        limiter.record_request()

        # Third request should be blocked
        assert not limiter.can_make_request()

    def test_rate_limiter_time_window_reset(self):
        """Test rate limiter resets after time window"""
        config = RateLimitConfig(max_calls_per_minute=1, max_calls_per_hour=10)
        limiter = RateLimiter(config)

        # Make one request
        assert limiter.can_make_request()
        limiter.record_request()

        # Should be blocked immediately
        assert not limiter.can_make_request()

        # Simulate time passing by clearing old requests
        limiter.minute_requests.clear()

        # Should be allowed again
        assert limiter.can_make_request()


class TestClaudeService:
    """Test ClaudeService functionality"""

    def setup_method(self):
        """Setup for each test"""
        # Reset singleton for clean tests
        reset_claude_service()

    def test_singleton_pattern(self):
        """Test that ClaudeService is a singleton"""
        service1 = ClaudeService()
        service2 = ClaudeService()

        assert service1 is service2

    def test_service_initialization(self):
        """Test service initialization"""
        config = ClaudeBridgeConfig(mock_mode=True)
        rate_config = RateLimitConfig(max_calls_per_minute=60)

        service = ClaudeService(config=config, rate_config=rate_config)

        assert service.config.mock_mode is True
        assert service.rate_limiter.config.max_calls_per_minute == 60
        assert service.cache_ttl == 300
        assert isinstance(service.metrics, ClaudeMetrics)

    def test_cache_key_generation(self):
        """Test cache key generation"""
        service = ClaudeService()

        key1 = service._generate_cache_key("plan", {"task": "test"})
        key2 = service._generate_cache_key("plan", {"task": "test"})
        key3 = service._generate_cache_key("plan", {"task": "different"})

        assert key1 == key2
        assert key1 != key3

    @patch('hive_claude_bridge.claude_service.ClaudeService._call_bridge')
    def test_cache_hit(self, mock_call):
        """Test cache hit returns cached response"""
        service = ClaudeService()

        # First call should cache result
        mock_response = {"result": "cached"}
        mock_call.return_value = mock_response

        result1 = service.plan_task(
            task_id="test",
            description="test task",
            use_cache=True
        )

        # Second call should use cache
        result2 = service.plan_task(
            task_id="test",
            description="test task",
            use_cache=True
        )

        assert result1 == result2
        assert mock_call.call_count == 1  # Only called once
        assert service.metrics.cached_responses == 1

    @patch('hive_claude_bridge.claude_service.ClaudeService._call_bridge')
    def test_cache_disabled(self, mock_call):
        """Test cache can be disabled"""
        service = ClaudeService()

        mock_response = {"result": "not cached"}
        mock_call.return_value = mock_response

        result1 = service.plan_task(
            task_id="test",
            description="test task",
            use_cache=False
        )

        result2 = service.plan_task(
            task_id="test",
            description="test task",
            use_cache=False
        )

        assert result1 == result2
        assert mock_call.call_count == 2  # Called twice
        assert service.metrics.cached_responses == 0

    def test_cache_expiry(self):
        """Test cache entries expire correctly"""
        service = ClaudeService(cache_ttl=1)  # 1 second TTL

        # Add expired entry
        old_time = datetime.now() - timedelta(seconds=2)
        service.cache["test_key"] = CacheEntry(
            response={"old": "data"},
            timestamp=old_time
        )

        # Clean cache should remove expired entry
        service._clean_cache()

        assert "test_key" not in service.cache

    def test_rate_limiting_blocks_requests(self):
        """Test rate limiting blocks excessive requests"""
        config = RateLimitConfig(max_calls_per_minute=1, max_calls_per_hour=5)
        service = ClaudeService(rate_config=config)

        # First request should work
        with patch.object(service, '_call_bridge') as mock_call:
            mock_call.return_value = {"result": "success"}

            result1 = service.plan_task(
                task_id="test1",
                description="test task",
                use_cache=False
            )

            # Second request should be rate limited
            with pytest.raises(ClaudeRateLimitError):
                service.plan_task(
                    task_id="test2",
                    description="test task",
                    use_cache=False
                )

    def test_metrics_tracking(self):
        """Test metrics are properly tracked"""
        service = ClaudeService()

        with patch.object(service, '_call_bridge') as mock_call:
            mock_call.return_value = {"result": "success"}

            # Make successful call
            service.plan_task(
                task_id="test",
                description="test task",
                use_cache=False
            )

            assert service.metrics.total_calls == 1
            assert service.metrics.successful_calls == 1
            assert service.metrics.failed_calls == 0

    def test_error_handling(self):
        """Test error handling and metrics"""
        service = ClaudeService()

        with patch.object(service, '_call_bridge') as mock_call:
            mock_call.side_effect = Exception("Test error")

            with pytest.raises(ClaudeServiceError):
                service.plan_task(
                    task_id="test",
                    description="test task",
                    use_cache=False
                )

            assert service.metrics.total_calls == 1
            assert service.metrics.successful_calls == 0
            assert service.metrics.failed_calls == 1

    def test_get_metrics(self):
        """Test metrics retrieval"""
        service = ClaudeService()

        metrics = service.get_metrics()

        assert isinstance(metrics, dict)
        assert "total_calls" in metrics
        assert "success_rate" in metrics

    def test_clear_cache(self):
        """Test cache clearing"""
        service = ClaudeService()

        # Add some cache entries
        service.cache["key1"] = CacheEntry({"data": 1}, datetime.now())
        service.cache["key2"] = CacheEntry({"data": 2}, datetime.now())

        assert len(service.cache) == 2

        service.clear_cache()

        assert len(service.cache) == 0

    def test_reset_metrics(self):
        """Test metrics reset"""
        service = ClaudeService()

        # Set some metrics
        service.metrics.total_calls = 10
        service.metrics.successful_calls = 8

        service.reset_metrics()

        assert service.metrics.total_calls == 0
        assert service.metrics.successful_calls == 0


class TestServiceHelpers:
    """Test service helper functions"""

    def test_get_claude_service(self):
        """Test get_claude_service function"""
        reset_claude_service()  # Clean slate

        service1 = get_claude_service()
        service2 = get_claude_service()

        assert service1 is service2
        assert isinstance(service1, ClaudeService)

    def test_get_claude_service_with_config(self):
        """Test get_claude_service with custom config"""
        reset_claude_service()

        config = ClaudeBridgeConfig(mock_mode=True)
        rate_config = RateLimitConfig(max_calls_per_minute=120)

        service = get_claude_service(config=config, rate_config=rate_config)

        assert service.config.mock_mode is True
        assert service.rate_limiter.config.max_calls_per_minute == 120

    def test_reset_claude_service(self):
        """Test service reset"""
        service1 = get_claude_service()
        reset_claude_service()
        service2 = get_claude_service()

        assert service1 is not service2


if __name__ == "__main__":
    pytest.main([__file__])