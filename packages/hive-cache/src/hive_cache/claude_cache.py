"""Specialized caching for Claude API responses with intelligent TTL management."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from typing import Any

from hive_logging import get_logger

from .cache_client import HiveCacheClient, get_cache_client
from .config import CacheConfig

logger = get_logger(__name__)


class ClaudeAPICache:
    """

        Specialized cache for Claude API responses with intelligent TTL and optimization.

        Features:
        - Smart cache key generation from prompts and parameters
        - Response-size-aware TTL management
        - Claude model-specific caching strategies
        - Automatic cache warming for common prompts
        - Response compression for large outputs
    """

    def __init__(self, cache_client: HiveCacheClient, config: CacheConfig) -> None:
        self.cache_client = cache_client
        self.config = config
        self.namespace = config.claude_cache_namespace

        # Cache statistics specific to Claude API
        self.claude_metrics = {
            "api_calls_saved": 0,
            "total_cache_checks": 0,
            "cache_hit_rate": 0.0,
            "total_response_size_cached": 0,
            "largest_response_cached": 0,
        }

    @classmethod
    async def create_async(cls, config: CacheConfig | None = None) -> ClaudeAPICache:
        """Create Claude API cache instance.

        Args:
            config: Optional cache configuration

        Returns:
            ClaudeAPICache instance
        """
        cache_client = await get_cache_client(config)
        if config is None:
            config = CacheConfig.from_env()

        return cls(cache_client, config)

    def _generate_cache_key(
        self,
        prompt: str,
        model: str = "claude-3-opus",
        max_tokens: int | None = None,
        temperature: float = 0.0,
        system: str | None = None,
        **kwargs,
    ) -> str:
        """Generate consistent cache key for Claude API parameters.

        Args:
            prompt: User prompt,
            model: Claude model name,
            max_tokens: Maximum tokens for response,
            temperature: Sampling temperature,
            system: System prompt,
            **kwargs: Additional parameters

        Returns:
            Cache key string
        """
        # Create a normalized parameter dictionary
        cache_params = {
            "model": model,
            "prompt": prompt.strip(),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system.strip() if system else None,
        }

        # Add other significant parameters
        for key, value in kwargs.items():
            if key in ["top_p", "top_k", "stop_sequences", "metadata"]:
                cache_params[key] = value

        # Sort parameters for consistent hashing
        param_str = str(sorted(cache_params.items()))

        # Generate hash
        cache_hash = hashlib.sha256(param_str.encode()).hexdigest()[:32]

        return f"claude_api_{model}_{cache_hash}"

    def _calculate_response_ttl(self, response: dict[str, Any], base_ttl: int | None = None) -> int:
        """Calculate intelligent TTL based on response characteristics.

        Args:
            response: Claude API response
            base_ttl: Base TTL to adjust

        Returns:
            Calculated TTL in seconds
        """
        if base_ttl is None:
            base_ttl = self.config.claude_default_ttl

        # Response size factor (larger responses cached longer)
        response_text = response.get("content", [{}])[0].get("text", "")
        response_size = (len(response_text),)

        size_factor = 1.0
        if response_size > 10000:  # Large responses
            size_factor = 2.0
        elif response_size > 5000:  # Medium responses
            size_factor = 1.5
        elif response_size < 500:  # Small responses
            size_factor = 0.5

        # Model factor (more expensive models cached longer)
        model_factors = {
            "claude-3-opus": 2.0,  # Most expensive,
            "claude-3-sonnet": 1.5,  # Medium cost,
            "claude-3-haiku": 1.0,  # Least expensive
        }

        model = response.get("model", "claude-3-opus")
        model_factor = model_factors.get(model, 1.0)

        # Calculate final TTL
        calculated_ttl = int(base_ttl * size_factor * model_factor)

        # Clamp to configured limits
        return max(self.config.min_ttl, min(calculated_ttl, self.config.max_ttl))

    def _should_cache_response(self, response: dict[str, Any]) -> bool:
        """Determine if response should be cached based on size and content.

        Args:
            response: Claude API response

        Returns:
            True if response should be cached
        """
        # Check response size
        response_text = response.get("content", [{}])[0].get("text", "")
        response_size = len(response_text.encode("utf-8"))

        if response_size > self.config.claude_max_response_size:
            logger.info(f"Response too large to cache: {response_size} bytes")
            return False

        # Check for error responses
        if "error" in response:
            logger.info("Not caching error response")
            return False

        # Check for incomplete responses
        finish_reason = response.get("stop_reason")
        if finish_reason == "max_tokens":
            logger.info("Not caching truncated response")
            return False

        return True

    async def get_cached_response_async(
        self,
        prompt: str,
        model: str = "claude-3-opus",
        max_tokens: int | None = None,
        temperature: float = 0.0,
        system: str | None = None,
        **kwargs,
    ) -> Optional[dict[str, Any]]:
        """Get cached Claude API response if available.

        Args:
            prompt: User prompt,
            model: Claude model name,
            max_tokens: Maximum tokens for response,
            temperature: Sampling temperature,
            system: System prompt,
            **kwargs: Additional parameters

        Returns:
            Cached response or None if not found
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(prompt, model, max_tokens, temperature, system, **kwargs)

            # Check cache
            self.claude_metrics["total_cache_checks"] += (1,)
            cached_response = await self.cache_client.get(cache_key, self.namespace)

            if cached_response is not None:
                self.claude_metrics["api_calls_saved"] += 1
                logger.info(f"Cache hit for Claude API call: {cache_key}")

                # Update hit rate
                self.claude_metrics["cache_hit_rate"] = (
                    self.claude_metrics["api_calls_saved"] / self.claude_metrics["total_cache_checks"]
                )

                return cached_response

            return None

        except Exception as e:
            (logger.warning(f"Failed to get cached Claude response: {e}"),)
            return None

    async def cache_response_async(
        self,
        prompt: str,
        response: dict[str, Any],
        model: str = "claude-3-opus",
        max_tokens: int | None = None,
        temperature: float = 0.0,
        system: str | None = None,
        ttl: int | None = None,
        **kwargs,
    ) -> bool:
        """Cache Claude API response.

        Args:
            prompt: User prompt,
            response: Claude API response,
            model: Claude model name,
            max_tokens: Maximum tokens for response,
            temperature: Sampling temperature,
            system: System prompt,
            ttl: Custom TTL (uses intelligent calculation if None),
            **kwargs: Additional parameters

        Returns:
            True if response was cached successfully
        """
        try:
            # Check if response should be cached
            if not self._should_cache_response(response):
                return False

            # Generate cache key
            cache_key = self._generate_cache_key(prompt, model, max_tokens, temperature, system, **kwargs)

            # Calculate TTL
            if ttl is None:
                ttl = self._calculate_response_ttl(response)

            # Add caching metadata
            cached_response = {
                **response,
                "_cache_metadata": {"cached_at": time.time(), "ttl": ttl, "cache_key": cache_key},
            }

            # Cache the response
            success = await self.cache_client.set(cache_key, cached_response, ttl, self.namespace)

            if success:
                # Update metrics
                response_text = response.get("content", [{}])[0].get("text", "")
                response_size = len(response_text.encode("utf-8"))
                self.claude_metrics["total_response_size_cached"] += response_size
                self.claude_metrics["largest_response_cached"] = max(
                    self.claude_metrics["largest_response_cached"],
                    response_size,
                )

                logger.info(f"Cached Claude API response: {cache_key} (TTL: {ttl}s, Size: {response_size} bytes)")

            return success

        except Exception as e:
            (logger.error(f"Failed to cache Claude response: {e}"),)
            return False

    async def get_or_fetch_async(
        self,
        prompt: str,
        fetcher: Callable,
        model: str = "claude-3-opus",
        max_tokens: int | None = None,
        temperature: float = 0.0,
        system: str | None = None,
        cache_ttl: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Get cached response or fetch from Claude API if not cached.

        Args:
            prompt: User prompt,
            fetcher: Async function to fetch from Claude API,
            model: Claude model name,
            max_tokens: Maximum tokens for response,
            temperature: Sampling temperature,
            system: System prompt,
            cache_ttl: Custom cache TTL,
            **kwargs: Additional parameters

        Returns:
            Claude API response (cached or fresh)
        """
        # Try cache first
        cached_response = await self.get_cached_response_async(prompt, model, max_tokens, temperature, system, **kwargs)

        if cached_response is not None:
            return cached_response

        # Fetch from API
        if callable(fetcher):
            if hasattr(fetcher, "__code__") and fetcher.__code__.co_flags & 0x80:  # async function,
                response = await fetcher()
            else:
                response = fetcher()
        else:
            raise ValueError("Fetcher must be callable")

        # Cache the response
        await self.cache_response_async(prompt, response, model, max_tokens, temperature, system, cache_ttl, **kwargs)

        return response

    async def warm_cache_async(self, common_prompts: list[dict[str, Any]]) -> dict[str, bool]:
        """Pre-warm cache with common prompts.

        Args:
            common_prompts: List of prompt dictionaries with parameters

        Returns:
            Dictionary mapping prompt keys to cache success status
        """
        results = {}

        for prompt_config in common_prompts:
            prompt = prompt_config.get("prompt")
            if not prompt:
                continue

            try:
                # Check if already cached
                cached = await self.get_cached_response_async(**prompt_config)
                if cached:
                    results[prompt[:50] + "..."] = True
                    continue

                # Would need to implement actual API call here for warming
                logger.info(f"Cache warming would require API call for: {prompt[:50]}...")
                results[prompt[:50] + "..."] = False

            except Exception as e:
                logger.error(f"Failed to warm cache for prompt: {e}")
                results[prompt[:50] + "..."] = False

        return results

    async def invalidate_by_pattern_async(self, pattern: str = "*") -> int:
        """Invalidate cached responses matching a pattern.

        Args:
            pattern: Key pattern to match

        Returns:
            Number of keys invalidated
        """
        try:
            return await self.cache_client.delete_pattern(pattern, self.namespace)
        except Exception as e:
            logger.error(f"Failed to invalidate cache pattern: {e}")
            return 0

    async def get_cache_stats_async(self) -> dict[str, Any]:
        """Get Claude-specific cache statistics.

        Returns:
            Cache statistics dictionary
        """
        # Get general cache metrics
        general_metrics = self.cache_client.get_metrics()

        # Combine with Claude-specific metrics
        return {
            **self.claude_metrics,
            "general_cache_metrics": general_metrics,
            "namespace": self.namespace,
            "config": {
                "default_ttl": self.config.claude_default_ttl,
                "max_response_size": self.config.claude_max_response_size,
            },
        }

    async def cleanup_expired_async(self) -> int:
        """Clean up expired cache entries (Redis handles this automatically).

        Returns:
            Number of keys cleaned (0 since Redis auto-expires)
        """
        # Redis automatically handles TTL expiration
        # This method exists for interface compatibility
        logger.info("Redis automatically handles TTL expiration")
        return 0
