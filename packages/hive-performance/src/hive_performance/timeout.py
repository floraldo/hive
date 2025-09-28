"""Timeout handling for async operations"""

import asyncio
from functools import wraps
from typing import Any, Optional
from hive_logging import get_logger

logger = get_logger(__name__)


def with_timeout(seconds: float):
    """Decorator to add timeout to async functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"{func.__name__} timed out after {seconds}s")
                raise

        return wrapper
    return decorator


class TimeoutManager:
    """Manage timeouts for multiple operations"""

    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout
        self._active_tasks = set()

    async def run_with_timeout_async(
        self,
        coro,
        timeout: Optional[float] = None,
        fallback: Optional[Any] = None
    ) -> Any:
        """Run coroutine with timeout and optional fallback"""
        timeout = timeout or self.default_timeout

        try:
            task = asyncio.create_task(coro)
            self._active_tasks.add(task)

            result = await asyncio.wait_for(task, timeout=timeout)
            return result

        except asyncio.TimeoutError:
            logger.warning(f"Operation timed out after {timeout}s")
            if fallback is not None:
                return fallback
            raise

        finally:
            self._active_tasks.discard(task)

    async def cancel_all_async(self):
        """Cancel all active tasks"""
        for task in self._active_tasks:
            task.cancel()

        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

        self._active_tasks.clear()
