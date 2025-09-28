"""
Hive async utilities and patterns with enhanced resilience.

Centralized async infrastructure including connection pooling, retry logic,
and resilience patterns (circuit breakers, timeouts, error handling).
"""

from .context import AsyncResourceManager, async_context
from .pools import AsyncConnectionManager, ConnectionPool, PoolConfig
from .retry import (
    AsyncRetryConfig,
    async_retry,
    create_retry_decorator,
    retry_on_connection_error,
)
from .tasks import gather_with_concurrency, run_with_timeout
from .resilience import (
    AsyncCircuitBreaker,
    AsyncTimeoutManager,
    CircuitState,
    async_circuit_breaker,
    async_timeout,
    async_resilient,
)
from .advanced_timeout import (
    AdvancedTimeoutManager,
    TimeoutConfig,
    TimeoutMetrics,
    timeout_context,
    with_adaptive_timeout,
)

__all__ = [
    # Context management
    "AsyncResourceManager",
    "async_context",

    # Retry utilities
    "async_retry",
    "AsyncRetryConfig",
    "create_retry_decorator",
    "retry_on_connection_error",

    # Connection pooling
    "ConnectionPool",
    "AsyncConnectionManager",
    "PoolConfig",

    # Task management
    "gather_with_concurrency",
    "run_with_timeout",

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
    "timeout_context",
    "with_adaptive_timeout",
]