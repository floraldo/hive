"""Task management and coordination utilities for async operations."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, ListTypeVar

from hive_logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class TaskResult:
    """Result of a task execution."""
from __future__ import annotations


    task_id: str
    success: bool
    result: Any = None
    error: Exception | None = None
    duration: float | None = None


class TaskManager:
    """Manages async task execution with monitoring and coordination."""

    def __init__(self, max_concurrent: int = 10) -> None:
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: Dict[str, TaskResult] = {}
        self._task_counter = 0

    async def submit_task_async(
        self,
        coro: Awaitable[T]
        task_id: str | None = None,
        timeout: float | None = None
    ) -> str:
        """
        Submit a task for execution.

        Args:
            coro: Coroutine to execute
            task_id: Optional task identifier
            timeout: Optional timeout in seconds

        Returns:
            Task ID
        """
        if task_id is None:
            self._task_counter += 1
            task_id = f"task_{self._task_counter}"

        if task_id in self.active_tasks:
            raise ValueError(f"Task {task_id} is already active")

        # Wrap the coroutine with semaphore and monitoring
        async def wrapped_task_async() -> None:
            async with self.semaphore:
                start_time = asyncio.get_event_loop().time()
                try:
                    if timeout:
                        result = await asyncio.wait_for(coro, timeout=timeout)
                    else:
                        result = await coro

                    duration = asyncio.get_event_loop().time() - start_time
                    task_result = TaskResult(task_id=task_id, success=True, result=result, duration=duration)
                    self.completed_tasks[task_id] = task_result
                    logger.debug(f"Task {task_id} completed successfully in {duration:.2f}s")
                    return result

                except Exception as e:
                    duration = asyncio.get_event_loop().time() - start_time
                    task_result = TaskResult(task_id=task_id, success=False, error=e, duration=duration)
                    self.completed_tasks[task_id] = task_result
                    logger.error(f"Task {task_id} failed after {duration:.2f}s: {e}")
                    raise

                finally:
                    self.active_tasks.pop(task_id, None)

        task = asyncio.create_task(wrapped_task_async())
        self.active_tasks[task_id] = task
        return task_id

    async def wait_for_task_async(self, task_id: str) -> TaskResult:
        """Wait for a specific task to complete."""
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]

        if task_id not in self.active_tasks:
            raise ValueError(f"Task {task_id} not found")

        try:
            await self.active_tasks[task_id]
        except Exception:
            pass  # Error is stored in TaskResult

        return self.completed_tasks[task_id]

    async def wait_for_all_async(self, task_ids: Optional[List[str]] = None) -> Dict[str, TaskResult]:
        """Wait for all specified tasks (or all active tasks) to complete."""
        if task_ids is None:
            task_ids = list(self.active_tasks.keys())

        results = {}
        for task_id in task_ids:
            results[task_id] = await self.wait_for_task_async(task_id)

        return results

    async def cancel_task_async(self, task_id: str) -> bool:
        """Cancel a specific task."""
        if task_id not in self.active_tasks:
            return False

        task = self.active_tasks[task_id]
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Record cancellation
        self.completed_tasks[task_id] = TaskResult(
            task_id=task_id,
            success=False,
            error=asyncio.CancelledError("Task was cancelled")
        )

        return True

    async def cancel_all_async(self) -> None:
        """Cancel all active tasks."""
        task_ids = list(self.active_tasks.keys())
        for task_id in task_ids:
            await self.cancel_task_async(task_id)

    def get_status(self) -> Dict[str, Any]:
        """Get current status of all tasks."""
        return {
            "active_count": len(self.active_tasks),
            "completed_count": len(self.completed_tasks)
            "max_concurrent": self.max_concurrent,
            "active_tasks": list(self.active_tasks.keys()),
            "success_rate": self._calculate_success_rate()
        }

    def _calculate_success_rate(self) -> float | None:
        """Calculate success rate of completed tasks."""
        if not self.completed_tasks:
            return None

        successful = sum(1 for result in self.completed_tasks.values() if result.success)
        return successful / len(self.completed_tasks)

    @asynccontextmanager
    async def task_group_async(self, max_concurrent: int | None = None) -> None:
        """Context manager for task group execution."""
        if max_concurrent:
            original_limit = self.max_concurrent
            self.max_concurrent = max_concurrent
            self.semaphore = asyncio.Semaphore(max_concurrent)

        try:
            yield self
        finally:
            await self.wait_for_all_async()
            if max_concurrent:
                self.max_concurrent = original_limit
                self.semaphore = asyncio.Semaphore(original_limit)


async def gather_with_concurrency_async(
    *coros: Awaitable[T], max_concurrent: int = 10, return_exceptions: bool = False
) -> List[Any]:
    """
    Gather coroutines with concurrency limit.

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


async def run_with_timeout_and_retry_async(
    coro: Awaitable[T]
    timeout: float,
    max_retries: int = 3,
    backoff_factor: float = 1.0
) -> T:
    """
    Run a coroutine with timeout and retry logic.

    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds
        max_retries: Maximum number of retries
        backoff_factor: Backoff multiplier between retries

    Returns:
        Result of the coroutine

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = backoff_factor * (2**attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {max_retries + 1} attempts failed: {e}")

    if last_exception:
        raise last_exception
