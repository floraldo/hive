"""
Composite decorators combining multiple observability patterns.

High-level decorators that bundle common monitoring patterns extracted
from production usage in EcoSystemiser.
"""

from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Callable
from typing import Any

from hive_logging import get_logger

from .decorators import _metrics_registry, _tracing_context, counted, timed, traced, track_errors

logger = get_logger(__name__)


def track_request(
    operation_name: str,
    labels: dict[str, str] | None = None,
    record_errors: bool = True,
) -> Callable:
    """
    Composite decorator for tracking HTTP/API requests.

    Combines:
    - @timed: Request duration histogram
    - @counted: Request counter
    - @traced: Distributed trace span
    - @track_errors: Error counter (if record_errors=True)

    Args:
        operation_name: Base name for metrics (e.g., "api.users.get")
        labels: Additional metric labels (e.g., {"endpoint": "/users", "method": "GET"})
        record_errors: Whether to track errors (default: True)

    Example:
        @track_request("api.users.get", labels={"endpoint": "/users"})
        async def get_users(request):
            return await fetch_users()
    """

    def decorator(func: Callable) -> Callable:
        # Stack decorators from innermost to outermost
        instrumented = func
        if record_errors:
            instrumented = track_errors(f"{operation_name}.errors", labels=labels)(instrumented)
        instrumented = traced(operation_name, attributes=labels or {})(instrumented)
        instrumented = counted(f"{operation_name}.calls", labels=labels)(instrumented)
        instrumented = timed(f"{operation_name}.duration", labels=labels)(instrumented)
        return instrumented

    return decorator


def track_cache_operation(
    cache_level: str,
    operation_type: str = "get",
) -> Callable:
    """
    Composite decorator for tracking cache operations.

    Tracks cache hits/misses and calculates hit ratio.

    Args:
        cache_level: Cache level (e.g., "memory", "disk", "redis")
        operation_type: Operation type (e.g., "get", "set", "delete")

    Example:
        @track_cache_operation("redis", "get")
        async def get_from_cache(key: str):
            return await redis.get(key)

    Metrics Generated:
        - cache.{level}.{operation}.calls: Total operations
        - cache.{level}.{operation}.duration: Operation duration
        - cache.{level}.hits: Cache hits (when result is not None)
        - cache.{level}.misses: Cache misses (when result is None)
    """

    def decorator(func: Callable) -> Callable:
        base_labels = {"level": cache_level, "operation": operation_type}

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Track call and duration
                await _metrics_registry.record_counter(f"cache.{cache_level}.{operation_type}.calls", 1.0, base_labels)

                start = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)

                    # Track hit/miss based on result
                    if result is not None:
                        await _metrics_registry.record_counter(f"cache.{cache_level}.hits", 1.0, {"level": cache_level})
                    else:
                        await _metrics_registry.record_counter(
                            f"cache.{cache_level}.misses", 1.0, {"level": cache_level}
                        )

                    return result
                finally:
                    duration = time.perf_counter() - start
                    await _metrics_registry.record_histogram(
                        f"cache.{cache_level}.{operation_type}.duration", duration, base_labels
                    )

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    logger.warning(f"No event loop available for sync function {func.__name__}. Skipping metrics.")
                    return func(*args, **kwargs)

                # Record metrics synchronously via event loop
                loop.create_task(
                    _metrics_registry.record_counter(f"cache.{cache_level}.{operation_type}.calls", 1.0, base_labels)
                )

                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)

                    # Track hit/miss
                    if result is not None:
                        loop.create_task(
                            _metrics_registry.record_counter(f"cache.{cache_level}.hits", 1.0, {"level": cache_level})
                        )
                    else:
                        loop.create_task(
                            _metrics_registry.record_counter(f"cache.{cache_level}.misses", 1.0, {"level": cache_level})
                        )

                    return result
                finally:
                    duration = time.perf_counter() - start
                    loop.create_task(
                        _metrics_registry.record_histogram(
                            f"cache.{cache_level}.{operation_type}.duration", duration, base_labels
                        )
                    )

            return sync_wrapper

    return decorator


def track_adapter_request(adapter_name: str) -> Callable:
    """
    Composite decorator for tracking external adapter/API requests.

    Combines:
    - @timed: Request latency
    - @counted: Request counter with success/failure status
    - @traced: Distributed trace span
    - @track_errors: Error counter

    Args:
        adapter_name: Name of the adapter (e.g., "weather_api", "database")

    Example:
        @track_adapter_request("weather_api")
        async def fetch_weather(location: str):
            return await api.get(f"/weather/{location}")

    Metrics Generated:
        - adapter.{name}.duration: Request latency histogram
        - adapter.{name}.calls: Total requests counter
        - adapter.{name}.errors: Error counter
        - Trace span: "adapter.{name}.request"
    """

    def decorator(func: Callable) -> Callable:
        base_labels = {"adapter": adapter_name}

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Start span and timer
                span = _tracing_context.start_span(f"adapter.{adapter_name}.request", attributes=base_labels)
                start = time.perf_counter()

                try:
                    result = await func(*args, **kwargs)

                    # Record success
                    await _metrics_registry.record_counter(
                        f"adapter.{adapter_name}.calls", 1.0, {**base_labels, "status": "success"}
                    )
                    _tracing_context.end_span(span, status="OK")

                    return result

                except Exception as e:
                    # Record failure
                    await _metrics_registry.record_counter(
                        f"adapter.{adapter_name}.calls", 1.0, {**base_labels, "status": "failure"}
                    )
                    await _metrics_registry.record_counter(
                        f"adapter.{adapter_name}.errors", 1.0, {**base_labels, "error_type": type(e).__name__}
                    )
                    _tracing_context.end_span(span, status="ERROR", exception=str(e))
                    raise

                finally:
                    # Record latency
                    duration = time.perf_counter() - start
                    await _metrics_registry.record_histogram(f"adapter.{adapter_name}.duration", duration, base_labels)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    logger.warning(f"No event loop available for sync function {func.__name__}. Skipping metrics.")
                    return func(*args, **kwargs)

                span = _tracing_context.start_span(f"adapter.{adapter_name}.request", attributes=base_labels)
                start = time.perf_counter()

                try:
                    result = func(*args, **kwargs)

                    # Record success
                    loop.create_task(
                        _metrics_registry.record_counter(
                            f"adapter.{adapter_name}.calls", 1.0, {**base_labels, "status": "success"}
                        )
                    )
                    _tracing_context.end_span(span, status="OK")

                    return result

                except Exception as e:
                    # Record failure
                    loop.create_task(
                        _metrics_registry.record_counter(
                            f"adapter.{adapter_name}.calls", 1.0, {**base_labels, "status": "failure"}
                        )
                    )
                    loop.create_task(
                        _metrics_registry.record_counter(
                            f"adapter.{adapter_name}.errors", 1.0, {**base_labels, "error_type": type(e).__name__}
                        )
                    )
                    _tracing_context.end_span(span, status="ERROR", exception=str(e))
                    raise

                finally:
                    duration = time.perf_counter() - start
                    loop.create_task(
                        _metrics_registry.record_histogram(f"adapter.{adapter_name}.duration", duration, base_labels)
                    )

            return sync_wrapper

    return decorator


__all__ = [
    "track_request",
    "track_cache_operation",
    "track_adapter_request",
]
