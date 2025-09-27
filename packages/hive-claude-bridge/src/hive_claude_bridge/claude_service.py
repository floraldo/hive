"""
Centralized Claude Service
Manages all Claude API interactions with rate limiting, caching, and monitoring
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from collections import deque
from threading import Lock
import logging

from .bridge import BaseClaludeBridge, ClaudeBridgeConfig
from .planner_bridge import ClaudePlannerBridge
from .reviewer_bridge import ClaudeReviewerBridge
from .exceptions import ClaudeRateLimitError, ClaudeServiceError
from hive_errors import ErrorReporter
from hive_db_utils.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ClaudeMetrics:
    """Metrics for Claude API usage"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    cached_responses: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    rate_limited: int = 0

    @property
    def average_latency_ms(self) -> float:
        """Calculate average latency"""
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "cached_responses": self.cached_responses,
            "total_tokens": self.total_tokens,
            "average_latency_ms": self.average_latency_ms,
            "success_rate": self.success_rate,
            "rate_limited": self.rate_limited
        }


@dataclass
class CacheEntry:
    """Cache entry for Claude responses"""
    response: Any
    timestamp: datetime
    hit_count: int = 0

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if cache entry is expired"""
        age = datetime.now() - self.timestamp
        return age.total_seconds() > ttl_seconds


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    max_calls_per_minute: int = 30
    max_calls_per_hour: int = 1000
    burst_size: int = 5
    cooldown_seconds: int = 60


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.minute_calls = deque()
        self.hour_calls = deque()
        self.tokens = config.burst_size
        self.last_refill = time.time()
        self.lock = Lock()

    def can_proceed(self) -> bool:
        """Check if request can proceed"""
        with self.lock:
            now = time.time()

            # Clean old timestamps
            minute_ago = now - 60
            hour_ago = now - 3600

            while self.minute_calls and self.minute_calls[0] < minute_ago:
                self.minute_calls.popleft()

            while self.hour_calls and self.hour_calls[0] < hour_ago:
                self.hour_calls.popleft()

            # Check limits
            if len(self.minute_calls) >= self.config.max_calls_per_minute:
                return False

            if len(self.hour_calls) >= self.config.max_calls_per_hour:
                return False

            # Refill tokens
            time_since_refill = now - self.last_refill
            tokens_to_add = int(time_since_refill * (self.config.burst_size / 60))
            if tokens_to_add > 0:
                self.tokens = min(self.config.burst_size, self.tokens + tokens_to_add)
                self.last_refill = now

            # Check if we have tokens
            if self.tokens <= 0:
                return False

            # Consume token and record call
            self.tokens -= 1
            self.minute_calls.append(now)
            self.hour_calls.append(now)

            return True

    def get_wait_time(self) -> float:
        """Get time to wait before next request can proceed"""
        with self.lock:
            if not self.minute_calls:
                return 0.0

            oldest_minute_call = self.minute_calls[0]
            wait_time = 60 - (time.time() - oldest_minute_call)

            return max(0.0, wait_time)


class ClaudeService:
    """
    Centralized service for all Claude API interactions

    Features:
    - Rate limiting to prevent API throttling
    - Response caching to reduce redundant calls
    - Metrics collection for monitoring
    - Unified error handling
    - Async/sync operation support
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        """Ensure singleton instance"""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        config: Optional[ClaudeBridgeConfig] = None,
        rate_config: Optional[RateLimitConfig] = None,
        cache_ttl: Optional[int] = None
    ):
        """Initialize Claude service

        Args:
            config: Bridge configuration (defaults to centralized config)
            rate_config: Rate limiting configuration (defaults to centralized config)
            cache_ttl: Cache TTL in seconds (defaults to centralized config)
        """
        # Only initialize once
        if hasattr(self, '_initialized'):
            return

        # Get centralized configuration
        global_config = get_config()
        claude_config = global_config.get_claude_config()

        # Use centralized config with overrides
        if config is None:
            config = ClaudeBridgeConfig(
                mock_mode=claude_config["mock_mode"],
                timeout=claude_config["timeout"],
                max_retries=claude_config["max_retries"]
            )

        if rate_config is None:
            rate_config = RateLimitConfig(
                max_calls_per_minute=claude_config["rate_limit_per_minute"],
                max_calls_per_hour=claude_config["rate_limit_per_hour"],
                burst_size=claude_config["burst_size"]
            )

        self.config = config
        self.rate_limiter = RateLimiter(rate_config)
        self.cache: Dict[str, CacheEntry] = {}
        self.cache_ttl = cache_ttl if cache_ttl is not None else claude_config["cache_ttl"]
        self.metrics = ClaudeMetrics()
        self.error_reporter = ErrorReporter()

        # Initialize bridges
        self.planner_bridge = ClaudePlannerBridge(config=self.config)
        self.reviewer_bridge = ClaudeReviewerBridge(config=self.config)

        # Callback hooks for monitoring
        self.pre_call_hooks: List[Callable] = []
        self.post_call_hooks: List[Callable] = []

        self._initialized = True

        logger.info("Claude Service initialized with rate limiting and caching")

    def _generate_cache_key(self, operation: str, **kwargs) -> str:
        """Generate cache key for request"""
        # Create deterministic key from operation and parameters
        key_data = {
            "operation": operation,
            **kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        """Get response from cache if available"""
        if cache_key in self.cache:
            entry = self.cache[cache_key]

            if not entry.is_expired(self.cache_ttl):
                entry.hit_count += 1
                self.metrics.cached_responses += 1
                logger.debug(f"Cache hit for key {cache_key[:8]}... (hits: {entry.hit_count})")
                return entry.response
            else:
                # Remove expired entry
                del self.cache[cache_key]

        return None

    def _cache_response(self, cache_key: str, response: Any):
        """Cache response"""
        self.cache[cache_key] = CacheEntry(
            response=response,
            timestamp=datetime.now()
        )

        # Limit cache size
        if len(self.cache) > 100:
            # Remove oldest entries
            sorted_keys = sorted(
                self.cache.keys(),
                key=lambda k: self.cache[k].timestamp
            )
            for key in sorted_keys[:20]:
                del self.cache[key]

    def _wait_for_rate_limit(self) -> bool:
        """Wait for rate limit if necessary

        Returns:
            True if can proceed, False if should abort
        """
        max_wait = 120  # Maximum 2 minutes wait
        start_time = time.time()

        while not self.rate_limiter.can_proceed():
            wait_time = self.rate_limiter.get_wait_time()

            if time.time() - start_time + wait_time > max_wait:
                logger.warning("Rate limit wait time exceeded maximum")
                return False

            if wait_time > 0:
                logger.info(f"Rate limited, waiting {wait_time:.1f} seconds")
                time.sleep(min(wait_time, 1.0))
                self.metrics.rate_limited += 1

        return True

    def _execute_with_metrics(
        self,
        operation: str,
        func: Callable,
        use_cache: bool = True,
        **kwargs
    ) -> Any:
        """Execute operation with metrics tracking

        Args:
            operation: Operation name for metrics
            func: Function to execute
            use_cache: Whether to use caching
            **kwargs: Arguments for the function

        Returns:
            Operation result
        """
        # Generate cache key
        cache_key = self._generate_cache_key(operation, **kwargs) if use_cache else None

        # Check cache
        if use_cache:
            cached = self._get_cached_response(cache_key)
            if cached is not None:
                return cached

        # Wait for rate limit
        if not self._wait_for_rate_limit():
            raise ClaudeRateLimitError("Rate limit exceeded")

        # Execute pre-call hooks
        for hook in self.pre_call_hooks:
            try:
                hook(operation, kwargs)
            except Exception as e:
                logger.warning(f"Pre-call hook failed: {e}")

        # Track metrics
        start_time = time.time()
        self.metrics.total_calls += 1

        try:
            # Execute operation
            result = func(**kwargs)

            # Update metrics
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.successful_calls += 1
            self.metrics.total_latency_ms += elapsed_ms

            # Cache result
            if use_cache and cache_key:
                self._cache_response(cache_key, result)

            # Execute post-call hooks
            for hook in self.post_call_hooks:
                try:
                    hook(operation, kwargs, result, elapsed_ms)
                except Exception as e:
                    logger.warning(f"Post-call hook failed: {e}")

            logger.info(f"Claude {operation} completed in {elapsed_ms:.0f}ms")
            return result

        except Exception as e:
            self.metrics.failed_calls += 1

            error = ClaudeServiceError(
                message=f"Claude operation {operation} failed",
                operation=operation,
                original_error=e
            )
            self.error_reporter.report_error(error)

            # Execute post-call hooks with error
            for hook in self.post_call_hooks:
                try:
                    hook(operation, kwargs, None, 0, error=e)
                except Exception as hook_error:
                    logger.warning(f"Post-call hook failed: {hook_error}")

            raise

    # Planning Operations

    def generate_execution_plan(
        self,
        task_description: str,
        context_data: Optional[Dict[str, Any]] = None,
        priority: int = 1,
        requestor: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Generate execution plan for a task

        Args:
            task_description: Description of the task
            context_data: Additional context
            priority: Task priority
            requestor: Who requested the task
            use_cache: Whether to use caching

        Returns:
            Execution plan dictionary
        """
        return self._execute_with_metrics(
            "generate_plan",
            self.planner_bridge.generate_execution_plan,
            use_cache=use_cache,
            task_description=task_description,
            context_data=context_data or {},
            priority=priority,
            requestor=requestor
        )

    # Review Operations

    def review_code(
        self,
        task_id: str,
        task_description: str,
        code_files: Dict[str, str],
        test_results: Optional[Dict[str, Any]] = None,
        objective_analysis: Optional[Dict[str, Any]] = None,
        transcript: Optional[str] = None,
        use_cache: bool = False  # Don't cache reviews by default
    ) -> Dict[str, Any]:
        """Review code implementation

        Args:
            task_id: Task identifier
            task_description: What the task was supposed to do
            code_files: Dictionary of filename -> content
            test_results: Test execution results
            objective_analysis: Static analysis results
            transcript: Claude conversation transcript
            use_cache: Whether to use caching

        Returns:
            Review result dictionary
        """
        return self._execute_with_metrics(
            "review_code",
            self.reviewer_bridge.review_code,
            use_cache=use_cache,
            task_id=task_id,
            task_description=task_description,
            code_files=code_files,
            test_results=test_results,
            objective_analysis=objective_analysis,
            transcript=transcript
        )

    # Async Support

    async def generate_execution_plan_async(
        self,
        task_description: str,
        context_data: Optional[Dict[str, Any]] = None,
        priority: int = 1,
        requestor: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Async version of generate_execution_plan"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.generate_execution_plan,
            task_description,
            context_data,
            priority,
            requestor,
            use_cache
        )

    async def review_code_async(
        self,
        task_id: str,
        task_description: str,
        code_files: Dict[str, str],
        test_results: Optional[Dict[str, Any]] = None,
        objective_analysis: Optional[Dict[str, Any]] = None,
        transcript: Optional[str] = None,
        use_cache: bool = False
    ) -> Dict[str, Any]:
        """Async version of review_code"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.review_code,
            task_id,
            task_description,
            code_files,
            test_results,
            objective_analysis,
            transcript,
            use_cache
        )

    # Monitoring and Management

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics"""
        return self.metrics.to_dict()

    def clear_cache(self):
        """Clear response cache"""
        self.cache.clear()
        logger.info("Claude service cache cleared")

    def reset_metrics(self):
        """Reset metrics"""
        self.metrics = ClaudeMetrics()
        logger.info("Claude service metrics reset")

    def add_pre_call_hook(self, hook: Callable):
        """Add pre-call hook for monitoring"""
        self.pre_call_hooks.append(hook)

    def add_post_call_hook(self, hook: Callable):
        """Add post-call hook for monitoring"""
        self.post_call_hooks.append(hook)


# Global service instance
_service: Optional[ClaudeService] = None


def get_claude_service(
    config: Optional[ClaudeBridgeConfig] = None,
    rate_config: Optional[RateLimitConfig] = None
) -> ClaudeService:
    """Get or create the global Claude service

    Args:
        config: Bridge configuration
        rate_config: Rate limiting configuration

    Returns:
        ClaudeService singleton instance
    """
    global _service
    if _service is None:
        _service = ClaudeService(config=config, rate_config=rate_config)
    return _service


def reset_claude_service():
    """Reset the global Claude service"""
    global _service
    _service = None