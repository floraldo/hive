#!/usr/bin/env python3
"""Async Resource Management Best Practices for Hive Platform

Common patterns and utilities for proper async resource management.
"""

import asyncio
import weakref
from contextlib import asynccontextmanager


class TaskManager:
    """Manages async tasks with proper lifecycle"""

    def __init__(self):
        self._tasks: weakref.WeakSet = weakref.WeakSet()

    def create_task(self, coro) -> asyncio.Task:
        """Create and track a task"""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        return task

    async def cancel_all(self):
        """Cancel all tracked tasks"""
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*tasks, return_exceptions=True)


@asynccontextmanager
async def managed_connection(create_conn, close_conn=None):
    """Generic async context manager for connections"""
    conn = None
    try:
        conn = await create_conn()
        yield conn
    finally:
        if conn and close_conn:
            await close_conn(conn)


class AsyncResourcePool:
    """Thread-safe async resource pool"""

    def __init__(self, create_resource, max_size=10):
        self._create_resource = create_resource
        self._pool = asyncio.Queue(maxsize=max_size)
        self._lock = asyncio.Lock()
        self._closed = False

    async def acquire(self):
        """Acquire resource with proper error handling"""
        if self._closed:
            raise RuntimeError("Pool is closed")

        try:
            # Try to get from pool
            return await asyncio.wait_for(self._pool.get(), timeout=5.0)
        except TimeoutError:
            # Create new resource if pool is empty
            async with self._lock:
                return await self._create_resource()

    async def release(self, resource):
        """Release resource back to pool"""
        if not self._closed:
            try:
                await self._pool.put(resource)
            except asyncio.QueueFull:
                # Pool is full, close the resource
                await self._close_resource(resource)

    async def close(self):
        """Close all resources in pool"""
        async with self._lock:
            self._closed = True
            while not self._pool.empty():
                try:
                    resource = self._pool.get_nowait()
                    await self._close_resource(resource)
                except asyncio.QueueEmpty:
                    break


async def safe_gather(*coros, return_exceptions=True):
    """Safer version of asyncio.gather"""
    return await asyncio.gather(*coros, return_exceptions=return_exceptions)


class AsyncStateLock:
    """Lock for protecting shared state in async context"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._state = {}

    async def update_state(self, key, value):
        """Update state with lock protection"""
        async with self._lock:
            self._state[key] = value

    async def get_state(self, key, default=None):
        """Get state with lock protection"""
        async with self._lock:
            return self._state.get(key, default)


# Example usage patterns
async def example_proper_resource_management():
    """Example of proper async resource management"""
    # 1. Task management
    task_manager = TaskManager()
    task = task_manager.create_task(some_async_operation())

    try:
        await task
    except Exception as e:
        logger.error(f"Task failed: {e}")
    finally:
        await task_manager.cancel_all()

    # 2. Connection management
    async with managed_connection(create_conn=create_database_connection, close_conn=close_database_connection) as conn:
        await conn.execute("SELECT 1")

    # 3. Pool management
    pool = AsyncResourcePool(create_resource=create_connection)
    try:
        resource = await pool.acquire()
        try:
            await use_resource(resource)
        finally:
            await pool.release(resource)
    finally:
        await pool.close()

    # 4. Safe gathering
    await safe_gather(operation1(), operation2(), operation3(), return_exceptions=True)

    # 5. Protected state
    state_lock = AsyncStateLock()
    await state_lock.update_state("counter", 1)
    await state_lock.get_state("counter")
