from hive_logging import get_logger

logger = get_logger(__name__)

"""Basic async task utilities for infrastructure use."""

import asyncio
from typing import Any, Awaitable, List, TypeVar

T = TypeVar("T")


async def gather_with_concurrency_async(
    *coros: Awaitable[T], max_concurrent: int = 10, return_exceptions: bool = False
) -> List[Any]:
    """
    Gather coroutines with concurrency limit.

    This is a basic infrastructure utility. For advanced task management,
    use hive_orchestrator.tasks.TaskManager.

    Args:
        *coros: Coroutines to execute
        max_concurrent: Maximum number of concurrent executions
        return_exceptions: Whether to return exceptions as results

    Returns:
        List of results in the same order as input coroutines
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def limited_coro_async(coro: Awaitable[T]) -> T:
        async with semaphore:
            return await coro

    limited_coros = [limited_coro_async(coro) for coro in coros]
    return await asyncio.gather(*limited_coros, return_exceptions=return_exceptions)


async def run_with_timeout_async(coro: Awaitable[T], timeout: float) -> T:
    """
    Run a coroutine with timeout.

    Basic infrastructure utility. For advanced retry logic,
    use hive_orchestrator.tasks.run_with_timeout_and_retry.

    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds

    Returns:
        Result of the coroutine
    """
    return await asyncio.wait_for(coro, timeout=timeout)
