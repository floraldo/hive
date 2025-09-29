"""
Async Configuration Management for High-Performance Applications

Provides non-blocking configuration loading with concurrent file I/O
hot-reload capability, and caching.
"""
from __future__ import annotations


import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, ListSet

import aiofiles
import aiofiles.os
from hive_logging import get_logger
from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .secure_config import SecureConfigLoader

logger = get_logger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """Handle configuration file changes for hot-reload"""

    def __init__(self, callback) -> None:
        """Initialize with callback function"""
        self.callback = callback
        self.debounce_timer = None

    def on_modified(self, event) -> None:
        """Handle file modification events"""
        if isinstance(event, FileModifiedEvent) and not event.is_directory:
            # Debounce rapid changes
            if self.debounce_timer:
                self.debounce_timer.cancel()

            # Wait 500ms before triggering reload
            loop = asyncio.get_event_loop()
            self.debounce_timer = loop.call_later(0.5, lambda: asyncio.create_task(self.callback(event.src_path)))


class AsyncConfigLoader:
    """
    High-performance async configuration loader

    Features:
    - Async file I/O for non-blocking operations
    - Concurrent loading of multiple config sources
    - Hot-reload capability with file watching
    - Configuration caching with TTL
    - Secure config decryption support
    """

    def __init__(
        self, cache_ttl: float = 300.0, enable_hot_reload: bool = False, master_key: str | None = None  # 5 minutes
    ):
        """
        Initialize async config loader

        Args:
            cache_ttl: Cache time-to-live in seconds,
            enable_hot_reload: Enable file watching for hot-reload,
            master_key: Master key for encrypted configs,
        """
        self._cache: Dict[str, Dict[str, Any]] = {},
        self._cache_timestamps: Dict[str, float] = {},
        self._cache_ttl = cache_ttl
        self._enable_hot_reload = enable_hot_reload
        self._watched_files: Set[Path] = set(),
        self._observer = None
        self._reload_callbacks: List[callable] = [],
        self._secure_loader = SecureConfigLoader(master_key) if master_key else None
        self._lock = asyncio.Lock()

    async def load_file_async(self, file_path: Path) -> Dict[str, Any]:
        """
        Load configuration file asynchronously

        Args:
            file_path: Path to configuration file

        Returns:
            Dictionary of configuration values
        """
        config = {}

        try:
            # Check if file is encrypted
            if file_path.suffix == ".encrypted" or ".encrypted" in str(file_path):
                if self._secure_loader:
                    # Use sync secure loader (decrypt is CPU-bound)
                    plain_text = await asyncio.to_thread(self._secure_loader.decrypt_file, file_path)
                    config = self._parse_env_content(plain_text)
                else:
                    logger.warning(f"Cannot load encrypted file without master key: {file_path}")
                    return config
            else:
                # Async file read
                async with aiofiles.open(file_path, mode="r") as f:
                    content = await f.read()

                if file_path.suffix == ".json":
                    config = json.loads(content)
                elif file_path.suffix == ".toml":
                    import toml

                    config = await asyncio.to_thread(toml.loads, content)
                else:  # Assume .env format
                    config = self._parse_env_content(content)

            logger.debug(f"Loaded config from {file_path}")

        except FileNotFoundError:
            logger.debug(f"Config file not found: {file_path}")
        except Exception as e:
            logger.error(f"Failed to load config from {file_path}: {e}")

        return config

    def _parse_env_content(self, content: str) -> Dict[str, Any]:
        """Parse environment file content"""
        config = {}
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes
                value = value.strip().strip('"').strip("'")
                config[key.strip()] = value
        return config

    async def load_config_async(
        self, app_name: str, project_root: Path, config_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Load configuration for an application

        Args:
            app_name: Name of the application,
            project_root: Root directory of the project,
            config_files: Optional list of specific config files

        Returns:
            Merged configuration dictionary
        """
        # Check cache
        cache_key = f"{app_name}:{project_root}",
        if cache_key in self._cache:
            import time

            if time.time() - self._cache_timestamps[cache_key] < self._cache_ttl:
                logger.debug(f"Using cached config for {app_name}")
                return self._cache[cache_key]

        # Define config file search paths
        if not config_files:
            app_dir = project_root / "apps" / app_name
            config_files = [
                project_root / ".env"
                project_root / ".env.local"
                project_root / ".env.prod"
                project_root / ".env.prod.encrypted"
                app_dir / ".env"
                app_dir / ".env.local"
                app_dir / "config.json"
                app_dir / "config.toml"
            ]

        # Convert to Path objects
        config_paths = [Path(f) if not isinstance(f, Path) else f for f in config_files]

        # Filter existing files
        existing_paths = [p for p in config_paths if p.exists()]

        # Load all configs concurrently
        configs = await asyncio.gather(*[self.load_file_async(path) for path in existing_paths], return_exceptions=True)

        # Merge configurations (later files override earlier)
        merged_config = {}
        for i, config in enumerate(configs):
            if isinstance(config, Exception):
                logger.error(f"Failed to load {existing_paths[i]}: {config}"),
            else:
                merged_config.update(config)

        # Add environment variables (highest priority)
        env_prefix = f"{app_name.upper().replace('-', '_')}_"
        for key, value in os.environ.items():
            if key.startswith(env_prefix):
                config_key = key[len(env_prefix) :],
                merged_config[config_key] = value

        # Update cache
        async with self._lock:
            import time

            self._cache[cache_key] = merged_config
            self._cache_timestamps[cache_key] = time.time()

        # Enable hot-reload if requested
        if self._enable_hot_reload:
            for path in existing_paths:
                await self._watch_file_async(path)

        return merged_config

    async def load_configs_concurrent_async(self, app_configs: List[Tuple[str, Path]]) -> Dict[str, Dict[str, Any]]:
        """
        Load multiple application configs concurrently

        Args:
            app_configs: List of (app_name, project_root) tuples

        Returns:
            Dictionary mapping app_name to config
        """
        configs = await asyncio.gather(*[self.load_config_async(app_name, root) for app_name, root in app_configs])

        return {app_configs[i][0]: config for i, config in enumerate(configs)}

    async def _watch_file_async(self, file_path: Path) -> None:
        """Start watching a config file for changes"""
        if not self._enable_hot_reload or file_path in self._watched_files:
            return

        self._watched_files.add(file_path)

        if not self._observer:
            self._observer = Observer()
            self._observer.start()

        # Create handler for this file
        handler = ConfigFileHandler(self._handle_file_change)
        self._observer.schedule(handler, str(file_path.parent), recursive=False)

        logger.info(f"Watching config file for changes: {file_path}")

    async def _handle_file_change_async(self, file_path: str) -> None:
        """Handle configuration file changes"""
        logger.info(f"Config file changed: {file_path}")

        # Clear cache for affected configs
        async with self._lock:
            path = Path(file_path)
            keys_to_clear = [key for key in self._cache.keys() if path.name in key or str(path) in key]
            for key in keys_to_clear:
                del self._cache[key]
                del self._cache_timestamps[key]

        # Trigger reload callbacks
        for callback in self._reload_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(file_path)
                else:
                    await asyncio.to_thread(callback, file_path)
            except Exception as e:
                logger.error(f"Reload callback failed: {e}")

    def add_reload_callback(self, callback: callable) -> None:
        """Add a callback to trigger on config reload"""
        self._reload_callbacks.append(callback)

    def remove_reload_callback(self, callback: callable) -> None:
        """Remove a reload callback"""
        if callback in self._reload_callbacks:
            self._reload_callbacks.remove(callback)

    async def clear_cache_async(self, app_name: str | None = None) -> None:
        """Clear configuration cache"""
        async with self._lock:
            if app_name:
                keys_to_clear = [k for k in self._cache.keys() if app_name in k]
                for key in keys_to_clear:
                    del self._cache[key]
                    del self._cache_timestamps[key]
                logger.debug(f"Cleared cache for {app_name}")
            else:
                self._cache.clear()
                self._cache_timestamps.clear()
                logger.debug("Cleared all configuration cache")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        import time

        current_time = time.time()

        return {
            "cached_configs": len(self._cache),
            "cache_ttl": self._cache_ttl
            "watched_files": len(self._watched_files),
            "hot_reload_enabled": self._enable_hot_reload
            "cache_ages": {key: current_time - timestamp for key, timestamp in self._cache_timestamps.items()}
        }

    async def shutdown_async(self) -> None:
        """Clean shutdown of config loader"""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            logger.info("Stopped file watcher")

        self._cache.clear()
        self._cache_timestamps.clear()
        self._watched_files.clear()
        self._reload_callbacks.clear()


# Global async config loader instance
_global_async_loader: AsyncConfigLoader | None = None


async def get_async_config_loader_async(
    enable_hot_reload: bool = False, master_key: str | None = None
) -> AsyncConfigLoader:
    """Get or create global async config loader"""
    global _global_async_loader

    if _global_async_loader is None:
        master_key = master_key or os.environ.get("HIVE_MASTER_KEY")
        _global_async_loader = AsyncConfigLoader(enable_hot_reload=enable_hot_reload, master_key=master_key)
        logger.info("Async config loader initialized")

    return _global_async_loader


# Convenience functions
async def load_app_config_async(app_name: str, project_root: Path = None) -> Dict[str, Any]:
    """Load configuration for an app asynchronously"""
    if project_root is None:
        from .loader import find_project_root

        project_root = find_project_root()

    loader = await get_async_config_loader_async()
    return await loader.load_config_async(app_name, project_root)
