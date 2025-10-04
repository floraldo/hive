"""
Hive async utilities and patterns with unified resilience management.

Centralized async infrastructure including connection pooling, retry logic,
and unified resilience patterns (circuit breakers + timeouts + error handling).
"""

from hive_logging import get_logger

from .advanced_timeout import (
    AdvancedTimeoutManager,  # Backward compatibility alias to AsyncResilienceManager
    AsyncResilienceManager,
    CircuitState,
    TimeoutConfig,
    TimeoutMetrics,
    resilience_context_async,
    timeout_context_async,  # Backward compatibility alias
    with_adaptive_timeout,  # Backward compatibility alias
    with_resilience,
)
from .context import AsyncResourceManager, async_context
from .pools import AsyncConnectionManager, ConnectionPool, PoolConfig
from .retry import AsyncRetryConfig, create_retry_decorator, run_async_with_retry_async
from .tasks import gather_with_concurrency_async, run_with_timeout_async

logger = get_logger(__name__)

# Backward compatibility imports from resilience.py (DEPRECATED - use AsyncResilienceManager)
try:
    from .resilience import (
        AsyncCircuitBreaker,  # DEPRECATED - use AsyncResilienceManager
        AsyncTimeoutManager,  # DEPRECATED - use AsyncResilienceManager
        async_circuit_breaker,  # DEPRECATED - use with_resilience
        async_resilient,  # DEPRECATED - use with_resilience
        async_timeout,  # DEPRECATED - use with_resilience
    )
except ImportError:
    # Fallback to AsyncResilienceManager if resilience.py is removed
    AsyncCircuitBreaker = AsyncResilienceManager  # type: ignore
    AsyncTimeoutManager = AsyncResilienceManager  # type: ignore
    async_circuit_breaker = with_resilience  # type: ignore
    async_resilient = with_resilience  # type: ignore
    async_timeout = with_resilience  # type: ignore

# Aliases for backward compatibility
async_retry = run_async_with_retry_async
gather_with_concurrency = gather_with_concurrency_async
timeout_context = resilience_context_async

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
    # UNIFIED Resilience Management (PRIMARY INTERFACE)
    "AsyncResilienceManager",  # Use this for all new code
    "CircuitState",
    "TimeoutConfig",
    "TimeoutMetrics",
    "resilience_context_async",
    "with_resilience",
    # Backward Compatibility Aliases (DEPRECATED)
    "AdvancedTimeoutManager",  # Alias to AsyncResilienceManager
    "AsyncCircuitBreaker",  # DEPRECATED - use AsyncResilienceManager
    "AsyncTimeoutManager",  # DEPRECATED - use AsyncResilienceManager
    "async_circuit_breaker",  # DEPRECATED - use with_resilience
    "async_timeout",  # DEPRECATED - use with_resilience
    "async_resilient",  # DEPRECATED - use with_resilience
    "timeout_context_async",  # DEPRECATED - use resilience_context_async
    "timeout_context",  # DEPRECATED - use resilience_context_async
    "with_adaptive_timeout",  # DEPRECATED - use with_resilience
]
