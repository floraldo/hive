"""
Unit tests for RateLimiter
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from hive_claude_bridge.claude_service import RateLimiter, RateLimitConfig


class TestRateLimitConfig:
    """Test RateLimitConfig dataclass"""

    def test_default_config(self):
        """Test default rate limit configuration"""
        config = RateLimitConfig()

        assert config.max_calls_per_minute == 30
        assert config.max_calls_per_hour == 1000
        assert config.burst_size == 5
        assert config.cooldown_seconds == 60

    def test_custom_config(self):
        """Test custom rate limit configuration"""
        config = RateLimitConfig(
            max_calls_per_minute=60,
            max_calls_per_hour=2000,
            burst_size=10,
            cooldown_seconds=30
        )

        assert config.max_calls_per_minute == 60
        assert config.max_calls_per_hour == 2000
        assert config.burst_size == 10
        assert config.cooldown_seconds == 30


class TestRateLimiter:
    """Test RateLimiter implementation"""

    def test_initialization(self):
        """Test rate limiter initialization"""
        config = RateLimitConfig(max_calls_per_minute=60)
        limiter = RateLimiter(config)

        assert limiter.config == config
        assert len(limiter.minute_requests) == 0
        assert len(limiter.hour_requests) == 0
        assert limiter.tokens == config.burst_size

    def test_can_make_request_with_tokens(self):
        """Test can_make_request when tokens available"""
        config = RateLimitConfig(burst_size=5)
        limiter = RateLimiter(config)

        assert limiter.can_make_request()
        assert limiter.tokens == 5

    def test_can_make_request_no_tokens_within_limits(self):
        """Test can_make_request when no tokens but within rate limits"""
        config = RateLimitConfig(
            max_calls_per_minute=60,
            max_calls_per_hour=1000,
            burst_size=0
        )
        limiter = RateLimiter(config)

        # No tokens, but should still allow if within limits
        assert limiter.can_make_request()

    def test_can_make_request_minute_limit_exceeded(self):
        """Test can_make_request when minute limit exceeded"""
        config = RateLimitConfig(
            max_calls_per_minute=2,
            max_calls_per_hour=1000,
            burst_size=0
        )
        limiter = RateLimiter(config)

        # Fill up the minute limit
        now = datetime.now()
        limiter.minute_requests.extend([now, now])

        assert not limiter.can_make_request()

    def test_can_make_request_hour_limit_exceeded(self):
        """Test can_make_request when hour limit exceeded"""
        config = RateLimitConfig(
            max_calls_per_minute=1000,
            max_calls_per_hour=2,
            burst_size=0
        )
        limiter = RateLimiter(config)

        # Fill up the hour limit
        now = datetime.now()
        limiter.hour_requests.extend([now, now])

        assert not limiter.can_make_request()

    def test_record_request_consumes_token(self):
        """Test record_request consumes a token"""
        config = RateLimitConfig(burst_size=5)
        limiter = RateLimiter(config)

        initial_tokens = limiter.tokens
        limiter.record_request()

        assert limiter.tokens == initial_tokens - 1

    def test_record_request_adds_to_queues(self):
        """Test record_request adds timestamp to tracking queues"""
        config = RateLimitConfig()
        limiter = RateLimiter(config)

        initial_minute_count = len(limiter.minute_requests)
        initial_hour_count = len(limiter.hour_requests)

        limiter.record_request()

        assert len(limiter.minute_requests) == initial_minute_count + 1
        assert len(limiter.hour_requests) == initial_hour_count + 1

    def test_token_replenishment(self):
        """Test token bucket replenishment"""
        config = RateLimitConfig(burst_size=5, max_calls_per_minute=60)
        limiter = RateLimiter(config)

        # Consume all tokens
        for _ in range(5):
            limiter.record_request()

        assert limiter.tokens == 0

        # Mock time passage to trigger replenishment
        with patch('time.time') as mock_time:
            # Simulate 1 second passing (should add 1 token at 60/min rate)
            mock_time.return_value = time.time() + 1
            limiter._refill_tokens()

            assert limiter.tokens == 1

    def test_token_replenishment_max_burst(self):
        """Test tokens don't exceed burst size"""
        config = RateLimitConfig(burst_size=3, max_calls_per_minute=60)
        limiter = RateLimiter(config)

        # Mock significant time passage
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 10  # 10 seconds
            limiter._refill_tokens()

            # Should not exceed burst size
            assert limiter.tokens == 3

    def test_cleanup_old_requests_minute(self):
        """Test cleanup of old minute requests"""
        config = RateLimitConfig()
        limiter = RateLimiter(config)

        # Add old request (over 1 minute ago)
        old_time = datetime.now() - timedelta(minutes=2)
        limiter.minute_requests.append(old_time)

        # Add recent request
        recent_time = datetime.now()
        limiter.minute_requests.append(recent_time)

        limiter._cleanup_old_requests()

        # Only recent request should remain
        assert len(limiter.minute_requests) == 1
        assert limiter.minute_requests[0] == recent_time

    def test_cleanup_old_requests_hour(self):
        """Test cleanup of old hour requests"""
        config = RateLimitConfig()
        limiter = RateLimiter(config)

        # Add old request (over 1 hour ago)
        old_time = datetime.now() - timedelta(hours=2)
        limiter.hour_requests.append(old_time)

        # Add recent request
        recent_time = datetime.now()
        limiter.hour_requests.append(recent_time)

        limiter._cleanup_old_requests()

        # Only recent request should remain
        assert len(limiter.hour_requests) == 1
        assert limiter.hour_requests[0] == recent_time

    def test_wait_for_rate_limit_available_immediately(self):
        """Test wait_for_rate_limit when request can be made immediately"""
        config = RateLimitConfig(burst_size=5)
        limiter = RateLimiter(config)

        start_time = time.time()
        limiter.wait_for_rate_limit()
        end_time = time.time()

        # Should return immediately
        assert end_time - start_time < 0.1

    def test_wait_for_rate_limit_with_delay(self):
        """Test wait_for_rate_limit when delay is needed"""
        config = RateLimitConfig(
            max_calls_per_minute=1,
            max_calls_per_hour=10,
            burst_size=0
        )
        limiter = RateLimiter(config)

        # Make a request to hit the limit
        limiter.record_request()

        # Next request should need to wait
        with patch('time.sleep') as mock_sleep:
            with patch.object(limiter, 'can_make_request', side_effect=[False, True]):
                limiter.wait_for_rate_limit()

                # Should have called sleep
                mock_sleep.assert_called()

    def test_get_wait_time_no_wait_needed(self):
        """Test get_wait_time when no wait is needed"""
        config = RateLimitConfig(burst_size=5)
        limiter = RateLimiter(config)

        wait_time = limiter.get_wait_time()

        assert wait_time == 0

    def test_get_wait_time_minute_limit(self):
        """Test get_wait_time when minute limit hit"""
        config = RateLimitConfig(
            max_calls_per_minute=1,
            max_calls_per_hour=10,
            burst_size=0
        )
        limiter = RateLimiter(config)

        # Hit minute limit
        limiter.minute_requests.append(datetime.now())

        wait_time = limiter.get_wait_time()

        # Should need to wait close to 60 seconds
        assert 59 <= wait_time <= 61

    def test_get_wait_time_hour_limit(self):
        """Test get_wait_time when hour limit hit"""
        config = RateLimitConfig(
            max_calls_per_minute=100,
            max_calls_per_hour=1,
            burst_size=0
        )
        limiter = RateLimiter(config)

        # Hit hour limit
        limiter.hour_requests.append(datetime.now())

        wait_time = limiter.get_wait_time()

        # Should need to wait close to 3600 seconds
        assert 3590 <= wait_time <= 3610

    def test_reset(self):
        """Test rate limiter reset"""
        config = RateLimitConfig(burst_size=5)
        limiter = RateLimiter(config)

        # Make some requests
        limiter.record_request()
        limiter.record_request()

        assert len(limiter.minute_requests) == 2
        assert len(limiter.hour_requests) == 2
        assert limiter.tokens == 3

        # Reset
        limiter.reset()

        assert len(limiter.minute_requests) == 0
        assert len(limiter.hour_requests) == 0
        assert limiter.tokens == config.burst_size

    def test_integration_burst_then_steady_rate(self):
        """Test integration: burst of requests then steady rate"""
        config = RateLimitConfig(
            max_calls_per_minute=60,  # 1 per second
            max_calls_per_hour=1000,
            burst_size=3
        )
        limiter = RateLimiter(config)

        # Should allow burst of 3 requests
        for i in range(3):
            assert limiter.can_make_request()
            limiter.record_request()

        # 4th request should fail (no tokens, need to wait for replenishment)
        assert not limiter.can_make_request()

        # Simulate 1 second passing
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 1
            limiter._refill_tokens()

            # Should now allow 1 more request
            assert limiter.can_make_request()
            limiter.record_request()

            # Should block again
            assert not limiter.can_make_request()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])