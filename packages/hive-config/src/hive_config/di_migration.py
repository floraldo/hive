"""
Dependency Injection Migration for Hive Configuration

This module provides migration utilities for replacing the global configuration
singleton with proper dependency injection while maintaining backward compatibility.
"""

import warnings
from typing import Optional, Any, Dict
from pathlib import Path

# Import original singleton
from .unified_config import HiveConfig, _config_instance, load_config as original_load_config


def create_injectable_config_loader():
    """
    Create an injectable configuration loader that can replace the singleton

    This provides a bridge between the old singleton pattern and the new DI pattern.
    """
    try:
        from hive_di.migration import GlobalContainerManager
        from hive_di.interfaces import IConfigurationService

        def get_config_via_di():
            """Get configuration via dependency injection"""
            container = GlobalContainerManager.get_global_container()
            return container.resolve(IConfigurationService)

        return get_config_via_di

    except ImportError:
        # DI framework not available, fall back to original implementation
        return None


def migrate_get_config():
    """
    Create a migrated version of get_config that uses DI when available

    This function maintains backward compatibility while enabling migration to DI.
    """
    di_loader = create_injectable_config_loader()

    def get_config_migrated() -> HiveConfig:
        """
        Get configuration using DI if available, otherwise fall back to singleton
        """
        if di_loader:
            warnings.warn(
                "Using global get_config() is deprecated. "
                "Use dependency injection to get IConfigurationService instead.",
                DeprecationWarning,
                stacklevel=2
            )
            try:
                di_config = di_loader()
                # Convert DI config to legacy HiveConfig format
                return _convert_di_config_to_legacy(di_config)
            except Exception:
                # Fall back to singleton if DI fails
                pass

        # Use original singleton implementation
        return original_load_config()

    return get_config_migrated


def _convert_di_config_to_legacy(di_config) -> HiveConfig:
    """
    Convert DI configuration service to legacy HiveConfig format

    This provides compatibility between the new DI configuration and the old format.
    """
    try:
        # Get configuration data from DI service
        db_config = di_config.get_database_config()
        claude_config = di_config.get_claude_config()
        event_config = di_config.get_event_bus_config()
        error_config = di_config.get_error_reporting_config()
        climate_config = di_config.get_climate_config()

        # Create legacy HiveConfig instance
        legacy_config = HiveConfig()

        # Map DI config to legacy format
        if hasattr(legacy_config, 'database'):
            legacy_config.database.min_connections = db_config.get('min_connections', 2)
            legacy_config.database.max_connections = db_config.get('max_connections', 10)
            legacy_config.database.connection_timeout = db_config.get('connection_timeout', 30.0)

        # Add other configuration mappings as needed
        return legacy_config

    except Exception:
        # If conversion fails, create default config
        return HiveConfig()


def patch_config_singleton():
    """
    Patch the global configuration singleton to use DI

    This replaces the global functions with DI-aware versions.
    """
    import sys

    # Get the unified_config module
    config_module = sys.modules.get('hive_config.unified_config')
    if config_module:
        # Replace the load_config function
        migrated_loader = migrate_get_config()
        config_module.load_config = migrated_loader

        # Also replace any direct get_config imports
        config_module.get_config = migrated_loader


def create_di_compatible_config(config_path: Optional[Path] = None,
                               use_environment: bool = True) -> Dict[str, Any]:
    """
    Create a configuration dictionary compatible with the DI framework

    Args:
        config_path: Optional path to configuration file
        use_environment: Whether to override with environment variables

    Returns:
        Configuration dictionary for DI services
    """
    # Load using original method
    legacy_config = original_load_config(config_path, use_environment)

    # Convert to DI format
    di_config = {
        'database': {
            'min_connections': getattr(legacy_config.database, 'min_connections', 2),
            'max_connections': getattr(legacy_config.database, 'max_connections', 10),
            'connection_timeout': getattr(legacy_config.database, 'connection_timeout', 30.0),
            'database_path': getattr(legacy_config.database, 'database_path', None)
        },
        'claude': {
            'mock_mode': getattr(legacy_config.claude, 'mock_mode', False),
            'timeout': getattr(legacy_config.claude, 'timeout', 30.0),
            'rate_limit_requests': getattr(legacy_config.claude, 'rate_limit_requests', 100),
            'rate_limit_window': getattr(legacy_config.claude, 'rate_limit_window', 60),
            'api_key': getattr(legacy_config.claude, 'api_key', None)
        },
        'event_bus': {
            'max_events_in_memory': 1000,
            'event_retention_days': 30,
            'enable_async': True
        },
        'error_reporting': {
            'max_errors_in_memory': 500,
            'error_retention_days': 90,
            'enable_email_alerts': False,
            'alert_email': None
        },
        'climate': {
            'default_adapter': 'meteostat',
            'cache_enabled': True,
            'cache_ttl': 3600,
            'max_parallel_requests': 5
        }
    }

    return di_config


# Migration helper for applications
def setup_config_di_migration():
    """
    Set up configuration dependency injection migration

    This should be called early in application startup to enable DI migration.
    """
    try:
        from hive_di.migration import GlobalContainerManager
        from hive_di.interfaces import IConfigurationService
        from hive_di.services import ConfigurationService

        # Create DI configuration
        di_config_data = create_di_compatible_config()

        # Create DI container if not exists
        container = GlobalContainerManager.get_global_container()

        # Register configuration service if not already registered
        if not container.is_registered(IConfigurationService):
            config_service = ConfigurationService(config_source=di_config_data)
            container.register_instance(IConfigurationService, config_service)

        # Patch the singleton
        patch_config_singleton()

        return True

    except ImportError:
        # DI framework not available
        return False


# Backward compatibility wrapper
class DICompatibleHiveConfig:
    """
    Wrapper that makes DI configuration service compatible with legacy HiveConfig interface

    This allows existing code to continue working while using DI under the hood.
    """

    def __init__(self, di_config_service):
        """
        Initialize with DI configuration service

        Args:
            di_config_service: Instance of IConfigurationService from DI framework
        """
        self._di_config = di_config_service

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration (legacy interface)"""
        return self._di_config.get_database_config()

    def get_claude_config(self) -> Dict[str, Any]:
        """Get Claude configuration (legacy interface)"""
        return self._di_config.get_claude_config()

    def get_event_bus_config(self) -> Dict[str, Any]:
        """Get event bus configuration (legacy interface)"""
        return self._di_config.get_event_bus_config()

    def get_error_reporting_config(self) -> Dict[str, Any]:
        """Get error reporting configuration (legacy interface)"""
        return self._di_config.get_error_reporting_config()

    def get_climate_config(self) -> Dict[str, Any]:
        """Get climate configuration (legacy interface)"""
        return self._di_config.get_climate_config()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (legacy interface)"""
        return self._di_config.get(key, default)

    def reload(self) -> None:
        """Reload configuration (legacy interface)"""
        self._di_config.reload()

    @property
    def database(self):
        """Database configuration property (legacy interface)"""
        return _DictAsObject(self._di_config.get_database_config())

    @property
    def claude(self):
        """Claude configuration property (legacy interface)"""
        return _DictAsObject(self._di_config.get_claude_config())


class _DictAsObject:
    """Helper class to make dictionary accessible as object attributes"""

    def __init__(self, data: Dict[str, Any]):
        self.__dict__.update(data)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")