"""
Configuration bridge between EcoSystemiser and Hive platform.

This module provides integration between EcoSystemiser's domain-specific
configuration and the unified Hive configuration system, following the
inherit→extend pattern.
"""

from __future__ import annotations

from ecosystemiser.settings import Settings as EcoSystemiserSettings
from hive_config import DatabaseConfig as HiveDatabaseConfig
from hive_config import HiveConfig, create_config_from_sources
from hive_logging import get_logger

logger = get_logger(__name__)


class EcoSystemiserConfig:
    """
    Configuration bridge that inherits from Hive platform and extends with
    domain-specific EcoSystemiser settings.

    Follows the inherit→extend pattern:
    - Inherits: Core platform settings (database, logging, etc.) from hive-config
    - Extends: Domain-specific settings (climate adapters, solvers, etc.)
    """

    def __init__(self, hive_config: HiveConfig | None = None):
        # Inherit platform configuration (with dependency injection)
        # Use create_config_from_sources() instead of deprecated get_config()
        self._hive_config = hive_config or create_config_from_sources()

        # Extend with domain-specific configuration
        self._eco_config = EcoSystemiserSettings()

    @property
    def database(self) -> HiveDatabaseConfig:
        """Platform database configuration (inherited)"""
        return self._hive_config.database

    @property
    def climate_adapters(self):
        """Domain-specific climate adapter configuration (extended)"""
        return self._eco_config.profile_loader

    @property
    def solver(self):
        """Domain-specific solver configuration (extended)"""
        return self._eco_config.solver

    @property
    def cache(self):
        """Domain-specific cache configuration (extended)"""
        return self._eco_config.cache

    @property
    def http(self):
        """Domain-specific HTTP configuration (extended)"""
        return self._eco_config.http

    @property
    def observability(self):
        """Domain-specific observability configuration (extended)"""
        return self._eco_config.observability

    @property
    def api(self):
        """Domain-specific API configuration (extended)"""
        return self._eco_config.api

    @property
    def features(self):
        """Domain-specific feature flags (extended)"""
        return self._eco_config.features

    def is_adapter_enabled(self, adapter_name: str) -> bool:
        """Check if a climate adapter is enabled"""
        return self._eco_config.is_adapter_enabled(adapter_name)

    def get_adapter_config(self, adapter_name: str) -> dict:
        """Get configuration for a specific adapter"""
        return self._eco_config.get_adapter_config(adapter_name)

    def get_database_manager(self):
        """Get database manager using hive-db patterns"""
        # Import here to avoid circular dependencies
        try:
            from hive_db import create_database_manager

            return create_database_manager(self.database)
        except ImportError:
            logger.warning("hive-db not available, using fallback database access")
            return None


# Singleton instance following hive patterns
_config: EcoSystemiserConfig | None = None


def get_ecosystemiser_config() -> EcoSystemiserConfig:
    """Get singleton EcoSystemiser configuration instance"""
    global _config

    if _config is None:
        _config = EcoSystemiserConfig()
        logger.info("EcoSystemiser configuration bridge initialized")

    return _config


def reload_ecosystemiser_config() -> EcoSystemiserConfig:
    """Force reload configuration (useful for testing)"""
    global _config
    _config = EcoSystemiserConfig()
    logger.info("EcoSystemiser configuration bridge reloaded")
    return _config
