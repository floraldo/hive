"""
Hive async utilities and patterns with enhanced resilience.

Centralized async infrastructure including connection pooling, retry logic,
and resilience patterns (circuit breakers, timeouts, error handling).
"""

from hive_logging import get_logger

from .advanced_timeout import (
    AdvancedTimeoutManager,
    TimeoutConfig,
    TimeoutMetrics,
    timeout_context_async,
    with_adaptive_timeout,
)
from .context import AsyncResourceManager, async_context
from .pools import AsyncConnectionManager, ConnectionPool, PoolConfig
from .resilience import (
    AsyncCircuitBreaker,
    AsyncTimeoutManager,
    CircuitState,
    async_circuit_breaker,
    async_resilient,
    async_timeout,
)
from .retry import AsyncRetryConfig, create_retry_decorator, run_async_with_retry_async
from .tasks import gather_with_concurrency_async, run_with_timeout_async

logger = get_logger(__name__)

# Aliases for backward compatibility
async_retry = run_async_with_retry_async
gather_with_concurrency = gather_with_concurrency_async
timeout_context = timeout_context_async

__all__ = [
    # Context management
    "AsyncResourceManager",
    "async_context",
    # Retry utilities
    "run_async_with_retry_async",
    "async_retry",  # Alias for backward compatibility
    "AsyncRetryConfig",
    "create_retry_decorator",
    # Connection pooling
    "ConnectionPool",
    "AsyncConnectionManager",
    "PoolConfig",
    # Task management
    "gather_with_concurrency_async",
    "gather_with_concurrency",  # Alias
    "run_with_timeout_async",
    # Resilience patterns (consolidated from hive-performance)
    "AsyncCircuitBreaker",
    "AsyncTimeoutManager",
    "CircuitState",
    "async_circuit_breaker",
    "async_timeout",
    "async_resilient",
    # Advanced timeout management
    "AdvancedTimeoutManager",
    "TimeoutConfig",
    "TimeoutMetrics",
    "timeout_context_async",
    "timeout_context",  # Alias
    "with_adaptive_timeout",
]
