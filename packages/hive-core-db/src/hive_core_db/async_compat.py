#!/usr/bin/env python3
"""
Async Compatibility Layer for Phase 4.1 Migration

Provides backward compatibility wrappers that allow sync code to use async database
operations transparently during the migration period. Ensures zero breaking changes.
"""

import asyncio
import threading
import logging
import functools
from typing import Any, Callable, TypeVar, Union
from contextlib import contextmanager

from .async_connection_pool import get_async_connection, close_async_pool

logger = logging.getLogger(__name__)

T = TypeVar('T')


class AsyncEventLoopManager:
    """
    Manages event loops for sync-to-async compatibility.

    Ensures proper async operation execution from sync contexts while
    maintaining thread safety and preventing event loop conflicts.
    """

    def __init__(self):
        self._thread_loops = {}
        self._lock = threading.Lock()

    def run_async(self, coro) -> Any:
        """
        Run an async coroutine from sync context.

        Args:
            coro: Async coroutine to execute

        Returns:
            Result of the coroutine
        """
        thread_id = threading.get_ident()

        # Try to use existing event loop in this thread
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an async context, we need to run in thread pool
            return self._run_in_thread_pool(coro)
        except RuntimeError:
            # No running loop, safe to create/use one
            pass

        # Get or create loop for this thread
        with self._lock:
            if thread_id not in self._thread_loops:
                self._thread_loops[thread_id] = asyncio.new_event_loop()
                asyncio.set_event_loop(self._thread_loops[thread_id])

            loop = self._thread_loops[thread_id]

        return loop.run_until_complete(coro)

    def _run_in_thread_pool(self, coro):
        """Run coroutine in a separate thread to avoid event loop conflicts."""
        import concurrent.futures

        def run_in_new_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_in_new_loop)
            return future.result()

    def cleanup(self):
        """Clean up thread-local event loops."""
        with self._lock:
            for loop in self._thread_loops.values():
                if not loop.is_closed():
                    loop.close()
            self._thread_loops.clear()


# Global event loop manager
_loop_manager = AsyncEventLoopManager()


def sync_wrapper(async_func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to create sync wrapper for async functions.

    Allows sync code to call async database functions transparently.

    Args:
        async_func: Async function to wrap

    Returns:
        Sync wrapper function
    """
    @functools.wraps(async_func)
    def wrapper(*args, **kwargs):
        coro = async_func(*args, **kwargs)
        return _loop_manager.run_async(coro)

    return wrapper


@contextmanager
def get_sync_async_connection():
    """
    Sync context manager that provides async connection compatibility.

    This allows existing sync code to use async connections transparently:

    Example:
        # Existing sync code works unchanged
        with get_sync_async_connection() as conn:
            cursor = conn.execute("SELECT * FROM tasks")
            results = cursor.fetchall()
    """
    class AsyncConnectionWrapper:
        """Wrapper that makes async connection look sync."""

        def __init__(self, async_conn):
            self._async_conn = async_conn

        def execute(self, sql, parameters=None):
            """Sync wrapper for async execute."""
            async def _execute():
                if parameters:
                    return await self._async_conn.execute(sql, parameters)
                else:
                    return await self._async_conn.execute(sql)

            cursor = _loop_manager.run_async(_execute())
            return AsyncCursorWrapper(cursor)

        def executemany(self, sql, parameters_list):
            """Sync wrapper for async executemany."""
            async def _executemany():
                return await self._async_conn.executemany(sql, parameters_list)

            return _loop_manager.run_async(_executemany())

        def commit(self):
            """Sync wrapper for async commit."""
            async def _commit():
                await self._async_conn.commit()

            return _loop_manager.run_async(_commit())

        def rollback(self):
            """Sync wrapper for async rollback."""
            async def _rollback():
                await self._async_conn.rollback()

            return _loop_manager.run_async(_rollback())

        def close(self):
            """Sync wrapper for async close."""
            async def _close():
                await self._async_conn.close()

            return _loop_manager.run_async(_close())

    class AsyncCursorWrapper:
        """Wrapper that makes async cursor look sync."""

        def __init__(self, async_cursor):
            self._async_cursor = async_cursor

        def fetchone(self):
            """Sync wrapper for async fetchone."""
            async def _fetchone():
                return await self._async_cursor.fetchone()

            return _loop_manager.run_async(_fetchone())

        def fetchall(self):
            """Sync wrapper for async fetchall."""
            async def _fetchall():
                return await self._async_cursor.fetchall()

            return _loop_manager.run_async(_fetchall())

        def fetchmany(self, size=None):
            """Sync wrapper for async fetchmany."""
            async def _fetchmany():
                if size:
                    return await self._async_cursor.fetchmany(size)
                else:
                    return await self._async_cursor.fetchmany()

            return _loop_manager.run_async(_fetchmany())

    # Simplified sync wrapper for async connection
    async def _get_and_enter():
        async_cm = get_async_connection()
        conn = await async_cm.__aenter__()
        return async_cm, conn

    # Get the async context manager and connection
    async_cm, conn = _loop_manager.run_async(_get_and_enter())
    wrapped_conn = AsyncConnectionWrapper(conn)

    try:
        yield wrapped_conn
    finally:
        # Clean up the async context manager
        async def _exit():
            await async_cm.__aexit__(None, None, None)

        _loop_manager.run_async(_exit())


class AsyncToSyncAdapter:
    """
    Adapter class for converting async database functions to sync.

    Provides a clean interface for accessing async database operations
    from sync code during the migration period.
    """

    @staticmethod
    @sync_wrapper
    async def execute_query(query: str, parameters=None):
        """Execute a query using async connection."""
        async with get_async_connection() as conn:
            if parameters:
                cursor = await conn.execute(query, parameters)
            else:
                cursor = await conn.execute(query)
            return await cursor.fetchall()

    @staticmethod
    @sync_wrapper
    async def execute_update(query: str, parameters=None):
        """Execute an update/insert/delete using async connection."""
        async with get_async_connection() as conn:
            if parameters:
                cursor = await conn.execute(query, parameters)
            else:
                cursor = await conn.execute(query)
            await conn.commit()
            return cursor.rowcount

    @staticmethod
    @sync_wrapper
    async def execute_transaction(queries_and_params):
        """Execute multiple queries in a transaction."""
        async with get_async_connection() as conn:
            try:
                results = []
                for query, params in queries_and_params:
                    if params:
                        cursor = await conn.execute(query, params)
                    else:
                        cursor = await conn.execute(query)
                    results.append(cursor.rowcount)
                await conn.commit()
                return results
            except Exception:
                await conn.rollback()
                raise


def cleanup_async_compat():
    """Clean up async compatibility resources."""
    _loop_manager.cleanup()

    # Clean up async pool
    try:
        _loop_manager.run_async(close_async_pool())
    except Exception as e:
        logger.debug(f"Error cleaning up async pool: {e}")


# Convenience functions for direct use
execute_query_sync = AsyncToSyncAdapter.execute_query
execute_update_sync = AsyncToSyncAdapter.execute_update
execute_transaction_sync = AsyncToSyncAdapter.execute_transaction


def async_database_enabled() -> bool:
    """Check if async database operations are available."""
    try:
        import aiosqlite
        return True
    except ImportError:
        return False


# Register cleanup function for graceful shutdown
import atexit
atexit.register(cleanup_async_compat)