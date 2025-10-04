"""
Performance optimization for God Mode agents.

Provides:
- Embedding caching to reduce redundant API calls
- Web search result caching
- Batch processing for archival operations
- Circuit breaker for API failures
"""

from __future__ import annotations

import asyncio
import hashlib
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class EmbeddingCache:
    """
    LRU cache for embeddings to reduce redundant API calls.

    Caches embeddings with TTL and size limits for optimal memory usage.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """Initialize embedding cache.

        Args:
            max_size: Maximum number of cached embeddings (LRU eviction).
            ttl_seconds: Time-to-live for cached entries in seconds.
        """
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: OrderedDict[str, tuple[Any, datetime]] = OrderedDict()
        self._hits = 0
        self._misses = 0

        logger.info(f"Initialized EmbeddingCache (max_size={max_size}, ttl={ttl_seconds}s)")

    def _hash_content(self, content: str) -> str:
        """Generate cache key from content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, content: str) -> Any | None:
        """Get cached embedding if available and not expired.

        Args:
            content: Content to lookup embedding for.

        Returns:
            Cached embedding or None if not found/expired.
        """
        cache_key = self._hash_content(content)

        if cache_key not in self._cache:
            self._misses += 1
            return None

        embedding, cached_at = self._cache[cache_key]

        # Check if expired
        if datetime.now() - cached_at > self.ttl:
            del self._cache[cache_key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        self._hits += 1

        logger.debug(f"Embedding cache HIT (key={cache_key[:8]}...)")
        return embedding

    def put(self, content: str, embedding: Any) -> None:
        """Store embedding in cache.

        Args:
            content: Content that was embedded.
            embedding: The embedding vector.
        """
        cache_key = self._hash_content(content)

        # Evict oldest if at capacity
        if cache_key not in self._cache and len(self._cache) >= self.max_size:
            evicted_key = next(iter(self._cache))
            del self._cache[evicted_key]
            logger.debug(f"Evicted oldest cache entry: {evicted_key[:8]}...")

        self._cache[cache_key] = (embedding, datetime.now())
        self._cache.move_to_end(cache_key)

        logger.debug(f"Cached embedding (key={cache_key[:8]}...)")

    def clear(self) -> None:
        """Clear all cached embeddings."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Embedding cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with hits, misses, hit_rate, size.
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "max_size": self.max_size,
        }


class WebSearchCache:
    """
    Cache for web search results to reduce API calls.

    Caches search results with TTL for cost and latency optimization.
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 1800):
        """Initialize web search cache.

        Args:
            max_size: Maximum number of cached search results.
            ttl_seconds: Time-to-live for cached results (default 30 min).
        """
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: OrderedDict[str, tuple[list, datetime]] = OrderedDict()
        self._hits = 0
        self._misses = 0

        logger.info(f"Initialized WebSearchCache (max_size={max_size}, ttl={ttl_seconds}s)")

    def _generate_key(self, query: str, num_results: int) -> str:
        """Generate cache key from query parameters."""
        key_data = f"{query}|{num_results}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(self, query: str, num_results: int) -> list | None:
        """Get cached search results if available.

        Args:
            query: Search query.
            num_results: Number of results requested.

        Returns:
            Cached results or None if not found/expired.
        """
        cache_key = self._generate_key(query, num_results)

        if cache_key not in self._cache:
            self._misses += 1
            return None

        results, cached_at = self._cache[cache_key]

        # Check if expired
        if datetime.now() - cached_at > self.ttl:
            del self._cache[cache_key]
            self._misses += 1
            return None

        # Move to end (LRU)
        self._cache.move_to_end(cache_key)
        self._hits += 1

        logger.debug(f"Web search cache HIT for query: '{query[:50]}...'")
        return results

    def put(self, query: str, num_results: int, results: list) -> None:
        """Store search results in cache.

        Args:
            query: Search query.
            num_results: Number of results.
            results: Search results to cache.
        """
        cache_key = self._generate_key(query, num_results)

        # Evict oldest if at capacity
        if cache_key not in self._cache and len(self._cache) >= self.max_size:
            evicted_key = next(iter(self._cache))
            del self._cache[evicted_key]

        self._cache[cache_key] = (results, datetime.now())
        self._cache.move_to_end(cache_key)

        logger.debug(f"Cached web search results for: '{query[:50]}...'")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "max_size": self.max_size,
        }


