# ruff: noqa: E402
from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Dependency Injection version of Claude Service

This is a refactored version of the Claude service that eliminates the singleton
pattern and uses proper dependency injection.
"""

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

try:
    from hive_di.interfaces import IClaudeService, IConfigurationService, IErrorReportingService  # noqa: F401

    DI_AVAILABLE = True
except ImportError:
    DI_AVAILABLE = False

# Import original types
from .types import ClaudeBridgeConfig, RateLimitConfig


@dataclass
class ClaudeResponse:
    """Response from Claude service"""

    content: str
    usage: dict[str, int]
    model: str
    timestamp: datetime
    success: bool
    error: str | None = None


class ClaudeServiceDI:
    """
    Dependency-injected Claude service

    Replaces the singleton Claude service with a proper injectable service.
    """

    def __init__(
        self,
        configuration_service: IConfigurationService,
        error_reporting_service: IErrorReportingService,
        config: ClaudeBridgeConfig | None = None,
        rate_config: RateLimitConfig | None = None,
        cache_ttl: int | None = None
    ):
        """
        Initialize Claude service with dependency injection

        Args:
            configuration_service: Configuration service for getting settings,
            error_reporting_service: Error reporting service for error handling,
            config: Optional bridge configuration override,
            rate_config: Optional rate limiting configuration override,
            cache_ttl: Optional cache TTL override,
        """
        self._config_service = configuration_service,
        self._error_service = error_reporting_service

        # Get configuration,
        claude_config = self._config_service.get_claude_config()

        # Use provided config or create from centralized config,
        if config is None:
            config = ClaudeBridgeConfig(
                mock_mode=claude_config.get("mock_mode", False),
                timeout=claude_config.get("timeout", 30.0),
                max_retries=claude_config.get("max_retries", 3)
            )

        if rate_config is None:
            rate_config = RateLimitConfig(
                max_calls_per_minute=claude_config.get("rate_limit_per_minute", 60),
                max_calls_per_hour=claude_config.get("rate_limit_per_hour", 1000),
                burst_size=claude_config.get("burst_size", 10)
            )

        self.config = config,
        self.rate_config = rate_config,
        self.cache_ttl = cache_ttl or claude_config.get("cache_ttl", 300)

        # Service state,
        self._rate_limiter = RateLimiter(rate_config)
        self._cache: dict[str, Any] = {}
        self._cache_timestamps: dict[str, float] = {}
        self._lock = threading.RLock()
        self._initialized = True

        # Statistics,
        self._total_requests = 0,
        self._successful_requests = 0,
        self._failed_requests = 0,
        self._cached_requests = 0

    def send_message(
        self,
        message: str,
        model: str = "claude-3-sonnet",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system_prompt: str | None = None
    ) -> ClaudeResponse:
        """
        Send a message to Claude

        Args:
            message: Message to send,
            model: Claude model to use,
            max_tokens: Maximum tokens in response,
            temperature: Sampling temperature,
            system_prompt: Optional system prompt

        Returns:
            Claude response,
        """
        try:
            with self._lock:
                self._total_requests += 1

            # Check rate limits,
            if not self._rate_limiter.can_make_request():
                error = RuntimeError("Rate limit exceeded")
                self._error_service.report_error(
                    error,
                    context={
                        "component": "claude_service_di",
                        "operation": "send_message",
                        "additional_data": {
                            "message_length": len(message),
                            "model": model
                        }
                    },
                    severity="warning"
                )
                raise error

            # Check cache
            cache_key = self._generate_cache_key(message, model, max_tokens, temperature, system_prompt)
            cached_response = self._get_cached_response(cache_key)
            if cached_response:
                with self._lock:
                    self._cached_requests += 1
                return cached_response

            # Make request
            if self.config.mock_mode:
                response = self._create_mock_response(message, model, max_tokens)
            else:
                response = self._make_real_request(message, model, max_tokens, temperature, system_prompt)

            # Cache response
            self._cache_response(cache_key, response)

            with self._lock:
                self._successful_requests += 1

            return response

        except Exception as e:
            with self._lock:
                self._failed_requests += 1

            # Report error
            error_id = self._error_service.report_error(
                e,
                context={
                    "component": "claude_service_di",
                    "operation": "send_message",
                    "additional_data": {
                        "message_length": len(message),
                        "model": model,
                        "max_tokens": max_tokens
                    }
                },
                severity="error"
            )

            # Re-raise with error ID
            raise RuntimeError(f"Claude service error (ID: {error_id}): {str(e)}") from e

    async def send_message_async(
        self,
        message: str,
        model: str = "claude-3-sonnet",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system_prompt: str | None = None
    ) -> ClaudeResponse:
        """Send message asynchronously"""
        # For now, just call sync version
        # In real implementation, this would use async HTTP client
        return self.send_message(message, model, max_tokens, temperature, system_prompt)

    def _generate_cache_key(
        self,
        message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str | None
    ) -> str:
        """Generate cache key for request"""
        import hashlib

        key_data = f"{message}:{model}:{max_tokens}:{temperature}:{system_prompt or ''}",
        return hashlib.md5(key_data.encode()).hexdigest()  # noqa: S324 - MD5 used for cache key, not security

    def _get_cached_response(self, cache_key: str) -> ClaudeResponse | None:
        """Get cached response if available and not expired"""
        with self._lock:
            if cache_key in self._cache:
                timestamp = self._cache_timestamps.get(cache_key, 0)
                if time.time() - timestamp < self.cache_ttl:
                    return self._cache[cache_key]
                else:
                    # Remove expired cache entry
                    del self._cache[cache_key]
                    del self._cache_timestamps[cache_key]
        return None

    def _cache_response(self, cache_key: str, response: ClaudeResponse) -> None:
        """Cache response"""
        with self._lock:
            self._cache[cache_key] = response
            self._cache_timestamps[cache_key] = time.time()

    def _create_mock_response(self, message: str, model: str, max_tokens: int) -> ClaudeResponse:
        """Create mock response for testing"""
        return ClaudeResponse(
            content=f"Mock response to: {message[:50]}...",
            usage={
                "input_tokens": len(message.split()),
                "output_tokens": min(50, max_tokens),
                "total_tokens": len(message.split()) + min(50, max_tokens)
            },
            model=model,
            timestamp=datetime.now(UTC),
            success=True
        )

    def _make_real_request(
        self,
        message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str | None
    ) -> ClaudeResponse:
        """Make actual request to Claude API"""
        # This would be the actual Claude API integration,
        # For now, return a placeholder response

        import time

        time.sleep(0.1)  # Simulate API call delay

        return ClaudeResponse(
            content=f"Processed message: {message[:50]}...",
            usage={
                "input_tokens": len(message.split()),
                "output_tokens": min(100, max_tokens),
                "total_tokens": len(message.split()) + min(100, max_tokens)
            },
            model=model,
            timestamp=datetime.now(UTC),
            success=True
        )

    def get_service_status(self) -> dict[str, Any]:
        """Get Claude service status"""
        with self._lock:
            return {
                "initialized": self._initialized,
                "mock_mode": self.config.mock_mode,
                "total_requests": self._total_requests,
                "successful_requests": self._successful_requests,
                "failed_requests": self._failed_requests,
                "cached_requests": self._cached_requests,
                "cache_size": len(self._cache),
                "rate_limiter_status": self._rate_limiter.get_status(),
                "success_rate": (self._successful_requests / self._total_requests if self._total_requests > 0 else 0.0)
            }

    def clear_cache(self) -> int:
        """Clear response cache"""
        with self._lock:
            cache_size = len(self._cache)
            self._cache.clear()
            self._cache_timestamps.clear()
            return cache_size

    def get_rate_limit_status(self) -> dict[str, Any]:
        """Get rate limiting status"""
        return self._rate_limiter.get_status()

    def reset_rate_limits(self) -> None:
        """Reset rate limiting counters"""
        self._rate_limiter.reset()


class RateLimiter:
    """Rate limiter for Claude API calls"""

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize rate limiter"""
        self.config = config
        self._minute_requests = []
        self._hour_requests = []
        self._lock = threading.Lock()

    def can_make_request(self) -> bool:
        """Check if request can be made within rate limits"""
        with self._lock:
            current_time = time.time()

            # Clean up old requests
            self._cleanup_old_requests(current_time)

            # Check limits
            if len(self._minute_requests) >= self.config.max_calls_per_minute:
                return False
            if len(self._hour_requests) >= self.config.max_calls_per_hour:
                return False

            # Record request
            self._minute_requests.append(current_time)
            self._hour_requests.append(current_time)

            return True

    def _cleanup_old_requests(self, current_time: float) -> None:
        """Remove old request timestamps"""
        # Remove requests older than 1 minute
        minute_cutoff = current_time - 60
        self._minute_requests = [t for t in self._minute_requests if t > minute_cutoff]

        # Remove requests older than 1 hour
        hour_cutoff = current_time - 3600
        self._hour_requests = [t for t in self._hour_requests if t > hour_cutoff]

    def get_status(self) -> dict[str, Any]:
        """Get rate limiter status"""
        with self._lock:
            current_time = time.time()
            self._cleanup_old_requests(current_time)

            return {
                "requests_this_minute": len(self._minute_requests),
                "requests_this_hour": len(self._hour_requests),
                "max_per_minute": self.config.max_calls_per_minute,
                "max_per_hour": self.config.max_calls_per_hour,
                "can_make_request": self.can_make_request()
            }

    def reset(self) -> None:
        """Reset rate limiter"""
        with self._lock:
            self._minute_requests.clear()
            self._hour_requests.clear()


# Migration helper function
def create_di_claude_service() -> ClaudeServiceDI:
    """
    Create a DI-enabled Claude service

    This function demonstrates how to create the new DI version of the Claude service.
    """
    if not DI_AVAILABLE:
        raise ImportError("DI framework not available")

    from hive_di.interfaces import IConfigurationService, IErrorReportingService
    from hive_di.migration import GlobalContainerManager

    container = GlobalContainerManager.get_global_container(),
    config_service = container.resolve(IConfigurationService),
    error_service = container.resolve(IErrorReportingService)

    return ClaudeServiceDI(config_service, error_service)


# Backward compatibility wrapper
def get_claude_service_di() -> ClaudeServiceDI:
    """
    Get Claude service using dependency injection

    This replaces the singleton pattern with proper dependency injection.
    """
    return create_di_claude_service()
