"""
Async Configuration Management for High-Performance Applications

Provides non-blocking configuration loading with concurrent file I/O
optional hot-reload capability, and caching.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os

# Optional watchdog import for hot-reload functionality
try:
    from watchdog.events import FileModifiedEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None
    FileModifiedEvent = None

from hive_logging import get_logger

from .secure_config import SecureConfigLoader

logger = get_logger(__name__)


class ConfigFileHandler:
    """Handle configuration file changes for hot-reload"""

    def __init__(self, callback) -> None:
        """Initialize with callback function"""
        if not WATCHDOG_AVAILABLE:
            raise ImportError(
                "watchdog package is required for hot-reload functionality. Install with: pip install watchdog",
            )

        # Only inherit from FileSystemEventHandler if watchdog is available
        self.__class__.__bases__ = (FileSystemEventHandler,)
        super().__init__()

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
    - Optional hot-reload capability (requires watchdog package)
    - Secure encrypted configuration support
    - Configuration caching and validation
    """

    def __init__(
        self,
        enable_hot_reload: bool = False,
        cache_configs: bool = True,
        secure_loader: SecureConfigLoader | None = None,
    ):
        """
        Initialize async configuration loader

        Args:
            enable_hot_reload: Enable file watching for configuration changes,
                              (requires watchdog package)
            cache_configs: Enable configuration caching for performance,
            secure_loader: SecureConfigLoader instance for encrypted configs,
        """
        self.enable_hot_reload = enable_hot_reload
        self.cache_configs = cache_configs
        self.secure_loader = secure_loader or SecureConfigLoader()

        # Configuration cache
        self._config_cache: dict[str, dict[str, Any]] = ({},)
        self._file_timestamps: dict[str, float] = {}

        # Hot-reload infrastructure (only if enabled and available)
        self._observer: Observer | None = (None,)
        self._watched_paths: set[str] = (set(),)
        self._reload_callbacks: list[callable] = []

        # Validate hot-reload capability
        if self.enable_hot_reload and not WATCHDOG_AVAILABLE:
            logger.warning(
                "Hot-reload requested but watchdog package not available. ",
                "Install with: pip install watchdog. Disabling hot-reload.",
            )
            self.enable_hot_reload = False

    async def load_config_async(self, config_path: Path, config_type: str = "env") -> dict[str, Any]:
        """
        Load configuration file asynchronously

        Args:
            config_path: Path to configuration file
            config_type: Type of config file ("env", "json", "yaml")

        Returns:
            Dictionary of configuration values
        """
        config_key = str(config_path)

        # Check cache first (if enabled)
        if self.cache_configs and await self._is_cache_valid_async(config_path):
            logger.debug(f"Using cached config for {config_path}")
            return self._config_cache.get(config_key, {})

        logger.debug(f"Loading config from {config_path}")

        try:
            # Check if file exists
            if not await aiofiles.os.path.exists(config_path):
                logger.warning(f"Config file not found: {config_path}")
                return {}

            # Load based on config type
            if config_type == "env" or config_path.suffix in [".env", ".encrypted"]:
                config = await self._load_env_config_async(config_path)
            elif config_type == "json" or config_path.suffix == ".json":
                config = await self._load_json_config_async(config_path)
            elif config_type == "yaml" or config_path.suffix in [".yaml", ".yml"]:
                config = await self._load_yaml_config_async(config_path)
            else:
                # Default to env format
                config = await self._load_env_config_async(config_path)

            # Cache the result
            if self.cache_configs:
                self._config_cache[config_key] = config
                stat = await aiofiles.os.stat(config_path)
                self._file_timestamps[config_key] = stat.st_mtime

            # Setup hot-reload if enabled
            if self.enable_hot_reload:
                await self._setup_file_watching_async(config_path)

            return config

        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return {}

    async def _load_env_config_async(self, config_path: Path) -> dict[str, Any]:
        """Load environment-style configuration file"""
        config = {}

        try:
            # Check if encrypted
            if ".encrypted" in str(config_path) or config_path.suffix == ".encrypted":
                # Use secure loader for encrypted files
                content = self.secure_loader.decrypt_file(config_path)
            else:
                # Read plain text file
                async with aiofiles.open(config_path) as f:
                    content = await f.read()

            # Parse env format
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip().strip('"').strip("'")

        except Exception as e:
            logger.error(f"Failed to load env config: {e}")

        return config

    async def _load_json_config_async(self, config_path: Path) -> dict[str, Any]:
        """Load JSON configuration file"""
        try:
            async with aiofiles.open(config_path) as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load JSON config: {e}")
            return {}

    async def _load_yaml_config_async(self, config_path: Path) -> dict[str, Any]:
        """Load YAML configuration file"""
        try:
            # YAML support is optional
            import yaml

            async with aiofiles.open(config_path) as f:
                content = await f.read()
                return yaml.safe_load(content) or {}
        except ImportError:
            logger.error("PyYAML package required for YAML config support")
            return {}
        except Exception as e:
            logger.error(f"Failed to load YAML config: {e}")
            return {}

    async def load_multiple_configs_async(self, config_paths: list[Path]) -> dict[str, Any]:
        """
        Load multiple configuration files concurrently

        Args:
            config_paths: List of configuration file paths

        Returns:
            Merged configuration dictionary (later files override earlier)
        """
        # Create concurrent loading tasks
        tasks = [self.load_config_async(path) for path in config_paths]

        # Wait for all configs to load
        config_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge configurations
        merged_config = {}
        for i, result in enumerate(config_results):
            if isinstance(result, Exception):
                logger.error(f"Failed to load config {config_paths[i]}: {result}")
                continue

            if isinstance(result, dict):
                merged_config.update(result)
                logger.debug(f"Merged config from {config_paths[i]}")

        return merged_config

    async def _is_cache_valid_async(self, config_path: Path) -> bool:
        """Check if cached configuration is still valid"""
        config_key = str(config_path)

        if config_key not in self._config_cache:
            return False

        try:
            stat = await aiofiles.os.stat(config_path)
            cached_mtime = self._file_timestamps.get(config_key, 0)
            return stat.st_mtime <= cached_mtime
        except Exception:
            return False

    async def _setup_file_watching_async(self, config_path: Path) -> None:
        """Setup file watching for hot-reload (if enabled and available)"""
        if not self.enable_hot_reload or not WATCHDOG_AVAILABLE:
            return

        path_str = str(config_path.parent)

        if path_str in self._watched_paths:
            return

        try:
            if self._observer is None:
                self._observer = Observer()
                self._observer.start()
                logger.debug("Started configuration file observer")

            # Create event handler
            handler = ConfigFileHandler(self._on_config_change_async)

            # Watch the directory
            self._observer.schedule(handler, path_str, recursive=False)
            self._watched_paths.add(path_str)

            logger.debug(f"Watching directory for config changes: {path_str}")

        except Exception as e:
            logger.error(f"Failed to setup file watching: {e}")

    async def _on_config_change_async(self, file_path: str) -> None:
        """Handle configuration file changes"""
        logger.info(f"Configuration file changed: {file_path}")

        # Clear cache for changed file
        if str(file_path) in self._config_cache:
            del self._config_cache[str(file_path)]
            logger.debug(f"Cleared cache for {file_path}")

        # Notify callbacks
        for callback in self._reload_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(file_path)
                else:
                    callback(file_path)
            except Exception as e:
                logger.error(f"Error in reload callback: {e}")

    def add_reload_callback(self, callback: callable) -> None:
        """Add callback to be called when configuration files change"""
        if not self.enable_hot_reload:
            logger.warning("Hot-reload not enabled, callback will not be triggered")
            return

        self._reload_callbacks.append(callback)
        logger.debug("Added configuration reload callback")

    def clear_cache(self) -> None:
        """Clear all cached configurations"""
        self._config_cache.clear()
        self._file_timestamps.clear()
        logger.debug("Cleared configuration cache")

    def stop_watching(self) -> None:
        """Stop file watching and cleanup resources"""
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()
            self._observer = None
            self._watched_paths.clear()
            logger.debug("Stopped configuration file watching")

    def __del__(self) -> None:
        """Cleanup on garbage collection"""
        self.stop_watching()


