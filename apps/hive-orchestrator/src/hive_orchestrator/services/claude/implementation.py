"""
Claude Service Implementation
Contains the business logic implementation for Claude API interactions.
Separated from core interfaces to maintain clean architecture.
"""
from __future__ import annotations


import asyncio
import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Callable, Dict, List

from hive_config import get_config
from hive_errors import ErrorReporter
from hive_logging import get_logger

from ...core.claude.bridge import BaseClaludeBridge, ClaudeBridgeConfig
from ...core.claude.exceptions import ClaudeRateLimitError, ClaudeServiceError
from ...core.claude.planner_bridge import ClaudePlannerBridge
from ...core.claude.reviewer_bridge import ClaudeReviewerBridge

logger = get_logger(__name__)


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
            "total_calls": self.total_calls
            "successful_calls": self.successful_calls
            "failed_calls": self.failed_calls
            "cached_responses": self.cached_responses
            "total_tokens": self.total_tokens
            "average_latency_ms": self.average_latency_ms
            "success_rate": self.success_rate
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
    """Token bucket rate limiter implementation"""

    def __init__(self, config: RateLimitConfig) -> None:
        self.config = config
        self.minute_calls = deque()
        self.hour_calls = deque()
        self.tokens = config.burst_size
        self.last_refill = time.time()
        self.lock = Lock()

    def _clean_old_calls(self) -> None:
        """Remove calls outside the time windows"""
        now = time.time()

        # Clean minute window
        while self.minute_calls and self.minute_calls[0] < now - 60:
            self.minute_calls.popleft()

        # Clean hour window
        while self.hour_calls and self.hour_calls[0] < now - 3600:
            self.hour_calls.popleft()

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill

        if elapsed >= 1:  # Refill every second
            tokens_to_add = int(elapsed) * (self.config.burst_size / 60)
            self.tokens = min(self.config.burst_size, self.tokens + tokens_to_add)
            self.last_refill = now

    def can_make_request(self) -> bool:
        """Check if a request can be made within rate limits"""
        with self.lock:
            self._clean_old_calls()
            self._refill_tokens()

            # Check minute limit
            if len(self.minute_calls) >= self.config.max_calls_per_minute:
                return False

            # Check hour limit
            if len(self.hour_calls) >= self.config.max_calls_per_hour:
                return False

            # Check burst tokens
            if self.tokens < 1:
                return False

            return True

    def record_request(self) -> None:
        """Record a request being made"""
        with self.lock:
            now = time.time()
            self.minute_calls.append(now)
            self.hour_calls.append(now)
            self.tokens = max(0, self.tokens - 1)

    def get_wait_time(self) -> float:
        """Get the wait time until next request can be made"""
        with self.lock:
            self._clean_old_calls()

            # If under all limits, no wait
            if self.can_make_request():
                return 0.0

            # Calculate wait based on minute window
            if len(self.minute_calls) >= self.config.max_calls_per_minute:
                oldest_minute_call = self.minute_calls[0]
                wait = 60 - (time.time() - oldest_minute_call)
                return max(0, wait)

            # Calculate wait based on hour window
            if len(self.hour_calls) >= self.config.max_calls_per_hour:
                oldest_hour_call = self.hour_calls[0]
                wait = 3600 - (time.time() - oldest_hour_call)
                return max(0, wait)

            # Wait for token refill
            return 1.0  # Wait 1 second for token refill


class ResponseCache:
    """Cache for Claude API responses"""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.cache: Dict[str, CacheEntry] = {}
        self.ttl_seconds = ttl_seconds
        self.lock = Lock()

    def _generate_key(self, prompt: str, **kwargs) -> str:
        """Generate cache key from prompt and parameters"""
        cache_data = {"prompt": prompt, **kwargs}
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()

    def get(self, prompt: str, **kwargs) -> Any | None:
        """Get cached response if available and not expired"""
        key = self._generate_key(prompt, **kwargs)

        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if not entry.is_expired(self.ttl_seconds):
                    entry.hit_count += 1
                    logger.debug(f"Cache hit for key {key[:8]}... (hits: {entry.hit_count})")
                    return entry.response
                else:
                    # Remove expired entry
                    del self.cache[key]
                    logger.debug(f"Cache expired for key {key[:8]}...")

        return None

    def set(self, prompt: str, response: Any, **kwargs) -> None:
        """Cache a response"""
        key = self._generate_key(prompt, **kwargs)

        with self.lock:
            self.cache[key] = CacheEntry(response=response, timestamp=datetime.now(), hit_count=0)
            logger.debug(f"Cached response for key {key[:8]}...")

    def clear(self) -> None:
        """Clear all cached responses"""
        with self.lock:
            self.cache.clear()
            logger.info("Response cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_entries = len(self.cache)
            total_hits = sum(entry.hit_count for entry in self.cache.values())
            expired = sum(1 for entry in self.cache.values() if entry.is_expired(self.ttl_seconds))

        return {
            "total_entries": total_entries
            "total_hits": total_hits
            "expired_entries": expired
            "hit_rate": total_hits / max(1, total_entries + total_hits)
        }


# Note: The actual ClaudeService class would be moved here from claude_service.py
# but keeping it there for now to avoid breaking imports. In a full refactor
# we would:
# 1. Move the ClaudeService implementation here
# 2. Create an abstract ClaudeServiceInterface in core/claude/interfaces.py
# 3. Update all imports to use the implementation from this file
