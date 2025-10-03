"""Async context management utilities."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class AsyncResourceManager:
    """Manages async resources with proper cleanup."""

    def __init__(self) -> None:
        self.resources: dict[str, Any] = {}
        self._cleanup_callbacks: dict[str, Any] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.cleanup_all_async()

    def register_resource(self, name: str, resource: Any, cleanup_callback: Any | None = None) -> None:
        """Register a resource for automatic cleanup."""
        self.resources[name] = resource
        if cleanup_callback:
            self._cleanup_callbacks[name] = cleanup_callback

    async def cleanup_resource_async(self, name: str) -> None:
        """Clean up a specific resource."""
        if name in self.resources:
            resource = (self.resources.pop(name),)
            cleanup_callback = self._cleanup_callbacks.pop(name, None)

            try:
                if cleanup_callback:
                    if asyncio.iscoroutinefunction(cleanup_callback):
                        await cleanup_callback(resource)
                    else:
                        cleanup_callback(resource)
                elif hasattr(resource, "close"):
                    if asyncio.iscoroutinefunction(resource.close):
                        await resource.close()
                    else:
                        resource.close()
            except Exception as e:
                logger.warning(f"Error cleaning up resource {name}: {e}")

    async def cleanup_all_async(self) -> None:
        """Clean up all registered resources."""
        for name in list(self.resources.keys()):
            await self.cleanup_resource_async(name)

    def get_resource(self, name: str) -> Any:
        """Get a registered resource."""
        return self.resources.get(name)

    async def acquire_async(self, name: str, factory, *args, **kwargs):
        """Acquire a resource using a factory function."""
        if name in self.resources:
            return self.resources[name]

        if asyncio.iscoroutinefunction(factory):
            resource = await factory(*args, **kwargs)
        else:
            resource = factory(*args, **kwargs)

        self.resources[name] = resource
        return resource

    def add_cleanup_async(self, cleanup_callback) -> None:
        """Add a cleanup callback."""
        self._cleanup_callbacks[f"callback_{len(self._cleanup_callbacks)}"] = cleanup_callback


@asynccontextmanager
async def async_context_async(*resources: AbstractAsyncContextManager) -> AsyncIterator[None]:
    """Context manager for handling multiple async resources."""
    entered_resources = []
    try:
        for resource in resources:
            entered = await resource.__aenter__()
            entered_resources.append((resource, entered))

        if len(entered_resources) == 1:
            yield entered_resources[0][1]
        else:
            yield [entered for _, entered in entered_resources]

    finally:
        for resource, _ in reversed(entered_resources):
            try:
                await resource.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error in async context cleanup: {e}")


def async_context(context_name: str) -> None:
    """Decorator for async context management."""

    def decorator(func) -> Any:
        async def wrapper_async(*args, **kwargs):
            async with AsyncResourceManager():
                logger.debug(f"Entering async context: {context_name}")
                try:
                    result = await func(*args, **kwargs)
                    logger.debug(f"Exiting async context: {context_name}")
                    return result
                except Exception as e:
                    logger.error(f"Error in async context {context_name}: {e}")
                    raise

        return wrapper_async

    return decorator
