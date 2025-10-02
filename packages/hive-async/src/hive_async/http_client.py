"""
Resilient HTTP client with circuit breaker protection.

Provides HTTP client wrapper with built-in circuit breaker, retry logic,
and timeout management for external API calls.
"""

from __future__ import annotations

import asyncio
from typing import Any

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

import requests

from hive_errors import CircuitBreakerOpenError
from hive_logging import get_logger

from .resilience import AsyncCircuitBreaker

logger = get_logger(__name__)


class ResilientHttpClient:
    """
    HTTP client with circuit breaker protection for external APIs.

    Wraps requests/httpx/aiohttp with resilience patterns to prevent
    cascading failures from external service issues.

    Features:
    - Circuit breaker per domain
    - Automatic retry with exponential backoff
    - Request/response logging
    - Timeout management
    - Fallback support
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 30,
        default_timeout: float = 10.0,
        max_retries: int = 2,
    ):
        """
        Initialize resilient HTTP client.

        Args:
            failure_threshold: Failures before circuit opens
            recovery_timeout: Seconds before attempting recovery
            default_timeout: Default request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.default_timeout = default_timeout
        self.max_retries = max_retries

        # Circuit breakers per domain
        self._circuit_breakers: dict[str, AsyncCircuitBreaker] = {}

        # Stats
        self._request_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "circuit_breaker_blocks": 0,
            "retries": 0,
        }

    def _get_circuit_breaker(self, domain: str) -> AsyncCircuitBreaker:
        """Get or create circuit breaker for domain."""
        if domain not in self._circuit_breakers:
            self._circuit_breakers[domain] = AsyncCircuitBreaker(
                failure_threshold=self.failure_threshold,
                recovery_timeout=self.recovery_timeout,
                expected_exception=requests.RequestException,
            )
        return self._circuit_breakers[domain]

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL for circuit breaker keying."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    def get(self, url: str, timeout: float | None = None, **kwargs) -> requests.Response:
        """
        Make GET request with circuit breaker protection.

        Args:
            url: Request URL
            timeout: Request timeout (uses default if None)
            **kwargs: Additional requests arguments

        Returns:
            requests.Response object

        Raises:
            CircuitBreakerOpenError: Circuit breaker is open
            requests.RequestException: HTTP errors
        """
        return self._request_with_resilience("GET", url, timeout=timeout, **kwargs)

    def post(self, url: str, timeout: float | None = None, **kwargs) -> requests.Response:
        """
        Make POST request with circuit breaker protection.

        Args:
            url: Request URL
            timeout: Request timeout (uses default if None)
            **kwargs: Additional requests arguments (data, json, etc.)

        Returns:
            requests.Response object

        Raises:
            CircuitBreakerOpenError: Circuit breaker is open
            requests.RequestException: HTTP errors
        """
        return self._request_with_resilience("POST", url, timeout=timeout, **kwargs)

    def put(self, url: str, timeout: float | None = None, **kwargs) -> requests.Response:
        """Make PUT request with circuit breaker protection."""
        return self._request_with_resilience("PUT", url, timeout=timeout, **kwargs)

    def delete(self, url: str, timeout: float | None = None, **kwargs) -> requests.Response:
        """Make DELETE request with circuit breaker protection."""
        return self._request_with_resilience("DELETE", url, timeout=timeout, **kwargs)

    def _request_with_resilience(
        self,
        method: str,
        url: str,
        timeout: float | None = None,
        **kwargs,
    ) -> requests.Response:
        """Execute HTTP request with circuit breaker and retry."""
        domain = self._extract_domain(url)
        circuit_breaker = self._get_circuit_breaker(domain)
        timeout = timeout or self.default_timeout

        self._request_stats["total_requests"] += 1

        # Check if circuit breaker is open
        if circuit_breaker.is_open:
            self._request_stats["circuit_breaker_blocks"] += 1
            logger.warning(f"Circuit breaker OPEN for {domain} - request blocked")
            raise CircuitBreakerOpenError(
                f"Circuit breaker is OPEN for {domain}",
                failure_count=circuit_breaker.failure_count,
                recovery_time=circuit_breaker.recovery_timeout,
            )

        # Retry loop
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                # Execute request through circuit breaker
                async def _make_request():
                    return requests.request(method, url, timeout=timeout, **kwargs)

                # Run async circuit breaker call in sync context
                loop = asyncio.new_event_loop()
                try:
                    response = loop.run_until_complete(circuit_breaker.call_async(_make_request))
                finally:
                    loop.close()

                # Success
                self._request_stats["successful_requests"] += 1

                if attempt > 0:
                    logger.info(f"{method} {url} succeeded on attempt {attempt + 1}")

                return response

            except requests.RequestException as e:
                last_exception = e
                self._request_stats["failed_requests"] += 1

                if attempt < self.max_retries:
                    self._request_stats["retries"] += 1
                    backoff_seconds = 2**attempt  # Exponential backoff
                    logger.warning(
                        f"{method} {url} failed (attempt {attempt + 1}), retrying in {backoff_seconds}s: {e}",
                    )
                    import time

                    time.sleep(backoff_seconds)
                else:
                    logger.error(f"{method} {url} failed after {attempt + 1} attempts: {e}")

        # All retries exhausted
        raise last_exception

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics."""
        return {
            **self._request_stats,
            "circuit_breakers": {domain: breaker.get_status() for domain, breaker in self._circuit_breakers.items()},
        }

    def reset_circuit_breaker(self, domain: str | None = None) -> None:
        """
        Reset circuit breaker for domain.

        Args:
            domain: Domain to reset (resets all if None)
        """
        if domain:
            if domain in self._circuit_breakers:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self._circuit_breakers[domain].reset_async())
                finally:
                    loop.close()
                logger.info(f"Circuit breaker reset for {domain}")
        else:
            loop = asyncio.new_event_loop()
            try:
                for domain, breaker in self._circuit_breakers.items():
                    loop.run_until_complete(breaker.reset_async())
                    logger.info(f"Circuit breaker reset for {domain}")
            finally:
                loop.close()


class AsyncResilientHttpClient:
    """
    Async HTTP client with circuit breaker protection.

    Requires aiohttp or httpx to be installed.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 30,
        default_timeout: float = 10.0,
        max_retries: int = 2,
    ):
        """Initialize async resilient HTTP client."""
        if not (AIOHTTP_AVAILABLE or HTTPX_AVAILABLE):
            raise ImportError(
                "Either aiohttp or httpx must be installed for async HTTP client. "
                "Install with: pip install aiohttp OR pip install httpx",
            )

        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.default_timeout = default_timeout
        self.max_retries = max_retries

        self._circuit_breakers: dict[str, AsyncCircuitBreaker] = {}
        self._session = None

    def _get_circuit_breaker(self, domain: str) -> AsyncCircuitBreaker:
        """Get or create circuit breaker for domain."""
        if domain not in self._circuit_breakers:
            self._circuit_breakers[domain] = AsyncCircuitBreaker(
                failure_threshold=self.failure_threshold,
                recovery_timeout=self.recovery_timeout,
            )
        return self._circuit_breakers[domain]

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    async def get(self, url: str, timeout: float | None = None, **kwargs):
        """Make async GET request with circuit breaker protection."""
        return await self._request_with_resilience("GET", url, timeout=timeout, **kwargs)

    async def post(self, url: str, timeout: float | None = None, **kwargs):
        """Make async POST request with circuit breaker protection."""
        return await self._request_with_resilience("POST", url, timeout=timeout, **kwargs)

    async def _request_with_resilience(self, method: str, url: str, timeout: float | None = None, **kwargs):
        """Execute async HTTP request with circuit breaker and retry."""
        domain = self._extract_domain(url)
        circuit_breaker = self._get_circuit_breaker(domain)
        timeout = timeout or self.default_timeout

        # Check if circuit breaker is open
        if circuit_breaker.is_open:
            logger.warning(f"Circuit breaker OPEN for {domain} - request blocked")
            raise CircuitBreakerOpenError(
                f"Circuit breaker is OPEN for {domain}",
                failure_count=circuit_breaker.failure_count,
                recovery_time=circuit_breaker.recovery_timeout,
            )

        # Retry loop
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                if HTTPX_AVAILABLE:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await circuit_breaker.call_async(client.request, method, url, **kwargs)
                        return response

                elif AIOHTTP_AVAILABLE:
                    timeout_obj = aiohttp.ClientTimeout(total=timeout)
                    async with aiohttp.ClientSession(timeout=timeout_obj) as session:

                        async def _make_request():
                            return await session.request(method, url, **kwargs)

                        response = await circuit_breaker.call_async(_make_request)
                        return response

            except Exception as e:
                last_exception = e

                if attempt < self.max_retries:
                    backoff_seconds = 2**attempt
                    logger.warning(
                        f"{method} {url} failed (attempt {attempt + 1}), retrying in {backoff_seconds}s: {e}",
                    )
                    await asyncio.sleep(backoff_seconds)
                else:
                    logger.error(f"{method} {url} failed after {attempt + 1} attempts: {e}")

        raise last_exception


# Global singleton instances
_sync_client = None
_async_client = None


def get_resilient_http_client() -> ResilientHttpClient:
    """Get global resilient HTTP client instance."""
    global _sync_client
    if _sync_client is None:
        _sync_client = ResilientHttpClient()
    return _sync_client


def get_async_resilient_http_client() -> AsyncResilientHttpClient:
    """Get global async resilient HTTP client instance."""
    global _async_client
    if _async_client is None:
        _async_client = AsyncResilientHttpClient()
    return _async_client