class CircuitBreaker:
    """
    Circuit breaker pattern for API call protection.

    Prevents cascading failures by opening circuit after threshold failures.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
        half_open_attempts: int = 3,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit.
            recovery_timeout_seconds: Time to wait before attempting recovery.
            half_open_attempts: Number of test attempts in half-open state.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout_seconds)
        self.half_open_attempts = half_open_attempts

        self.state = "closed"  # closed, open, half_open
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None

        logger.info(
            f"Initialized CircuitBreaker "
            f"(threshold={failure_threshold}, timeout={recovery_timeout_seconds}s)"
        )

    def can_execute(self) -> bool:
        """Check if operation can be executed.

        Returns:
            True if circuit allows execution, False if open.
        """
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if recovery timeout elapsed
            if self.last_failure_time and datetime.now() - self.last_failure_time > self.recovery_timeout:
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                self.state = "half_open"
                self.success_count = 0
                return True
            return False

        if self.state == "half_open":
            return True

        return False

    def record_success(self) -> None:
        """Record successful operation."""
        if self.state == "half_open":
            self.success_count += 1
            if self.success_count >= self.half_open_attempts:
                logger.info("Circuit breaker transitioning to CLOSED (recovered)")
                self.state = "closed"
                self.failure_count = 0
                self.success_count = 0
        elif self.state == "closed":
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == "closed" and self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker OPENED after {self.failure_count} failures "
                f"(recovery in {self.recovery_timeout.total_seconds()}s)"
            )
            self.state = "open"

        elif self.state == "half_open":
            logger.warning("Circuit breaker returning to OPEN (recovery failed)")
            self.state = "open"
            self.success_count = 0

    def get_state(self) -> dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }


class BatchArchiver:
    """
    Batch processor for archival operations.

    Collects archival requests and processes them in batches for efficiency.
    """

    def __init__(self, batch_size: int = 10, flush_interval_seconds: float = 5.0):
        """Initialize batch archiver.

        Args:
            batch_size: Number of items to batch before processing.
            flush_interval_seconds: Max time to wait before auto-flushing.
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds

        self._queue: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._last_flush = datetime.now()

        logger.info(
            f"Initialized BatchArchiver "
            f"(batch_size={batch_size}, flush_interval={flush_interval_seconds}s)"
        )

    async def add(self, item: dict[str, Any]) -> None:
        """Add item to batch queue.

        Args:
            item: Archival item to queue.
        """
        async with self._lock:
            self._queue.append(item)

            # Auto-flush if batch size reached
            if len(self._queue) >= self.batch_size:
                await self._flush()

            # Auto-flush if interval elapsed
            elif (datetime.now() - self._last_flush).total_seconds() >= self.flush_interval:
                await self._flush()

    async def _flush(self) -> None:
        """Process all queued items."""
        if not self._queue:
            return

        batch = self._queue.copy()
        self._queue.clear()
        self._last_flush = datetime.now()

        logger.info(f"Flushing batch of {len(batch)} archival items")

        # Process batch (actual archival logic would go here)
        # For now, this is a placeholder for batch processing

    async def flush(self) -> None:
        """Manually flush the queue."""
        async with self._lock:
            await self._flush()

    def get_stats(self) -> dict[str, Any]:
        """Get batch archiver statistics."""
        return {
            "queue_size": len(self._queue),
            "batch_size": self.batch_size,
            "flush_interval": self.flush_interval,
            "last_flush": self._last_flush.isoformat(),
        }