# Factory function for easy instantiation
def create_async_config_loader(
    enable_hot_reload: bool = False, cache_configs: bool = True, master_key: str | None = None,
) -> AsyncConfigLoader:
    """
    Create an AsyncConfigLoader with optional secure configuration support

    Args:
        enable_hot_reload: Enable file watching (requires watchdog package),
        cache_configs: Enable configuration caching,
        master_key: Master key for encrypted configuration files

    Returns:
        Configured AsyncConfigLoader instance
    """
    secure_loader = SecureConfigLoader(master_key) if master_key else None

    loader = AsyncConfigLoader(
        enable_hot_reload=enable_hot_reload, cache_configs=cache_configs, secure_loader=secure_loader,
    )

    if enable_hot_reload and not WATCHDOG_AVAILABLE:
        logger.warning("Hot-reload requested but watchdog not available. Install with: pip install watchdog")

    return loader


# Async utility functions
async def load_app_config_async(app_name: str, project_root: Path, enable_hot_reload: bool = False) -> dict[str, Any]:
    """
    Load application configuration with standard fallback hierarchy

    Loads in order (later configs override earlier):
    1. Global .env
    2. Global .env.prod (if exists)
    3. Global .env.prod.encrypted (if master key available)
    4. App-specific .env
    5. App-specific .env.prod (if exists)
    6. App-specific .env.prod.encrypted (if master key available)

    Args:
        app_name: Name of the application
        project_root: Root directory of the project
        enable_hot_reload: Enable configuration hot-reload

    Returns:
        Merged configuration dictionary
    """
    loader = create_async_config_loader(enable_hot_reload=enable_hot_reload)

    # Define config file hierarchy
    app_dir = project_root / "apps" / app_name
    config_paths = [
        project_root / ".env",
        project_root / ".env.prod",
        project_root / ".env.prod.encrypted",
        app_dir / ".env",
        app_dir / ".env.prod",
        app_dir / ".env.prod.encrypted",
    ]

    # Filter to existing files
    existing_paths = []
    for path in config_paths:
        if await aiofiles.os.path.exists(path):
            existing_paths.append(path)

    if not existing_paths:
        logger.warning(f"No configuration files found for app {app_name}")
        return {}

    logger.debug(f"Loading configs for {app_name}: {[str(p) for p in existing_paths]}")
    return await loader.load_multiple_configs_async(existing_paths)
