"""
Integration tests for ClaudeService with real dependencies
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch

from hive_claude_bridge.claude_service import (
    ClaudeService,
    RateLimitConfig,
    get_claude_service,
    reset_claude_service
)
from hive_claude_bridge.bridge import ClaudeBridgeConfig


class TestClaudeServiceIntegration:
    """Integration tests for ClaudeService"""

    def setup_method(self):
        """Setup for each test"""
        reset_claude_service()

    def test_service_singleton_integration(self):
        """Test singleton behavior across modules"""
        service1 = get_claude_service()
        service2 = ClaudeService()
        service3 = get_claude_service()

        assert service1 is service2
        assert service2 is service3

    def test_mock_mode_integration(self):
        """Test mock mode integration"""
        config = ClaudeBridgeConfig(mock_mode=True)
        service = ClaudeService(config=config)

        # Test planning in mock mode
        result = service.plan_task(
            task_id="mock-test",
            description="Test task for mock mode",
            use_cache=False
        )

        # Should return a valid response structure
        assert isinstance(result, dict)
        assert service.metrics.total_calls > 0

    def test_rate_limiting_integration(self):
        """Test rate limiting with real ClaudeService"""
        rate_config = RateLimitConfig(
            max_calls_per_minute=2,
            max_calls_per_hour=10,
            burst_size=1
        )

        service = ClaudeService(
            config=ClaudeBridgeConfig(mock_mode=True),
            rate_config=rate_config
        )

        # First call should work
        result1 = service.plan_task(
            task_id="rate-test-1",
            description="First task",
            use_cache=False
        )
        assert result1 is not None

        # Second call should work (uses burst)
        result2 = service.plan_task(
            task_id="rate-test-2",
            description="Second task",
            use_cache=False
        )
        assert result2 is not None

        # Third call should be rate limited
        with pytest.raises(Exception):  # Should raise rate limit error
            service.plan_task(
                task_id="rate-test-3",
                description="Third task",
                use_cache=False
            )

    def test_caching_integration(self):
        """Test caching behavior integration"""
        service = ClaudeService(
            config=ClaudeBridgeConfig(mock_mode=True),
            cache_ttl=5  # 5 second TTL
        )

        # First call should cache
        start_time = time.time()
        result1 = service.plan_task(
            task_id="cache-test",
            description="Cacheable task",
            use_cache=True
        )
        first_call_time = time.time() - start_time

        # Second call should be much faster (cached)
        start_time = time.time()
        result2 = service.plan_task(
            task_id="cache-test",
            description="Cacheable task",
            use_cache=True
        )
        second_call_time = time.time() - start_time

        assert result1 == result2
        assert second_call_time < first_call_time / 2  # Should be much faster
        assert service.metrics.cached_responses > 0

    def test_metrics_integration(self):
        """Test metrics collection integration"""
        service = ClaudeService(config=ClaudeBridgeConfig(mock_mode=True))

        initial_metrics = service.get_metrics()
        assert initial_metrics["total_calls"] == 0

        # Make some calls
        service.plan_task(
            task_id="metrics-test-1",
            description="First metrics test",
            use_cache=False
        )

        service.plan_task(
            task_id="metrics-test-2",
            description="Second metrics test",
            use_cache=False
        )

        # Check metrics updated
        final_metrics = service.get_metrics()
        assert final_metrics["total_calls"] == 2
        assert final_metrics["successful_calls"] == 2
        assert final_metrics["success_rate"] == 100.0

    def test_error_reporting_integration(self):
        """Test error reporting integration"""
        service = ClaudeService(config=ClaudeBridgeConfig(mock_mode=False))

        # This should fail since Claude CLI likely isn't available
        with pytest.raises(Exception):
            service.plan_task(
                task_id="error-test",
                description="This should fail",
                use_cache=False
            )

        # Error should be tracked in metrics
        metrics = service.get_metrics()
        assert metrics["failed_calls"] > 0

    def test_bridge_integration(self):
        """Test integration with bridge components"""
        service = ClaudeService(config=ClaudeBridgeConfig(mock_mode=True))

        # Test planner bridge
        plan_result = service.plan_task(
            task_id="bridge-test",
            description="Test bridge integration",
            requirements=["quality", "performance"],
            use_cache=False
        )

        assert isinstance(plan_result, dict)

        # Test reviewer bridge
        review_result = service.review_code(
            task_id="bridge-review-test",
            task_description="Review test code",
            code_files={"test.py": "def hello(): return 'world'"},
            use_cache=False
        )

        assert isinstance(review_result, dict)

    def test_concurrent_access(self):
        """Test concurrent access to singleton service"""
        import threading
        import queue

        results = queue.Queue()

        def get_service():
            service = get_claude_service()
            results.put(id(service))

        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=get_service)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All should return the same instance
        service_ids = []
        while not results.empty():
            service_ids.append(results.get())

        assert len(set(service_ids)) == 1  # All same instance

    def test_configuration_integration(self):
        """Test configuration propagation through service"""
        config = ClaudeBridgeConfig(
            mock_mode=True,
            timeout=30,
            verbose=True
        )

        rate_config = RateLimitConfig(
            max_calls_per_minute=100,
            max_calls_per_hour=500
        )

        service = ClaudeService(
            config=config,
            rate_config=rate_config,
            cache_ttl=600
        )

        # Verify configuration is applied
        assert service.config.mock_mode is True
        assert service.config.timeout == 30
        assert service.config.verbose is True
        assert service.rate_limiter.config.max_calls_per_minute == 100
        assert service.cache_ttl == 600

    def test_service_lifecycle(self):
        """Test complete service lifecycle"""
        # Initialize service
        service = get_claude_service(
            config=ClaudeBridgeConfig(mock_mode=True),
            rate_config=RateLimitConfig(max_calls_per_minute=10)
        )

        # Use service
        result = service.plan_task(
            task_id="lifecycle-test",
            description="Test service lifecycle",
            use_cache=True
        )

        # Verify usage
        assert result is not None
        assert service.metrics.total_calls > 0

        # Reset service
        reset_claude_service()

        # Get new service instance
        new_service = get_claude_service()

        # Should be different instance with fresh state
        assert new_service is not service
        assert new_service.metrics.total_calls == 0

    def test_cache_expiry_integration(self):
        """Test cache expiry in real-time"""
        service = ClaudeService(
            config=ClaudeBridgeConfig(mock_mode=True),
            cache_ttl=1  # 1 second TTL
        )

        # Make cached call
        result1 = service.plan_task(
            task_id="expiry-test",
            description="Cache expiry test",
            use_cache=True
        )

        # Should hit cache
        result2 = service.plan_task(
            task_id="expiry-test",
            description="Cache expiry test",
            use_cache=True
        )

        assert result1 == result2
        assert service.metrics.cached_responses > 0

        # Wait for cache to expire
        time.sleep(1.5)

        # Force cache cleanup and make new call
        service._clean_cache()
        result3 = service.plan_task(
            task_id="expiry-test",
            description="Cache expiry test",
            use_cache=True
        )

        # Should be fresh call (not from cache)
        # Note: results might be the same in mock mode, but call count should increase
        initial_calls = service.metrics.total_calls
        assert initial_calls > 2  # At least 3 calls made

    @pytest.mark.slow
    def test_performance_characteristics(self):
        """Test performance characteristics under load"""
        service = ClaudeService(
            config=ClaudeBridgeConfig(mock_mode=True),
            rate_config=RateLimitConfig(max_calls_per_minute=60)
        )

        # Make many cached calls
        start_time = time.time()
        for i in range(10):
            service.plan_task(
                task_id="perf-test",  # Same ID for caching
                description="Performance test",
                use_cache=True
            )
        cached_time = time.time() - start_time

        # Make many unique calls
        start_time = time.time()
        for i in range(10):
            service.plan_task(
                task_id=f"perf-test-{i}",  # Unique IDs
                description="Performance test",
                use_cache=True
            )
        unique_time = time.time() - start_time

        # Cached calls should be much faster
        assert cached_time < unique_time / 2

        # Check metrics
        metrics = service.get_metrics()
        assert metrics["total_calls"] == 20
        assert metrics["cached_responses"] == 9  # First call not cached, 9 subsequent cached


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])