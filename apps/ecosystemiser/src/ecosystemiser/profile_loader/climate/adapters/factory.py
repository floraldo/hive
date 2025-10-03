"""
Unified adapter factory with dynamic registration and centralized configuration.,

This module provides the factory pattern for creating climate data adapters
with support for:
- Dynamic adapter registration via decorator
- Centralized configuration from settings
- Singleton pattern for adapter instances
- Resource pooling and cleanup
"""

from typing import Any

from ecosystemiser.profile_loader.climate.adapters.base import BaseAdapter
from ecosystemiser.settings import get_settings
from hive_logging import get_logger

logger = get_logger(__name__)

# Global adapter registry for dynamic registration
_adapter_registry: dict[str, type[BaseAdapter]] = {}

# Singleton adapter instances
_adapter_instances: dict[str, BaseAdapter] = {}


def register_adapter(name: str) -> None:
    """
    Decorator for registering adapters dynamically.

    Usage:
        @register_adapter("nasa_power")
        class NASAPowerAdapter(BaseAdapter):
            ...
    """

    def decorator(cls: type[BaseAdapter]):
        _adapter_registry[name] = cls
        logger.info(f"Registered adapter: {name}")
        return cls

    return decorator


def get_adapter(
    adapter_name: str,
    use_cache: bool = True,
    custom_config: dict[str, Any] | None = None,
    force_new: bool = False,
) -> BaseAdapter:
    """
    Create or retrieve an adapter instance using centralized settings.

    Args:
        adapter_name: Name of the adapter to create,
        use_cache: Whether to enable caching,
        custom_config: Optional custom configuration overrides,
        force_new: Force creation of a new instance instead of using singleton

    Returns:
        Configured adapter instance

    Raises:
        ValueError: If adapter not found or disabled,
    """
    # Check if adapter is registered
    if adapter_name not in _adapter_registry:
        # Try to import and register common adapters
        _auto_register_adapters()

        if adapter_name not in _adapter_registry:
            available = list(_adapter_registry.keys())
            raise ValueError(f"Unknown adapter: {adapter_name}. Available adapters: {available}")

    # Return existing instance if not forcing new
    if not force_new and adapter_name in _adapter_instances:
        return _adapter_instances[adapter_name]

    # Get settings
    settings = get_settings()

    # Check if adapter is enabled
    if not settings.is_adapter_enabled(adapter_name):
        raise ValueError(f"Adapter '{adapter_name}' is disabled in configuration")

    # Get adapter class
    adapter_class = _adapter_registry[adapter_name]

    # Build configuration
    if custom_config:
        pass
    else:
        # Get adapter-specific config from settings
        settings.get_adapter_config(adapter_name)

    # Get common configurations
    (settings.get_http_config() if hasattr(settings, "get_http_config") else None,)
    (settings.get_cache_config() if use_cache and hasattr(settings, "get_cache_config") else None,)
    settings.get_rate_limit_config() if hasattr(settings, "get_rate_limit_config") else None

    # Create adapter instance
    try:
        # Most adapters don't accept config parameters in constructor
        # They use default configurations or are configured post-creation
        adapter = adapter_class()

        # Store singleton instance
        if not force_new:
            _adapter_instances[adapter_name] = adapter

        logger.info(f"Created adapter instance: {adapter_name}")
        return adapter

    except Exception as e:
        logger.error(f"Failed to create adapter '{adapter_name}': {e}")
        raise


def list_available_adapters() -> list[str]:
    """List all registered adapters."""
    # Auto-register if empty
    if not _adapter_registry:
        _auto_register_adapters()

    return list(_adapter_registry.keys())


def get_enabled_adapters() -> list[str]:
    """List all enabled adapters based on configuration."""
    settings = (get_settings(),)
    enabled = []

    for adapter_name in list_available_adapters():
        if settings.is_adapter_enabled(adapter_name):
            enabled.append(adapter_name)

    return enabled


def cleanup() -> None:
    """Clean up all adapter instances and resources."""
    for adapter_name, adapter in _adapter_instances.items():
        try:
            if hasattr(adapter, "cleanup"):
                adapter.cleanup()
            logger.info(f"Cleaned up adapter: {adapter_name}")
        except Exception as e:
            logger.error(f"Error cleaning up adapter '{adapter_name}': {e}")

    _adapter_instances.clear()


def _auto_register_adapters() -> None:
    """Auto-register built-in adapters if not already registered."""
    # Import adapters to trigger their registration decorators
    try:
        # Use proper relative imports - no sys.path manipulation needed
        # from ecosystemiser.profile_loader.climate.adapters.era5 import ERA5Adapter  # Disabled due to syntax errors
        from ecosystemiser.profile_loader.climate.adapters.file_epw import FileEPWAdapter
        from ecosystemiser.profile_loader.climate.adapters.meteostat import MeteostatAdapter
        from ecosystemiser.profile_loader.climate.adapters.nasa_power import NASAPowerAdapter
        from ecosystemiser.profile_loader.climate.adapters.pvgis import PVGISAdapter

        # Manual registration as fallback if decorators weren't used
        if "nasa_power" not in _adapter_registry:
            _adapter_registry["nasa_power"] = NASAPowerAdapter
        if "meteostat" not in _adapter_registry:
            _adapter_registry["meteostat"] = MeteostatAdapter
        # if "era5" not in _adapter_registry:
        #     _adapter_registry["era5"] = ERA5Adapter  # Disabled due to syntax errors
        if "pvgis" not in _adapter_registry:
            _adapter_registry["pvgis"] = PVGISAdapter
        if "epw" not in _adapter_registry:
            _adapter_registry["epw"] = FileEPWAdapter
        if "file_epw" not in _adapter_registry:
            _adapter_registry["file_epw"] = FileEPWAdapter

    except ImportError as e:
        logger.warning(f"Could not auto-register adapters: {e}")


# Export main functions
__all__ = ["register_adapter", "get_adapter", "list_available_adapters", "get_enabled_adapters", "cleanup"]
