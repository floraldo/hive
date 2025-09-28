"""Async context management utilities."""

import asyncio
from typing import Any, Dict, Optional, AsyncContextManager
from contextlib import asynccontextmanager
from hive_logging import get_logger

logger = get_logger(__name__)


class AsyncResourceManager:
    """Manages async resources with proper cleanup."""

    def __init__(self):
        self.resources: Dict[str, Any] = {}
        self._cleanup_callbacks: Dict[str, Any] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup_all()

    def register_resource(self, name: str, resource: Any, cleanup_callback: Optional[Any] = None):
        """Register a resource for automatic cleanup."""
        self.resources[name] = resource
        if cleanup_callback:
            self._cleanup_callbacks[name] = cleanup_callback

    async def cleanup_resource(self, name: str):
        """Clean up a specific resource."""
        if name in self.resources:
            resource = self.resources.pop(name)
            cleanup_callback = self._cleanup_callbacks.pop(name, None)

            try:
                if cleanup_callback:
                    if asyncio.iscoroutinefunction(cleanup_callback):
                        await cleanup_callback(resource)
                    else:
                        cleanup_callback(resource)
                elif hasattr(resource, 'close'):
                    if asyncio.iscoroutinefunction(resource.close):
                        await resource.close()
                    else:
                        resource.close()
            except Exception as e:
                logger.warning(f"Error cleaning up resource {name}: {e}")

    async def cleanup_all(self):
        """Clean up all registered resources."""
        for name in list(self.resources.keys()):
            await self.cleanup_resource(name)

    def get_resource(self, name: str) -> Any:
        """Get a registered resource."""
        return self.resources.get(name)


@asynccontextmanager
async def async_context(*resources: AsyncContextManager):
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